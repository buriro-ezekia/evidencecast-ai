# Provides controlled one-scene NVIDIA image and narration validation through Genblaze and B2.
from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from evidencecast.audio_store import B2AudioStore
from evidencecast.nvidia_live import (
    DEFAULT_NVIDIA_AUDIO_MODEL,
    DEFAULT_NVIDIA_IMAGE_MODEL,
    DEFAULT_NVIDIA_LANGUAGE,
    DEFAULT_NVIDIA_TTS_ENDPOINT,
    DEFAULT_NVIDIA_VOICE,
    generate_nvidia_audio_segment,
    generate_nvidia_image_scene,
    nvidia_key_configured,
)
from evidencecast.storage import B2EvidenceStore, B2Settings, StorageConfigurationError, StorageOperationError

load_dotenv(REPOSITORY_ROOT / ".env", override=True)

st.set_page_config(
    page_title="EvidenceCast NVIDIA Validation",
    page_icon="🟢",
    layout="wide",
)

DEFAULT_STORYBOARD_URI = (
    "b2://evidencecast-ai-buriro-2026/evidencecast/sources/c9/"
    "c959ebebe624ebec10c23a73c7ec1a4e4a270feacaa0748d4a7a7fbbf7f9fcfe/"
    "storyboards/SB-e27c3386b25a84a0/storyboard.json"
)
DEFAULT_NARRATION_URI = (
    "b2://evidencecast-ai-buriro-2026/evidencecast/sources/c9/"
    "c959ebebe624ebec10c23a73c7ec1a4e4a270feacaa0748d4a7a7fbbf7f9fcfe/"
    "storyboards/SB-e27c3386b25a84a0/narration/NP-15ad65aedbeaf9c0/narration-review.json"
)

