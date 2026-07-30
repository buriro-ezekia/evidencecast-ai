# Renders the EvidenceCast Day 4 narration review, audio generation and progress-streaming workspace.
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from evidencecast.audio import DEFAULT_AUDIO_MODEL, stream_narration_audio_generation
from evidencecast.audio_store import B2AudioStore
from evidencecast.narration import (
    NarrationValidationError,
    create_narration_plan,
    narration_review_status,
    normalise_reviewed_segments,
    require_all_segments_approved,
)
from evidencecast.storage import B2Settings, StorageConfigurationError, StorageOperationError

load_dotenv(REPOSITORY_ROOT / ".env", override=True)

st.set_page_config(
    page_title="EvidenceCast Narration",
    page_icon="🎙️",
    layout="wide",
)

DAY4_DEFAULTS = {
    "narration_plan": None,
    "narration_plan_uri": None,
    "narration_review_uri": None,
    "audio_events": [],
    "audio_summary": None,
    "audio_summary_uri": None,
}
for key, value in DAY4_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.title("Narration and audio generation")
st.caption(
    "Turn the approved-only storyboard into editable narration, require explicit human approval, "
    "then generate three traceable audio clips through Genblaze and Backblaze B2."
)

storyboard = st.session_state.get("storyboard")

if not storyboard:
    st.warning(
        "No storyboard is active in this Streamlit session. Open **Storyboard and images** and "
        "create the storyboard again, or load a previously downloaded storyboard JSON below."
    )
    uploaded_storyboard = st.file_uploader(
        "Load a downloaded storyboard JSON",
        type=["json"],
        help="This restores the working session without recreating the source or changing B2 records.",
    )
    if uploaded_storyboard is not None:
        try:
            loaded = json.loads(uploaded_storyboard.getvalue().decode("utf-8"))
            if loaded.get("scene_count") != 3 or loaded.get("review_mode") != "approved_only":
                raise NarrationValidationError(
                    "The uploaded JSON is not a validated approved-only three-scene storyboard."
                )
            st.session_state.storyboard = loaded
            storyboard = loaded
            st.success("Storyboard JSON loaded into the current session.")
        except (UnicodeDecodeError, json.JSONDecodeError, NarrationValidationError) as exc:
            st.error(str(exc))

if not storyboard:
    st.stop()

source_sha256 = str(storyboard["source_sha256"])
storyboard_id = str(storyboard["storyboard_id"])

summary_columns = st.columns(4)
summary_columns[0].metric("Storyboard", storyboard_id)
summary_columns[1].metric("Scenes", int(storyboard["scene_count"]))
summary_columns[2].metric("Review mode", str(storyboard["review_mode"]))
summary_columns[3].metric("Source SHA", source_sha256[:12] + "…")

st.subheader("1. Build editable narration JSON")
st.info(
    "Narration starts from the evidence-linked scene text. Edit it for natural speech without "
    "changing the supported meaning, then approve every segment before audio generation."
)

language = st.selectbox(
    "Narration language",
    options=["English (UK)", "English (US)"],
    index=0,
)
voice_style = st.text_input(
    "Voice style",
    value="clear, calm and educational",
    max_chars=160,
)

if st.button(
    "Create narration plan and save it to B2",
    type="primary",
    use_container_width=True,
):
    try:
        with st.status("Building narration plan", expanded=True) as status:
            st.write("Validating the approved-only storyboard…")
            narration_plan = create_narration_plan(
                storyboard,
                language=language,
                voice_style=voice_style,
            )
            narration_payload = narration_plan.to_dict()

            st.write("Saving the editable narration plan to B2…")
            store = B2AudioStore(B2Settings.from_environment())
            plan_object = store.store_narration_plan(
                source_sha256=source_sha256,
                storyboard_id=storyboard_id,
                narration_id=narration_plan.narration_id,
                narration_plan=narration_payload,
            )

            st.session_state.narration_plan = narration_payload
            st.session_state.narration_plan_uri = plan_object.uri
            st.session_state.narration_review_uri = None
            st.session_state.audio_events = []
            st.session_state.audio_summary = None
            st.session_state.audio_summary_uri = None
            status.update(label="Narration plan saved", state="complete", expanded=False)
        st.success("The three-segment narration plan is stored in B2 and ready for human review.")
    except (NarrationValidationError, StorageConfigurationError, StorageOperationError) as exc:
        st.error(str(exc))

