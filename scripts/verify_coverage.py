#!/usr/bin/env python3
"""Verify a deterministic, one-dimensional coverage taxonomy for production."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from natural_flow_rag.settings import load_settings  # noqa: E402
from scripts.compare_reindex_plan import load_bm25_ids, load_current_records  # noqa: E402

SCHEMA_VERSION = 1


def id_list_sha256(ids: list[str]) -> str:
    payload = json.dumps(sorted(ids), indent=2) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def git_value(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()  # noqa: S603,S607


def smoke_bucket(count: int) -> str:
    return ">=3" if count >= 3 else str(count)


def assignment_key(assignment: dict[str, Any]) -> str:
    return str(assignment.get("chunk_id", ""))


def _category_report(
    category: dict[str, Any],
    assignments: list[dict[str, Any]],
    records_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    chunk_ids = sorted(assignment_key(item) for item in assignments)
    independence_groups = {str(item["independence_group"]) for item in assignments}
    source_ids = sorted({str(item["source_id"]) for item in assignments})
    cw_ids = sorted(
        {
            str(records_by_id[chunk_id]["metadata"].get("cw_id"))
            for chunk_id in chunk_ids
            if chunk_id in records_by_id and records_by_id[chunk_id]["metadata"].get("cw_id")
        }
        | {str(item["cw_id"]) for item in assignments if item.get("cw_id")}
    )
    count = len(independence_groups)
    return {
        "category_id": str(category["category_id"]),
        "category_name": str(category["name"]),
        "record_count": len(chunk_ids),
        "independent_example_count": count,
        "source_count": len(source_ids),
        "chunk_ids": chunk_ids,
        "cw_ids": cw_ids,
        "source_ids": source_ids,
        "smoke_floor_bucket": smoke_bucket(count),
        "smoke_floor_label": "smoke_test_floor" if count >= 3 else None,
        "caveat_text": str(category.get("caveat_text", "Counts are descriptive only.")),
    }


def build_report(
    *,
    records: list[dict[str, Any]],
    bm25_ids: list[str],
    taxonomy: dict[str, Any],
    expected_count: int,
    expected_id_list_sha256: str,
    evaluation_case_count: int = 0,
    branch: str = "unknown",
    commit: str = "unknown",
    version: str = "unknown",
    generated_at: str | None = None,
) -> dict[str, Any]:
    chroma_ids = sorted(str(record["id"]) for record in records)
    assignments = taxonomy.get("assignments") if isinstance(taxonomy, dict) else None
    categories = taxonomy.get("categories") if isinstance(taxonomy, dict) else None
    assignments = assignments if isinstance(assignments, list) else []
    categories = categories if isinstance(categories, list) else []
    by_id = Counter(assignment_key(item) for item in assignments)
    duplicate_ids = sorted(chunk_id for chunk_id, count in by_id.items() if count > 1)
    unknown_ids = sorted(set(by_id) - set(chroma_ids))
    missing_ids = sorted(set(chroma_ids) - set(by_id))
    records_by_id = {str(record["id"]): record for record in records}
    category_by_id = {str(category.get("category_id")): category for category in categories}
    category_assignments: dict[str, list[dict[str, Any]]] = {
        category_id: [] for category_id in sorted(category_by_id)
    }
    findings: list[str] = []
    for item in assignments:
        category_id = str(item.get("category_id", ""))
        chunk_id = assignment_key(item)
        if category_id not in category_by_id:
            findings.append(f"unknown_category:{category_id}")
        else:
            category_assignments[category_id].append(item)
        if chunk_id in records_by_id:
            metadata = records_by_id[chunk_id].get("metadata", {}) or {}
            if str(item.get("source_id", "")) != str(metadata.get("source_id", "")):
                findings.append(f"source_mismatch:{chunk_id}")
        if item.get("review_status") == "review_required":
            findings.append(f"review_required:{chunk_id}")

    category_reports = [
        _category_report(
            category_by_id[category_id], category_assignments[category_id], records_by_id
        )
        for category_id in sorted(category_by_id)
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "branch": branch,
        "commit": commit,
        "version": version,
        "expected_production_count": expected_count,
        "measured_chroma_count": len(chroma_ids),
        "measured_bm25_count": len(bm25_ids),
        "exact_parity": chroma_ids == sorted(str(item) for item in bm25_ids),
        "production_id_list_sha256": id_list_sha256(chroma_ids),
        "expected_id_list_sha256": expected_id_list_sha256,
        "evaluation_case_count": evaluation_case_count,
        "category_count": len(category_reports),
        "categorized_record_count": len(assignments) - len(duplicate_ids),
        "review_required_count": sum(
            1 for item in assignments if item.get("review_status") == "review_required"
        ),
        "categories": category_reports,
        "uncategorized_ids": missing_ids,
        "duplicate_assignment_ids": duplicate_ids,
        "unknown_assignment_ids": unknown_ids,
        "findings": sorted(set(findings)),
        "mutation_performed": False,
    }
    report["verdict"] = (
        "pass"
        if (
            expected_count == len(chroma_ids) == len(bm25_ids)
            and report["exact_parity"]
            and report["production_id_list_sha256"] == expected_id_list_sha256
            and evaluation_case_count == 0
            and not missing_ids
            and not duplicate_ids
            and not unknown_ids
            and not report["findings"]
        )
        else "fail"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument("--expected-id-list-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = load_settings()
    records, _ = load_current_records(settings)
    bm25_ids = load_bm25_ids(settings)
    taxonomy = yaml.safe_load(args.taxonomy.read_text(encoding="utf-8")) or {}
    evaluation_count = sum(
        1 for record in records if record.get("metadata", {}).get("doc_type") == "evaluation_case"
    )
    report = build_report(
        records=records,
        bm25_ids=bm25_ids,
        taxonomy=taxonomy,
        expected_count=args.expected_count,
        expected_id_list_sha256=args.expected_id_list_sha256,
        evaluation_case_count=evaluation_count,
        branch=git_value(["branch", "--show-current"]),
        commit=git_value(["rev-parse", "HEAD"]),
        version=__import__("natural_flow_rag").__version__,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
