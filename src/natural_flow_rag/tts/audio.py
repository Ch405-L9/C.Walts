"""Deterministic chunking, caching, retry, and atomic audio output."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..narration import NarrationPlan, NarrationSegment
from .base import TTSAdapter, TTSAudioError, TTSRequest, TTSRequestError, TTSResult


@dataclass(frozen=True)
class AudioChunk:
    text: str
    segment_indices: tuple[int, ...]
    previous_text: str | None
    next_text: str | None


@dataclass(frozen=True)
class AudioSynthesisResult:
    output_path: Path
    sidecar_path: Path
    duration_seconds: float | None
    chunk_count: int
    provider_request_count: int
    cache_hit_count: int
    retry_count: int
    voice_settings_used: dict[str, Any]
    mapped_controls: dict[str, Any]
    unmapped_controls: tuple[str, ...]


def chunk_segments(
    segments: tuple[NarrationSegment, ...], max_chars: int = 2400
) -> tuple[AudioChunk, ...]:
    """Group adjacent plan segments without splitting words or sentences."""
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    chunks: list[AudioChunk] = []
    current: list[NarrationSegment] = []
    length = 0
    for segment in segments:
        addition = len(segment.text) if not current else len(segment.text) + 1
        if current and length + addition > max_chars:
            chunks.append(_make_chunk(current, chunks[-1].text if chunks else None, None))
            current = []
            length = 0
        current.append(segment)
        length += len(segment.text) if length == 0 else len(segment.text) + 1
    if current:
        chunks.append(_make_chunk(current, chunks[-1].text if chunks else None, None))
    if len(chunks) > 1:
        chunks = [
            AudioChunk(
                chunk.text,
                chunk.segment_indices,
                chunks[index - 1].text if index else None,
                chunks[index + 1].text if index + 1 < len(chunks) else None,
            )
            for index, chunk in enumerate(chunks)
        ]
    return tuple(chunks)


def _make_chunk(
    segments: list[NarrationSegment], previous: str | None, next_text: str | None
) -> AudioChunk:
    return AudioChunk(
        text=" ".join(segment.text for segment in segments),
        segment_indices=tuple(segment.segment_index for segment in segments),
        previous_text=previous,
        next_text=next_text,
    )


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def cache_key(request: TTSRequest, provider: str, pronunciation_identity: str | None = None) -> str:
    payload = {
        "spoken_text_sha256": hashlib.sha256(request.text.encode("utf-8")).hexdigest(),
        "provider": provider,
        "voice_id": request.voice_id,
        "model_id": request.model_id,
        "voice_settings": request.voice_settings,
        "output_format": request.output_format,
        "apply_text_normalization": request.apply_text_normalization,
        "pronunciation_dictionary_identity": pronunciation_identity,
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def validate_audio_file(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise TTSAudioError("audio output is empty")
    metadata: dict[str, Any] = {"file_size_bytes": path.stat().st_size}
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            result = subprocess.run(  # noqa: S603 - executable is resolved from PATH
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=format_name,duration",
                    "-show_entries",
                    "stream=sample_rate,channels",
                    "-of",
                    "json",
                    str(path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            data = json.loads(result.stdout)
            fmt = data.get("format", {})
            metadata["format"] = fmt.get("format_name")
            metadata["duration_seconds"] = float(fmt["duration"]) if fmt.get("duration") else None
            streams = data.get("streams") or []
            if streams:
                metadata["sample_rate"] = streams[0].get("sample_rate")
                metadata["channels"] = streams[0].get("channels")
            if metadata.get("duration_seconds", 0) <= 0:
                raise TTSAudioError("audio duration is zero")
        except (OSError, subprocess.CalledProcessError, ValueError, KeyError) as exc:
            raise TTSAudioError("audio format validation failed") from exc
    else:
        header = path.read_bytes()[:3]
        if header != b"ID3" and not (header and header[0] == 0xFF):
            raise TTSAudioError("audio container is not recognized")
        metadata["format"] = "mp3"
        metadata["duration_seconds"] = None
    return metadata


class AudioSynthesisService:
    def __init__(
        self,
        adapter: TTSAdapter,
        provider: str = "elevenlabs",
        cache_dir: Path | str = "var/audio_cache",
        max_chars: int = 2400,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.adapter = adapter
        self.provider = provider
        self.cache_dir = Path(cache_dir)
        self.max_chars = max_chars
        self.sleep = sleep

    def build_requests(
        self, plan: NarrationPlan, voice_id: str, model_id: str, output_format: str
    ) -> tuple[TTSRequest, ...]:
        from .elevenlabs import map_plan_to_request

        return tuple(
            map_plan_to_request(
                plan,
                chunk.text,
                voice_id,
                model_id,
                output_format,
                chunk.previous_text,
                chunk.next_text,
            )[0]
            for chunk in chunk_segments(plan.segments, self.max_chars)
        )

    def synthesize(
        self,
        plan: NarrationPlan,
        output_path: Path | str,
        voice_id: str,
        model_id: str,
        output_format: str = "mp3_44100_128",
        with_timestamps: bool = False,
        pronunciation_dictionary_identity: str | None = None,
    ) -> AudioSynthesisResult:
        from .elevenlabs import map_plan_to_request

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        chunks = chunk_segments(plan.segments, self.max_chars)
        if not chunks:
            raise TTSAudioError("narration plan contains no speech segments")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        audio_paths: list[Path] = []
        cache_hits = requests = retries = 0
        mapped_controls: dict[str, Any] = {}
        unmapped: set[str] = set()
        voice_settings: dict[str, Any] = {}
        try:
            for _index, chunk in enumerate(chunks):
                request, mapped, ignored = map_plan_to_request(
                    plan,
                    chunk.text,
                    voice_id,
                    model_id,
                    output_format,
                    chunk.previous_text,
                    chunk.next_text,
                    with_timestamps,
                )
                mapped_controls.update(mapped)
                unmapped.update(ignored)
                voice_settings = dict(request.voice_settings)
                key = cache_key(request, self.provider, pronunciation_dictionary_identity)
                cached = self.cache_dir / f"{key}.audio"
                if cached.is_file() and cached.stat().st_size > 0:
                    cache_hits += 1
                    audio_paths.append(cached)
                    continue
                result: TTSResult | None = None
                for attempt in range(3):
                    try:
                        requests += 1
                        result = self.adapter.synthesize(request)
                        if not result.audio_bytes:
                            raise TTSAudioError("provider returned zero-length audio")
                        break
                    except TTSRequestError as exc:
                        if not exc.retryable or attempt == 2:
                            raise
                        retries += 1
                        self.sleep(0.1 * (2**attempt))
                if result is None:
                    raise TTSAudioError("provider returned no audio")
                temp_cache = cached.with_suffix(".tmp")
                temp_cache.write_bytes(result.audio_bytes)
                if temp_cache.stat().st_size <= 0:
                    temp_cache.unlink(missing_ok=True)
                    raise TTSAudioError("provider returned zero-length audio")
                os.replace(temp_cache, cached)
                audio_paths.append(cached)
            self._assemble(audio_paths, output)
            audio_metadata = validate_audio_file(output)
            sidecar = output.with_suffix(output.suffix + ".json")
            sidecar_data = {
                "schema_version": 1,
                "source_text_sha256": plan.source_text_sha256,
                "narration_plan_sha256": hashlib.sha256(
                    _canonical_json(plan.to_dict())
                ).hexdigest(),
                "provider": self.provider,
                "provider_model": model_id,
                "voice_id": voice_id,
                "output_format": output_format,
                "audio_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "duration_seconds": audio_metadata.get("duration_seconds"),
                "chunk_count": len(chunks),
                "provider_request_count": requests,
                "cache_hit_count": cache_hits,
                "retry_count": retries,
                "voice_settings_used": voice_settings,
                "mapped_controls": mapped_controls,
                "unmapped_controls": sorted(unmapped),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "text_preserved": True,
            }
            temp_sidecar = sidecar.with_suffix(sidecar.suffix + ".tmp")
            temp_sidecar.write_bytes(_canonical_json(sidecar_data))
            os.replace(temp_sidecar, sidecar)
            return AudioSynthesisResult(
                output,
                sidecar,
                audio_metadata.get("duration_seconds"),
                len(chunks),
                requests,
                cache_hits,
                retries,
                voice_settings,
                mapped_controls,
                tuple(sorted(unmapped)),
            )
        except Exception:
            output.unlink(missing_ok=True)
            output.with_suffix(output.suffix + ".json").unlink(missing_ok=True)
            raise

    def _assemble(self, paths: list[Path], output: Path) -> None:
        temp_output = output.with_suffix(output.suffix + ".tmp")
        if len(paths) == 1:
            shutil.copyfile(paths[0], temp_output)
        else:
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise TTSAudioError("ffmpeg is required to assemble multiple audio chunks")
            with tempfile.TemporaryDirectory(prefix="cwalts-audio-") as directory:
                concat = Path(directory) / "concat.txt"
                concat.write_text(
                    "\n".join(f"file '{path.resolve()}'" for path in paths) + "\n", encoding="utf-8"
                )
                subprocess.run(  # noqa: S603 - executable is resolved from PATH
                    [
                        ffmpeg,
                        "-y",
                        "-f",
                        "concat",
                        "-safe",
                        "0",
                        "-i",
                        str(concat),
                        "-c",
                        "copy",
                        str(temp_output),
                    ],
                    check=True,
                    capture_output=True,
                )
        if not temp_output.is_file() or temp_output.stat().st_size <= 0:
            temp_output.unlink(missing_ok=True)
            raise TTSAudioError("audio assembly produced no output")
        os.replace(temp_output, output)


__all__ = [
    "AudioChunk",
    "AudioSynthesisResult",
    "AudioSynthesisService",
    "cache_key",
    "chunk_segments",
    "validate_audio_file",
]
