#!/usr/bin/env python3
"""Ad-hoc retrieval check.  python scripts/query.py "make this sound natural" --explain"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from natural_flow_rag.citations import build_citations  # noqa: E402
from natural_flow_rag.embeddings import OllamaEmbedder  # noqa: E402
from natural_flow_rag.lexical_search import LexicalIndex  # noqa: E402
from natural_flow_rag.retrieval import Retriever  # noqa: E402
from natural_flow_rag.settings import load_settings  # noqa: E402
from natural_flow_rag.vector_store import VectorStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--explain", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    store = VectorStore(settings)
    lexical = LexicalIndex(settings.project_root / "var" / "bm25" / "index.json")
    retriever = Retriever(settings, store, OllamaEmbedder(settings.embedding), lexical)

    result = retriever.search(args.query, k=args.k)
    print(f"\n{len(result.chunks)} chunks in {result.latency_ms} ms "
          f"(dense {result.dense_n}, lexical {result.lexical_n}, fused {result.fused_n})\n")

    for chunk in result.chunks:
        marker = " [neighbor]" if chunk.is_neighbor else ""
        print(f"— {chunk.source_title} ({chunk.license}){marker}")
        if args.explain:
            print(f"  id={chunk.chunk_id} via={chunk.found_by} "
                  f"dense={chunk.dense_rank} lexical={chunk.lexical_rank} "
                  f"rrf={chunk.score:.6f}")
        body = chunk.text.strip().replace("\n", " ")
        print(f"  {body[:300]}{'...' if len(body) > 300 else ''}\n")

    attributions = {c.license for c in build_citations(result.chunks)}
    if attributions:
        print(f"licenses in play: {sorted(attributions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
