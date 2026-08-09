#!/usr/bin/env python3
"""Validate future calibration-only qrels records against frozen production IDs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from natural_flow_rag.settings import load_settings  # noqa: E402
from scripts.compare_reindex_plan import load_current_records  # noqa: E402


def validate_queries(queries: list[dict[str, Any]]) -> list[str]:
    findings: list[str] = []
    seen: set[str] = set()
    for query in queries:
        query_id = str(query.get("query_id", query.get("id", "")))
        if not query_id:
            findings.append("query_id_missing")
        if query_id in seen:
            findings.append(f"duplicate_query_id:{query_id}")
        seen.add(query_id)
        if query.get("split") != "calibration":
            findings.append(f"holdout_or_unknown_split:{query_id}")
        query_hash = str(query.get("query_sha256", ""))
        if len(query_hash) != 64:
            findings.append(f"query_sha256_missing:{query_id}")
        elif query.get("query_text") is not None:
            actual = hashlib.sha256(str(query["query_text"]).encode("utf-8")).hexdigest()
            if actual != query_hash:
                findings.append(f"query_sha256_mismatch:{query_id}")
    return findings


def validate_qrels(
    *,
    judgments: list[dict[str, Any]],
    queries: list[dict[str, Any]],
    production_records: list[dict[str, Any]],
    collection_version_identity: str,
) -> dict[str, Any]:
    findings = validate_queries(queries)
    query_by_id = {str(query.get("query_id", query.get("id", ""))): query for query in queries}
    records_by_id = {str(record["id"]): record for record in production_records}
    seen: set[tuple[str, str]] = set()
    schema = json.loads((ROOT / "schemas" / "qrels.schema.json").read_text(encoding="utf-8"))
    for judgment in judgments:
        try:
            jsonschema.validate(judgment, schema)
        except jsonschema.ValidationError as exc:
            findings.append(f"schema:{exc.message}")
        query_id = str(judgment.get("query_id", ""))
        chunk_id = str(judgment.get("chunk_id", ""))
        if query_id not in query_by_id:
            findings.append(f"unknown_query_id:{query_id}")
            continue
        query = query_by_id[query_id]
        if query.get("split") != "calibration":
            findings.append(f"holdout_query_refused:{query_id}")
        if judgment.get("query_sha256") != query.get("query_sha256"):
            findings.append(f"query_sha256_mismatch:{query_id}")
        if judgment.get("collection_version_identity") != collection_version_identity:
            findings.append(f"collection_identity_mismatch:{query_id}")
        key = (query_id, chunk_id)
        if key in seen:
            findings.append(f"duplicate_judgment:{query_id}:{chunk_id}")
        seen.add(key)
        record = records_by_id.get(chunk_id)
        if record is None:
            findings.append(f"unknown_chunk_id:{chunk_id}")
            continue
        metadata = record.get("metadata", {}) or {}
        for field in ("source_id", "source_path", "doc_type"):
            if judgment.get(field) != metadata.get(field):
                findings.append(f"document_provenance_mismatch:{query_id}:{chunk_id}:{field}")
    return {
        "schema_version": 1,
        "judgment_count": len(judgments),
        "query_count": len(queries),
        "holdout_judgment_count": sum(1 for item in judgments if item.get("split") == "holdout"),
        "findings": sorted(set(findings)),
        "mutation_performed": False,
        "verdict": "pass" if not findings else "fail",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-manifest", type=Path, required=True)
    parser.add_argument("--judgments", type=Path, required=True)
    parser.add_argument("--collection-version-identity", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    query_payload = yaml.safe_load(args.query_manifest.read_text(encoding="utf-8"))
    queries = (
        query_payload.get("queries", query_payload)
        if isinstance(query_payload, dict)
        else query_payload
    )
    judgments_payload = json.loads(args.judgments.read_text(encoding="utf-8"))
    judgments = (
        judgments_payload.get("judgments", judgments_payload)
        if isinstance(judgments_payload, dict)
        else judgments_payload
    )
    records, _ = load_current_records(load_settings())
    report = validate_qrels(
        judgments=judgments,
        queries=queries,
        production_records=records,
        collection_version_identity=args.collection_version_identity,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
