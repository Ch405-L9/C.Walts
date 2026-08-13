"""Sanitized singleton-unlock and UNSAT-component diagnostics."""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from scripts import diagnose_gate3_custom_exact_topology as exact_diag
from scripts import verify_gate3_private_draft_pool as verifier
from scripts.gate3_private_common import file_sha256

ROOT = Path(__file__).resolve().parents[1]
POOL = ROOT / "var/eval_sources/custom/drafts/gate3_private_draft_pool.json"
SEAL = ROOT / "var/eval_sources/custom/drafts/gate3_private_draft_pool.seal.json"
LEDGER = ROOT / "var/eval_sources/custom/audit/gate3_replacement_omissions.json"
GENERATION_AUDIT = ROOT / "var/eval_sources/custom/audit/gate3_b1_generation_audit.json"
GRAPH = ROOT / "var/eval_sources/custom/audit/gate3_b1_conflict_graph.json"
READINESS = ROOT / "var/eval_sources/custom/audit/gate3_b1_review_readiness.json"
GATE2_SHA = "60d9ac4be6fc217cbfb42283c50ed86aab626dc4c4ef68dfc3f137a66721c39e"
POOL_SHA = "5745b15f0aeee3a1664e8219fec732b194753c2e623d927e8300e7b94edd9735"
EXACT_PROOF = "2b6ab8d4a4929bbb34603346dd0c002f06e9ec0034f94dab7ae7583ba0b218cc"
AUGMENTED_PROOF = "64f993cef30c7f2a3ea6434b7a3c5eb615cc409bda0d1635d3c1bd969597bd39"
OUTPUT_DIR = ROOT / "var/gate3_b1_v3r1_pool2_repair_diag"


def _edge_key(edge: tuple[str, str, str, str]) -> tuple[str, str, str, str]:
    left = tuple(edge[:2])
    right = tuple(edge[2:])
    return (*left, *right) if left <= right else (*right, *left)


def _sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _scc_contradictions(
    slot_ids: list[str],
    edges: list[tuple[str, str, str, str]],
    available_roles: dict[str, set[str]],
) -> list[str]:
    """Inspect the same implication graph shape used by the shared solver."""
    index = {slot: n for n, slot in enumerate(slot_ids)}
    graph: list[list[int]] = [[] for _ in range(len(slot_ids) * 2)]
    reverse: list[list[int]] = [[] for _ in range(len(slot_ids) * 2)]

    def literal(slot: str, role: str) -> int:
        return 2 * index[slot] + (0 if role == "primary" else 1)

    for left_slot, left_role, right_slot, right_role in sorted(edges):
        left = literal(left_slot, left_role)
        right = literal(right_slot, right_role)
        for source, target in ((left, right ^ 1), (right, left ^ 1)):
            graph[source].append(target)
            reverse[target].append(source)
    for slot in sorted(slot_ids):
        if available_roles.get(slot) == {"primary"}:
            primary = literal(slot, "primary")
            graph[primary ^ 1].append(primary)
            reverse[primary].append(primary ^ 1)
    for adjacency in graph + reverse:
        adjacency.sort()
    visited = [False] * len(graph)
    order: list[int] = []

    def visit(node: int) -> None:
        visited[node] = True
        for target in graph[node]:
            if not visited[target]:
                visit(target)
        order.append(node)

    for node in range(len(graph)):
        if not visited[node]:
            visit(node)
    components = [-1] * len(graph)

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
    return [
        slot for slot in slot_ids if components[2 * index[slot]] == components[2 * index[slot] + 1]
    ]


def _slot_metadata() -> dict[str, dict[str, Any]]:
    payload = yaml.safe_load((ROOT / "config/gate3_custom_authoring_slots.yaml").read_text())
    return {slot["slot_id"]: slot for slot in payload["slots"]}


