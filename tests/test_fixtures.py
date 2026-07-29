# Tests all three judge fixtures for evidence traceability and downstream compatibility.
from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from evidencecast.fixtures import build_fixture_workflow, list_fixture_reports


def test_fixture_catalogue_contains_three_sample_reports() -> None:
    catalogue = list_fixture_reports()
    assert len(catalogue) == 3
    assert {item["fixture_id"] for item in catalogue} == {
        "biolarviciding-community-acceptance",
        "climate-finance-smallholders",
        "teacher-attendance-supervision",
    }
    assert all(item["provider_required"] is False for item in catalogue)


def test_all_fixture_reports_are_complete_and_traceable() -> None:
    for item in list_fixture_reports():
        workflow = build_fixture_workflow(item["fixture_id"])
        source = workflow["source"]
        review = workflow["review"]
        storyboard = workflow["storyboard"]
        narration = workflow["narration"]

        assert workflow["fixture"]["synthetic"] is True
        assert len(source["source_sha256"]) == 64
        assert review["review_status"] == "completed"
        assert len(review["cards"]) == 3
        assert storyboard["scene_count"] == 3
        assert storyboard["review_mode"] == "approved_only"
        assert narration["segment_count"] == 3
        assert narration["review_status"] == "completed"

        cards_by_id = {card["card_id"]: card for card in review["cards"]}
        segments_by_scene = {segment["scene_number"]: segment for segment in narration["segments"]}

        for card in review["cards"]:
            assert card["status"] == "approved"
            assert card["claim"] in source["text"]
            assert card["source_sha256"] == source["source_sha256"]

        for scene in storyboard["scenes"]:
            assert len(scene["evidence_card_ids"]) == 1
            card = cards_by_id[scene["evidence_card_ids"][0]]
            assert scene["key_claim"] == card["claim"]
            segment = segments_by_scene[scene["scene_number"]]
            assert segment["review_status"] == "approved"
            assert segment["evidence_card_ids"] == scene["evidence_card_ids"]
            assert segment["source_claim"] == scene["key_claim"]
            assert segment["reviewed_text"]
