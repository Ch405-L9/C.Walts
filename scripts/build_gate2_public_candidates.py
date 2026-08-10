#!/usr/bin/env python3
"""Gate 2-A metadata inventory and policy checks; canonical selection is reserved for Gate 2-B."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
CLINC = ROOT / "var/eval_sources/extracted/clinc150/clinc150_uci/data_full.json"
MASSIVE = ROOT / "var/eval_sources/extracted/massive_1_0_en_us/1.0/data/en-US.jsonl"
BANK_ROOT = ROOT / "var/eval_sources/extracted/banking77/task-specific-datasets-master/banking_data"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_text(value: str) -> str:
    import unicodedata

    value = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(" ".join(line.split()) for line in value.split("\n")).strip()


def exact_base_group_dp(
    groups: list[tuple[str, int]], calibration_target: int, holdout_target: int
) -> dict:
    """Prove exact assignment of whole base groups without writing membership."""
    ordered = sorted(groups, key=lambda item: (item[0], item[1]))
    states: dict[tuple[int, int], str] = {(0, 0): ""}
    for fingerprint, size in ordered:
        next_states = dict(states)
        for (calibration, holdout), proof in sorted(states.items()):
            if calibration + size <= calibration_target:
                next_states.setdefault((calibration + size, holdout), proof + f"C:{fingerprint};")
            if holdout + size <= holdout_target:
                next_states.setdefault((calibration, holdout + size), proof + f"H:{fingerprint};")
        states = next_states
    target = (calibration_target, holdout_target)
    proof_material = {
        "groups": ordered,
        "target": [calibration_target, holdout_target],
        "reachable_state_count": len(states),
        "target_reachable": target in states,
    }
    return {
        "exact_base_group_feasible": target in states,
        "target": {"calibration": calibration_target, "holdout": holdout_target},
        "base_group_count": len(ordered),
        "reachable_state_count": len(states),
        "feasibility_proof_sha256": digest(json.dumps(proof_material, sort_keys=True)),
        "membership_written": False,
    }


def structure() -> dict:
    clinc = json.loads(CLINC.read_text())
    clinc_counts = {
        part: dict(sorted(collections.Counter(row[1] for row in rows).items()))
        for part, rows in clinc.items()
    }
    massive_rows = [json.loads(line) for line in MASSIVE.read_text().splitlines()]
    massive_counts = {
        "partition": dict(
            sorted(collections.Counter(row["partition"] for row in massive_rows).items())
        ),
        "scenario": dict(
            sorted(collections.Counter(row["scenario"] for row in massive_rows).items())
        ),
        "intent": dict(sorted(collections.Counter(row["intent"] for row in massive_rows).items())),
    }
    import csv

    banking = {}
    for part in ("train", "test"):
        with (BANK_ROOT / f"{part}.csv").open(newline="") as f:
            rows = list(csv.DictReader(f))
        banking[part] = {
            "count": len(rows),
            "category_counts": dict(
                sorted(collections.Counter(row["category"] for row in rows).items())
            ),
        }
    return {
        "schema_version": 1,
        "query_text_included": False,
        "clinc150": {"top_level_keys": sorted(clinc), "partitions": clinc_counts},
        "massive_1_0_en_us": {
            "fields": sorted(massive_rows[0]),
            "count": len(massive_rows),
            "counts": massive_counts,
        },
        "banking77": banking,
    }


CLINC_NEAR = {
    "calculator",
    "change_language",
    "definition",
    "directions",
    "distance",
    "exchange_rate",
    "gas",
    "ingredient_substitution",
    "ingredients_list",
    "measurement_conversion",
    "nutrition_info",
    "recipe",
    "spelling",
    "translate",
    "weather",
}
MASSIVE_NEAR_SCENARIOS = {
    "calendar",
    "datetime",
    "email",
    "general",
    "lists",
    "qa",
    "recommendation",
    "transport",
    "weather",
}
MASSIVE_LABEL_OVERRIDES = {
    "cooking_recipe": "ineligible_for_gate2_public",
    "qa_factoid": "ineligible_for_gate2_public",
    "iot_coffee": "near_domain_unsupported",
    "alarm_query": "near_domain_unsupported",
    "takeaway_order": "near_domain_unsupported",
    "play_music": "near_domain_unsupported",
    "weather_query": "ineligible_for_gate2_public",
    "recommendation_locations": "ineligible_for_gate2_public",
}


def freeze_policy() -> None:
    clinc = json.loads(CLINC.read_text())
    clinc_labels = sorted({row[1] for key in ("train", "val", "test") for row in clinc[key]})
    massive_rows = [json.loads(line) for line in MASSIVE.read_text().splitlines()]
    massive_intent_scenario = {}
    for row in massive_rows:
        massive_intent_scenario.setdefault(row["intent"], row["scenario"])
        if massive_intent_scenario[row["intent"]] != row["scenario"]:
            raise SystemExit(f"massive_intent_spans_scenarios:{row['intent']}")
    massive_map = {
        intent: MASSIVE_LABEL_OVERRIDES.get(
            intent,
            "near_domain_unsupported"
            if scenario in MASSIVE_NEAR_SCENARIOS
            else "far_out_of_domain",
        )
        for intent, scenario in sorted(massive_intent_scenario.items())
    }
    import csv

    with (BANK_ROOT / "train.csv").open(newline="") as f:
        bank_labels = sorted({row["category"] for row in csv.DictReader(f)})
    policy = {
        "schema_version": 1,
        "policy_id": "gate2-public-selection-v1",
        "benchmark_version": "0.4",
        "candidate_schema": "schemas/eval_candidate_manifest.schema.json",
        "provenance_kind": "public_verbatim",
        "id_namespace": {
            "prefix": "CWQ-PUB",
            "first": 1,
            "last": 315,
            "pattern": "^CWQ-PUB-[0-9]{4}$",
        },
        "acquisition_to_allocation": {
            "clinc150": "clinc150",
            "clinc150_oos": "clinc150",
            "massive_en_us": "massive_1_0_en_us",
            "banking77": "banking77",
        },
        "quotas": {
            "near_domain_unsupported": {"clinc150": 60, "massive_en_us": 45},
            "far_out_of_domain": {"massive_en_us": 90, "banking77": 45},
            "ambiguous_adversarial_insufficient": {"clinc150_oos": 75},
            "public_total": 315,
        },
        "partition_policy": {
            "clinc150": ["train", "val", "test"],
            "massive_1_0_en_us": ["train", "dev", "test"],
            "banking77": ["train", "test"],
        },
        "label_policy": {
            "clinc150": {
                label: (
                    "near_domain_unsupported"
                    if label in CLINC_NEAR
                    else "ineligible_for_gate2_public"
                )
                for label in clinc_labels
            },
            "massive_1_0_en_us": massive_map,
            "banking77": {label: "far_out_of_domain" for label in bank_labels},
            "clinc150_oos": {
                part: "ambiguous_adversarial_insufficient"
                for part in ("oos_train", "oos_val", "oos_test")
            },
        },
        "expected_behavior": {
            "near_domain_unsupported": "request_clarification",
            "far_out_of_domain": "abstain",
            "ambiguous_adversarial_insufficient": "request_clarification",
        },
        "expected_behavior_by_label": {
            "clinc150": {label: "request_clarification" for label in sorted(CLINC_NEAR)},
            "massive_1_0_en_us": {
                label: (
                    "request_clarification" if value == "near_domain_unsupported" else "abstain"
                )
                for label, value in massive_map.items()
                if value != "ineligible_for_gate2_public"
            },
            "banking77": {label: "abstain" for label in bank_labels},
            "clinc150_oos": {
                part: "request_clarification" for part in ("oos_train", "oos_val", "oos_test")
            },
        },
        "mixed_cluster_resolution": {
            "method": "frozen_label_disposition_before_selection",
            "overrides": MASSIVE_LABEL_OVERRIDES,
            "reason": (
                "deterministic exact-duplicate families must not cross Gate 2 strata; "
                "qa_factoid is excluded because it overlaps official CLINC OOS material"
            ),
            "post_policy_behavior": "any remaining mixed cluster is a hard failure",
        },
        "group_policy": {
            "algorithm_id": "gate2-source-leakage-group-v1",
            "format": "G2-<dataset-short>-<sha256-prefix>",
            "singleton_rule": "only when no source/template relationship is evidenced",
            "union_rules": [
                "exact canonical duplicate",
                "material template family",
                "source-provided common family",
                "Stage 5 same_family disposition",
            ],
            "template_priority": [
                "source_provided_family",
                "deterministic_structural_family",
                "null",
            ],
        },
        "duplicate_policy": {
            "exact": "canonical_text_global_hard_reject",
            "near": "reuse_stage5_exhaustive_comparison_and_fingerprint_bound_dispositions",
            "mixed_stratum_failure": "mixed_stratum_leakage_cluster",
        },
        "balance_algorithm": (
            "balanced_round_robin_over_sha256_sorted_eligible_labels_with_exact_"
            "whole_cluster_resolution"
        ),
        "future_split_constraints": {
            "near_clinc150": [45, 15],
            "near_massive_en_us": [30, 15],
            "far_massive_en_us": [50, 40],
            "far_banking77": [25, 20],
            "ambiguous_clinc150_oos": [75, 0],
        },
        "no_performance_peek": True,
        "no_split": True,
    }
    (ROOT / "config/gate2_public_selection_policy.yaml").write_text(
        yaml.safe_dump(policy, sort_keys=False), encoding="utf-8"
    )


def preselection_analysis() -> dict:
    policy = yaml.safe_load((ROOT / "config/gate2_public_selection_policy.yaml").read_text())
    clinc = json.loads(CLINC.read_text())
    massive_rows = [json.loads(line) for line in MASSIVE.read_text().splitlines()]
    import csv

    banking_rows = []
    for partition in ("train", "test"):
        with (BANK_ROOT / f"{partition}.csv").open(newline="") as f:
            banking_rows.extend({**row, "_partition": partition} for row in csv.DictReader(f))
    strata = collections.defaultdict(list)

    def add(
        dataset: str, allocation: str, label: str, partition: str, text: str, native: str | None
    ) -> None:
        disposition = policy["label_policy"][
            dataset if dataset != "clinc150_oos" else "clinc150_oos"
        ][label if dataset != "clinc150_oos" else partition]
        if disposition == "ineligible_for_gate2_public":
            return
        class_name = disposition
        key = (class_name, allocation)
        canonical = canonical_text(text)
        strata[key].append(
            {
                "text_sha256": digest(canonical),
                "label": label,
                "partition": partition,
                "native": native,
            }
        )

    for partition in ("train", "val", "test"):
        for row in clinc[partition]:
            add("clinc150", "clinc150", row[1], partition, row[0], None)
    for partition in ("oos_train", "oos_val", "oos_test"):
        for row in clinc[partition]:
            add("clinc150_oos", "clinc150_oos", "oos", partition, row[0], None)
    for row in massive_rows:
        add(
            "massive_1_0_en_us",
            "massive_en_us",
            row["intent"],
            row["partition"],
            row["utt"],
            str(row["id"]),
        )
    for row in banking_rows:
        add("banking77", "banking77", row["category"], row["_partition"], row["text"], None)
    quota_map = {
        ("near_domain_unsupported", "clinc150"): 60,
        ("near_domain_unsupported", "massive_en_us"): 45,
        ("far_out_of_domain", "massive_en_us"): 90,
        ("far_out_of_domain", "banking77"): 45,
        ("ambiguous_adversarial_insufficient", "clinc150_oos"): 75,
    }
    future_map = {
        ("near_domain_unsupported", "clinc150"): [45, 15],
        ("near_domain_unsupported", "massive_en_us"): [30, 15],
        ("far_out_of_domain", "massive_en_us"): [50, 40],
        ("far_out_of_domain", "banking77"): [25, 20],
        ("ambiguous_adversarial_insufficient", "clinc150_oos"): [75, 0],
    }
    result = {}
    all_hashes = collections.defaultdict(list)
    for key, rows in sorted(strata.items()):
        for row in rows:
            all_hashes[row["text_sha256"]].append(key)
        sizes = collections.Counter(row["text_sha256"] for row in rows)
        quota = quota_map[key]
        targets = future_map[key]
        dp = exact_base_group_dp(sorted(sizes.items()), targets[0], targets[1])
        result[f"{key[0]}/{key[1]}"] = {
            "eligible_record_count": len(rows),
            "eligible_label_count": len({row["label"] for row in rows}),
            "eligible_partition_count": len({row["partition"] for row in rows}),
            "exact_duplicate_family_count": sum(1 for size in sizes.values() if size > 1),
            "base_group_count": len(sizes),
            "eligible_cluster_count": len(sizes),
            "base_group_definition": (
                "exact canonical-text duplicate identity; "
                "final Stage 5 clusters remain pending"
            ),
            "cluster_size_histogram": dict(sorted(collections.Counter(sizes.values()).items())),
            "public_quota": quota,
            "future_calibration_holdout": targets,
            "public_quota_feasible": dp["exact_base_group_feasible"],
            "future_split_feasible": dp["exact_base_group_feasible"],
            "exact_base_group_feasible": dp["exact_base_group_feasible"],
            "feasibility_proof_sha256": dp["feasibility_proof_sha256"],
            "reachable_state_count": dp["reachable_state_count"],
            "membership_written": False,
        }
    mixed = sum(1 for keys in all_hashes.values() if len(set(keys)) > 1)
    return {
        "schema_version": 1,
        "selection_executed": False,
        "query_text_included": False,
        "strata": result,
        "mixed_stratum_exact_duplicate_families": mixed,
        "preselection_feasibility_level": "exact_whole_base_group_dp",
        "final_leakage_cluster_feasibility": "pending_gate2_b_final_candidate_validation",
        "future_split_algorithm": "whole-base-group exact DP; no membership written",
        "verdict": "pass"
        if all(v["public_quota_feasible"] and v["future_split_feasible"] for v in result.values())
        and mixed == 0
        else "fail",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument("--verify-policy", action="store_true")
    parser.add_argument("--verify-acquisition", action="store_true")
    parser.add_argument("--feasibility", action="store_true")
    parser.add_argument("--freeze-policy", action="store_true")
    parser.add_argument("--select", action="store_true")
    args = parser.parse_args()
    if args.select:
        raise SystemExit("canonical_selection_reserved_for_gate2_b")
    if args.freeze_policy:
        freeze_policy()
        print("policy frozen")
        return 0
    policy_path = ROOT / "config/gate2_public_selection_policy.yaml"
    if args.verify_policy or args.feasibility:
        policy = yaml.safe_load(policy_path.read_text())
        schema = json.loads(
            (ROOT / "schemas/gate2_public_selection_policy.schema.json").read_text()
        )
        jsonschema.validate(policy, schema)
        if (
            policy["quotas"]["public_total"] != 315
            or policy["provenance_kind"] != "public_verbatim"
        ):
            raise SystemExit("policy_contract_failed")
    if args.verify_acquisition:
        from verify_eval_acquisition import main as verify

        old = sys.argv[:]
        sys.argv = ["verify_eval_acquisition.py"]
        verify()
        sys.argv = old
    if args.inventory:
        print(json.dumps(structure(), sort_keys=True, indent=2))
    if args.feasibility:
        print(json.dumps(preselection_analysis(), sort_keys=True, indent=2))
    if not any(
        (args.inventory, args.verify_policy, args.verify_acquisition, args.feasibility, args.select)
    ):
        raise SystemExit("select_a_gate2_a_mode")
    return 0


if __name__ == "__main__":
    sys.exit(main())
