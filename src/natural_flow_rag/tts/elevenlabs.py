"""Conservative ElevenLabs HTTP adapter.

The adapter owns provider-specific request fields. NarrationPlan remains
provider-neutral and is never sent as prompt text.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from ..narration import NarrationPlan
from .base import TTSCapabilities, TTSConfigurationError, TTSRequest, TTSRequestError, TTSResult

SUPPORTED_MODELS = ("eleven_multilingual_v2", "eleven_flash_v2_5", "eleven_v3")
SUPPORTED_FORMATS = ("mp3_44100_128", "mp3_44100_192", "pcm_44100")

_PROFILES: dict[str, dict[str, float | bool]] = {
    "neutral_clear": {
        "stability": 0.68,
        "similarity_boost": 0.75,
        "style": 0.0,
        "use_speaker_boost": True,
        "speed": 1.0,
    },
    "technical": {
        "stability": 0.80,
        "similarity_boost": 0.75,
        "style": 0.0,
        "use_speaker_boost": True,
        "speed": 0.93,
    },
    "compliance": {
        "stability": 0.82,
        "similarity_boost": 0.75,
        "style": 0.0,
        "use_speaker_boost": True,
        "speed": 0.93,
    },
    "educational": {
        "stability": 0.74,
        "similarity_boost": 0.75,
        "style": 0.03,
        "use_speaker_boost": True,
        "speed": 0.98,
    },
    "children": {
        "stability": 0.56,
        "similarity_boost": 0.75,
        "style": 0.08,
        "use_speaker_boost": True,
        "speed": 1.04,
    },
    "horror_suspense": {
        "stability": 0.76,
        "similarity_boost": 0.75,
        "style": 0.03,
        "use_speaker_boost": True,
        "speed": 0.94,
    },
    "commercial": {
        "stability": 0.62,
        "similarity_boost": 0.75,
        "style": 0.06,
        "use_speaker_boost": True,
        "speed": 1.03,
    },
    "reflective": {
        "stability": 0.76,
        "similarity_boost": 0.75,
        "style": 0.02,
        "use_speaker_boost": True,
        "speed": 0.93,
    },
}


@dataclass(frozen=True)
class ElevenLabsConfig:
    api_key: str | None
    voice_id: str | None
    model_id: str = "eleven_multilingual_v2"
    output_format: str = "mp3_44100_128"
    base_url: str = "https://api.elevenlabs.io"
    apply_text_normalization: str = "auto"
    pronunciation_dictionary_locators: tuple[dict[str, str], ...] = ()
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(
        cls, voice_id: str | None = None, model_id: str | None = None
    ) -> ElevenLabsConfig:
        return cls(
            api_key=os.getenv("ELEVENLABS_API_KEY"),
            voice_id=voice_id or os.getenv("CWALTS_ELEVENLABS_VOICE_ID"),
            model_id=model_id or os.getenv("CWALTS_ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
            output_format=os.getenv("CWALTS_ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128"),
        )


class ElevenLabsAdapter:
    def __init__(self, config: ElevenLabsConfig):
        self.config = config

    def capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            provider="elevenlabs",
            models=SUPPORTED_MODELS,
            output_formats=SUPPORTED_FORMATS,
            supports_timestamps=True,
            supports_continuity=True,
            supports_pronunciation_dictionaries=True,
            supported_controls=(
                "stability",
                "similarity_boost",
                "style",
                "use_speaker_boost",
                "speed",
            ),
        )

    def validate_configuration(self) -> None:
        if not self.config.api_key:
            raise TTSConfigurationError("missing ELEVENLABS_API_KEY")
        if not self.config.voice_id:
            raise TTSConfigurationError("missing CWALTS_ELEVENLABS_VOICE_ID")
        if self.config.model_id not in SUPPORTED_MODELS:
            raise TTSConfigurationError("unsupported ElevenLabs model")
        if self.config.output_format not in SUPPORTED_FORMATS:
            raise TTSConfigurationError("unsupported ElevenLabs output format")

    def synthesize(self, request: TTSRequest) -> TTSResult:
        self.validate_configuration()
        path = f"/v1/text-to-speech/{urllib.parse.quote(request.voice_id, safe='')}"
        if request.with_timestamps:
            path += "/with-timestamps"
        query = urllib.parse.urlencode({"output_format": request.output_format})
        payload: dict[str, Any] = {
            "text": request.text,
            "model_id": request.model_id,
            "voice_settings": request.voice_settings,
            "apply_text_normalization": request.apply_text_normalization,
        }
        if request.previous_text:
            payload["previous_text"] = request.previous_text
        if request.next_text:
            payload["next_text"] = request.next_text
        if request.pronunciation_dictionary_locators:
            payload["pronunciation_dictionary_locators"] = list(
                request.pronunciation_dictionary_locators
            )
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        http_request = urllib.request.Request(  # noqa: S310 - base URL is fixed/configured HTTP(S)
            f"{self.config.base_url}{path}?{query}",
            data=body,
            method="POST",
            headers={"xi-api-key": self.config.api_key or "", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 - base URL is fixed/configured HTTP(S)
                http_request, timeout=self.config.timeout_seconds
            ) as response:
                raw = response.read()
                content_type = response.headers.get("Content-Type", "audio/mpeg")
                request_id = response.headers.get("request-id")
        except urllib.error.HTTPError as exc:
            raise _sanitized_http_error(exc, request.text, self.config.api_key) from None
        except (urllib.error.URLError, TimeoutError):
            raise TTSRequestError(None, True) from None
        if request.with_timestamps:
            try:
                data = json.loads(raw.decode("utf-8"))
                audio = base64.b64decode(data["audio_base64"], validate=True)
                alignment = data.get("alignment") or data.get("normalized_alignment")
            except (ValueError, KeyError, base64.binascii.Error):
                raise TTSRequestError(None, False, "invalid timestamp response") from None
            return TTSResult(audio, "audio/mpeg", alignment, request_id)
        return TTSResult(raw, content_type, None, request_id)


def _safe_provider_text(value: Any, forbidden: tuple[str, ...]) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if any(secret and secret in value for secret in forbidden):
        return "provider_error_message_redacted"
    return value[:240]


def _sanitized_http_error(
    error: urllib.error.HTTPError,
    request_text: str,
    api_key: str | None,
) -> TTSRequestError:
    body = error.read()
    provider_error_type = None
    provider_status = None
    provider_message = None
    try:
        data = json.loads(body.decode("utf-8"))
        detail = data.get("detail") if isinstance(data, dict) else None
        forbidden = (api_key or "", request_text)
        provider_error_type = _safe_provider_text(
            data.get("error_type") if isinstance(data, dict) else None,
            forbidden,
        )
        if isinstance(detail, dict):
            provider_status = _safe_provider_text(detail.get("status"), forbidden)
            provider_message = _safe_provider_text(detail.get("message"), forbidden)
        elif isinstance(detail, str):
            provider_message = _safe_provider_text(detail, forbidden)
    except (UnicodeDecodeError, json.JSONDecodeError):
        provider_status = "unparseable_provider_error"
    return TTSRequestError(
        status_code=error.code,
        retryable=error.code == 429 or error.code >= 500,
        provider_error_type=provider_error_type,
        provider_status=provider_status,
        provider_message=provider_message,
        request_id=error.headers.get("request-id") if error.headers else None,
    )


def map_plan_to_request(
    plan: NarrationPlan,
    text: str,
    voice_id: str,
    model_id: str,
    output_format: str,
    previous_text: str | None = None,
    next_text: str | None = None,
    with_timestamps: bool = False,
    pronunciation_dictionary_locators: tuple[dict[str, str], ...] = (),
) -> tuple[TTSRequest, dict[str, Any], tuple[str, ...]]:
    profile = plan.content_profile
    key = profile.get("genre") if profile.get("genre") in _PROFILES else profile.get("domain")
    voice_settings = dict(_PROFILES.get(str(key), _PROFILES["neutral_clear"]))
    mapped = {
        "voice_id": voice_id,
        "model_id": model_id,
        "voice_settings": voice_settings,
        "speed": voice_settings["speed"],
    }
    unmapped = [
        "pause_before_ms",
        "pause_after_ms",
        "emphasis",
        "pitch_tendency",
        "volume_tendency",
    ]
    if pronunciation_dictionary_locators:
        mapped["pronunciation_dictionary_locators"] = pronunciation_dictionary_locators
    else:
        unmapped.append("pronunciation_hints")
    request = TTSRequest(
        text=text,
        voice_id=voice_id,
        model_id=model_id,
        output_format=output_format,
        voice_settings=voice_settings,
        apply_text_normalization="auto",
        previous_text=previous_text,
        next_text=next_text,
        pronunciation_dictionary_locators=pronunciation_dictionary_locators,
        with_timestamps=with_timestamps,
    )
    return request, mapped, tuple(unmapped)


__all__ = [
    "ElevenLabsAdapter",
    "ElevenLabsConfig",
    "SUPPORTED_FORMATS",
    "SUPPORTED_MODELS",
    "map_plan_to_request",
]
