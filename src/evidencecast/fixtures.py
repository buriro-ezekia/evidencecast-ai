# Provides deterministic sample-report workflows for judge exploration and deployment tests.
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FIXTURE_TIMESTAMP = "2026-07-29T00:00:00+00:00"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIRECTORY = REPOSITORY_ROOT / "fixtures" / "reports"


class FixtureError(RuntimeError):
    """Raised when a fixture report or its traceability contract is invalid."""


@dataclass(frozen=True)
class FixtureDefinition:
    fixture_id: str
    title: str
    domain: str
    filename: str
    description: str
    claims: tuple[str, str, str]


FIXTURE_DEFINITIONS: tuple[FixtureDefinition, ...] = (
    FixtureDefinition(
        fixture_id="biolarviciding-community-acceptance",
        title="Community Acceptance of Biolarviciding",
        domain="Public health",
        filename="biolarviciding-community-acceptance.md",
        description="Malaria-vector-control awareness, effectiveness, willingness and acceptance.",
        claims=(
            "Awareness of biolarviciding was high among surveyed residents, but understanding of how and where larvicides are applied varied across communities.",
            "Residents generally viewed biolarviciding as an effective complement to established malaria-control measures rather than a replacement for bed nets, environmental management or timely treatment.",
            "Willingness to support the intervention was strongest when implementation included clear public information, trusted local leadership and opportunities for residents to ask questions.",
        ),
    ),
    FixtureDefinition(
        fixture_id="climate-finance-smallholders",
        title="Climate Finance and Smallholder Income Resilience",
        domain="Climate adaptation",
        filename="climate-finance-smallholders.md",
        description="Timing, access and complementary support in climate-finance delivery.",
        claims=(
            "Smallholder income resilience improves when climate finance reaches farmers before or soon after climate shocks, rather than arriving only after prolonged livelihood losses.",
            "Accessible credit, index-based insurance and adaptation grants can support recovery, but complex eligibility rules and weak local information may exclude the households most exposed to climate risk.",
            "Financing is more useful when it is combined with climate information, extension support and investments in water management, resilient seed and market access.",
        ),
    ),
    FixtureDefinition(
        fixture_id="teacher-attendance-supervision",
        title="School Supervision and Teacher Attendance",
        domain="Education",
        filename="teacher-attendance-supervision.md",
        description="Monitoring, mentorship, motivation and supportive school leadership.",
        claims=(
            "Regular attendance checks help supervisors identify patterns of absence, but monitoring is more effective when it is followed by constructive discussion rather than punishment alone.",
            "Mentorship supports teacher attendance by connecting accountability with professional guidance, problem solving and clearer expectations for classroom responsibilities.",
            "Teacher motivation and a positive working environment can strengthen commitment, particularly where supervisors recognise good performance and respond to manageable workplace barriers.",
        ),
    ),
)


_DEFINITION_BY_ID = {definition.fixture_id: definition for definition in FIXTURE_DEFINITIONS}


def fixture_mode_enabled() -> bool:
    """Return whether fixture mode is enabled by environment configuration."""

    import os

    return os.getenv("EVIDENCECAST_FIXTURE_MODE", "1").strip().lower() in {"1", "true", "yes", "on"}


def _slug_hash(prefix: str, value: str, length: int = 16) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}-{digest}"


def _read_report(definition: FixtureDefinition) -> str:
    path = REPORT_DIRECTORY / definition.filename
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FixtureError(f"Could not read fixture report '{definition.filename}': {exc}") from exc
    if not text.strip():
        raise FixtureError(f"Fixture report '{definition.filename}' is empty.")
    for claim in definition.claims:
        if claim not in text:
            raise FixtureError(
                f"Fixture claim is not present verbatim in '{definition.filename}': {claim}"
            )
    return text


def _sentence_excerpt(text: str, claim: str) -> str:
    index = text.find(claim)
    if index < 0:
        raise FixtureError("Fixture claim could not be linked to its source text.")
    start = max(0, index - 80)
    end = min(len(text), index + len(claim) + 80)
    return " ".join(text[start:end].split())


def _page_number(text: str, claim: str) -> int:
    # Markdown fixtures are treated as one-page judge samples.
    if claim not in text:
        raise FixtureError("Fixture claim is missing from the source report.")
    return 1


