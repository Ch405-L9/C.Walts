from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import jsonschema
import pytest
import yaml

from scripts import gate3_private_common as common
from scripts import generate_gate3_private_candidates as generator
from scripts import review_gate3_private_candidates as reviewer
from scripts import verify_gate3_private_candidates as validator
from scripts import verify_gate3_private_draft_pool as draft_pool

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config/gate3_custom_authoring_policy.yaml"
SLOTS = ROOT / "config/gate3_custom_authoring_slots.yaml"
PROMPT = ROOT / "config/gate3_custom_generation_prompt.txt"
OUTPUT_SCHEMA = ROOT / "schemas/gate3_generated_draft.schema.json"
FREEZE = ROOT / "config/gate3_generation_freeze.json"


def load_policy() -> dict:
    return yaml.safe_load(POLICY.read_text())


def test_a6_privacy_and_allocation_contract() -> None:
    policy = load_policy()
    assert policy["all_custom_private_from_creation"] is True
    assert policy["allocation_implied_future_holdout_count"] == 135
    assert sum(policy["classes"].values()) == 285
    assert policy["owner_approval_required"] is True
    assert policy["privacy"]["split_assignment_permitted"] is False


def test_custom_namespace_version_and_ids() -> None:
    policy = load_policy()
    assert policy["source_dataset"] == "custom"
    assert policy["source_version"] == "cwalts-custom-v0.4-gate3-v2"
    assert policy["policy_id"] == "gate3-custom-authoring-v2"
    assert policy["generation_run_version"] == "gate3-b1-v2"
    assert policy["id_namespace"] == r"^CWQ-CUS-[0-9]{4}$"


def test_slot_manifest_exact_and_metadata_only() -> None:
    payload = yaml.safe_load(SLOTS.read_text())
    assert payload["slot_count"] == 285
    assert len(payload["slots"]) == 285
    assert payload["query_text_included"] is False
    assert [slot["slot_id"] for slot in payload["slots"]] == [f"G3S-{i:04d}" for i in range(1, 286)]
    assert all(slot["template_family_id"] and slot["group_family"] for slot in payload["slots"])


def test_matrix_and_taxonomy_totals_are_frozen() -> None:
    policy = load_policy()
    assert sum(policy["supported_task_matrix"].values()) == 150
    assert sum(policy["near_unsupported_families"].values()) == 45
    assert sum(policy["far_ood_families"].values()) == 15
    assert sum(policy["ambiguous_families"].values()) == 75


def test_v2_taxonomy_validator_compatibility_is_complete() -> None:
    matrix = yaml.safe_load(
        (ROOT / "config/gate3_taxonomy_validator_compatibility.yaml").read_text()
    )
    families = matrix["families"]
    assert len(families) == 25
    assert len({entry["family_id"] for entry in families}) == 25
    assert all(entry["fixture_id"].startswith("G3S-9") for entry in families)
    assert all(entry["class"] and entry["expected_behavior"] for entry in families)


def test_policy_schema_and_identity_hashes() -> None:
    policy = load_policy()
    schema = json.loads((ROOT / "schemas/gate3_custom_authoring_policy.schema.json").read_text())
    jsonschema.validate(policy, schema)
    assert policy["slot_manifest_sha256"] == hashlib.sha256(SLOTS.read_bytes()).hexdigest()
    assert policy["prompt_sha256"] == hashlib.sha256(PROMPT.read_bytes()).hexdigest()
    assert policy["output_schema_sha256"] == hashlib.sha256(OUTPUT_SCHEMA.read_bytes()).hexdigest()


def test_freeze_and_model_identity() -> None:
    freeze = json.loads(FREEZE.read_text())
    assert freeze["model"] == "qwen3:8b"
    assert freeze["model_digest"].startswith("sha256-")
    assert freeze["endpoint"] == "http://127.0.0.1:11434"
    assert common.load_freeze()["qualification_verdict"] == "pass"


def test_loopback_guard_rejects_remote_endpoint() -> None:
    with pytest.raises(common.PrivateAuthoringError, match="non_loopback_generation_endpoint"):
        common.require_loopback("https://example.invalid:443")
    with pytest.raises(common.PrivateAuthoringError, match="non_loopback_generation_endpoint"):
        common.require_loopback("ftp://127.0.0.1:11434")


