# Probes local media duration with FFprobe so subtitle cues match the uploaded narration clips.
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .final_media import FinalMediaError


def probe_duration_seconds(path: Path, *, timeout: int = 30) -> float:
    """Return a positive media duration from FFprobe."""

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise FinalMediaError(
            "FFprobe is not installed or is not available on PATH. Install ffmpeg in the Codespace."
        )
    if not path.exists() or path.stat().st_size == 0:
        raise FinalMediaError(f"Cannot probe a missing or empty media file: {path}")
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise FinalMediaError(f"FFprobe timed out while reading {path.name}.") from exc
    if result.returncode != 0:
        raise FinalMediaError(
            f"FFprobe could not read {path.name}: {(result.stderr or result.stdout).strip()}"
        )
    try:
        duration = float(result.stdout.strip())
    except ValueError as exc:
        raise FinalMediaError(f"FFprobe returned an invalid duration for {path.name}.") from exc
    if duration <= 0:
        raise FinalMediaError(f"FFprobe returned a non-positive duration for {path.name}.")
    return duration
