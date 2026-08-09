#!/usr/bin/env python3
"""Fail-closed integrity checks for the future calibration/holdout split."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

ALGORITHM_ID = "group-stratified-exact-subset-v1"
SEAL_SCHEMA_VERSION = 1
ID_PATTERN = re.compile(r"^CWQ-[A-Z]+-[0-9]{4}$")
PUBLIC_KINDS = {"public_verbatim", "public_transformed"}
CUSTOM_KINDS = {"owner_authored", "vendor_generated_owner_approved"}
CLASS_NAMES = {
    "supported_in_domain",
    "near_domain_unsupported",
    "far_out_of_domain",
    "ambiguous_adversarial_insufficient",
}
EXPECTED_BEHAVIORS = {
    "grounded",
    "partially_grounded",
    "exact_lexical",
    "abstain",
    "assist_ungrounded_only",
    "request_clarification",
}
ALLOCATION_TO_DATASET = {
    "clinc150": "clinc150",
    "clinc150_oos": "clinc150",
    "massive_en_us": "massive_1_0_en_us",
    "banking77": "banking77",
}


class SplitIntegrityError(ValueError):
    """A deterministic, operator-facing integrity failure."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {message}" if message else code)


def nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def canonical_text(value: str) -> str:
    value = nfc(value).replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.split()) for line in value.split("\n")]
    return "\n".join(lines).strip()


def canonicalize(value: Any) -> Any:
    if isinstance(value, str):
        return nfc(value)
    if isinstance(value, dict):
        return {str(key): canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    return value


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        canonicalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SplitIntegrityError("invalid_yaml_root", str(path))
    return payload


def load_allocation(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or ROOT / "config" / "query_allocation.yaml")


def load_candidate_schema() -> dict[str, Any]:
    return json.loads(
        (ROOT / "schemas" / "eval_candidate_manifest.schema.json").read_text(encoding="utf-8")
    )


def load_split_schema() -> dict[str, Any]:
    return json.loads(
        (ROOT / "schemas" / "eval_split_manifest.schema.json").read_text(encoding="utf-8")
    )


def validate_schema(instance: Any, schema: dict[str, Any]) -> None:
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
    if errors:
        raise SplitIntegrityError("schema_validation_failed", errors[0].message)


def provenance_kind(record: dict[str, Any]) -> str:
    provenance = record.get("provenance")
    if not isinstance(provenance, dict):
        raise SplitIntegrityError("provenance_missing")
    kind = provenance.get("kind")
    if not isinstance(kind, str):
        raise SplitIntegrityError("provenance_kind_missing")
    return kind


def public_or_custom(record: dict[str, Any]) -> str:
    kind = provenance_kind(record)
    if kind in PUBLIC_KINDS:
        return "public"
    if kind in CUSTOM_KINDS:
        return "custom"
    raise SplitIntegrityError("unsupported_provenance_kind", kind)


def derive_allocation_source(record: dict[str, Any]) -> str:
    dataset = record.get("source_dataset")
    class_name = record.get("class")
    source_kind = public_or_custom(record)
    if source_kind == "custom":
        if dataset != "custom":
            raise SplitIntegrityError("custom_dataset_namespace_mismatch")
        return "custom"
    if dataset == "clinc150" and class_name == "near_domain_unsupported":
        return "clinc150"
    if dataset == "clinc150" and class_name == "ambiguous_adversarial_insufficient":
        return "clinc150_oos"
    if dataset == "massive_1_0_en_us" and class_name in {
        "near_domain_unsupported",
        "far_out_of_domain",
    }:
        return "massive_en_us"
    if dataset == "banking77" and class_name == "far_out_of_domain":
        return "banking77"
    raise SplitIntegrityError("unsupported_class_source_pair", f"{class_name}:{dataset}")


def record_fingerprint(record: dict[str, Any]) -> str:
    fields = {
        "id": record.get("id"),
        "query_text": canonical_text(str(record.get("query_text", ""))),
        "class": record.get("class"),
        "expected_behavior": record.get("expected_behavior"),
        "source_dataset": record.get("source_dataset"),
        "source_version": record.get("source_version"),
        "source_record_id": record.get("source_record_id"),
        "source_partition": record.get("source_partition"),
        "source_intent": record.get("source_intent"),
        "source_domain": record.get("source_domain"),
        "group_id": record.get("group_id"),
        "template_fingerprint": record.get("template_fingerprint"),
        "license_ref": record.get("license_ref"),
        "provenance": record.get("provenance"),
    }
    return sha256_value(fields)


def allocation_cell(record: dict[str, Any]) -> tuple[str, str, str]:
    return (str(record["class"]), derive_allocation_source(record), public_or_custom(record))


def allocation_targets(allocation: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, int]]:
    classes = allocation.get("classes")
    if not isinstance(classes, dict):
        raise SplitIntegrityError("allocation_classes_missing")
    targets: dict[tuple[str, str, str], dict[str, int]] = {}
    for class_name, class_data in classes.items():
        if not isinstance(class_data, dict):
            raise SplitIntegrityError("allocation_class_invalid", str(class_name))
        for split in ("calibration", "holdout"):
            cells = class_data.get(split, {})
            if not isinstance(cells, dict):
                raise SplitIntegrityError("allocation_split_invalid", f"{class_name}:{split}")
            for source_key, target in cells.items():
                if not isinstance(target, int) or target < 0:
                    raise SplitIntegrityError("allocation_target_invalid", str(target))
                public_kind = "custom" if source_key == "custom" else "public"
                key = (str(class_name), str(source_key), public_kind)
                targets.setdefault(key, {})[split] = target
    return targets


