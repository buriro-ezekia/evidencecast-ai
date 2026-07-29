# Tests local evidence image rendering, approved narration synthesis and cross-stage safeguards.
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

import evidencecast.local_assets as local_assets


def _storyboard() -> dict[str, Any]:
    return {
        "storyboard_id": "SB-local-test",
        "source_sha256": "a" * 64,
        "scene_count": 3,
        "review_mode": "approved_only",
        "title": "EvidenceCast local validation",
        "scenes": [
            {
                "scene_number": number,
                "title": f"Scene title {number}",
                "key_claim": f"Approved evidence claim {number}.",
                "evidence_card_ids": [f"EC-{number:02d}"],
                "page_number": number,
            }
            for number in range(1, 4)
        ],
    }


def _narration_plan() -> dict[str, Any]:
    return {
        "narration_id": "NP-local-test",
        "storyboard_id": "SB-local-test",
        "source_sha256": "a" * 64,
        "review_status": "completed",
        "segments": [
            {
                "scene_number": number,
                "segment_id": f"NS-{number:02d}",
                "evidence_card_ids": [f"EC-{number:02d}"],
                "reviewed_text": f"Approved spoken narration {number}.",
                "review_status": "approved",
            }
            for number in range(1, 4)
        ],
    }


def test_local_scene_image_is_labelled_and_valid(tmp_path: Path) -> None:
    output = tmp_path / "scene.png"
    asset = local_assets.create_local_scene_image(
        scene=_storyboard()["scenes"][0],
        output_path=output,
    )

    assert output.exists()
    assert asset.kind == "image"
    assert asset.generator == "evidencecast-local-pillow"
    assert asset.sha256
    assert asset.size_bytes == output.stat().st_size
    with Image.open(output) as image:
        assert image.size == (1280, 720)
        assert image.mode == "RGB"


def test_local_narration_requires_approval(tmp_path: Path) -> None:
    segment = _narration_plan()["segments"][0]
    segment["review_status"] = "pending"

    with pytest.raises(local_assets.LocalAssetError, match="not approved"):
        local_assets.synthesise_local_narration(
            segment=segment,
            output_path=tmp_path / "scene.wav",
        )


def test_local_narration_builds_espeak_command(monkeypatch: Any, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(local_assets, "require_espeak", lambda: "/usr/bin/espeak-ng")

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        output_path = Path(command[command.index("-w") + 1])
        output_path.write_bytes(b"RIFF" + b"\x00" * 128)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(local_assets.subprocess, "run", fake_run)
    segment = _narration_plan()["segments"][0]
    output = tmp_path / "scene.wav"
    asset = local_assets.synthesise_local_narration(segment=segment, output_path=output)

    command = captured["command"]
    assert command[0] == "/usr/bin/espeak-ng"
    assert command[command.index("-v") + 1] == "en-gb"
    assert command[command.index("-w") + 1] == str(output)
    assert command[-1] == segment["reviewed_text"]
    assert asset.kind == "audio"
    assert asset.generator == "local-espeak-ng"
    assert asset.media_type == "audio/wav"


def test_complete_local_bundle_generates_six_assets(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(local_assets, "require_espeak", lambda: "/usr/bin/espeak-ng")

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        output_path = Path(command[command.index("-w") + 1])
        output_path.write_bytes(b"RIFF" + b"\x00" * 256)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(local_assets.subprocess, "run", fake_run)
    result = local_assets.generate_local_validation_assets(
        storyboard=_storyboard(),
        narration_plan=_narration_plan(),
        output_directory=tmp_path,
    )

    assert result["status"] == "completed"
    assert result["origin"] == "local_validation_fallback"
    assert len(result["images"]) == 3
    assert len(result["audio"]) == 3
    assert all(Path(value["path"]).exists() for value in [*result["images"], *result["audio"]])
    assert all(value["evidence_card_ids"] for value in [*result["images"], *result["audio"]])


def test_local_bundle_rejects_evidence_link_mismatch(tmp_path: Path) -> None:
    narration = _narration_plan()
    narration["segments"][1]["evidence_card_ids"] = ["EC-WRONG"]

    with pytest.raises(local_assets.LocalAssetError, match="Scene 2 evidence-card links"):
        local_assets.generate_local_validation_assets(
            storyboard=_storyboard(),
            narration_plan=narration,
            output_directory=tmp_path,
        )