narration_plan = st.session_state.narration_plan
if not narration_plan:
    st.stop()

st.code(
    "\n".join(
        [
            f"Narration ID: {narration_plan['narration_id']}",
            f"Storyboard ID: {narration_plan['storyboard_id']}",
            f"Narration plan: {st.session_state.narration_plan_uri}",
        ]
    )
)

st.subheader("2. Edit and approve narration")
editor_frame = pd.DataFrame(narration_plan["segments"])
editor_frame["evidence_card_ids"] = editor_frame["evidence_card_ids"].apply(
    lambda values: ", ".join(values) if isinstance(values, list) else str(values)
)
ordered_columns = [
    "scene_number",
    "review_status",
    "reviewed_text",
    "pronunciation_notes",
    "target_duration_seconds",
    "source_claim",
    "evidence_card_ids",
    "segment_id",
    "draft_text",
    "updated_at",
]
editor_frame = editor_frame[[column for column in ordered_columns if column in editor_frame.columns]]

reviewed_frame = st.data_editor(
    editor_frame,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "scene_number": st.column_config.NumberColumn("Scene", disabled=True, format="%d"),
        "review_status": st.column_config.SelectboxColumn(
            "Decision",
            options=["pending", "approved", "rejected"],
            required=True,
            width="small",
        ),
        "reviewed_text": st.column_config.TextColumn("Editable spoken narration", width="large"),
        "pronunciation_notes": st.column_config.TextColumn(
            "Pronunciation notes",
            width="medium",
            help="For example: pronounce XLOOKUP as 'X lookup'.",
        ),
        "target_duration_seconds": st.column_config.NumberColumn(
            "Target seconds",
            min_value=5,
            max_value=60,
            step=1,
        ),
        "source_claim": st.column_config.TextColumn("Locked evidence claim", disabled=True, width="large"),
        "evidence_card_ids": st.column_config.TextColumn("Evidence cards", disabled=True),
        "segment_id": None,
        "draft_text": None,
        "updated_at": None,
    },
    key="narration_review_editor",
)

counts = reviewed_frame["review_status"].value_counts().to_dict()
count_columns = st.columns(3)
count_columns[0].metric("Pending", int(counts.get("pending", 0)))
count_columns[1].metric("Approved", int(counts.get("approved", 0)))
count_columns[2].metric("Rejected", int(counts.get("rejected", 0)))

save_column, download_column = st.columns(2)
if save_column.button(
    "Save reviewed narration to B2",
    type="primary",
    use_container_width=True,
):
    try:
        rows = reviewed_frame.where(pd.notna(reviewed_frame), None).to_dict(orient="records")
        for row in rows:
            card_ids = row.get("evidence_card_ids", "")
            row["evidence_card_ids"] = [
                value.strip() for value in str(card_ids).split(",") if value.strip()
            ]
        normalised_segments = normalise_reviewed_segments(rows)
        review_status = narration_review_status(normalised_segments)

        updated_plan = dict(narration_plan)
        updated_plan["segments"] = normalised_segments
        updated_plan["review_status"] = review_status
        updated_plan["language"] = language
        updated_plan["voice_style"] = voice_style

        store = B2AudioStore(B2Settings.from_environment())
        review_object = store.store_narration_review(
            source_sha256=source_sha256,
            storyboard_id=storyboard_id,
            narration_id=updated_plan["narration_id"],
            segments=normalised_segments,
            review_status=review_status,
            language=language,
            voice_style=voice_style,
        )
        st.session_state.narration_plan = updated_plan
        st.session_state.narration_review_uri = review_object.uri
        st.success(f"Narration review saved with status '{review_status}' at {review_object.uri}")
    except (
        NarrationValidationError,
        StorageConfigurationError,
        StorageOperationError,
        ValueError,
    ) as exc:
        st.error(str(exc))

try:
    download_rows = reviewed_frame.where(pd.notna(reviewed_frame), None).to_dict(orient="records")
    for row in download_rows:
        row["evidence_card_ids"] = [
            value.strip()
            for value in str(row.get("evidence_card_ids", "")).split(",")
            if value.strip()
        ]
    download_segments = normalise_reviewed_segments(download_rows)
    download_payload = dict(narration_plan)
    download_payload["segments"] = download_segments
    download_payload["review_status"] = narration_review_status(download_segments)
    download_column.download_button(
        "Download narration JSON",
        data=json.dumps(download_payload, ensure_ascii=False, indent=2),
        file_name=f"{narration_plan['narration_id']}-reviewed.json",
        mime="application/json",
        use_container_width=True,
    )
