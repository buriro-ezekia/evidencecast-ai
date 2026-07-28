# Renders the EvidenceCast Day 3 storyboard, three-scene image generation and progress-streaming workspace.
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from evidencecast.media import DEFAULT_MODELS, stream_storyboard_image_generation
from evidencecast.storage import (
    B2EvidenceStore,
    B2Settings,
    StorageConfigurationError,
    StorageOperationError,
)
from evidencecast.storyboard import (
    StoryboardValidationError,
    approved_evidence_cards,
    create_storyboard,
)

load_dotenv(REPOSITORY_ROOT / ".env", override=True)

st.set_page_config(
    page_title="EvidenceCast Storyboard",
    page_icon="🎬",
    layout="wide",
)

DAY3_DEFAULTS = {
    "storyboard": None,
    "storyboard_uri": None,
    "scene_prompts_uri": None,
    "generation_events": [],
    "generation_summary": None,
    "generation_summary_uri": None,
}
for key, value in DAY3_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.title("Storyboard and image generation")
st.caption(
    "Create a three-scene storyboard from approved evidence only, persist every intermediate "
    "record to Backblaze B2, and stream Genblaze image-generation progress."
)

source_bundle = st.session_state.get("source_bundle")
cards = st.session_state.get("evidence_cards")

if not source_bundle or not cards:
    st.warning(
        "No reviewed evidence source is active. Open the EvidenceCast AI main page, upload a "
        "source, review its cards and save the review before returning here."
    )
    st.stop()

source_sha256 = str(source_bundle["source_sha256"])
approved_cards = approved_evidence_cards(cards)

summary_columns = st.columns(4)
summary_columns[0].metric("Source", str(source_bundle.get("original", {}).get("uri", "Stored in B2")).split("/")[-1])
summary_columns[1].metric("Approved cards", len(approved_cards))
summary_columns[2].metric("Required scenes", 3)
summary_columns[3].metric("Source SHA", source_sha256[:12] + "…")

st.subheader("1. Build structured storyboard JSON")
st.info(
    "Exactly three approved evidence cards are required. Pending and rejected cards are never "
    "used to create scene claims or image prompts."
)

storyboard_title = st.text_input(
    "Storyboard title",
    value="EvidenceCast three-scene evidence story",
    max_chars=160,
)

create_disabled = len(approved_cards) < 3
if create_disabled:
    st.warning(
        f"Only {len(approved_cards)} approved card(s) are available. Approve and save at least "
        f"{3 - len(approved_cards)} more card(s) on the main page."
    )

if st.button(
    "Create storyboard and save intermediates to B2",
    type="primary",
    disabled=create_disabled,
    use_container_width=True,
):
    try:
        with st.status("Building evidence-grounded storyboard", expanded=True) as status:
            st.write("Validating approved evidence cards…")
            storyboard = create_storyboard(
                cards,
                source_sha256=source_sha256,
                title=storyboard_title,
            )
            storyboard_payload = storyboard.to_dict()

            st.write("Saving structured storyboard JSON to B2…")
            store = B2EvidenceStore(B2Settings.from_environment())
            storyboard_object = store.store_storyboard(
                source_sha256=source_sha256,
                storyboard_id=storyboard.storyboard_id,
                storyboard=storyboard_payload,
            )

            st.write("Saving scene prompts and evidence-card links to B2…")
            prompts_object = store.store_scene_prompts(
                source_sha256=source_sha256,
                storyboard_id=storyboard.storyboard_id,
                scenes=storyboard_payload["scenes"],
            )

            st.session_state.storyboard = storyboard_payload
            st.session_state.storyboard_uri = storyboard_object.uri
            st.session_state.scene_prompts_uri = prompts_object.uri
            st.session_state.generation_events = []
            st.session_state.generation_summary = None
            st.session_state.generation_summary_uri = None
            status.update(label="Storyboard and prompt records saved", state="complete", expanded=False)
        st.success("The structured storyboard and all three scene prompts are stored in B2.")
    except (StoryboardValidationError, StorageConfigurationError, StorageOperationError) as exc:
        st.error(str(exc))

storyboard_payload = st.session_state.storyboard
if not storyboard_payload:
    st.stop()

st.code(
    "\n".join(
        [
            f"Storyboard ID: {storyboard_payload['storyboard_id']}",
            f"Storyboard JSON: {st.session_state.storyboard_uri}",
            f"Scene prompts: {st.session_state.scene_prompts_uri}",
        ]
    )
)

with st.expander("Preview structured storyboard JSON", expanded=True):
    st.json(storyboard_payload)

st.download_button(
    "Download storyboard JSON",
    data=json.dumps(storyboard_payload, ensure_ascii=False, indent=2),
    file_name=f"{storyboard_payload['storyboard_id']}.json",
    mime="application/json",
    use_container_width=True,
)

