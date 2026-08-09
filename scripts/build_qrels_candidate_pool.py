#!/usr/bin/env python3
"""Build deterministic calibration-only qrels candidate pools.

Stage 3A intentionally requires precomputed arm results. Future Gate 4 may
provide dense/BM25 results from the approved retrieval interfaces; this keeps
the infrastructure testable without executing real evaluation queries early.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from natural_flow_rag.settings import load_settings  # noqa: E402
from scripts.compare_reindex_plan import load_bm25_ids, load_current_records  # noqa: E402

DEFAULT_DENSE_DEPTH = 32
DEFAULT_BM25_DEPTH = 32


def query_sha256(query_text: str) -> str:
    return hashlib.sha256(query_text.encode("utf-8")).hexdigest()


def load_queries(path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    queries = payload.get("queries") if isinstance(payload, dict) else payload
    if not isinstance(queries, list):
        raise ValueError("query manifest must be a list or an object with queries")
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for query in queries:
        if not isinstance(query, dict):
            raise ValueError("query records must be mappings")
        query_id = str(query.get("query_id", query.get("id", ""))).strip()
        if not query_id:
            raise ValueError("query_id is required")
        if query_id in seen:
            raise ValueError(f"duplicate query_id: {query_id}")
        seen.add(query_id)
        split = str(query.get("split", ""))
        if split != "calibration":
            raise ValueError(f"only calibration queries are eligible, got {split!r}")
        query_hash = str(query.get("query_sha256", ""))
        if len(query_hash) != 64 or any(c not in "0123456789abcdef" for c in query_hash):
            raise ValueError(f"query_sha256 is required for {query_id}")
        if (
            query.get("query_text") is not None
            and query_sha256(str(query["query_text"])) != query_hash
        ):
            raise ValueError(f"query_sha256 mismatch for {query_id}")
        result.append(query)
    return sorted(result, key=lambda item: str(item.get("query_id", item.get("id"))))


def build_candidate_pool(
    *,
    query: dict[str, Any],
    dense_results: list[dict[str, Any]],
    bm25_results: list[dict[str, Any]],
    dense_depth: int = DEFAULT_DENSE_DEPTH,
    bm25_depth: int = DEFAULT_BM25_DEPTH,
    all_production_ids: list[str] | None = None,
) -> dict[str, Any]:
    query_id = str(query.get("query_id", query.get("id", "")))
    if all_production_ids is not None:
        candidates = [
            {
                "chunk_id": chunk_id,
                "discovery_arm": "all-production-records",
                "dense_rank": None,
                "dense_score": None,
                "bm25_rank": None,
                "bm25_score": None,
            }
            for chunk_id in sorted(all_production_ids)
        ]
    else:
        by_id: dict[str, dict[str, Any]] = {}
        for arm, results, depth in (
            ("dense", dense_results, dense_depth),
            ("bm25", bm25_results, bm25_depth),
        ):
            for result in results[: max(0, depth)]:
                chunk_id = str(result.get("chunk_id", ""))
                if not chunk_id:
                    raise ValueError(f"{arm} result has no chunk_id")
                item = by_id.setdefault(chunk_id, {"chunk_id": chunk_id})
                item[f"{arm}_rank"] = int(result.get("rank", 0))
                item[f"{arm}_score"] = float(result.get("score", 0.0))
        candidates = []
        for item in by_id.values():
            arms = [arm for arm in ("dense", "bm25") if f"{arm}_rank" in item]
            item["discovery_arm"] = "+".join(arms)
            candidates.append(item)
        candidates.sort(
            key=lambda item: (
                min(item.get("dense_rank", 10**9), item.get("bm25_rank", 10**9)),
                item["chunk_id"],
            )
        )
    return {"query_id": query_id, "split": "calibration", "candidates": candidates}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-manifest", type=Path, required=True)
    parser.add_argument(
        "--arm-results", type=Path, help="Synthetic or future precomputed arm results JSON"
    )
    parser.add_argument("--dense-depth", type=int, default=DEFAULT_DENSE_DEPTH)
    parser.add_argument("--bm25-depth", type=int, default=DEFAULT_BM25_DEPTH)
    parser.add_argument("--all-production-records", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    queries = load_queries(args.query_manifest)
    if not args.arm_results and not args.all_production_records:
        raise SystemExit(
            "Stage 3A requires --arm-results or --all-production-records; "
            "no retrieval is run implicitly"
        )
    arm_payload = (
        json.loads(args.arm_results.read_text(encoding="utf-8")) if args.arm_results else {}
    )
    settings = load_settings()
    records, _ = load_current_records(settings)
    production_ids = sorted(str(record["id"]) for record in records)
    if len(production_ids) != 96 or sorted(load_bm25_ids(settings)) != production_ids:
        raise SystemExit(
            "production execution contract requires exact 96-record Chroma/BM25 parity"
        )
    pools = []
    for query in queries:
        query_id = str(query.get("query_id", query.get("id")))
        arms = arm_payload.get(query_id, {})
        pools.append(
            build_candidate_pool(
                query=query,
                dense_results=arms.get("dense", []),
                bm25_results=arms.get("bm25", []),
                dense_depth=args.dense_depth,
                bm25_depth=args.bm25_depth,
                all_production_ids=production_ids if args.all_production_records else None,
            )
        )
    output = {
        "schema_version": 1,
        "dense_depth": args.dense_depth,
        "bm25_depth": args.bm25_depth,
        "pools": pools,
        "mutation_performed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    main()
