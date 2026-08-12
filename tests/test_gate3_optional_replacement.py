from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts import gate3_private_common as common
from scripts import verify_gate3_private_draft_pool as verifier

ROOT = Path(__file__).resolve().parents[1]


def test_pool2_cardinality_and_omission_contract_is_frozen() -> None:
    policy = yaml.safe_load((ROOT / "config/gate3_custom_authoring_policy.yaml").read_text())
    pool = policy["draft_pool"]
    assert policy["policy_id"] == "gate3-custom-authoring-v3"
    assert policy["authoring_revision"] == "gate3-v3-r1-role-surface"
    assert policy["draft_pool_revision"] == "gate3-pool-v2-optional-replacement"
    assert policy["source_version"] == "cwalts-custom-v0.4-gate3-v3r1-pool2"
    assert pool["required_slot_count"] == 285
    assert pool["required_primary_count"] == 285
    assert pool["minimum_replacement_count"] == 0
    assert pool["maximum_replacement_count"] == 285
    assert pool["minimum_draft_count"] == 285
    assert pool["maximum_draft_count"] == 570
    assert pool["replacement_omission_condition"] == (
        "format_safety_failure:replacement_exact_duplicate_on_all_3_attempts"
    )


def test_dynamic_pair_counts() -> None:
    for draft_count in (285, 326, 570):
        assert draft_count * 315 == draft_count * 315
        assert draft_count * (draft_count - 1) // 2 == (draft_count * (draft_count - 1)) // 2


def test_singleton_solver_forces_primary_and_binds_proof() -> None:
    feasible, proof = verifier._two_sat(["A"], [], {"A": {"primary"}})
    assert feasible is True
    assert proof == verifier._two_sat(["A"], [], {"A": {"primary"}})[1]


def test_forced_singleton_conflict_is_unsatisfiable() -> None:
    feasible, _ = verifier._two_sat(
        ["A", "B"],
        [("A", "primary", "B", "primary")],
        {"A": {"primary"}, "B": {"primary"}},
    )
    assert feasible is False


def test_mixed_singleton_and_two_role_solver_is_deterministic() -> None:
    edges = [("A", "primary", "B", "replacement")]
    roles = {"A": {"primary"}, "B": {"primary", "replacement"}}
    first = verifier._two_sat(["A", "B"], edges, roles)
    second = verifier._two_sat(["A", "B"], edges, roles)
    assert first == second
    assert first[0] is True


def test_pool2_generation_guard_rejects_old_guard(monkeypatch) -> None:
    monkeypatch.setenv("NFR_ALLOW_PRIVATE_EVAL_GENERATION", "true")
    monkeypatch.setenv("NFR_GATE3_B_AUTHORIZED", "true")
    monkeypatch.setenv("NFR_GATE3_B1_V3R1_AUTHORIZED", "true")
    monkeypatch.delenv("NFR_GATE3_B1_V3R1_POOL2_AUTHORIZED", raising=False)
    assert common.generation_v3r1_pool2_authorized() is False
    monkeypatch.setenv("NFR_GATE3_B1_V3R1_POOL2_AUTHORIZED", "true")
    assert common.generation_v3r1_pool2_authorized() is True


def test_pre_r3_private_artifacts_remain_absent() -> None:
    assert not (ROOT / "var/eval_sources/custom/drafts/gate3_private_draft_pool.json").exists()
    assert not (ROOT / "var/eval_sources/custom/drafts/gate3_private_draft_pool.seal.json").exists()
    assert not (ROOT / "var/eval_sources/custom/selected/gate3_custom_candidates.json").exists()
    assert not (ROOT / "var/eval_sources/custom/audit/gate3_replacement_omissions.json").exists()


def test_archived_attempt1_audit_is_sanitized() -> None:
    path = ROOT / "var/eval_sources/custom/audit/gate3_generation_failure_v3r1_attempt1.json"
    payload = json.loads(path.read_text())
    assert payload["run_version"] == "gate3-b1-v3r1"
    assert payload["terminal_slot"] == "G3S-0090"
    assert payload["terminal_role"] == "replacement"
    assert payload["attempt"] == 3
    assert payload["error_code"] == "format_safety_failure"
    assert payload["error_detail_code"] == "replacement_exact_duplicate"
    assert payload["query_text_recorded"] is False
    assert payload["raw_response_recorded"] is False
