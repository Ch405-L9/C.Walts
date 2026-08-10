#!/usr/bin/env python3
"""Stage 8 protocol and Gate 1.2 exit checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROTOCOL = ROOT / "config" / "stage8_dense_coverage_probes.yaml"
TAXONOMY = ROOT / "eval" / "coverage" / "structure-taxonomy.yaml"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_protocol(path: Path = PROTOCOL) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data.get("protocol_id") != "gate1_2-stage8-dense-coverage-v1":
        raise ValueError("protocol_id mismatch")
    if data.get("benchmark_record") or data.get("holdout_record") or data.get("qrels_eligible"):
        raise ValueError("protocol is not diagnostic-only")
    if data.get("tuning_permitted") or data.get("retrieval_k") != 5 or data.get("rounds") != 3:
        raise ValueError("protocol measurement controls changed")
    probes = data.get("probes") or []
    if len(probes) != 4 or len({p["id"] for p in probes}) != 4:
        raise ValueError("protocol must contain four unique probes")
    return data


def load_taxonomy(path: Path = TAXONOMY) -> dict[str, dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {str(row["chunk_id"]): row for row in data["assignments"]}


def classify_result(result: dict, taxonomy: dict[str, dict]) -> dict:
    metadata = result.get("metadata") or {}
    chunk_id = str(result.get("chunk_id", ""))
    row = taxonomy.get(chunk_id, {})
    qualifying = (
        not result.get("is_neighbor", False)
        and metadata.get("doc_type") == "approved_example"
        and row.get("doc_type") == "approved_example"
        and row.get("review_status") == "accepted"
        and bool(row.get("independence_group"))
    )
    return {
        "chunk_id": chunk_id,
        "rank": result.get("rank"),
        "source_id": metadata.get("source_id"),
        "doc_type": metadata.get("doc_type"),
        "cw_id": row.get("cw_id"),
        "category_id": row.get("category_id"),
        "independence_group": row.get("independence_group"),
        "qualifying": qualifying,
    }


def evaluate_round(results: list[list[dict]]) -> dict:
    groups = {r["independence_group"] for probe in results for r in probe if r["qualifying"]}
    primary = [
        next((r["independence_group"] for r in probe if r["qualifying"]), None)
        for probe in results
    ]
    every_probe_has_support = all(
        any(r["qualifying"] for r in probe) for probe in results
    )
    no_evaluation = all(
        not r.get("evaluation_case", False) for probe in results for r in probe
    )
    passed = (
        every_probe_has_support
        and len(groups) >= 2
        and len({g for g in primary if g}) >= 2
        and no_evaluation
    )
    return {
        "passed": passed,
        "qualifying_groups": sorted(groups),
        "primary_qualifying_groups": primary,
        "probe_count": len(results),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-protocol", action="store_true")
    parser.add_argument("--diagnostic-results", type=Path)
    args = parser.parse_args()
    try:
        protocol = load_protocol()
        report = {
            "protocol_sha256": sha256(PROTOCOL),
            "protocol_id": protocol["protocol_id"],
            "verified": True,
        }
        if args.diagnostic_results:
            payload = json.loads(args.diagnostic_results.read_text(encoding="utf-8"))
            report["rounds"] = payload["rounds"]
            report["closure_proven"] = all(r["passed"] for r in payload["rounds"])
        print(json.dumps(report, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"verified": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
