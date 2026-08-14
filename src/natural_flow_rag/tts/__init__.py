"""Text-to-speech provider adapters and local audio orchestration."""

from .base import (
    TTSAdapter,
    TTSAudioError,
    TTSCapabilities,
    TTSConfigurationError,
    TTSRequest,
    TTSRequestError,
    TTSResult,
)
from .elevenlabs import ElevenLabsAdapter, ElevenLabsConfig, map_plan_to_request

__all__ = [
    "ElevenLabsAdapter",
    "ElevenLabsConfig",
    "TTSAudioError",
    "TTSAdapter",
    "TTSConfigurationError",
    "TTSRequest",
    "TTSRequestError",
    "TTSResult",
    "TTSCapabilities",
    "map_plan_to_request",
]
