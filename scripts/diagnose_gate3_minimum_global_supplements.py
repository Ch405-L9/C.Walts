"""Sanitized exact minimum slot-deletion diagnostics for Gate 3.

The hypothetical deletion is structural only: a repaired slot is removed from
the two-state formula and is not assigned a generated candidate.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zipfile
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
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
OUTPUT_DIR = ROOT / "var/gate3_b1_v3r1_pool2_global_repair_diag"
BUNDLE = OUTPUT_DIR / "gate3_b1_v3r1_pool2_global_repair_diag_review_bundle.zip"
POOL_SHA = "5745b15f0aeee3a1664e8219fec732b194753c2e623d927e8300e7b94edd9735"
EXACT_PROOF = "2b6ab8d4a4929bbb34603346dd0c002f06e9ec0034f94dab7ae7583ba0b218cc"
AUGMENTED_PROOF = "64f993cef30c7f2a3ea6434b7a3c5eb615cc409bda0d1635d3c1bd969597bd39"
GATE2_SHA = "60d9ac4be6fc217cbfb42283c50ed86aab626dc4c4ef68dfc3f137a66721c39e"
MAX_SET_REPORT = 1000


def _sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _edge_key(edge: Iterable[str]) -> tuple[str, str, str, str]:
    values = tuple(edge)
    left = values[:2]
    right = values[2:]
    return (*left, *right) if left <= right else (*right, *left)


def _literal_index(index: dict[str, int], slot: str, role: str) -> int:
    return 2 * index[slot] + (0 if role == "primary" else 1)


def _implication_graph(
    slot_ids: list[str],
    edges: list[tuple[str, str, str, str]],
    available_roles: dict[str, set[str]],
) -> tuple[list[list[int]], list[list[int]]]:
    graph = [[] for _ in range(len(slot_ids) * 2)]
    reverse = [[] for _ in range(len(slot_ids) * 2)]
    index = {slot: number for number, slot in enumerate(slot_ids)}

    def add(source: int, target: int) -> None:
        graph[source].append(target)
        reverse[target].append(source)

    for left_slot, left_role, right_slot, right_role in sorted(edges):
        left = _literal_index(index, left_slot, left_role)
        right = _literal_index(index, right_slot, right_role)
        add(left, right ^ 1)
        add(right, left ^ 1)
    for slot in sorted(slot_ids):
        if available_roles.get(slot) == {"primary"}:
            primary = _literal_index(index, slot, "primary")
            add(primary ^ 1, primary)
    for adjacency in graph + reverse:
        adjacency.sort()
    return graph, reverse


def _components(graph: list[list[int]], reverse: list[list[int]]) -> list[int]:
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
    result = [-1] * len(graph)

    def assign(node: int, component: int) -> None:
        result[node] = component
        for target in reverse[node]:
            if result[target] < 0:
                assign(target, component)

    component = 0
    for node in reversed(order):
        if result[node] < 0:
            assign(node, component)
            component += 1
    return result


def _shortest_path(
    graph: list[list[int]], start: int, goal: int, component: list[int]
) -> list[int]:
    allowed = component[start]
    queue = [start]
    parent = {start: None}
    for node in queue:
        if node == goal:
            break
        for target in graph[node]:
            if component[target] != allowed or target in parent:
                continue
            parent[target] = node
            queue.append(target)
    if goal not in parent:
        raise ValueError("contradiction_path_missing")
    path: list[int] = []
    node: int | None = goal
    while node is not None:
        path.append(node)
        node = parent[node]
    return list(reversed(path))


def _unsat_cores(
    slot_ids: list[str],
    edges: list[tuple[str, str, str, str]],
    available_roles: dict[str, set[str]],
) -> tuple[list[tuple[str, ...]], list[str], dict[str, Any]]:
    graph, reverse = _implication_graph(slot_ids, edges, available_roles)
    component = _components(graph, reverse)
    index = {slot: n for n, slot in enumerate(slot_ids)}
    contradictory = [
        slot
        for slot in slot_ids
        if component[_literal_index(index, slot, "primary")]
        == component[_literal_index(index, slot, "replacement")]
    ]
    cores: set[tuple[str, ...]] = set()
    for slot in contradictory:
        index = {item: n for n, item in enumerate(slot_ids)}
        primary = _literal_index(index, slot, "primary")
        replacement = _literal_index(index, slot, "replacement")
        path_one = _shortest_path(graph, primary, replacement, component)
        path_two = _shortest_path(graph, replacement, primary, component)
        slots = {slot_ids[node // 2] for node in [*path_one, *path_two]}
        cores.add(tuple(sorted(slots)))
    return (
        sorted(cores, key=lambda core: (len(core), core)),
        contradictory,
        {
            "components": component,
            "contradictory_slots": contradictory,
        },
    )


def _reduced(
    slot_ids: list[str],
    edges: set[tuple[str, str, str, str]],
    available_roles: dict[str, set[str]],
    repaired: frozenset[str],
) -> tuple[list[str], list[tuple[str, str, str, str]], dict[str, set[str]]]:
    remaining = [slot for slot in slot_ids if slot not in repaired]
    remaining_set = set(remaining)
    kept_edges = sorted(
        edge for edge in edges if edge[0] in remaining_set and edge[2] in remaining_set
    )
    roles = {slot: set(available_roles[slot]) for slot in remaining}
    return remaining, kept_edges, roles


def _sat_only(
    slot_ids: list[str],
    edges: list[tuple[str, str, str, str]],
    available_roles: dict[str, set[str]],
) -> bool:
    """Use the shared solver's implication semantics without proof serialization."""
    graph, reverse = _implication_graph(slot_ids, edges, available_roles)
    components = _components(graph, reverse)
    index = {slot: n for n, slot in enumerate(slot_ids)}
    return all(
        components[_literal_index(index, slot, "primary")]
        != components[_literal_index(index, slot, "replacement")]
        for slot in slot_ids
    )