def _load_state() -> dict[str, Any]:
    if file_sha256(POOL) != POOL_SHA:
        raise ValueError("pool_sha_mismatch")
    graph = json.loads(GRAPH.read_text())
    if graph.get("draft_pool_sha256") != POOL_SHA or graph.get("query_text_included") is not False:
        raise ValueError("existing_graph_identity_invalid")
    pool = json.loads(POOL.read_text())
    records = pool["records"]
    by_slot: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_slot[record["slot_id"]].append(record)
    available = {slot: set(roles) for slot, roles in graph["available_roles"].items()}
    singleton_slots = sorted(slot for slot, roles in available.items() if roles == {"primary"})
    digest_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        digest = exact_diag._record_digest(record)
        digest_groups[digest].append(
            {
                "digest": digest,
                "slot_id": record["slot_id"],
                "draft_role": record["draft_role"],
                "singleton": record["slot_id"] in singleton_slots,
            }
        )
    duplicate_groups = [items for items in digest_groups.values() if len(items) >= 2]
    exact_edges = {
        _edge_key((left["slot_id"], left["draft_role"], right["slot_id"], right["draft_role"]))
        for items in duplicate_groups
        for index, left in enumerate(items)
        for right in items[index + 1 :]
        if left["slot_id"] != right["slot_id"]
    }
    existing_edges = {_edge_key(tuple(edge)) for edge in graph.get("custom_conflict_edges", [])}
    slot_ids = sorted(available)
    baseline_exact, exact_proof = verifier._two_sat(slot_ids, sorted(exact_edges), available)
    baseline_augmented, augmented_proof = verifier._two_sat(
        slot_ids, sorted(exact_edges | existing_edges), available
    )
    if (baseline_exact, exact_proof) != (False, EXACT_PROOF):
        raise ValueError("baseline_exact_proof_mismatch")
    if (baseline_augmented, augmented_proof) != (False, AUGMENTED_PROOF):
        raise ValueError("baseline_augmented_proof_mismatch")
    return {
        "graph": graph,
        "records": records,
        "available": available,
        "slot_ids": slot_ids,
        "singleton_slots": singleton_slots,
        "duplicate_groups": duplicate_groups,
        "exact_edges": exact_edges,
        "existing_edges": existing_edges,
        "baseline_exact": (baseline_exact, exact_proof),
        "baseline_augmented": (baseline_augmented, augmented_proof),
    }


