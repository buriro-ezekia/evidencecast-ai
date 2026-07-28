# Produces subtitles, a captioned MP4, a thumbnail and a three-scene infographic export.
from __future__ import annotations

import hashlib
import shutil
import subprocess
import textwrap
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont, ImageOps


class FinalMediaError(RuntimeError):
    """Raised when subtitles or final-media assembly cannot be completed safely."""


@dataclass(frozen=True)
class FinalMediaAsset:
    """One locally assembled output and its integrity metadata."""

    path: str
    sha256: str
    size_bytes: int
    media_type: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _vtt_timestamp(seconds: float) -> str:
    return _srt_timestamp(seconds).replace(",", ".")


def _subtitle_text(text: str, *, width: int = 58) -> str:
    cleaned = " ".join(str(text).split())
    if not cleaned:
        raise FinalMediaError("Subtitle text cannot be blank.")
    return "\n".join(textwrap.wrap(cleaned, width=width, break_long_words=False))


def build_subtitles(
    segments: list[dict[str, Any]],
    *,
    minimum_duration_seconds: float = 3.0,
) -> tuple[str, str, list[dict[str, Any]]]:
    """Create SRT and WebVTT subtitles using approved narration scene durations."""

    if len(segments) != 3:
        raise FinalMediaError("Exactly three narration segments are required for subtitles.")
    ordered = sorted(segments, key=lambda value: int(value["scene_number"]))
    cursor = 0.0
    cues: list[dict[str, Any]] = []
    srt_blocks: list[str] = []
    vtt_blocks: list[str] = ["WEBVTT", ""]

    for index, segment in enumerate(ordered, start=1):
        if str(segment.get("review_status", "")).lower() != "approved":
            raise FinalMediaError(f"Scene {index} narration is not approved.")
        duration = max(
            minimum_duration_seconds,
            float(segment.get("actual_duration_seconds") or segment.get("target_duration_seconds") or 12),
        )
        start = cursor
        end = cursor + duration
        text = _subtitle_text(str(segment.get("reviewed_text", "")))
        cue = {
            "scene_number": int(segment["scene_number"]),
            "start_seconds": start,
            "end_seconds": end,
            "text": text,
        }
        cues.append(cue)
        srt_blocks.extend(
            [
                str(index),
                f"{_srt_timestamp(start)} --> {_srt_timestamp(end)}",
                text,
                "",
            ]
        )
        vtt_blocks.extend(
            [
                f"{_vtt_timestamp(start)} --> {_vtt_timestamp(end)}",
                text,
                "",
            ]
        )
        cursor = end

    return "\n".join(srt_blocks).rstrip() + "\n", "\n".join(vtt_blocks).rstrip() + "\n", cues


def write_subtitles(
    segments: list[dict[str, Any]],
    *,
    output_directory: Path,
) -> dict[str, Any]:
    """Write SRT, WebVTT and cue JSON-ready metadata to a local output directory."""

    output_directory.mkdir(parents=True, exist_ok=True)
    srt_text, vtt_text, cues = build_subtitles(segments)
    srt_path = output_directory / "captions.srt"
    vtt_path = output_directory / "captions.vtt"
    srt_path.write_text(srt_text, encoding="utf-8")
    vtt_path.write_text(vtt_text, encoding="utf-8")
    return {
        "srt_path": srt_path,
        "vtt_path": vtt_path,
        "cues": cues,
        "duration_seconds": cues[-1]["end_seconds"],
    }


def _run(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise FinalMediaError(f"FFmpeg timed out after {timeout} seconds.") from exc
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "Unknown FFmpeg failure").strip()
        raise FinalMediaError(f"FFmpeg failed: {stderr[-4000:]}")
    return result


def require_ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise FinalMediaError(
            "FFmpeg is not installed or is not available on PATH. Install ffmpeg in the Codespace."
        )
    return executable


def _escape_subtitle_filter_path(path: Path) -> str:
    value = str(path.resolve())
    value = value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return value


def compose_captioned_mp4(
    *,
    scene_images: list[Path],
    scene_audio: list[Path],
    subtitle_path: Path,
    output_path: Path,
    workspace: Path,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
    timeout: int = 600,
) -> FinalMediaAsset:
    """Compose three still-image/audio scenes and burn evidence-grounded subtitles."""

    if len(scene_images) != 3 or len(scene_audio) != 3:
        raise FinalMediaError("Exactly three scene images and three narration audio clips are required.")
    for path in [*scene_images, *scene_audio, subtitle_path]:
        if not path.exists() or path.stat().st_size == 0:
            raise FinalMediaError(f"Required assembly input is missing or empty: {path}")

    ffmpeg = require_ffmpeg()
    workspace.mkdir(parents=True, exist_ok=True)
    segment_paths: list[Path] = []
    video_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
    )

    for index, (image_path, audio_path) in enumerate(zip(scene_images, scene_audio), start=1):
        segment_path = workspace / f"scene-{index:02d}.mp4"
        _run(
            [
                ffmpeg,
                "-y",
                "-loop",
                "1",
                "-i",
                str(image_path),
                "-i",
                str(audio_path),
                "-vf",
                video_filter,
                "-c:v",
                "libx264",
                "-tune",
                "stillimage",
                "-r",
                str(fps),
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                "-movflags",
                "+faststart",
                str(segment_path),
            ],
            timeout=timeout,
        )
        segment_paths.append(segment_path)

    concat_file = workspace / "segments.txt"
    concat_file.write_text(
        "\n".join(f"file '{path.resolve().as_posix()}'" for path in segment_paths) + "\n",
        encoding="utf-8",
    )
    joined_path = workspace / "joined.mp4"
    _run(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(joined_path),
        ],
        timeout=timeout,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    subtitle_filter = (
        f"subtitles=filename='{_escape_subtitle_filter_path(subtitle_path)}':"
        "force_style='FontSize=24,Outline=2,Shadow=1,MarginV=34,Alignment=2'"
    )
    _run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(joined_path),
            "-vf",
            subtitle_filter,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        timeout=timeout,
    )
    return FinalMediaAsset(
        path=str(output_path),
        sha256=sha256_file(output_path),
        size_bytes=output_path.stat().st_size,
        media_type="video/mp4",
    )


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


