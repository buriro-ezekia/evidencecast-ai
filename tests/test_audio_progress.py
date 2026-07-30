# Tests streamed narration-audio orchestration without external provider or B2 calls.
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

import evidencecast.audio as audio


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

    def store_audio_generation_request(self, **kwargs: Any) -> _Stored:
        return self._save("generation-request", kwargs)

    def store_audio_segment_request(self, **kwargs: Any) -> _Stored:
        return self._save("segment-request", kwargs)

    def store_audio_segment_result(self, **kwargs: Any) -> _Stored:
        return self._save("segment-result", kwargs)

    def store_audio_progress_event(self, **kwargs: Any) -> _Stored:
        return self._save("progress-event", kwargs)

    def store_audio_generation_summary(self, **kwargs: Any) -> _Stored:
        return self._save("generation-summary", kwargs)


def _plan() -> dict[str, Any]:
    return {
        "narration_id": "NP-test-plan",
        "storyboard_id": "SB-test-storyboard",
        "source_sha256": "b" * 64,
        "language": "English (UK)",
        "voice_style": "clear, calm and educational",
        "review_status": "completed",
        "segments": [
            {
                "scene_number": number,
                "segment_id": f"NS-{number:02d}",
                "evidence_card_ids": [f"EC-{number:02d}"],
                "reviewed_text": f"Approved narration text {number}.",
                "pronunciation_notes": "",
                "review_status": "approved",
            }
            for number in range(1, 4)
        ],
    }


def _successful_segment(**kwargs: Any) -> dict[str, Any]:
    segment = kwargs["segment"]
    number = int(segment["scene_number"])
    return {
        "scene_number": number,
        "segment_id": segment["segment_id"],
        "evidence_card_ids": segment["evidence_card_ids"],
        "reviewed_text": segment["reviewed_text"],
        "provider": "gmicloud",
        "model": kwargs["provider_model"],
        "voice_id": kwargs["voice_id"],
        "run_id": f"run-{number}",
        "step_status": "succeeded",
        "asset_url": f"https://example.test/scene-{number}.mp3",
        "asset_sha256": str(number) * 64,
        "asset_mime_type": "audio/mpeg",
        "manifest_uri": f"b2://test-bucket/manifests/audio-{number}.json",
        "manifest_canonical_hash": str(number + 3) * 64,
        "manifest_verified": True,
        "completed_at": "2026-07-28T00:00:00Z",
    }


def test_nested_gmi_payload_maps_prompt_to_text() -> None:
    payload = {
        "payload": {
            "prompt": "Approved narration text.",
            "voice_id": "presenter_female",
        }
    }

    normalised = audio._normalise_gmi_tts_payload(payload)

    assert normalised["payload"]["text"] == "Approved narration text."
    assert "prompt" not in normalised["payload"]
    assert normalised["payload"]["voice_id"] == "presenter_female"


def test_flat_gmi_payload_maps_prompt_to_text() -> None:
    normalised = audio._normalise_gmi_tts_payload({"prompt": "Narration"})

    assert normalised == {"text": "Narration"}


def test_default_minimax_voice_is_english_presenter() -> None:
    assert audio._default_voice_for_model("minimax-tts-speech-2.6-turbo") == "presenter_female"


def test_non_tts_model_is_rejected() -> None:
    with pytest.raises(audio.AudioGenerationConfigurationError, match="Unsupported narration model"):
        audio._default_voice_for_model("minimax-music-2.5")


def test_audio_progress_persists_three_results(monkeypatch: Any) -> None:
    store = _FakeStore()
    monkeypatch.setenv("GMI_API_KEY", "test-key")
    monkeypatch.setattr(audio, "_create_genblaze_storage", lambda settings: object())
    monkeypatch.setattr(audio, "_generate_segment_audio", _successful_segment)

    events = list(
        audio.stream_narration_audio_generation(
            narration_plan=_plan(),
            store=store,
        )
    )

    assert events[0].stage == "audio_generation_started"
    assert events[-1].stage == "audio_generation_completed"
    assert events[-1].progress == 1.0
    assert len([event for event in events if event.stage == "audio_segment_completed"]) == 3
    assert len([name for name, _ in store.calls if name == "segment-request"]) == 3
    assert len([name for name, _ in store.calls if name == "segment-result"]) == 3
    assert len([name for name, _ in store.calls if name == "progress-event"]) == len(events)
    assert len([name for name, _ in store.calls if name == "generation-summary"]) == 1
    request = next(values for name, values in store.calls if name == "generation-request")
    assert request["request"]["voice_id"] == "presenter_female"


def test_audio_progress_records_partial_failure(monkeypatch: Any) -> None:
    store = _FakeStore()
    monkeypatch.setenv("GMI_API_KEY", "test-key")
    monkeypatch.setattr(audio, "_create_genblaze_storage", lambda settings: object())

    def generate_with_failure(**kwargs: Any) -> dict[str, Any]:
        if int(kwargs["segment"]["scene_number"]) == 2:
            raise RuntimeError("audio provider unavailable")
        return _successful_segment(**kwargs)

    monkeypatch.setattr(audio, "_generate_segment_audio", generate_with_failure)

    events = list(
        audio.stream_narration_audio_generation(
            narration_plan=_plan(),
            store=store,
        )
    )

    assert events[-1].stage == "audio_generation_failed"
    assert events[-1].scene_number == 2
    assert "audio provider unavailable" in events[-1].message
    summaries = [values for name, values in store.calls if name == "generation-summary"]
    assert len(summaries) == 1
    assert summaries[0]["summary"]["status"] == "failed"
    assert summaries[0]["summary"]["voice_id"] == "presenter_female"
    assert len(summaries[0]["summary"]["completed_segments"]) == 1


def test_audio_generation_requires_gmi_key(monkeypatch: Any) -> None:
    store = _FakeStore()
    monkeypatch.delenv("GMI_API_KEY", raising=False)

    try:
        list(audio.stream_narration_audio_generation(narration_plan=_plan(), store=store))
        raised = False
    except audio.AudioGenerationConfigurationError:
        raised = True

    assert raised
    assert "GMI_API_KEY" not in os.environ
