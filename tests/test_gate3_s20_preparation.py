from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts import generate_gate3_s20_supplements as generator
from scripts import verify_gate3_s20_supplemental_repair as validator
from scripts.gate3_private_common import canonical_sha256, derive_request_seed

ROOT = Path(__file__).resolve().parents[1]
TARGET = json.loads((ROOT / "config/gate3_s20_target_slots.json").read_text())
EXPECTED_TARGETS = TARGET["slot_ids"]


def test_target_set_and_rebinding() -> None:
    assert len(EXPECTED_TARGETS) == 20
    assert EXPECTED_TARGETS == sorted(set(EXPECTED_TARGETS))
    assert TARGET["repair_set_sha256"] == canonical_sha256(EXPECTED_TARGETS)
    assert set(validator.target_metadata()) == set(EXPECTED_TARGETS)


def test_target_singleton_reconciliation() -> None:
    assert validator.target_role_counts() == {
        "singleton_count": 1,
        "two_role_count": 19,
        "singleton_slot_id": "G3S-0162",
    }


def test_unused_surface_assignment_is_deterministic() -> None:
    assignment = validator.target_surface_profiles()
    assert set(assignment.values()) <= {"A", "B", "C"}
    assert assignment["G3S-0101"] == "A"
    assert assignment["G3S-0102"] == "B"
    assert assignment["G3S-0106"] == "C"
    assert len(assignment) == 20


def test_supplement_seed_contract() -> None:
    expected = [
        derive_request_seed(
            "gate3-custom-authoring-v3",
            "G3S-0101",
            "supplemental",
            attempt,
            17,
        )
        for attempt in (1, 2, 3)
    ]
    actual = [
        generator.derive_supplement_seed("gate3-custom-authoring-v3", "G3S-0101", attempt)
        for attempt in (1, 2, 3)
    ]
    assert actual == expected
    assert len(set(actual)) == 3


def test_authorization_guard_is_independent(monkeypatch) -> None:
    monkeypatch.delenv("NFR_GATE3_B1_S20_AUTHORIZED", raising=False)
    monkeypatch.setenv("NFR_ALLOW_PRIVATE_EVAL_GENERATION", "true")
    monkeypatch.setenv("NFR_GATE3_B_AUTHORIZED", "true")
    assert not all(generator.authorization_status().values())
    monkeypatch.setenv("NFR_GATE3_B1_S20_AUTHORIZED", "true")
    assert all(generator.authorization_status().values())


def test_generalized_solver_supports_units_and_replacement_only() -> None:
    feasible, _ = validator._two_sat_generalized(
        ["A", "B"], [], {"A": {"primary"}, "B": {"replacement"}}
    )
    assert feasible
    feasible, _ = validator._two_sat_generalized(
        ["A", "B"], [("A", "primary", "B", "replacement")], {"A": {"primary"}, "B": {"replacement"}}
    )
    assert not feasible
    old, _ = validator.base_verifier._two_sat(
        ["A", "B"], [], {"A": {"primary"}, "B": {"primary"}}
    )
    new, _ = validator._two_sat_generalized(
        ["A", "B"], [], {"A": {"primary"}, "B": {"primary"}}
    )
    assert old == new


def test_no_generation_or_private_text_output_in_pre_tools() -> None:
    for name in ("generate_gate3_s20_supplements.py", "verify_gate3_s20_supplemental_repair.py"):
        source = (ROOT / "scripts" / name).read_text()
        assert "ollama" not in source.lower()
        assert "print(query" not in source
    assert not (
        ROOT / "var/eval_sources/custom/supplements/gate3_s20_supplement_pool.json"
    ).exists()


def test_base_exact_edges_reconstruct_accepted_count() -> None:
    pool = json.loads(
        (ROOT / "var/eval_sources/custom/drafts/gate3_private_draft_pool.json").read_text()
    )["records"]
    assert len(validator.base_exact_edges(pool)) == 243


