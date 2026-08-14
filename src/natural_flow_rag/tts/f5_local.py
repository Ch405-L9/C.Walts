"""Local F5-TTS zero-shot voice-cloning adapter."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..narration import NarrationPlan
from .base import TTSCapabilities, TTSConfigurationError, TTSRequest, TTSResult


@dataclass(frozen=True)
class LocalF5Config:
    reference_audio: Path | None
    reference_text: str | None = None
    model_id: str = "F5TTS_v1_Base"
    voice_name: str = "B.Lawson"
    device: str = "cpu"

    @classmethod
    def from_env(cls) -> LocalF5Config:
        reference = os.getenv("CWALTS_F5_REFERENCE_AUDIO")
        text_path = os.getenv("CWALTS_F5_REFERENCE_TEXT")
        reference_text = None
        if text_path:
            path = Path(text_path)
            if path.is_file():
                reference_text = path.read_text(encoding="utf-8").strip()
        return cls(
            reference_audio=Path(reference) if reference else None,
            reference_text=reference_text,
            model_id=os.getenv("CWALTS_F5_MODEL_ID", "F5TTS_v1_Base"),
            voice_name=os.getenv("CWALTS_LOCAL_VOICE_NAME", "B.Lawson"),
            device=os.getenv("CWALTS_F5_DEVICE", "cpu"),
        )


class LocalF5Adapter:
    """F5-TTS adapter with lazy model loading and no network API credentials."""

    def __init__(self, config: LocalF5Config, engine: Any | None = None):
        self.config = config
        self._engine = engine

    def capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            provider="f5_local",
            models=("F5TTS_v1_Base",),
            output_formats=("wav",),
            supports_timestamps=False,
            supports_continuity=False,
            supports_pronunciation_dictionaries=False,
            supported_controls=(),
        )

    def validate_configuration(self) -> None:
        reference = self.config.reference_audio
        if reference is None or not reference.is_file():
            raise TTSConfigurationError("missing or unreadable CWALTS_F5_REFERENCE_AUDIO")
        if reference.stat().st_size <= 0:
            raise TTSConfigurationError("CWALTS_F5_REFERENCE_AUDIO is empty")
        if self.config.model_id != "F5TTS_v1_Base":
            raise TTSConfigurationError("unsupported local F5 model")

    def build_request(
        self,
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
        del plan, voice_id, previous_text, next_text, with_timestamps
        if pronunciation_dictionary_locators:
            raise TTSConfigurationError("local F5 does not support pronunciation dictionaries")
        if output_format != "wav":
            raise TTSConfigurationError("local F5 output format must be wav")
        reference = self.config.reference_audio
        reference_hash = None
        if reference and reference.is_file():
            reference_hash = hashlib.sha256(reference.read_bytes()).hexdigest()
        mapped = {
            "reference_audio_sha256": reference_hash,
            "reference_text_configured": bool(self.config.reference_text),
            "device": self.config.device,
        }
        request = TTSRequest(
            text=text,
            voice_id=self.config.voice_name,
            model_id=model_id,
            output_format="wav",
        )
        return request, mapped, (
            "pause_before_ms",
            "pause_after_ms",
            "emphasis",
            "pace_modifier",
            "energy_modifier",
            "pitch_tendency",
            "volume_tendency",
            "dialogue_handling",
            "pronunciation_hints",
        )

    def _load_engine(self) -> Any:
        if self._engine is None:
            from f5_tts.api import F5TTS

            self._engine = F5TTS(model=self.config.model_id, device=self.config.device)
        return self._engine

    def synthesize(self, request: TTSRequest) -> TTSResult:
        self.validate_configuration()
        engine = self._load_engine()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as output:
            output_path = Path(output.name)
        try:
            engine.infer(
                str(self.config.reference_audio),
                self.config.reference_text or "",
                request.text,
                show_info=lambda _message: None,
                file_wave=str(output_path),
            )
            audio = output_path.read_bytes()
            if not audio:
                raise TTSConfigurationError("local F5 returned empty audio")
            return TTSResult(audio, "audio/wav")
        finally:
            output_path.unlink(missing_ok=True)


def map_plan_to_request(
    adapter: LocalF5Adapter,
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
    return adapter.build_request(
        plan,
        text,
        voice_id,
        model_id,
        output_format,
        previous_text,
        next_text,
        with_timestamps,
        pronunciation_dictionary_locators,
    )


__all__ = ["LocalF5Adapter", "LocalF5Config", "map_plan_to_request"]
