# Tests NVIDIA provider configuration and hosted TTS payload handling without external requests.
from __future__ import annotations

from typing import Any

import pytest
from genblaze_core import Modality
from genblaze_core.exceptions import ProviderError
from genblaze_core.models.step import Step

from evidencecast.nvidia_live import (
    DEFAULT_NVIDIA_AUDIO_MODEL,
    DEFAULT_NVIDIA_VOICE,
    NvidiaHostedTTSProvider,
    _scene,
    _segment,
    nvidia_key_configured,
)


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes, text: str = "") -> None:
        self.status_code = status_code
        self.content = content
        self.text = text
        self.headers = {"content-type": "audio/wav"}


class _FakeClient:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self.response

    def close(self) -> None:
        self.closed = True


def _audio_step() -> Step:
    return Step(
        provider="nvidia-hosted-tts",
        model=DEFAULT_NVIDIA_AUDIO_MODEL,
        prompt="Approved evidence narration.",
        modality=Modality.AUDIO,
        params={
            "language": "en-US",
            "voice": DEFAULT_NVIDIA_VOICE,
            "encoding": "LINEAR_PCM",
            "sample_rate_hz": 44100,
        },
    )


def test_nvidia_key_configuration_is_boolean_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    assert nvidia_key_configured() is False
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-value-never-returned")
    assert nvidia_key_configured() is True


def test_hosted_tts_provider_sends_expected_form_fields(tmp_path: Any) -> None:
    client = _FakeClient(_FakeResponse(200, b"RIFF-test-wave-bytes"))
    provider = NvidiaHostedTTSProvider(
        api_key="nvapi-test",
        endpoint="https://nvidia.example.test/v1/audio/synthesize",
        output_dir=tmp_path,
        http_client=client,  # type: ignore[arg-type]
    )

    generated = provider.generate(_audio_step())

    assert len(generated.assets) == 1
    assert generated.assets[0].media_type == "audio/wav"
    assert generated.assets[0].sha256
    assert generated.assets[0].size_bytes == len(b"RIFF-test-wave-bytes")
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["headers"]["Authorization"] == "Bearer nvapi-test"
    assert call["data"] == {
        "text": "Approved evidence narration.",
        "language": "en-US",
        "voice": DEFAULT_NVIDIA_VOICE,
        "encoding": "LINEAR_PCM",
        "sample_rate_hz": "44100",
    }


def test_hosted_tts_provider_classifies_auth_failure(tmp_path: Any) -> None:
    client = _FakeClient(_FakeResponse(401, b"", "invalid token"))
    provider = NvidiaHostedTTSProvider(
        api_key="nvapi-test",
        endpoint="https://nvidia.example.test/v1/audio/synthesize",
        output_dir=tmp_path,
        http_client=client,  # type: ignore[arg-type]
    )

    with pytest.raises(ProviderError, match=r"NVIDIA TTS failed \(401\)"):
        provider.generate(_audio_step())


def test_scene_and_segment_selection_require_approved_three_part_workflow() -> None:
    storyboard = {
        "scene_count": 3,
        "scenes": [
            {"scene_number": number, "evidence_card_ids": [f"EC-{number}"], "visual_prompt": "Prompt"}
            for number in (1, 2, 3)
        ],
    }
    narration = {
        "segments": [
            {
                "scene_number": number,
                "review_status": "approved",
                "reviewed_text": f"Narration {number}",
            }
            for number in (1, 2, 3)
        ]
    }

    assert _scene(storyboard, 2)["scene_number"] == 2
    assert _segment(narration, 3)["reviewed_text"] == "Narration 3"

    narration["segments"][0]["review_status"] = "pending"
    with pytest.raises(ValueError, match="not approved"):
        _segment(narration, 1)
