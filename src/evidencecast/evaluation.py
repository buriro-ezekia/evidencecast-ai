# Evaluates EvidenceCast scene consistency, provenance completeness and retry lineage.
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


class EvaluationError(ValueError):
    """Raised when an evaluation or regeneration request is structurally invalid."""


@dataclass(frozen=True)
class ConsistencyCheck:
    """One machine-readable evaluation result."""

    check_id: str
    label: str
    passed: bool
    detail: str
    scene_number: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_sha256(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "").strip().lower()))


def _scene_map(values: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    mapped: dict[int, dict[str, Any]] = {}
    for value in values:
        number = int(value.get("scene_number", 0))
        if number in mapped:
            raise EvaluationError(f"Scene {number} appears more than once.")
        mapped[number] = value
    return mapped


def evaluate_evidence_consistency(
    *,
    storyboard: dict[str, Any],
    narration_plan: dict[str, Any],
    image_summary: dict[str, Any] | None = None,
    audio_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check that storyboard, narration and optional generated assets remain evidence-linked."""

    checks: list[ConsistencyCheck] = []

    def add(
        check_id: str,
        label: str,
        passed: bool,
        detail: str,
        scene_number: int | None = None,
    ) -> None:
        checks.append(
            ConsistencyCheck(
                check_id=check_id,
                label=label,
                passed=bool(passed),
                detail=detail,
                scene_number=scene_number,
            )
        )

    storyboard_scenes = list(storyboard.get("scenes", []))
    narration_segments = list(narration_plan.get("segments", []))
    add(
        "storyboard-three-scenes",
        "Storyboard contains exactly three scenes",
        storyboard.get("scene_count") == 3 and len(storyboard_scenes) == 3,
        f"Declared {storyboard.get('scene_count')}; found {len(storyboard_scenes)} scene records.",
    )
    add(
        "storyboard-approved-only",
        "Storyboard uses approved evidence only",
        storyboard.get("review_mode") == "approved_only",
        f"review_mode={storyboard.get('review_mode')!r}",
    )
    add(
        "source-sha-match",
        "Storyboard and narration reference the same source",
        storyboard.get("source_sha256") == narration_plan.get("source_sha256")
        and _is_sha256(storyboard.get("source_sha256")),
        "The source SHA-256 values must match and be valid.",
    )
    add(
        "storyboard-id-match",
        "Narration references the active storyboard",
        storyboard.get("storyboard_id") == narration_plan.get("storyboard_id"),
        "The narration storyboard_id must equal the active storyboard_id.",
    )
    add(
        "narration-three-segments",
        "Narration contains exactly three segments",
        len(narration_segments) == 3 and narration_plan.get("segment_count", 3) == 3,
        f"Found {len(narration_segments)} narration segments.",
    )

    storyboard_map = _scene_map(storyboard_scenes)
    narration_map = _scene_map(narration_segments)
    for scene_number in (1, 2, 3):
        scene = storyboard_map.get(scene_number)
        segment = narration_map.get(scene_number)
        add(
            f"scene-{scene_number}-present",
            f"Scene {scene_number} exists in storyboard and narration",
            scene is not None and segment is not None,
            "Both records are required.",
            scene_number,
        )
        if scene is None or segment is None:
            continue
        scene_cards = [str(value) for value in scene.get("evidence_card_ids", [])]
        segment_cards = [str(value) for value in segment.get("evidence_card_ids", [])]
        add(
            f"scene-{scene_number}-evidence-link",
            f"Scene {scene_number} retains the same evidence-card links",
            bool(scene_cards) and scene_cards == segment_cards,
            f"Storyboard cards={scene_cards}; narration cards={segment_cards}.",
            scene_number,
        )
        add(
            f"scene-{scene_number}-claim-present",
            f"Scene {scene_number} retains a source claim",
            bool(str(scene.get("key_claim", "")).strip())
            and bool(str(segment.get("source_claim", scene.get("key_claim", ""))).strip()),
            "The locked source claim must not be blank.",
            scene_number,
        )
        add(
            f"scene-{scene_number}-narration-approved",
            f"Scene {scene_number} narration is explicitly approved",
            str(segment.get("review_status", "")).lower() == "approved"
            and bool(str(segment.get("reviewed_text", "")).strip()),
            "Approved non-empty spoken text is required.",
            scene_number,
        )

    def evaluate_media_summary(
        summary: dict[str, Any] | None,
        *,
        media_kind: str,
        collection_keys: tuple[str, ...],
    ) -> None:
        if summary is None:
            add(
                f"{media_kind}-summary-optional",
                f"{media_kind.title()} summary supplied for final verification",
                True,
                "No summary supplied; structural evidence checks still completed.",
            )
            return
        add(
            f"{media_kind}-summary-completed",
            f"{media_kind.title()} generation summary reports completed",
            summary.get("status") == "completed",
            f"status={summary.get('status')!r}",
        )
        records: list[dict[str, Any]] = []
        for key in collection_keys:
            candidate = summary.get(key)
            if isinstance(candidate, list):
                records = candidate
                break
        record_map = _scene_map(records) if records else {}
        for scene_number in (1, 2, 3):
            record = record_map.get(scene_number)
            add(
                f"{media_kind}-scene-{scene_number}-record",
                f"{media_kind.title()} scene {scene_number} has an asset record",
                record is not None,
                "A completed record is required for final delivery.",
                scene_number,
            )
            if record is None:
                continue
            add(
                f"{media_kind}-scene-{scene_number}-sha",
                f"{media_kind.title()} scene {scene_number} has a valid SHA-256",
                _is_sha256(record.get("asset_sha256")),
                f"asset_sha256={record.get('asset_sha256')!r}",
                scene_number,
            )
            add(
                f"{media_kind}-scene-{scene_number}-manifest",
                f"{media_kind.title()} scene {scene_number} has a verified manifest",
                bool(record.get("manifest_uri")) and record.get("manifest_verified") is True,
                "manifest_uri must exist and manifest_verified must be true.",
                scene_number,
            )

    evaluate_media_summary(
        image_summary,
        media_kind="image",
        collection_keys=("scenes", "completed_scenes"),
    )
    evaluate_media_summary(
        audio_summary,
        media_kind="audio",
        collection_keys=("segments", "completed_segments"),
    )

    failed = [check for check in checks if not check.passed]
    report_seed = "|".join(
        [
            str(storyboard.get("storyboard_id", "")),
            str(narration_plan.get("narration_id", "")),
            *[f"{check.check_id}:{int(check.passed)}" for check in checks],
        ]
    )
    report_id = "EVAL-" + hashlib.sha256(report_seed.encode("utf-8")).hexdigest()[:16]
    return {
        "evaluation_id": report_id,
        "storyboard_id": storyboard.get("storyboard_id"),
        "narration_id": narration_plan.get("narration_id"),
        "source_sha256": storyboard.get("source_sha256"),
        "status": "passed" if not failed else "failed",
        "check_count": len(checks),
        "passed_count": len(checks) - len(failed),
        "failed_count": len(failed),
        "evaluated_at": datetime.now(UTC).isoformat(),
        "checks": [check.to_dict() for check in checks],
    }


def create_regeneration_request(
    *,
    media_kind: str,
    scene_number: int,
    parent_run_id: str,
    reason: str,
    attempt: int = 1,
    max_attempts: int = 2,
) -> dict[str, Any]:
    """Create a traceable child request for one image scene or narration segment."""

    normalised_kind = media_kind.strip().lower()
    if normalised_kind not in {"image", "audio"}:
        raise EvaluationError("media_kind must be 'image' or 'audio'.")
    if scene_number not in {1, 2, 3}:
        raise EvaluationError("scene_number must be 1, 2 or 3.")
    if not parent_run_id.strip():
        raise EvaluationError("A parent run ID is required for regeneration lineage.")
    if not reason.strip():
        raise EvaluationError("A regeneration reason is required.")
    if attempt < 1 or max_attempts < 1 or attempt > max_attempts:
        raise EvaluationError("Retry attempt values are invalid.")

    child_run_id = (
        f"REGEN-{normalised_kind.upper()}-S{scene_number}-"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    )
    return {
        "child_run_id": child_run_id,
        "parent_run_id": parent_run_id.strip(),
        "relationship": "scene_regeneration",
        "media_kind": normalised_kind,
        "scene_number": scene_number,
        "reason": reason.strip(),
        "attempt": attempt,
        "max_attempts": max_attempts,
        "created_at": datetime.now(UTC).isoformat(),
    }


def retry_delay_seconds(attempt: int, *, base_seconds: int = 2, maximum_seconds: int = 30) -> int:
    """Return bounded exponential retry delay for a one-scene regeneration."""

    if attempt < 1:
        raise EvaluationError("attempt must be at least 1.")
    return min(maximum_seconds, base_seconds * (2 ** (attempt - 1)))
