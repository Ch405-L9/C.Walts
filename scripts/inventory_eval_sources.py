#!/usr/bin/env python3
"""Inventory acquired evaluation-source datasets without selecting records."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = PROJECT_ROOT / "var" / "eval_sources" / "extracted"
MANIFEST = (
    PROJECT_ROOT / "var" / "eval_sources" / "manifests" / "acquisition-manifest.json"
)
BOUNDARY = PROJECT_ROOT / "docs" / "evidence" / "gate0-boundary.json"
REPORT_JSON = PROJECT_ROOT / "docs" / "evidence" / "dataset-inventory-gate0.json"
REPORT_MD = PROJECT_ROOT / "docs" / "dataset-acquisition-report-gate0.md"


class InventoryError(RuntimeError):
    pass


# Candidacy is an annotation, not a selection. A label is flagged "near-domain"
# when one of its underscore-separated tokens starts with one of these stems,
# i.e. when the label is about language, wording, speech, or delivery — the
# subject C.Walts actually covers. The rule is deliberately mechanical so a
# reviewer can reproduce or reject it without re-reading 151 labels. Nothing
# downstream consumes these lists yet.
#
# Token-prefix, not substring: a plain `in` test flagged `spending_history`
# through "story" and `sync_device` through a "syn" stem, neither of which has
# anything to do with narration.
NEAR_DOMAIN_KEYWORDS = (
    "accent",
    "audio",
    "definition",
    "joke",
    "language",
    "meaning",
    "podcast",
    "pronounc",
    "quirky",
    "read",
    "speak",
    "speech",
    "spell",
    "story",
    "synonym",
    "text",
    "translat",
    "voice",
    "volume",
    "word",
    "write",
)

CANDIDACY_RULE = (
    "A label is MECHANICALLY PROPOSED, and nothing more, when one of its "
    "underscore-separated tokens begins with one of: "
    f"{', '.join(NEAR_DOMAIN_KEYWORDS)}. A string match is not a domain "
    "judgement: CLINC150's `text` means 'send a text message', not written "
    "text, and it is proposed only because the rule cannot tell the difference. "
    "Every proposed label is UNAPPROVED and requires human review before any "
    "use. No query has been selected."
)

# Named in the Gate 0.1 review as labels a reader would reasonably doubt. They
# are listed in the report so the burden of justifying each one is explicit
# rather than buried in a list of nine.
DISPUTED_PROPOSALS = (
    "meaning_of_life",
    "tell_joke",
    "text",
    "change_volume",
    "general_quirky",
)


def candidate_split(names: Iterable[str]) -> dict[str, object]:
    proposed: list[str] = []
    not_proposed: list[str] = []
    for name in sorted(set(names)):
        tokens = name.casefold().replace("-", "_").split("_")
        if any(
            token.startswith(keyword)
            for token in tokens
            for keyword in NEAR_DOMAIN_KEYWORDS
        ):
            proposed.append(name)
        else:
            not_proposed.append(name)
    return {
        "approval_status": "unapproved",
        "approved_by": None,
        "mechanically_proposed_unapproved": proposed,
        "not_proposed_by_the_rule": not_proposed,
    }


def text_stats(values: Iterable[str]) -> dict[str, object]:
    items = [value.strip() for value in values if value and value.strip()]
    lengths = [len(item.split()) for item in items]
    lowered = [item.casefold() for item in items]
    duplicates = sum(count - 1 for count in Counter(lowered).values() if count > 1)
    return {
        "records": len(items),
        "exact_casefold_duplicate_records": duplicates,
        "word_count": {
            "minimum": min(lengths) if lengths else 0,
            "median": statistics.median(lengths) if lengths else 0,
            "maximum": max(lengths) if lengths else 0,
        },
    }


def parse_clinc(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise InventoryError("CLINC data_full.json must be an object")
    split_counts: dict[str, int] = {}
    label_counts: Counter[str] = Counter()
    texts: list[str] = []
    for split, rows in data.items():
        if not isinstance(rows, list):
            continue
        split_counts[split] = len(rows)
        for row in rows:
            if not isinstance(row, list) or len(row) < 2:
                raise InventoryError(f"unexpected CLINC row in {split}: {row!r}")
            text, label = str(row[0]), str(row[1])
            texts.append(text)
            label_counts[label] += 1
    return {
        "split_counts": split_counts,
        "label_count": len(label_counts),
        "labels": sorted(label_counts),
        "oos_records": sum(
            count for label, count in label_counts.items()
            if label.casefold() in {"oos", "out_of_scope", "out-of-scope"}
        ),
        "oos_split_counts": {
            split: count for split, count in split_counts.items()
            if split.casefold().startswith("oos")
        },
        "candidate_labels": candidate_split(label_counts),
        "candidacy_rule": CANDIDACY_RULE,
        "text": text_stats(texts),
    }


def parse_massive(path: Path) -> dict[str, object]:
    scenario_counts: Counter[str] = Counter()
    intent_counts: Counter[str] = Counter()
    partition_counts: Counter[str] = Counter()
    texts: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            locale = row.get("locale")
            if locale != "en-US":
                raise InventoryError(
                    f"MASSIVE locale mismatch at line {line_number}: {locale}"
                )
            texts.append(str(row["utt"]))
            scenario_counts[str(row["scenario"])] += 1
            intent_counts[str(row["intent"])] += 1
            partition_counts[str(row["partition"])] += 1
    return {
        "scenario_counts": dict(sorted(scenario_counts.items())),
        "intent_counts": dict(sorted(intent_counts.items())),
        "partition_counts": dict(sorted(partition_counts.items())),
        "scenario_count": len(scenario_counts),
        "intent_count": len(intent_counts),
        "candidate_scenarios": candidate_split(scenario_counts),
        "candidate_intents": candidate_split(intent_counts),
        "candidacy_rule": CANDIDACY_RULE,
        "dataset_shape": (
            "Single-shot assistant utterances labelled by scenario and intent. "
            "MASSIVE is not a multi-intent dataset."
        ),
        "text": text_stats(texts),
    }


def parse_banking(train: Path, test: Path, categories: Path) -> dict[str, object]:
    category_list = json.loads(categories.read_text(encoding="utf-8"))
    if not isinstance(category_list, list):
        raise InventoryError("Banking77 categories.json must be an array")
    partition_counts: dict[str, int] = {}
    observed: Counter[str] = Counter()
    texts: list[str] = []
    for split, path in [("train", train), ("test", test)]:
        count = 0
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            # Both CSVs ship a `text,category` header. It is asserted rather than
            # skipped blindly: a silently absent header would cost one real record.
            header = next(reader, None)
            if header != ["text", "category"]:
                raise InventoryError(
                    f"unexpected Banking77 header in {path}: {header!r}"
                )
            for row in reader:
                if len(row) != 2:
                    raise InventoryError(f"unexpected Banking77 row in {path}: {row!r}")
                text, category = row
                texts.append(text)
                observed[category] += 1
                count += 1
        partition_counts[split] = count
    unknown = sorted(set(observed) - set(map(str, category_list)))
    if unknown:
        raise InventoryError(f"Banking77 categories absent from categories.json: {unknown}")
    return {
        "partition_counts": partition_counts,
        "category_count": len(category_list),
        "categories": sorted(map(str, category_list)),
        "candidate_use": (
            "Far out-of-domain only. Every category is retail-banking customer "
            "support, which shares no vocabulary with narration or prosody."
        ),
        "text": text_stats(texts),
    }


def acquisition_provenance() -> dict[str, object]:
    """Lift the checksums and licence conclusions out of the ignored manifest.

    ``var/eval_sources/`` is local-only, so the manifest itself is never tracked.
    The provenance a reviewer needs — URL, version, archive and extracted-file
    hashes, and which licence markers were verified in-band — is copied here so
    it survives in the repository without any dataset text coming with it.
    """
    if not MANIFEST.exists():
        raise InventoryError(
            f"acquisition manifest is missing: {MANIFEST}. "
            "Run scripts/acquire_eval_sources.py --execute first."
        )
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    datasets: dict[str, object] = {}
    for name, entry in manifest["datasets"].items():
        datasets[name] = {
            "version": entry["version"],
            "official_page": entry["official_page"],
            "declared_license": entry["declared_license"],
            "license_reconciliation": entry.get("license_reconciliation"),
            "archive_url": entry["download"]["url"],
            "archive_final_url": entry["download"]["final_url"],
            "archive_bytes": entry["download"]["bytes"],
            "archive_sha256": entry["download"]["sha256"],
            "extracted_files": entry["extracted_files"],
            "license_verification": entry["license_verification"],
        }
    archive_bytes = sum(
        entry["download"]["bytes"] for entry in manifest["datasets"].values()
    )
    extracted_bytes = sum(
        record["bytes"]
        for entry in manifest["datasets"].values()
        for record in entry["extracted_files"]
    )
    return {
        "config_sha256": manifest["config_sha256"],
        "archive_bytes_total": archive_bytes,
        "extracted_bytes_total": extracted_bytes,
        "datasets": datasets,
    }


def production_boundary() -> dict[str, object]:
    if not BOUNDARY.exists():
        raise InventoryError(f"boundary measurements are missing: {BOUNDARY}")
    return json.loads(BOUNDARY.read_text(encoding="utf-8"))


def build_inventory() -> dict[str, object]:
    clinc_root = EXTRACTED / "clinc150" / "clinc150_uci"
    massive_root = EXTRACTED / "massive_1_0_en_us" / "1.0"
    banking_root = (
        EXTRACTED
        / "banking77"
        / "task-specific-datasets-master"
    )
    return {
        "schema_version": 1,
        "selection_performed": False,
        "production_ingestion_performed": False,
        "acquisition": acquisition_provenance(),
        "production_boundary": production_boundary(),
        "datasets": {
            "clinc150": parse_clinc(clinc_root / "data_full.json"),
            "massive_1_0_en_us": parse_massive(
                massive_root / "data" / "en-US.jsonl"
            ),
            "banking77": parse_banking(
                banking_root / "banking_data" / "train.csv",
                banking_root / "banking_data" / "test.csv",
                banking_root / "banking_data" / "categories.json",
            ),
        },
    }


def write_reports(inventory: dict[str, object]) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(
        json.dumps(inventory, indent=2) + "\n", encoding="utf-8"
    )
    datasets = inventory["datasets"]
    acquisition = inventory["acquisition"]
    clinc = datasets["clinc150"]
    massive = datasets["massive_1_0_en_us"]
    banking = datasets["banking77"]

    def words(entry: dict[str, object]) -> str:
        wc = entry["text"]["word_count"]
        return f"{wc['minimum']} / {wc['median']} / {wc['maximum']}"

    lines = [
        "# C.Walts v0.4 Gate 0 — dataset acquisition and inventory",
        "",
        "Generated by `scripts/inventory_eval_sources.py`. This file is a report, not",
        "data: it carries counts, label names, checksums, and licence conclusions, and",
        "no rows of any dataset.",
        "",
        "**No query was selected. Nothing was chunked, embedded, or ingested.** The",
        "acquired records are evaluation-query candidates; they are test inputs, not",
        "knowledge, and they never enter `badgr_natural_flow_v1`, `var/chroma/`, or",
        "`var/bm25/`.",
        "",
        "## Summary",
        "",
        "| Dataset | Records | Labels/domains | Duplicate records | Words min/median/max |",
        "|---|---:|---|---:|---|",
        (
            f"| CLINC150 | {clinc['text']['records']} | "
            f"{clinc['label_count']} labels | "
            f"{clinc['text']['exact_casefold_duplicate_records']} | {words(clinc)} |"
        ),
        (
            f"| MASSIVE 1.0 en-US | {massive['text']['records']} | "
            f"{massive['scenario_count']} scenarios / "
            f"{massive['intent_count']} intents | "
            f"{massive['text']['exact_casefold_duplicate_records']} | {words(massive)} |"
        ),
        (
            f"| Banking77 | {banking['text']['records']} | "
            f"{banking['category_count']} categories | "
            f"{banking['text']['exact_casefold_duplicate_records']} | {words(banking)} |"
        ),
        "",
        "### Duplicate counts, confirmed",
        "",
        "A duplicate is an exact repeat after case-folding and stripping surrounding",
        "whitespace, counted across all splits of a dataset. For n identical records the",
        "count contributed is n-1, so the figure is the number of records that could be",
        "dropped without losing a distinct query.",
        "",
        "| Dataset | Exact case-folded duplicate records |",
        "|---|---:|",
        f"| CLINC150 | {clinc['text']['exact_casefold_duplicate_records']} |",
        f"| MASSIVE 1.0 en-US | "
        f"{massive['text']['exact_casefold_duplicate_records']} |",
        f"| Banking77 | {banking['text']['exact_casefold_duplicate_records']} |",
        "",
        "**No duplicate was removed.** De-duplication is a selection decision, and no",
        "selection has been made. They are counted so the next phase inherits a known",
        "figure rather than rediscovering it.",
        "",
        "## Provenance and licence verification",
        "",
        f"Approved-source config SHA-256: `{acquisition['config_sha256']}`",
        "",
        "| Dataset | Version | Licence (verified in-band) | Archive SHA-256 |",
        "|---|---|---|---|",
    ]
    for name, entry in acquisition["datasets"].items():
        lines.append(
            f"| {name} | {entry['version']} | {entry['declared_license']} | "
            f"`{entry['archive_sha256']}` |"
        )
    lines += [
        "",
        "Every archive was fetched over HTTPS from its first-party origin. No Hugging",
        "Face mirror or third-party copy was used.",
        "",
        "| Dataset | Source URL |",
        "|---|---|",
    ]
    for name, entry in acquisition["datasets"].items():
        lines.append(f"| {name} | {entry['archive_url']} |")
    lines += [
        "",
        "### Extracted files",
        "",
        "| Dataset | Member | Bytes | SHA-256 |",
        "|---|---|---:|---|",
    ]
    for name, entry in acquisition["datasets"].items():
        for record in entry["extracted_files"]:
            lines.append(
                f"| {name} | `{record['member']}` | {record['bytes']} | "
                f"`{record['sha256']}` |"
            )
    lines += [
        "",
        "### Licence markers asserted inside each archive",
        "",
        "| Dataset | Licence file | Markers required and found |",
        "|---|---|---|",
    ]
    for name, entry in acquisition["datasets"].items():
        verification = entry["license_verification"]
        markers = "; ".join(f"`{m}`" for m in verification["markers_verified"])
        lines.append(f"| {name} | `{verification['path']}` | {markers} |")

    for name, entry in acquisition["datasets"].items():
        reconciliation = entry.get("license_reconciliation")
        if not reconciliation:
            continue
        lines += [
            "",
            f"### {name} — licence discrepancy, recorded rather than resolved",
            "",
            "Two authoritative sources disagree. Both are preserved; neither is erased.",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| Archive URL | {reconciliation['archive_url']} |",
            f"| Archive SHA-256 | `{reconciliation['archive_sha256']}` |",
            f"| Embedded licence path | `{reconciliation['embedded_license_path']}` |",
            f"| Embedded licence SHA-256 | "
            f"`{reconciliation['embedded_license_sha256']}` |",
            f"| Embedded licence version | "
            f"{reconciliation['embedded_license_version']} |",
            f"| Embedded licence opening | "
            f"{reconciliation['embedded_license_first_lines']} |",
            f"| Landing page | {reconciliation['landing_page_url']} |",
            f"| Landing-page statement | "
            f"\"{reconciliation['landing_page_license_statement']}\" |",
            f"| Landing-page DOI | {reconciliation['landing_page_doi']} |",
            f"| Access date | {reconciliation['access_date']} |",
            f"| Operative minimum for this archive | "
            f"**{reconciliation['operative_minimum']}** |",
            f"| Attribution required | {reconciliation['attribution_required']} |",
            f"| Commercial use | {reconciliation['commercial_use']} |",
            f"| Transformation | {reconciliation['transformation']} |",
            f"| Redistribution | {reconciliation['redistribution']} |",
            "",
            f"{reconciliation['operative_minimum_rationale']}",
            "",
            "**Unresolved discrepancy.** "
            f"{reconciliation['unresolved_discrepancy_note']}",
            "",
            "Attribution as required:",
            "",
            f"> {reconciliation['attribution_text']}",
        ]
    lines += [
        "",
        "## CLINC150",
        "",
        f"Splits: {clinc['split_counts']}.",
        "",
        f"Labels: {clinc['label_count']} (150 in-domain intents plus `oos`). "
        f"Out-of-scope records: {clinc['oos_records']}, distributed as "
        f"{clinc['oos_split_counts']}.",
        "",
        "The explicit out-of-scope split is the reason this source was approved: it is",
        "the only one of the three that ships human-written queries already labelled as",
        "unanswerable by the assistant they were collected for.",
        "",
        "## MASSIVE 1.0 en-US",
        "",
        f"{massive['dataset_shape']}",
        "",
        f"Partitions: {massive['partition_counts']}.",
        "",
        f"Scenario record counts: {massive['scenario_counts']}.",
        "",
        "## Banking77",
        "",
        f"Partitions: {banking['partition_counts']}. "
        f"Categories: {banking['category_count']}.",
        "",
        f"{banking['candidate_use']}",
        "",
        "Both CSVs carry a `text,category` header row, which the inventory asserts and",
        "excludes from the counts above.",
        "",
        "## Mechanically proposed labels — UNAPPROVED",
        "",
        "**Nothing below is a near-domain classification.** These are the labels a",
        "string rule matched. None has been approved, none has been selected, and no",
        "label may be treated as near-domain on the strength of this list alone.",
        "",
        f"{clinc['candidacy_rule']}",
        "",
        "### Proposals a reviewer should expect to reject or qualify",
        "",
        "The rule matched these, and each needs a human decision before use:",
        "",
        "| Label | Why the rule matched | Why that may be wrong |",
        "|---|---|---|",
        "| `text` (CLINC150) | token `text` | The intent is *send a text message*. "
        "It has nothing to do with written text or wording. |",
        "| `change_volume` (CLINC150) | token `volume` | Device loudness, not vocal "
        "delivery or emphasis. |",
        "| `meaning_of_life` (CLINC150) | token `meaning` | Philosophical small talk, "
        "not lexical or semantic meaning. |",
        "| `tell_joke` (CLINC150) | token `joke` | Delivery-adjacent at best; humour "
        "timing is not the narration guidance C.Walts covers. |",
        "| `general_quirky` (MASSIVE) | token `quirky` | A catch-all bucket, not a "
        "domain. Its contents are heterogeneous and must be inspected per record. |",
        "",
        "### CLINC150 — mechanically proposed, unapproved",
        "",
        f"{', '.join(clinc['candidate_labels']['mechanically_proposed_unapproved'])}",
        "",
        f"The other {len(clinc['candidate_labels']['not_proposed_by_the_rule'])} labels "
        "were not proposed by the rule. Not being proposed is also not a judgement: the "
        "rule can miss. Both lists are in the JSON inventory.",
        "",
        "### MASSIVE — mechanically proposed scenarios, unapproved",
        "",
        f"{', '.join(massive['candidate_scenarios']['mechanically_proposed_unapproved'])}",
        "",
        "### MASSIVE — mechanically proposed intents, unapproved",
        "",
        f"{', '.join(massive['candidate_intents']['mechanically_proposed_unapproved'])}",
        "",
        "### Banking77",
        "",
        "The rule proposed nothing. All 77 categories are retail-banking customer",
        "support. This is the one place the report states a domain conclusion, and it",
        "rests on reading the category names, not on the token rule.",
        "",
        "## Production boundary, measured before and after",
        "",
        "| Item | Before | After |",
        "|---|---|---|",
    ]
    boundary = inventory["production_boundary"]
    labels = [
        ("chroma_badgr_natural_flow_v1", "Chroma `badgr_natural_flow_v1`"),
        (
            "chroma_badgr_natural_flow_feedback_v1",
            "Chroma `badgr_natural_flow_feedback_v1`",
        ),
        ("bm25_chunk_ids", "BM25 chunk_ids"),
        ("bm25_token_rows", "BM25 token rows"),
        ("badgr_harness_store_md5", "BADGR Harness store MD5"),
        ("free_disk_gib", "Free disk (GiB)"),
    ]
    for key, label in labels:
        lines.append(
            f"| {label} | {boundary['before'][key]} | {boundary['after'][key]} |"
        )
    lines += [
        "",
        "No ingestion or reindex tool was called. Nothing was chunked or embedded.",
        "The measurement commands are recorded in "
        "`docs/evidence/gate0-boundary.json`.",
        "",
        "## Disk use",
        "",
        f"Archives: {acquisition['archive_bytes_total']:,} bytes. "
        f"Extracted allowlisted files: {acquisition['extracted_bytes_total']:,} bytes. "
        f"Both live under `var/eval_sources/`, which is Git-ignored.",
        "",
        "| Dataset | Archive bytes |",
        "|---|---:|",
    ]
    for name, entry in acquisition["datasets"].items():
        lines.append(f"| {name} | {entry['archive_bytes']:,} |")
    lines += [
        "",
        "## Boundary",
        "",
        "Full aggregate inventory: `docs/evidence/dataset-inventory-gate0.json`.",
        "Raw archives and extracted files stay under `var/eval_sources/`, which is",
        "Git-ignored and never committed.",
        "",
        "The root `SHA256SUMS` records the Gate 0 package as delivered. Three of its",
        "twelve files — both acquisition scripts and the test module — were edited",
        "during this phase for lint compliance, two hardening changes, and the",
        "adversarial suite, so those three entries no longer match by design. The",
        "reasons and the post-edit hashes are in `docs/execution-log.md`.",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify() -> None:
    inventory = build_inventory()
    existing = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    if inventory != existing:
        raise InventoryError("current source inventory differs from recorded report")
    print("Dataset inventory verified.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    try:
        if args.verify:
            verify()
        else:
            inventory = build_inventory()
            write_reports(inventory)
            print(f"Wrote {REPORT_JSON.relative_to(PROJECT_ROOT)}")
            print(f"Wrote {REPORT_MD.relative_to(PROJECT_ROOT)}")
        return 0
    except (InventoryError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
