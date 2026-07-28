# Runs the EvidenceCast Streamlit evidence-ingestion, extraction and human-review interface.
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from evidencecast.cards import create_evidence_cards, overall_review_status
from evidencecast.extraction import ExtractionError, extract_source
from evidencecast.storage import (
    B2EvidenceStore,
    B2Settings,
    StorageConfigurationError,
    StorageOperationError,
)

load_dotenv(REPOSITORY_ROOT / ".env", override=True)

st.set_page_config(
    page_title="EvidenceCast AI",
    page_icon="📚",
    layout="wide",
)

STATUS_OPTIONS = ["pending", "approved", "rejected"]
SESSION_DEFAULTS = {
    "source_bundle": None,
    "extraction": None,
    "evidence_cards": None,
    "review_uri": None,
}
for session_key, default_value in SESSION_DEFAULTS.items():
    if session_key not in st.session_state:
        st.session_state[session_key] = default_value


def _create_store() -> B2EvidenceStore:
    return B2EvidenceStore(B2Settings.from_environment())


def _normalise_editor_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    rows = frame.where(pd.notna(frame), None).to_dict(orient="records")
    timestamp = datetime.now(UTC).isoformat()
    normalised: list[dict[str, object]] = []
    for row in rows:
        status = str(row.get("status") or "pending").strip().lower()
        if status not in STATUS_OPTIONS:
            status = "pending"
        claim = str(row.get("claim") or "").strip()
        if not claim:
            raise ValueError("Every evidence card must retain a non-empty claim.")
        row["status"] = status
        row["claim"] = claim
        row["reviewer_note"] = str(row.get("reviewer_note") or "").strip()
        row["updated_at"] = timestamp
        normalised.append(row)
    return normalised


def _clear_workflow() -> None:
    for key in SESSION_DEFAULTS:
        st.session_state[key] = None


st.title("EvidenceCast AI")
st.caption(
    "Upload trusted research evidence, preserve the source in Backblaze B2, "
    "extract traceable findings and approve, reject or edit every evidence card before media generation."
)

with st.sidebar:
    st.subheader("Evidence workflow")
    st.markdown(
        "1. Upload source\n\n"
        "2. Store original in B2\n\n"
        "3. Extract report text\n\n"
        "4. Create evidence cards\n\n"
        "5. Human review"
    )
    try:
        settings = B2Settings.from_environment()
        st.success("B2 configuration loaded")
        st.code(f"Bucket: {settings.bucket}\nRegion: {settings.region}\nPrefix: {settings.prefix}")
    except StorageConfigurationError as exc:
        st.error(str(exc))
    if st.button("Start a new source", use_container_width=True):
        _clear_workflow()
        st.rerun()

st.header("1. Upload and process a source")
uploaded_file = st.file_uploader(
    "Choose a PDF, Markdown or plain-text research document",
    type=["pdf", "txt", "md", "markdown"],
    help="The original bytes are stored in your private Backblaze B2 bucket before review begins.",
)
maximum_cards = st.slider("Maximum evidence-card candidates", 3, 20, 10)

if st.button("Store, extract and create evidence cards", type="primary", disabled=uploaded_file is None):
    assert uploaded_file is not None
    source_bytes = uploaded_file.getvalue()
    if not source_bytes:
        st.error("The selected file is empty.")
    else:
        try:
            with st.status("Processing evidence source", expanded=True) as status:
                st.write("Validating Backblaze B2 configuration…")
                store = _create_store()

                st.write("Extracting report text while preserving page references…")
                extraction = extract_source(uploaded_file.name, uploaded_file.type, source_bytes)
                source_sha256 = store.sha256_bytes(source_bytes)

                st.write("Uploading the original source and extraction artefacts to B2…")
                source_bundle = store.store_source_bundle(
                    filename=uploaded_file.name,
                    media_type=uploaded_file.type or "application/octet-stream",
                    source_bytes=source_bytes,
                    extracted_text=extraction.full_text,
                    extraction_metadata=extraction.metadata(),
                )

                st.write("Creating deterministic evidence-card candidates…")
                cards = [
                    card.to_dict()
                    for card in create_evidence_cards(
                        extraction,
                        source_sha256=source_sha256,
                        maximum_cards=maximum_cards,
                    )
                ]
                if not cards:
                    raise ExtractionError(
                        "Text was extracted, but no reviewable evidence-card candidates were found."
                    )

                initial_review = store.store_evidence_cards(
                    source_sha256=source_sha256,
                    cards=cards,
                    review_status="pending",
                )

                st.session_state.source_bundle = source_bundle
                st.session_state.extraction = extraction
                st.session_state.evidence_cards = cards
                st.session_state.review_uri = initial_review.uri
                status.update(label="Evidence source processed", state="complete", expanded=False)
            st.success("The source, extracted text and pending evidence cards are stored in B2.")
        except (ExtractionError, StorageConfigurationError, StorageOperationError, ValueError) as exc:
            st.error(str(exc))
        except Exception as exc:
            st.exception(exc)