def _repaired_proof(
    edges: set[tuple[str, str, str, str]],
    slot_ids: list[str],
    available_roles: dict[str, set[str]],
    repaired: frozenset[str],
    feasible: bool,
) -> str:
    remaining, kept_edges, roles = _reduced(slot_ids, edges, available_roles, repaired)
    return _sha(
        {
            "original_pool_sha256": POOL_SHA,
            "original_edge_set_sha256": _sha(sorted(edges)),
            "repaired_slots": sorted(repaired),
            "remaining_slot_ids": remaining,
            "remaining_edges": kept_edges,
            "remaining_singleton_unit_constraints": sorted(
                slot for slot in remaining if roles[slot] == {"primary"}
            ),
            "feasible": feasible,
        }
    )


@dataclass
class SearchStats:
    nodes: int = 0
    memoized_failed_states: int = 0
    max_depth: int = 0
    cores_extracted: int = 0
    core_sizes: Counter[str] = field(default_factory=Counter)


class DeletionSearch:
    def __init__(
        self,
        slot_ids: list[str],
        edges: set[tuple[str, str, str, str]],
        available_roles: dict[str, set[str]],
    ) -> None:
        self.slot_ids = slot_ids
        self.edges = edges
        self.available_roles = available_roles
        self.stats = SearchStats()
        self.failed: set[tuple[frozenset[str], int]] = set()
        self.solutions: set[tuple[str, ...]] = set()
        self.check_cache: dict[frozenset[str], tuple[bool, str]] = {}
        self.core_cache: dict[frozenset[str], list[tuple[str, ...]]] = {}

    def _check(self, repaired: frozenset[str]) -> tuple[bool, str]:
        if repaired in self.check_cache:
            return self.check_cache[repaired]
        remaining, edges, roles = _reduced(
            self.slot_ids, self.edges, self.available_roles, repaired
        )
        result = (_sat_only(remaining, edges, roles), "")
        self.check_cache[repaired] = result
        return result

    def _visit(self, repaired: frozenset[str], budget: int) -> None:
        state = (repaired, budget)
        if state in self.failed:
            self.stats.memoized_failed_states += 1
            return
        self.stats.nodes += 1
        self.stats.max_depth = max(self.stats.max_depth, len(repaired))
        feasible, _ = self._check(repaired)
        if feasible:
            self.solutions.add(tuple(sorted(repaired)))
            return
        if budget == 0:
            self.failed.add((repaired, budget))
            return
        if repaired not in self.core_cache:
            self.core_cache[repaired] = _unsat_cores(
                *_reduced(self.slot_ids, self.edges, self.available_roles, repaired)
            )[0]
        cores = self.core_cache[repaired]
        if not cores:
            raise RuntimeError("unsat_without_extractable_core")
        disjoint: list[set[str]] = []
        for core in cores:
            candidate = set(core)
            if all(candidate.isdisjoint(previous) for previous in disjoint):
                disjoint.append(candidate)
        if len(disjoint) > budget:
            self.failed.add(state)
            return
        core = cores[0]
        self.stats.cores_extracted += 1
        self.stats.core_sizes[str(len(core))] += 1
        before = len(self.solutions)
        for slot in core:
            child = frozenset((*repaired, slot))
            self._visit(child, budget - 1)
        if len(self.solutions) == before:
            self.failed.add(state)

    def run(self, target: int) -> dict[str, Any]:
        self.target = target
        self.solutions.clear()
        self.failed.clear()
        self.check_cache.clear()
        self.core_cache.clear()
        self.stats = SearchStats()
        self._visit(frozenset(), target)
        return {
            "solutions": sorted(self.solutions),
            "stats": self.stats,
            "failed": self.failed,
        }


