from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from scripts import gate3_private_common as common
from scripts import generate_gate3_private_candidates as generator

ROOT = Path(__file__).resolve().parents[1]


def test_surface_contract_is_balanced_and_metadata_only() -> None:
    contract = common.load_surface_profiles()
    assert contract["contract_id"] == "gate3-surface-variation-v1"
    assert contract["assignment_id"] == "slot-ordinal-mod3-v1"
    assert set(contract["profiles"]) == {"A", "B", "C"}
    for profile in contract["profiles"].values():
        assert profile["semantic_preservation_required"] is True
        assert profile["second_task_forbidden"] is True
        assert profile["new_fact_invention_forbidden"] is True
        assert not any(
            term in profile["instruction"].lower() for term in ("qrel", "holdout", "calibration")
        )


def test_profile_schedule_is_balanced_and_shadow_ordinal_equivalent() -> None:
    canonical = [common.surface_profile_pair(n) for n in range(1, 286)]
    shadow = [common.surface_profile_pair(n) for n in range(1, 286)]
    assert canonical == shadow
    primary = {key: 0 for key in "ABC"}
    replacement = {key: 0 for key in "ABC"}
    profiles = common.load_surface_profiles()["profiles"]
    reverse = {value["profile_id"]: key for key, value in profiles.items()}
    for left, right in canonical:
        primary[reverse[left["profile_id"]]] += 1
        replacement[reverse[right["profile_id"]]] += 1
    assert primary == replacement == {"A": 95, "B": 95, "C": 95}


def test_effective_prompt_identity_is_bound_without_changing_base_prompt() -> None:
    prompt = ROOT / "config/gate3_custom_generation_prompt.txt"
    assert hashlib.sha256(prompt.read_bytes()).hexdigest() == (
        "e48d79b4b7599e291e495dcbd87af6f96953c19de99fbe46d0de989c5b638ba7"
    )
    policy = yaml.safe_load((ROOT / "config/gate3_custom_authoring_policy.yaml").read_text())
    assert policy["policy_id"] == "gate3-custom-authoring-v3"
    assert policy["authoring_revision"] == "gate3-v3-r1-role-surface"
    assert policy["effective_prompt_contract_sha256"] == common.effective_prompt_contract_sha256(
        policy["prompt_sha256"]
    )


def test_prompt_receives_profile_but_not_primary_text() -> None:
    profile, _ = common.surface_profile_pair(1)
    prompt = generator.build_generation_prompt(
        generator.load_base_prompt(), {"slot_id": "G3S-9001"}, "primary", profile
    )
    assert "Surface realization profile (instruction):" in prompt
    assert "synthetic primary prose" not in prompt
    assert "qrel" not in prompt.lower()


def test_profile_pair_prompts_are_distinct_instructions() -> None:
    base = generator.load_base_prompt()
    profiles = common.load_surface_profiles()["profiles"]
    prompts = {
        key: generator.build_generation_prompt(base, {"slot_id": "synthetic"}, "primary", value)
        for key, value in profiles.items()
    }
    assert len({prompts["A"], prompts["B"], prompts["C"]}) == 3
    assert prompts["A"] != prompts["B"]
    assert prompts["B"] != prompts["C"]
    assert prompts["C"] != prompts["A"]


def test_no_failed_shadow_id_special_cases_in_generation_code() -> None:
    source = (ROOT / "scripts/generate_gate3_private_candidates.py").read_text()
    for failed_id in ("G3S-9068", "G3S-9078", "G3S-9085", "G3S-9278"):
        assert failed_id not in source
    assert "slot_ordinal=index" in source


def test_authorization_is_pool2_only() -> None:
    assert common.GENERATION_ACTIVATION == "gate3-b1-v3r1-pool2"
    assert common.GENERATION_V3R1_POOL2_AUTHORIZATION == "NFR_GATE3_B1_V3R1_POOL2_AUTHORIZED"
    assert (
        "NFR_GATE3_B1_V3_AUTHORIZED"
        not in (ROOT / "scripts/generate_gate3_private_candidates.py").read_text()
    )


def test_parameter_and_seed_contract_unchanged() -> None:
    freeze = json.loads((ROOT / "config/gate3_generation_freeze.json").read_text())
    assert (
        freeze["parameter_hash"]
        == "15d29fc7b64faf33d191b42ca4646470f696c691f811632430a8880e10e549f1"
    )
    assert (
        common.derive_request_seed("gate3-custom-authoring-v3", "G3S-0001", "primary", 1)
        == 515879888
    )
