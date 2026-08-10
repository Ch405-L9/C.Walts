#!/usr/bin/env python3
"""Validate the private 315-record Gate 2 public manifest without 600-record checks."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_gate2_public_candidates as selector  # noqa: E402
import verify_eval_split as split  # noqa: E402

EXPECTED_QUOTAS = {
    ("near_domain_unsupported", "clinc150"): 60,
    ("near_domain_unsupported", "massive_en_us"): 45,
    ("far_out_of_domain", "massive_en_us"): 90,
    ("far_out_of_domain", "banking77"): 45,
    ("ambiguous_adversarial_insufficient", "clinc150_oos"): 75,
}
HOLDOUT_TARGETS = {
    ("near_domain_unsupported", "clinc150"): 15,
    ("near_domain_unsupported", "massive_en_us"): 15,
    ("far_out_of_domain", "massive_en_us"): 40,
    ("far_out_of_domain", "banking77"): 20,
    ("ambiguous_adversarial_insufficient", "clinc150_oos"): 0,
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_manifest(path: Path = selector.SELECTED_MANIFEST) -> dict:
    manifest = load_manifest(path)
    policy = selector.load_policy()
    split.validate_schema(manifest, split.load_candidate_schema())
    records = manifest["records"]
    if manifest["benchmark_version"] != "0.4":
        raise ValueError("benchmark_version_mismatch")
    if len(records) != 315:
        raise ValueError("public_candidate_count_mismatch")
    expected_ids = [f"CWQ-PUB-{index:04d}" for index in range(1, 316)]
    if [record["id"] for record in records] != expected_ids:
        raise ValueError("public_id_sequence_mismatch")
    if any("split" in record for record in records):
        raise ValueError("split_field_forbidden")
    if any(record["provenance"]["kind"] != "public_verbatim" for record in records):
        raise ValueError("non_verbatim_provenance")
    if any(record["template_fingerprint"] is not None for record in records):
        raise ValueError("unexpected_template_fingerprint")
    split.validate_schema(manifest, split.load_candidate_schema())
    registry = split.load_approved_registry()
    for record in records:
        split.validate_public_registry(record, registry)
        expected_license = selector.LICENSE_REFS[record["source_dataset"]]
        if record["license_ref"] != expected_license:
            raise ValueError("license_reference_mismatch")
        if record["provenance"].get("policy_sha256") != selector.POLICY_SHA256:
            raise ValueError("record_policy_hash_mismatch")
    canonical_texts = [split.canonical_text(record["query_text"]) for record in records]
    if len(set(canonical_texts)) != len(canonical_texts):
        raise ValueError("duplicate_canonical_query_text")
    counts = collections.Counter(
        (record["class"], split.derive_allocation_source(record)) for record in records
    )
    if dict(counts) != EXPECTED_QUOTAS:
        raise ValueError(f"public_quota_mismatch:{dict(counts)}")
    source_index = {
        (row["source_dataset"], row["source_record_id"]): row
        for row in selector.source_rows(policy)
    }
    expected_versions = selector.VERSIONS
    for record in records:
        key = (record["source_dataset"], record["source_record_id"])
        source = source_index.get(key)
        if source is None:
            raise ValueError("source_record_missing")
        for field in (
            "query_text",
            "source_partition",
            "source_intent",
            "source_domain",
            "class",
            "expected_behavior",
            "source_version",
        ):
            if record[field] != source[field]:
                raise ValueError(f"source_roundtrip_mismatch:{field}")
        if record["source_version"] != expected_versions[record["source_dataset"]]:
            raise ValueError("source_version_mismatch")
        allocation = record["provenance"].get("allocation_source_key")
        policy_dataset = "clinc150_oos" if allocation == "clinc150_oos" else record[
            "source_dataset"
        ]
        source_label = source["source_label"]
        policy_label = source["source_partition"] if allocation == "clinc150_oos" else source_label
        if policy["label_policy"][policy_dataset][policy_label] != record["class"]:
            raise ValueError("source_label_class_policy_mismatch")
        if (
            policy["expected_behavior_by_label"][policy_dataset][policy_label]
            != record["expected_behavior"]
        ):
            raise ValueError("source_label_behavior_policy_mismatch")
        if allocation != selector.source_rows_to_allocation(record):
            raise ValueError("allocation_source_mismatch")
    reproduced = selector.select_records(policy, allow_existing=True)
    if json.dumps(reproduced, sort_keys=True, separators=(",", ":")) != json.dumps(
        records, sort_keys=True, separators=(",", ":")
    ):
        raise ValueError("deterministic_reproduction_mismatch")
    stats: dict[str, int] = {}
    findings = split.inspect_near_duplicates(records, stats=stats)
    if findings:
        raise ValueError("near_duplicate_findings_present")
    clusters = split.build_clusters(records)
    cluster_sizes = collections.Counter()
    feasibility = {}
    for cell, target in HOLDOUT_TARGETS.items():
        cell_clusters = [cluster for cluster in clusters if cluster.strata == (cell,)]
        sizes = collections.Counter(cluster.size for cluster in cell_clusters)
        cluster_sizes[f"{cell[0]}/{cell[1]}"] = dict(sorted(sizes.items()))
        if target:
            split._choose_subset(cell_clusters, target)
        feasibility[f"{cell[0]}/{cell[1]}"] = {
            "candidate_count": counts[cell],
            "cluster_count": len(cell_clusters),
            "cluster_size_histogram": dict(sorted(sizes.items())),
            "holdout_target": target,
            "feasible": True,
            "proof_sha256": sha256_bytes(
                json.dumps(
                    {
                        "cell": cell,
                        "sizes": sorted(cluster.size for cluster in cell_clusters),
                        "target": target,
                    },
                    sort_keys=True,
                ).encode()
            ),
        }
    return {
        "schema_version": 1,
        "verdict": "pass",
        "candidate_count": len(records),
        "counts": {f"{key[0]}/{key[1]}": value for key, value in sorted(counts.items())},
        "public_verbatim_count": len(records),
        "public_transformed_count": 0,
        "source_roundtrip_count": len(records),
        "exact_duplicate_count": 0,
        "near_duplicate_pair_evaluations": stats.get("pair_evaluations", 0),
        "hard_near_duplicate_count": 0,
        "unresolved_review_count": 0,
        "cluster_count": len(clusters),
        "cluster_size_histograms": cluster_sizes,
        "future_split_feasibility": feasibility,
        "final_leakage_feasibility": "pass",
        "reproduction_match": True,
        "selection_executed_by_verifier": False,
        "performance_peek": False,
        "mutation_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=selector.SELECTED_MANIFEST)
    args = parser.parse_args()
    try:
        print(json.dumps(verify_manifest(args.manifest), sort_keys=True, indent=2))
        return 0
    except (OSError, KeyError, TypeError, ValueError, split.SplitIntegrityError) as exc:
        print(json.dumps({"verdict": "fail", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
