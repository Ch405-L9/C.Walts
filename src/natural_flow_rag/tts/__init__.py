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
from .f5_local import LocalF5Adapter, LocalF5Config

__all__ = [
    "ElevenLabsAdapter",
    "ElevenLabsConfig",
    "LocalF5Adapter",
    "LocalF5Config",
    "TTSAudioError",
    "TTSAdapter",
    "TTSConfigurationError",
    "TTSRequest",
    "TTSRequestError",
    "TTSResult",
    "TTSCapabilities",
    "map_plan_to_request",
]
