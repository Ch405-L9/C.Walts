#!/usr/bin/env python3
"""Create and validate an isolated Stage 8 rollback rehearsal.

The live store is never replaced. The existing whole-store snapshot creator is
used for the backup; this helper copies its verified files into a temporary
project-contained root and opens Chroma/BM25 there.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from natural_flow_rag.embeddings import OllamaEmbedder  # noqa: E402
from natural_flow_rag.lexical_search import LexicalIndex  # noqa: E402
from natural_flow_rag.retrieval import Retriever  # noqa: E402
from natural_flow_rag.settings import load_settings  # noqa: E402
from natural_flow_rag.vector_store import VectorStore  # noqa: E402

EXPECTED_ID_SHA = "da637c728f8ef7603b6cb5977401ed6d013187ed7a85173f9d4eb70203cf0a03"
EXPECTED_SEMANTIC = "60910f5bbb1c8ab0328a0129e80ec740275f9f55c2d9bd95dbae9ad7f66cb83f"
EXPECTED_COUNT = 96
FEEDBACK = "badgr_natural_flow_feedback_v1"


def id_sha(ids: set[str]) -> str:
    return hashlib.sha256((json.dumps(sorted(ids), indent=2) + "\n").encode()).hexdigest()


def copy_snapshot(snapshot: Path, root: Path) -> tuple[Path, Path]:
    chroma = root / "restored" / "chroma"
    bm25 = root / "restored" / "bm25" / "index.json"
    chroma.parent.mkdir(parents=True)
    shutil.copytree(snapshot / "chroma", chroma)
    bm25.parent.mkdir(parents=True)
    shutil.copy2(snapshot / "bm25-index.json", bm25)
    return chroma, bm25


def _settings(root: Path, chroma: Path):
    raw = yaml.safe_load((ROOT / "config" / "rag.yaml").read_text(encoding="utf-8"))
    raw["collection"]["persistence_path"] = str(chroma.relative_to(ROOT))
    config = root / "temporary-rag.yaml"
    config.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return load_settings(config)


def rehearse(snapshot: Path, keep: bool = False) -> dict[str, object]:
    root = Path(tempfile.mkdtemp(prefix="stage8-", dir=ROOT / "var" / "stage8_rehearsal"))
    try:
        chroma, bm25_path = copy_snapshot(snapshot, root)
        settings = _settings(root, chroma)
        store = VectorStore(settings)
        collection = store.get()
        records = collection.get(include=["metadatas"])
        ids = set(records["ids"])
        bm25 = LexicalIndex(bm25_path)
        bm25.load()
        bm25_ids = set(bm25.chunk_ids)
        embedder = OllamaEmbedder(settings.embedding)
        retriever = Retriever(settings, store, embedder, bm25)
        lexical_hits = len(bm25.search("ToBI", 3))
        hybrid = retriever.search("How should a technical warning be paced when read aloud", k=5)
        dense = retriever._dense("How should a technical warning be paced when read aloud", 5, None)
        forbidden = sum(
            1
            for m in records["metadatas"]
            if (m or {}).get("doc_type") == "evaluation_case"
        )
        feedback = store.client.get_collection(FEEDBACK).count()
        report = {
            "snapshot": str(snapshot.relative_to(ROOT)),
            "root": str(root.relative_to(ROOT)),
            "chroma_count": collection.count(),
            "feedback_count": feedback,
            "bm25_count": len(bm25_ids),
            "exact_parity": ids == bm25_ids,
            "id_sha256": id_sha(ids),
            "semantic_digest": None,
            "evaluation_case_count": forbidden,
            "dense_hits": len(dense.get("ids", [[]])[0]),
            "lexical_hits": lexical_hits,
            "hybrid_hits": len(hybrid.chunks),
            "dense_arm_participated": bool(dense.get("ids", [[]])[0]),
            "lexical_arm_participated": hybrid.lexical_error is None and hybrid.lexical_n > 0,
            "hybrid_provenance": all(c.metadata.get("source_id") for c in hybrid.chunks),
        }
        # The accepted semantic digest is independently checked by the existing
        # source/restore verifier; this rehearsal reports its identity fields.
        report["pass"] = all([
            report["chroma_count"] == EXPECTED_COUNT,
            report["feedback_count"] == 2,
            report["bm25_count"] == EXPECTED_COUNT,
            report["exact_parity"],
            report["id_sha256"] == EXPECTED_ID_SHA,
            report["evaluation_case_count"] == 0,
            report["dense_hits"] > 0,
            report["lexical_hits"] > 0,
            report["hybrid_hits"] > 0,
            report["dense_arm_participated"],
            report["lexical_arm_participated"],
            report["hybrid_provenance"],
        ])
        if not keep:
            shutil.rmtree(root)
            report["cleanup"] = not root.exists()
        else:
            report["cleanup"] = False
        return report
    except Exception:
        if not keep and root.exists():
            shutil.rmtree(root)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(rehearse(args.snapshot.resolve(), args.keep), indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"pass": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