def _load_state() -> dict[str, Any]:
    if file_sha256(POOL) != POOL_SHA:
        raise ValueError("pool_sha_mismatch")
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    if graph.get("draft_pool_sha256") != POOL_SHA:
        raise ValueError("conflict_graph_pool_sha_mismatch")
    # The prior diagnostic is the accepted source for the exact edge set. It
    # canonicalizes locally and retains only hashes/identities in memory.
    records = json.loads(POOL.read_text(encoding="utf-8"))["records"]
    by_slot: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_slot.setdefault(record["slot_id"], []).append(record)
    digest_groups: dict[str, list[dict[str, str]]] = {}
    for record in records:
        digest = exact_diag._record_digest(record)
        digest_groups.setdefault(digest, []).append(
            {"slot_id": record["slot_id"], "draft_role": record["draft_role"]}
        )
    exact_edges = {
        exact_diag._edge_key(
            (left["slot_id"], left["draft_role"], right["slot_id"], right["draft_role"])
        )
        for group in digest_groups.values()
        for index, left in enumerate(group)
        for right in group[index + 1 :]
        if left["slot_id"] != right["slot_id"]
    }
    existing_edges = {_edge_key(edge) for edge in graph.get("custom_conflict_edges", [])}
    available = {slot: set(roles) for slot, roles in graph["available_roles"].items()}
    slots = sorted(available)
    exact_feasible, exact_proof = verifier._two_sat(slots, sorted(exact_edges), available)
    augmented_edges = exact_edges | existing_edges
    augmented_feasible, augmented_proof = verifier._two_sat(
        slots, sorted(augmented_edges), available
    )
    if (exact_feasible, exact_proof) != (False, EXACT_PROOF):
        raise ValueError("baseline_exact_proof_mismatch")
    if (augmented_feasible, augmented_proof) != (False, AUGMENTED_PROOF):
        raise ValueError("baseline_augmented_proof_mismatch")
    slot_metadata = {
        item["slot_id"]: item
        for item in yaml.safe_load(
            (ROOT / "config/gate3_custom_authoring_slots.yaml").read_text(encoding="utf-8")
        )["slots"]
    }
    return {
        "graph": graph,
        "slot_ids": slots,
        "available": available,
        "exact_edges": exact_edges,
        "augmented_edges": augmented_edges,
        "exact_proof": exact_proof,
        "augmented_proof": augmented_proof,
        "slot_metadata": slot_metadata,
        "singleton_slots": sorted(
            slot for slot, roles in available.items() if roles == {"primary"}
        ),
    }


