"""Offline adapter and audio orchestration tests."""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

import natural_flow_rag.tts.audio as audio_module
import natural_flow_rag.tts.elevenlabs as elevenlabs_module
from natural_flow_rag.narration import NarrationSegment
from natural_flow_rag.runtime import NarrationRuntime
from natural_flow_rag.tts.audio import AudioSynthesisService, cache_key, chunk_segments
from natural_flow_rag.tts.base import TTSRequest, TTSRequestError, TTSResult
from natural_flow_rag.tts.elevenlabs import ElevenLabsAdapter, ElevenLabsConfig, map_plan_to_request
from natural_flow_rag.tts.f5_local import LocalF5Adapter, LocalF5Config


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


def test_cache_identity_covers_continuity_timestamps_and_pronunciation() -> None:
    base = TTSRequest("spoken", "voice", "model", "format")
    changed = TTSRequest(
        "spoken",
        "voice",
        "model",
        "format",
        previous_text="previous",
        next_text="next",
        with_timestamps=True,
        pronunciation_dictionary_locators=({"pronunciation_dictionary_id": "dict"},),
    )
    assert cache_key(base, "provider") != cache_key(changed, "provider")


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


def test_timestamps_and_pronunciation_locators_are_persisted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(audio_module, "validate_audio_file", lambda path: {"duration_seconds": 1.0})
    adapter = MockAdapter(
        [TTSResult(b"ID3timed", alignment={
            "chars": ["x"],
            "charStartTimesSeconds": [0.0],
            "charEndTimesSeconds": [0.2],
        })]
    )
    service = AudioSynthesisService(adapter, cache_dir=tmp_path / "cache")
    result = service.synthesize(
        _plan(),
        tmp_path / "timed.mp3",
        "voice",
        "eleven_multilingual_v2",
        with_timestamps=True,
        pronunciation_dictionary_locators=({"pronunciation_dictionary_id": "dict"},),
    )
    assert result.timestamps_path is not None
    timing = result.timestamps_path.read_text(encoding="utf-8")
    assert "character_count" in timing
    assert "chars" not in timing
    assert adapter.calls[0].pronunciation_dictionary_locators


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


@pytest.mark.parametrize(
    ("status_code", "provider_status", "provider_message", "retryable"),
    [
        (403, "insufficient_permissions", "Text to Speech permission required", False),
        (402, "quota_exceeded", "Account quota is exhausted", False),
        (400, "validation_error", "Invalid output format", False),
        (401, "invalid_api_key", "The API key is invalid", False),
        (429, "rate_limit_exceeded", "Too many requests", True),
    ],
)
def test_http_error_parsing_is_sanitized(
    status_code: int,
    provider_status: str,
    provider_message: str,
    retryable: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.dumps(
        {
            "error_type": "provider_error",
            "detail": {"status": provider_status, "message": provider_message},
            "request_text": "PRIVATE_QUERY_SENTINEL",
        }
    ).encode()

    def fail(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://api.example.test",
            status_code,
            "provider failure",
            {"request-id": "request-123"},
            io.BytesIO(payload),
        )

    monkeypatch.setattr(elevenlabs_module.urllib.request, "urlopen", fail)
    adapter = ElevenLabsAdapter(ElevenLabsConfig("secret-api-key", "voice"))
    request = TTSRequest("PRIVATE_QUERY_SENTINEL", "voice", "model", "format")
    with pytest.raises(TTSRequestError) as raised:
        adapter.synthesize(request)
    error = raised.value
    assert error.http_status == status_code
    assert error.provider_error_type == "provider_error"
    assert error.provider_status == provider_status
    assert error.provider_message == provider_message
    assert error.request_id == "request-123"
    assert error.retryable is retryable
    assert "secret-api-key" not in str(error)
    assert "PRIVATE_QUERY_SENTINEL" not in str(error)


def test_unparseable_http_error_is_not_dumped(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://api.example.test",
            422,
            "provider failure",
            {},
            io.BytesIO(b"PRIVATE_QUERY_SENTINEL raw response"),
        )

    monkeypatch.setattr(elevenlabs_module.urllib.request, "urlopen", fail)
    adapter = ElevenLabsAdapter(ElevenLabsConfig("secret-api-key", "voice"))
    with pytest.raises(TTSRequestError) as raised:
        adapter.synthesize(TTSRequest("PRIVATE_QUERY_SENTINEL", "voice", "model", "format"))
    error = raised.value
    assert error.http_status == 422
    assert error.provider_status == "unparseable_provider_error"
    assert error.provider_message is None
    assert error.retryable is False


def test_local_f5_mapping_preserves_source_text_and_needs_no_api_key(tmp_path: Path) -> None:
    reference = tmp_path / "reference.mp3"
    reference.write_bytes(b"reference")
    adapter = LocalF5Adapter(LocalF5Config(reference_audio=reference))
    adapter.validate_configuration()
    plan = _plan("A local voice sample.")
    request, mapped, unmapped = adapter.build_request(
        plan, plan.segments[0].text, "ignored", "F5TTS_v1_Base", "wav"
    )
    assert request.text == plan.segments[0].text
    assert request.voice_id == "B.Lawson"
    assert "reference_audio_sha256" in mapped
    assert "pitch_tendency" in unmapped
    assert adapter.capabilities().provider == "f5_local"


def test_local_f5_missing_reference_fails_clearly() -> None:
    adapter = LocalF5Adapter(LocalF5Config(reference_audio=None))
    with pytest.raises(ValueError, match="CWALTS_F5_REFERENCE_AUDIO"):
        adapter.validate_configuration()


def test_local_f5_mock_inference_returns_audio_without_network(tmp_path: Path) -> None:
    reference = tmp_path / "reference.mp3"
    reference.write_bytes(b"reference")

    class FakeEngine:
        def infer(self, ref_file, ref_text, gen_text, **kwargs):
            assert ref_file == str(reference)
            assert ref_text == "Reference words."
            assert gen_text == "Synthetic speech."
            Path(kwargs["file_wave"]).write_bytes(b"RIFFsynthetic-wav")

    adapter = LocalF5Adapter(
        LocalF5Config(reference, reference_text="Reference words."), engine=FakeEngine()
    )
    result = adapter.synthesize(TTSRequest("Synthetic speech.", "B.Lawson", "F5TTS_v1_Base", "wav"))
    assert result.audio_bytes == b"RIFFsynthetic-wav"
    assert result.content_type == "audio/wav"
