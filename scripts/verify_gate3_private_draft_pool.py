"""Validate the private Gate 3-B1 draft pool without exposing its text."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import jsonschema
import yaml

try:
    from scripts import verify_eval_split as split
    from scripts.gate3_private_common import (
        CONFLICT_RELATIVE,
        DRAFT_SCHEMA,
        FREEZE,
        GATE2_PUBLIC_MANIFEST,
        GENERATOR,
        POLICY,
        READINESS_RELATIVE,
        SLOTS,
        PrivateAuthoringError,
        atomic_write_bytes,
        canonical_sha256,
        derive_draft_fingerprint,
        derive_group_id,
        derive_template_fingerprint,
        file_sha256,
        load_freeze,
        resolve_private_path,
        verify_gate2_manifest_identity,
    )
except ModuleNotFoundError:  # pragma: no cover
    import verify_eval_split as split
    from gate3_private_common import (
        CONFLICT_RELATIVE,
        DRAFT_SCHEMA,
        FREEZE,
        GATE2_PUBLIC_MANIFEST,
        GENERATOR,
        POLICY,
        READINESS_RELATIVE,
        SLOTS,
        PrivateAuthoringError,
        atomic_write_bytes,
        canonical_sha256,
        derive_draft_fingerprint,
        derive_group_id,
        derive_template_fingerprint,
        file_sha256,
        load_freeze,
        resolve_private_path,
        verify_gate2_manifest_identity,
    )

EXPECTED_ROLES = ("primary", "replacement")


def _draft_view(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["draft_id"],
        "query_text": record["query_text"],
        "class": record["class"],
        "expected_behavior": record["expected_behavior"],
        "source_dataset": "custom",
        "source_version": "cwalts-custom-v0.4-gate3-v2",
        "source_record_id": record["slot_id"],
        "group_id": record["group_id"],
        "template_fingerprint": record["template_fingerprint"],
        "provenance": {"kind": "vendor_generated_owner_approved"},
    }


def _near_kind(left: dict[str, Any], right: dict[str, Any]) -> tuple[bool, bool, dict[str, Any]]:
    metrics = split.similarity_pair(left["query_text"], right["query_text"])
    ratio = metrics["sequence_matcher_ratio"]
    jaccard = metrics["token_3gram_jaccard"]
    hard = ratio >= 0.92 or (
        jaccard is not None
        and jaccard >= 0.85
        and (
            left.get("class") == right.get("class")
            or left.get("template_fingerprint") == right.get("template_fingerprint")
        )
    )
    review = 0.85 <= ratio < 0.92 or (jaccard is not None and 0.70 <= jaccard < 0.85)
    return hard, review, metrics


def _two_sat(slot_ids: list[str], edges: list[tuple[str, str, str, str]]) -> tuple[bool, str]:
    """Solve one-role-per-slot clauses deterministically with SCCs."""
    index = {slot: n for n, slot in enumerate(slot_ids)}
    node_count = len(slot_ids) * 2
    graph: list[list[int]] = [[] for _ in range(node_count)]
    reverse: list[list[int]] = [[] for _ in range(node_count)]

    def literal(slot: str, role: str) -> int:
        return 2 * index[slot] + (0 if role == "primary" else 1)

    def negate(node: int) -> int:
        return node ^ 1

    for left_slot, left_role, right_slot, right_role in sorted(edges):
        left = literal(left_slot, left_role)
        right = literal(right_slot, right_role)
        for source, target in ((left, negate(right)), (right, negate(left))):
            graph[source].append(target)
            reverse[target].append(source)
    for adjacency in graph + reverse:
        adjacency.sort()
    visited = [False] * node_count
    order: list[int] = []

    def visit(node: int) -> None:
        visited[node] = True
        for target in graph[node]:
            if not visited[target]:
                visit(target)
        order.append(node)

    for node in range(node_count):
        if not visited[node]:
            visit(node)
    components = [-1] * node_count

    def assign(node: int, component: int) -> None:
        components[node] = component
        for target in reverse[node]:
            if components[target] < 0:
                assign(target, component)

    component = 0
    for node in reversed(order):
        if components[node] < 0:
            assign(node, component)
            component += 1
    feasible = all(components[2 * n] != components[2 * n + 1] for n in range(len(slot_ids)))
    proof = canonical_sha256(
        {
            "slot_ids": slot_ids,
            "edge_count": len(edges),
            "components": components,
            "feasible": feasible,
        }
    )
    return feasible, proof


def validate_record_integrity(
    record: dict[str, Any],
    slot: dict[str, Any],
    policy: dict[str, Any],
    freeze: dict[str, Any],
    freeze_sha: str,
) -> None:
    """Rebind every stored identity to frozen metadata and current freeze state."""
    for field in (
        "slot_id", "class", "expected_behavior", "task_family", "scenario_family",
        "structural_family", "register", "preservation_burden", "group_family",
        "template_family_id",
    ):
        if record.get(field) != slot.get(field):
            raise PrivateAuthoringError(f"slot_metadata_mismatch:{field}")
    if record["draft_id"] != f"G3D-{record['slot_id']}-{record['draft_role']}":
        raise PrivateAuthoringError("draft_id_mismatch")
    if record["policy_sha256"] != file_sha256(POLICY) or record[
        "generation_freeze_sha256"
    ] != freeze_sha:
        raise PrivateAuthoringError("draft_freeze_identity_mismatch")
    if record["prompt_sha256"] != file_sha256(
        Path(__file__).parents[1] / "config/gate3_custom_generation_prompt.txt"
    ):
        raise PrivateAuthoringError("draft_prompt_identity_mismatch")
    if record["generation_model"] != freeze["model"]:
        raise PrivateAuthoringError("draft_model_mismatch")
    if record["generation_model_digest"] != freeze["model_digest"]:
        raise PrivateAuthoringError("draft_model_digest_mismatch")
    if record["group_id"] != derive_group_id(slot, policy):
        raise PrivateAuthoringError("draft_group_id_mismatch")
    if record["template_fingerprint"] != derive_template_fingerprint(
        slot, policy, record["prompt_sha256"]
    ):
        raise PrivateAuthoringError("draft_template_fingerprint_mismatch")
    if record["draft_fingerprint"] != derive_draft_fingerprint(
        record["slot_id"], record["draft_role"], record["query_text"],
        record["policy_sha256"], record["generation_freeze_sha256"],
    ):
        raise PrivateAuthoringError("draft_fingerprint_mismatch")


def validate_pool(path: Path, write_audit: bool = True) -> dict[str, Any]:
    expected = resolve_private_path("drafts/gate3_private_draft_pool.json")
    if path.resolve() != expected.resolve():
        raise PrivateAuthoringError("canonical_pool_path_required")
    freeze = load_freeze()
    freeze_sha = file_sha256(FREEZE)
    policy = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    seal_path = resolve_private_path("drafts/gate3_private_draft_pool.seal.json")
    if not seal_path.exists():
        raise PrivateAuthoringError("draft_pool_seal_missing")
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    required_seal_fields = {
        "schema_version", "draft_pool_id", "draft_pool_sha256", "draft_count",
        "primary_count", "replacement_count", "policy_sha256", "slot_sha256",
        "prompt_sha256", "schema_sha256", "parameter_hash", "model_digest",
        "generation_model", "generation_run_version", "generation_activation_commit",
        "activated_generator_sha256", "activated_generation_freeze_sha256",
        "split", "qrels", "canonical_candidate_manifest",
    }
    if not required_seal_fields.issubset(seal):
        raise PrivateAuthoringError("draft_pool_seal_contract_invalid")
    if file_sha256(path) != seal["draft_pool_sha256"]:
        raise PrivateAuthoringError("draft_pool_seal_sha256_mismatch")
    seal_expectations = {
        "draft_count": 570,
        "primary_count": 285,
        "replacement_count": 285,
        "policy_sha256": file_sha256(POLICY),
        "slot_sha256": file_sha256(SLOTS),
        "prompt_sha256": file_sha256(
            Path(__file__).parents[1] / "config/gate3_custom_generation_prompt.txt"
        ),
        "schema_sha256": file_sha256(DRAFT_SCHEMA),
        "parameter_hash": freeze["parameter_hash"],
        "model_digest": freeze["model_digest"],
        "generation_model": freeze["model"],
        "generation_run_version": "gate3-b1-v2",
        "activated_generator_sha256": file_sha256(GENERATOR),
        "activated_generation_freeze_sha256": freeze_sha,
        "split": False,
        "qrels": False,
        "canonical_candidate_manifest": False,
    }
    if any(seal.get(key) != value for key, value in seal_expectations.items()):
        raise PrivateAuthoringError("draft_pool_seal_identity_mismatch")
    if not isinstance(seal["generation_activation_commit"], str) or not seal[
        "generation_activation_commit"
    ]:
        raise PrivateAuthoringError("generation_activation_commit_missing")
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data.get("records")
    if data.get("draft_pool_id") != "gate3-private-drafts-570-v0.4" or not isinstance(
        records, list
    ):
        raise PrivateAuthoringError("draft_pool_identity_invalid")
    if len(records) != 570:
        raise PrivateAuthoringError("draft_count_mismatch")
    slots_payload = yaml.safe_load(SLOTS.read_text())
    slot_by_id = {slot["slot_id"]: slot for slot in slots_payload["slots"]}
    slot_ids = sorted(slot["slot_id"] for slot in slots_payload["slots"])
    by_slot: dict[str, list[dict[str, Any]]] = defaultdict(list)
    schema = json.loads(DRAFT_SCHEMA.read_text(encoding="utf-8"))
    for record in records:
        if set(record) - {
            "draft_id",
            "slot_id",
            "draft_role",
            "query_text",
            "class",
            "expected_behavior",
            "task_family",
            "scenario_family",
            "structural_family",
            "register",
            "preservation_burden",
            "group_family",
            "group_id",
            "template_family_id",
            "template_fingerprint",
            "generation_model",
            "generation_model_digest",
            "policy_sha256",
            "generation_freeze_sha256",
            "prompt_sha256",
            "draft_fingerprint",
        }:
            raise PrivateAuthoringError("unexpected_draft_metadata")
        jsonschema.validate({k: record[k] for k in ("slot_id", "draft_role", "query_text")}, schema)
        if record["slot_id"] not in slot_ids or record["draft_role"] not in EXPECTED_ROLES:
            raise PrivateAuthoringError("draft_slot_role_invalid")
        slot = slot_by_id[record["slot_id"]]
        validate_record_integrity(record, slot, policy, freeze, freeze_sha)
        by_slot[record["slot_id"]].append(record)
    if set(by_slot) != set(slot_ids) or any(len(items) != 2 for items in by_slot.values()):
        raise PrivateAuthoringError("slot_role_coverage_invalid")
    for items in by_slot.values():
        if {item["draft_role"] for item in items} != set(EXPECTED_ROLES):
            raise PrivateAuthoringError("slot_role_pair_invalid")
        if split.canonical_text(items[0]["query_text"]) == split.canonical_text(
            items[1]["query_text"]
        ):
            raise PrivateAuthoringError("primary_replacement_exact_duplicate")

    views = [_draft_view(record) for record in records]
    public_path = GATE2_PUBLIC_MANIFEST
    verify_gate2_manifest_identity(public_path)
    public_records = json.loads(public_path.read_text(encoding="utf-8"))["records"]
    exact_cross = 0
    gate2_conflicts: list[dict[str, Any]] = []
    for draft in views:
        draft_text = split.canonical_text(draft["query_text"])
        for public in public_records:
            if draft_text == split.canonical_text(public["query_text"]):
                exact_cross += 1
                gate2_conflicts.append(
                    {"draft_id": draft["id"], "public_id": public["id"], "type": "exact"}
                )
                continue
            hard, review, metrics = _near_kind(draft, public)
            if hard or review:
                gate2_conflicts.append(
                    {
                        "draft_id": draft["id"],
                        "public_id": public["id"],
                        "type": "hard" if hard else "review",
                        "metrics": metrics,
                    }
                )
    custom_exact = 0
    custom_hard = 0
    custom_review = 0
    same_family: list[dict[str, Any]] = []
    graph_edges: list[tuple[str, str, str, str]] = []
    for index, left in enumerate(views):
        for right in views[index + 1 :]:
            if split.canonical_text(left["query_text"]) == split.canonical_text(
                right["query_text"]
            ):
                custom_exact += 1
                continue
            hard, review, metrics = _near_kind(left, right)
            if not (hard or review):
                continue
            if left["slot_id"] == right["slot_id"]:
                continue
            if hard:
                custom_hard += 1
                graph_edges.append(
                    (left["slot_id"], left["draft_role"], right["slot_id"], right["draft_role"])
                )
            elif (
                left["template_fingerprint"] == right["template_fingerprint"]
                or left["group_id"] == right["group_id"]
            ):
                same_family.append(
                    {"left": left["draft_id"], "right": right["draft_id"], "metrics": metrics}
                )
            else:
                custom_review += 1
                graph_edges.append(
                    (left["slot_id"], left["draft_role"], right["slot_id"], right["draft_role"])
                )
    feasible, proof = _two_sat(slot_ids, graph_edges)
    conflict_path = resolve_private_path(CONFLICT_RELATIVE)
    readiness_path = resolve_private_path(READINESS_RELATIVE)
    summary = {
        "schema_version": 1,
        "draft_count": 570,
        "slot_count": 285,
        "gate2_pair_evaluations": 570 * 315,
        "gate2_exact_duplicates": exact_cross,
        "gate2_hard_or_review_conflicts": len(gate2_conflicts),
        "custom_pair_evaluations": 570 * 569 // 2,
        "custom_exact_duplicates": custom_exact,
        "custom_hard_conflicts": custom_hard,
        "custom_unrelated_review_conflicts": custom_review,
        "same_family_review_relations": len(same_family),
        "one_role_per_slot_feasible": feasible,
        "feasibility_proof_sha256": proof,
        "performance_peek": False,
        "owner_approval_count": 0,
        "canonical_manifest_present": False,
        "query_text_printed": False,
        "verdict": "pass" if feasible and not gate2_conflicts and not custom_exact else "fail",
    }
    if write_audit:
        graph_payload = {
            "schema_version": 1,
            "draft_pool_sha256": file_sha256(path),
            "gate2_conflicts": gate2_conflicts,
            "custom_conflict_edges": [list(edge) for edge in graph_edges],
            "same_family_relations": same_family,
            "feasibility_proof_sha256": proof,
            "query_text_included": False,
        }
        atomic_write_bytes(
            conflict_path, (json.dumps(graph_payload, sort_keys=True, indent=2) + "\n").encode()
        )
        atomic_write_bytes(
            readiness_path, (json.dumps(summary, sort_keys=True, indent=2) + "\n").encode()
        )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    try:
        path = args.manifest or resolve_private_path("drafts/gate3_private_draft_pool.json")
        print(json.dumps(validate_pool(path), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, jsonschema.ValidationError) as exc:
        print(json.dumps({"verdict": "fail", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