def _find(parent: dict[str, str], item: str) -> str:
    while parent[item] != item:
        parent[item] = parent[parent[item]]
        item = parent[item]
    return item


def _union(parent: dict[str, str], left: str, right: str) -> None:
    left_root, right_root = _find(parent, left), _find(parent, right)
    if left_root != right_root:
        parent[max(left_root, right_root)] = min(left_root, right_root)


@dataclass(frozen=True)
class LeakageCluster:
    fingerprint: str
    record_ids: tuple[str, ...]
    strata: tuple[tuple[str, str, str], ...]

    @property
    def size(self) -> int:
        return len(self.record_ids)


def build_clusters(
    records: list[dict[str, Any]], extra_links: list[tuple[str, str]] | None = None
) -> list[LeakageCluster]:
    by_id = {str(record["id"]): record for record in records}
    parent = {record_id: record_id for record_id in by_id}
    group_owner: dict[str, str] = {}
    template_owner: dict[str, str] = {}
    for record_id in sorted(by_id):
        record = by_id[record_id]
        group = str(record["group_id"])
        if group in group_owner:
            _union(parent, record_id, group_owner[group])
        else:
            group_owner[group] = record_id
        template = record.get("template_fingerprint")
        if template:
            template = str(template)
            if template in template_owner:
                _union(parent, record_id, template_owner[template])
            else:
                template_owner[template] = record_id
    for left, right in extra_links or []:
        if left not in parent or right not in parent:
            raise SplitIntegrityError("disposition_candidate_missing")
        _union(parent, left, right)
    members: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record_id, record in by_id.items():
        members[_find(parent, record_id)].append(record)
    clusters: list[LeakageCluster] = []
    for cluster_records in members.values():
        record_ids = tuple(sorted(str(record["id"]) for record in cluster_records))
        strata = tuple(sorted({allocation_cell(record) for record in cluster_records}))
        if len(strata) != 1:
            raise SplitIntegrityError("mixed_stratum_leakage_cluster", ",".join(record_ids))
        group_ids = sorted({str(record["group_id"]) for record in cluster_records})
        templates = sorted(
            {
                str(record["template_fingerprint"])
                for record in cluster_records
                if record.get("template_fingerprint")
            }
        )
        member_fingerprints = sorted(record_fingerprint(record) for record in cluster_records)
        structure = {
            "algorithm_id": ALGORITHM_ID,
            "stratum": strata[0],
            "group_ids": group_ids,
            "template_fingerprints": templates,
            "record_fingerprints": member_fingerprints,
        }
        clusters.append(LeakageCluster(sha256_value(structure), record_ids, strata))
    return sorted(clusters, key=lambda cluster: (cluster.fingerprint, cluster.record_ids))


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+|[^\w\s]", canonical_text(text), flags=re.UNICODE)


