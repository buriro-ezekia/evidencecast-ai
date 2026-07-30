# Regenerates one image scene or narration segment with parent-child lineage and bounded retries.
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Iterator

from .audio import (
    DEFAULT_AUDIO_MODEL,
    _create_genblaze_storage as _create_audio_storage,
    _default_voice_for_model,
    _generate_segment_audio,
)
from .evaluation import create_regeneration_request, retry_delay_seconds
from .final_store import B2FinalMediaStore
from .media import DEFAULT_MODELS, _generate_scene_image


@dataclass(frozen=True)
class RegenerationEvent:
    """One user-visible regeneration and retry event."""

    stage: str
    message: str
    created_at: str
    child_run_id: str
    parent_run_id: str
    media_kind: str
    scene_number: int
    attempt: int
    payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_retryable_provider_error(error: Exception | str) -> bool:
    """Retry only transient provider failures, never validation, auth, policy or credit failures."""

    message = str(error).lower()
    non_retryable_terms = (
        "insufficient credits",
        "402",
        "invalid payload",
        "required parameter",
        "400",
        "unauthorised",
        "unauthorized",
        "401",
        "forbidden",
        "403",
        "content policy",
        "safety",
    )
    if any(term in message for term in non_retryable_terms):
        return False
    retryable_terms = (
        "timeout",
        "timed out",
        "rate limit",
        "429",
        "500",
        "502",
        "503",
        "504",
        "temporarily unavailable",
        "connection reset",
        "connection error",
    )
    return any(term in message for term in retryable_terms)


