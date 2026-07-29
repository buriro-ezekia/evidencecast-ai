# Runs controlled NVIDIA image and narration validation through Genblaze and Backblaze B2.
from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from genblaze_core import KeyStrategy, Modality, ObjectStorageSink, Pipeline
from genblaze_core.exceptions import ProviderError
from genblaze_core.models.asset import Asset
from genblaze_core.models.enums import ProviderErrorCode
from genblaze_core.models.step import Step
from genblaze_core.providers.base import ProviderCapabilities, SyncProvider
from genblaze_core.runnable.config import RunnableConfig
from genblaze_nvidia import NvidiaImageProvider
from genblaze_s3 import S3StorageBackend

from .audio_store import B2AudioStore
from .storage import B2EvidenceStore, B2Settings

DEFAULT_NVIDIA_IMAGE_MODEL = "stabilityai/stable-diffusion-3-5-large"
DEFAULT_NVIDIA_AUDIO_MODEL = "nvidia/magpie-tts-multilingual"
DEFAULT_NVIDIA_TTS_ENDPOINT = (
    "https://877104f7-e885-42b9-8de8-f6e4c6303969.invocation.api.nvcf.nvidia.com"
    "/v1/audio/synthesize"
)
DEFAULT_NVIDIA_VOICE = "Magpie-Multilingual.EN-US.Aria"
DEFAULT_NVIDIA_LANGUAGE = "en-US"


class NvidiaConfigurationError(RuntimeError):
    """Raised when NVIDIA live validation is not configured safely."""


class NvidiaHostedTTSProvider(SyncProvider):
    """Genblaze provider for NVIDIA's hosted Magpie multilingual TTS endpoint."""

    name = "nvidia-hosted-tts"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        endpoint: str | None = None,
        http_timeout: float = 180.0,
        output_dir: str | Path | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        super().__init__()
        self._api_key = (api_key or os.getenv("NVIDIA_API_KEY", "")).strip()
        self._endpoint = (
            endpoint
            or os.getenv("NVIDIA_TTS_ENDPOINT", "").strip()
            or DEFAULT_NVIDIA_TTS_ENDPOINT
        )
        self._output_dir = Path(output_dir) if output_dir is not None else None
        self._client = http_client or httpx.Client(timeout=http_timeout)
        self._owns_client = http_client is None

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported_modalities=[Modality.AUDIO],
            supported_inputs=["text"],
            output_formats=["audio/wav"],
            models=[DEFAULT_NVIDIA_AUDIO_MODEL],
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def generate(self, step: Step, config: RunnableConfig | None = None) -> Step:
        if not self._api_key:
            raise ProviderError(
                "NVIDIA_API_KEY is not configured.",
                error_code=ProviderErrorCode.AUTH_FAILURE,
            )

        text = str(step.prompt or "").strip()
        if not text:
            raise ProviderError(
                "NVIDIA narration text cannot be empty.",
                error_code=ProviderErrorCode.INVALID_INPUT,
            )
        if len(text) > 2000:
            raise ProviderError(
                "NVIDIA narration text exceeds the 2,000-character request limit.",
                error_code=ProviderErrorCode.INVALID_INPUT,
            )

        language = str(step.params.get("language", DEFAULT_NVIDIA_LANGUAGE)).strip()
        voice = str(step.params.get("voice", DEFAULT_NVIDIA_VOICE)).strip()
        encoding = str(step.params.get("encoding", "LINEAR_PCM")).strip()
        sample_rate_hz = int(step.params.get("sample_rate_hz", 44100))

        try:
            response = self._client.post(
                self._endpoint,
                headers={"Authorization": f"Bearer {self._api_key}"},
                data={
                    "text": text,
                    "language": language,
                    "voice": voice,
                    "encoding": encoding,
                    "sample_rate_hz": str(sample_rate_hz),
                },
            )
        except httpx.TimeoutException as exc:
            raise ProviderError(
                f"NVIDIA TTS request timed out: {exc}",
                error_code=ProviderErrorCode.TIMEOUT,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"NVIDIA TTS transport failed: {exc}",
                error_code=ProviderErrorCode.SERVER_ERROR,
            ) from exc

        if response.status_code != 200:
            detail = response.text.strip() or "No error detail returned."
            if response.status_code in {401, 403}:
                error_code = ProviderErrorCode.AUTH_FAILURE
            elif response.status_code == 429:
                error_code = ProviderErrorCode.RATE_LIMIT
            elif response.status_code >= 500:
                error_code = ProviderErrorCode.SERVER_ERROR
            else:
                error_code = ProviderErrorCode.INVALID_INPUT
            raise ProviderError(
                f"NVIDIA TTS failed ({response.status_code}): {detail[:1000]}",
                error_code=error_code,
            )

        audio_bytes = bytes(response.content)
        if not audio_bytes:
            raise ProviderError(
                "NVIDIA TTS returned an empty audio response.",
                error_code=ProviderErrorCode.SERVER_ERROR,
            )

        output_dir = self._output_dir or Path(tempfile.gettempdir())
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"nvidia-magpie-{uuid4().hex[:12]}.wav"
        output_path.write_bytes(audio_bytes)

        step.provider_payload = {
            "nvidia": {
                "status": "succeeded",
                "endpoint_kind": "hosted-magpie-tts",
                "language": language,
                "voice": voice,
                "sample_rate_hz": sample_rate_hz,
            }
        }
        step.assets.append(
            Asset(
                url=output_path.resolve().as_uri(),
                media_type="audio/wav",
                sha256=hashlib.sha256(audio_bytes).hexdigest(),
                size_bytes=len(audio_bytes),
            )
        )
        return step


