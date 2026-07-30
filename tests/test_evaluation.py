# Tests EvidenceCast consistency checks, manifest requirements and regeneration request lineage.
from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from evidencecast.evaluation import (
    create_regeneration_request,
    evaluate_evidence_consistency,
    retry_delay_seconds,
)


def _storyboard() -> dict[str, object]:
    return {
        "storyboard_id": "SB-test",
        "source_sha256": "a" * 64,
        "scene_count": 3,
        "review_mode": "approved_only",
        "title": "Evidence story",
        "scenes": [
            {
                "scene_number": number,
                "evidence_card_ids": [f"EC-{number}"],
                "key_claim": f"Supported claim {number}.",
                "page_number": number,
            }
            for number in (1, 2, 3)
        ],
    }


def _narration() -> dict[str, object]:
    return {
        "narration_id": "NP-test",
        "storyboard_id": "SB-test",
        "source_sha256": "a" * 64,
        "segment_count": 3,
        "segments": [
            {
                "scene_number": number,
                "evidence_card_ids": [f"EC-{number}"],
                "source_claim": f"Supported claim {number}.",
                "reviewed_text": f"Approved narration {number}.",
                "review_status": "approved",
                "target_duration_seconds": 12,
            }
            for number in (1, 2, 3)
        ],
    }


def _completed_summary(collection_key: str) -> dict[str, object]:
    return {
        "status": "completed",
        collection_key: [
            {
                "scene_number": number,
                "asset_sha256": str(number) * 64,
                "manifest_uri": f"b2://bucket/manifest-{number}.json",
                "manifest_verified": True,
            }
            for number in (1, 2, 3)
        ],
    }


def test_structural_consistency_passes_without_paid_media() -> None:
    report = evaluate_evidence_consistency(
        storyboard=_storyboard(),
        narration_plan=_narration(),
    )

    assert report["status"] == "passed"
    assert report["failed_count"] == 0
    assert report["evaluation_id"].startswith("EVAL-")


def test_evidence_card_mismatch_is_detected() -> None:
    narration = _narration()
    narration["segments"][1]["evidence_card_ids"] = ["EC-unsupported"]

    report = evaluate_evidence_consistency(
        storyboard=_storyboard(),
        narration_plan=narration,
    )

    assert report["status"] == "failed"
    failed_ids = {check["check_id"] for check in report["checks"] if not check["passed"]}
    assert "scene-2-evidence-link" in failed_ids


def test_completed_media_summaries_require_hashes_and_verified_manifests() -> None:
    report = evaluate_evidence_consistency(
        storyboard=_storyboard(),
        narration_plan=_narration(),
        image_summary=_completed_summary("scenes"),
        audio_summary=_completed_summary("segments"),
    )

    assert report["status"] == "passed"

    broken_audio = _completed_summary("segments")
    broken_audio["segments"][2]["manifest_verified"] = False
    broken_report = evaluate_evidence_consistency(
        storyboard=_storyboard(),
        narration_plan=_narration(),
        image_summary=_completed_summary("scenes"),
        audio_summary=broken_audio,
    )
    assert broken_report["status"] == "failed"


def test_regeneration_request_records_parent_child_relationship() -> None:
    request = create_regeneration_request(
        media_kind="image",
        scene_number=2,
        parent_run_id="GEN-parent",
        reason="Caption overlaps the subject.",
        max_attempts=3,
    )

    assert request["parent_run_id"] == "GEN-parent"
    assert request["child_run_id"].startswith("REGEN-IMAGE-S2-")
    assert request["relationship"] == "scene_regeneration"
    assert request["max_attempts"] == 3


def test_retry_delay_is_bounded_exponential() -> None:
    assert retry_delay_seconds(1) == 2
    assert retry_delay_seconds(2) == 4
    assert retry_delay_seconds(10) == 30