source_bundle = st.session_state.source_bundle
extraction = st.session_state.extraction
cards = st.session_state.evidence_cards

if source_bundle and extraction and cards:
    st.divider()
    st.header("2. Source and extraction record")
    first_column, second_column, third_column, fourth_column = st.columns(4)
    first_column.metric("File", extraction.filename)
    second_column.metric("Pages", extraction.page_count if extraction.page_count is not None else "Text")
    third_column.metric("Characters", f"{extraction.character_count:,}")
    fourth_column.metric("Cards", len(cards))

    st.code(
        "\n".join(
            [
                f"Source SHA-256: {source_bundle['source_sha256']}",
                f"Original: {source_bundle['original']['uri']}",
                f"Extracted text: {source_bundle['extracted_text']['uri']}",
                f"Extraction metadata: {source_bundle['extraction_metadata_uri']}",
            ]
        )
    )

    with st.expander("Preview extracted report text"):
        st.text_area(
            "Extracted text",
            extraction.full_text,
            height=320,
            disabled=True,
            label_visibility="collapsed",
        )

    st.divider()
    st.header("3. Approve, reject or edit evidence cards")
    st.info(
        "Edit the claim directly, select Approved or Rejected, and record a reviewer note. "
        "Source excerpts and page references are locked to preserve traceability."
    )

    editor_frame = pd.DataFrame(cards)
    ordered_columns = [
        "status",
        "claim",
        "evidence_type",
        "page_number",
        "reviewer_note",
        "source_excerpt",
        "card_id",
        "created_at",
        "updated_at",
    ]
    editor_frame = editor_frame[[column for column in ordered_columns if column in editor_frame.columns]]

    reviewed_frame = st.data_editor(
        editor_frame,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "status": st.column_config.SelectboxColumn(
                "Decision",
                options=STATUS_OPTIONS,
                required=True,
                width="small",
            ),
            "claim": st.column_config.TextColumn("Editable evidence claim", width="large"),
            "evidence_type": st.column_config.TextColumn("Type", disabled=True),
            "page_number": st.column_config.NumberColumn("Page", disabled=True, format="%d"),
            "reviewer_note": st.column_config.TextColumn("Reviewer note", width="medium"),
            "source_excerpt": st.column_config.TextColumn("Locked source excerpt", disabled=True, width="large"),
            "card_id": None,
            "created_at": None,
            "updated_at": None,
        },
        key="evidence_card_editor",
    )

    decision_counts = reviewed_frame["status"].value_counts().to_dict()
    pending_count = int(decision_counts.get("pending", 0))
    approved_count = int(decision_counts.get("approved", 0))
    rejected_count = int(decision_counts.get("rejected", 0))
    count_columns = st.columns(3)
    count_columns[0].metric("Pending", pending_count)
    count_columns[1].metric("Approved", approved_count)
    count_columns[2].metric("Rejected", rejected_count)

    save_column, download_column = st.columns([1, 1])
    if save_column.button("Save reviewed evidence cards to B2", type="primary", use_container_width=True):
        try:
            reviewed_cards = _normalise_editor_rows(reviewed_frame)
            review_status = overall_review_status(reviewed_cards)
            store = _create_store()
            stored_review = store.store_evidence_cards(
                source_sha256=source_bundle["source_sha256"],
                cards=reviewed_cards,
                review_status=review_status,
            )
            st.session_state.evidence_cards = reviewed_cards
            st.session_state.review_uri = stored_review.uri
            st.success(
                f"Review saved with status '{review_status}' at {stored_review.uri}"
            )
        except (ValueError, StorageConfigurationError, StorageOperationError) as exc:
            st.error(str(exc))

    download_payload = {
        "source_sha256": source_bundle["source_sha256"],
        "review_status": overall_review_status(_normalise_editor_rows(reviewed_frame)),
        "cards": _normalise_editor_rows(reviewed_frame),
    }
    download_column.download_button(
        "Download review JSON",
        data=json.dumps(download_payload, ensure_ascii=False, indent=2),
        file_name="evidence-cards-reviewed.json",
        mime="application/json",
        use_container_width=True,
    )

    if st.session_state.review_uri:
        st.caption(f"Current B2 review record: `{st.session_state.review_uri}`")
else:
    st.info("Upload and process a source to open the evidence-card review workspace.")