def nvidia_key_configured() -> bool:
    """Return only whether an NVIDIA key exists; never expose its value."""

    return bool(os.getenv("NVIDIA_API_KEY", "").strip())


def _require_nvidia_key() -> None:
    if not nvidia_key_configured():
        raise NvidiaConfigurationError(
            "NVIDIA_API_KEY is missing. Add it to the local .env file and never paste it into "
            "Streamlit fields, GitHub, logs or chat messages."
        )


def _create_genblaze_storage(settings: B2Settings) -> ObjectStorageSink:
    backend = S3StorageBackend.for_backblaze(
        settings.bucket,
        key_id=settings.key_id,
        app_key=settings.app_key,
        region=settings.region,
        auto_lifecycle=False,
    )
    return ObjectStorageSink(backend, key_strategy=KeyStrategy.HIERARCHICAL)


def _scene(storyboard: dict[str, Any], scene_number: int) -> dict[str, Any]:
    scenes = list(storyboard.get("scenes", []))
    if storyboard.get("scene_count") != 3 or len(scenes) != 3:
        raise ValueError("A validated three-scene storyboard is required.")
    for candidate in scenes:
        if int(candidate.get("scene_number", 0)) == scene_number:
            return candidate
    raise ValueError(f"Storyboard scene {scene_number} was not found.")


def _segment(narration: dict[str, Any], scene_number: int) -> dict[str, Any]:
    segments = list(narration.get("segments", []))
    if len(segments) != 3:
        raise ValueError("A completed three-segment narration review is required.")
    for candidate in segments:
        if int(candidate.get("scene_number", 0)) == scene_number:
            if str(candidate.get("review_status", "")).lower() != "approved":
                raise ValueError(f"Narration scene {scene_number} is not approved.")
            if not str(candidate.get("reviewed_text", "")).strip():
                raise ValueError(f"Narration scene {scene_number} has no reviewed text.")
            return candidate
    raise ValueError(f"Narration scene {scene_number} was not found.")


def _verified_asset_record(result: Any, *, kind: str) -> dict[str, Any]:
    if not result.run.steps:
        raise RuntimeError(f"Genblaze recorded no {kind} step.")
    if result.failed_steps():
        raise RuntimeError(result.error_summary() or f"NVIDIA {kind} generation failed.")
    step = result.run.steps[0]
    if not step.assets:
        raise RuntimeError(f"NVIDIA {kind} generation returned no asset.")
    asset = step.assets[0]
    verified = result.manifest.verify()
    if not asset.sha256:
        raise RuntimeError(f"The B2-persisted NVIDIA {kind} asset has no SHA-256 value.")
    if not result.manifest.manifest_uri:
        raise RuntimeError(f"The NVIDIA {kind} provenance manifest was not persisted to B2.")
    if not verified:
        raise RuntimeError(f"Manifest.verify() returned False for the NVIDIA {kind} asset.")
    return {
        "run_id": result.run.run_id,
        "step_status": str(step.status),
        "asset_url": asset.url,
        "asset_sha256": asset.sha256,
        "asset_mime_type": asset.mime_type,
        "manifest_uri": result.manifest.manifest_uri,
        "manifest_canonical_hash": result.manifest.canonical_hash,
        "manifest_verified": verified,
    }


