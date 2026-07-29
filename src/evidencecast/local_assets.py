# Generates clearly labelled local validation images and narration audio from approved evidence only.
from __future__ import annotations

import hashlib
import shutil
import subprocess
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


class LocalAssetError(RuntimeError):
    """Raised when local validation assets cannot be produced safely."""


@dataclass(frozen=True)
class LocalValidationAsset:
    """One locally generated validation asset and its integrity metadata."""

    scene_number: int
    kind: str
    path: str
    sha256: str
    size_bytes: int
    media_type: str
    generator: str
    evidence_card_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _wrapped_lines(text: str, *, width: int) -> list[str]:
    return textwrap.wrap(
        " ".join(str(text).split()),
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    *,
    text: str,
    xy: tuple[int, int],
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    width_chars: int,
    line_gap: int,
    max_lines: int,
) -> int:
    x, y = xy
    for line in _wrapped_lines(text, width=width_chars)[:max_lines]:
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((x, y), line, font=font)
        y += (bbox[3] - bbox[1]) + line_gap
    return y


def _scene_palette(scene_number: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    palettes = {
        1: ((20, 44, 76), (57, 189, 248)),
        2: ((38, 55, 35), (132, 204, 22)),
        3: ((72, 35, 63), (244, 114, 182)),
    }
    return palettes.get(scene_number, ((35, 45, 65), (96, 165, 250)))


def _draw_scene_symbol(draw: ImageDraw.ImageDraw, scene_number: int, accent: tuple[int, int, int]) -> None:
    """Draw a deterministic simple visual without introducing external facts."""

    if scene_number == 1:
        draw.ellipse((875, 175, 1055, 355), outline=accent, width=14)
        draw.line((1015, 315, 1125, 425), fill=accent, width=18)
        symbol_font = _load_font(86, bold=True)
        draw.text((825, 430), "*   ?", font=symbol_font, fill=accent)
    elif scene_number == 2:
        table_x, table_y = 815, 165
        cell_w, cell_h = 135, 72
        for row in range(4):
            for column in range(2):
                x0 = table_x + column * cell_w
                y0 = table_y + row * cell_h
                draw.rounded_rectangle(
                    (x0, y0, x0 + cell_w - 8, y0 + cell_h - 8),
                    radius=10,
                    outline=accent,
                    width=4,
                )
        small = _load_font(28, bold=True)
        draw.text((835, 185), "ID", font=small, fill=accent)
        draw.text((972, 185), "Price", font=small, fill=accent)
        draw.text((828, 260), "P003", font=small, fill=(245, 245, 245))
        draw.text((985, 260), "£25", font=small, fill=(245, 245, 245))
        draw.line((745, 330, 805, 330), fill=accent, width=12)
        draw.polygon([(805, 330), (780, 310), (780, 350)], fill=accent)
    else:
        draw.rounded_rectangle((815, 185, 1120, 300), radius=24, outline=accent, width=8)
        draw.rounded_rectangle((815, 385, 1120, 500), radius=24, outline=accent, width=8)
        arrow = [(950, 315), (985, 315), (985, 350), (1015, 350), (968, 392), (920, 350), (950, 350)]
        draw.polygon(arrow, fill=accent)
        small = _load_font(31, bold=True)
        draw.text((850, 220), "Lookup", font=small, fill=(245, 245, 245))
        draw.text((845, 420), "Not found", font=small, fill=(245, 245, 245))


def create_local_scene_image(
    *,
    scene: dict[str, Any],
    output_path: Path,
    width: int = 1280,
    height: int = 720,
) -> LocalValidationAsset:
    """Create one evidence-grounded, clearly labelled local scene image."""

    scene_number = int(scene["scene_number"])
    evidence_card_ids = [str(value) for value in scene.get("evidence_card_ids", [])]
    title = " ".join(str(scene.get("title", f"Scene {scene_number}")).split())
    claim = " ".join(str(scene.get("key_claim", "")).split())
    if not evidence_card_ids or not claim:
        raise LocalAssetError(f"Scene {scene_number} is missing evidence links or its key claim.")

    background, accent = _scene_palette(scene_number)
    canvas = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(canvas)

    draw.rectangle((0, 0, width, 18), fill=accent)
    draw.rounded_rectangle((54, 48, 730, 650), radius=28, fill=(248, 250, 252))
    draw.rounded_rectangle((765, 48, 1226, 650), radius=28, fill=(12, 22, 37))

    eyebrow_font = _load_font(22, bold=True)
    scene_font = _load_font(34, bold=True)
    title_font = _load_font(46, bold=True)
    claim_font = _load_font(29)
    evidence_font = _load_font(20)
    label_font = _load_font(19, bold=True)

    draw.text((90, 86), "EVIDENCECAST AI", font=eyebrow_font, fill=accent)
    draw.text((90, 132), f"SCENE {scene_number}", font=scene_font, fill=(30, 41, 59))
    title_y = _draw_text_block(
        draw,
        text=title,
        xy=(90, 192),
        font=title_font,
        fill=(15, 23, 42),
        width_chars=27,
        line_gap=8,
        max_lines=3,
    )
    claim_y = max(345, title_y + 18)
    _draw_text_block(
        draw,
        text=claim,
        xy=(90, claim_y),
        font=claim_font,
        fill=(51, 65, 85),
        width_chars=41,
        line_gap=7,
        max_lines=5,
    )

    evidence_text = "Evidence: " + ", ".join(evidence_card_ids)
    page_number = scene.get("page_number")
    if page_number not in (None, ""):
        evidence_text += f" • Source page {page_number}"
    draw.text((90, 600), evidence_text, font=evidence_font, fill=(71, 85, 105))

    _draw_scene_symbol(draw, scene_number, accent)
    draw.rounded_rectangle((805, 565, 1185, 616), radius=18, fill=accent)
    draw.text((842, 580), "LOCAL VALIDATION ASSET", font=label_font, fill=(4, 20, 34))
    draw.text(
        (788, 664),
        "Built from approved evidence; not provider-generated",
        font=evidence_font,
        fill=(226, 232, 240),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)
    return LocalValidationAsset(
        scene_number=scene_number,
        kind="image",
        path=str(output_path),
        sha256=_sha256_file(output_path),
        size_bytes=output_path.stat().st_size,
        media_type="image/png",
        generator="evidencecast-local-pillow",
        evidence_card_ids=evidence_card_ids,
    )


def require_espeak() -> str:
    """Return an installed eSpeak executable or raise an actionable error."""

    executable = shutil.which("espeak-ng") or shutil.which("espeak")
    if not executable:
        raise LocalAssetError(
            "Local narration requires eSpeak NG. Install it with: sudo apt-get update && "
            "sudo apt-get install -y espeak-ng"
        )
    return executable


def synthesise_local_narration(
    *,
    segment: dict[str, Any],
    output_path: Path,
    voice: str = "en-gb",
    speed: int = 155,
    pitch: int = 48,
    timeout: int = 120,
) -> LocalValidationAsset:
    """Create one clearly attributed local WAV narration from approved reviewed text."""

    scene_number = int(segment["scene_number"])
    evidence_card_ids = [str(value) for value in segment.get("evidence_card_ids", [])]
    reviewed_text = " ".join(str(segment.get("reviewed_text", "")).split())
    if str(segment.get("review_status", "")).strip().lower() != "approved":
        raise LocalAssetError(f"Scene {scene_number} narration is not approved.")
    if not evidence_card_ids or not reviewed_text:
        raise LocalAssetError(f"Scene {scene_number} narration is missing evidence links or spoken text.")

    executable = require_espeak()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        executable,
        "-v",
        voice,
        "-s",
        str(int(speed)),
        "-p",
        str(int(pitch)),
        "-w",
        str(output_path),
        reviewed_text,
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise LocalAssetError(f"Local narration timed out for scene {scene_number}.") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Unknown eSpeak failure").strip()
        raise LocalAssetError(f"Local narration failed for scene {scene_number}: {detail[-2000:]}")
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise LocalAssetError(f"Local narration produced no WAV file for scene {scene_number}.")

    return LocalValidationAsset(
        scene_number=scene_number,
        kind="audio",
        path=str(output_path),
        sha256=_sha256_file(output_path),
        size_bytes=output_path.stat().st_size,
        media_type="audio/wav",
        generator=f"local-{Path(executable).name}",
        evidence_card_ids=evidence_card_ids,
    )


def generate_local_validation_assets(
    *,
    storyboard: dict[str, Any],
    narration_plan: dict[str, Any],
    output_directory: Path,
) -> dict[str, Any]:
    """Generate three labelled scene images and three approved local narration WAV files."""

    scenes = sorted(list(storyboard.get("scenes", [])), key=lambda value: int(value["scene_number"]))
    segments = sorted(
        list(narration_plan.get("segments", [])),
        key=lambda value: int(value["scene_number"]),
    )
    if len(scenes) != 3 or len(segments) != 3:
        raise LocalAssetError("Exactly three storyboard scenes and three narration segments are required.")
    if str(storyboard.get("storyboard_id")) != str(narration_plan.get("storyboard_id")):
        raise LocalAssetError("The narration plan does not belong to the active storyboard.")
    if str(storyboard.get("source_sha256")) != str(narration_plan.get("source_sha256")):
        raise LocalAssetError("The storyboard and narration source SHA-256 values do not match.")

    output_directory.mkdir(parents=True, exist_ok=True)
    images: list[LocalValidationAsset] = []
    audio: list[LocalValidationAsset] = []
    for scene, segment in zip(scenes, segments):
        scene_number = int(scene["scene_number"])
        if int(segment["scene_number"]) != scene_number:
            raise LocalAssetError("Storyboard and narration scene ordering does not match.")
        if set(map(str, scene.get("evidence_card_ids", []))) != set(
            map(str, segment.get("evidence_card_ids", []))
        ):
            raise LocalAssetError(f"Scene {scene_number} evidence-card links do not match.")
        images.append(
            create_local_scene_image(
                scene=scene,
                output_path=output_directory / f"scene-{scene_number:02d}-local.png",
            )
        )
        audio.append(
            synthesise_local_narration(
                segment=segment,
                output_path=output_directory / f"scene-{scene_number:02d}-local.wav",
            )
        )

    return {
        "status": "completed",
        "origin": "local_validation_fallback",
        "disclosure": (
            "Images were rendered locally with Pillow and narration was synthesised locally with "
            "eSpeak from approved text. These are not provider-generated Genblaze assets."
        ),
        "images": [asset.to_dict() for asset in images],
        "audio": [asset.to_dict() for asset in audio],
    }