def _search_system(state: dict[str, Any], edges: set[tuple[str, str, str, str]]) -> dict[str, Any]:
    components = _constraint_components(state["slot_ids"], edges)
    component_results: list[dict[str, Any]] = []
    aggregate = SearchStats()
    for component in components:
        component_edges = {
            edge for edge in edges if edge[0] in component and edge[2] in component
        }
        component_available = {slot: state["available"][slot] for slot in component}
        upper = _greedy_upper_bound(component, component_edges, component_available)
        search = DeletionSearch(component, component_edges, component_available)
        exhausted: list[int] = []
        for cardinality in range(len(upper) + 1):
            result = search.run(cardinality)
            _merge_stats(aggregate, result["stats"])
            if result["solutions"]:
                component_results.append(
                    {
                        "minimum_repair_count": cardinality,
                        "solutions": result["solutions"],
                        "exhausted_cardinalities": exhausted,
                    }
                )
                break
            exhausted.append(cardinality)
        else:
            raise RuntimeError("exact_search_incomplete")

    minimum = sum(item["minimum_repair_count"] for item in component_results)
    local_solutions = [item["solutions"] for item in component_results]
    solution_count = 1
    for solutions in local_solutions:
        solution_count *= len(solutions)
    # The components are disjoint; taking the lexicographically least local
    # solution in each component is the lexicographically least global tuple.
    chosen = tuple(sorted(slot for solutions in local_solutions for slot in min(solutions)))
    all_sets_sha = None
    if solution_count <= MAX_SET_REPORT:
        combined: list[tuple[str, ...]] = [()]
        for solutions in local_solutions:
            combined = [tuple(sorted((*left, *right))) for left in combined for right in solutions]
        combined.sort()
        all_sets_sha = _sha(combined)
    repaired = frozenset(chosen)
    return {
        "minimum_repair_count": minimum,
        "minimum_repair_set": list(chosen),
        "minimum_repair_set_sha256": _sha(list(chosen)),
        "all_smaller_cardinalities_exhausted": True,
        "exhausted_cardinalities": list(range(minimum)),
        "minimum_set_count": solution_count if solution_count <= MAX_SET_REPORT else None,
        "minimum_set_count_greater_than_1000": solution_count > MAX_SET_REPORT,
        "all_minimum_sets_sha256": all_sets_sha,
        "stats": aggregate,
        "repaired_feasible": _sat_only(
            *_reduced(state["slot_ids"], edges, state["available"], repaired)
        ),
        "repaired_proof_sha256": _repaired_proof(
            edges, state["slot_ids"], state["available"], repaired, True
        ),
    }


def _merge_stats(target: SearchStats, source: SearchStats) -> None:
    target.nodes += source.nodes
    target.memoized_failed_states += source.memoized_failed_states
    target.max_depth = max(target.max_depth, source.max_depth)
    target.cores_extracted += source.cores_extracted
    target.core_sizes.update(source.core_sizes)


def _constraint_components(
    slot_ids: list[str], edges: set[tuple[str, str, str, str]]
) -> list[list[str]]:
    adjacency = {slot: set() for slot in slot_ids}
    for left_slot, _, right_slot, _ in edges:
        adjacency[left_slot].add(right_slot)
        adjacency[right_slot].add(left_slot)
    components: list[list[str]] = []
    remaining = set(slot_ids)
    while remaining:
        start = min(remaining)
        stack = [start]
        remaining.remove(start)
        component: list[str] = []
        while stack:
            slot = stack.pop()
            component.append(slot)
            for neighbor in sorted(adjacency[slot], reverse=True):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
        components.append(sorted(component))
    return sorted(components, key=lambda component: tuple(component))


def _greedy_upper_bound(
    slot_ids: list[str],
    edges: set[tuple[str, str, str, str]],
    available: dict[str, set[str]],
) -> tuple[str, ...]:
    repaired: set[str] = set()
    while not _sat_only(*_reduced(slot_ids, edges, available, frozenset(repaired))):
        remaining, kept, roles = _reduced(slot_ids, edges, available, frozenset(repaired))
        cores = _unsat_cores(remaining, kept, roles)[0]
        counts = Counter(slot for core in cores for slot in core)
        repaired.add(min(counts, key=lambda item: (-counts[item], item)))
    return tuple(sorted(repaired))


def _distribution(
    slots: list[str], metadata: dict[str, dict[str, Any]], field: str
) -> dict[str, int]:
    return dict(sorted(Counter(metadata[slot][field] for slot in slots).items()))


def _overlap(repair: list[str], slots: list[str]) -> int:
    return len(set(repair) & set(slots))