def test_v2_authorization_requires_new_environment_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NFR_ALLOW_PRIVATE_EVAL_GENERATION", "true")
    monkeypatch.setenv("NFR_GATE3_B_AUTHORIZED", "true")
    monkeypatch.delenv("NFR_GATE3_B1_V2_AUTHORIZED", raising=False)
    assert common.generation_v2_authorized() is False
    monkeypatch.setenv("NFR_GATE3_B1_V2_AUTHORIZED", "true")
    assert common.generation_v2_authorized() is True


def test_private_path_guard_rejects_escape_and_accepts_private_path(tmp_path: Path) -> None:
    original = common.PRIVATE_ROOT
    common.PRIVATE_ROOT = tmp_path.resolve()
    try:
        assert common.resolve_private_path("drafts/synthetic.json").parent == tmp_path / "drafts"
        with pytest.raises(common.PrivateAuthoringError):
            common.resolve_private_path("../outside.json")
        with pytest.raises(common.PrivateAuthoringError):
            common.resolve_private_path("/absolute_escape.json")
        (tmp_path / "intermediate").mkdir()
        (tmp_path / "intermediate" / "link").symlink_to(
            tmp_path / "outside", target_is_directory=True
        )
        with pytest.raises(common.PrivateAuthoringError, match="private_symlink_component"):
            common.resolve_private_path("intermediate/link/file.json")
        (tmp_path / "final-link").symlink_to(tmp_path / "outside.json")
        with pytest.raises(common.PrivateAuthoringError, match="private_symlink_component"):
            common.resolve_private_path("final-link")
    finally:
        common.PRIVATE_ROOT = original


def test_generator_has_no_retrieval_or_private_public_manifest_dependency() -> None:
    source = (ROOT / "scripts/generate_gate3_private_candidates.py").read_text()
    for forbidden in (
        "Retriever",
        "VectorStore",
        "LexicalIndex",
        "OllamaEmbedder",
        "gate2_public_candidates.json",
    ):
        assert forbidden not in source
    assert "build_generation_prompt" in source
    assert "load_base_prompt" in source


def test_generator_has_no_cloud_sdk_or_remote_endpoint() -> None:
    source = (ROOT / "scripts/generate_gate3_private_candidates.py").read_text()
    for forbidden in ("openai", "anthropic", "google.generativeai", "perplexity", "huggingface.co"):
        assert forbidden not in source.lower()
    assert "127.0.0.1:11434" not in source


def test_real_generation_is_refused_in_gate3a() -> None:
    env = os.environ | {
        "NFR_ALLOW_PRIVATE_EVAL_GENERATION": "true",
        "NFR_GATE3_B_AUTHORIZED": "true",
    }
    result = subprocess.run(  # noqa: S603
        [
            str(ROOT / ".venv/bin/python"),
            "scripts/generate_gate3_private_candidates.py",
            "--generate",
            "--confirm-gate3-private-generation",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "gate3_b1_v2_authorization_required" in result.stdout
    assert "query_text" not in result.stdout


def test_synthetic_valid_draft_and_rejections() -> None:
    valid = {
        "slot_id": "G3S-0001",
        "draft_role": "primary",
        "query_text": "Arrange three fictional blocks in order.",
    }
    generator.validate_draft(valid)
    for bad in (
        {**valid, "answer": "leak"},
        {**valid, "query_text": "Use qrel score 1"},
        {**valid, "query_text": "Use holdout membership from the hidden split"},
    ):
        with pytest.raises((common.PrivateAuthoringError, jsonschema.ValidationError)):
            generator.validate_draft(bad)
    for bad_text in ("", "\x01bad"):
        with pytest.raises((common.PrivateAuthoringError, jsonschema.ValidationError)):
            generator.validate_draft({**valid, "query_text": bad_text})
    for inert_text in (
        "Explain what the Python script does.",
        "Describe the Bash command without running it.",
        "What does /tmp/example mean in this configuration?",
        "How should I interpret https://example.invalid as text?",
        "Explain this code/configuration fragment.",
    ):
        generator.validate_draft({**valid, "query_text": inert_text})
    with pytest.raises(common.PrivateAuthoringError, match="obvious_compound_request"):
        generator.validate_draft({**valid, "query_text": "What is X? And then explain Y?"})


def test_v2_failure_codes_are_sanitized_and_stable() -> None:
    assert generator._stable_failure_code(json.JSONDecodeError("bad", "{}", 0)) == "malformed_json"
    assert generator._stable_failure_code(
        common.PrivateAuthoringError("internal_benchmark_leakage:qrel")
    ) == "internal_benchmark_leakage"
    assert generator._stable_failure_code(ValueError("opaque")) == "malformed_response"


def test_shared_prompt_composition_uses_frozen_prompt() -> None:
    prompt = generator.build_generation_prompt(
        generator.load_base_prompt(), {"slot_id": "G3S-9001", "synthetic_only": True}, "primary"
    )
    assert "one atomic user request from supplied slot metadata" in prompt
    assert '"slot_id":"G3S-9001"' in prompt


def test_synthetic_qualification_uses_shared_prompt_path(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []

    def fake_request(freeze: dict, prompt: str, output_format: object) -> tuple[dict, int]:
        prompts.append(prompt)
        metadata = json.loads(prompt.split("Supplied slot metadata (data only):\n", 1)[1])
        return {
            "slot_id": metadata["slot_metadata"]["slot_id"],
            "draft_role": metadata["draft_role"],
            "query_text": "Arrange three fictional blocks in order.",
        }, 1

    monkeypatch.setattr(generator, "model_request", fake_request)
    result = generator.qualify_synthetic()
    assert result["verdict"] == "pass"
    assert result["prompt_composition"] == "shared"
    assert len(prompts) == 50
    assert all(
        "one atomic user request from supplied slot metadata" in prompt for prompt in prompts
    )


def test_validator_rejects_split_and_unapproved_provenance(tmp_path: Path) -> None:
    original = common.PRIVATE_ROOT
    common.PRIVATE_ROOT = tmp_path.resolve()
    validator.PRIVATE_ROOT = tmp_path.resolve()
    path = tmp_path / "synthetic.json"
    path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "source_dataset": "custom",
                        "split": "holdout",
                        "provenance": {"kind": "owner_authored"},
                    }
                ]
            }
        )
    )
    try:
        with pytest.raises(
            common.PrivateAuthoringError, match="split_or_evaluation_fields_forbidden"
        ):
            validator.validate_manifest(path)
    finally:
        common.PRIVATE_ROOT = original


