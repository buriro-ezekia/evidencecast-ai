# Generates three storyboard scene images through Genblaze while streaming and persisting progress to Backblaze B2.
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Iterator
from uuid import uuid4

from genblaze_core import KeyStrategy, Modality, ObjectStorageSink, Pipeline
from genblaze_gmicloud import GMICloudImageProvider
from genblaze_s3 import S3StorageBackend

from .storage import B2EvidenceStore, B2Settings


class ImageGenerationConfigurationError(RuntimeError):
    """Raised when a selected image provider is unavailable or unconfigured."""


@dataclass(frozen=True)
class GenerationEvent:
    """One user-visible and B2-persisted progress update."""

    sequence: int
    stage: str
    message: str
    progress: float
    created_at: str
    scene_number: int | None = None
    payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PROVIDER_ENVIRONMENT_VARIABLES = {
    "gmicloud": "GMI_API_KEY",
    "openai": "OPENAI_API_KEY",
}

DEFAULT_MODELS = {
    "gmicloud": "seedream-5.0-lite",
    "openai": "gpt-image-1",
}


def _create_genblaze_storage(settings: B2Settings) -> ObjectStorageSink:
    backend = S3StorageBackend.for_backblaze(
        settings.bucket,
        key_id=settings.key_id,
        app_key=settings.app_key,
        region=settings.region,
        auto_lifecycle=False,
    )
    return ObjectStorageSink(backend, key_strategy=KeyStrategy.HIERARCHICAL)


def _create_provider(
    provider_name: str,
    *,
    model: str | None,
    size: str,
    quality: str,
    aspect_ratio: str,
) -> tuple[Any, str, dict[str, Any]]:
    normalised = provider_name.strip().lower()
    if normalised not in PROVIDER_ENVIRONMENT_VARIABLES:
        raise ImageGenerationConfigurationError(
            f"Unsupported image provider '{provider_name}'. Choose gmicloud or openai."
        )

    environment_variable = PROVIDER_ENVIRONMENT_VARIABLES[normalised]
    if not os.getenv(environment_variable, "").strip():
        raise ImageGenerationConfigurationError(
            f"{environment_variable} is missing. Configure it in the local .env file; "
            "never place provider credentials in storyboard JSON or GitHub."
        )

    resolved_model = model.strip() if model and model.strip() else DEFAULT_MODELS[normalised]
    if normalised == "gmicloud":
        return GMICloudImageProvider(), resolved_model, {"aspect_ratio": aspect_ratio}

    try:
        from genblaze_openai import DalleProvider
    except ImportError as exc:
        raise ImageGenerationConfigurationError(
            "The OpenAI Genblaze connector is not installed. Run pip install -r requirements.txt."
        ) from exc
    return DalleProvider(), resolved_model, {"size": size, "quality": quality}


def _provider_failure_message(provider_name: str, result: Any) -> str:
    error_summary = result.error_summary() or "Unknown provider failure."
    normalised = error_summary.lower()
    if provider_name == "gmicloud" and (
        "insufficient credits" in normalised or "402" in normalised
    ):
        return (
            "GMI Cloud authenticated the request but refused image generation because the "
            "organisation has insufficient credits. The storyboard and request records remain "
            "stored in B2, but no scene image was produced."
        )
    return f"Genblaze image generation failed: {error_summary}"