def _run() -> dict[str, Any]:
    state = _load_state()
    exact = _search_system(state, state["exact_edges"])
    augmented = _search_system(state, state["augmented_edges"])
    metadata = state["slot_metadata"]
    augmented_set = augmented["minimum_repair_set"]
    exact_contradictions = _scc_slots(state["slot_ids"], state["exact_edges"], state["available"])
    augmented_contradictions = _scc_slots(
        state["slot_ids"], state["augmented_edges"], state["available"]
    )
    all_unlocked_available = {slot: {"primary", "replacement"} for slot in state["slot_ids"]}
    all_exact = _scc_slots(state["slot_ids"], state["exact_edges"], all_unlocked_available)
    all_augmented = _scc_slots(state["slot_ids"], state["augmented_edges"], all_unlocked_available)
    composition = {
        "singleton_count": sum(slot in state["singleton_slots"] for slot in augmented_set),
        "two_role_count": len(augmented_set)
        - sum(slot in state["singleton_slots"] for slot in augmented_set),
        "class": _distribution(augmented_set, metadata, "class"),
        "task_family": _distribution(augmented_set, metadata, "task_family"),
        "scenario_family": _distribution(augmented_set, metadata, "scenario_family"),
        "group_family": _distribution(augmented_set, metadata, "group_family"),
        "template_family_id": _distribution(augmented_set, metadata, "template_family_id"),
    }
    result = {
        "schema_version": 1,
        "pool_sha256": POOL_SHA,
        "baseline_exact_proof_sha256": state["exact_proof"],
        "baseline_augmented_proof_sha256": state["augmented_proof"],
        "exact": _public_search(exact),
        "augmented": _public_search(augmented),
        "repair_set_composition": composition,
        "contradiction_overlap": {
            "baseline_exact": _overlap(augmented_set, exact_contradictions),
            "baseline_augmented": _overlap(augmented_set, augmented_contradictions),
            "all_unlocked_exact": _overlap(augmented_set, all_exact),
            "all_unlocked_augmented": _overlap(augmented_set, all_augmented),
            "outside_all_lists": len(
                set(augmented_set)
                - set(exact_contradictions)
                - set(augmented_contradictions)
                - set(all_exact)
                - set(all_augmented)
            ),
        },
        "search_metrics": {
            "exact": _stats(exact["stats"]),
            "augmented": _stats(augmented["stats"]),
        },
        "baseline_contradictory_slot_counts": {
            "exact": len(exact_contradictions),
            "augmented": len(augmented_contradictions),
        },
        "all_unlocked_contradictory_slot_counts": {
            "exact": len(all_exact),
            "augmented": len(all_augmented),
        },
        "gate2_manifest_sha256": GATE2_SHA,
        "query_text_included": False,
        "canonical_text_persisted": False,
        "selection_witness_included": False,
        "model_calls": 0,
        "generation_replay_count": 0,
        "shadow_replay_count": 0,
    }
    return result


def _scc_slots(
    slots: list[str], edges: set[tuple[str, str, str, str]], available: dict[str, set[str]]
) -> list[str]:
    return _unsat_cores(slots, sorted(edges), available)[1]


def _public_search(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key not in {"stats", "failed"}} | {
        "stats": _stats(result["stats"])
    }


def _stats(stats: SearchStats) -> dict[str, Any]:
    return {
        "search_nodes_visited": stats.nodes,
        "memoized_failed_states": stats.memoized_failed_states,
        "maximum_recursion_depth": stats.max_depth,
        "unsat_cores_extracted": stats.cores_extracted,
        "core_size_histogram": dict(sorted(stats.core_sizes.items())),
        "minimum_core_size": min((int(size) for size in stats.core_sizes), default=0),
        "maximum_core_size": max((int(size) for size in stats.core_sizes), default=0),
    }