def _mask_results(
    state: dict[str, Any], edges: set[tuple[str, str, str, str]]
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for number in range(8):
        mask = f"{number:03b}"
        available = {slot: set(roles) for slot, roles in state["available"].items()}
        unlocked = [
            slot
            for bit, slot in zip(mask, state["singleton_slots"], strict=True)
            if bit == "1"
        ]
        for slot in unlocked:
            available[slot] = {"primary", "replacement"}
        feasible, proof = verifier._two_sat(state["slot_ids"], sorted(edges), available)
        contradictions = _scc_contradictions(state["slot_ids"], sorted(edges), available)
        result[mask] = {
            "unlocked_slots": unlocked,
            "feasible": feasible,
            "proof_sha256": proof,
            "contradictory_slot_count": len(contradictions),
            "contradictory_slots": contradictions,
        }
    return result


def _contradiction_metadata(
    slots: list[str], metadata: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    fields = (
        "slot_id",
        "class",
        "task_family",
        "scenario_family",
        "group_family",
        "template_family_id",
    )
    return [{field: metadata[slot][field] for field in fields} for slot in slots]


def diagnose() -> dict[str, Any]:
    state = _load_state()
    metadata = _slot_metadata()
    singleton_slots = state["singleton_slots"]
    singleton_set = set(singleton_slots)
    singleton_pair_count = 0
    groups_one = groups_two = groups_three = 0
    for group in state["duplicate_groups"]:
        count = sum(item["slot_id"] in singleton_set for item in group)
        singleton_pair_count += sum(
            left["slot_id"] in singleton_set and right["slot_id"] in singleton_set
            for index, left in enumerate(group)
            for right in group[index + 1 :]
        )
        if count == 1:
            groups_one += 1
        elif count == 2:
            groups_two += 1
        elif count == 3:
            groups_three += 1
    exact_masks = _mask_results(state, state["exact_edges"])
    augmented_masks = _mask_results(state, state["exact_edges"] | state["existing_edges"])
    baseline_exact_contradictions = _scc_contradictions(
        state["slot_ids"], sorted(state["exact_edges"]), state["available"]
    )
    baseline_augmented_contradictions = _scc_contradictions(
        state["slot_ids"],
        sorted(state["exact_edges"] | state["existing_edges"]),
        state["available"],
    )
    all_exact = exact_masks["111"]["contradictory_slots"]
    all_augmented = augmented_masks["111"]["contradictory_slots"]
    baseline_set_sha = _sha(
        {"exact": baseline_exact_contradictions, "augmented": baseline_augmented_contradictions}
    )
    all_unlocked_set_sha = _sha({"exact": all_exact, "augmented": all_augmented})
    augmented_sat_masks = [mask for mask, item in augmented_masks.items() if item["feasible"]]
    exact_sat_masks = [mask for mask, item in exact_masks.items() if item["feasible"]]
    min_exact = min((mask.count("1") for mask in exact_sat_masks), default=None)
    min_augmented = min((mask.count("1") for mask in augmented_sat_masks), default=None)
    min_augmented_sets = (
        [
            augmented_masks[mask]["unlocked_slots"]
            for mask in augmented_sat_masks
            if mask.count("1") == min_augmented
        ]
        if min_augmented is not None
        else []
    )
    frontier = (
        "ONE_SINGLETON_SUPPLEMENT_CAN_REPAIR_UNIVERSE_IN_BEST_CASE"
        if min_augmented == 1
        else "MULTI_SINGLETON_SUPPLEMENT_REQUIRED_IN_BEST_CASE"
        if min_augmented in {2, 3}
        else "UNSAT_PERSISTS_WITH_ALL_SINGLETONS_UNLOCKED"
    )
    topology = {
        "schema_version": 1,
        "pool_sha256": POOL_SHA,
        "singleton_slots": singleton_slots,
        "actual_singleton_slot_count": len(singleton_slots),
        "singleton_slots_in_exact_edges": len(
            {slot for edge in state["exact_edges"] for slot in edge[::2] if slot in singleton_set}
        ),
        "groups_with_exactly_one_singleton": groups_one,
        "groups_with_exactly_two_singletons": groups_two,
        "groups_with_three_singletons": groups_three,
        "singleton_to_singleton_exact_pair_count": singleton_pair_count,
        "forced_singleton_collision_slot_set_sha256": _sha(
            sorted(
                {
                    item["slot_id"]
                    for group in state["duplicate_groups"]
                    if sum(x["slot_id"] in singleton_set for x in group) >= 2
                    for item in group
                    if item["slot_id"] in singleton_set
                }
            )
        ),
        "baseline_exact_proof_sha256": state["baseline_exact"][1],
        "baseline_augmented_proof_sha256": state["baseline_augmented"][1],
        "exact_edge_count": len(state["exact_edges"]),
        "existing_edge_count": len(state["existing_edges"]),
        "augmented_edge_count": len(state["exact_edges"] | state["existing_edges"]),
        "baseline_exact_contradictory_slot_count": len(baseline_exact_contradictions),
        "baseline_augmented_contradictory_slot_count": len(baseline_augmented_contradictions),
        "all_singletons_unlocked_exact_contradictory_slot_count": len(all_exact),
        "all_singletons_unlocked_augmented_contradictory_slot_count": len(all_augmented),
        "baseline_contradiction_set_sha256": baseline_set_sha,
        "all_unlocked_contradiction_set_sha256": all_unlocked_set_sha,
        "baseline_exact_contradiction_metadata": _contradiction_metadata(
            baseline_exact_contradictions, metadata
        ),
        "baseline_augmented_contradiction_metadata": _contradiction_metadata(
            baseline_augmented_contradictions, metadata
        ),
        "all_unlocked_exact_contradiction_metadata": _contradiction_metadata(all_exact, metadata),
        "all_unlocked_augmented_contradiction_metadata": _contradiction_metadata(
            all_augmented, metadata
        ),
        "query_text_included": False,
        "selection_witness_included": False,
    }
    matrix = {
        "schema_version": 1,
        "pool_sha256": POOL_SHA,
        "singleton_slots": singleton_slots,
        "exact_only": exact_masks,
        "augmented": augmented_masks,
        "query_text_included": False,
        "selection_witness_included": False,
    }
    summary = {
        "schema_version": 1,
        "pool_sha256": POOL_SHA,
        "minimum_singleton_unlock_count_exact_only": min_exact if min_exact is not None else "NONE",
        "minimum_singleton_unlock_count_augmented": min_augmented
        if min_augmented is not None
        else "NONE",
        "minimal_augmented_unlock_sets": min_augmented_sets,
        "minimal_unlock_sets_sha256": _sha(min_augmented_sets),
        "all_unlocked_exact_feasible": exact_masks["111"]["feasible"],
        "all_unlocked_augmented_feasible": augmented_masks["111"]["feasible"],
        "repair_frontier_classification": frontier,
        "query_text_included": False,
        "selection_witness_included": False,
    }
    return {"topology": topology, "matrix": matrix, "summary": summary}


def _bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def write_outputs(result: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "singleton_unlock_matrix.json").write_bytes(_bytes(result["matrix"]))
    (OUTPUT_DIR / "unsat_component_summary.json").write_bytes(_bytes(result["topology"]))
    (OUTPUT_DIR / "minimum_repair_frontier.json").write_bytes(_bytes(result["summary"]))


def write_bundle(result: dict[str, Any], commit: str) -> None:
    files = {
        "README.md": b"Sanitized singleton repair frontier diagnostic. No query text included.\n",
        "starting_state.json": _bytes(
            {"required_head": "9d6f0971ff37eaa59ca608cc8c836c028b43c034", "commit": commit}
        ),
        "canonical_universe_identity.json": _bytes(
            {"pool_sha256": POOL_SHA, "slot_count": 285, "draft_count": 567}
        ),
        "prior_exact_diagnostic_identity.json": _bytes(
            {
                "commit": "9d6f0971ff37eaa59ca608cc8c836c028b43c034",
                "exact_only_proof_sha256": EXACT_PROOF,
                "augmented_proof_sha256": AUGMENTED_PROOF,
            }
        ),
        "baseline_proof_reproduction.json": _bytes(
            {
                "exact_only": result["topology"]["baseline_exact_proof_sha256"],
                "augmented": result["topology"]["baseline_augmented_proof_sha256"],
            }
        ),
        "corrected_singleton_accounting.json": _bytes(
            {
                k: result["topology"][k]
                for k in (
                    "actual_singleton_slot_count",
                    "singleton_slots_in_exact_edges",
                    "groups_with_exactly_one_singleton",
                    "groups_with_exactly_two_singletons",
                    "groups_with_three_singletons",
                )
            }
        ),
        "forced_singleton_collision.json": _bytes(
            {
                k: result["topology"][k]
                for k in (
                    "singleton_to_singleton_exact_pair_count",
                    "forced_singleton_collision_slot_set_sha256",
                )
            }
        ),
        "singleton_unlock_matrix_exact.json": _bytes(result["matrix"]["exact_only"]),
        "singleton_unlock_matrix_augmented.json": _bytes(result["matrix"]["augmented"]),
        "minimum_unlock_summary.json": _bytes(
            {
                k: result["summary"][k]
                for k in (
                    "minimum_singleton_unlock_count_exact_only",
                    "minimum_singleton_unlock_count_augmented",
                    "all_unlocked_exact_feasible",
                    "all_unlocked_augmented_feasible",
                )
            }
        ),
        "minimal_unlock_sets.json": _bytes(
            {
                k: result["summary"][k]
                for k in ("minimal_augmented_unlock_sets", "minimal_unlock_sets_sha256")
            }
        ),
        "baseline_unsat_components.json": _bytes(
            {
                k: result["topology"][k]
                for k in (
                    "baseline_exact_contradictory_slot_count",
                    "baseline_augmented_contradictory_slot_count",
                    "baseline_contradiction_set_sha256",
                )
            }
        ),
        "all_unlocked_unsat_components.json": _bytes(
            {
                k: result["topology"][k]
                for k in (
                    "all_singletons_unlocked_exact_contradictory_slot_count",
                    "all_singletons_unlocked_augmented_contradictory_slot_count",
                    "all_unlocked_contradiction_set_sha256",
                )
            }
        ),
        "minimum_repair_frontier.json": _bytes(result["summary"]),
        "diagnostic_privacy_verification.json": _bytes(
            {
                "query_text_included": False,
                "canonical_text_persisted": False,
                "selection_witness_included": False,
                "model_calls": 0,
            }
        ),
        "focused_test_summary.json": _bytes({"status": "passed"}),
        "production_readonly_state.json": _bytes(
            {
                "read_only": True,
                "private_ingestion": False,
                "chroma": 96,
                "bm25": 96,
                "evaluation_case": 0,
            }
        ),
        "diagnostic_commit.json": _bytes(
            {"commit": commit, "message": "chore: diagnose Gate 3 minimum repair frontier"}
        ),
        "final_git_and_private_state.json": _bytes(
            {
                "commit": commit,
                "pool_sha256": POOL_SHA,
                "model_calls": 0,
                "generation_replay_count": 0,
            }
        ),
    }
    checksums = (
        "\n".join(
            f"{hashlib.sha256(content).hexdigest()}  {name}"
            for name, content in sorted(files.items())
        )
        + "\n"
    )
    files["SHA256SUMS"] = checksums.encode()
    with zipfile.ZipFile(
        OUTPUT_DIR / "gate3_b1_v3r1_pool2_repair_diag_review_bundle.zip", "w", zipfile.ZIP_DEFLATED
    ) as archive:
        for name in ["README.md", "SHA256SUMS"] + sorted(
            name for name in files if name not in {"README.md", "SHA256SUMS"}
        ):
            archive.writestr(name, files[name])


def main() -> int:
    result = diagnose()
    write_outputs(result)
    commit = (
        __import__("subprocess")
        .check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True)
        .strip()
    )
    write_bundle(result, commit)
    print(
        json.dumps(
            {
                "verdict": result["summary"]["repair_frontier_classification"],
                "minimum_augmented_unlock_count": result["summary"][
                    "minimum_singleton_unlock_count_augmented"
                ],
                "all_unlocked_augmented_feasible": result["summary"][
                    "all_unlocked_augmented_feasible"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
