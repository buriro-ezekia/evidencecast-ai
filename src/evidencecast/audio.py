# Generates reviewed narration audio through Genblaze while streaming and persisting progress to Backblaze B2.
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Iterator
from uuid import uuid4

from genblaze_core import KeyStrategy, Modality, ObjectStorageSink, Pipeline
from genblaze_gmicloud import GMICloudAudioProvider
from genblaze_s3 import S3StorageBackend

from .narration import require_all_segments_approved
from .storage import B2EvidenceStore, B2Settings


class AudioGenerationConfigurationError(RuntimeError):
    """Raised when narration audio cannot be configured safely."""


DEFAULT_AUDIO_MODEL = "minimax-tts-speech-2.6-turbo"
DEFAULT_TTS_VOICES = {
    "minimax-tts": "presenter_female",
    "elevenlabs-tts": "21m00Tcm4TlvDq8ikWAM",
    "inworld-tts": "ashley",
}


def _normalise_gmi_tts_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Map Genblaze's canonical ``prompt`` field to GMI's required ``text`` field."""

    normalised = dict(payload)
    nested_payload = normalised.get("payload")
    if isinstance(nested_payload, dict):
        nested = dict(nested_payload)
        if "text" not in nested and "prompt" in nested:
            nested["text"] = nested.pop("prompt")
        normalised["payload"] = nested
    elif "text" not in normalised and "prompt" in normalised:
        normalised["text"] = normalised.pop("prompt")
    return normalised


class EvidenceCastGMICloudAudioProvider(GMICloudAudioProvider):
    """GMI audio provider with a narrow compatibility fix for TTS payloads."""

    def prepare_payload(self, step: Any) -> dict[str, Any]:
        payload = super().prepare_payload(step)
        return _normalise_gmi_tts_payload(payload)


@dataclass(frozen=True)
class AudioProgressEvent:
    """One durable user-visible narration-generation update."""

    sequence: int
    stage: str
    message: str
    progress: float
    created_at: str
    scene_number: int | None = None
    payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _create_genblaze_storage(settings: B2Settings) -> ObjectStorageSink:
    backend = S3StorageBackend.for_backblaze(
        settings.bucket,
        key_id=settings.key_id,
        app_key=settings.app_key,
        region=settings.region,
        auto_lifecycle=False,
    )
    return ObjectStorageSink(backend, key_strategy=KeyStrategy.HIERARCHICAL)


def _require_gmi_key() -> None:
    if not os.getenv("GMI_API_KEY", "").strip():
        raise AudioGenerationConfigurationError(
            "GMI_API_KEY is missing. Configure it in the local .env file and never place "
            "provider credentials in narration JSON or GitHub."
        )


def _default_voice_for_model(model: str) -> str:
    normalised = model.strip().lower()
    for prefix, voice_id in DEFAULT_TTS_VOICES.items():
        if normalised.startswith(prefix):
            return voice_id
    raise AudioGenerationConfigurationError(
        f"Unsupported narration model '{model}'. Use a GMI text-to-speech model beginning with "
        "minimax-tts, elevenlabs-tts or inworld-tts."
    )


def _failure_message(result: Any) -> str:
    error_summary = result.error_summary() or "Unknown provider failure."
    normalised = error_summary.lower()
    if "insufficient credits" in normalised or "402" in normalised:
        return (
            "GMI Cloud authenticated the narration request but refused audio generation because "
            "the organisation has insufficient credits. The narration plan, request, progress "
            "events and failed result remain stored in B2, but no audio clip was produced."
        )
    return f"Genblaze narration audio generation failed: {error_summary}"


def _generate_segment_audio(
    *,
    segment: dict[str, Any],
    narration_id: str,
    provider_model: str,
    voice_id: str,
    storage: ObjectStorageSink,
    timeout: int,
) -> dict[str, Any]:
    scene_number = int(segment["scene_number"])
    reviewed_text = str(segment["reviewed_text"]).strip()
    provider = EvidenceCastGMICloudAudioProvider()

    result = (
        Pipeline(
            f"evidencecast-{narration_id.lower()}-scene-{scene_number:02d}-audio",
            project_id="evidencecast-ai",
        )
        .step(
            provider,
            model=provider_model,
            prompt=reviewed_text,
            voice_id=voice_id,
            language="en",
            output_format="mp3",
            modality=Modality.AUDIO,
            metadata={
                "narration_id": narration_id,
                "segment_id": segment["segment_id"],
                "scene_number": scene_number,
                "evidence_card_ids": list(segment["evidence_card_ids"]),
                "language": segment.get("language", "English (UK)"),
                "voice_style": segment.get("voice_style", "clear, calm and educational"),
                "voice_id": voice_id,
                "pronunciation_notes": segment.get("pronunciation_notes", ""),
            },
        )
        .run(
            sink=storage,
            timeout=timeout,
            max_retries=1,
            raise_on_failure=False,
        )
    )

    if not result.run.steps:
        raise RuntimeError("Genblaze completed without recording an audio-generation step.")
    if result.failed_steps():
        raise RuntimeError(_failure_message(result))

    step = result.run.steps[0]
    if not step.assets:
        raise RuntimeError("The narration step completed without an audio asset.")
    asset = step.assets[0]
    verified = result.manifest.verify()
    if not asset.sha256:
        raise RuntimeError("The B2-persisted narration asset has no SHA-256 value.")
    if not result.manifest.manifest_uri:
        raise RuntimeError("The narration provenance manifest was not persisted to B2.")
    if not verified:
        raise RuntimeError("Manifest.verify() returned False for the narration audio asset.")

    return {
        "scene_number": scene_number,
        "segment_id": segment["segment_id"],
        "evidence_card_ids": segment["evidence_card_ids"],
        "reviewed_text": reviewed_text,
        "provider": "gmicloud",
        "model": provider_model,
        "voice_id": voice_id,
        "run_id": result.run.run_id,
        "step_status": str(step.status),
        "asset_url": asset.url,
        "asset_sha256": asset.sha256,
        "asset_mime_type": asset.mime_type,
        "manifest_uri": result.manifest.manifest_uri,
        "manifest_canonical_hash": result.manifest.canonical_hash,
        "manifest_verified": verified,
        "completed_at": datetime.now(UTC).isoformat(),
    }


def stream_narration_audio_generation(
    *,
    narration_plan: dict[str, Any],
    store: B2EvidenceStore,
    model: str | None = None,
    timeout: int = 180,
) -> Iterator[AudioProgressEvent]:
    """Generate three approved narration clips and stream durable progress events."""

    _require_gmi_key()
    segments = list(narration_plan.get("segments", []))
    require_all_segments_approved(segments)

    source_sha256 = str(narration_plan["source_sha256"])
    storyboard_id = str(narration_plan["storyboard_id"])
    narration_id = str(narration_plan["narration_id"])
    provider_model = model.strip() if model and model.strip() else DEFAULT_AUDIO_MODEL
    voice_id = _default_voice_for_model(provider_model)
    audio_run_id = f"AUD-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    storage = _create_genblaze_storage(store.settings)
    sequence = 0

    def persist_event(
        stage: str,
        message: str,
        progress: float,
        *,
        scene_number: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AudioProgressEvent:
        nonlocal sequence
        sequence += 1
        event = AudioProgressEvent(
            sequence=sequence,
            stage=stage,
            message=message,
            progress=max(0.0, min(1.0, progress)),
            created_at=datetime.now(UTC).isoformat(),
            scene_number=scene_number,
            payload=payload,
        )
        stored = store.store_audio_progress_event(
            source_sha256=source_sha256,
            storyboard_id=storyboard_id,
            narration_id=narration_id,
            audio_run_id=audio_run_id,
            sequence=sequence,
            event=event.to_dict(),
        )
        enriched = dict(payload or {})
        enriched["progress_event_uri"] = stored.uri
        return AudioProgressEvent(
            sequence=event.sequence,
            stage=event.stage,
            message=event.message,
            progress=event.progress,
            created_at=event.created_at,
            scene_number=event.scene_number,
            payload=enriched,
        )

    request = {
        "audio_run_id": audio_run_id,
        "narration_id": narration_id,
        "storyboard_id": storyboard_id,
        "source_sha256": source_sha256,
        "provider": "gmicloud",
        "model": provider_model,
        "voice_id": voice_id,
        "timeout": timeout,
        "segment_count": 3,
        "language": narration_plan.get("language", "English (UK)"),
        "voice_style": narration_plan.get("voice_style", "clear, calm and educational"),
        "created_at": datetime.now(UTC).isoformat(),
    }
    request_object = store.store_audio_generation_request(
        source_sha256=source_sha256,
        storyboard_id=storyboard_id,
        narration_id=narration_id,
        audio_run_id=audio_run_id,
        request=request,
    )
    yield persist_event(
        "audio_generation_started",
        "Narration generation request saved to B2; preparing three approved audio segments.",
        0.05,
        payload={"audio_run_id": audio_run_id, "generation_request_uri": request_object.uri},
    )

    segment_results: list[dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        scene_number = int(segment["scene_number"])
        segment_request = {
            "audio_run_id": audio_run_id,
            "narration_id": narration_id,
            "storyboard_id": storyboard_id,
            "source_sha256": source_sha256,
            "scene_number": scene_number,
            "segment_id": segment["segment_id"],
            "evidence_card_ids": segment["evidence_card_ids"],
            "reviewed_text": segment["reviewed_text"],
            "pronunciation_notes": segment.get("pronunciation_notes", ""),
            "provider": "gmicloud",
            "model": provider_model,
            "voice_id": voice_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        segment_request_object = store.store_audio_segment_request(
            source_sha256=source_sha256,
            storyboard_id=storyboard_id,
            narration_id=narration_id,
            audio_run_id=audio_run_id,
            scene_number=scene_number,
            request=segment_request,
        )
        start_progress = 0.08 + ((index - 1) * 0.28)
        yield persist_event(
            "audio_segment_submitted",
            f"Scene {scene_number} narration request saved; submitting it through Genblaze.",
            start_progress,
            scene_number=scene_number,
            payload={"segment_request_uri": segment_request_object.uri},
        )

        try:
            enriched_segment = dict(segment)
            enriched_segment["language"] = narration_plan.get("language", "English (UK)")
            enriched_segment["voice_style"] = narration_plan.get(
                "voice_style", "clear, calm and educational"
            )
            segment_result = _generate_segment_audio(
                segment=enriched_segment,
                narration_id=narration_id,
                provider_model=provider_model,
                voice_id=voice_id,
                storage=storage,
                timeout=timeout,
            )
            result_object = store.store_audio_segment_result(
                source_sha256=source_sha256,
                storyboard_id=storyboard_id,
                narration_id=narration_id,
                audio_run_id=audio_run_id,
                scene_number=scene_number,
                result=segment_result,
            )
            segment_result["result_record_uri"] = result_object.uri
            segment_results.append(segment_result)
            yield persist_event(
                "audio_segment_completed",
                f"Scene {scene_number} narration audio and verified manifest are stored in B2.",
                start_progress + 0.24,
                scene_number=scene_number,
                payload=segment_result,
            )
        except Exception as exc:
            failure = {
                "audio_run_id": audio_run_id,
                "narration_id": narration_id,
                "scene_number": scene_number,
                "segment_id": segment["segment_id"],
                "status": "failed",
                "error": str(exc),
                "failed_at": datetime.now(UTC).isoformat(),
            }
            failure_object = store.store_audio_segment_result(
                source_sha256=source_sha256,
                storyboard_id=storyboard_id,
                narration_id=narration_id,
                audio_run_id=audio_run_id,
                scene_number=scene_number,
                result=failure,
            )
            summary = {
                "audio_run_id": audio_run_id,
                "narration_id": narration_id,
                "storyboard_id": storyboard_id,
                "source_sha256": source_sha256,
                "status": "failed",
                "provider": "gmicloud",
                "model": provider_model,
                "voice_id": voice_id,
                "completed_segments": segment_results,
                "failed_segment": failure,
                "saved_at": datetime.now(UTC).isoformat(),
            }
            summary_object = store.store_audio_generation_summary(
                source_sha256=source_sha256,
                storyboard_id=storyboard_id,
                narration_id=narration_id,
                audio_run_id=audio_run_id,
                summary=summary,
            )
            yield persist_event(
                "audio_generation_failed",
                f"Scene {scene_number} narration failed: {exc}",
                start_progress + 0.05,
                scene_number=scene_number,
                payload={
                    "audio_run_id": audio_run_id,
                    "segment_result_uri": failure_object.uri,
                    "generation_summary_uri": summary_object.uri,
                    "error": str(exc),
                },
            )
            return

    summary = {
        "audio_run_id": audio_run_id,
        "narration_id": narration_id,
        "storyboard_id": storyboard_id,
        "source_sha256": source_sha256,
        "status": "completed",
        "provider": "gmicloud",
        "model": provider_model,
        "voice_id": voice_id,
        "segment_count": len(segment_results),
        "segments": segment_results,
        "saved_at": datetime.now(UTC).isoformat(),
    }
    summary_object = store.store_audio_generation_summary(
        source_sha256=source_sha256,
        storyboard_id=storyboard_id,
        narration_id=narration_id,
        audio_run_id=audio_run_id,
        summary=summary,
    )
    yield persist_event(
        "audio_generation_completed",
        "All three narration clips and provenance manifests are stored in B2.",
        1.0,
        payload={
            "audio_run_id": audio_run_id,
            "generation_summary_uri": summary_object.uri,
            "summary": summary,
        },
    )
