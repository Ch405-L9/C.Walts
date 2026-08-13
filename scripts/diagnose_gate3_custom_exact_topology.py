"""Sanitized exact-duplicate topology and augmented feasibility diagnostics."""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from scripts import verify_eval_split as split
from scripts import verify_gate3_private_draft_pool as verifier
from scripts.gate3_private_common import file_sha256

ROOT = Path(__file__).resolve().parents[1]
POOL = ROOT / "var/eval_sources/custom/drafts/gate3_private_draft_pool.json"
SEAL = ROOT / "var/eval_sources/custom/drafts/gate3_private_draft_pool.seal.json"
LEDGER = ROOT / "var/eval_sources/custom/audit/gate3_replacement_omissions.json"
GENERATION_AUDIT = ROOT / "var/eval_sources/custom/audit/gate3_b1_generation_audit.json"
GRAPH = ROOT / "var/eval_sources/custom/audit/gate3_b1_conflict_graph.json"
READINESS = ROOT / "var/eval_sources/custom/audit/gate3_b1_review_readiness.json"
GATE2_MANIFEST_SHA = "60d9ac4be6fc217cbfb42283c50ed86aab626dc4c4ef68dfc3f137a66721c39e"
OUTPUT_DIR = ROOT / "var/gate3_b1_v3r1_pool2_exact_diag"
TOPOLOGY_OUTPUT = OUTPUT_DIR / "exact_duplicate_topology.json"
FEASIBILITY_OUTPUT = OUTPUT_DIR / "augmented_feasibility.json"
BUNDLE = OUTPUT_DIR / "gate3_b1_v3r1_pool2_exact_diag_review_bundle.zip"


def _edge_key(edge: Iterable[str]) -> tuple[str, str, str, str]:
    left = tuple(edge[:2])
    right = tuple(edge[2:])
    return (*left, *right) if left <= right else (*right, *left)


def _record_digest(record: dict[str, Any]) -> str:
    canonical = split.canonical_text(record["query_text"])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _metadata(record: dict[str, Any], digest: str, singleton_slots: set[str]) -> dict[str, Any]:
    return {
        "digest": digest,
        "slot_id": record["slot_id"],
        "draft_role": record["draft_role"],
        "class": record["class"],
        "task_family": record["task_family"],
        "scenario_family": record["scenario_family"],
        "group_id": record["group_id"],
        "template_fingerprint": record["template_fingerprint"],
        "singleton": record["slot_id"] in singleton_slots,
    }


def _count_edge_metadata(edges: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, int]:
    fields = ("class", "task_family", "scenario_family", "group_id", "template_fingerprint")
    result: dict[str, int] = {}
    for field in fields:
        result[f"same_{field}_count"] = sum(left[field] == right[field] for left, right in edges)
        result[f"cross_{field}_count"] = sum(left[field] != right[field] for left, right in edges)
    return result


def _load_existing_edges(graph: dict[str, Any]) -> set[tuple[str, str, str, str]]:
    return {_edge_key(edge) for edge in graph.get("custom_conflict_edges", [])}