for key, default in {
    "nvidia_storyboard": None,
    "nvidia_narration": None,
    "nvidia_image_summary": None,
    "nvidia_audio_summary": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.title("NVIDIA live provider validation")
st.caption(
    "Validate one image and one approved narration segment first. Every request, result, asset, "
    "SHA-256 value and Genblaze provenance manifest is stored in Backblaze B2."
)

if nvidia_key_configured():
    st.success("NVIDIA_API_KEY is configured locally. Its value is not displayed or stored in workflow JSON.")
else:
    st.error(
        "NVIDIA_API_KEY is not configured. Add it to the local .env file; never paste the key into "
        "this page, GitHub, logs or chat messages."
    )

st.info(
    "The hosted NVIDIA key normally begins with `nvapi-`. Image-model availability can vary by "
    "account; a rejected or unavailable model is recorded transparently rather than reported as success."
)

st.subheader("1. Restore approved workflow records")
storyboard_uri = st.text_input("B2 storyboard URI", value=DEFAULT_STORYBOARD_URI)
narration_uri = st.text_input("B2 approved narration-review URI", value=DEFAULT_NARRATION_URI)

if st.button("Restore NVIDIA validation inputs from B2", type="primary", use_container_width=True):
    try:
        store = B2AudioStore(B2Settings.from_environment())
        storyboard = store.load_json_from_b2_uri(storyboard_uri)
        narration = store.load_json_from_b2_uri(narration_uri)

        if storyboard.get("scene_count") != 3 or storyboard.get("review_mode") != "approved_only":
            raise ValueError("The storyboard must contain exactly three approved-only scenes.")
        if narration.get("review_status") != "completed":
            raise ValueError("The narration review must be completed.")
        segments = list(narration.get("segments", []))
        if len(segments) != 3 or any(
            str(segment.get("review_status", "")).lower() != "approved" for segment in segments
        ):
            raise ValueError("All three narration segments must be approved.")
        if narration.get("storyboard_id") != storyboard.get("storyboard_id"):
            raise ValueError("The narration review does not belong to the selected storyboard.")

        st.session_state.nvidia_storyboard = storyboard
        st.session_state.nvidia_narration = narration
        st.session_state.nvidia_image_summary = None
        st.session_state.nvidia_audio_summary = None
        st.success("Approved storyboard and narration records restored from B2.")
    except (StorageConfigurationError, StorageOperationError, ValueError) as exc:
        st.error(str(exc))

storyboard = st.session_state.nvidia_storyboard
narration = st.session_state.nvidia_narration

if not storyboard or not narration:
    st.stop()

metrics = st.columns(4)
metrics[0].metric("Storyboard", storyboard["storyboard_id"])
metrics[1].metric("Narration", narration["narration_id"])
metrics[2].metric("Scenes", storyboard["scene_count"])
metrics[3].metric("Approved narration", len(narration["segments"]))

image_tab, audio_tab = st.tabs(["NVIDIA image", "NVIDIA narration"])

with image_tab:
    st.subheader("2A. Generate one NVIDIA scene image")
    st.warning(
        "Start with one scene. Do not submit all three until this run returns a B2 asset, SHA-256, "
        "manifest URI and `Manifest.verify() = True`."
    )
    image_scene_number = st.selectbox("Image scene", options=[1, 2, 3], index=0, key="nvidia_image_scene")
    image_model = st.text_input(
        "NVIDIA image model",
        value=os.getenv("NVIDIA_IMAGE_MODEL", DEFAULT_NVIDIA_IMAGE_MODEL),
        help=(
            "The official Genblaze NVIDIA connector supports SDXL, Stable Diffusion 3.5 and "
            "FLUX-family model slugs. Availability is checked by the provider."
        ),
    )
    aspect_ratio = st.selectbox("Aspect ratio", options=["16:9", "1:1", "9:16"], index=0)
    image_timeout = st.number_input(
        "Image timeout in seconds",
        min_value=60,
        max_value=900,
        value=240,
        step=30,
    )

    if st.button(
        "Generate one NVIDIA image through Genblaze",
        type="primary",
        disabled=not nvidia_key_configured(),
        use_container_width=True,
    ):
        try:
            with st.status("Running controlled NVIDIA image validation", expanded=True) as status:
                st.write("Saving the scene request to B2…")
                st.write("Submitting the selected NVIDIA image model through Genblaze…")
                result = generate_nvidia_image_scene(
                    storyboard=storyboard,
                    scene_number=int(image_scene_number),
                    store=B2EvidenceStore(B2Settings.from_environment()),
                    model=image_model.strip() or DEFAULT_NVIDIA_IMAGE_MODEL,
                    timeout=int(image_timeout),
                    aspect_ratio=aspect_ratio,
                )
                st.session_state.nvidia_image_summary = result
                if result.get("status") == "completed":
                    status.update(label="NVIDIA image generated and verified", state="complete")
                    st.success("The NVIDIA image and verified Genblaze manifest are stored in B2.")
                else:
                    status.update(label="NVIDIA image validation stopped", state="error")
                    st.error(str(result.get("failed_scene", {}).get("error", "NVIDIA image generation failed.")))
        except (StorageConfigurationError, StorageOperationError, ValueError, RuntimeError) as exc:
            st.error(str(exc))

    image_summary = st.session_state.nvidia_image_summary
    if image_summary:
        st.caption(f"Current image summary: `{image_summary.get('generation_summary_uri', '')}`")
        if image_summary.get("status") == "completed":
            scene_result = image_summary["scene"]
            st.image(scene_result["asset_url"], use_container_width=True)
            st.code(
                "\n".join(
                    [
                        f"Provider: {scene_result['provider']}",
                        f"Model: {scene_result['model']}",
                        f"Asset: {scene_result['asset_url']}",
                        f"SHA-256: {scene_result['asset_sha256']}",
                        f"Manifest: {scene_result['manifest_uri']}",
                        f"Manifest verified: {scene_result['manifest_verified']}",
                    ]
                )
            )
        with st.expander("NVIDIA image result JSON"):
            st.json(image_summary)

with audio_tab:
    st.subheader("2B. Generate one NVIDIA narration clip")
    st.caption(
        "This route uses NVIDIA Magpie multilingual TTS inside a Genblaze pipeline and stores the "
        "result and provenance manifest in B2."
    )
    audio_scene_number = st.selectbox("Narration scene", options=[1, 2, 3], index=0, key="nvidia_audio_scene")
    audio_model = st.text_input(
        "NVIDIA audio model",
        value=os.getenv("NVIDIA_AUDIO_MODEL", DEFAULT_NVIDIA_AUDIO_MODEL),
    )
    language = st.selectbox("Language", options=["en-US"], index=0)
    voice = st.text_input(
        "Voice",
        value=os.getenv("NVIDIA_TTS_VOICE", DEFAULT_NVIDIA_VOICE),
    )
    sample_rate_hz = st.selectbox("Sample rate", options=[22050, 44100], index=1)
    audio_timeout = st.number_input(
        "Audio timeout in seconds",
        min_value=60,
        max_value=900,
        value=240,
        step=30,
    )
    with st.expander("Advanced NVIDIA TTS endpoint"):
        tts_endpoint = st.text_input(
            "Hosted synthesis endpoint",
            value=os.getenv("NVIDIA_TTS_ENDPOINT", DEFAULT_NVIDIA_TTS_ENDPOINT),
            help="This is a service URL, not a credential. Keep the API key only in .env.",
        )

    selected_segment = next(
        segment
        for segment in narration["segments"]
        if int(segment["scene_number"]) == int(audio_scene_number)
    )
    st.text_area(
        "Approved narration to synthesise",
        value=str(selected_segment["reviewed_text"]),
        disabled=True,
        height=120,
    )

    if st.button(
        "Generate one NVIDIA narration clip through Genblaze",
        type="primary",
        disabled=not nvidia_key_configured(),
        use_container_width=True,
    ):
        try:
            with st.status("Running controlled NVIDIA narration validation", expanded=True) as status:
                st.write("Saving the approved narration request to B2…")
                st.write("Submitting NVIDIA Magpie TTS through Genblaze…")
                result = generate_nvidia_audio_segment(
                    narration=narration,
                    scene_number=int(audio_scene_number),
                    store=B2AudioStore(B2Settings.from_environment()),
                    model=audio_model.strip() or DEFAULT_NVIDIA_AUDIO_MODEL,
                    voice=voice.strip() or DEFAULT_NVIDIA_VOICE,
                    language=language or DEFAULT_NVIDIA_LANGUAGE,
                    endpoint=tts_endpoint.strip() or DEFAULT_NVIDIA_TTS_ENDPOINT,
                    timeout=int(audio_timeout),
                    sample_rate_hz=int(sample_rate_hz),
                )
                st.session_state.nvidia_audio_summary = result
                if result.get("status") == "completed":
                    status.update(label="NVIDIA narration generated and verified", state="complete")
                    st.success("The NVIDIA narration clip and verified Genblaze manifest are stored in B2.")
                else:
                    status.update(label="NVIDIA narration validation stopped", state="error")
                    st.error(str(result.get("failed_segment", {}).get("error", "NVIDIA narration failed.")))
        except (StorageConfigurationError, StorageOperationError, ValueError, RuntimeError) as exc:
            st.error(str(exc))

    audio_summary = st.session_state.nvidia_audio_summary
    if audio_summary:
        st.caption(f"Current audio summary: `{audio_summary.get('generation_summary_uri', '')}`")
        if audio_summary.get("status") == "completed":
            segment_result = audio_summary["segment"]
            st.audio(segment_result["asset_url"], format="audio/wav")
            st.code(
                "\n".join(
                    [
                        f"Provider: {segment_result['provider']}",
                        f"Model: {segment_result['model']}",
                        f"Voice: {segment_result['voice']}",
                        f"Asset: {segment_result['asset_url']}",
                        f"SHA-256: {segment_result['asset_sha256']}",
                        f"Manifest: {segment_result['manifest_uri']}",
                        f"Manifest verified: {segment_result['manifest_verified']}",
                    ]
                )
            )
        with st.expander("NVIDIA narration result JSON"):
            st.json(audio_summary)
