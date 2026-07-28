# Renders EvidenceCast final media assembly, consistency evaluation and scene-regeneration controls.
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import streamlit as st
from dotenv import load_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from evidencecast.evaluation import EvaluationError, evaluate_evidence_consistency
from evidencecast.final_media import (
    FinalMediaError,
    compose_captioned_mp4,
    create_infographic,
    create_thumbnail,
    write_subtitles,
)
from evidencecast.final_store import B2FinalMediaStore
from evidencecast.media_probe import probe_duration_seconds
from evidencecast.regeneration import stream_scene_regeneration
from evidencecast.storage import B2Settings, StorageConfigurationError, StorageOperationError

load_dotenv(REPOSITORY_ROOT / ".env", override=True)

st.set_page_config(page_title="EvidenceCast Final Media", page_icon="🎬", layout="wide")

DEFAULTS = {
    "final_evaluation": None,
    "final_evaluation_uri": None,
    "final_delivery": None,
    "regeneration_events": [],
    "regeneration_summary_uri": None,
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.title("Final media and evaluation")
st.caption(
    "Produce subtitles, compose a captioned MP4 with FFmpeg, export a thumbnail and infographic, "
    "evaluate evidence consistency, and regenerate one scene with explicit parent-child lineage."
)

storyboard = st.session_state.get("storyboard")
narration_plan = st.session_state.get("narration_plan")

if not storyboard or not narration_plan:
    st.warning(
        "The current session does not contain both the storyboard and approved narration. "
        "Restore them directly from B2 below."
    )
    storyboard_uri = st.text_input(
        "B2 storyboard URI",
        value=(
            "b2://evidencecast-ai-buriro-2026/evidencecast/sources/c9/"
            "c959ebebe624ebec10c23a73c7ec1a4e4a270feacaa0748d4a7a7fbbf7f9fcfe/"
            "storyboards/SB-e27c3386b25a84a0/storyboard.json"
        ),
    )
    narration_uri = st.text_input(
        "B2 approved narration-review URI",
        value=(
            "b2://evidencecast-ai-buriro-2026/evidencecast/sources/c9/"
            "c959ebebe624ebec10c23a73c7ec1a4e4a270feacaa0748d4a7a7fbbf7f9fcfe/"
            "storyboards/SB-e27c3386b25a84a0/narration/NP-15ad65aedbeaf9c0/"
            "narration-review.json"
        ),
    )
    if st.button("Restore storyboard and approved narration from B2", type="primary"):
        try:
            store = B2FinalMediaStore(B2Settings.from_environment())
            loaded_storyboard = store.load_json_from_b2_uri(storyboard_uri)
            loaded_review = store.load_json_from_b2_uri(narration_uri)
            if loaded_storyboard.get("scene_count") != 3:
                raise EvaluationError("The storyboard must contain exactly three scenes.")
            segments = list(loaded_review.get("segments", []))
            if len(segments) != 3 or any(
                str(segment.get("review_status", "")).lower() != "approved"
                for segment in segments
            ):
                raise EvaluationError("The narration review must contain three approved segments.")
            loaded_plan = {
                "narration_id": loaded_review["narration_id"],
                "storyboard_id": loaded_review["storyboard_id"],
                "source_sha256": loaded_review["source_sha256"],
                "created_at": loaded_review.get("saved_at"),
                "language": loaded_review.get("language", "English (UK)"),
                "voice_style": loaded_review.get("voice_style", "clear, calm and educational"),
                "segment_count": 3,
                "review_status": loaded_review.get("review_status", "completed"),
                "segments": segments,
            }
            st.session_state.storyboard = loaded_storyboard
            st.session_state.narration_plan = loaded_plan
            storyboard = loaded_storyboard
            narration_plan = loaded_plan
            st.success("Storyboard and three approved narration segments restored from B2.")
        except (
            EvaluationError,
            StorageConfigurationError,
            StorageOperationError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            st.error(str(exc))

if not storyboard or not narration_plan:
    st.stop()

source_sha256 = str(storyboard["source_sha256"])
storyboard_id = str(storyboard["storyboard_id"])
narration_id = str(narration_plan["narration_id"])

metrics = st.columns(4)
metrics[0].metric("Storyboard", storyboard_id)
metrics[1].metric("Narration", narration_id)
metrics[2].metric("Scenes", len(storyboard.get("scenes", [])))
metrics[3].metric("Approved narration", sum(
    str(segment.get("review_status", "")).lower() == "approved"
    for segment in narration_plan.get("segments", [])
))

st.subheader("1. Evidence consistency and manifest evaluation")
st.info(
    "Structural evaluation works without paid media generation. Optional completed image and audio "
    "summaries add SHA-256 and provenance-manifest verification checks."
)
image_summary_uri = st.text_input("Completed image generation-summary B2 URI (optional)", value="")
audio_summary_uri = st.text_input("Completed audio generation-summary B2 URI (optional)", value="")

if st.button("Run consistency checks and save evaluation to B2", type="primary", use_container_width=True):
    try:
        store = B2FinalMediaStore(B2Settings.from_environment())
        image_summary = store.load_json_from_b2_uri(image_summary_uri) if image_summary_uri.strip() else None
        audio_summary = store.load_json_from_b2_uri(audio_summary_uri) if audio_summary_uri.strip() else None
        report = evaluate_evidence_consistency(
            storyboard=storyboard,
            narration_plan=narration_plan,
            image_summary=image_summary,
            audio_summary=audio_summary,
        )
        report_object = store.store_evaluation_report(
            source_sha256=source_sha256,
            storyboard_id=storyboard_id,
            evaluation=report,
        )
        st.session_state.final_evaluation = report
        st.session_state.final_evaluation_uri = report_object.uri
        if report["status"] == "passed":
            st.success(f"All {report['check_count']} consistency checks passed.")
        else:
            st.warning(
                f"{report['failed_count']} of {report['check_count']} checks failed. "
                "Review the failed checks before final delivery."
            )
    except (
        EvaluationError,
        StorageConfigurationError,
        StorageOperationError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        st.error(str(exc))

if st.session_state.final_evaluation:
    report = st.session_state.final_evaluation
    check_rows = [
        {
            "Check": check["label"],
            "Scene": check.get("scene_number"),
            "Passed": check["passed"],
            "Detail": check["detail"],
        }
        for check in report["checks"]
    ]
    st.dataframe(check_rows, use_container_width=True, hide_index=True)
    st.caption(f"Evaluation record: `{st.session_state.final_evaluation_uri}`")

st.subheader("2. Subtitles, captioned MP4, thumbnail and infographic")
st.caption(
    "Upload one approved scene image and one narration clip for each scene. This also supports "
    "manual validation while paid provider outputs remain unavailable. Inputs and outputs are "
    "stored with SHA-256 metadata in B2."
)

uploaded_images = []
uploaded_audio = []
for scene_number in (1, 2, 3):
    image_column, audio_column = st.columns(2)
    uploaded_images.append(
        image_column.file_uploader(
            f"Scene {scene_number} image",
            type=["png", "jpg", "jpeg", "webp"],
            key=f"final_image_{scene_number}",
        )
    )
    uploaded_audio.append(
        audio_column.file_uploader(
            f"Scene {scene_number} narration audio",
            type=["mp3", "wav", "m4a", "aac"],
            key=f"final_audio_{scene_number}",
        )
    )

assembly_ready = all(value is not None for value in [*uploaded_images, *uploaded_audio])
if not assembly_ready:
    st.warning("Upload all three images and all three narration clips to enable final assembly.")

if st.button(
    "Build and verify final delivery package",
    type="primary",
    disabled=not assembly_ready,
    use_container_width=True,
):
    try:
        delivery_id = f"DEL-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
        store = B2FinalMediaStore(B2Settings.from_environment())
        with tempfile.TemporaryDirectory(prefix="evidencecast-final-") as temporary_directory:
            workspace = Path(temporary_directory)
            input_directory = workspace / "inputs"
            output_directory = workspace / "outputs"
            input_directory.mkdir(parents=True, exist_ok=True)
            output_directory.mkdir(parents=True, exist_ok=True)

            image_paths: list[Path] = []
            audio_paths: list[Path] = []
            input_records: list[dict[str, object]] = []
            uploaded_input_objects = []

            for scene_number, uploaded in enumerate(uploaded_images, start=1):
                suffix = Path(uploaded.name).suffix.lower() or ".png"
                path = input_directory / f"scene-{scene_number:02d}-image{suffix}"
                data = uploaded.getvalue()
                path.write_bytes(data)
                image_paths.append(path)
                media_type = uploaded.type or mimetypes.guess_type(path.name)[0] or "image/png"
                stored = store.store_delivery_asset(
                    source_sha256=source_sha256,
                    storyboard_id=storyboard_id,
                    delivery_id=delivery_id,
                    filename=path.name,
                    data=data,
                    media_type=media_type,
                    role=f"scene-{scene_number}-image-input",
                )
                uploaded_input_objects.append(stored)
                input_records.append(
                    {
                        "scene_number": scene_number,
                        "kind": "image",
                        "filename": path.name,
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "size_bytes": len(data),
                        "b2_uri": stored.uri,
                    }
                )

            timed_segments = [dict(segment) for segment in narration_plan["segments"]]
            for scene_number, uploaded in enumerate(uploaded_audio, start=1):
                suffix = Path(uploaded.name).suffix.lower() or ".mp3"
                path = input_directory / f"scene-{scene_number:02d}-audio{suffix}"
                data = uploaded.getvalue()
                path.write_bytes(data)
                audio_paths.append(path)
                duration = probe_duration_seconds(path)
                timed_segments[scene_number - 1]["actual_duration_seconds"] = duration
                media_type = uploaded.type or mimetypes.guess_type(path.name)[0] or "audio/mpeg"
                stored = store.store_delivery_asset(
                    source_sha256=source_sha256,
                    storyboard_id=storyboard_id,
                    delivery_id=delivery_id,
                    filename=path.name,
                    data=data,
                    media_type=media_type,
                    role=f"scene-{scene_number}-audio-input",
                )
                uploaded_input_objects.append(stored)
                input_records.append(
                    {
                        "scene_number": scene_number,
                        "kind": "audio",
                        "filename": path.name,
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "size_bytes": len(data),
                        "duration_seconds": duration,
                        "b2_uri": stored.uri,
                    }
                )

            subtitle_result = write_subtitles(timed_segments, output_directory=output_directory)
            video_path = output_directory / "evidencecast-captioned.mp4"
            video_asset = compose_captioned_mp4(
                scene_images=image_paths,
                scene_audio=audio_paths,
                subtitle_path=subtitle_result["srt_path"],
                output_path=video_path,
                workspace=workspace / "ffmpeg",
            )
            thumbnail_asset = create_thumbnail(
                source_image=image_paths[0],
                title=str(storyboard.get("title", "EvidenceCast evidence story")),
                subtitle="Approved evidence • traceable narration • captioned delivery",
                output_path=output_directory / "thumbnail.jpg",
            )
            infographic_asset = create_infographic(
                storyboard=storyboard,
                output_path=output_directory / "infographic.png",
            )

            srt_text = subtitle_result["srt_path"].read_text(encoding="utf-8")
            vtt_text = subtitle_result["vtt_path"].read_text(encoding="utf-8")
            srt_object = store.store_subtitle_asset(
                source_sha256=source_sha256,
                storyboard_id=storyboard_id,
                delivery_id=delivery_id,
                filename="captions.srt",
                text=srt_text,
                media_type="application/x-subrip; charset=utf-8",
            )
            vtt_object = store.store_subtitle_asset(
                source_sha256=source_sha256,
                storyboard_id=storyboard_id,
                delivery_id=delivery_id,
                filename="captions.vtt",
                text=vtt_text,
                media_type="text/vtt; charset=utf-8",
            )
            output_objects = [
                store.store_delivery_asset(
                    source_sha256=source_sha256,
                    storyboard_id=storyboard_id,
                    delivery_id=delivery_id,
                    filename="evidencecast-captioned.mp4",
                    data=video_path.read_bytes(),
                    media_type="video/mp4",
                    role="final-captioned-video",
                ),
                store.store_delivery_asset(
                    source_sha256=source_sha256,
                    storyboard_id=storyboard_id,
                    delivery_id=delivery_id,
                    filename="thumbnail.jpg",
                    data=Path(thumbnail_asset.path).read_bytes(),
                    media_type="image/jpeg",
                    role="thumbnail",
                ),
                store.store_delivery_asset(
                    source_sha256=source_sha256,
                    storyboard_id=storyboard_id,
                    delivery_id=delivery_id,
                    filename="infographic.png",
                    data=Path(infographic_asset.path).read_bytes(),
                    media_type="image/png",
                    role="infographic",
                ),
                srt_object,
                vtt_object,
            ]
            verifications = [
                store.verify_stored_object(value)
                for value in [*uploaded_input_objects, *output_objects]
            ]
            all_verified = all(value["verified"] for value in verifications)
            manifest = {
                "delivery_id": delivery_id,
                "source_sha256": source_sha256,
                "storyboard_id": storyboard_id,
                "narration_id": narration_id,
                "created_at": datetime.now(UTC).isoformat(),
                "status": "completed" if all_verified else "verification_failed",
                "assembly_tool": "ffmpeg",
                "caption_formats": ["srt", "webvtt", "burned-in"],
                "inputs": input_records,
                "outputs": [
                    {
                        "role": "final-captioned-video",
                        "uri": output_objects[0].uri,
                        "sha256": output_objects[0].sha256,
                        "size_bytes": output_objects[0].size_bytes,
                    },
                    {
                        "role": "thumbnail",
                        "uri": output_objects[1].uri,
                        "sha256": output_objects[1].sha256,
                        "size_bytes": output_objects[1].size_bytes,
                    },
                    {
                        "role": "infographic",
                        "uri": output_objects[2].uri,
                        "sha256": output_objects[2].sha256,
                        "size_bytes": output_objects[2].size_bytes,
                    },
                    {
                        "role": "srt-subtitles",
                        "uri": srt_object.uri,
                        "sha256": srt_object.sha256,
                    },
                    {
                        "role": "webvtt-subtitles",
                        "uri": vtt_object.uri,
                        "sha256": vtt_object.sha256,
                    },
                ],
                "b2_verifications": verifications,
            }
            manifest_object = store.store_assembly_manifest(
                source_sha256=source_sha256,
                storyboard_id=storyboard_id,
                delivery_id=delivery_id,
                manifest=manifest,
            )
            delivery = {
                "delivery_id": delivery_id,
                "manifest_uri": manifest_object.uri,
                "manifest": manifest,
                "video_bytes": video_path.read_bytes(),
                "thumbnail_bytes": Path(thumbnail_asset.path).read_bytes(),
                "infographic_bytes": Path(infographic_asset.path).read_bytes(),
                "srt_bytes": srt_text.encode("utf-8"),
                "vtt_bytes": vtt_text.encode("utf-8"),
            }
            st.session_state.final_delivery = delivery
            if all_verified:
                st.success("Captioned MP4, subtitles, thumbnail and infographic were stored and verified in B2.")
            else:
                st.error("The delivery was stored, but one or more B2 integrity checks failed.")
    except (
        FinalMediaError,
        StorageConfigurationError,
        StorageOperationError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        st.error(str(exc))

if st.session_state.final_delivery:
    delivery = st.session_state.final_delivery
    st.code(
        "\n".join(
            [
                f"Delivery ID: {delivery['delivery_id']}",
                f"Assembly manifest: {delivery['manifest_uri']}",
                f"Status: {delivery['manifest']['status']}",
            ]
        )
    )
    download_columns = st.columns(5)
    download_columns[0].download_button(
        "Download MP4",
        delivery["video_bytes"],
        file_name="evidencecast-captioned.mp4",
        mime="video/mp4",
    )
    download_columns[1].download_button(
        "Download SRT", delivery["srt_bytes"], file_name="captions.srt", mime="application/x-subrip"
    )
    download_columns[2].download_button(
        "Download VTT", delivery["vtt_bytes"], file_name="captions.vtt", mime="text/vtt"
    )
    download_columns[3].download_button(
        "Download thumbnail", delivery["thumbnail_bytes"], file_name="thumbnail.jpg", mime="image/jpeg"
    )
    download_columns[4].download_button(
        "Download infographic", delivery["infographic_bytes"], file_name="infographic.png", mime="image/png"
    )

st.subheader("3. Scene-level regeneration, lineage and retry handling")
st.caption(
    "Create one child run for a selected image scene or narration segment. Non-retryable failures "
    "such as invalid payloads, authentication errors and insufficient credits stop immediately. "
    "Only transient timeouts, rate limits and server errors are retried."
)
media_kind = st.selectbox("Media to regenerate", options=["image", "audio"])
scene_number = st.selectbox("Scene", options=[1, 2, 3])
parent_run_id = st.text_input("Parent generation run ID")
reason = st.text_area("Reason for regeneration", max_chars=500)
max_attempts = st.number_input("Maximum attempts", min_value=1, max_value=3, value=2, step=1)
provider_name = "gmicloud"
if media_kind == "image":
    provider_name = st.selectbox("Image provider", options=["gmicloud", "openai"])
model_override = st.text_input("Model override (optional)", value="")

provider_ready = bool(
    os.getenv("GMI_API_KEY", "").strip()
    if provider_name == "gmicloud"
    else os.getenv("OPENAI_API_KEY", "").strip()
)
regeneration_ready = bool(parent_run_id.strip() and reason.strip() and provider_ready)
if not provider_ready:
    st.warning("The selected provider credential is not configured locally.")

if st.button(
    "Regenerate selected scene with lineage",
    type="primary",
    disabled=not regeneration_ready,
    use_container_width=True,
):
    try:
        store = B2FinalMediaStore(B2Settings.from_environment())
        events: list[dict[str, object]] = []
        final_event = None
        with st.status("Running scene-level regeneration", expanded=True) as status:
            for event in stream_scene_regeneration(
                storyboard=storyboard,
                narration_plan=narration_plan,
                store=store,
                media_kind=media_kind,
                scene_number=int(scene_number),
                parent_run_id=parent_run_id,
                reason=reason,
                provider_name=provider_name,
                model=model_override or None,
                max_attempts=int(max_attempts),
            ):
                final_event = event
                events.append(event.to_dict())
                st.write(event.message)
            st.session_state.regeneration_events = events
            if final_event and final_event.stage == "regeneration_completed":
                status.update(label="Scene regeneration completed", state="complete", expanded=False)
                st.success(final_event.message)
            elif final_event and final_event.stage == "regeneration_failed":
                status.update(label="Scene regeneration failed", state="error", expanded=True)
                st.error(final_event.message)
            else:
                status.update(label="Regeneration ended without a final event", state="error")
        if final_event and final_event.payload:
            st.session_state.regeneration_summary_uri = final_event.payload.get("summary_uri")
    except (
        EvaluationError,
        StorageConfigurationError,
        StorageOperationError,
        RuntimeError,
        ValueError,
    ) as exc:
        st.error(str(exc))

if st.session_state.regeneration_events:
    with st.expander("Regeneration event log"):
        st.json(st.session_state.regeneration_events)
if st.session_state.regeneration_summary_uri:
    st.caption(f"Current regeneration summary: `{st.session_state.regeneration_summary_uri}`")