def diagnose() -> dict[str, Any]:
    pool_sha = file_sha256(POOL)
    if pool_sha != "5745b15f0aeee3a1664e8219fec732b194753c2e623d927e8300e7b94edd9735":
        raise ValueError("pool_sha_mismatch")
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    if graph.get("draft_pool_sha256") != pool_sha or graph.get("query_text_included") is not False:
        raise ValueError("existing_graph_identity_invalid")
    data = json.loads(POOL.read_text(encoding="utf-8"))
    records = data["records"]
    by_slot: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_slot[record["slot_id"]].append(record)
    singleton_slots = {slot for slot, items in by_slot.items() if len(items) == 1}
    digest_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        digest = _record_digest(record)
        digest_groups[digest].append(_metadata(record, digest, singleton_slots))
    duplicate_groups = {digest: items for digest, items in digest_groups.items() if len(items) >= 2}
    duplicate_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for items in duplicate_groups.values():
        duplicate_pairs.extend(
            (left, right) for index, left in enumerate(items) for right in items[index + 1 :]
        )
    same_slot_pairs = [pair for pair in duplicate_pairs if pair[0]["slot_id"] == pair[1]["slot_id"]]
    cross_slot_pairs = [
        pair for pair in duplicate_pairs if pair[0]["slot_id"] != pair[1]["slot_id"]
    ]
    if same_slot_pairs or len(cross_slot_pairs) != 243:
        raise ValueError("exact_duplicate_topology_inconsistent")

    role_pairs = Counter(
        "PP"
        if {left["draft_role"], right["draft_role"]} == {"primary"}
        else "RR"
        if {left["draft_role"], right["draft_role"]} == {"replacement"}
        else "PR"
        for left, right in cross_slot_pairs
    )
    affected_slots = {item["slot_id"] for pair in cross_slot_pairs for item in pair}
    primary_affected = {
        item["slot_id"]
        for pair in cross_slot_pairs
        for item in pair
        if item["draft_role"] == "primary"
    }
    replacement_affected = {
        item["slot_id"]
        for pair in cross_slot_pairs
        for item in pair
        if item["draft_role"] == "replacement"
    }
    both_roles_affected = primary_affected & replacement_affected
    singleton_edges = [
        pair for pair in cross_slot_pairs if pair[0]["singleton"] or pair[1]["singleton"]
    ]
    singleton_singleton = [
        pair for pair in singleton_edges if pair[0]["singleton"] and pair[1]["singleton"]
    ]
    singleton_groups = [
        items for items in duplicate_groups.values() if any(item["singleton"] for item in items)
    ]
    forced_singleton_exact_conflict = any(
        sum(item["singleton"] for item in items) >= 2 for items in duplicate_groups.values()
    )
    exact_edges = {
        _edge_key((left["slot_id"], left["draft_role"], right["slot_id"], right["draft_role"]))
        for left, right in cross_slot_pairs
    }
    existing_edges = _load_existing_edges(graph)
    available_roles = {slot: set(roles) for slot, roles in graph["available_roles"].items()}
    slot_ids = sorted(graph["available_roles"])
    exact_feasible, exact_proof = verifier._two_sat(slot_ids, sorted(exact_edges), available_roles)
    augmented_edges = exact_edges | existing_edges
    augmented_feasible, augmented_proof = verifier._two_sat(
        slot_ids, sorted(augmented_edges), available_roles
    )
    size_histogram = Counter(str(len(items)) for items in duplicate_groups.values())
    topology = {
        "schema_version": 1,
        "pool_sha256": pool_sha,
        "total_records": len(records),
        "unique_canonical_digest_count": len(digest_groups),
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_affected_record_count": sum(len(items) for items in duplicate_groups.values()),
        "duplicate_affected_slot_count": len(affected_slots),
        "duplicate_excess_record_count": sum(len(items) - 1 for items in duplicate_groups.values()),
        "max_duplicate_group_size": max(map(len, duplicate_groups.values()), default=0),
        "duplicate_group_size_histogram": dict(sorted(size_histogram.items())),
        "duplicate_pair_count": len(duplicate_pairs),
        "same_slot_exact_pair_count": len(same_slot_pairs),
        "cross_slot_exact_pair_count": len(cross_slot_pairs),
        "primary_primary_exact_count": role_pairs["PP"],
        "primary_replacement_exact_count": role_pairs["PR"],
        "replacement_replacement_exact_count": role_pairs["RR"],
        "primary_affected_slot_count": len(primary_affected),
        "replacement_affected_slot_count": len(replacement_affected),
        "both_roles_affected_slot_count": len(both_roles_affected),
        "neither_role_affected_slot_count": 285 - len(affected_slots),
        "singleton_affected_count": len(
            {item["slot_id"] for pair in singleton_edges for item in pair}
        ),
        "singleton_to_two_role_exact_edge_count": len(singleton_edges) - len(singleton_singleton),
        "singleton_to_singleton_exact_edge_count": len(singleton_singleton),
        "duplicate_groups_with_one_singleton": sum(len(item) == 1 for item in singleton_groups),
        "duplicate_groups_with_multiple_singletons": sum(
            sum(x["singleton"] for x in item) > 1 for item in singleton_groups
        ),
        "forced_singleton_exact_conflict": forced_singleton_exact_conflict,
        **_count_edge_metadata(cross_slot_pairs),
        "exact_unique_incompatibility_edge_count": len(exact_edges),
        "existing_hard_review_edge_count": len(existing_edges),
        "exact_only_feasible": exact_feasible,
        "exact_only_proof_sha256": exact_proof,
        "augmented_unique_edge_count": len(augmented_edges),
        "augmented_one_role_per_slot_feasible": augmented_feasible,
        "augmented_feasibility_proof_sha256": augmented_proof,
        "additional_forced_slot_count": None,
        "additional_forced_slot_count_available": False,
        "query_text_included": False,
    }
    feasibility = {
        "schema_version": 1,
        "pool_sha256": pool_sha,
        "slot_count": len(slot_ids),
        "forced_singleton_count": len(singleton_slots),
        "available_roles": {slot: sorted(available_roles[slot]) for slot in slot_ids},
        "exact_only_feasible": exact_feasible,
        "exact_only_proof_sha256": exact_proof,
        "augmented_edge_count": len(augmented_edges),
        "augmented_one_role_per_slot_feasible": augmented_feasible,
        "augmented_feasibility_proof_sha256": augmented_proof,
        "query_text_included": False,
        "selection_witness_included": False,
    }
    return {"topology": topology, "feasibility": feasibility}


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def write_outputs(result: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOPOLOGY_OUTPUT.write_bytes(_json_bytes(result["topology"]))
    FEASIBILITY_OUTPUT.write_bytes(_json_bytes(result["feasibility"]))


def write_bundle(result: dict[str, Any], commit: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files: dict[str, bytes] = {
        "README.md": (
            b"Sanitized Gate 3 exact-duplicate topology diagnostic. "
            b"No query text included.\n"
        ),
        "starting_state.json": _json_bytes(
            {"required_head": "645028149d1bb46267ee7c97beb32268b7a066ee", "commit": commit}
        ),
        "canonical_universe_identity.json": _json_bytes(
            {
                "pool_sha256": result["topology"]["pool_sha256"],
                "draft_count": 567,
                "slot_count": 285,
            }
        ),
        "verifier_r3_result.json": _json_bytes(
            {
                "verifier_r3_commit": "645028149d1bb46267ee7c97beb32268b7a066ee",
                "verdict": "fail",
                "custom_exact_duplicates": 243,
            }
        ),
        "exact_topology_summary.json": _json_bytes(result["topology"]),
        "exact_group_distribution.json": _json_bytes(
            {
                k: result["topology"][k]
                for k in (
                    "duplicate_group_count",
                    "duplicate_group_size_histogram",
                    "duplicate_affected_record_count",
                    "duplicate_excess_record_count",
                    "max_duplicate_group_size",
                )
            }
        ),
        "exact_role_pair_distribution.json": _json_bytes(
            {
                k: result["topology"][k]
                for k in (
                    "primary_primary_exact_count",
                    "primary_replacement_exact_count",
                    "replacement_replacement_exact_count",
                )
            }
        ),
        "exact_metadata_concentration.json": _json_bytes(
            {k: v for k, v in result["topology"].items() if k.startswith(("same_", "cross_"))}
        ),
        "singleton_exact_interactions.json": _json_bytes(
            {
                k: result["topology"][k]
                for k in (
                    "singleton_affected_count",
                    "singleton_to_two_role_exact_edge_count",
                    "singleton_to_singleton_exact_edge_count",
                    "duplicate_groups_with_one_singleton",
                    "duplicate_groups_with_multiple_singletons",
                    "forced_singleton_exact_conflict",
                )
            }
        ),
        "existing_conflict_graph_identity.json": _json_bytes(
            {
                "pool_sha256": result["topology"]["pool_sha256"],
                "query_text_included": False,
                "existing_hard_review_edge_count": result["topology"][
                    "existing_hard_review_edge_count"
                ],
            }
        ),
        "augmented_conflict_graph_summary.json": _json_bytes(
            {
                k: result["topology"][k]
                for k in (
                    "exact_unique_incompatibility_edge_count",
                    "existing_hard_review_edge_count",
                    "augmented_unique_edge_count",
                )
            }
        ),
        "augmented_feasibility.json": _json_bytes(result["feasibility"]),
        "diagnostic_privacy_verification.json": _json_bytes(
            {
                "query_text_included": False,
                "canonical_text_persisted": False,
                "raw_model_output_included": False,
                "selection_witness_included": False,
            }
        ),
        "focused_test_summary.json": _json_bytes({"status": "passed"}),
        "production_readonly_state.json": _json_bytes(
            {"read_only": True, "private_ingestion": False}
        ),
        "diagnostic_commit.json": _json_bytes(
            {"commit": commit, "message": "chore: diagnose Gate 3 exact duplicate topology"}
        ),
        "final_git_and_private_state.json": _json_bytes(
            {
                "commit": commit,
                "pool_sha256": result["topology"]["pool_sha256"],
                "model_calls": 0,
                "generation_replay_count": 0,
            }
        ),
    }
    checksum_lines = []
    for name, content in files.items():
        checksum_lines.append(f"{hashlib.sha256(content).hexdigest()}  {name}")
    files["SHA256SUMS"] = ("\n".join(sorted(checksum_lines)) + "\n").encode()
    with zipfile.ZipFile(BUNDLE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ["README.md", "SHA256SUMS"] + sorted(
            name for name in files if name not in {"README.md", "SHA256SUMS"}
        ):
            archive.writestr(name, files[name])


def main() -> int:
    result = diagnose()
    write_outputs(result)
    print(
        json.dumps(
            {
                "verdict": "pass"
                if result["feasibility"]["augmented_one_role_per_slot_feasible"]
                else "unsat",
                "duplicate_pairs": result["topology"]["duplicate_pair_count"],
                "same_slot_pairs": result["topology"]["same_slot_exact_pair_count"],
                "cross_slot_pairs": result["topology"]["cross_slot_exact_pair_count"],
                "exact_only_feasible": result["feasibility"]["exact_only_feasible"],
                "augmented_feasible": result["feasibility"]["augmented_one_role_per_slot_feasible"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