def stream_scene_regeneration(
    *,
    storyboard: dict[str, Any],
    narration_plan: dict[str, Any],
    store: B2FinalMediaStore,
    media_kind: str,
    scene_number: int,
    parent_run_id: str,
    reason: str,
    provider_name: str = "gmicloud",
    model: str | None = None,
    timeout: int = 180,
    max_attempts: int = 2,
    image_size: str = "1536x1024",
    image_quality: str = "low",
    aspect_ratio: str = "16:9",
) -> Iterator[RegenerationEvent]:
    """Regenerate one scene and persist lineage, attempts, retry decisions and final result."""

    request = create_regeneration_request(
        media_kind=media_kind,
        scene_number=scene_number,
        parent_run_id=parent_run_id,
        reason=reason,
        attempt=1,
        max_attempts=max_attempts,
    )
    child_run_id = str(request["child_run_id"])
    normalised_kind = str(request["media_kind"])
    source_sha256 = str(storyboard["source_sha256"])
    storyboard_id = str(storyboard["storyboard_id"])
    request.update(
        {
            "source_sha256": source_sha256,
            "storyboard_id": storyboard_id,
            "narration_id": narration_plan.get("narration_id"),
            "provider": provider_name,
            "model": model,
            "timeout": timeout,
        }
    )
    request_object = store.store_regeneration_request(
        source_sha256=source_sha256,
        storyboard_id=storyboard_id,
        child_run_id=child_run_id,
        request=request,
    )
    lineage_object = store.store_lineage_edge(
        source_sha256=source_sha256,
        storyboard_id=storyboard_id,
        child_run_id=child_run_id,
        parent_run_id=parent_run_id,
        media_kind=normalised_kind,
        scene_number=scene_number,
    )
    yield RegenerationEvent(
        stage="regeneration_started",
        message=(
            f"Child run {child_run_id} linked to parent {parent_run_id}; "
            f"preparing {normalised_kind} scene {scene_number}."
        ),
        created_at=datetime.now(UTC).isoformat(),
        child_run_id=child_run_id,
        parent_run_id=parent_run_id,
        media_kind=normalised_kind,
        scene_number=scene_number,
        attempt=0,
        payload={
            "request_uri": request_object.uri,
            "lineage_uri": lineage_object.uri,
        },
    )

    if normalised_kind == "image":
        records = [
            value
            for value in storyboard.get("scenes", [])
            if int(value.get("scene_number", 0)) == scene_number
        ]
        if len(records) != 1:
            raise ValueError(f"Storyboard scene {scene_number} was not found exactly once.")
        selected_record = records[0]
        storage = _create_audio_storage(store.settings)
        resolved_model = model or DEFAULT_MODELS.get(provider_name, "")
    else:
        records = [
            value
            for value in narration_plan.get("segments", [])
            if int(value.get("scene_number", 0)) == scene_number
        ]
        if len(records) != 1:
            raise ValueError(f"Narration segment {scene_number} was not found exactly once.")
        selected_record = dict(records[0])
        if str(selected_record.get("review_status", "")).lower() != "approved":
            raise ValueError("Only approved narration segments can be regenerated.")
        selected_record["language"] = narration_plan.get("language", "English (UK)")
        selected_record["voice_style"] = narration_plan.get(
            "voice_style", "clear, calm and educational"
        )
        storage = _create_audio_storage(store.settings)
        resolved_model = model or DEFAULT_AUDIO_MODEL

    last_error: str | None = None
    for attempt in range(1, max_attempts + 1):
        yield RegenerationEvent(
            stage="attempt_started",
            message=f"Attempt {attempt} of {max_attempts} started for scene {scene_number} {normalised_kind}.",
            created_at=datetime.now(UTC).isoformat(),
            child_run_id=child_run_id,
            parent_run_id=parent_run_id,
            media_kind=normalised_kind,
            scene_number=scene_number,
            attempt=attempt,
        )
        try:
            if normalised_kind == "image":
                result = _generate_scene_image(
                    scene=selected_record,
                    provider_name=provider_name,
                    model=model,
                    storage=storage,
                    timeout=timeout,
                    size=image_size,
                    quality=image_quality,
                    aspect_ratio=aspect_ratio,
                    storyboard_id=storyboard_id,
                )
            else:
                voice_id = _default_voice_for_model(resolved_model)
                result = _generate_segment_audio(
                    segment=selected_record,
                    narration_id=str(narration_plan["narration_id"]),
                    provider_model=resolved_model,
                    voice_id=voice_id,
                    storage=storage,
                    timeout=timeout,
                )
            attempt_record = {
                "child_run_id": child_run_id,
                "parent_run_id": parent_run_id,
                "attempt": attempt,
                "status": "completed",
                "media_kind": normalised_kind,
                "scene_number": scene_number,
                "result": result,
                "completed_at": datetime.now(UTC).isoformat(),
            }
            attempt_object = store.store_regeneration_attempt(
                source_sha256=source_sha256,
                storyboard_id=storyboard_id,
                child_run_id=child_run_id,
                attempt=attempt,
                record=attempt_record,
            )
            summary = {
                "child_run_id": child_run_id,
                "parent_run_id": parent_run_id,
                "relationship": "scene_regeneration",
                "status": "completed",
                "media_kind": normalised_kind,
                "scene_number": scene_number,
                "attempts_used": attempt,
                "max_attempts": max_attempts,
                "result": result,
                "saved_at": datetime.now(UTC).isoformat(),
            }
            summary_object = store.store_regeneration_summary(
                source_sha256=source_sha256,
                storyboard_id=storyboard_id,
                child_run_id=child_run_id,
                summary=summary,
            )
            yield RegenerationEvent(
                stage="regeneration_completed",
                message=(
                    f"Scene {scene_number} {normalised_kind} regenerated on attempt {attempt}; "
                    "asset and verified provenance manifest are stored."
                ),
                created_at=datetime.now(UTC).isoformat(),
                child_run_id=child_run_id,
                parent_run_id=parent_run_id,
                media_kind=normalised_kind,
                scene_number=scene_number,
                attempt=attempt,
                payload={
                    "attempt_uri": attempt_object.uri,
                    "summary_uri": summary_object.uri,
                    "result": result,
                },
            )
            return
        except Exception as exc:
            last_error = str(exc)
            retryable = is_retryable_provider_error(exc)
            will_retry = retryable and attempt < max_attempts
            delay = retry_delay_seconds(attempt) if will_retry else 0
            attempt_record = {
                "child_run_id": child_run_id,
                "parent_run_id": parent_run_id,
                "attempt": attempt,
                "status": "failed",
                "media_kind": normalised_kind,
                "scene_number": scene_number,
                "error": last_error,
                "retryable": retryable,
                "will_retry": will_retry,
                "retry_delay_seconds": delay,
                "failed_at": datetime.now(UTC).isoformat(),
            }
            attempt_object = store.store_regeneration_attempt(
                source_sha256=source_sha256,
                storyboard_id=storyboard_id,
                child_run_id=child_run_id,
                attempt=attempt,
                record=attempt_record,
            )
            if will_retry:
                yield RegenerationEvent(
                    stage="retry_scheduled",
                    message=(
                        f"Attempt {attempt} failed with a transient error; retrying scene "
                        f"{scene_number} in {delay} seconds."
                    ),
                    created_at=datetime.now(UTC).isoformat(),
                    child_run_id=child_run_id,
                    parent_run_id=parent_run_id,
                    media_kind=normalised_kind,
                    scene_number=scene_number,
                    attempt=attempt,
                    payload={"attempt_uri": attempt_object.uri, "error": last_error},
                )
                time.sleep(delay)
                continue

            summary = {
                "child_run_id": child_run_id,
                "parent_run_id": parent_run_id,
                "relationship": "scene_regeneration",
                "status": "failed",
                "media_kind": normalised_kind,
                "scene_number": scene_number,
                "attempts_used": attempt,
                "max_attempts": max_attempts,
                "retryable": retryable,
                "error": last_error,
                "saved_at": datetime.now(UTC).isoformat(),
            }
            summary_object = store.store_regeneration_summary(
                source_sha256=source_sha256,
                storyboard_id=storyboard_id,
                child_run_id=child_run_id,
                summary=summary,
            )
            yield RegenerationEvent(
                stage="regeneration_failed",
                message=(
                    f"Scene {scene_number} {normalised_kind} regeneration stopped after "
                    f"attempt {attempt}: {last_error}"
                ),
                created_at=datetime.now(UTC).isoformat(),
                child_run_id=child_run_id,
                parent_run_id=parent_run_id,
                media_kind=normalised_kind,
                scene_number=scene_number,
                attempt=attempt,
                payload={
                    "attempt_uri": attempt_object.uri,
                    "summary_uri": summary_object.uri,
                    "error": last_error,
                },
            )
            return

    raise RuntimeError(last_error or "Regeneration ended without a result.")
