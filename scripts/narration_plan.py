#!/usr/bin/env python3
"""Build an inspectable narration plan without synthesizing audio."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from natural_flow_rag.embeddings import OllamaEmbedder  # noqa: E402
from natural_flow_rag.lexical_search import LexicalIndex  # noqa: E402
from natural_flow_rag.retrieval import Retriever  # noqa: E402
from natural_flow_rag.runtime import NarrationRuntime  # noqa: E402
from natural_flow_rag.settings import load_settings  # noqa: E402
from natural_flow_rag.vector_store import VectorStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--file", type=Path)
    parser.add_argument("--json", action="store_true", help="emit the complete plan as JSON")
    parser.add_argument("--no-retrieve", action="store_true", help="skip the local retrieval stack")
    args = parser.parse_args()
    text = args.text if args.text is not None else args.file.read_text(encoding="utf-8")

    retriever = None
    if not args.no_retrieve:
        settings = load_settings()
        retriever = Retriever(
            settings,
            VectorStore(settings),
            OllamaEmbedder(settings.embedding),
            LexicalIndex(settings.project_root / "var" / "bm25" / "index.json"),
        )
    plan = NarrationRuntime(retriever).plan(text)
    if args.json:
        print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(
            "route={route} confidence={confidence} segments={segments} "
            "retrieved={retrieved} fallback={fallback}".format(
                route=plan.content_profile["domain"],
                confidence=plan.content_profile["confidence"],
                segments=len(plan.segments),
                retrieved=plan.retrieval_summary["retrieval_count"],
                fallback=bool(plan.fallbacks),
            )
        )
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    raise SystemExit(main())