except NarrationValidationError as exc:
    download_column.warning(str(exc))

if st.session_state.narration_review_uri:
    st.caption(f"Current B2 narration review: `{st.session_state.narration_review_uri}`")

saved_plan = st.session_state.narration_plan
all_approved = False
try:
    require_all_segments_approved(saved_plan["segments"])
    all_approved = True
except NarrationValidationError:
    pass

st.subheader("3. Generate three narration audio clips")
st.caption(
    "Audio generation is blocked until all three narration segments are approved and saved. "
    "Every request, progress event, result, asset hash and provenance manifest is persisted."
)

model_override = st.text_input(
    "GMI Cloud audio model override (optional)",
    value="",
    placeholder=DEFAULT_AUDIO_MODEL,
)
timeout = st.number_input(
    "Timeout per narration segment in seconds",
    min_value=30,
    max_value=900,
    value=180,
    step=30,
)

gmi_ready = bool(os.getenv("GMI_API_KEY", "").strip())
if not all_approved:
    st.warning("Approve and save all three narration segments before generating audio.")
elif not gmi_ready:
    st.warning("GMI_API_KEY is not configured locally, so live narration generation is disabled.")
else:
    st.success("All narration segments are approved and GMI_API_KEY is configured locally.")

if st.button(
    "Generate three narration clips with Genblaze",
    type="primary",
    disabled=not (all_approved and gmi_ready),
    use_container_width=True,
):
    try:
        store = B2AudioStore(B2Settings.from_environment())
        progress_bar = st.progress(0, text="Preparing narration generation…")
        live_message = st.empty()
        event_rows: list[dict[str, object]] = []
        final_event = None

        with st.status("Generating three evidence-grounded narration clips", expanded=True) as status:
            for event in stream_narration_audio_generation(
                narration_plan=saved_plan,
                store=store,
                model=model_override or None,
                timeout=int(timeout),
            ):
                final_event = event
                event_rows.append(event.to_dict())
                st.session_state.audio_events = event_rows
                progress_bar.progress(int(event.progress * 100), text=event.message)
                live_message.info(event.message)
                st.write(f"{event.sequence:02d}. {event.message}")

            if final_event and final_event.stage == "audio_generation_completed":
                payload = final_event.payload or {}
                st.session_state.audio_summary = payload.get("summary")
                st.session_state.audio_summary_uri = payload.get("generation_summary_uri")
                status.update(
                    label="Three narration clips generated and verified",
                    state="complete",
                    expanded=False,
                )
                st.success("All three narration clips and provenance manifests are stored in B2.")
            elif final_event and final_event.stage == "audio_generation_failed":
                payload = final_event.payload or {}
                st.session_state.audio_summary_uri = payload.get("generation_summary_uri")
                status.update(
                    label="Narration generation stopped after a provider failure",
                    state="error",
                    expanded=True,
                )
                st.error(final_event.message)
            else:
                status.update(
                    label="Narration generation ended without a final result",
                    state="error",
                    expanded=True,
                )
                st.error("The audio progress stream ended without completion or failure.")
    except (
        NarrationValidationError,
        StorageConfigurationError,
        StorageOperationError,
        RuntimeError,
        ValueError,
    ) as exc:
        st.error(str(exc))

if st.session_state.audio_events:
    with st.expander("Narration progress event log"):
        st.json(st.session_state.audio_events)

if st.session_state.audio_summary_uri:
    st.caption(f"Current B2 narration summary: `{st.session_state.audio_summary_uri}`")

summary = st.session_state.audio_summary
if summary and summary.get("status") == "completed":
    st.subheader("4. Generated narration assets")
    for segment in summary.get("segments", []):
        st.markdown(f"### Scene {segment['scene_number']} narration")
        st.audio(segment["asset_url"])
        st.code(
            "\n".join(
                [
                    f"Run ID: {segment['run_id']}",
                    f"Audio asset: {segment['asset_url']}",
                    f"Audio SHA-256: {segment['asset_sha256']}",
                    f"Manifest: {segment['manifest_uri']}",
                    f"Manifest hash: {segment['manifest_canonical_hash']}",
                    f"Manifest verified: {segment['manifest_verified']}",
                    f"Result record: {segment['result_record_uri']}",
                ]
            )
        )
