# Creates reviewable evidence-card candidates from extracted research text.
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Iterable

from .extraction import ExtractionResult, ExtractedSegment


@dataclass(frozen=True)
class EvidenceCard:
    """A candidate evidence claim with traceable source context and review state."""

    card_id: str
    claim: str
    evidence_type: str
    source_excerpt: str
    page_number: int | None
    status: str
    reviewer_note: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")
_QUANTITATIVE_PATTERN = re.compile(
    r"(?:\b\d+(?:[.,]\d+)?\b|\b\d+(?:[.,]\d+)?\s*%|\bmean\b|\bmedian\b|\bconfidence interval\b)",
    re.IGNORECASE,
)
_FINDING_TERMS = {
    "found",
    "finding",
    "results",
    "reported",
    "observed",
    "showed",
    "demonstrated",
    "indicated",
    "revealed",
    "associated",
    "correlated",
    "increased",
    "decreased",
    "reduced",
    "improved",
    "significant",
    "prevalence",
    "proportion",
    "risk",
    "effect",
    "impact",
}
_LOW_VALUE_TERMS = {
    "table of contents",
    "copyright",
    "all rights reserved",
    "references",
    "bibliography",
    "acknowledgement",
}


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    return [sentence.strip() for sentence in _SENTENCE_BOUNDARY.split(text) if sentence.strip()]


def _score_sentence(sentence: str) -> int:
    lower = sentence.lower()
    if len(sentence) < 45 or len(sentence) > 700:
        return -10
    if any(term in lower for term in _LOW_VALUE_TERMS):
        return -10

    score = 0
    if _QUANTITATIVE_PATTERN.search(sentence):
        score += 4
    score += sum(1 for term in _FINDING_TERMS if term in lower)
    if any(marker in sentence for marker in ("=", "±", "CI", "OR", "RR", "p<", "p =", "p=")):
        score += 2
    if 80 <= len(sentence) <= 320:
        score += 1
    if sentence.endswith((".", "!", "?")):
        score += 1
    return score


def _classify_sentence(sentence: str) -> str:
    lower = sentence.lower()
    if _QUANTITATIVE_PATTERN.search(sentence):
        return "quantitative finding"
    if any(term in lower for term in ("associated", "correlated", "relationship", "predictor")):
        return "association"
    if any(term in lower for term in ("caused", "led to", "resulted in", "because of", "due to")):
        return "causal claim"
    if any(term in lower for term in ("recommend", "should", "need to", "must")):
        return "recommendation"
    if any(term in lower for term in ("participants reported", "respondents reported", "described", "perceived")):
        return "qualitative finding"
    return "research finding"


def _candidate_sentences(segments: Iterable[ExtractedSegment]) -> list[tuple[int, str, int | None]]:
    candidates: list[tuple[int, str, int | None]] = []
    sequence = 0
    for segment in segments:
        for sentence in _split_sentences(segment.text):
            score = _score_sentence(sentence)
            if score >= 2:
                candidates.append((score, sentence, segment.page_number))
            sequence += 1
    return candidates


def create_evidence_cards(
    extraction: ExtractionResult,
    *,
    source_sha256: str,
    maximum_cards: int = 10,
) -> list[EvidenceCard]:
    """Create deterministic, review-first evidence cards from high-signal sentences."""

    ranked = sorted(
        _candidate_sentences(extraction.segments),
        key=lambda item: (-item[0], item[2] if item[2] is not None else 0, item[1]),
    )

    selected: list[tuple[int, str, int | None]] = []
    seen_normalised: set[str] = set()
    for score, sentence, page_number in ranked:
        normalised = re.sub(r"\W+", " ", sentence.lower()).strip()
        if not normalised or normalised in seen_normalised:
            continue
        seen_normalised.add(normalised)
        selected.append((score, sentence, page_number))
        if len(selected) >= maximum_cards:
            break

    if not selected:
        fallback_sentences: list[tuple[int, str, int | None]] = []
        for segment in extraction.segments:
            for sentence in _split_sentences(segment.text):
                if 45 <= len(sentence) <= 700:
                    fallback_sentences.append((0, sentence, segment.page_number))
        selected = fallback_sentences[:maximum_cards]

    timestamp = datetime.now(UTC).isoformat()
    cards: list[EvidenceCard] = []
    for index, (_, sentence, page_number) in enumerate(selected, start=1):
        digest = hashlib.sha256(
            f"{source_sha256}:{index}:{sentence}".encode("utf-8")
        ).hexdigest()[:16]
        cards.append(
            EvidenceCard(
                card_id=f"EC-{digest}",
                claim=sentence[:500],
                evidence_type=_classify_sentence(sentence),
                source_excerpt=sentence[:700],
                page_number=page_number,
                status="pending",
                reviewer_note="",
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
    return cards


def overall_review_status(cards: list[dict[str, object]]) -> str:
    """Summarise the review state for persistence and display."""

    statuses = {str(card.get("status", "pending")) for card in cards}
    if not cards or statuses == {"pending"}:
        return "pending"
    if "pending" in statuses:
        return "in_progress"
    return "completed"
