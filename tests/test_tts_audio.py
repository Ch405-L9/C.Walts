"""Offline adapter and audio orchestration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

import natural_flow_rag.tts.audio as audio_module
from natural_flow_rag.narration import NarrationSegment
from natural_flow_rag.runtime import NarrationRuntime
from natural_flow_rag.tts.audio import AudioSynthesisService, chunk_segments
from natural_flow_rag.tts.base import TTSRequest, TTSRequestError, TTSResult
from natural_flow_rag.tts.elevenlabs import ElevenLabsConfig, map_plan_to_request


class MockAdapter:
    def __init__(self, responses: list[TTSResult | Exception] | None = None):
        self.responses = list(responses or [TTSResult(b"ID3mock-audio")])
        self.calls: list[TTSRequest] = []

    def validate_configuration(self) -> None:
        return None

    def capabilities(self):
        return None

    def synthesize(self, request: TTSRequest) -> TTSResult:
        self.calls.append(request)
        response = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        if isinstance(response, Exception):
            raise response
        return response


def _plan(text: str = "A clear sentence for audio."):
    return NarrationRuntime().plan(text, {"domain": "educational"})


def test_provider_mapping_is_deterministic_and_does_not_insert_prompt() -> None:
    plan = _plan()
    request, mapped, unmapped = map_plan_to_request(
        plan, plan.segments[0].text, "voice", "eleven_multilingual_v2", "mp3_44100_128"
    )
    assert request.text == plan.segments[0].text
    assert "Speak dramatically" not in request.text
    assert mapped["model_id"] == "eleven_multilingual_v2"
    assert "pitch_tendency" in unmapped


def test_chunking_is_bounded_and_deterministic() -> None:
    segments = tuple(
        NarrationSegment(f"Sentence {index}.", "x", index, False, 0, 0, "none", 1.0, 1.0, "neutral")
        for index in range(5)
    )
    first = chunk_segments(segments, max_chars=25)
    second = chunk_segments(segments, max_chars=25)
    assert first == second
    assert len(first) > 1
    assert all(chunk.text for chunk in first)


def test_cache_avoids_duplicate_provider_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(audio_module, "validate_audio_file", lambda path: {"duration_seconds": 1.0})
    adapter = MockAdapter()
    service = AudioSynthesisService(adapter, cache_dir=tmp_path / "cache")
    output_one = tmp_path / "one.mp3"
    output_two = tmp_path / "two.mp3"
    service.synthesize(_plan(), output_one, "voice", "eleven_multilingual_v2")
    result = service.synthesize(_plan(), output_two, "voice", "eleven_multilingual_v2")
    assert len(adapter.calls) == 1
    assert result.cache_hit_count == 1
    assert output_two.read_bytes().startswith(b"ID3")


def test_transient_retry_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audio_module, "validate_audio_file", lambda path: {"duration_seconds": 1.0})
    adapter = MockAdapter(
        [
            TTSRequestError(503, True),
            TTSRequestError(503, True),
            TTSResult(b"ID3retry"),
        ]
    )
    service = AudioSynthesisService(adapter, cache_dir=tmp_path / "cache", sleep=lambda _: None)
    result = service.synthesize(_plan(), tmp_path / "retry.mp3", "voice", "eleven_multilingual_v2")
    assert result.retry_count == 2
    assert result.provider_request_count == 3


def test_zero_length_audio_is_rejected_atomically(tmp_path: Path) -> None:
    adapter = MockAdapter([TTSResult(b"")])
    service = AudioSynthesisService(adapter, cache_dir=tmp_path / "cache")
    output = tmp_path / "bad.mp3"
    with pytest.raises(Exception, match="zero-length"):
        service.synthesize(_plan(), output, "voice", "eleven_multilingual_v2")
    assert not output.exists()


def test_missing_configuration_is_concise() -> None:
    from natural_flow_rag.tts.elevenlabs import ElevenLabsAdapter

    with pytest.raises(ValueError, match="missing ELEVENLABS_API_KEY"):
        ElevenLabsAdapter(ElevenLabsConfig(None, "voice")).validate_configuration()


def test_provider_error_does_not_include_secret() -> None:
    error = TTSRequestError(401, False)
    assert "redacted-test-marker" not in str(error)
