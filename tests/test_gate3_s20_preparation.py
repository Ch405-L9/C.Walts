from __future__ import annotations

import json
from pathlib import Path

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
