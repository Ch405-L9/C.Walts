#!/usr/bin/env python3
"""Validate Stage 2 public-source provenance without network access."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from natural_flow_rag.settings import ConfigError, load_settings  # noqa: E402

SCHEMA_VERSION = 1
ACCEPTED_LICENSES = ("CC BY 4.0", "CC-BY-4.0", "CC BY 3.0", "CC-BY-3.0", "CC0")
REJECTED_LICENSE_TOKENS = ("ND", "NC", "NON-COMMERCIAL", "NONCOMMERCIAL")
EXCLUSION_FIELDS = (
    "figures_excluded",
    "tables_excluded",
    "captions_excluded",
    "references_excluded",
    "supplementary_files_excluded",
    "embedded_third_party_quotations_excluded",
)


def git_value(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()  # noqa: S603,S607


def finding(
    source_id: str,
    field: str,
    code: str,
    severity: str,
    message: str,
) -> dict[str, str]:
    return {
        "source_id": source_id,
        "field": field,
        "code": code,
        "severity": severity,
        "message": message,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_identifier(record: dict[str, Any]) -> str:
    identifiers = article_identifiers(record)
    return identifiers[0] if identifiers else ""


def article_identifiers(record: dict[str, Any]) -> list[str]:
    out = []
    for key in ("doi", "pmcid", "pmid", "stable_article_identifier"):
        value = str(record.get(key, "")).strip()
        if value:
            out.append(f"{key}:{value.lower()}")
    return out


def normalize_license(value: str) -> str:
    return " ".join(value.replace("-", " ").upper().split())


def resolve_evidence_path(
    *,
    project_root: Path,
    manifest_path: Path,
    candidate: str,
    approved_roots: list[Path],
) -> Path:
    raw = Path(candidate)
    if raw.name == ".env-local" or ".env-local" in raw.parts:
        raise ConfigError("evidence paths must not expose .env-local")
    candidates = [raw]
    if not raw.is_absolute():
        candidates = [manifest_path.parent / raw, project_root / raw]
    for path in candidates:
        resolved = path.resolve()
        if any(resolved.is_relative_to(root.resolve()) for root in approved_roots):
            return resolved
    raise ConfigError(f"path {candidate!r} escapes approved evidence roots")


def validate_manifest(
    manifest_path: Path,
    *,
    project_root: Path | None = None,
    approved_roots: list[Path] | None = None,
    repository_commit: str = "unknown",
) -> dict[str, Any]:
    root = (project_root or Path(__file__).resolve().parents[1]).resolve()
    approved_roots = approved_roots or [
        root / "docs" / "evidence" / "source-snapshots",
        root / "var" / "source-snapshots",
    ]
    manifest_path = manifest_path.resolve()
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    checksum_results: list[dict[str, object]] = []
    evidence_path_checks: list[dict[str, object]] = []

    try:
        if not manifest_path.is_relative_to(root):
            raise ConfigError(f"manifest path {manifest_path} escapes project root {root}")
        payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "repository_commit": repository_commit,
            "manifest_path": str(manifest_path),
            "source_record_count": 0,
            "validated_source_ids": [],
            "accepted_license_allowlist": list(ACCEPTED_LICENSES),
            "errors": [
                finding("", "manifest_path", "manifest_unreadable", "ERROR", str(exc))
            ],
            "warnings": [],
            "checksum_results": [],
            "duplicate_checks": {},
            "evidence_path_checks": [],
            "verdict": "fail",
        }

    records = payload.get("sources")
    if not isinstance(records, list):
        records = []
        errors.append(
            finding("", "sources", "missing_sources", "ERROR", "manifest must contain sources")
        )

    source_ids: list[str] = []
    stable_ids: list[str] = []
    snapshot_metadata: dict[str, list[tuple[str, str, str]]] = defaultdict(list)

    for index, record in enumerate(records):
        source_id = str(record.get("source_id") or record.get("id") or f"<record-{index}>")
        source_ids.append(source_id)
        where = f"sources[{index}]"

        required = (
            "source_id",
            "title",
            "authors",
            "publisher",
            "official_url",
            "license",
            "local_snapshot_path",
            "checksum_algorithm",
            "checksum",
            "source_format",
            "extraction_locator_capability",
            "attribution_text",
        )
        for field in required:
            if not record.get(field):
                errors.append(
                    finding(
                        source_id,
                        field,
                        "missing_required_field",
                        "ERROR",
                        f"{where}.{field} is required",
                    )
                )

        if not (
            record.get("doi")
            or record.get("pmcid")
            or record.get("pmid")
            or record.get("stable_article_identifier")
        ):
            errors.append(
                finding(
                    source_id,
                    "stable_identifier",
                    "missing_stable_identifier",
                    "ERROR",
                    "one of DOI, PMCID, PMID, or stable_article_identifier is required",
                )
            )

        identifiers = article_identifiers(record)
        stable_ids.extend(identifiers)
        stable = identifiers[0] if identifiers else ""

        license_value = str(record.get("license", "")).strip()
        normalized_license = normalize_license(license_value)
        allowlist_normalized = {normalize_license(value) for value in ACCEPTED_LICENSES}
        if not license_value:
            errors.append(
                finding(
                    source_id,
                    "license",
                    "missing_article_license",
                    "ERROR",
                    "article-level license is required",
                )
            )
        elif any(token in normalized_license for token in REJECTED_LICENSE_TOKENS):
            errors.append(
                finding(
                    source_id,
                    "license",
                    "rejected_license",
                    "ERROR",
                    f"license {license_value!r} is incompatible with transformed rewrite use",
                )
            )
        elif normalized_license not in allowlist_normalized:
            errors.append(
                finding(
                    source_id,
                    "license",
                    "unknown_license",
                    "ERROR",
                    f"license {license_value!r} is not in the allowlist",
                )
            )

        if not record.get("license_url") and not record.get("license_evidence_path"):
            errors.append(
                finding(
                    source_id,
                    "license_evidence",
                    "missing_license_evidence",
                    "ERROR",
                    "license_url or license_evidence_path is required",
                )
            )
        if record.get("license_evidence_path"):
            try:
                evidence_path = resolve_evidence_path(
                    project_root=root,
                    manifest_path=manifest_path,
                    candidate=str(record["license_evidence_path"]),
                    approved_roots=approved_roots,
                )
                evidence_exists = evidence_path.is_file()
                evidence_path_checks.append(
                    {
                        "source_id": source_id,
                        "field": "license_evidence_path",
                        "path": str(
                            evidence_path.relative_to(root)
                            if evidence_path.is_relative_to(root)
                            else evidence_path
                        ),
                        "exists": evidence_exists,
                    }
                )
                if not evidence_exists:
                    errors.append(
                        finding(
                            source_id,
                            "license_evidence_path",
                            "missing_evidence_file",
                            "ERROR",
                            f"license evidence does not exist: {evidence_path}",
                        )
                    )
            except ConfigError as exc:
                errors.append(
                    finding(
                        source_id,
                        "license_evidence_path",
                        "evidence_path_outside_roots",
                        "ERROR",
                        str(exc),
                    )
                )

        if str(record.get("permission_basis", "")).lower() == "dataset":
            errors.append(
                finding(
                    source_id,
                    "permission_basis",
                    "dataset_permission_only",
                    "ERROR",
                    "dataset-level permission cannot substitute for article-level rights",
                )
            )

        if str(record.get("transformation_permission", "")).lower() not in {
            "before_after_rewrite",
            "transformation_permitted",
            "permitted",
        }:
            errors.append(
                finding(
                    source_id,
                    "transformation_permission",
                    "missing_transformation_permission",
                    "ERROR",
                    "transformed rewrite permission must be declared",
                )
            )

        for field in EXCLUSION_FIELDS:
            if record.get(field) is not True:
                errors.append(
                    finding(
                        source_id,
                        field,
                        "missing_exclusion_declaration",
                        "ERROR",
                        f"{field} must be true",
                    )
                )

        snapshot_path: Path | None = None
        if record.get("local_snapshot_path"):
            try:
                snapshot_path = resolve_evidence_path(
                    project_root=root,
                    manifest_path=manifest_path,
                    candidate=str(record["local_snapshot_path"]),
                    approved_roots=approved_roots,
                )
                exists = snapshot_path.is_file()
                evidence_path_checks.append(
                    {
                        "source_id": source_id,
                        "field": "local_snapshot_path",
                        "path": str(
                            snapshot_path.relative_to(root)
                            if snapshot_path.is_relative_to(root)
                            else snapshot_path
                        ),
                        "exists": exists,
                    }
                )
                if not exists:
                    errors.append(
                        finding(
                            source_id,
                            "local_snapshot_path",
                            "missing_snapshot",
                            "ERROR",
                            f"snapshot does not exist: {snapshot_path}",
                        )
                    )
            except ConfigError as exc:
                errors.append(
                    finding(
                        source_id,
                        "local_snapshot_path",
                        "evidence_path_outside_roots",
                        "ERROR",
                        str(exc),
                    )
                )

        checksum_algorithm = str(record.get("checksum_algorithm", "")).lower()
        expected_checksum = str(record.get("checksum", "")).lower()
        if checksum_algorithm and checksum_algorithm != "sha256":
            errors.append(
                finding(
                    source_id,
                    "checksum_algorithm",
                    "unsupported_checksum_algorithm",
                    "ERROR",
                    "only sha256 is supported",
                )
            )
        if snapshot_path and snapshot_path.is_file() and expected_checksum:
            actual = sha256_file(snapshot_path)
            match = actual == expected_checksum
            checksum_results.append(
                {
                    "source_id": source_id,
                    "algorithm": "sha256",
                    "expected": expected_checksum,
                    "actual": actual,
                    "match": match,
                }
            )
            if not match:
                errors.append(
                    finding(
                        source_id,
                        "checksum",
                        "checksum_mismatch",
                        "ERROR",
                        "snapshot checksum does not match",
                    )
                )

        if snapshot_path:
            snapshot_key = str(snapshot_path)
            snapshot_metadata[snapshot_key].append((source_id, stable, license_value))

        if not record.get("access_date") and not record.get("license_verified_on"):
            warnings.append(
                finding(
                    source_id,
                    "access_date",
                    "missing_verification_date",
                    "WARN",
                    "access_date or license_verified_on is recommended",
                )
            )

    duplicate_checks: dict[str, object] = {}
    for field_name, values in (
        ("source_id", source_ids),
        ("stable_identifier", stable_ids),
    ):
        duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
        duplicate_checks[field_name] = duplicates
        for value in duplicates:
            errors.append(
                finding(
                    value,
                    field_name,
                    f"duplicate_{field_name}",
                    "ERROR",
                    f"duplicate {field_name}: {value}",
                )
            )

    conflicting_identifiers = []
    by_stable: dict[str, set[str]] = defaultdict(set)
    by_stable_checksum: dict[str, set[str]] = defaultdict(set)
    for record in records:
        for stable in article_identifiers(record):
            by_stable[stable].add(str(record.get("license", "")))
            by_stable_checksum[stable].add(str(record.get("checksum", "")))
    for stable, licenses in sorted(by_stable.items()):
        if len(licenses) > 1:
            conflicting_identifiers.append(stable)
            errors.append(
                finding(
                    stable,
                    "license",
                    "conflicting_license_records",
                    "ERROR",
                    "same article has conflicting licenses",
                )
            )
    for stable, checksums in sorted(by_stable_checksum.items()):
        if len(checksums) > 1:
            errors.append(
                finding(
                    stable,
                    "checksum",
                    "conflicting_checksum_records",
                    "ERROR",
                    "same article has conflicting checksums",
                )
            )

    reused_snapshots = {
        path: rows
        for path, rows in sorted(snapshot_metadata.items())
        if len({(stable, license_value) for _, stable, license_value in rows}) > 1
    }
    for path in reused_snapshots:
        errors.append(
            finding(
                path,
                "local_snapshot_path",
                "snapshot_reused_inconsistent_metadata",
                "ERROR",
                "snapshot reused under inconsistent metadata",
            )
        )
    duplicate_checks["conflicting_stable_identifiers"] = conflicting_identifiers
    duplicate_checks["snapshot_reused_inconsistent_metadata"] = sorted(reused_snapshots)

    errors = sorted(errors, key=lambda item: (item["source_id"], item["field"], item["code"]))
    warnings = sorted(warnings, key=lambda item: (item["source_id"], item["field"], item["code"]))
    verdict = "pass" if not errors else "fail"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "repository_commit": repository_commit,
        "manifest_path": str(
            manifest_path.relative_to(root)
            if manifest_path.is_relative_to(root)
            else manifest_path
        ),
        "source_record_count": len(records),
        "validated_source_ids": sorted(source_ids),
        "accepted_license_allowlist": list(ACCEPTED_LICENSES),
        "errors": errors,
        "warnings": warnings,
        "checksum_results": sorted(checksum_results, key=lambda row: str(row["source_id"])),
        "duplicate_checks": duplicate_checks,
        "evidence_path_checks": sorted(evidence_path_checks, key=lambda row: str(row["source_id"])),
        "verdict": verdict,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument(
        "--approved-root",
        action="append",
        help="approved local root for snapshots and license evidence; repeatable",
    )
    args = parser.parse_args()
    settings = load_settings()
    approved_roots = (
        [settings.resolve_inside_project(root) for root in args.approved_root]
        if args.approved_root
        else None
    )
    report = validate_manifest(
        settings.resolve_inside_project(args.manifest),
        project_root=settings.project_root,
        approved_roots=approved_roots,
        repository_commit=git_value(["rev-parse", "HEAD"]),
    )
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "stage2 source validation: "
        f"verdict={report['verdict']} "
        f"sources={report['source_record_count']} "
        f"errors={len(report['errors'])} "
        f"warnings={len(report['warnings'])}"
    )
    print(f"report: {output}")
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
