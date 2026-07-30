# Tests EvidenceCast text extraction, evidence-card generation and review-state summaries.
from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from evidencecast.cards import create_evidence_cards, overall_review_status
from evidencecast.extraction import extract_source


def test_text_extraction_and_card_generation_are_traceable() -> None:
    source = (
        "The survey included 506 participants from four wards. "
        "Results showed that 90.3% of respondents accepted the intervention. "
        "Participants reported that clear community information improved trust."
    ).encode("utf-8")

    extraction = extract_source("report.txt", "text/plain", source)
    cards = create_evidence_cards(
        extraction,
        source_sha256="a" * 64,
        maximum_cards=5,
    )

    assert extraction.character_count > 0
    assert extraction.page_count is None
    assert cards
    assert any("90.3%" in card.claim for card in cards)
    assert all(card.status == "pending" for card in cards)
    assert all(card.card_id.startswith("EC-") for card in cards)


def test_review_status_transitions() -> None:
    assert overall_review_status([]) == "pending"
    assert overall_review_status([{"status": "pending"}]) == "pending"
    assert overall_review_status(
        [{"status": "approved"}, {"status": "pending"}]
    ) == "in_progress"
    assert overall_review_status(
        [{"status": "approved"}, {"status": "rejected"}]
    ) == "completed"
