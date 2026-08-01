#!/usr/bin/env python3
"""Corpus lint — Prompt D §G1 gate. Read-only; writes a report, never the store.

    python scripts/corpus_lint.py            # human report, exit 1 on failure
    python scripts/corpus_lint.py --json     # machine report

Checks, in the order Prompt D lists them:

  front matter / manifest coverage . every corpus file belongs to a declared source
  unique ids ...................... deterministic chunk ids do not collide
  accepted statuses ............... license_status is one of the accepted values
  license labels .................. no source or chunk carries an empty license
  no secrets ...................... credential patterns in corpus text
  no binaries ..................... no media or archive bytes under corpus/
  no duplicates ................... no two chunks with identical text
  no unapproved claims ............ "production ready" style assertions
  polarity ........................ nothing from a negative source is labelled
                                    as a positive example, and vice versa

Composition percentages (Prompt D §D) are reported here too: any auxiliary source
class above 40% of the collection fails the gate.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from natural_flow_rag.chunking import chunk_text  # noqa: E402
from natural_flow_rag.loaders import SUPPORTED, discover, load  # noqa: E402
from natural_flow_rag.normalize import normalize  # noqa: E402
from natural_flow_rag.schemas import chunk_id, sha256_text  # noqa: E402
from natural_flow_rag.settings import load_settings, load_sources  # noqa: E402

ACCEPTED_STATUSES = {"approved", "quarantined", "refused", "deferred"}

# Auxiliary classes may inform a rewrite but must not dominate the collection.
PRIMARY_DOC_TYPES = {"approved_example", "style_rule"}
AUXILIARY_CAP = 0.40

SECRET_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
    re.compile(r"(?i)\b(api[_-]?key|secret|password)\b\s*[:=]\s*['\"][^'\"]{8,}"),
]

UNAPPROVED_CLAIMS = re.compile(
    r"(?i)\b(production[- ]ready|fully operational|guaranteed results|100% accurate)\b"
)

BINARY_SUFFIXES = {".mp3", ".m4a", ".mp4", ".wav", ".zip", ".pdf", ".sqlite3", ".bin"}

NEGATIVE_DOC_TYPE = "negative_pattern"
# Text that would make a chunk read as an endorsed exemplar.
POSITIVE_MARKERS = re.compile(r"(?i)`?positive_target`?|approved (?:target|exemplar)")


class Finding(dict):
    def __init__(self, check: str, severity: str, message: str, where: str = ""):
        super().__init__(check=check, severity=severity, message=message, where=where)


def lint() -> tuple[list[Finding], dict]:
    settings = load_settings()
    manifest = load_sources()
    root = settings.project_root
    findings: list[Finding] = []

    sources = manifest.get("sources", []) or []
    declared_paths = {}
    for source in sources:
        status = source.get("license_status")
        if status not in ACCEPTED_STATUSES:
            findings.append(Finding(
                "accepted statuses", "FAIL",
                f"source {source.get('id')!r} has license_status {status!r}; "
                f"accepted: {sorted(ACCEPTED_STATUSES)}"))
        if status == "approved" and not str(source.get("license", "")).strip():
            findings.append(Finding(
                "license labels", "FAIL",
                f"approved source {source.get('id')!r} has an empty license"))
        declared_paths[settings.resolve_inside_project(source["path"])] = source

    corpus_root = root / "corpus" / "raw"

    # ── binaries and manifest coverage ────────────────────────────────────────
    for path in sorted(corpus_root.rglob("*")) if corpus_root.exists() else []:
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() in BINARY_SUFFIXES:
            findings.append(Finding(
                "no binaries", "FAIL",
                f"binary {path.suffix} inside the text corpus", str(path.relative_to(root))))
            continue
        if path.suffix.lower() not in SUPPORTED:
            continue  # manifests and configs are not ingested; not an error
        if not any(path.is_relative_to(declared) for declared in declared_paths):
            findings.append(Finding(
                "manifest coverage", "FAIL",
                "corpus file belongs to no declared source",
                str(path.relative_to(root))))

    # ── chunk-level checks ────────────────────────────────────────────────────
    profiles = settings.chunking.get("profiles", {})
    tokenizer = settings.chunking.get("tokenizer", "cl100k_base")
    seen_ids: dict[str, str] = {}
    seen_text: dict[str, str] = {}
    by_doc_type: Counter[str] = Counter()
    by_source: Counter[str] = Counter()
    per_source_files: dict[str, list[str]] = defaultdict(list)

    for source in sources:
        if source.get("license_status") != "approved":
            continue
        source_path = settings.resolve_inside_project(source["path"])
        for path in discover(source_path):
            text = normalize(load(path).text)
            chunks = chunk_text(
                text,
                profile=source.get("chunk_profile", "reference"),
                profiles=profiles,
                tokenizer=tokenizer,
                hard_maximum_tokens=int(settings.chunking.get("hard_maximum_tokens", 2048)),
                safe_target_ceiling=int(settings.chunking.get("safe_target_ceiling", 1024)),
            )
            per_source_files[source["id"]].append(path.name)
            doc_type = source.get("doc_type") or "unknown"

            for chunk in chunks:
                identifier = chunk_id(source["id"], sha256_text(chunk.text), chunk.index)
                where = f"{path.name}#{chunk.index}"
                by_doc_type[doc_type] += 1
                by_source[source["id"]] += 1

                if identifier in seen_ids:
                    findings.append(Finding(
                        "unique ids", "FAIL",
                        f"chunk id collision with {seen_ids[identifier]}", where))
                seen_ids[identifier] = where

                digest = sha256_text(chunk.text.strip())
                if digest in seen_text:
                    findings.append(Finding(
                        "no duplicates", "FAIL",
                        f"identical chunk text already present at {seen_text[digest]}", where))
                seen_text[digest] = where

                for pattern in SECRET_PATTERNS:
                    if pattern.search(chunk.text):
                        findings.append(Finding(
                            "no secrets", "FAIL", "credential-shaped string in corpus", where))
                        break

                if UNAPPROVED_CLAIMS.search(chunk.text):
                    findings.append(Finding(
                        "no unapproved claims", "WARN",
                        "chunk asserts a release-readiness claim", where))

                # Polarity: a negative-pattern chunk must not read as an endorsed
                # exemplar, and a positive source must not carry the negative type.
                if doc_type == NEGATIVE_DOC_TYPE and POSITIVE_MARKERS.search(chunk.text):
                    findings.append(Finding(
                        "polarity", "FAIL",
                        "negative-pattern chunk contains positive-target marking", where))
                if doc_type != NEGATIVE_DOC_TYPE and "negative_contrast" in chunk.text:
                    findings.append(Finding(
                        "polarity", "WARN",
                        f"chunk in doc_type={doc_type} references negative_contrast", where))

    total = sum(by_doc_type.values())
    composition = {
        doc_type: {"chunks": n, "percent": round(100 * n / total, 1) if total else 0.0}
        for doc_type, n in sorted(by_doc_type.items(), key=lambda kv: -kv[1])
    }
    for doc_type, stats in composition.items():
        if doc_type not in PRIMARY_DOC_TYPES and stats["percent"] > AUXILIARY_CAP * 100:
            findings.append(Finding(
                "composition", "FAIL",
                f"auxiliary class {doc_type!r} is {stats['percent']}% of the collection, "
                f"above the {int(AUXILIARY_CAP * 100)}% cap (Prompt D §D)"))

    report = {
        "total_chunks": total,
        "by_doc_type": composition,
        "by_source": dict(by_source),
        "files": {k: sorted(v) for k, v in per_source_files.items()},
        "findings": findings,
        "failures": sum(1 for f in findings if f["severity"] == "FAIL"),
        "warnings": sum(1 for f in findings if f["severity"] == "WARN"),
    }
    return findings, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the machine report")
    args = parser.parse_args()

    findings, report = lint()

    if args.json:
        print(json.dumps(report, indent=2))
        return 1 if report["failures"] else 0

    print(f"\ncorpus lint — {report['total_chunks']} chunks\n")
    print("composition by doc_type (Prompt D §D, 40% auxiliary cap):")
    for doc_type, stats in report["by_doc_type"].items():
        mark = "primary" if doc_type in PRIMARY_DOC_TYPES else "auxiliary"
        print(f"  {doc_type:<20} {stats['chunks']:>4} chunks  {stats['percent']:>5}%  {mark}")

    print("\nby source:")
    for source_id, count in report["by_source"].items():
        print(f"  {source_id:<26} {count:>4}")

    if not findings:
        print("\nPASS — no findings.\n")
        return 0

    print()
    for finding in findings:
        where = f"  [{finding['where']}]" if finding["where"] else ""
        print(f"  {finding['severity']:<4} {finding['check']:<22} {finding['message']}{where}")
    print(f"\n{report['failures']} failure(s), {report['warnings']} warning(s)\n")
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
