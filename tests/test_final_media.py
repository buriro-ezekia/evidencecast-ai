# Tests subtitle timing and final thumbnail/infographic export without paid media calls.
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from evidencecast.final_media import (
    build_subtitles,
    create_infographic,
    create_thumbnail,
)


def _segments() -> list[dict[str, object]]:
    return [
        {
            "scene_number": 1,
            "review_status": "approved",
            "reviewed_text": "First approved narration.",
            "actual_duration_seconds": 4.5,
        },
        {
            "scene_number": 2,
            "review_status": "approved",
            "reviewed_text": "Second approved narration.",
            "actual_duration_seconds": 5.0,
        },
        {
            "scene_number": 3,
            "review_status": "approved",
            "reviewed_text": "Third approved narration.",
            "actual_duration_seconds": 6.25,
        },
    ]


def _storyboard() -> dict[str, object]:
    return {
        "title": "EvidenceCast three-scene story",
        "scenes": [
            {
                "scene_number": number,
                "key_claim": f"Approved evidence claim {number} with a concise explanation.",
                "evidence_card_ids": [f"EC-{number}"],
                "page_number": number,
            }
            for number in (1, 2, 3)
        ],
    }


def test_subtitles_use_cumulative_audio_durations() -> None:
    srt, vtt, cues = build_subtitles(_segments())

    assert "00:00:00,000 --> 00:00:04,500" in srt
    assert "00:00:04,500 --> 00:00:09,500" in srt
    assert "00:00:09.500 --> 00:00:15.750" in vtt
    assert cues[-1]["end_seconds"] == 15.75


def test_thumbnail_and_infographic_are_created(tmp_path: Path) -> None:
    source = tmp_path / "scene.png"
    Image.new("RGB", (640, 360), "white").save(source)

    thumbnail = create_thumbnail(
        source_image=source,
        title="EvidenceCast",
        subtitle="Approved evidence with traceable narration",
        output_path=tmp_path / "thumbnail.jpg",
    )
    infographic = create_infographic(
        storyboard=_storyboard(),
        output_path=tmp_path / "infographic.png",
    )

    assert Path(thumbnail.path).exists()
    assert thumbnail.sha256 and thumbnail.size_bytes > 0
    assert Path(infographic.path).exists()
    assert infographic.sha256 and infographic.size_bytes > 0

    with Image.open(thumbnail.path) as image:
        assert image.size == (1280, 720)
    with Image.open(infographic.path) as image:
        assert image.size == (1080, 1350)
