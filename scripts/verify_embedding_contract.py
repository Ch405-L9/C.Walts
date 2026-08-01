#!/usr/bin/env python3
"""Prove the explicit nomic-embed-text contract in a DISPOSABLE collection.

Prompt C §8.1. Nothing here touches `badgr_natural_flow_v1` or any production
store: the probe uses its own PersistentClient rooted at `var/tmp/contract-probe/`,
which is deleted after the evidence is recorded.

What is proven, and why each check exists:

  1. dimension is 768 through the real client (not a curl of the raw API);
  2. the persisted collection schema records `nomic-embed-text`, NOT Chroma's
     384-dimension default embedder — this is audit hazard B2, the reason the
     production collections `badgr_corpus` and `job_opportunities` are unsafe to
     query with `query_texts=`;
  3. `query_texts=` and an explicit query embedding return the same neighbour,
     i.e. the recorded function is genuinely the same model the vectors came from;
  4. no ONNX fallback model is downloaded or invoked (Chroma's default embedder
     fetches MiniLM on first use; its cache must stay absent/unchanged);
  5. persistence stays inside the project root.

Evidence is written to docs/evidence/embedding-contract.json.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from natural_flow_rag.embeddings import OllamaEmbedder  # noqa: E402
from natural_flow_rag.settings import load_settings  # noqa: E402

ONNX_CACHE = Path.home() / ".cache" / "chroma" / "onnx_models"

PROBE_DOCS = [
    "Pace the line by meaning, not by punctuation. One main thought per breath group.",
    "The service account impersonates a specific user; access is bounded by OAuth scopes.",
    "Reflective narration can carry more space between clauses without becoming slow.",
]


def onnx_state() -> dict:
    if not ONNX_CACHE.exists():
        return {"present": False, "files": 0, "bytes": 0}
    files = [p for p in ONNX_CACHE.rglob("*") if p.is_file()]
    return {"present": True, "files": len(files), "bytes": sum(p.stat().st_size for p in files)}


def sqlite_schema(db_path: Path, collection_name: str) -> dict:
    """Read-only inspection — the Chroma API is not the only witness."""
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = sorted(row[0] for row in cursor.fetchall())

        cursor.execute("PRAGMA table_info(collections)")
        columns = [row[1] for row in cursor.fetchall()]

        # chromadb 1.5.8 keeps the embedding-function record in `schema_str`;
        # `config_json_str` is "{}" for collections created through this path.
        wanted = [
            c for c in ("id", "name", "dimension", "config_json_str", "schema_str")
            if c in columns
        ]
        # S608: the column list is the intersection of a hardcoded tuple with
        # PRAGMA output, so no caller-supplied text reaches the statement; the
        # only value is bound. SQLite cannot parameterize column names.
        cursor.execute(
            f"SELECT {', '.join(wanted)} FROM collections WHERE name = ?",  # noqa: S608
            (collection_name,),
        )
        row = cursor.fetchone()
        record = dict(zip(wanted, row, strict=False)) if row else {}

        segments = []
        if "segments" in tables:
            cursor.execute("PRAGMA table_info(segments)")
            seg_cols = [r[1] for r in cursor.fetchall()]
            if "collection" in seg_cols and "id" in record:
                pick = [c for c in ("scope", "type") if c in seg_cols]
                cursor.execute(
                    f"SELECT {', '.join(pick)} FROM segments WHERE collection = ?",  # noqa: S608
                    (record["id"],),
                )
                segments = [dict(zip(pick, r, strict=False)) for r in cursor.fetchall()]

        return {"tables": tables, "collection_row": record, "segments": segments}
    finally:
        connection.close()


def main() -> int:
    settings = load_settings()
    root = settings.project_root
    probe_root = settings.resolve_inside_project(Path("var/tmp/contract-probe"))
    name = "nfr_contract_probe"

    if probe_root.exists():
        shutil.rmtree(probe_root)
    probe_root.mkdir(parents=True, exist_ok=True)

    onnx_before = onnx_state()
    evidence: dict = {
        "generated": datetime.now(UTC).isoformat(),
        "probe_collection": name,
        "probe_persistence": str(probe_root),
        "inside_project_root": probe_root.is_relative_to(root.resolve()),
        "configured_model": settings.embedding.model,
        "configured_dimension": settings.embedding.vector_dimension,
        "onnx_cache_before": onnx_before,
        "checks": {},
    }

    # ── 1. dimension through the project's own client ─────────────────────────
    embedder = OllamaEmbedder(settings.embedding)
    result = embedder.probe()
    evidence["measured"] = {
        "dimension": result.dimension,
        "l2_norm": round(result.l2_norm, 6),
        "model": result.model,
        "prenormalized": result.normalized,
    }
    evidence["checks"]["dimension_is_768"] = result.dimension == 768

    # ── 2. create the disposable collection with the explicit function ────────
    import chromadb
    from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

    embedding_function = OllamaEmbeddingFunction(
        url=settings.embedding.endpoint,
        model_name=settings.embedding.model,
        timeout=settings.embedding.timeout_seconds,
    )
    client = chromadb.PersistentClient(path=str(probe_root))
    collection = client.create_collection(
        name=name,
        embedding_function=embedding_function,
        configuration={"hnsw": {"space": settings.collection.space}},
    )

    vectors = embedder.embed(PROBE_DOCS)
    collection.add(
        ids=[f"probe_{i}" for i in range(len(PROBE_DOCS))],
        embeddings=vectors,
        documents=PROBE_DOCS,
        metadatas=[{"probe": True} for _ in PROBE_DOCS],
    )
    evidence["checks"]["explicit_vectors_accepted"] = collection.count() == len(PROBE_DOCS)
    evidence["stored_vector_dimension"] = len(
        collection.get(ids=["probe_0"], include=["embeddings"])["embeddings"][0]
    )
    evidence["checks"]["stored_dimension_is_768"] = evidence["stored_vector_dimension"] == 768

    # ── 3. query_texts vs explicit embedding must agree ───────────────────────
    query = "how should a technical warning be paced when read aloud"
    by_text = collection.query(query_texts=[query], n_results=1)
    by_vector = collection.query(query_embeddings=[embedder.embed_one(query)], n_results=1)
    evidence["query_texts_top_id"] = by_text["ids"][0][0]
    evidence["query_vector_top_id"] = by_vector["ids"][0][0]
    evidence["query_texts_distance"] = round(float(by_text["distances"][0][0]), 6)
    evidence["query_vector_distance"] = round(float(by_vector["distances"][0][0]), 6)
    evidence["checks"]["query_paths_agree"] = (
        by_text["ids"][0][0] == by_vector["ids"][0][0]
        and abs(by_text["distances"][0][0] - by_vector["distances"][0][0]) < 1e-4
    )

    # ── 4. schema records the real model, not Chroma's default ────────────────
    schema = sqlite_schema(probe_root / "chroma.sqlite3", name)
    evidence["sqlite"] = schema
    row = schema.get("collection_row", {})
    config_blob = json.dumps(
        {"config": row.get("config_json_str"), "schema": row.get("schema_str")}
    )
    api_config = {}
    try:
        api_config = embedding_function.get_config()
    except Exception as exc:  # noqa: BLE001 — evidence, not control flow
        api_config = {"error": type(exc).__name__, "detail": str(exc)}
    evidence["embedding_function_config"] = api_config
    evidence["checks"]["schema_names_nomic"] = "nomic-embed-text" in config_blob
    evidence["checks"]["schema_is_not_chroma_default"] = not any(
        marker in config_blob.lower()
        for marker in ("default_embedding_function", "all-minilm", "onnxmini")
    )
    declared_dimension = schema.get("collection_row", {}).get("dimension")
    evidence["schema_declared_dimension"] = declared_dimension
    evidence["checks"]["schema_dimension_is_768"] = declared_dimension in (768, None)

    # ── 4b. a caller who FORGETS the embedding function must not get 384-d ────
    # This is hazard B2 restated as an experiment: reopen the collection with no
    # embedding_function argument at all — the exact mistake that made the
    # production collections unsafe — and confirm the persisted schema still
    # drives the query.
    del client
    reopened_client = chromadb.PersistentClient(path=str(probe_root))
    reopened = reopened_client.get_collection(name=name)
    naive = reopened.query(query_texts=[query], n_results=1)
    evidence["reopened_without_ef"] = {
        "top_id": naive["ids"][0][0],
        "distance": round(float(naive["distances"][0][0]), 6),
        "python_side_function": type(getattr(reopened, "_embedding_function", None)).__name__,
    }
    evidence["checks"]["reopen_without_ef_matches"] = (
        naive["ids"][0][0] == by_text["ids"][0][0]
        and abs(naive["distances"][0][0] - by_text["distances"][0][0]) < 1e-6
    )
    del reopened_client
    client = chromadb.PersistentClient(path=str(probe_root))

    # ── 5. no ONNX fallback was pulled ────────────────────────────────────────
    onnx_after = onnx_state()
    evidence["onnx_cache_after"] = onnx_after
    evidence["checks"]["no_onnx_fallback"] = onnx_after == onnx_before

    evidence["checks"]["persistence_inside_project"] = evidence["inside_project_root"]
    evidence["passed"] = all(evidence["checks"].values())

    # ── teardown: the disposable collection leaves nothing behind ─────────────
    client.delete_collection(name)
    del client
    shutil.rmtree(probe_root, ignore_errors=True)
    evidence["probe_removed"] = not probe_root.exists()

    out = root / "docs" / "evidence" / "embedding-contract.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    width = max(len(k) for k in evidence["checks"])
    print(f"\nembedding contract probe — {settings.embedding.model}\n")
    for check, ok in evidence["checks"].items():
        print(f"  {'PASS' if ok else 'FAIL'}  {check:<{width}}")
    print(f"\n  measured dimension: {result.dimension}   L2 norm: {result.l2_norm:.6f}")
    print(f"  evidence: {out.relative_to(root)}")
    print(f"\n{'CONTRACT PROVEN' if evidence['passed'] else 'CONTRACT NOT PROVEN'}\n")
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
