#!/usr/bin/env python3
"""Validate Stage 2 candidate passages against preserved source snapshots."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from natural_flow_rag.chunking import count_tokens  # noqa: E402
from natural_flow_rag.schemas import sha256_text  # noqa: E402
from natural_flow_rag.settings import ConfigError, load_settings  # noqa: E402
from scripts.validate_stage2_sources import (  # noqa: E402
    resolve_evidence_path,
    sha256_file,
)

SCHEMA_VERSION = 1
EXPECTED_IDS = tuple(f"ST2-CAND-{index:03d}" for index in range(1, 13))
EXPECTED_ALLOCATION = {
    "dense": 4,
    "procedural": 2,
    "numeric": 2,
    "identifier_date": 2,
    "technical_status": 2,
}
PASSAGE_NORMALIZATION = "jats_body_text_without_bibr_xrefs_whitespace_collapse"
ARRAY_FIELDS = (
    "protected_facts",
    "protected_terminology",
    "protected_numbers_units",
    "protected_dates",
    "protected_identifiers_version_strings",
    "protected_negation",
    "protected_obligation_modality",
    "protected_certainty_uncertainty",
    "protected_conditions_exceptions_scope_limits",
    "factual_preservation_review_criteria",
    "spoken_delivery_review_criteria",
    "status_update_evidence",
)
FORBIDDEN_REWRITE_FIELDS = {
    "final_rewrite",
    "target_text",
    "rewrite",
    "rewritten_text",
    "before_text",
    "after_text",
}
FORBIDDEN_TEXT_MARKERS = ("EVAL-009", "holdout")


def git_value(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()  # noqa: S603,S607


def finding(
    candidate_id: str,
    field: str,
    code: str,
    severity: str,
    message: str,
) -> dict[str, str]:
    return {
        "candidate_id": candidate_id,
        "field": field,
        "code": code,
        "severity": severity,
        "message": message,
    }


def stable_source_identifiers(record: dict[str, Any]) -> list[str]:
    identifiers = []
    for key in ("doi", "pmcid", "pmid", "stable_article_identifier"):
        value = str(record.get(key, "")).strip()
        if value:
            identifiers.append(f"{key}:{value.lower()}")
    return identifiers


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    records = []
    errors = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        return [], [finding("", "candidates", "candidate_file_unreadable", "ERROR", str(exc))]
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(
                finding(
                    f"<line-{line_number}>",
                    "jsonl",
                    "invalid_jsonl_record",
                    "ERROR",
                    str(exc),
                )
            )
            continue
        if isinstance(record, dict):
            records.append(record)
        else:
            errors.append(
                finding(
                    f"<line-{line_number}>",
                    "jsonl",
                    "candidate_record_not_object",
                    "ERROR",
                    "each JSONL row must be an object",
                )
            )
    return records, errors


def string_values(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from string_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from string_values(child)


def load_manifest_sources(
    manifest_path: Path,
    *,
    project_root: Path,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    try:
        payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return {}, [finding("", "manifest", "manifest_unreadable", "ERROR", str(exc))]
    records = payload.get("sources")
    if not isinstance(records, list):
        return {}, [
            finding(
                "",
                "manifest.sources",
                "manifest_missing_sources",
                "ERROR",
                "sources must be a list",
            )
        ]
    by_id: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    for record in records:
        source_id = str(record.get("source_id", "")).strip()
        if not source_id:
            errors.append(
                finding(
                    "",
                    "source_id",
                    "manifest_source_missing_id",
                    "ERROR",
                    "source_id is required",
                )
            )
            continue
        if source_id in by_id:
            errors.append(
                finding(
                    "",
                    "source_id",
                    "manifest_duplicate_source_id",
                    "ERROR",
                    f"duplicate source_id {source_id}",
                )
            )
        by_id[source_id] = record
    for source_id, record in by_id.items():
        path = str(record.get("local_snapshot_path", ""))
        if path.startswith("var/"):
            errors.append(
                finding(
                    "",
                    "local_snapshot_path",
                    "manifest_uses_unpromoted_snapshot",
                    "ERROR",
                    f"{source_id} points to local-only path {path}",
                )
            )
        if not (Path(path).is_absolute() or (project_root / path).is_file()):
            errors.append(
                finding(
                    "",
                    "local_snapshot_path",
                    "manifest_snapshot_missing",
                    "ERROR",
                    f"{source_id} snapshot does not exist: {path}",
                )
            )
    return by_id, errors


def xml_text_without_bibr_xrefs(element: ET.Element) -> str:
    pieces: list[str] = []

    def walk(node: ET.Element) -> None:
        if node.tag.endswith("xref") and node.attrib.get("ref-type") == "bibr":
            if node.tail:
                pieces.append(node.tail)
            return
        if node.text:
            pieces.append(node.text)
        for child in list(node):
            walk(child)
        if node.tail:
            pieces.append(node.tail)

    walk(element)
    return collapse_whitespace("".join(pieces))


def collapse_whitespace(text: str) -> str:
    return " ".join(text.split())


def split_sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(])", text)
        if sentence.strip()
    ]


def section_title(section: ET.Element) -> str:
    title = section.find("./title")
    return xml_text_without_bibr_xrefs(title) if title is not None else ""


def iter_sections(parent: ET.Element, path: list[str] | None = None):
    path = path or []
    for section in parent.findall("./sec"):
        title = section_title(section)
        current = [*path, title] if title else path
        yield section, current
        yield from iter_sections(section, current)


def matching_sections(
    body: ET.Element,
    exact_section: str,
    subsection: str,
) -> list[tuple[ET.Element, str]]:
    if exact_section == "Article body opening section":
        return [(body, "body")]
    matches = []
    for section, path in iter_sections(body):
        joined = " > ".join(path)
        exact_matches = not exact_section or exact_section in joined or joined in exact_section
        subsection_matches = not subsection or subsection in joined
        if exact_matches and subsection_matches:
            matches.append((section, joined))
    return matches


def ordinal(value: object, field: str) -> int:
    if isinstance(value, int):
        return value
    raw = str(value)
    if "-" in raw and field == "sentence_ordinal":
        raw = raw.split("-", 1)[0]
    return int(raw)


def sentence_span(value: object) -> tuple[int, int]:
    if isinstance(value, int):
        return value, value
    raw = str(value)
    if "-" in raw:
        start, end = raw.split("-", 1)
        return int(start), int(end)
    number = int(raw)
    return number, number


def parse_xml_snapshot(path: Path) -> ET.Element:
    # Some PMC snapshots contain an undeclared nbsp entity; this is XML parsing
    # hygiene, not source-passage normalization.
    return ET.fromstring(path.read_text(encoding="utf-8").replace("&nbsp;", " "))  # noqa: S314


def resolve_passage(
    *,
    snapshot_path: Path,
    exact_section: str,
    subsection: str,
    paragraph_ordinal: object,
    sentence_ordinal: object,
) -> tuple[str | None, str | None]:
    root = parse_xml_snapshot(snapshot_path)
    body = root.find(".//body")
    if body is None:
        return None, None
    candidates = matching_sections(body, exact_section, subsection)
    paragraph_index = ordinal(paragraph_ordinal, "paragraph_ordinal") - 1
    sentence_start, sentence_end = sentence_span(sentence_ordinal)
    for section, section_path in candidates:
        paragraphs = section.findall("./p")
        if paragraph_index < 0 or paragraph_index >= len(paragraphs):
            continue
        sentences = split_sentences(xml_text_without_bibr_xrefs(paragraphs[paragraph_index]))
        if sentence_start < 1 or sentence_end > len(sentences) or sentence_start > sentence_end:
            continue
        return " ".join(sentences[sentence_start - 1 : sentence_end]), section_path
    return None, None


def validate_candidates(
    candidates_path: Path,
    manifest_path: Path,
    *,
    project_root: Path | None = None,
    approved_roots: list[Path] | None = None,
    repository_commit: str = "unknown",
) -> dict[str, Any]:
    root = (project_root or Path(__file__).resolve().parents[1]).resolve()
    approved_roots = approved_roots or [root / "docs" / "evidence" / "source-snapshots"]
    candidates_path = candidates_path.resolve()
    manifest_path = manifest_path.resolve()
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    checksum_results: list[dict[str, Any]] = []
    passage_results: list[dict[str, Any]] = []

    records, load_errors = load_jsonl(candidates_path)
    errors.extend(load_errors)
    sources, manifest_errors = load_manifest_sources(manifest_path, project_root=root)
    errors.extend(manifest_errors)

    ids = [str(record.get("candidate_id", "")) for record in records]
    id_counts = Counter(ids)
    duplicate_ids = sorted(candidate_id for candidate_id, count in id_counts.items() if count > 1)
    if len(records) != len(EXPECTED_IDS):
        errors.append(
            finding(
                "",
                "candidate_count",
                "candidate_count_mismatch",
                "ERROR",
                f"expected 12 candidate records, found {len(records)}",
            )
        )
    if sorted(ids) != sorted(EXPECTED_IDS):
        errors.append(
            finding(
                "",
                "candidate_id",
                "candidate_id_set_mismatch",
                "ERROR",
                f"expected ids {list(EXPECTED_IDS)}, found {sorted(ids)}",
            )
        )
    for candidate_id in duplicate_ids:
        errors.append(
            finding(
                candidate_id,
                "candidate_id",
                "duplicate_candidate_id",
                "ERROR",
                f"duplicate candidate_id {candidate_id}",
            )
        )

    allocation = Counter(str(record.get("family", "")) for record in records)
    if dict(allocation) != EXPECTED_ALLOCATION:
        errors.append(
            finding(
                "",
                "family",
                "allocation_mismatch",
                "ERROR",
                "expected allocation "
                f"{EXPECTED_ALLOCATION}, found {dict(sorted(allocation.items()))}",
            )
        )

    snapshot_cache: dict[str, Path] = {}
    tokenizer = (
        load_settings().chunking.get("tokenizer", "cl100k_base")
        if root == Path.cwd().resolve()
        else "cl100k_base"
    )

    for record in records:
        candidate_id = str(record.get("candidate_id", ""))
        for field in ARRAY_FIELDS:
            if not isinstance(record.get(field), list):
                errors.append(
                    finding(
                        candidate_id,
                        field,
                        "protected_field_not_array",
                        "ERROR",
                        f"{field} must be an array",
                    )
                )
        for field in FORBIDDEN_REWRITE_FIELDS:
            if field in record:
                errors.append(
                    finding(
                        candidate_id,
                        field,
                        "final_rewrite_field_present",
                        "ERROR",
                        f"{field} is not allowed in Stage 2.2B-1 candidates",
                    )
                )
        for field in ("eval009_accessed", "holdout_accessed", "final_rewrite_authored"):
            if record.get(field) is not False:
                errors.append(
                    finding(
                        candidate_id,
                        field,
                        "safety_flag_not_false",
                        "ERROR",
                        f"{field} must be false",
                    )
                )
        serialized = "\n".join(string_values(record))
        for marker in FORBIDDEN_TEXT_MARKERS:
            if marker.lower() in serialized.lower():
                errors.append(
                    finding(
                        candidate_id,
                        "record_text",
                        "forbidden_eval_or_holdout_reference",
                        "ERROR",
                        f"candidate text references {marker}",
                    )
                )
        source_passage = str(record.get("source_passage", ""))
        if not source_passage.strip():
            errors.append(
                finding(
                    candidate_id,
                    "source_passage",
                    "empty_source_passage",
                    "ERROR",
                    "source passage is empty",
                )
            )
        declared_normalization = str(record.get("source_passage_normalization", ""))
        if declared_normalization != PASSAGE_NORMALIZATION:
            errors.append(
                finding(
                    candidate_id,
                    "source_passage_normalization",
                    "undeclared_text_normalization",
                    "ERROR",
                    f"normalization must be {PASSAGE_NORMALIZATION!r}",
                )
            )
            continue

        source_id = str(record.get("source_id", "")).strip()
        source = sources.get(source_id)
        if source is None:
            errors.append(
                finding(
                    candidate_id,
                    "source_id",
                    "missing_source",
                    "ERROR",
                    f"source_id {source_id!r} is absent from manifest",
                )
            )
            continue
        try:
            snapshot_path = snapshot_cache[source_id]
        except KeyError:
            try:
                snapshot_path = resolve_evidence_path(
                    project_root=root,
                    manifest_path=manifest_path,
                    candidate=str(source["local_snapshot_path"]),
                    approved_roots=approved_roots,
                )
                snapshot_cache[source_id] = snapshot_path
            except ConfigError as exc:
                errors.append(
                    finding(
                        candidate_id,
                        "local_snapshot_path",
                        "snapshot_path_invalid",
                        "ERROR",
                        str(exc),
                    )
                )
                continue

        expected_checksum = str(source.get("checksum", "")).lower()
        actual_checksum = sha256_file(snapshot_path) if snapshot_path.is_file() else ""
        checksum_match = bool(expected_checksum and actual_checksum == expected_checksum)
        checksum_results.append(
            {
                "candidate_id": candidate_id,
                "source_id": source_id,
                "snapshot_path": str(
                    snapshot_path.relative_to(root)
                    if snapshot_path.is_relative_to(root)
                    else snapshot_path
                ),
                "expected": expected_checksum,
                "actual": actual_checksum,
                "match": checksum_match,
            }
        )
        if not checksum_match:
            errors.append(
                finding(
                    candidate_id,
                    "checksum",
                    "checksum_mismatch",
                    "ERROR",
                    f"snapshot checksum mismatch for source {source_id}",
                )
            )
            continue

        resolved_text, resolved_locator = resolve_passage(
            snapshot_path=snapshot_path,
            exact_section=str(record.get("exact_section", "")),
            subsection=str(record.get("subsection", "")),
            paragraph_ordinal=record.get("paragraph_ordinal"),
            sentence_ordinal=record.get("sentence_ordinal"),
        )
        passage_match = resolved_text == source_passage
        passage_hash = sha256_text(source_passage)
        token_count = count_tokens(source_passage, tokenizer)
        passage_results.append(
            {
                "candidate_id": candidate_id,
                "source_id": source_id,
                "resolved_locator": resolved_locator,
                "passage_match": passage_match,
                "expected_sha256": record.get("source_passage_sha256"),
                "actual_sha256": passage_hash,
                "expected_token_count": record.get("source_token_count"),
                "actual_token_count": token_count,
            }
        )
        if resolved_text is None:
            errors.append(
                finding(
                    candidate_id,
                    "deterministic_locator",
                    "unresolved_locator",
                    "ERROR",
                    "section, paragraph, and sentence locator did not resolve",
                )
            )
            continue
        if not passage_match:
            errors.append(
                finding(
                    candidate_id,
                    "source_passage",
                    "source_passage_mismatch",
                    "ERROR",
                    "source_passage does not match the resolved source span",
                )
            )
        if record.get("source_passage_sha256") != passage_hash:
            errors.append(
                finding(
                    candidate_id,
                    "source_passage_sha256",
                    "passage_hash_mismatch",
                    "ERROR",
                    "source_passage_sha256 does not match source_passage",
                )
            )
        if record.get("source_token_count") != token_count:
            errors.append(
                finding(
                    candidate_id,
                    "source_token_count",
                    "token_count_mismatch",
                    "ERROR",
                    f"source_token_count does not match {tokenizer}",
                )
            )

    errors = sorted(errors, key=lambda item: (item["candidate_id"], item["field"], item["code"]))
    warnings = sorted(
        warnings,
        key=lambda item: (item["candidate_id"], item["field"], item["code"]),
    )
    verdict = "pass" if not errors else "fail"
    candidates_display_path = (
        candidates_path.relative_to(root)
        if candidates_path.is_relative_to(root)
        else candidates_path
    )
    manifest_display_path = (
        manifest_path.relative_to(root)
        if manifest_path.is_relative_to(root)
        else manifest_path
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "repository_commit": repository_commit,
        "candidates_path": str(candidates_display_path),
        "manifest_path": str(manifest_display_path),
        "candidate_record_count": len(records),
        "expected_candidate_ids": list(EXPECTED_IDS),
        "actual_candidate_ids": ids,
        "duplicate_candidate_ids": duplicate_ids,
        "expected_allocation": EXPECTED_ALLOCATION,
        "actual_allocation": dict(sorted(allocation.items())),
        "tokenizer": tokenizer,
        "passage_normalization": PASSAGE_NORMALIZATION,
        "checksum_results": sorted(
            checksum_results,
            key=lambda row: (row["source_id"], row["candidate_id"]),
        ),
        "passage_results": sorted(passage_results, key=lambda row: row["candidate_id"]),
        "errors": errors,
        "warnings": warnings,
        "verdict": verdict,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument(
        "--approved-root",
        action="append",
        help="approved local root for source snapshots; repeatable",
    )
    args = parser.parse_args()
    settings = load_settings()
    approved_roots = (
        [settings.resolve_inside_project(root) for root in args.approved_root]
        if args.approved_root
        else None
    )
    report = validate_candidates(
        settings.resolve_inside_project(args.candidates),
        settings.resolve_inside_project(args.manifest),
        project_root=settings.project_root,
        approved_roots=approved_roots,
        repository_commit=git_value(["rev-parse", "HEAD"]),
    )
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "stage2 candidate validation: "
        f"verdict={report['verdict']} "
        f"records={report['candidate_record_count']} "
        f"errors={len(report['errors'])} "
        f"warnings={len(report['warnings'])}"
    )
    print(f"report: {output}")
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
