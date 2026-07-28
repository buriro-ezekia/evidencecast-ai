# Tests scene-level regeneration lineage, transient retries and non-retryable failures.
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

import evidencecast.regeneration as regeneration


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

    def store_regeneration_request(self, **kwargs: Any) -> _Stored:
        return self._save("request", kwargs)

    def store_lineage_edge(self, **kwargs: Any) -> _Stored:
        return self._save("lineage", kwargs)

    def store_regeneration_attempt(self, **kwargs: Any) -> _Stored:
        return self._save("attempt", kwargs)

    def store_regeneration_summary(self, **kwargs: Any) -> _Stored:
        return self._save("summary", kwargs)


def _storyboard() -> dict[str, Any]:
    return {
        "storyboard_id": "SB-test",
        "source_sha256": "a" * 64,
        "scenes": [
            {
                "scene_number": number,
                "title": f"Scene {number}",
                "evidence_card_ids": [f"EC-{number}"],
                "visual_prompt": f"Visual prompt {number}",
            }
            for number in (1, 2, 3)
        ],
    }


def _narration() -> dict[str, Any]:
    return {
        "narration_id": "NP-test",
        "language": "English (UK)",
        "voice_style": "clear",
        "segments": [
            {
                "scene_number": number,
                "segment_id": f"NS-{number}",
                "evidence_card_ids": [f"EC-{number}"],
                "reviewed_text": f"Narration {number}",
                "review_status": "approved",
            }
            for number in (1, 2, 3)
        ],
    }


def _image_result(scene_number: int) -> dict[str, Any]:
    return {
        "scene_number": scene_number,
        "asset_url": f"https://example.test/{scene_number}.png",
        "asset_sha256": str(scene_number) * 64,
        "manifest_uri": f"b2://bucket/{scene_number}.json",
        "manifest_verified": True,
    }


def test_retryable_error_is_retried_then_succeeds(monkeypatch: Any) -> None:
    store = _FakeStore()
    monkeypatch.setattr(regeneration, "_create_audio_storage", lambda settings: object())
    monkeypatch.setattr(regeneration.time, "sleep", lambda seconds: None)
    attempts = {"count": 0}

    def generate(**kwargs: Any) -> dict[str, Any]:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("503 temporarily unavailable")
        return _image_result(int(kwargs["scene"]["scene_number"]))

    monkeypatch.setattr(regeneration, "_generate_scene_image", generate)
    events = list(
        regeneration.stream_scene_regeneration(
            storyboard=_storyboard(),
            narration_plan=_narration(),
            store=store,
            media_kind="image",
            scene_number=2,
            parent_run_id="GEN-parent",
            reason="Improve legibility",
            max_attempts=2,
        )
    )

    assert attempts["count"] == 2
    assert any(event.stage == "retry_scheduled" for event in events)
    assert events[-1].stage == "regeneration_completed"
    assert len([name for name, _ in store.calls if name == "attempt"]) == 2
    lineage = [values for name, values in store.calls if name == "lineage"]
    assert lineage[0]["parent_run_id"] == "GEN-parent"


def test_credit_failure_is_not_retried(monkeypatch: Any) -> None:
    store = _FakeStore()
    monkeypatch.setattr(regeneration, "_create_audio_storage", lambda settings: object())
    calls = {"count": 0}

    def fail(**kwargs: Any) -> dict[str, Any]:
        calls["count"] += 1
        raise RuntimeError("402 insufficient credits")

    monkeypatch.setattr(regeneration, "_generate_scene_image", fail)
    events = list(
        regeneration.stream_scene_regeneration(
            storyboard=_storyboard(),
            narration_plan=_narration(),
            store=store,
            media_kind="image",
            scene_number=1,
            parent_run_id="GEN-parent",
            reason="Retry provider run",
            max_attempts=3,
        )
    )

    assert calls["count"] == 1
    assert not any(event.stage == "retry_scheduled" for event in events)
    assert events[-1].stage == "regeneration_failed"
    summaries = [values for name, values in store.calls if name == "summary"]
    assert summaries[0]["summary"]["retryable"] is False


def test_retry_classifier_distinguishes_transient_and_permanent_failures() -> None:
    assert regeneration.is_retryable_provider_error("429 rate limit") is True
    assert regeneration.is_retryable_provider_error("504 gateway timeout") is True
    assert regeneration.is_retryable_provider_error("400 required parameter missing") is False
    assert regeneration.is_retryable_provider_error("402 insufficient credits") is False
