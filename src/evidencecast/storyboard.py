# Builds deterministic, evidence-grounded three-scene storyboards from approved evidence cards.
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


class StoryboardValidationError(ValueError):
    """Raised when reviewed evidence cannot support the requested storyboard."""


@dataclass(frozen=True)
class StoryboardScene:
    """One traceable visual scene derived from exactly one approved evidence card."""

    scene_number: int
    title: str
    evidence_card_ids: list[str]
    key_claim: str
    narration: str
    on_screen_text: str
    visual_prompt: str
    duration_seconds: int
    source_excerpt: str
    page_number: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Storyboard:
    """A versioned three-scene media plan linked to its approved evidence cards."""

    storyboard_id: str
    source_sha256: str
    title: str
    created_at: str
    scene_count: int
    review_mode: str
    approved_card_ids: list[str]
    scenes: list[StoryboardScene]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["scenes"] = [scene.to_dict() for scene in self.scenes]
        return payload


def approved_evidence_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return approved cards with usable IDs, claims and source excerpts."""

    approved: list[dict[str, Any]] = []
    for card in cards:
        status = str(card.get("status", "pending")).strip().lower()
        claim = str(card.get("claim", "")).strip()
        card_id = str(card.get("card_id", "")).strip()
        excerpt = str(card.get("source_excerpt", "")).strip()
        if status == "approved" and claim and card_id and excerpt:
            approved.append(card)
    return approved


def _clean_title(text: str, *, fallback: str) -> str:
    words = re.sub(r"\s+", " ", text).strip(" .,:;-\n\t").split()
    if not words:
        return fallback
    title = " ".join(words[:9])
    return title[:80].rstrip(" .,:;-")


def _on_screen_text(claim: str) -> str:
    words = re.sub(r"\s+", " ", claim).strip().split()
    shortened = " ".join(words[:14])
    if len(words) > 14:
        shortened = shortened.rstrip(".,;:") + "…"
    return shortened[:120]


def _visual_prompt(scene_number: int, title: str, claim: str) -> str:
    return (
        f"Create scene {scene_number} of a coherent three-scene evidence communication story. "
        f"Scene title: {title}. Evidence claim: {claim}. "
        "Use a clean professional editorial-infographic composition, accessible public-interest "
        "visual language, strong subject hierarchy, consistent lighting and visual identity, "
        "16:9 landscape format. Represent only concepts supported by the claim; do not invent "
        "statistics, quotations, people, organisations or causal conclusions. Avoid dense text, "
        "logos, trademarks, watermarks and decorative data labels."
    )


def create_storyboard(
    cards: list[dict[str, Any]],
    *,
    source_sha256: str,
    title: str = "EvidenceCast three-scene evidence story",
    scene_count: int = 3,
) -> Storyboard:
    """Create a deterministic storyboard using approved evidence cards only."""

    if scene_count != 3:
        raise StoryboardValidationError("EvidenceCast Day 3 requires exactly three scenes.")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", source_sha256):
        raise StoryboardValidationError("source_sha256 must be a 64-character hexadecimal SHA-256 value.")

    approved = approved_evidence_cards(cards)
    if len(approved) < scene_count:
        raise StoryboardValidationError(
            f"At least {scene_count} approved evidence cards are required; found {len(approved)}. "
            "Approve additional cards and save the review before creating the storyboard."
        )

    selected = approved[:scene_count]
    approved_card_ids = [str(card["card_id"]) for card in selected]
    storyboard_digest = hashlib.sha256(
        f"{source_sha256}:{':'.join(approved_card_ids)}".encode("utf-8")
    ).hexdigest()[:16]

    scenes: list[StoryboardScene] = []
    for scene_number, card in enumerate(selected, start=1):
        claim = re.sub(r"\s+", " ", str(card["claim"])).strip()
        evidence_type = str(card.get("evidence_type", "research finding")).strip()
        fallback_title = f"Scene {scene_number}: {evidence_type.title()}"
        scene_title = _clean_title(claim, fallback=fallback_title)
        page_value = card.get("page_number")
        page_number = int(page_value) if isinstance(page_value, (int, float)) and page_value == page_value else None

        scenes.append(
            StoryboardScene(
                scene_number=scene_number,
                title=scene_title,
                evidence_card_ids=[str(card["card_id"])],
                key_claim=claim,
                narration=claim,
                on_screen_text=_on_screen_text(claim),
                visual_prompt=_visual_prompt(scene_number, scene_title, claim),
                duration_seconds=12,
                source_excerpt=str(card["source_excerpt"]).strip(),
                page_number=page_number,
            )
        )

    return Storyboard(
        storyboard_id=f"SB-{storyboard_digest}",
        source_sha256=source_sha256.lower(),
        title=title.strip() or "EvidenceCast three-scene evidence story",
        created_at=datetime.now(UTC).isoformat(),
        scene_count=len(scenes),
        review_mode="approved_only",
        approved_card_ids=approved_card_ids,
        scenes=scenes,
    )