def _ngrams(tokens: list[str], size: int = 3) -> set[tuple[str, ...]]:
    return {tuple(tokens[index : index + size]) for index in range(max(0, len(tokens) - size + 1))}


def similarity_pair(left: str, right: str) -> dict[str, float]:
    left_text, right_text = canonical_text(left), canonical_text(right)
    left_grams, right_grams = _ngrams(_tokens(left_text)), _ngrams(_tokens(right_text))
    union = left_grams | right_grams
    jaccard = len(left_grams & right_grams) / len(union) if union else 1.0
    return {
        "sequence_matcher_ratio": difflib.SequenceMatcher(
            None, left_text, right_text, autojunk=False
        ).ratio(),
        "token_3gram_jaccard": jaccard,
    }


def inspect_near_duplicates(
    records: list[dict[str, Any]], dispositions: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    disposition_map = {
        str(item.get("pair_fingerprint")): item for item in (dispositions or [])
    }
    findings: list[dict[str, Any]] = []
    ordered = sorted(records, key=lambda item: str(item["id"]))
    token_sets = {str(item["id"]): _ngrams(_tokens(str(item["query_text"]))) for item in ordered}
    gram_index: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for record_id, grams in token_sets.items():
        for gram in grams:
            gram_index[gram].append(record_id)
    by_id = {str(item["id"]): item for item in ordered}
    candidate_pairs: set[tuple[str, str]] = set()
    for ids in gram_index.values():
        for index, left_id in enumerate(sorted(ids)):
            for right_id in sorted(ids)[index + 1 :]:
                candidate_pairs.add((left_id, right_id))
    for left_id, right_id in sorted(candidate_pairs):
        left, right = by_id[left_id], by_id[right_id]
        metrics = similarity_pair(str(left["query_text"]), str(right["query_text"]))
        ratio, jaccard = metrics["sequence_matcher_ratio"], metrics["token_3gram_jaccard"]
        same_family = bool(
            left.get("template_fingerprint")
            and left.get("template_fingerprint") == right.get("template_fingerprint")
        )
        same_class = left.get("class") == right.get("class")
        hard = ratio >= 0.92 or (jaccard >= 0.85 and (same_class or same_family))
        review = 0.85 <= ratio < 0.92 or 0.70 <= jaccard < 0.85
        if hard or review:
            pair = {
                "ids": sorted([str(left["id"]), str(right["id"])]),
                "metrics": metrics,
                "hard": hard,
                "review": review,
                "pair_fingerprint": sha256_value(
                    sorted([record_fingerprint(left), record_fingerprint(right)])
                ),
            }
            disposition = disposition_map.get(pair["pair_fingerprint"])
            if review and not hard and not disposition:
                pair["requires_disposition"] = True
            elif disposition:
                pair["disposition"] = disposition.get("disposition")
            findings.append(pair)
    return findings


def disposition_links(
    records: list[dict[str, Any]], dispositions: list[dict[str, Any]] | None
) -> list[tuple[str, str]]:
    by_fingerprint = {record_fingerprint(record): str(record["id"]) for record in records}
    links: list[tuple[str, str]] = []
    for disposition in dispositions or []:
        left_fp = str(disposition.get("candidate_a_fingerprint", ""))
        right_fp = str(disposition.get("candidate_b_fingerprint", ""))
        pair_fp = str(disposition.get("pair_fingerprint", ""))
        if left_fp not in by_fingerprint or right_fp not in by_fingerprint:
            raise SplitIntegrityError("stale_disposition_fingerprint")
        if sha256_value(sorted([left_fp, right_fp])) != pair_fp:
            raise SplitIntegrityError("stale_disposition_fingerprint")
        if disposition.get("disposition") == "same_family":
            links.append((by_fingerprint[left_fp], by_fingerprint[right_fp]))
    return links


def validate_candidate_manifest(
    manifest: dict[str, Any], allocation: dict[str, Any] | None = None
) -> dict[str, Any]:
    validate_schema(manifest, load_candidate_schema())
    records = manifest["records"]
    allocation = allocation or load_allocation()
    targets = allocation_targets(allocation)
    seen_ids: set[str] = set()
    seen_text: dict[str, str] = {}
    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    for record in records:
        record_id = str(record["id"])
        if not ID_PATTERN.fullmatch(record_id):
            raise SplitIntegrityError("invalid_query_id", record_id)
        if record_id in seen_ids:
            raise SplitIntegrityError("duplicate_query_id", record_id)
        seen_ids.add(record_id)
        text_key = canonical_text(str(record["query_text"]))
        if text_key in seen_text:
            raise SplitIntegrityError("duplicate_query_text", record_id)
        seen_text[text_key] = record_id
        if (
            record["class"] not in CLASS_NAMES
            or record["expected_behavior"] not in EXPECTED_BEHAVIORS
        ):
            raise SplitIntegrityError("invalid_query_class_or_behavior", record_id)
        cell = allocation_cell(record)
        if cell not in targets:
            raise SplitIntegrityError("unexpected_allocation_source", f"{cell[0]}:{cell[1]}")
        counts[cell] += 1
    dispositions = manifest.get("near_duplicate_review_dispositions")
    clusters = build_clusters(records, disposition_links(records, dispositions))
    findings = inspect_near_duplicates(records, dispositions)
    if any(item.get("hard") for item in findings):
        raise SplitIntegrityError("hard_near_duplicate", findings[0]["pair_fingerprint"])
    if any(item.get("requires_disposition") for item in findings):
        raise SplitIntegrityError("near_duplicate_review_required")
    for cluster in clusters:
        if len(cluster.strata) != 1:
            raise SplitIntegrityError("mixed_stratum_leakage_cluster")
    expected_total = sum(
        sum(values.values())
        for values in (
            class_data.get(split, {})
            for class_data in allocation["classes"].values()
            for split in ("calibration", "holdout")
        )
    )
    if len(records) != expected_total:
        raise SplitIntegrityError("candidate_total_mismatch", str(len(records)))
    for cell, values in targets.items():
        expected = values.get("calibration", 0) + values.get("holdout", 0)
        if counts[cell] != expected:
            raise SplitIntegrityError(
                "allocation_cell_total_mismatch", f"{cell}:{counts[cell]}!={expected}"
            )
    return {
        "records": records,
        "clusters": clusters,
        "counts": dict(counts),
        "targets": targets,
        "record_fingerprints": {str(r["id"]): record_fingerprint(r) for r in records},
        "near_duplicate_findings": findings,
    }


def _choose_subset(clusters: list[LeakageCluster], target: int) -> tuple[LeakageCluster, ...]:
    ordered = sorted(
        clusters,
        key=lambda cluster: (
            sha256_value({"algorithm_id": ALGORITHM_ID, "cluster": cluster.fingerprint}),
            cluster.fingerprint,
            cluster.record_ids,
        ),
    )
    states: dict[int, tuple[str, ...]] = {0: ()}
    for cluster in ordered:
        key = cluster.fingerprint
        for total, selected in sorted(list(states.items()), reverse=True):
            new_total = total + cluster.size
            if new_total > target or new_total in states:
                continue
            states[new_total] = tuple(sorted((*selected, key)))
    if target not in states:
        raise SplitIntegrityError("impossible_group_quota", str(target))
    selected_keys = set(states[target])
    return tuple(cluster for cluster in ordered if cluster.fingerprint in selected_keys)


def membership_sha(ids: list[str]) -> str:
    return sha256_value(sorted(ids))


def generate_split(
    manifest: dict[str, Any], allocation: dict[str, Any] | None = None
) -> dict[str, Any]:
    checked = validate_candidate_manifest(manifest, allocation)
    allocation = allocation or load_allocation()
    by_id = {str(record["id"]): record for record in checked["records"]}
    split_by_id: dict[str, str] = {}
    for cell, targets in checked["targets"].items():
        cell_clusters = [cluster for cluster in checked["clusters"] if cluster.strata == (cell,)]
        target = targets.get("calibration", 0)
        chosen = (
            {cluster.fingerprint for cluster in _choose_subset(cell_clusters, target)}
            if target
            else set()
        )
        for cluster in cell_clusters:
            split = "calibration" if cluster.fingerprint in chosen else "holdout"
            for record_id in cluster.record_ids:
                split_by_id[record_id] = split
    records = []
    for record_id in sorted(by_id):
        record = by_id[record_id]
        records.append(
            {
                "id": record_id,
                "split": split_by_id[record_id],
                "class": record["class"],
                "allocation_source_key": derive_allocation_source(record),
                "public_or_custom": public_or_custom(record),
                "group_id": record["group_id"],
                "template_fingerprint": record.get("template_fingerprint"),
                "record_fingerprint": checked["record_fingerprints"][record_id],
            }
        )
    split_manifest = {
        "schema_version": 1,
        "benchmark_version": manifest["benchmark_version"],
        "algorithm_id": ALGORITHM_ID,
        "candidate_manifest_sha256": sha256_value(manifest),
        "allocation_config_sha256": sha256_value(allocation),
        "approved_dataset_config_sha256": sha256_file(
            ROOT / "config" / "approved_eval_datasets.json"
        ),
        "record_count": len(records),
        "calibration_count": sum(item["split"] == "calibration" for item in records),
        "holdout_count": sum(item["split"] == "holdout" for item in records),
        "records": records,
    }
    validate_schema(split_manifest, load_split_schema())
    identity = {
        "seal_schema_version": SEAL_SCHEMA_VERSION,
        "benchmark_version": manifest["benchmark_version"],
        "algorithm_id": ALGORITHM_ID,
        "allocation_config_sha256": split_manifest["allocation_config_sha256"],
        "approved_dataset_config_sha256": split_manifest["approved_dataset_config_sha256"],
        "candidate_manifest_sha256": split_manifest["candidate_manifest_sha256"],
        "split_manifest_sha256": sha256_value(split_manifest),
        "calibration_membership_sha256": membership_sha(
            [item["id"] for item in records if item["split"] == "calibration"]
        ),
        "holdout_membership_sha256": membership_sha(
            [item["id"] for item in records if item["split"] == "holdout"]
        ),
        "group_membership_sha256": sha256_value(
            sorted((item["group_id"], item["split"]) for item in records)
        ),
        "record_count": len(records),
        "calibration_count": split_manifest["calibration_count"],
        "holdout_count": split_manifest["holdout_count"],
    }
    return {
        "split_manifest": split_manifest,
        "immutable_identity": identity,
        "split_identity_sha256": sha256_value(identity),
        "lifecycle": {"state": "sealed_unused", "events": []},
        "mutation_performed": False,
    }


def transition_lifecycle(
    seal: dict[str, Any], state: str, evidence_sha256: str, *, timestamp: str | None = None
) -> dict[str, Any]:
    allowed = {"sealed_unused": "scored_once", "scored_once": "retired_regression"}
    current = seal["lifecycle"]["state"]
    if allowed.get(current) != state:
        raise SplitIntegrityError("invalid_lifecycle_transition", f"{current}->{state}")
    previous = (
        seal["lifecycle"]["events"][-1]["event_hash"] if seal["lifecycle"]["events"] else "0" * 64
    )
    event = {
        "from": current,
        "to": state,
        "timestamp_utc": timestamp or datetime.now(UTC).isoformat(),
        "evidence_sha256": evidence_sha256,
        "previous_event_hash": previous,
    }
    event["event_hash"] = sha256_value(event)
    seal["lifecycle"]["events"].append(event)
    seal["lifecycle"]["state"] = state
    return seal


def verify_seal(seal: dict[str, Any]) -> None:
    identity = seal.get("immutable_identity")
    if not isinstance(identity, dict) or seal.get("split_identity_sha256") != sha256_value(
        identity
    ):
        raise SplitIntegrityError("seal_identity_mismatch")
    events = seal.get("lifecycle", {}).get("events", [])
    previous = "0" * 64
    for event in events:
        expected = dict(event)
        actual = expected.pop("event_hash", None)
        if event.get("previous_event_hash") != previous or actual != sha256_value(expected):
            raise SplitIntegrityError("lifecycle_chain_tampered")
        previous = actual
    if events and seal["lifecycle"]["state"] != events[-1]["to"]:
        raise SplitIntegrityError("lifecycle_state_mismatch")


def verify_config(allocation_path: Path | None = None) -> dict[str, Any]:
    allocation = load_allocation(allocation_path)
    targets = allocation_targets(allocation)
    totals = allocation.get("totals", {})
    expected = {"total": 600, "calibration": 300, "holdout": 300, "public": 315, "custom": 285}
    actual = {
        "total": totals.get("overall", {}).get("total"),
        "calibration": totals.get("calibration", {}).get("total"),
        "holdout": totals.get("holdout", {}).get("total"),
        "public": totals.get("overall", {}).get("public"),
        "custom": totals.get("overall", {}).get("custom"),
    }
    if actual != expected or sum(sum(values.values()) for values in targets.values()) != 600:
        raise SplitIntegrityError("allocation_totals_invalid")
    return {
        "verdict": "pass",
        "algorithm_id": ALGORITHM_ID,
        "allocation_config_sha256": sha256_file(
            allocation_path or ROOT / "config" / "query_allocation.yaml"
        ),
        "targets": {": ".join(key): value for key, value in sorted(targets.items())},
        "mutation_performed": False,
    }


def verify_gate0() -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts" / "verify_gate0_integrity.py"), "--verify"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise SplitIntegrityError("gate0_integrity_failed")


def verify_production_boundary() -> dict[str, Any]:
    verify_gate0()
    from natural_flow_rag.settings import load_settings
    from scripts.compare_reindex_plan import load_bm25_ids, load_current_records

    settings = load_settings()
    records, _ = load_current_records(settings)
    bm25_ids = load_bm25_ids(settings)
    eval_chroma = [
        str(item["id"])
        for item in records
        if item.get("metadata", {}).get("doc_type") == "evaluation_case"
    ]
    source_manifest = load_yaml(ROOT / "config" / "sources.yaml")
    findings = []
    exact_parity = sorted(str(item["id"]) for item in records) == sorted(bm25_ids)
    if len(records) != 96 or len(bm25_ids) != 96 or not exact_parity:
        findings.append("production_count_or_parity")
    if eval_chroma:
        findings.append("evaluation_record_in_chroma")
    for source in source_manifest.get("sources", []):
        if not isinstance(source, dict):
            findings.append("invalid_production_source_entry")
            continue
        path = str(source.get("path", ""))
        if (
            source.get("doc_type") == "evaluation_case"
            or path.startswith("eval/")
            or path.startswith("var/eval_sources/")
        ):
            findings.append("evaluation_source_in_production_manifest")
    return {
        "verdict": "pass" if not findings else "fail",
        "chroma_count": len(records),
        "bm25_count": len(bm25_ids),
        "exact_parity": exact_parity,
        "evaluation_case_count": len(eval_chroma),
        "findings": findings,
        "mutation_performed": False,
    }


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SplitIntegrityError("manifest_not_mapping")
    return payload


def atomic_generate(
    manifest: dict[str, Any], output_root: Path, *, confirm: bool = False
) -> dict[str, Any]:
    if not confirm or __import__("os").environ.get("NFR_ALLOW_EVAL_WRITES") != "true":
        raise SplitIntegrityError("write_authorization_required")
    output_root.mkdir(parents=True, exist_ok=True)
    final = output_root / f"{manifest['benchmark_version']}-{ALGORITHM_ID}"
    if final.exists():
        raise SplitIntegrityError("sealed_destination_exists")
    with tempfile.TemporaryDirectory(prefix="stage5-split-", dir=output_root) as temp_name:
        staging = Path(temp_name)
        seal = generate_split(manifest)
        (staging / "split_manifest.json").write_text(
            json.dumps(seal["split_manifest"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (staging / "seal.json").write_text(
            json.dumps(seal, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        staging.replace(final)
    return {"verdict": "pass", "output": str(final), "mutation_performed": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--verify-config", action="store_true")
    modes.add_argument("--verify-candidates", type=Path)
    modes.add_argument("--verify-production-boundary", action="store_true")
    modes.add_argument("--verify-seal", type=Path)
    modes.add_argument("--generate", type=Path)
    modes.add_argument("--mark-scored", type=Path)
    modes.add_argument("--retire", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--confirm-eval-split-generation", action="store_true")
    parser.add_argument("--confirm-holdout-scored", action="store_true")
    parser.add_argument("--confirm-holdout-retirement", action="store_true")
    parser.add_argument("--evidence-sha256")
    args = parser.parse_args()
    try:
        if args.verify_config:
            report = verify_config()
        elif args.verify_production_boundary:
            report = verify_production_boundary()
        elif args.verify_candidates:
            report = {
                "verdict": "pass",
                "candidate": validate_candidate_manifest(load_manifest(args.verify_candidates)),
                "mutation_performed": False,
            }
        elif args.verify_seal:
            seal = load_manifest(args.verify_seal)
            verify_seal(seal)
            report = {
                "verdict": "pass",
                "split_identity_sha256": seal["split_identity_sha256"],
                "lifecycle_state": seal["lifecycle"]["state"],
                "mutation_performed": False,
            }
        elif args.generate:
            report = atomic_generate(
                load_manifest(args.generate),
                args.output_root or Path("var/eval_split"),
                confirm=args.confirm_eval_split_generation,
            )
        elif args.mark_scored or args.retire:
            seal_path = args.mark_scored or args.retire
            if __import__("os").environ.get("NFR_ALLOW_EVAL_WRITES") != "true":
                raise SplitIntegrityError("write_authorization_required")
            if not args.evidence_sha256:
                raise SplitIntegrityError("evidence_sha256_required")
            if args.mark_scored and not args.confirm_holdout_scored:
                raise SplitIntegrityError("holdout_scored_confirmation_required")
            if args.retire and not args.confirm_holdout_retirement:
                raise SplitIntegrityError("holdout_retirement_confirmation_required")
            seal = load_manifest(seal_path)
            transition_lifecycle(
                seal,
                "scored_once" if args.mark_scored else "retired_regression",
                args.evidence_sha256,
            )
            seal_path.write_text(
                json.dumps(seal, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            report = {
                "verdict": "pass",
                "lifecycle_state": seal["lifecycle"]["state"],
                "mutation_performed": True,
            }
        else:
            raise SplitIntegrityError("unsupported_mode")
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, jsonschema.ValidationError, SplitIntegrityError) as exc:
        print(
            json.dumps(
                {"verdict": "fail", "finding": str(exc), "mutation_performed": False},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
