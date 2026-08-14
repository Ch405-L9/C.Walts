"""Provider-neutral contracts for narration-to-audio adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class TTSConfigurationError(ValueError):
    """Raised when a provider cannot be configured safely."""


class TTSRequestError(RuntimeError):
    """Sanitized provider request failure."""

    def __init__(
        self,
        status_code: int | None,
        retryable: bool,
        message: str = "tts request failed",
        provider_error_type: str | None = None,
        provider_status: str | None = None,
        provider_message: str | None = None,
        request_id: str | None = None,
    ):
        super().__init__(message)
        self.http_status = status_code
        self.status_code = status_code
        self.retryable = retryable
        self.provider_error_type = provider_error_type
        self.provider_status = provider_status
        self.provider_message = provider_message
        self.request_id = request_id


class TTSAudioError(RuntimeError):
    """Raised when audio cannot be validated or assembled."""


@dataclass(frozen=True)
class TTSCapabilities:
    provider: str
    models: tuple[str, ...]
    output_formats: tuple[str, ...]
    supports_timestamps: bool
    supports_continuity: bool
    supports_pronunciation_dictionaries: bool
    supported_controls: tuple[str, ...]


@dataclass(frozen=True)
class TTSRequest:
    text: str
    voice_id: str
    model_id: str
    output_format: str
    voice_settings: dict[str, Any] = field(default_factory=dict)
    apply_text_normalization: str = "auto"
    previous_text: str | None = None
    next_text: str | None = None
    pronunciation_dictionary_locators: tuple[dict[str, str], ...] = ()
    with_timestamps: bool = False


@dataclass(frozen=True)
class TTSResult:
    audio_bytes: bytes
    content_type: str = "audio/mpeg"
    alignment: dict[str, Any] | None = None
    request_id: str | None = None


class TTSAdapter(Protocol):
    def synthesize(self, request: TTSRequest) -> TTSResult: ...

    def capabilities(self) -> TTSCapabilities: ...

    def validate_configuration(self) -> None: ...


__all__ = [
    "TTSAudioError",
    "TTSAdapter",
    "TTSConfigurationError",
    "TTSRequest",
    "TTSRequestError",
    "TTSResult",
    "TTSCapabilities",
]