def _mock_generator(monkeypatch, tmp_path, responses):
    freeze = json.loads((ROOT / "config/gate3_s20_generation_freeze.json").read_text())
    policy = json.loads(
        json.dumps(
            {
                "policy_id": "gate3-custom-authoring-v3",
                "supplement_policy_id": "gate3-v3r1-s20-supplement-v1",
            }
        )
    )
    slots = yaml.safe_load(
        (ROOT / "config/gate3_custom_authoring_slots.yaml").read_text()
    )
    monkeypatch.setattr(generator, "_load", lambda: (freeze, policy, slots))
    monkeypatch.setattr(generator, "require_loopback", lambda _: None)
    monkeypatch.setattr(generator, "verify_model_identity", lambda _: {"model": "mock"})
    monkeypatch.setattr(generator, "validate_draft", lambda _: None)
    monkeypatch.setattr(generator.validator, "validate_supplements", lambda *a, **k: {})
    monkeypatch.setattr(generator, "resolve_private_path", lambda rel: tmp_path / Path(rel).name)
    monkeypatch.setattr(generator, "current_git_head", lambda: "mock-head")
    calls = []

    def request(_freeze, _prompt, seed):
        calls.append(seed)
        response = responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        assert response["draft_role"] == "supplemental"
        return response

    monkeypatch.setattr(generator, "_model_request", request)
    monkeypatch.setenv("NFR_ALLOW_PRIVATE_EVAL_GENERATION", "true")
    monkeypatch.setenv("NFR_GATE3_B_AUTHORIZED", "true")
    monkeypatch.setenv("NFR_GATE3_B1_S20_AUTHORIZED", "true")
    return calls, slots


def test_mocked_twenty_slot_path_is_atomic_and_ordered(monkeypatch, tmp_path) -> None:
    responses = [
        {"slot_id": slot, "draft_role": "supplemental", "query_text": f"synthetic {i}"}
        for i, slot in enumerate(EXPECTED_TARGETS)
    ]
    calls, _ = _mock_generator(monkeypatch, tmp_path, responses)
    result = generator.generate()
    assert result["accepted_count"] == 20
    assert len(calls) == 20
    assert (tmp_path / "gate3_s20_supplement_pool.json").exists()
    assert (tmp_path / "gate3_s20_supplement_pool.seal.json").exists()
    records = json.loads((tmp_path / "gate3_s20_supplement_pool.json").read_text())["records"]
    assert [record["slot_id"] for record in records] == EXPECTED_TARGETS


def test_mocked_retry_is_same_slot_and_three_calls(monkeypatch, tmp_path) -> None:
    responses = [
        ValueError("exact_conflict"),
        ValueError("supplemental_structural_unsat"),
        {"slot_id": EXPECTED_TARGETS[0], "draft_role": "supplemental", "query_text": "ok"},
    ]
    responses.extend(
        {"slot_id": slot, "draft_role": "supplemental", "query_text": f"synthetic {i}"}
        for i, slot in enumerate(EXPECTED_TARGETS[1:], start=1)
    )
    calls, _ = _mock_generator(monkeypatch, tmp_path, responses)
    generator.generate()
    assert len(calls) == 22
    assert calls[:3] == [
        generator.derive_supplement_seed("gate3-v3r1-s20-supplement-v1", EXPECTED_TARGETS[0], n)
        for n in (1, 2, 3)
    ]


def test_mocked_terminal_failure_writes_only_sanitized_failure(monkeypatch, tmp_path) -> None:
    responses = [ValueError("terminal") for _ in range(3)]
    _mock_generator(monkeypatch, tmp_path, responses)
    with pytest.raises(ValueError):
        generator.generate()
    assert not (tmp_path / "gate3_s20_supplement_pool.json").exists()
    assert not (tmp_path / "gate3_s20_supplement_pool.seal.json").exists()
    failure = json.loads((tmp_path / "gate3_s20_generation_failure.json").read_text())
    assert failure["query_text_recorded"] is False
    assert "query_text" not in failure
