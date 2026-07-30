# Builds and validates human-reviewed narration plans from approved-only storyboard scenes.
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


class NarrationValidationError(ValueError):
    """Raised when a storyboard or narration review cannot support audio generation."""


REVIEW_STATUSES = ("pending", "approved", "rejected")


@dataclass(frozen=True)
class NarrationSegment:
    """One editable narration segment linked to its storyboard evidence."""

    scene_number: int
    segment_id: str
    evidence_card_ids: list[str]
    source_claim: str
    draft_text: str
    reviewed_text: str
    pronunciation_notes: str
    review_status: str
    target_duration_seconds: int
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NarrationPlan:
    """A three-segment narration plan derived from a validated storyboard."""

    narration_id: str
    storyboard_id: str
    source_sha256: str
    created_at: str
    language: str
    voice_style: str
    segment_count: int
    review_status: str
    segments: list[NarrationSegment]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["segments"] = [segment.to_dict() for segment in self.segments]
        return payload


def _normalise_narration_text(text: str) -> str:
    """Remove extraction artefacts without adding unsupported meaning."""

    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"^\d+\s+(?=[A-Za-z])", "", cleaned)
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    return cleaned


def narration_review_status(segments: list[dict[str, Any]]) -> str:
    """Summarise pending, in-progress or completed human narration review."""

    if not segments:
        return "pending"
    statuses = [str(segment.get("review_status", "pending")).strip().lower() for segment in segments]
    if all(status == "pending" for status in statuses):
        return "pending"
    if any(status == "pending" for status in statuses):
        return "in_progress"
    return "completed"


def create_narration_plan(
    storyboard: dict[str, Any],
    *,
    language: str = "English (UK)",
    voice_style: str = "clear, calm and educational",
) -> NarrationPlan:
    """Create deterministic editable narration segments from exactly three storyboard scenes."""

    scenes = list(storyboard.get("scenes", []))
    if storyboard.get("scene_count") != 3 or len(scenes) != 3:
        raise NarrationValidationError("A validated three-scene storyboard is required.")
    if storyboard.get("review_mode") != "approved_only":
        raise NarrationValidationError("Narration can only be created from an approved-only storyboard.")

    storyboard_id = str(storyboard.get("storyboard_id", "")).strip()
    source_sha256 = str(storyboard.get("source_sha256", "")).strip().lower()
    if not storyboard_id:
        raise NarrationValidationError("The storyboard ID is missing.")
    if not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise NarrationValidationError("The storyboard source SHA-256 is invalid.")

    narration_digest = hashlib.sha256(
        f"{storyboard_id}:{language}:{voice_style}".encode("utf-8")
    ).hexdigest()[:16]
    timestamp = datetime.now(UTC).isoformat()
    segments: list[NarrationSegment] = []

    for scene in scenes:
        scene_number = int(scene["scene_number"])
        evidence_card_ids = [str(value) for value in scene.get("evidence_card_ids", [])]
        source_claim = _normalise_narration_text(str(scene.get("key_claim", "")))
        draft_source = str(scene.get("narration") or source_claim)
        draft_text = _normalise_narration_text(draft_source)
        if not evidence_card_ids or not source_claim or not draft_text:
            raise NarrationValidationError(
                f"Scene {scene_number} is missing an evidence link, source claim or narration text."
            )

        segment_digest = hashlib.sha256(
            f"{storyboard_id}:{scene_number}:{':'.join(evidence_card_ids)}".encode("utf-8")
        ).hexdigest()[:16]
        segments.append(
            NarrationSegment(
                scene_number=scene_number,
                segment_id=f"NS-{segment_digest}",
                evidence_card_ids=evidence_card_ids,
                source_claim=source_claim,
                draft_text=draft_text,
                reviewed_text=draft_text,
                pronunciation_notes="",
                review_status="pending",
                target_duration_seconds=int(scene.get("duration_seconds", 12)),
                updated_at=timestamp,
            )
        )

    return NarrationPlan(
        narration_id=f"NP-{narration_digest}",
        storyboard_id=storyboard_id,
        source_sha256=source_sha256,
        created_at=timestamp,
        language=language,
        voice_style=voice_style,
        segment_count=len(segments),
        review_status="pending",
        segments=segments,
    )


def normalise_reviewed_segments(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate edited narration rows before persisting them or generating audio."""

    timestamp = datetime.now(UTC).isoformat()
    normalised: list[dict[str, Any]] = []
    for row in rows:
        scene_number = int(row["scene_number"])
        status = str(row.get("review_status", "pending")).strip().lower()
        if status not in REVIEW_STATUSES:
            status = "pending"
        reviewed_text = _normalise_narration_text(str(row.get("reviewed_text", "")))
        if not reviewed_text:
            raise NarrationValidationError(
                f"Scene {scene_number} must retain non-empty reviewed narration text."
            )
        if len(reviewed_text) > 3000:
            raise NarrationValidationError(
                f"Scene {scene_number} narration exceeds the 3,000-character safety limit."
            )
        normalised_row = dict(row)
        normalised_row["review_status"] = status
        normalised_row["reviewed_text"] = reviewed_text
        normalised_row["pronunciation_notes"] = str(row.get("pronunciation_notes", "")).strip()
        normalised_row["updated_at"] = timestamp
        normalised.append(normalised_row)
    return normalised


def require_all_segments_approved(segments: list[dict[str, Any]]) -> None:
    """Block TTS until all three narration segments have explicit approval."""

    if len(segments) != 3:
        raise NarrationValidationError("Exactly three narration segments are required.")
    unapproved = [
        int(segment["scene_number"])
        for segment in segments
        if str(segment.get("review_status", "pending")).strip().lower() != "approved"
    ]
    if unapproved:
        numbers = ", ".join(str(number) for number in unapproved)
        raise NarrationValidationError(
            f"Approve all narration segments before audio generation. Unapproved scenes: {numbers}."
        )
