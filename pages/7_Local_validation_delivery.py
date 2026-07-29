# Builds a complete local EvidenceCast delivery package when paid provider media is unavailable.
from __future__ import annotations

import hashlib
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
from evidencecast.local_assets import LocalAssetError, generate_local_validation_assets
from evidencecast.media_probe import probe_duration_seconds
from evidencecast.storage import B2Settings, StorageConfigurationError, StorageOperationError

load_dotenv(REPOSITORY_ROOT / ".env", override=True)

st.set_page_config(
    page_title="EvidenceCast Local Delivery",
    page_icon="🧪",
    layout="wide",
)

DEFAULTS = {
    "local_delivery": None,
    "local_delivery_evaluation_uri": None,
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.title("Local validation delivery")
st.caption(
    "Generate three clearly labelled local scene images and three local narration WAV files from "
    "approved evidence, then create and verify the complete FFmpeg delivery package."
)
st.warning(
    "This pathway is for functional validation while GMI Cloud is unfunded. The generated inputs "
    "are explicitly recorded as local Pillow and eSpeak assets, not provider-generated Genblaze media."
)

storyboard = st.session_state.get("storyboard")
narration_plan = st.session_state.get("narration_plan")

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

if st.button("Restore approved workflow from B2", type="primary", use_container_width=True):
    try:
        store = B2FinalMediaStore(B2Settings.from_environment())
        loaded_storyboard = store.load_json_from_b2_uri(storyboard_uri)
        loaded_review = store.load_json_from_b2_uri(narration_uri)
        scenes = list(loaded_storyboard.get("scenes", []))
        segments = list(loaded_review.get("segments", []))
        if len(scenes) != 3:
            raise EvaluationError("The storyboard must contain exactly three scenes.")
        if len(segments) != 3 or any(
            str(segment.get("review_status", "")).strip().lower() != "approved"
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
        st.session_state.local_delivery = None
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
    st.info("Restore the approved workflow before building the local validation package.")
    st.stop()

source_sha256 = str(storyboard["source_sha256"])
storyboard_id = str(storyboard["storyboard_id"])
narration_id = str(narration_plan["narration_id"])

metrics = st.columns(4)
metrics[0].metric("Storyboard", storyboard_id)
metrics[1].metric("Narration", narration_id)
metrics[2].metric("Scenes", len(storyboard.get("scenes", [])))
metrics[3].metric(
    "Approved narration",
    sum(
        str(segment.get("review_status", "")).strip().lower() == "approved"
        for segment in narration_plan.get("segments", [])
    ),
)

st.subheader("Build complete local validation package")
st.write(
    "The process will render evidence-grounded PNG scene cards, synthesise approved narration to "
    "WAV with eSpeak, calculate real audio timing with FFprobe, produce SRT and WebVTT subtitles, "
    "burn captions into an MP4, create a thumbnail and infographic, upload everything to B2, and "
    "verify the stored SHA-256 and object sizes."
)

if st.button("Generate, assemble and verify local delivery", type="primary", use_container_width=True):
    try:
        delivery_id = f"DEL-LOCAL-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
        store = B2FinalMediaStore(B2Settings.from_environment())
        progress = st.progress(0, text="Starting local delivery…")

        with st.status("Building complete local validation delivery", expanded=True) as status:
            st.write("1. Running evidence consistency checks…")
            evaluation = evaluate_evidence_consistency(
                storyboard=storyboard,
                narration_plan=narration_plan,
                image_summary=None,
                audio_summary=None,
            )
            if evaluation["status"] != "passed":
                raise EvaluationError(
                    f"Evidence consistency failed: {evaluation['failed_count']} checks did not pass."
                )
            evaluation_object = store.store_evaluation_report(
                source_sha256=source_sha256,
                storyboard_id=storyboard_id,
                evaluation=evaluation,
            )
            st.session_state.local_delivery_evaluation_uri = evaluation_object.uri
            progress.progress(10, text="Evidence consistency passed.")

            with tempfile.TemporaryDirectory(prefix="evidencecast-local-delivery-") as temporary_directory:
                workspace = Path(temporary_directory)
                local_input_directory = workspace / "local-inputs"
                output_directory = workspace / "outputs"

                st.write("2. Rendering three local evidence scene images and approved narration clips…")
                local_bundle = generate_local_validation_assets(
                    storyboard=storyboard,
                    narration_plan=narration_plan,
                    output_directory=local_input_directory,
                )
                image_paths = [Path(value["path"]) for value in local_bundle["images"]]
                audio_paths = [Path(value["path"]) for value in local_bundle["audio"]]
                progress.progress(28, text="Six local validation inputs created.")

                st.write("3. Uploading and verifying local input assets in B2…")
                input_objects = []
                input_records: list[dict[str, object]] = []
                for record in [*local_bundle["images"], *local_bundle["audio"]]:
                    path = Path(str(record["path"]))
                    data = path.read_bytes()
                    stored = store.store_delivery_asset(
                        source_sha256=source_sha256,
                        storyboard_id=storyboard_id,
                        delivery_id=delivery_id,
                        filename=path.name,
                        data=data,
                        media_type=str(record["media_type"]),
                        role=f"scene-{record['scene_number']}-{record['kind']}-local-input",
                    )
                    input_objects.append(stored)
                    input_records.append(
                        {
                            "scene_number": int(record["scene_number"]),
                            "kind": str(record["kind"]),
                            "origin": "local_validation_fallback",
                            "generator": str(record["generator"]),
                            "filename": path.name,
                            "sha256": hashlib.sha256(data).hexdigest(),
                            "size_bytes": len(data),
                            "b2_uri": stored.uri,
                            "evidence_card_ids": list(record["evidence_card_ids"]),
                        }
                    )
                progress.progress(42, text="Local inputs stored in B2.")

                st.write("4. Measuring narration duration and producing subtitles…")
                timed_segments = [dict(segment) for segment in narration_plan["segments"]]
                for scene_number, audio_path in enumerate(audio_paths, start=1):
                    duration = probe_duration_seconds(audio_path)
                    timed_segments[scene_number - 1]["actual_duration_seconds"] = duration
                    for record in input_records:
                        if record["scene_number"] == scene_number and record["kind"] == "audio":
                            record["duration_seconds"] = duration
                subtitle_result = write_subtitles(timed_segments, output_directory=output_directory)
                progress.progress(54, text="SRT and WebVTT subtitles created.")

                st.write("5. Composing the captioned MP4 with FFmpeg…")
                video_path = output_directory / "evidencecast-captioned.mp4"
                video_asset = compose_captioned_mp4(
                    scene_images=image_paths,
                    scene_audio=audio_paths,
                    subtitle_path=subtitle_result["srt_path"],
                    output_path=video_path,
                    workspace=workspace / "ffmpeg",
                )
                progress.progress(72, text="Captioned MP4 created.")

                st.write("6. Creating thumbnail and infographic exports…")
                thumbnail_asset = create_thumbnail(
                    source_image=image_paths[0],
                    title=str(storyboard.get("title", "EvidenceCast evidence story")),
                    subtitle="Local validation • approved evidence • captioned delivery",
                    output_path=output_directory / "thumbnail.jpg",
                )
                infographic_asset = create_infographic(
                    storyboard=storyboard,
                    output_path=output_directory / "infographic.png",
                )
                progress.progress(80, text="Thumbnail and infographic created.")

                st.write("7. Uploading final outputs and verifying B2 integrity…")
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
                    for value in [*input_objects, *output_objects]
                ]
                all_verified = all(value["verified"] for value in verifications)

                manifest = {
                    "delivery_id": delivery_id,
                    "source_sha256": source_sha256,
                    "storyboard_id": storyboard_id,
                    "narration_id": narration_id,
                    "created_at": datetime.now(UTC).isoformat(),
                    "status": "completed" if all_verified else "verification_failed",
                    "delivery_mode": "local_validation_fallback",
                    "provider_generated": False,
                    "disclosure": local_bundle["disclosure"],
                    "assembly_tool": "ffmpeg",
                    "image_generator": "pillow",
                    "narration_generator": "espeak",
                    "caption_formats": ["srt", "webvtt", "burned-in"],
                    "evaluation_uri": evaluation_object.uri,
                    "inputs": input_records,
                    "outputs": [
                        {
                            "role": "final-captioned-video",
                            "uri": output_objects[0].uri,
                            "sha256": output_objects[0].sha256,
                            "size_bytes": output_objects[0].size_bytes,
                            "local_sha256": video_asset.sha256,
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
                progress.progress(100, text="Local delivery stored and verified.")

                delivery = {
                    "delivery_id": delivery_id,
                    "manifest_uri": manifest_object.uri,
                    "manifest": manifest,
                    "video_bytes": video_path.read_bytes(),
                    "thumbnail_bytes": Path(thumbnail_asset.path).read_bytes(),
                    "infographic_bytes": Path(infographic_asset.path).read_bytes(),
                    "srt_bytes": srt_text.encode("utf-8"),
                    "vtt_bytes": vtt_text.encode("utf-8"),
                    "scene_images": [path.read_bytes() for path in image_paths],
                    "scene_audio": [path.read_bytes() for path in audio_paths],
                }
                st.session_state.local_delivery = delivery

            if all_verified:
                status.update(
                    label="Complete local validation delivery stored and verified",
                    state="complete",
                    expanded=False,
                )
                st.success(
                    "The captioned MP4, subtitles, thumbnail, infographic and six local inputs were "
                    "stored and verified in B2."
                )
            else:
                status.update(
                    label="Delivery stored with integrity failures",
                    state="error",
                    expanded=True,
                )
                st.error("One or more B2 SHA-256 or object-size checks failed.")
    except (
        EvaluationError,
        FinalMediaError,
        LocalAssetError,
        StorageConfigurationError,
        StorageOperationError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        st.error(str(exc))

if st.session_state.local_delivery:
    delivery = st.session_state.local_delivery
    st.subheader("Completed local delivery")
    st.code(
        "\n".join(
            [
                f"Delivery ID: {delivery['delivery_id']}",
                f"Assembly manifest: {delivery['manifest_uri']}",
                f"Status: {delivery['manifest']['status']}",
                "Provider-generated: False",
                "Input origin: local Pillow images and eSpeak narration",
            ]
        )
    )
    st.video(delivery["video_bytes"])
    preview_columns = st.columns(3)
    for index, data in enumerate(delivery["scene_images"]):
        preview_columns[index].image(data, caption=f"Scene {index + 1} local validation image")
    st.image(delivery["infographic_bytes"], caption="EvidenceCast infographic export", width=500)

    download_columns = st.columns(5)
    download_columns[0].download_button(
        "Download MP4",
        delivery["video_bytes"],
        file_name="evidencecast-captioned.mp4",
        mime="video/mp4",
    )
    download_columns[1].download_button(
        "Download SRT",
        delivery["srt_bytes"],
        file_name="captions.srt",
        mime="application/x-subrip",
    )
    download_columns[2].download_button(
        "Download VTT",
        delivery["vtt_bytes"],
        file_name="captions.vtt",
        mime="text/vtt",
    )
    download_columns[3].download_button(
        "Download thumbnail",
        delivery["thumbnail_bytes"],
        file_name="thumbnail.jpg",
        mime="image/jpeg",
    )
    download_columns[4].download_button(
        "Download infographic",
        delivery["infographic_bytes"],
        file_name="infographic.png",
        mime="image/png",
    )

    with st.expander("Local narration previews"):
        for index, data in enumerate(delivery["scene_audio"], start=1):
            st.markdown(f"**Scene {index} narration**")
            st.audio(data, format="audio/wav")