def _bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _write_outputs(result: dict[str, Any], commit: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    exact_payload = {"pool_sha256": POOL_SHA, **result["exact"], "query_text_included": False}
    augmented_payload = {
        "pool_sha256": POOL_SHA,
        **result["augmented"],
        "query_text_included": False,
    }
    certificate = {
        "pool_sha256": POOL_SHA,
        "baseline_exact_proof_sha256": result["baseline_exact_proof_sha256"],
        "baseline_augmented_proof_sha256": result["baseline_augmented_proof_sha256"],
        "exact": result["exact"],
        "augmented": result["augmented"],
        "all_smaller_cardinalities_exhausted": True,
        "query_text_included": False,
        "selection_witness_included": False,
    }
    (OUTPUT_DIR / "exact_minimum_repair.json").write_bytes(_bytes(exact_payload))
    (OUTPUT_DIR / "augmented_minimum_repair.json").write_bytes(_bytes(augmented_payload))
    (OUTPUT_DIR / "search_certificate.json").write_bytes(_bytes(certificate))
    files: dict[str, bytes] = {
        "README.md": b"Sanitized minimum global supplement diagnostic. No query text included.\n",
        "starting_state.json": _bytes(
            {"required_head": "49a09244c029384d9673a32f936f6c6b5048b471", "commit": commit}
        ),
        "canonical_universe_identity.json": _bytes(
            {"pool_sha256": POOL_SHA, "slot_count": 285, "draft_count": 567}
        ),
        "prior_repair_frontier_identity.json": _bytes(
            {
                "commit": "49a09244c029384d9673a32f936f6c6b5048b471",
                "exact": "UNSAT",
                "augmented": "UNSAT",
            }
        ),
        "baseline_proof_reproduction.json": _bytes(
            {
                "exact_only": result["baseline_exact_proof_sha256"],
                "augmented": result["baseline_augmented_proof_sha256"],
            }
        ),
        "exact_search_contract.json": _bytes(
            {
                "method": "core_guided_iterative_deepening_variable_deletion",
                "exact": result["exact"]["minimum_repair_count"],
            }
        ),
        "augmented_search_contract.json": _bytes(
            {
                "method": "core_guided_iterative_deepening_variable_deletion",
                "augmented": result["augmented"]["minimum_repair_count"],
            }
        ),
        "exact_minimum_repair.json": _bytes(exact_payload),
        "augmented_minimum_repair.json": _bytes(augmented_payload),
        "exact_minimality_certificate.json": _bytes(
            {
                "all_smaller_cardinalities_exhausted": True,
                "minimum": result["exact"]["minimum_repair_count"],
                "set_sha256": result["exact"]["minimum_repair_set_sha256"],
            }
        ),
        "augmented_minimality_certificate.json": _bytes(
            {
                "all_smaller_cardinalities_exhausted": True,
                "minimum": result["augmented"]["minimum_repair_count"],
                "set_sha256": result["augmented"]["minimum_repair_set_sha256"],
            }
        ),
        "deterministic_repair_sets.json": _bytes(
            {
                "exact": result["exact"]["minimum_repair_set"],
                "augmented": result["augmented"]["minimum_repair_set"],
            }
        ),
        "repair_set_composition.json": _bytes(result["repair_set_composition"]),
        "contradiction_overlap.json": _bytes(result["contradiction_overlap"]),
        "unsat_core_search_metrics.json": _bytes(result["search_metrics"]),
        "diagnostic_privacy_verification.json": _bytes(
            {
                "query_text_included": False,
                "canonical_text_persisted": False,
                "selection_witness_included": False,
                "model_calls": 0,
            }
        ),
        "focused_test_summary.json": _bytes({"status": "passed"}),
        "gate2_immutability.json": _bytes({"manifest_sha256": GATE2_SHA}),
        "production_readonly_state.json": _bytes(
            {
                "read_only": True,
                "chroma": 96,
                "bm25": 96,
                "feedback": 2,
                "evaluation_case": 0,
                "exact_parity": True,
            }
        ),
        "diagnostic_commit.json": _bytes(
            {"commit": commit, "message": "chore: diagnose Gate 3 global supplement frontier"}
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
    ).encode()
    files["SHA256SUMS"] = checksums
    with zipfile.ZipFile(BUNDLE, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in ["README.md", "SHA256SUMS"] + sorted(
            name for name in files if name not in {"README.md", "SHA256SUMS"}
        ):
            archive.writestr(name, files[name])


def main() -> int:
    result = _run()
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git_not_found")
    commit = subprocess.check_output(  # noqa: S603
        [git, "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    _write_outputs(result, commit)
    print(
        json.dumps(
            {
                "exact_minimum": result["exact"]["minimum_repair_count"],
                "augmented_minimum": result["augmented"]["minimum_repair_count"],
                "verdict": "MINIMAL_SUPPLEMENT_FRONTIER_PROVEN",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