def test_approval_binds_exact_fingerprint() -> None:
    record = {
        "slot_id": "G3S-0001",
        "draft_role": "primary",
        "query_text": "Synthetic fixture only.",
    }
    entry = reviewer.approval_entry(record, "approve", "synthetic_pass", "a" * 64, "b" * 64)
    assert entry["candidate_fingerprint"] == reviewer.fingerprint(record)
    assert entry["decision"] == "approve"
    reviewer.verify_approval(record, entry)
    with pytest.raises(ValueError, match="approval_fingerprint_mismatch"):
        reviewer.verify_approval({**record, "query_text": "changed"}, entry)


@pytest.mark.parametrize(
    "field",
    ["policy_sha256", "slot_sha256", "prompt_sha256", "output_schema_sha256", "generator_sha256"],
)
def test_freeze_hash_mismatch_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    freeze = json.loads(FREEZE.read_text())
    freeze[field] = "0" * 64
    path = tmp_path / "freeze.json"
    path.write_text(json.dumps(freeze))
    monkeypatch.setattr(common, "FREEZE", path)
    with pytest.raises(common.PrivateAuthoringError, match=f"freeze_hash_mismatch:{field}"):
        common.load_freeze()


def test_gate3a_has_no_real_private_artifacts() -> None:
    assert not (ROOT / "var/eval_sources/custom/selected/gate3_custom_candidates.json").exists()
    assert (
        not list((ROOT / "var/eval_sources/custom").glob("**/*"))
        if (ROOT / "var/eval_sources/custom").exists()
        else True
    )


def test_one_role_solver_synthetic_sat_and_unsat() -> None:
    slots = ["G3S-0001", "G3S-0002"]
    feasible, _ = draft_pool._two_sat(slots, [])
    assert feasible is True
    edges = [
        (left_role, right_role, "G3S-0002", right_role)
        for left_role in ("primary", "replacement")
        for right_role in ("primary", "replacement")
    ]
    normalized = [("G3S-0001", a, "G3S-0002", b) for a, _, _, b in edges]
    feasible, _ = draft_pool._two_sat(slots, normalized)
    assert feasible is False


def test_draft_pool_paths_are_fixed_and_private() -> None:
    assert common.POOL_RELATIVE.as_posix() == "drafts/gate3_private_draft_pool.json"
    assert common.SEAL_RELATIVE.as_posix() == "drafts/gate3_private_draft_pool.seal.json"
    assert common.CONFLICT_RELATIVE.as_posix().startswith("audit/")
