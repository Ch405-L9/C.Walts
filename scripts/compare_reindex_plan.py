#!/usr/bin/env python3
"""Read-only comparison of a proposed source build against production IDs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from natural_flow_rag.lexical_search import LexicalIndex  # noqa: E402
from natural_flow_rag.schemas import ChunkRecord, sha256_text  # noqa: E402
from natural_flow_rag.settings import (  # noqa: E402
    ConfigError,
    Settings,
    load_settings,
    load_sources,
)
from natural_flow_rag.vector_store import VectorStore  # noqa: E402
from scripts.ingest import build_records  # noqa: E402

SCHEMA_VERSION = 1
RELEVANT_METADATA_KEYS = (
    "source_id",
    "source_path",
    "source_title",
    "license",
    "license_url",
    "source_checksum",
    "chunk_index",
    "chunk_total",
    "chunk_profile",
    "embedding_model",
    "embedding_dimension",
    "tokenizer",
    "token_count",
    "section_heading",
    "doc_type",
    "dialect",
    "register",
)


def git_value(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()  # noqa: S603,S607


def finding(
    code: str,
    severity: str,
    message: str,
    *,
    ids: list[str] | None = None,
    source_id: str | None = None,
) -> dict[str, object]:
    out: dict[str, object] = {
        "code": code,
        "severity": severity,
        "message": message,
    }
    if ids is not None:
        out["ids"] = sorted(ids)
    if source_id is not None:
        out["source_id"] = source_id
    return out


def canonical_content_digest(text: str) -> str:
    return sha256_text(text.strip())


def relevant_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: metadata.get(key)
        for key in RELEVANT_METADATA_KEYS
        if metadata.get(key) is not None
    }


def record_payload(record: ChunkRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "text": record.text,
        "metadata": record.metadata(),
    }


def load_proposed_records(
    settings: Settings,
    manifest_path: Path,
    *,
    source_filter: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, object]]]:
    manifest = load_sources(manifest_path)
    root = settings.project_root
    errors: list[dict[str, object]] = []
    source_ids: list[str] = []
    records: list[dict[str, Any]] = []

    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        return [], [], [
            finding(
                "invalid_manifest",
                "ERROR",
                "proposed source config must contain a non-empty sources list",
            )
        ]

    for source in sources:
        source_id = str(source.get("id", ""))
        if source_filter and source_id not in source_filter:
            continue
        source_ids.append(source_id)
        try:
            settings.assert_ingestible_doc_type(source.get("doc_type"), f"source {source_id!r}")
            settings.resolve_ingest_path(source["path"])
        except (ConfigError, KeyError) as exc:
            errors.append(
                finding(
                    "invalid_source_scope",
                    "ERROR",
                    str(exc),
                    source_id=source_id or None,
                )
            )
            continue
        if source.get("license_status") != "approved":
            errors.append(
                finding(
                    "unapproved_source",
                    "ERROR",
                    f"source {source_id!r} has license_status {source.get('license_status')!r}",
                    source_id=source_id,
                )
            )
            continue
        if not str(source.get("license", "")).strip():
            errors.append(
                finding(
                    "missing_license",
                    "ERROR",
                    f"source {source_id!r} has an empty license",
                    source_id=source_id,
                )
            )
            continue
        try:
            built = build_records(settings, source, root)
        except Exception as exc:  # fail closed: bad chunking/id generation is a finding
            errors.append(
                finding(
                    "record_build_failed",
                    "ERROR",
                    f"source {source_id!r} could not be built: {exc}",
                    source_id=source_id,
                )
            )
            continue
        records.extend(record_payload(record) for record in built)

    return records, sorted(set(source_ids)), errors


def load_current_records(settings: Settings) -> tuple[list[dict[str, Any]], int]:
    store = VectorStore(settings)
    collection = store.get()
    payload = collection.get(include=["documents", "metadatas"])
    records = [
        {
            "id": chunk_id,
            "text": document or "",
            "metadata": metadata or {},
        }
        for chunk_id, document, metadata in zip(
            payload["ids"], payload["documents"], payload["metadatas"], strict=True
        )
    ]
    return records, len(records)


def load_bm25_ids(settings: Settings) -> list[str]:
    lexical = LexicalIndex(settings.project_root / "var" / "bm25" / "index.json")
    lexical.load()
    return list(lexical.chunk_ids)


def compare_records(
    *,
    current_records: list[dict[str, Any]],
    proposed_records: list[dict[str, Any]],
    production_bm25_ids: list[str],
    source_scope: list[str],
    repository_commit: str,
    branch: str,
    production_store_identity: dict[str, object],
    proposed_source_identity: dict[str, object],
    allowlisted_source_ids: list[str] | None = None,
    proposed_bm25_ids: list[str] | None = None,
    preload_findings: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    findings = list(preload_findings or [])
    scope = set(source_scope)
    allowlist = set(allowlisted_source_ids or source_scope)

    if not scope:
        findings.append(finding("empty_source_scope", "ERROR", "source scope is empty"))

    proposed_by_id: dict[str, dict[str, Any]] = {}
    current_by_id = {str(record["id"]): record for record in current_records}
    proposed_id_occurrences = Counter(str(record["id"]) for record in proposed_records)
    duplicate_id_groups = {
        chunk_id: [chunk_id] * count
        for chunk_id, count in sorted(proposed_id_occurrences.items())
        if count > 1
    }
    for record in proposed_records:
        proposed_by_id.setdefault(str(record["id"]), record)

    outside_collision_ids = sorted(
        chunk_id
        for chunk_id in proposed_by_id
        if chunk_id in current_by_id
        and current_by_id[chunk_id].get("metadata", {}).get("source_id") not in scope
    )

    proposed_content_by_digest: dict[str, list[str]] = defaultdict(list)
    for record in proposed_records:
        digest = canonical_content_digest(str(record.get("text", "")))
        proposed_content_by_digest[digest].append(str(record["id"]))
    current_content_by_digest: dict[str, list[str]] = defaultdict(list)
    for record in current_records:
        digest = canonical_content_digest(str(record.get("text", "")))
        current_content_by_digest[digest].append(str(record["id"]))

    duplicate_content_groups = {
        digest: sorted(set(ids) | set(current_content_by_digest.get(digest, [])))
        for digest, ids in proposed_content_by_digest.items()
        if len(set(ids) | set(current_content_by_digest.get(digest, []))) > 1
    }

    duplicate_ids = sorted(set(duplicate_id_groups) | set(outside_collision_ids))
    if duplicate_ids:
        findings.append(
            finding("duplicate_ids", "ERROR", "duplicate deterministic ids", ids=duplicate_ids)
        )
    if duplicate_content_groups:
        findings.append(
            finding(
                "duplicate_content",
                "ERROR",
                "duplicate canonical content in proposed build",
                ids=sorted({cid for ids in duplicate_content_groups.values() for cid in ids}),
            )
        )

    current_scope_ids: list[str] = []
    ambiguous_scope_ids: list[str] = []
    for record in current_records:
        metadata = record.get("metadata", {}) or {}
        source_id = metadata.get("source_id")
        if source_id in scope:
            current_scope_ids.append(str(record["id"]))
            if not metadata.get("source_path") or not metadata.get("source_checksum"):
                ambiguous_scope_ids.append(str(record["id"]))

    if ambiguous_scope_ids:
        findings.append(
            finding(
                "ambiguous_stale_scope",
                "ERROR",
                "source-scoped current ids lack ownership metadata",
                ids=ambiguous_scope_ids,
            )
        )

    if outside_collision_ids:
        findings.append(
            finding(
                "non_allowlisted_changes",
                "ERROR",
                "proposed ids collide outside the allowlisted source scope",
                ids=outside_collision_ids,
            )
        )

    proposed_source_ids = {
        str((record.get("metadata") or {}).get("source_id")) for record in proposed_records
    }
    non_allowlisted_sources = sorted(proposed_source_ids - allowlist)
    non_allowlisted_changes = [
        {"source_id": source_id, "reason": "not in allowlisted source scope"}
        for source_id in non_allowlisted_sources
    ]
    if non_allowlisted_changes:
        findings.append(
            finding(
                "non_allowlisted_source",
                "ERROR",
                "proposed source is outside the allowlist",
                source_id=non_allowlisted_sources[0],
            )
        )

    current_scope = set(current_scope_ids)
    proposed_ids = set(proposed_by_id)
    proposed_scope_ids = {
        str(record["id"])
        for record in proposed_records
        if (record.get("metadata") or {}).get("source_id") in scope
    }
    would_add_ids = sorted(proposed_ids - set(current_by_id))
    stale_ids = sorted(current_scope - proposed_scope_ids)
    unchanged_ids: list[str] = []
    content_changed_ids: list[str] = []
    metadata_changed_ids: list[str] = []
    for chunk_id in sorted(current_scope & proposed_scope_ids):
        current = current_by_id[chunk_id]
        proposed = proposed_by_id[chunk_id]
        same_content = canonical_content_digest(str(current.get("text", ""))) == (
            canonical_content_digest(str(proposed.get("text", "")))
        )
        same_metadata = relevant_metadata(current.get("metadata", {}) or {}) == (
            relevant_metadata(proposed.get("metadata", {}) or {})
        )
        if same_content and same_metadata:
            unchanged_ids.append(chunk_id)
        else:
            if not same_content:
                content_changed_ids.append(chunk_id)
            if not same_metadata:
                metadata_changed_ids.append(chunk_id)

    if content_changed_ids:
        findings.append(
            finding(
                "content_changed_ids",
                "ERROR",
                "existing deterministic ids have changed canonical content",
                ids=content_changed_ids,
            )
        )

    if metadata_changed_ids:
        findings.append(
            finding(
                "metadata_changed_ids",
                "ERROR",
                "existing deterministic ids have relevant metadata changes",
                ids=metadata_changed_ids,
            )
        )

    evaluation_case_ids = sorted(
        str(record["id"])
        for record in proposed_records
        if str((record.get("metadata") or {}).get("doc_type")) == "evaluation_case"
    )
    if evaluation_case_ids:
        findings.append(
            finding(
                "evaluation_case_leakage",
                "ERROR",
                "proposed build would add evaluation_case records",
                ids=evaluation_case_ids,
            )
        )

    predicted_ids = (set(current_by_id) - current_scope) | proposed_ids
    proposed_chroma_ids = sorted(predicted_ids)
    proposed_bm25_ids = sorted(
        proposed_bm25_ids if proposed_bm25_ids is not None else predicted_ids
    )
    proposed_id_parity = proposed_chroma_ids == proposed_bm25_ids
    if not proposed_id_parity:
        findings.append(
            finding(
                "proposed_id_parity",
                "ERROR",
                "predicted Chroma and BM25 id sets differ",
            )
        )

    current_bm25_set = set(production_bm25_ids)
    current_store_set = set(current_by_id)
    if current_bm25_set != current_store_set:
        findings.append(
            finding(
                "current_production_parity",
                "ERROR",
                "current production Chroma and BM25 id sets differ",
            )
        )

    verdict = "pass" if not any(f["severity"] == "ERROR" for f in findings) else "fail"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "repository_commit": repository_commit,
        "branch": branch,
        "production_store_identity": production_store_identity,
        "proposed_source_identity": proposed_source_identity,
        "mutation_performed": False,
        "current_production_count": len(current_records),
        "proposed_chunk_count": len(proposed_records),
        "predicted_production_count": len(predicted_ids),
        "would_add_ids": would_add_ids,
        "stale_ids": stale_ids,
        "unchanged_ids": unchanged_ids,
        "duplicate_ids": duplicate_ids,
        "content_changed_ids": content_changed_ids,
        "metadata_changed_ids": metadata_changed_ids,
        "source_scoped_current_ids": sorted(current_scope),
        "source_scoped_proposed_ids": sorted(proposed_scope_ids),
        "duplicate_content_groups": duplicate_content_groups,
        "duplicate_id_groups": duplicate_id_groups,
        "proposed_chroma_ids": proposed_chroma_ids,
        "proposed_bm25_ids": proposed_bm25_ids,
        "proposed_id_parity": proposed_id_parity,
        "evaluation_case_count": len(evaluation_case_ids),
        "non_allowlisted_changes": non_allowlisted_changes,
        "findings": sorted(findings, key=lambda f: (str(f["code"]), str(f.get("source_id", "")))),
        "verdict": verdict,
    }


def run_comparison(args: argparse.Namespace) -> dict[str, Any]:
    settings = load_settings()
    manifest_path = settings.resolve_inside_project(args.proposed_source_config)
    source_filter = set(args.source or []) or None
    proposed_records, source_scope, errors = load_proposed_records(
        settings, manifest_path, source_filter=source_filter
    )
    current_records, current_count = load_current_records(settings)
    bm25_ids = load_bm25_ids(settings)
    allowlisted = list(args.allow_source or source_scope)
    return compare_records(
        current_records=current_records,
        proposed_records=proposed_records,
        production_bm25_ids=bm25_ids,
        source_scope=source_scope,
        repository_commit=git_value(["rev-parse", "HEAD"]),
        branch=git_value(["branch", "--show-current"]),
        production_store_identity={
            "collection": settings.collection.name,
            "persistence_path": str(
                settings.resolve_inside_project(settings.collection.persistence_path)
            ),
            "count": current_count,
        },
        proposed_source_identity={
            "manifest_path": str(manifest_path.relative_to(settings.project_root)),
            "source_ids": source_scope,
        },
        allowlisted_source_ids=allowlisted,
        preload_findings=errors,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposed-source-config", required=True)
    parser.add_argument("--production-store", default="config")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--source", action="append", help="restrict to one proposed source id")
    parser.add_argument("--allow-source", action="append", help="allowlisted source id")
    args = parser.parse_args()
    if args.production_store != "config":
        raise SystemExit("--production-store currently supports only 'config'")
    report = run_comparison(args)
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "reindex comparison: "
        f"verdict={report['verdict']} "
        f"would_add={len(report['would_add_ids'])} "
        f"stale={len(report['stale_ids'])} "
        f"unchanged={len(report['unchanged_ids'])} "
        f"duplicates={len(report['duplicate_ids'])} "
        f"mutation_performed={report['mutation_performed']}"
    )
    print(f"report: {output}")
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
