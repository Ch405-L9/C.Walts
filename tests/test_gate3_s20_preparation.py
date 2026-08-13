from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jsonschema import ValidationError

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


def _mock_git_run(monkeypatch, status: bytes):
    def run(command, **kwargs):
        if command[1:3] == ["rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(command, 0, stdout="a" * 40, stderr="")
        if command[1:3] == ["rev-parse", "@{upstream}"]:
            return subprocess.CompletedProcess(command, 0, stdout="a" * 40, stderr="")
        return subprocess.CompletedProcess(command, 0, stdout=status, stderr=b"")

    monkeypatch.setattr(generator.subprocess, "run", run)
    monkeypatch.setattr(generator.shutil, "which", lambda _: "/usr/bin/git")


def test_runtime_guard_accepts_literal_owner_paths_and_empty_status(monkeypatch) -> None:
    owner = (
        b"?? C.Walts Stage 2.2B-1C Noncompliance Correction.md\0"
        b"?? C.Walts Stage 2.2B-1C Noncompliance Correction.pdf\0"
    )
    _mock_git_run(monkeypatch, owner)
    generator._runtime_state("a" * 40)
    _mock_git_run(monkeypatch, b"")
    generator._runtime_state("a" * 40)


@pytest.mark.parametrize(
    "status",
    [
        b"?? unexpected.txt\0",
        b" M tracked_file.py\0",
        b"M  tracked_file.py\0",
        b"?? C.Walts Stage 2.2B-1C Noncompliance Correction.md\0M  tracked_file.py\0",
    ],
)
def test_runtime_guard_rejects_unapproved_status(monkeypatch, status) -> None:
    _mock_git_run(monkeypatch, status)
    with pytest.raises(RuntimeError, match="runtime_worktree_not_clean"):
        generator._runtime_state("a" * 40)


def test_runtime_guard_rejects_rename_record(monkeypatch) -> None:
    _mock_git_run(monkeypatch, b"R  old.txt\0new.txt\0")
    with pytest.raises(RuntimeError, match="runtime_worktree_not_clean"):
        generator._runtime_state("a" * 40)


@pytest.mark.parametrize(
    "marker, expected",
    [
        ("runtime_worktree_not_clean", ("preflight_failure", "worktree_not_clean")),
        ("runtime_head_mismatch", ("preflight_failure", "head_mismatch")),
        ("runtime_expected_head_invalid", ("preflight_failure", "expected_head_invalid")),
        ("git_unavailable", ("preflight_failure", "git_unavailable")),
        ("supplement_artifact_preexists", ("preflight_failure", "artifact_preexists")),
        ("supplemental_authorization_missing", ("preflight_failure", "authorization_missing")),
        ("freeze_identity_mismatch:generator", ("preflight_failure", "freeze_identity_mismatch")),
    ],
)
def test_bounded_preflight_failures_are_classified(marker, expected) -> None:
    assert generator._stable_failure(RuntimeError(marker)) == expected


def test_generalized_solver_supports_units_and_replacement_only() -> None:
    feasible, _ = validator._two_sat_generalized(
        ["A", "B"], [], {"A": {"primary"}, "B": {"replacement"}}
    )
    assert feasible
    feasible, _ = validator._two_sat_generalized(
        ["A", "B"], [("A", "primary", "B", "replacement")], {"A": {"primary"}, "B": {"replacement"}}
    )
    assert not feasible
    old, _ = validator.base_verifier._two_sat(["A", "B"], [], {"A": {"primary"}, "B": {"primary"}})
    new, _ = validator._two_sat_generalized(["A", "B"], [], {"A": {"primary"}, "B": {"primary"}})
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


def test_exact_role_disposition_is_scoped() -> None:
    targets = {"G3S-0101", "G3S-0102"}
    assert validator.exact_base_action("G3S-0101", "G3S-0101", targets, True) == "fatal_same_target"
    assert (
        validator.exact_base_action("G3S-0101", "G3S-0102", targets, True)
        == "ignore_repaired_target"
    )
    assert validator.exact_base_action("G3S-0101", "G3S-0200", targets, True) == "remove_role"
    assert validator.exact_base_action("G3S-0101", "G3S-0200", targets, False) == "none"


def test_prompt_contains_frozen_base_and_no_history() -> None:
    slot = validator.target_metadata()[EXPECTED_TARGETS[0]]
    prompt = generator._prompt(slot, generator._profile_for(EXPECTED_TARGETS[0]))
    base = (ROOT / "config/gate3_custom_generation_prompt.txt").read_text()
    assert base in prompt
    assert "Supplemental-20 instruction layer:" in prompt
    assert slot["slot_id"] in prompt
    assert "previous candidate" in prompt
    assert "PRIVATE_HISTORICAL_QUERY_SENTINEL" not in prompt


def test_failure_classifier_never_uses_exception_text() -> None:
    stable, detail = generator._stable_failure(ValueError("PRIVATE_QUERY_SENTINEL"))
    assert (stable, detail) == ("internal_error", "unclassified")
    assert "PRIVATE_QUERY_SENTINEL" not in json.dumps({"stable": stable, "detail": detail})


def test_cli_failure_boundary_sanitizes_non_runtime_exception(monkeypatch, capsys) -> None:
    def fail(_expected_head: str) -> None:
        raise ValidationError(
            "PRIVATE_QUERY_SENTINEL", instance={"query_text": "PRIVATE_QUERY_SENTINEL"}
        )

    monkeypatch.setattr(generator, "generate", fail)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_gate3_s20_supplements.py",
            "--generate",
            "--confirm-gate3-s20-generation",
            "--expected-head",
            "a" * 40,
        ],
    )
    assert generator.main() == 1
    captured = capsys.readouterr()
    assert "PRIVATE_QUERY_SENTINEL" not in captured.out
    assert "PRIVATE_QUERY_SENTINEL" not in captured.err
    assert "Traceback" not in captured.out + captured.err
    assert json.loads(captured.out) == {
        "detail_code": "schema_failure",
        "stable_error_code": "format_safety_failure",
        "verdict": "fail",
    }
    stable, detail = generator._stable_failure(
        ValidationError("PRIVATE_QUERY_SENTINEL", instance={"query_text": "PRIVATE_QUERY_SENTINEL"})
    )
    assert (stable, detail) == ("format_safety_failure", "schema_failure")
    assert "PRIVATE_QUERY_SENTINEL" not in json.dumps({"stable": stable, "detail": detail})


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
    slots = yaml.safe_load((ROOT / "config/gate3_custom_authoring_slots.yaml").read_text())
    monkeypatch.setattr(generator, "_load", lambda: (freeze, policy, slots))
    monkeypatch.setattr(generator, "require_loopback", lambda _: None)
    monkeypatch.setattr(generator, "verify_model_identity", lambda _: {"model": "mock"})
    monkeypatch.setattr(generator, "validate_draft", lambda _: None)
    monkeypatch.setattr(
        generator.validator,
        "validate_supplements",
        lambda *a, **k: {"one_role_per_slot_feasible": True},
    )
    monkeypatch.setattr(generator, "resolve_private_path", lambda rel: tmp_path / Path(rel).name)
    monkeypatch.setattr(generator, "_runtime_state", lambda _: None)
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
    result = generator.generate("a" * 40)
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
    result = generator.generate("a" * 40)
    assert len(calls) == 22
    assert result["attempts"] == 22
    assert result["retries"] == 2
    assert calls[:3] == [
        generator.derive_supplement_seed("gate3-v3r1-s20-supplement-v1", EXPECTED_TARGETS[0], n)
        for n in (1, 2, 3)
    ]


