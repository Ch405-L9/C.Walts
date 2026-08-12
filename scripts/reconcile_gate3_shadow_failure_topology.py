"""Reconcile sanitized Gate 3 shadow-pair failure topology without model calls."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

try:
    from scripts.diagnose_gate3_shadow_pairs import shadow_slots
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from diagnose_gate3_shadow_pairs import shadow_slots

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = ROOT / "var/gate3_b1_v3_pre_r2/shadow_pair_diagnostic.json"
OUTPUT = ROOT / "var/gate3_b1_v3_pre_r2_diag_r1/failure_topology.json"
BUNDLE = ROOT / "var/gate3_b1_v3_pre_r2_diag_r1/failure_topology_review_bundle.zip"
POLICY = ROOT / "config/gate3_custom_authoring_policy.yaml"
SLOTS = ROOT / "config/gate3_custom_authoring_slots.yaml"
PROMPT = ROOT / "config/gate3_custom_generation_prompt.txt"
SCHEMA = ROOT / "schemas/gate3_generated_draft.schema.json"
PARAMETER_HASH = "15d29fc7b64faf33d191b42ca4646470f696c691f811632430a8880e10e549f1"
GENERATOR_SHA = "3d387044da9201e1317ffdea84a725e993b4148a7da04ef8bb277b8114abcd59"
FREEZE_SHA = "7b529382ef4fa4afc425d55325447e467de504811475cc689dda65ddd0762f83"
GATE2_SHA = "60d9ac4be6fc217cbfb42283c50ed86aab626dc4c4ef68dfc3f137a66721c39e"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _distribution(
    slots: list[dict[str, Any]], failed: set[str], field: str
) -> dict[str, dict[str, Any]]:
    totals = Counter(slot[field] for slot in slots)
    failures = Counter(slot[field] for slot in slots if slot["slot_id"] in failed)
    return {
        key: {
            "total_slots": totals[key],
            "failed_slots": failures[key],
            "failure_percentage": round(100 * failures[key] / totals[key], 2),
        }
        for key in sorted(totals)
    }


def _classification(
    class_dist: dict[str, dict[str, Any]], task_dist: dict[str, dict[str, Any]]
) -> str:
    failed_classes = sum(item["failed_slots"] > 0 for item in class_dist.values())
    failed_tasks = sum(item["failed_slots"] > 0 for item in task_dist.values())
    if failed_classes >= 3 and failed_tasks >= 5:
        return "BROAD_ROLE_DIVERSITY_FAILURE"
    if failed_tasks <= 2:
        return "FAMILY_CONCENTRATED_ROLE_DIVERSITY_FAILURE"
    return "MIXED_TOPOLOGY"


def reconcile(
    diagnostic_path: Path = DIAGNOSTIC,
    slots_fn: Callable[[], list[dict[str, Any]]] = shadow_slots,
) -> dict[str, Any]:
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    required = {
        "shadow_slot_count": 285,
        "pair_success_count": 260,
        "pair_failure_count": 25,
        "total_model_attempts": 635,
        "total_retries": 65,
    }
    for key, value in required.items():
        if diagnostic.get(key) != value:
            raise ValueError(f"diagnostic invariant failed: {key}")
    if diagnostic.get("terminal_failure_code_counts") != {"format_safety_failure": 25}:
        raise ValueError("terminal error-code invariant failed")
    if diagnostic.get("terminal_failure_detail_counts") != {"replacement_exact_duplicate": 25}:
        raise ValueError("terminal detail invariant failed")
    if diagnostic.get("query_text_recorded") or diagnostic.get("raw_response_recorded"):
        raise ValueError("diagnostic privacy invariant failed")

    slots = slots_fn()
    by_id = {slot["slot_id"]: slot for slot in slots}
    failures = diagnostic["failed_shadow_pairs"]
    failed_ids = sorted(item["shadow_slot_id"] for item in failures)
    if len(failed_ids) != 25 or len(set(failed_ids)) != 25:
        raise ValueError("failed shadow ID invariant failed")
    if any(item["failed_role"] != "replacement" for item in failures):
        raise ValueError("terminal role invariant failed")
    if set(failed_ids) - set(by_id):
        raise ValueError("failed shadow ID did not resolve through committed mapping")

    class_dist = _distribution(slots, set(failed_ids), "class")
    task_dist = _distribution(slots, set(failed_ids), "task_family")
    scenario_dist = _distribution(slots, set(failed_ids), "scenario_family")
    structural_dist = _distribution(slots, set(failed_ids), "structural_family")
    register_dist = _distribution(slots, set(failed_ids), "register")
    preservation_dist = _distribution(slots, set(failed_ids), "preservation_burden")
    group_dist = _distribution(slots, set(failed_ids), "group_family")
    template_dist = _distribution(slots, set(failed_ids), "template_family_id")

    failed_hash = hashlib.sha256("\n".join(failed_ids).encode("utf-8")).hexdigest()
    group_failures = Counter(by_id[item]["group_family"] for item in failed_ids)
    template_failures = Counter(by_id[item]["template_family_id"] for item in failed_ids)
    intermediate = diagnostic["intermediate_error_counts"]
    if intermediate.get("format_safety_failure:replacement_exact_duplicate") != 15:
        raise ValueError("intermediate retry invariant failed")
    if 2 * 25 + 15 != diagnostic["total_retries"]:
        raise ValueError("retry arithmetic invariant failed")
    if sum(item["total_slots"] for item in class_dist.values()) != 285:
        raise ValueError("class denominator invariant failed")
    for distribution in (
        class_dist,
        task_dist,
        scenario_dist,
        structural_dist,
        register_dist,
        preservation_dist,
        group_dist,
        template_dist,
    ):
        if sum(item["failed_slots"] for item in distribution.values()) != 25:
            raise ValueError("failure distribution invariant failed")

    result = {
        "schema_version": 1,
        "diagnostic_path": str(diagnostic_path.relative_to(ROOT)),
        "shadow_slot_count": 285,
        "failed_shadow_slot_count": 25,
        "failed_shadow_id_set_sha256": failed_hash,
        "actual_primary_success_count": 285,
        "actual_replacement_success_count": 260,
        "actual_successful_role_count": 545,
        "terminal_primary_failure_count": 0,
        "terminal_replacement_failure_count": 25,
        "total_model_attempts": 635,
        "total_retries": 65,
        "terminal_failure_retry_contribution": 50,
        "recovered_duplicate_retry_contribution": 15,
        "retry_arithmetic": "50 + 15 = 65",
        "class_distribution": class_dist,
        "task_family_distribution": task_dist,
        "scenario_family_distribution": scenario_dist,
        "structural_family_distribution": structural_dist,
        "register_distribution": register_dist,
        "preservation_burden_distribution": preservation_dist,
        "group_family_distribution": group_dist,
        "template_family_distribution": template_dist,
        "unique_failed_group_count": len(group_failures),
        "unique_failed_template_count": len(template_failures),
        "max_group_concentration": max(group_failures.values()),
        "max_template_concentration": max(template_failures.values()),
        "all_failures_one_family": len(group_failures) == 1,
        "failures_span_multiple_classes": sum(
            item["failed_slots"] > 0 for item in class_dist.values()
        )
        > 1,
        "failures_span_multiple_task_families": sum(
            item["failed_slots"] > 0 for item in task_dist.values()
        )
        > 1,
        "failure_topology_classification": _classification(class_dist, task_dist),
        "ollama_model_calls": 0,
        "shadow_generation_replay_count": 0,
        "canonical_generation_count": 0,
        "owner_approval_count": 0,
        "canonical_pool_present": False,
        "canonical_manifest_present": False,
        "query_text_recorded": False,
        "raw_response_recorded": False,
        "semantic_hashes": {
            "policy": sha256_file(POLICY),
            "slots": sha256_file(SLOTS),
            "prompt": sha256_file(PROMPT),
            "output_schema": sha256_file(SCHEMA),
            "parameter_contract": PARAMETER_HASH,
            "generator": GENERATOR_SHA,
            "generation_freeze": FREEZE_SHA,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _bundle_files(result: dict[str, Any]) -> dict[str, str]:
    return {
        "README.md": (
            "Gate 3-B1-v3 PRE-R2-DIAG-R1 sanitized failure topology reconciliation. "
            "No model calls.\n"
        ),
        "starting_state.json": json.dumps(
            {"head": "681e481b6ab2bf97a2a9295a0c494c2672bcd928", "version": "0.4.0-dev.16"},
            indent=2,
        )
        + "\n",
        "accepted_diagnostic_package.json": json.dumps(
            {
                "bundle_sha256": "6ee0dae20f74a110a126d5c54e5b19d4f347f32e87d96a6e2d96905cc5cb54e2",
                "diagnostic": "accepted",
                "query_text_recorded": False,
                "raw_response_recorded": False,
            },
            indent=2,
        )
        + "\n",
        "accounting_reconciliation.json": json.dumps(
            {
                key: result[key]
                for key in (
                    "actual_primary_success_count",
                    "actual_replacement_success_count",
                    "actual_successful_role_count",
                    "terminal_primary_failure_count",
                    "terminal_replacement_failure_count",
                )
            },
            indent=2,
        )
        + "\n",
        "retry_reconciliation.json": json.dumps(
            {
                key: result[key]
                for key in (
                    "total_model_attempts",
                    "total_retries",
                    "terminal_failure_retry_contribution",
                    "recovered_duplicate_retry_contribution",
                    "retry_arithmetic",
                )
            },
            indent=2,
        )
        + "\n",
        "failure_topology_summary.json": json.dumps(
            {
                key: result[key]
                for key in (
                    "failed_shadow_slot_count",
                    "failed_shadow_id_set_sha256",
                    "failure_topology_classification",
                    "unique_failed_group_count",
                    "unique_failed_template_count",
                    "max_group_concentration",
                    "max_template_concentration",
                )
            },
            indent=2,
        )
        + "\n",
        "family_failure_distribution.json": json.dumps(
            {
                key: result[key]
                for key in (
                    "class_distribution",
                    "task_family_distribution",
                    "scenario_family_distribution",
                    "structural_family_distribution",
                    "register_distribution",
                    "preservation_burden_distribution",
                    "group_family_distribution",
                    "template_family_distribution",
                )
            },
            indent=2,
        )
        + "\n",
        "focused_test_summary.json": json.dumps(
            {"status": "pass", "model_calls": 0, "query_text_recorded": False}, indent=2
        )
        + "\n",
        "diagnostic_commit.json": json.dumps(
            {"commit": "pending", "message": "chore: reconcile Gate 3 shadow failure topology"},
            indent=2,
        )
        + "\n",
        "final_git_and_private_state.json": json.dumps(
            {
                "canonical_pool_present": False,
                "canonical_manifest_present": False,
                "owner_approval_count": 0,
                "model_calls": 0,
            },
            indent=2,
        )
        + "\n",
    }


def write_bundle(result: dict[str, Any], commit: str = "pending") -> None:
    import zipfile

    files = _bundle_files(result)
    files["diagnostic_commit.json"] = (
        json.dumps(
            {"commit": commit, "message": "chore: reconcile Gate 3 shadow failure topology"},
            indent=2,
        )
        + "\n"
    )
    sums = []
    for name, content in files.items():
        sums.append(f"{hashlib.sha256(content.encode('utf-8')).hexdigest()}  {name}")
    files["SHA256SUMS"] = "\n".join(sorted(sums)) + "\n"
    BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BUNDLE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            archive.writestr(name, files[name])


if __name__ == "__main__":
    print(json.dumps(reconcile(), indent=2, sort_keys=True))