def generate_nvidia_image_scene(
    *,
    storyboard: dict[str, Any],
    scene_number: int,
    store: B2EvidenceStore,
    model: str = DEFAULT_NVIDIA_IMAGE_MODEL,
    timeout: int = 240,
    aspect_ratio: str = "16:9",
) -> dict[str, Any]:
    """Generate one storyboard image through the official Genblaze NVIDIA connector."""

    _require_nvidia_key()
    scene = _scene(storyboard, scene_number)
    source_sha256 = str(storyboard["source_sha256"])
    storyboard_id = str(storyboard["storyboard_id"])
    generation_id = f"NVIDIA-IMG-S{scene_number}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    request = {
        "generation_id": generation_id,
        "provider": "nvidia",
        "model": model,
        "storyboard_id": storyboard_id,
        "source_sha256": source_sha256,
        "scene_number": scene_number,
        "evidence_card_ids": list(scene["evidence_card_ids"]),
        "visual_prompt": scene["visual_prompt"],
        "aspect_ratio": aspect_ratio,
        "created_at": datetime.now(UTC).isoformat(),
    }
    request_object = store.store_generation_request(
        source_sha256=source_sha256,
        storyboard_id=storyboard_id,
        generation_id=generation_id,
        request=request,
    )
    store.store_scene_request(
        source_sha256=source_sha256,
        storyboard_id=storyboard_id,
        generation_id=generation_id,
        scene_number=scene_number,
        request=request,
    )

    try:
        storage = _create_genblaze_storage(store.settings)
        with tempfile.TemporaryDirectory(prefix="evidencecast-nvidia-image-") as output_dir:
            provider = NvidiaImageProvider(output_dir=output_dir, http_timeout=float(timeout))
            try:
                result = (
                    Pipeline(
                        f"evidencecast-nvidia-{storyboard_id.lower()}-scene-{scene_number:02d}",
                        project_id="evidencecast-ai",
                    )
                    .step(
                        provider,
                        model=model,
                        prompt=str(scene["visual_prompt"]),
                        modality=Modality.IMAGE,
                        aspect_ratio=aspect_ratio,
                        metadata={
                            "storyboard_id": storyboard_id,
                            "scene_number": scene_number,
                            "evidence_card_ids": list(scene["evidence_card_ids"]),
                            "provider": "nvidia",
                        },
                    )
                    .run(
                        sink=storage,
                        timeout=timeout,
                        max_retries=0,
                        raise_on_failure=False,
                    )
                )
            finally:
                provider.close()

        asset_record = _verified_asset_record(result, kind="image")
        scene_result = {
            **request,
            **asset_record,
            "status": "completed",
            "completed_at": datetime.now(UTC).isoformat(),
        }
        result_object = store.store_scene_result(
            source_sha256=source_sha256,
            storyboard_id=storyboard_id,
            generation_id=generation_id,
            scene_number=scene_number,
            result=scene_result,
        )
        scene_result["result_record_uri"] = result_object.uri
        summary = {
            "generation_id": generation_id,
            "status": "completed",
            "provider": "nvidia",
            "model": model,
            "scene": scene_result,
            "request_uri": request_object.uri,
            "saved_at": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:
        failure = {
            **request,
            "status": "failed",
            "error": str(exc),
            "failed_at": datetime.now(UTC).isoformat(),
        }
        result_object = store.store_scene_result(
            source_sha256=source_sha256,
            storyboard_id=storyboard_id,
            generation_id=generation_id,
            scene_number=scene_number,
            result=failure,
        )
        summary = {
            "generation_id": generation_id,
            "status": "failed",
            "provider": "nvidia",
            "model": model,
            "failed_scene": failure,
            "result_record_uri": result_object.uri,
            "request_uri": request_object.uri,
            "saved_at": datetime.now(UTC).isoformat(),
        }

    summary_object = store.store_generation_summary(
        source_sha256=source_sha256,
        storyboard_id=storyboard_id,
        generation_id=generation_id,
        summary=summary,
    )
    summary["generation_summary_uri"] = summary_object.uri
    return summary


def generate_nvidia_audio_segment(
    *,
    narration: dict[str, Any],
    scene_number: int,
    store: B2AudioStore,
    model: str = DEFAULT_NVIDIA_AUDIO_MODEL,
    voice: str = DEFAULT_NVIDIA_VOICE,
    language: str = DEFAULT_NVIDIA_LANGUAGE,
    endpoint: str | None = None,
    timeout: int = 240,
    sample_rate_hz: int = 44100,
) -> dict[str, Any]:
    """Generate one approved narration clip via a Genblaze-wrapped NVIDIA TTS provider."""

    _require_nvidia_key()
    segment = _segment(narration, scene_number)
    source_sha256 = str(narration["source_sha256"])
    storyboard_id = str(narration["storyboard_id"])
    narration_id = str(narration["narration_id"])
    audio_run_id = f"NVIDIA-AUD-S{scene_number}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    request = {
        "audio_run_id": audio_run_id,
        "provider": "nvidia",
        "model": model,
        "storyboard_id": storyboard_id,
        "narration_id": narration_id,
        "source_sha256": source_sha256,
        "scene_number": scene_number,
        "segment_id": segment["segment_id"],
        "evidence_card_ids": list(segment["evidence_card_ids"]),
        "reviewed_text": segment["reviewed_text"],
        "language": language,
        "voice": voice,
        "encoding": "LINEAR_PCM",
        "sample_rate_hz": sample_rate_hz,
        "created_at": datetime.now(UTC).isoformat(),
    }
    request_object = store.store_audio_generation_request(
        source_sha256=source_sha256,
        storyboard_id=storyboard_id,
        narration_id=narration_id,
        audio_run_id=audio_run_id,
        request=request,
    )
    store.store_audio_segment_request(
        source_sha256=source_sha256,
        storyboard_id=storyboard_id,
        narration_id=narration_id,
        audio_run_id=audio_run_id,
        scene_number=scene_number,
        request=request,
    )

    try:
        storage = _create_genblaze_storage(store.settings)
        with tempfile.TemporaryDirectory(prefix="evidencecast-nvidia-audio-") as output_dir:
            provider = NvidiaHostedTTSProvider(
                endpoint=endpoint,
                http_timeout=float(timeout),
                output_dir=output_dir,
            )
            try:
                result = (
                    Pipeline(
                        f"evidencecast-nvidia-{narration_id.lower()}-scene-{scene_number:02d}-audio",
                        project_id="evidencecast-ai",
                    )
                    .step(
                        provider,
                        model=model,
                        prompt=str(segment["reviewed_text"]),
                        modality=Modality.AUDIO,
                        language=language,
                        voice=voice,
                        encoding="LINEAR_PCM",
                        sample_rate_hz=sample_rate_hz,
                        metadata={
                            "narration_id": narration_id,
                            "segment_id": segment["segment_id"],
                            "scene_number": scene_number,
                            "evidence_card_ids": list(segment["evidence_card_ids"]),
                            "provider": "nvidia",
                        },
                    )
                    .run(
                        sink=storage,
                        timeout=timeout,
                        max_retries=0,
                        raise_on_failure=False,
                    )
                )
            finally:
                provider.close()

        asset_record = _verified_asset_record(result, kind="audio")
        segment_result = {
            **request,
            **asset_record,
            "status": "completed",
            "completed_at": datetime.now(UTC).isoformat(),
        }
        result_object = store.store_audio_segment_result(
            source_sha256=source_sha256,
            storyboard_id=storyboard_id,
            narration_id=narration_id,
            audio_run_id=audio_run_id,
            scene_number=scene_number,
            result=segment_result,
        )
        segment_result["result_record_uri"] = result_object.uri
        summary = {
            "audio_run_id": audio_run_id,
            "status": "completed",
            "provider": "nvidia",
            "model": model,
            "segment": segment_result,
            "request_uri": request_object.uri,
            "saved_at": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:
        failure = {
            **request,
            "status": "failed",
            "error": str(exc),
            "failed_at": datetime.now(UTC).isoformat(),
        }
        result_object = store.store_audio_segment_result(
            source_sha256=source_sha256,
            storyboard_id=storyboard_id,
            narration_id=narration_id,
            audio_run_id=audio_run_id,
            scene_number=scene_number,
            result=failure,
        )
        summary = {
            "audio_run_id": audio_run_id,
            "status": "failed",
            "provider": "nvidia",
            "model": model,
            "failed_segment": failure,
            "result_record_uri": result_object.uri,
            "request_uri": request_object.uri,
            "saved_at": datetime.now(UTC).isoformat(),
        }

    summary_object = store.store_audio_generation_summary(
        source_sha256=source_sha256,
        storyboard_id=storyboard_id,
        narration_id=narration_id,
        audio_run_id=audio_run_id,
        summary=summary,
    )
    summary["generation_summary_uri"] = summary_object.uri
    return summary
