"""Validate a Supplemental-20 candidate set without selecting or persisting a witness."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from scripts import verify_eval_split as split
from scripts import verify_gate3_private_draft_pool as base_verifier
from scripts.gate3_private_common import (
    GATE2_PUBLIC_MANIFEST,
    GATE2_PUBLIC_MANIFEST_SHA256,
    SLOTS,
    canonical_sha256,
    file_sha256,
)

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "config/gate3_s20_target_slots.json"
SURFACE = ROOT / "config/gate3_s20_surface_assignment.json"
SCHEMA = ROOT / "config/gate3_s20_supplement_schema.json"
FREEZE = ROOT / "config/gate3_s20_generation_freeze.json"
POOL = ROOT / "var/eval_sources/custom/drafts/gate3_private_draft_pool.json"
GRAPH = ROOT / "var/eval_sources/custom/audit/gate3_b1_conflict_graph.json"
EXPECTED_POOL_SHA = "5745b15f0aeee3a1664e8219fec732b194753c2e623d927e8300e7b94edd9735"
EXPECTED_TARGET_SHA = "daf9aafc4df9fc70469222889c9697e3eab0eb485d21eaa6d905b89f63a459ca"
EXPECTED_POLICY = "c937d2d877a4fecbe192407beae97311d2e90260354f3563c007df685a39b237"
EXPECTED_SEED_STRATEGY = "gate3-slot-role-attempt-sha256-v1"
EXPECTED_BASE_SEED = 17
EXPECTED_ROLES = {"primary", "replacement"}


def base_exact_edges(records: list[dict[str, Any]]) -> list[tuple[str, str, str, str]]:
    """Derive the accepted exact-text incompatibilities without retaining text."""
    by_digest: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        digest = hashlib.sha256(
            split.canonical_text(record["query_text"]).encode("utf-8")
        ).hexdigest()
        by_digest.setdefault(digest, []).append(record)
    edges: set[tuple[str, str, str, str]] = set()
    for group in by_digest.values():
        for index, left in enumerate(group):
            for right in group[index + 1 :]:
                if left["slot_id"] == right["slot_id"]:
                    raise ValueError("same_slot_exact_duplicate")
                endpoint = (
                    left["slot_id"],
                    left["draft_role"],
                    right["slot_id"],
                    right["draft_role"],
                )
                reverse = (endpoint[2], endpoint[3], endpoint[0], endpoint[1])
                edges.add(min(endpoint, reverse))
    if len(edges) != 243:
        raise ValueError("base_exact_edge_count_mismatch")
    return sorted(edges)


def target_payload() -> dict[str, Any]:
    payload = json.loads(TARGETS.read_text(encoding="utf-8"))
    slots = payload["slot_ids"]
    if slots != sorted(set(slots)) or len(slots) != 20:
        raise ValueError("target_set_not_sorted_or_unique")
    if payload["repair_set_sha256"] != canonical_sha256(slots):
        raise ValueError("target_set_sha_mismatch")
    if payload["repair_set_sha256"] != EXPECTED_TARGET_SHA:
        raise ValueError("target_set_not_accepted_frontier")
    return payload


def target_metadata() -> dict[str, dict[str, Any]]:
    slots = yaml.safe_load(SLOTS.read_text(encoding="utf-8"))["slots"]
    by_id = {item["slot_id"]: item for item in slots}
    targets = target_payload()["slot_ids"]
    if len(set(targets) & set(by_id)) != 20:
        raise ValueError("target_slot_rebinding_failed")
    return {slot: by_id[slot] for slot in targets}


def target_role_counts() -> dict[str, int]:
    omissions = json.loads(
        (ROOT / "var/eval_sources/custom/audit/gate3_replacement_omissions.json").read_text(
            encoding="utf-8"
        )
    )["omissions"]
    target = set(target_payload()["slot_ids"])
    singleton = {item["slot_id"] for item in omissions if item["slot_id"] in target}
    if len(singleton) != 1:
        raise ValueError("target_singleton_reconciliation_failed")
    return {"singleton_count": 1, "two_role_count": 19, "singleton_slot_id": next(iter(singleton))}


def target_surface_profiles() -> dict[str, str]:
    slots = sorted(
        item["slot_id"]
        for item in yaml.safe_load(SLOTS.read_text(encoding="utf-8"))["slots"]
    )
    profiles = json.loads(SURFACE.read_text(encoding="utf-8"))
    assignment: dict[str, str] = {}
    for slot in target_payload()["slot_ids"]:
        ordinal = slots.index(slot) + 1
        pair = ("A", "B", "C")[(ordinal - 1) % 3], ("B", "C", "A")[(ordinal - 1) % 3]
        assignment[slot] = profiles["rules"][f"{pair[0]},{pair[1]}"]
    return assignment


def _two_sat_generalized(
    slot_ids: list[str],
    edges: list[tuple[str, str, str, str]],
    available_roles: dict[str, set[str]],
) -> tuple[bool, str]:
    """The accepted SCC solver with unit clauses for either singleton role."""
    index = {slot: i for i, slot in enumerate(slot_ids)}
    graph = [[] for _ in range(2 * len(slot_ids))]
    reverse = [[] for _ in range(2 * len(slot_ids))]

    def literal(slot: str, role: str) -> int:
        return 2 * index[slot] + (0 if role == "primary" else 1)

    def add(source: int, target: int) -> None:
        graph[source].append(target)
        reverse[target].append(source)

    for left_slot, left_role, right_slot, right_role in sorted(edges):
        left, right = literal(left_slot, left_role), literal(right_slot, right_role)
        add(left, right ^ 1)
        add(right, left ^ 1)
    for slot in sorted(slot_ids):
        roles = available_roles.get(slot, set())
        if not roles or not roles <= EXPECTED_ROLES:
            return False, canonical_sha256({"slot_ids": slot_ids, "invalid_roles": sorted(roles)})
        if len(roles) == 1:
            role = next(iter(roles))
            chosen = literal(slot, role)
            add(chosen ^ 1, chosen)
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
        for source in reverse[node]:
            if components[source] < 0:
                assign(source, component)

    component = 0
    for node in reversed(order):
        if components[node] < 0:
            assign(node, component)
            component += 1
    feasible = all(
        components[2 * index[slot]] != components[2 * index[slot] + 1]
        for slot in slot_ids
    )
    return feasible, canonical_sha256(
        {
            "slot_ids": slot_ids,
            "edges": sorted(edges),
            "available_roles": {slot: sorted(available_roles[slot]) for slot in slot_ids},
            "components": components,
            "feasible": feasible,
        }
    )


def _view(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("draft_id", record.get("supplement_id", "supplement")),
        "slot_id": record["slot_id"],
        "draft_role": record["draft_role"],
        "query_text": record["query_text"],
        "class": record["class"],
        "expected_behavior": record["expected_behavior"],
        "source_dataset": "custom",
        "source_version": record.get("source_version", "cwalts-custom-v0.4-gate3-v3r1-s20"),
        "source_record_id": record["slot_id"],
        "group_id": record["group_id"],
        "template_fingerprint": record["template_fingerprint"],
        "provenance": {"kind": "supplemental"},
    }


def _conflict(left: dict[str, Any], right: dict[str, Any]) -> tuple[bool, bool, dict[str, Any]]:
    return base_verifier._near_kind(left, right)


def validate_supplements(
    records: list[dict[str, Any]], *, require_complete: bool = True
) -> dict[str, Any]:
    target = target_payload()["slot_ids"]
    metadata = target_metadata()
    if file_sha256(POOL) != EXPECTED_POOL_SHA:
        raise ValueError("base_pool_sha_mismatch")
    if file_sha256(GATE2_PUBLIC_MANIFEST) != GATE2_PUBLIC_MANIFEST_SHA256:
        raise ValueError("gate2_manifest_sha_mismatch")
    record_slots = {item.get("slot_id") for item in records}
    if len(records) > 20 or not record_slots <= set(target) or len(record_slots) != len(records):
        raise ValueError("supplement_cardinality_or_target_mismatch")
    if require_complete and (len(records) != 20 or record_slots != set(target)):
        raise ValueError("supplement_cardinality_or_target_mismatch")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    for record in records:
        jsonschema.validate(
            {
                "slot_id": record["slot_id"],
                "draft_role": record["draft_role"],
                "query_text": record["query_text"],
            },
            schema,
        )
    pool = json.loads(POOL.read_text(encoding="utf-8"))["records"]
    public = json.loads(GATE2_PUBLIC_MANIFEST.read_text(encoding="utf-8"))["records"]
    base_views = [base_verifier._draft_view(record) for record in pool]
    public_views = public
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    available = {slot: set(roles) for slot, roles in graph["available_roles"].items()}
    target_set = set(target)
    for slot in target:
        available.pop(slot, None)
    exact_seen: set[str] = set()
    exact_edges = base_exact_edges(pool)
    structural_edges: set[tuple[str, str, str, str]] = {
        edge for edge in exact_edges
        if edge[0] not in target_set and edge[2] not in target_set
    }
    structural_edges.update(
        tuple(edge) for edge in graph.get("custom_conflict_edges", [])
        if edge[0] not in target_set and edge[2] not in target_set
    )
    supplement_views = []
    for record in sorted(records, key=lambda item: item["slot_id"]):
        if record["draft_role"] != "supplemental" or record["slot_id"] not in metadata:
            raise ValueError("supplement_identity_invalid")
        text_key = split.canonical_text(record["query_text"])
        digest = hashlib.sha256(text_key.encode("utf-8")).hexdigest()
        if digest in exact_seen or any(
            text_key == split.canonical_text(item["query_text"]) for item in pool
        ):
            raise ValueError("supplemental_exact_duplicate")
        if any(text_key == split.canonical_text(item["query_text"]) for item in public):
            raise ValueError("supplemental_gate2_exact_duplicate")
        exact_seen.add(digest)
        supplement_views.append(_view(record))
    for index, left in enumerate(supplement_views):
        for right in supplement_views[index + 1 :]:
            hard, review, _ = _conflict(left, right)
            unrelated_review = review and (
                left["template_fingerprint"] != right["template_fingerprint"]
                and left["group_id"] != right["group_id"]
            )
            if hard or unrelated_review:
                raise ValueError("supplemental_pair_conflict")
    for supplement in supplement_views:
        for other in public_views:
            if supplement["slot_id"] == other.get("slot_id"):
                continue
            if split.canonical_text(supplement["query_text"]) == split.canonical_text(
                other["query_text"]
            ):
                raise ValueError("supplemental_exact_duplicate")
            hard, review, _ = _conflict(supplement, other)
            if hard or review:
                raise ValueError("supplemental_gate2_structural_conflict")
        for other in base_views:
            if split.canonical_text(supplement["query_text"]) == split.canonical_text(
                other["query_text"]
            ):
                raise ValueError("supplemental_exact_duplicate")
            if supplement["slot_id"] == other.get("slot_id"):
                raise ValueError("supplemental_same_target_conflict")
            if other.get("slot_id") in target_set:
                continue
            hard, review, _ = _conflict(supplement, other)
            if not (hard or review):
                continue
            if review and (
                supplement["template_fingerprint"] == other.get("template_fingerprint")
                or supplement["group_id"] == other.get("group_id")
            ):
                continue
            if other.get("slot_id") in available:
                available[other["slot_id"]].discard(other["draft_role"])
    remaining = sorted(available)
    feasible, proof = _two_sat_generalized(remaining, sorted(structural_edges), available)
    return {
        "supplement_count": len(records),
        "target_slot_count": len(target),
        "remaining_slot_count": len(remaining),
        "available_roles": {slot: sorted(available[slot]) for slot in remaining},
        "one_role_per_slot_feasible": feasible,
        "feasibility_proof_sha256": proof,
        "query_text_included": False,
        "model_calls": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = validate_supplements(payload["records"])
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
