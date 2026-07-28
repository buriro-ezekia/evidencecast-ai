# Tests deterministic storyboard construction and approved-only evidence selection.
from __future__ import annotations

import pytest

from evidencecast.storyboard import StoryboardValidationError, create_storyboard


SOURCE_SHA256 = "a" * 64


def _card(index: int, status: str = "approved") -> dict[str, object]:
    return {
        "card_id": f"EC-{index:02d}",
        "claim": f"Approved evidence claim number {index} contains a traceable research finding.",
        "evidence_type": "research finding",
        "source_excerpt": f"Source excerpt supporting evidence claim number {index}.",
        "page_number": index,
        "status": status,
        "reviewer_note": "Reviewed",
    }


def test_storyboard_uses_exactly_three_approved_cards() -> None:
    cards = [
        _card(1, "approved"),
        _card(2, "rejected"),
        _card(3, "approved"),
        _card(4, "pending"),
        _card(5, "approved"),
        _card(6, "approved"),
    ]

    storyboard = create_storyboard(cards, source_sha256=SOURCE_SHA256)

    assert storyboard.scene_count == 3
    assert storyboard.review_mode == "approved_only"
    assert storyboard.approved_card_ids == ["EC-01", "EC-03", "EC-05"]
    assert [scene.scene_number for scene in storyboard.scenes] == [1, 2, 3]
    assert all(scene.visual_prompt for scene in storyboard.scenes)
    assert all(len(scene.evidence_card_ids) == 1 for scene in storyboard.scenes)


def test_storyboard_id_is_stable_for_same_source_and_cards() -> None:
    cards = [_card(1), _card(2), _card(3)]

    first = create_storyboard(cards, source_sha256=SOURCE_SHA256)
    second = create_storyboard(cards, source_sha256=SOURCE_SHA256)

    assert first.storyboard_id == second.storyboard_id


def test_storyboard_requires_three_approved_cards() -> None:
    cards = [_card(1), _card(2), _card(3, "pending")]

    with pytest.raises(StoryboardValidationError, match="At least 3 approved evidence cards"):
        create_storyboard(cards, source_sha256=SOURCE_SHA256)


def test_storyboard_rejects_invalid_source_hash() -> None:
    with pytest.raises(StoryboardValidationError, match="source_sha256"):
        create_storyboard([_card(1), _card(2), _card(3)], source_sha256="not-a-sha")