st.subheader("2. Generate three scene images")
st.caption(
    "Each scene runs through Genblaze independently. The request, progress events, scene result, "
    "image asset, provenance manifest and final summary are persisted to B2."
)

provider_name = st.selectbox(
    "Image provider",
    options=["gmicloud", "openai"],
    index=0 if os.getenv("IMAGE_PROVIDER", "gmicloud").strip().lower() != "openai" else 1,
)
model_override = st.text_input(
    "Model override (optional)",
    value="",
    placeholder=DEFAULT_MODELS[provider_name],
    help="Leave blank to use the provider-specific default shown in the placeholder.",
)

advanced = st.expander("Generation settings")
with advanced:
    timeout = st.number_input("Timeout per scene in seconds", min_value=30, max_value=900, value=180, step=30)
    if provider_name == "gmicloud":
        aspect_ratio = st.selectbox("Aspect ratio", options=["16:9", "1:1", "9:16"], index=0)
        size = "1536x1024"
        quality = "low"
    else:
        size = st.selectbox("Image size", options=["1536x1024", "1024x1024", "1024x1536"], index=0)
        quality = st.selectbox("Image quality", options=["low", "medium", "high"], index=0)
        aspect_ratio = "16:9"

provider_environment = "GMI_API_KEY" if provider_name == "gmicloud" else "OPENAI_API_KEY"
provider_ready = bool(os.getenv(provider_environment, "").strip())
if provider_ready:
    st.success(f"{provider_environment} is configured locally.")
else:
    st.warning(
        f"{provider_environment} is not configured. Storyboard creation remains available, "
        "but live scene-image generation cannot start with this provider."
    )

if st.button(
    "Generate three scene images with Genblaze",
    type="primary",
    disabled=not provider_ready,
    use_container_width=True,
):
    try:
        store = B2EvidenceStore(B2Settings.from_environment())
        progress_bar = st.progress(0, text="Preparing generation…")
        live_message = st.empty()
        event_rows: list[dict[str, object]] = []
        final_event = None

        with st.status("Generating three evidence-grounded scene images", expanded=True) as status:
            for event in stream_storyboard_image_generation(
                storyboard=storyboard_payload,
                store=store,
                provider_name=provider_name,
                model=model_override or None,
                timeout=int(timeout),
                size=size,
                quality=quality,
                aspect_ratio=aspect_ratio,
            ):
                final_event = event
                event_rows.append(event.to_dict())
                st.session_state.generation_events = event_rows
                progress_bar.progress(
                    int(event.progress * 100),
                    text=event.message,
                )
                live_message.info(event.message)
                st.write(f"{event.sequence:02d}. {event.message}")

            if final_event and final_event.stage == "generation_completed":
                payload = final_event.payload or {}
                st.session_state.generation_summary = payload.get("summary")
                st.session_state.generation_summary_uri = payload.get("generation_summary_uri")
                status.update(label="Three scene images generated and verified", state="complete", expanded=False)
                st.success("All three images and their Genblaze provenance manifests are stored in B2.")
            elif final_event and final_event.stage == "generation_failed":
                payload = final_event.payload or {}
                st.session_state.generation_summary_uri = payload.get("generation_summary_uri")
                status.update(label="Image generation stopped after a provider failure", state="error", expanded=True)
                st.error(final_event.message)
            else:
                status.update(label="Generation ended without a final result", state="error", expanded=True)
                st.error("The progress stream ended without a completion or failure event.")
    except (StorageConfigurationError, StorageOperationError, ValueError, RuntimeError) as exc:
        st.error(str(exc))

if st.session_state.generation_events:
    with st.expander("Generation progress event log"):
        st.json(st.session_state.generation_events)

if st.session_state.generation_summary_uri:
    st.caption(f"Current B2 generation summary: `{st.session_state.generation_summary_uri}`")

summary = st.session_state.generation_summary
if summary and summary.get("status") == "completed":
    st.subheader("3. Generated scene assets")
    for scene in summary.get("scenes", []):
        st.markdown(f"### Scene {scene['scene_number']}: {scene['title']}")
        st.image(scene["asset_url"], caption=f"SHA-256: {scene['asset_sha256']}", use_container_width=True)
        st.code(
            "\n".join(
                [
                    f"Run ID: {scene['run_id']}",
                    f"Asset: {scene['asset_url']}",
                    f"Manifest: {scene['manifest_uri']}",
                    f"Manifest hash: {scene['manifest_canonical_hash']}",
                    f"Manifest verified: {scene['manifest_verified']}",
                    f"Result record: {scene['result_record_uri']}",
                ]
            )
        )