def _generate_scene_image(
    *,
    scene: dict[str, Any],
    provider_name: str,
    model: str | None,
    storage: ObjectStorageSink,
    timeout: int,
    size: str,
    quality: str,
    aspect_ratio: str,
    storyboard_id: str,
) -> dict[str, Any]:
    provider, resolved_model, provider_parameters = _create_provider(
        provider_name,
        model=model,
        size=size,
        quality=quality,
        aspect_ratio=aspect_ratio,
    )
    scene_number = int(scene["scene_number"])
    result = (
        Pipeline(
            f"evidencecast-{storyboard_id.lower()}-scene-{scene_number:02d}",
            project_id="evidencecast-ai",
        )
        .step(
            provider,
            model=resolved_model,
            prompt=str(scene["visual_prompt"]),
            modality=Modality.IMAGE,
            metadata={
                "storyboard_id": storyboard_id,
                "scene_number": scene_number,
                "evidence_card_ids": list(scene["evidence_card_ids"]),
            },
            **provider_parameters,
        )
        .run(
            sink=storage,
            timeout=timeout,
            max_retries=1,
            raise_on_failure=False,
        )
    )

    if not result.run.steps:
        raise RuntimeError("Genblaze completed without recording a scene-generation step.")
    if result.failed_steps():
        raise RuntimeError(_provider_failure_message(provider_name, result))

    step = result.run.steps[0]
    if not step.assets:
        raise RuntimeError("The scene-generation step completed without an image asset.")
    asset = step.assets[0]
    verified = result.manifest.verify()
    if not asset.sha256:
        raise RuntimeError("The B2-persisted scene image has no SHA-256 value.")
    if not result.manifest.manifest_uri:
        raise RuntimeError("The scene provenance manifest was not persisted to B2.")
    if not verified:
        raise RuntimeError("Manifest.verify() returned False for the generated scene image.")

    return {
        "scene_number": scene_number,
        "title": scene["title"],
        "evidence_card_ids": scene["evidence_card_ids"],
        "provider": provider_name,
        "model": resolved_model,
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


def stream_storyboard_image_generation(
    *,
    storyboard: dict[str, Any],
    store: B2EvidenceStore,
    provider_name: str,
    model: str | None = None,
    timeout: int = 180,
    size: str = "1536x1024",
    quality: str = "low",
    aspect_ratio: str = "16:9",
) -> Iterator[GenerationEvent]:
    """Generate all three scene images and stream durable progress events."""

    scenes = list(storyboard.get("scenes", []))
    if storyboard.get("scene_count") != 3 or len(scenes) != 3:
        raise ValueError("A validated three-scene storyboard is required for image generation.")

    source_sha256 = str(storyboard["source_sha256"])
    storyboard_id = str(storyboard["storyboard_id"])
    generation_id = f"GEN-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    storage = _create_genblaze_storage(store.settings)
    sequence = 0

    def persist_event(
        stage: str,
        message: str,
        progress: float,
        *,
        scene_number: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> GenerationEvent:
        nonlocal sequence
        sequence += 1
        event = GenerationEvent(
            sequence=sequence,
            stage=stage,
            message=message,
            progress=max(0.0, min(1.0, progress)),
            created_at=datetime.now(UTC).isoformat(),
            scene_number=scene_number,
            payload=payload,
        )
        stored_event = store.store_progress_event(
            source_sha256=source_sha256,
            storyboard_id=storyboard_id,
            generation_id=generation_id,
            sequence=sequence,
            event=event.to_dict(),
        )
        enriched_payload = dict(payload or {})
        enriched_payload["progress_event_uri"] = stored_event.uri
        return GenerationEvent(
            sequence=event.sequence,
            stage=event.stage,
            message=event.message,
            progress=event.progress,
            created_at=event.created_at,
            scene_number=event.scene_number,
            payload=enriched_payload,
        )

    generation_request = {
        "generation_id": generation_id,
        "storyboard_id": storyboard_id,
        "source_sha256": source_sha256,
        "provider": provider_name,
        "model": model or DEFAULT_MODELS.get(provider_name, ""),
        "timeout": timeout,
        "size": size,
        "quality": quality,
        "aspect_ratio": aspect_ratio,
        "scene_count": 3,
        "created_at": datetime.now(UTC).isoformat(),
    }
    request_object = store.store_generation_request(
        source_sha256=source_sha256,
        storyboard_id=storyboard_id,
        generation_id=generation_id,
        request=generation_request,
    )
    yield persist_event(
        "generation_started",
        "Generation request saved to B2; preparing three scene images.",
        0.05,
        payload={"generation_id": generation_id, "generation_request_uri": request_object.uri},
    )

    scene_results: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes, start=1):
        scene_number = int(scene["scene_number"])
        scene_request = {
            "generation_id": generation_id,
            "storyboard_id": storyboard_id,
            "source_sha256": source_sha256,
            "scene_number": scene_number,
            "title": scene["title"],
            "evidence_card_ids": scene["evidence_card_ids"],
            "visual_prompt": scene["visual_prompt"],
            "provider": provider_name,
            "model": model or DEFAULT_MODELS.get(provider_name, ""),
            "created_at": datetime.now(UTC).isoformat(),
        }
        scene_request_object = store.store_scene_request(
            source_sha256=source_sha256,
            storyboard_id=storyboard_id,
            generation_id=generation_id,
            scene_number=scene_number,
            request=scene_request,
        )
        start_progress = 0.08 + ((index - 1) * 0.28)
        yield persist_event(
            "scene_submitted",
            f"Scene {scene_number} request saved; submitting it through Genblaze.",
            start_progress,
            scene_number=scene_number,
            payload={"scene_request_uri": scene_request_object.uri},
        )

        try:
            scene_result = _generate_scene_image(
                scene=scene,
                provider_name=provider_name,
                model=model,
                storage=storage,
                timeout=timeout,
                size=size,
                quality=quality,
                aspect_ratio=aspect_ratio,
                storyboard_id=storyboard_id,
            )
            result_object = store.store_scene_result(
                source_sha256=source_sha256,
                storyboard_id=storyboard_id,
                generation_id=generation_id,
                scene_number=scene_number,
                result=scene_result,
            )
            scene_result["result_record_uri"] = result_object.uri
            scene_results.append(scene_result)
            yield persist_event(
                "scene_completed",
                f"Scene {scene_number} image and verified provenance manifest are stored in B2.",
                start_progress + 0.24,
                scene_number=scene_number,
                payload=scene_result,
            )
        except Exception as exc:
            failure = {
                "generation_id": generation_id,
                "storyboard_id": storyboard_id,
                "scene_number": scene_number,
                "status": "failed",
                "error": str(exc),
                "failed_at": datetime.now(UTC).isoformat(),
            }
            failure_object = store.store_scene_result(
                source_sha256=source_sha256,
                storyboard_id=storyboard_id,
                generation_id=generation_id,
                scene_number=scene_number,
                result=failure,
            )
            summary = {
                "generation_id": generation_id,
                "storyboard_id": storyboard_id,
                "source_sha256": source_sha256,
                "status": "failed",
                "provider": provider_name,
                "model": model or DEFAULT_MODELS.get(provider_name, ""),
                "completed_scenes": scene_results,
                "failed_scene": failure,
                "saved_at": datetime.now(UTC).isoformat(),
            }
            summary_object = store.store_generation_summary(
                source_sha256=source_sha256,
                storyboard_id=storyboard_id,
                generation_id=generation_id,
                summary=summary,
            )
            yield persist_event(
                "generation_failed",
                f"Scene {scene_number} failed: {exc}",
                start_progress + 0.05,
                scene_number=scene_number,
                payload={
                    "generation_id": generation_id,
                    "scene_result_uri": failure_object.uri,
                    "generation_summary_uri": summary_object.uri,
                    "error": str(exc),
                },
            )
            return

    summary = {
        "generation_id": generation_id,
        "storyboard_id": storyboard_id,
        "source_sha256": source_sha256,
        "status": "completed",
        "provider": provider_name,
        "model": model or DEFAULT_MODELS.get(provider_name, ""),
        "scene_count": len(scene_results),
        "scenes": scene_results,
        "saved_at": datetime.now(UTC).isoformat(),
    }
    summary_object = store.store_generation_summary(
        source_sha256=source_sha256,
        storyboard_id=storyboard_id,
        generation_id=generation_id,
        summary=summary,
    )
    yield persist_event(
        "generation_completed",
        "All three scene images and provenance manifests are stored in B2.",
        1.0,
        payload={
            "generation_id": generation_id,
            "generation_summary_uri": summary_object.uri,
            "summary": summary,
        },
    )
