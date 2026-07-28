# Tests narration-plan creation, review transitions and approval gating.
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from evidencecast.narration import (
    NarrationValidationError,
    create_narration_plan,
    narration_review_status,
    normalise_reviewed_segments,
    require_all_segments_approved,
)


def _storyboard() -> dict[str, object]:
    return {
        "storyboard_id": "SB-test",
        "source_sha256": "a" * 64,
        "scene_count": 3,
        "review_mode": "approved_only",
        "scenes": [
            {
                "scene_number": number,
                "evidence_card_ids": [f"EC-{number:02d}"],
                "key_claim": f"Evidence claim {number}.",
                "narration": f"Narration sentence {number}.",
                "duration_seconds": 12,
            }
            for number in range(1, 4)
        ],
    }


def test_narration_plan_is_deterministic_and_traceable() -> None:
    first = create_narration_plan(_storyboard())
    second = create_narration_plan(_storyboard())

    assert first.narration_id == second.narration_id
    assert first.segment_count == 3
    assert first.review_status == "pending"
    assert [segment.scene_number for segment in first.segments] == [1, 2, 3]
    assert all(segment.evidence_card_ids for segment in first.segments)
    assert all(segment.reviewed_text for segment in first.segments)


def test_review_status_transitions() -> None:
    assert narration_review_status([]) == "pending"
    assert narration_review_status([{"review_status": "pending"}]) == "pending"
    assert narration_review_status(
        [{"review_status": "approved"}, {"review_status": "pending"}]
    ) == "in_progress"
    assert narration_review_status(
        [{"review_status": "approved"}, {"review_status": "rejected"}]
    ) == "completed"


def test_audio_requires_all_segments_approved() -> None:
    plan = create_narration_plan(_storyboard()).to_dict()
    segments = plan["segments"]
    segments[0]["review_status"] = "approved"
    segments[1]["review_status"] = "approved"

    with pytest.raises(NarrationValidationError, match="Unapproved scenes: 3"):
        require_all_segments_approved(segments)

    segments[2]["review_status"] = "approved"
    require_all_segments_approved(segments)


def test_review_normalisation_rejects_blank_spoken_text() -> None:
    plan = create_narration_plan(_storyboard()).to_dict()
    segments = plan["segments"]
    segments[1]["reviewed_text"] = "   "

    with pytest.raises(NarrationValidationError, match="Scene 2"):
        normalise_reviewed_segments(segments)


def test_narration_rejects_non_approved_storyboard() -> None:
    storyboard = _storyboard()
    storyboard["review_mode"] = "mixed"

    with pytest.raises(NarrationValidationError, match="approved-only"):
        create_narration_plan(storyboard)