def list_fixture_reports() -> list[dict[str, Any]]:
    """Return the public fixture catalogue without loading complete workflows."""

    catalogue: list[dict[str, Any]] = []
    for definition in FIXTURE_DEFINITIONS:
        text = _read_report(definition)
        catalogue.append(
            {
                "fixture_id": definition.fixture_id,
                "title": definition.title,
                "domain": definition.domain,
                "description": definition.description,
                "filename": definition.filename,
                "character_count": len(text),
                "scene_count": 3,
                "provider_required": False,
            }
        )
    return catalogue


def build_fixture_workflow(fixture_id: str) -> dict[str, Any]:
    """Build a fully approved, traceable three-scene workflow for one sample report."""

    try:
        definition = _DEFINITION_BY_ID[fixture_id]
    except KeyError as exc:
        valid = ", ".join(sorted(_DEFINITION_BY_ID))
        raise FixtureError(f"Unknown fixture '{fixture_id}'. Available fixtures: {valid}.") from exc

    report_text = _read_report(definition)
    source_bytes = report_text.encode("utf-8")
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    storyboard_id = _slug_hash("SB-FIX", f"{fixture_id}:{source_sha256}")
    narration_id = _slug_hash("NP-FIX", f"{storyboard_id}:English (UK)")

    cards: list[dict[str, Any]] = []
    scenes: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []

    for scene_number, claim in enumerate(definition.claims, start=1):
        card_id = _slug_hash("EC-FIX", f"{source_sha256}:{scene_number}:{claim}")
        segment_id = _slug_hash("NS-FIX", f"{narration_id}:{scene_number}:{claim}")
        excerpt = _sentence_excerpt(report_text, claim)
        short_title = re.sub(r"[^A-Za-z0-9 ]+", "", claim).strip().split()
        scene_title = " ".join(short_title[:7])
        narration_text = claim

        cards.append(
            {
                "card_id": card_id,
                "source_sha256": source_sha256,
                "status": "approved",
                "claim": claim,
                "evidence_type": "fixture finding",
                "page_number": _page_number(report_text, claim),
                "source_excerpt": excerpt,
                "reviewer_note": "Pre-approved synthetic fixture for judge exploration.",
                "created_at": FIXTURE_TIMESTAMP,
                "updated_at": FIXTURE_TIMESTAMP,
            }
        )
        scenes.append(
            {
                "scene_number": scene_number,
                "title": scene_title,
                "evidence_card_ids": [card_id],
                "key_claim": claim,
                "narration": narration_text,
                "on_screen_text": claim,
                "visual_prompt": (
                    f"Create a clear editorial evidence card for {definition.domain.lower()}. "
                    f"Represent only this approved claim: {claim} "
                    "Do not invent statistics, quotations, people, organisations or causal claims."
                ),
                "duration_seconds": 12,
                "source_excerpt": excerpt,
                "page_number": 1,
            }
        )
        segments.append(
            {
                "segment_id": segment_id,
                "scene_number": scene_number,
                "evidence_card_ids": [card_id],
                "source_claim": claim,
                "draft_text": narration_text,
                "reviewed_text": narration_text,
                "reviewer_notes": "Synthetic fixture narration approved for deployment testing.",
                "pronunciation_notes": "Use clear UK English pronunciation.",
                "review_status": "approved",
                "target_duration_seconds": 12,
                "language": "English (UK)",
                "voice_style": "clear, calm and educational",
                "created_at": FIXTURE_TIMESTAMP,
                "updated_at": FIXTURE_TIMESTAMP,
            }
        )

    return {
        "fixture": {
            "fixture_id": definition.fixture_id,
            "title": definition.title,
            "domain": definition.domain,
            "description": definition.description,
            "synthetic": True,
            "provider_required": False,
            "fixture_version": "1.0",
        },
        "source": {
            "filename": definition.filename,
            "media_type": "text/markdown",
            "source_sha256": source_sha256,
            "character_count": len(report_text),
            "page_count": 1,
            "text": report_text,
        },
        "review": {
            "source_sha256": source_sha256,
            "review_status": "completed",
            "cards": cards,
        },
        "storyboard": {
            "storyboard_id": storyboard_id,
            "source_sha256": source_sha256,
            "title": definition.title,
            "created_at": FIXTURE_TIMESTAMP,
            "scene_count": 3,
            "review_mode": "approved_only",
            "scenes": scenes,
        },
        "narration": {
            "narration_id": narration_id,
            "storyboard_id": storyboard_id,
            "source_sha256": source_sha256,
            "created_at": FIXTURE_TIMESTAMP,
            "language": "English (UK)",
            "voice_style": "clear, calm and educational",
            "segment_count": 3,
            "review_status": "completed",
            "segments": segments,
        },
    }
