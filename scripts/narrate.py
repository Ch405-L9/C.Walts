#!/usr/bin/env python3
"""Build a narration plan and optionally synthesize it to a local audio file."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from natural_flow_rag.runtime import NarrationRuntime  # noqa: E402
from natural_flow_rag.settings import load_settings  # noqa: E402
from natural_flow_rag.tts.audio import AudioSynthesisService  # noqa: E402
from natural_flow_rag.tts.base import TTSRequestError  # noqa: E402
from natural_flow_rag.tts.elevenlabs import (  # noqa: E402
    ElevenLabsAdapter,
    ElevenLabsConfig,
)
from natural_flow_rag.tts.f5_local import LocalF5Adapter, LocalF5Config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--file", type=Path)
    parser.add_argument("--output", type=Path, default=Path("var/audio/narration.mp3"))
    parser.add_argument("--voice-id")
    parser.add_argument("--model-id")
    parser.add_argument("--with-timestamps", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument(
        "--no-retrieve", action="store_true", help="skip local retrieval for development"
    )
    args = parser.parse_args()
    text = args.text if args.text is not None else args.file.read_text(encoding="utf-8")
    provider = os.getenv("CWALTS_TTS_PROVIDER", "f5_local")
    if provider not in {"elevenlabs", "f5_local"}:
        raise SystemExit("unsupported CWALTS_TTS_PROVIDER")

    retriever = None
    if not args.no_retrieve:
        settings = load_settings()
        from natural_flow_rag.embeddings import OllamaEmbedder
        from natural_flow_rag.lexical_search import LexicalIndex
        from natural_flow_rag.retrieval import Retriever
        from natural_flow_rag.vector_store import VectorStore

        retriever = Retriever(
            settings,
            VectorStore(settings),
            OllamaEmbedder(settings.embedding),
            LexicalIndex(settings.project_root / "var" / "bm25" / "index.json"),
        )
    plan = NarrationRuntime(retriever).plan(text)
    if provider == "f5_local":
        config = LocalF5Config.from_env()
        adapter = LocalF5Adapter(config)
        voice_id = config.voice_name
        model_id = args.model_id or config.model_id
        output_format = "wav"
    else:
        config = ElevenLabsConfig.from_env(args.voice_id, args.model_id)
        adapter = ElevenLabsAdapter(config)
        voice_id = config.voice_id or "configured-voice-required"
        model_id = config.model_id
        output_format = config.output_format
    service = AudioSynthesisService(adapter, provider=provider, cache_dir=Path("var/audio_cache"))
    requests = service.build_requests(
        plan,
        voice_id,
        model_id,
        output_format,
        with_timestamps=args.with_timestamps,
    )
    summary = {
        "route": plan.content_profile["domain"],
        "confidence": plan.content_profile["confidence"],
        "segment_count": len(plan.segments),
        "chunk_count": len(requests),
        "retrieval_count": plan.retrieval_summary.get("retrieval_count", 0),
        "fallbacks": list(plan.fallbacks),
        "provider": provider,
        "provider_model": model_id,
        "voice_configured": bool(voice_id),
        "dry_run": args.dry_run,
        "request_text_hashes": [
            hashlib.sha256(request.text.encode()).hexdigest()
            for request in requests
        ],
    }
    if args.dry_run:
        if args.json_summary:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(
                "dry_run provider=elevenlabs chunks={chunk_count} route={route} "
                "retrieval={retrieval_count}".format(
                    **summary
                )
            )
        return 0
    adapter.validate_configuration()
    try:
        result = service.synthesize(
            plan,
            args.output,
            voice_id,
            model_id,
            output_format,
            args.with_timestamps,
        )
    except TTSRequestError as exc:
        summary.update(
            {
                "http_status": exc.http_status,
                "provider_error_type": exc.provider_error_type,
                "provider_status": exc.provider_status,
                "provider_message": exc.provider_message,
                "request_id": exc.request_id,
                "retryable": exc.retryable,
            }
        )
        if args.json_summary:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(
                "tts_error status={http_status} provider_status={provider_status} "
                "retryable={retryable}".format(**summary)
            )
        return 2
    summary.update(
        {
            "output": str(result.output_path),
            "sidecar": str(result.sidecar_path),
            "provider_request_count": result.provider_request_count,
            "cache_hit_count": result.cache_hit_count,
            "retry_count": result.retry_count,
            "duration_seconds": result.duration_seconds,
        }
    )
    if args.json_summary:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print("audio={output} duration={duration_seconds} chunks={chunk_count}".format(**summary))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    raise SystemExit(main())