def _fit_text(draw: ImageDraw.ImageDraw, text: str, width_pixels: int, font: ImageFont.ImageFont) -> list[str]:
    words = " ".join(text.split()).split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        proposed = f"{current} {word}".strip()
        box = draw.textbbox((0, 0), proposed, font=font)
        if box[2] - box[0] <= width_pixels or not current:
            current = proposed
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def create_thumbnail(
    *,
    source_image: Path,
    title: str,
    subtitle: str,
    output_path: Path,
) -> FinalMediaAsset:
    """Create a 16:9 delivery thumbnail from the first approved scene image."""

    with Image.open(source_image) as source:
        canvas = ImageOps.fit(source.convert("RGB"), (1280, 720), method=Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle((0, 390, 1280, 720), fill=(0, 0, 0, 178))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(canvas)
    title_font = _load_font(54, bold=True)
    subtitle_font = _load_font(28)
    y = 430
    for line in _fit_text(draw, title, 1120, title_font)[:3]:
        draw.text((80, y), line, font=title_font, fill="white")
        y += 66
    for line in _fit_text(draw, subtitle, 1120, subtitle_font)[:2]:
        draw.text((82, y + 8), line, font=subtitle_font, fill=(235, 235, 235, 255))
        y += 38
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, format="JPEG", quality=92, optimize=True)
    return FinalMediaAsset(
        path=str(output_path),
        sha256=sha256_file(output_path),
        size_bytes=output_path.stat().st_size,
        media_type="image/jpeg",
    )


def create_infographic(
    *,
    storyboard: dict[str, Any],
    output_path: Path,
) -> FinalMediaAsset:
    """Export a readable three-card infographic derived only from storyboard evidence claims."""

    scenes = sorted(list(storyboard.get("scenes", [])), key=lambda value: int(value["scene_number"]))
    if len(scenes) != 3:
        raise FinalMediaError("A three-scene storyboard is required for the infographic export.")

    canvas = Image.new("RGB", (1080, 1350), "white")
    draw = ImageDraw.Draw(canvas)
    heading_font = _load_font(48, bold=True)
    scene_font = _load_font(30, bold=True)
    body_font = _load_font(24)
    evidence_font = _load_font(19)
    draw.text((70, 55), str(storyboard.get("title", "EvidenceCast evidence story")), font=heading_font, fill=(25, 25, 25))
    draw.text(
        (72, 120),
        "Three approved evidence claims with traceable source-card identifiers",
        font=evidence_font,
        fill=(75, 75, 75),
    )

    card_y = 190
    for scene in scenes:
        card_height = 330
        draw.rounded_rectangle(
            (60, card_y, 1020, card_y + card_height),
            radius=24,
            fill=(246, 247, 249),
            outline=(205, 210, 218),
            width=2,
        )
        draw.text(
            (95, card_y + 30),
            f"Scene {scene['scene_number']}",
            font=scene_font,
            fill=(28, 55, 92),
        )
        y = card_y + 82
        claim_lines = _fit_text(draw, str(scene.get("key_claim", "")), 830, body_font)
        for line in claim_lines[:7]:
            draw.text((95, y), line, font=body_font, fill=(35, 35, 35))
            y += 34
        evidence_ids = ", ".join(str(value) for value in scene.get("evidence_card_ids", []))
        page_number = scene.get("page_number")
        footer = f"Evidence: {evidence_ids}"
        if page_number is not None:
            footer += f"  •  Source page {page_number}"
        draw.text((95, card_y + 285), footer, font=evidence_font, fill=(75, 75, 75))
        card_y += card_height + 35

    draw.text(
        (70, 1300),
        f"Exported {datetime.now(UTC).date().isoformat()} • EvidenceCast AI",
        font=evidence_font,
        fill=(90, 90, 90),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)
    return FinalMediaAsset(
        path=str(output_path),
        sha256=sha256_file(output_path),
        size_bytes=output_path.stat().st_size,
        media_type="image/png",
    )


def asset_from_path(path: Path, media_type: str) -> FinalMediaAsset:
    if not path.exists() or path.stat().st_size == 0:
        raise FinalMediaError(f"Output asset is missing or empty: {path}")
    return FinalMediaAsset(
        path=str(path),
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
        media_type=media_type,
    )