def test_mocked_terminal_failure_writes_only_sanitized_failure(monkeypatch, tmp_path) -> None:
    responses = [ValueError("terminal") for _ in range(3)]
    _mock_generator(monkeypatch, tmp_path, responses)
    with pytest.raises(RuntimeError):
        generator.generate("a" * 40)
    assert not (tmp_path / "gate3_s20_supplement_pool.json").exists()
    assert not (tmp_path / "gate3_s20_supplement_pool.seal.json").exists()
    failure = json.loads((tmp_path / "gate3_s20_generation_failure.json").read_text())
    assert failure["query_text_recorded"] is False
    assert "query_text" not in failure


def test_staged_install_rolls_back_without_deleting_preexisting_artifacts(tmp_path) -> None:
    staged = tmp_path / "stage"
    staged.mkdir()
    for name in ("pool", "audit", "seal"):
        (staged / name).write_text(name)
    destinations = tuple(tmp_path / name for name in ("pool", "audit", "seal"))
    destinations[1].write_text("preexisting")
    with pytest.raises(RuntimeError, match="supplement_artifact_preexists"):
        generator._install_staged_artifacts(staged, destinations)
    assert not destinations[0].exists()
    assert destinations[1].read_text() == "preexisting"
    assert not destinations[2].exists()
