# Tests streamed three-scene generation orchestration without making external provider or B2 calls.
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

import evidencecast.media as media


class _Stored:
    def __init__(self, uri: str) -> None:
        self.uri = uri


class _FakeStore:
    def __init__(self) -> None:
        self.settings = SimpleNamespace(bucket="test-bucket")
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def _save(self, name: str, values: dict[str, Any]) -> _Stored:
        self.calls.append((name, values))
        return _Stored(f"b2://test-bucket/{name}/{len(self.calls)}.json")

    def store_generation_request(self, **kwargs: Any) -> _Stored:
        return self._save("generation-request", kwargs)

    def store_scene_request(self, **kwargs: Any) -> _Stored:
        return self._save("scene-request", kwargs)

    def store_scene_result(self, **kwargs: Any) -> _Stored:
        return self._save("scene-result", kwargs)

    def store_progress_event(self, **kwargs: Any) -> _Stored:
        return self._save("progress-event", kwargs)

    def store_generation_summary(self, **kwargs: Any) -> _Stored:
        return self._save("generation-summary", kwargs)


def _storyboard() -> dict[str, Any]:
    return {
        "storyboard_id": "SB-test-storyboard",
        "source_sha256": "b" * 64,
        "scene_count": 3,
        "scenes": [
            {
                "scene_number": number,
                "title": f"Scene {number}",
                "evidence_card_ids": [f"EC-{number:02d}"],
                "visual_prompt": f"Evidence-grounded visual prompt {number}",
            }
            for number in range(1, 4)
        ],
    }


def _successful_scene(**kwargs: Any) -> dict[str, Any]:
    scene = kwargs["scene"]
    number = int(scene["scene_number"])
    return {
        "scene_number": number,
        "title": scene["title"],
        "evidence_card_ids": scene["evidence_card_ids"],
        "provider": kwargs["provider_name"],
        "model": "test-model",
        "run_id": f"run-{number}",
        "step_status": "succeeded",
        "asset_url": f"https://example.test/scene-{number}.png",
        "asset_sha256": str(number) * 64,
        "asset_mime_type": "image/png",
        "manifest_uri": f"b2://test-bucket/manifests/scene-{number}.json",
        "manifest_canonical_hash": str(number + 3) * 64,
        "manifest_verified": True,
        "completed_at": "2026-07-28T00:00:00Z",
    }


def test_progress_stream_persists_three_scene_results(monkeypatch: Any) -> None:
    store = _FakeStore()
    monkeypatch.setattr(media, "_create_genblaze_storage", lambda settings: object())
    monkeypatch.setattr(media, "_generate_scene_image", _successful_scene)

    events = list(
        media.stream_storyboard_image_generation(
            storyboard=_storyboard(),
            store=store,
            provider_name="gmicloud",
        )
    )

    assert events[0].stage == "generation_started"
    assert events[-1].stage == "generation_completed"
    assert events[-1].progress == 1.0
    assert len([event for event in events if event.stage == "scene_completed"]) == 3
    assert len([name for name, _ in store.calls if name == "scene-request"]) == 3
    assert len([name for name, _ in store.calls if name == "scene-result"]) == 3
    assert len([name for name, _ in store.calls if name == "progress-event"]) == len(events)
    assert len([name for name, _ in store.calls if name == "generation-summary"]) == 1


def test_progress_stream_records_partial_failure(monkeypatch: Any) -> None:
    store = _FakeStore()
    monkeypatch.setattr(media, "_create_genblaze_storage", lambda settings: object())

    def generate_with_failure(**kwargs: Any) -> dict[str, Any]:
        if int(kwargs["scene"]["scene_number"]) == 2:
            raise RuntimeError("provider unavailable")
        return _successful_scene(**kwargs)

    monkeypatch.setattr(media, "_generate_scene_image", generate_with_failure)

    events = list(
        media.stream_storyboard_image_generation(
            storyboard=_storyboard(),
            store=store,
            provider_name="gmicloud",
        )
    )

    assert events[-1].stage == "generation_failed"
    assert events[-1].scene_number == 2
    assert "provider unavailable" in events[-1].message
    summaries = [values for name, values in store.calls if name == "generation-summary"]
    assert len(summaries) == 1
    assert summaries[0]["summary"]["status"] == "failed"
    assert len(summaries[0]["summary"]["completed_scenes"]) == 1
