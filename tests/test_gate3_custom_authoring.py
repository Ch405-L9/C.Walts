from __future__ import annotations

import ast
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
    assert policy["source_version"] == "cwalts-custom-v0.4-gate3-v3r1-pool2"
    assert policy["policy_id"] == "gate3-custom-authoring-v3"
    assert policy["generation_run_version"] == "gate3-b1-v3r1-pool2"
    assert policy["draft_pool_revision"] == "gate3-pool-v2-optional-replacement"
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


def test_private_pool_draft_view_preserves_structural_and_source_identity() -> None:
    record = {
        "draft_id": "G3D-G3S-9001-primary",
        "slot_id": "G3S-9001",
        "draft_role": "primary",
        "query_text": "Synthetic request.",
        "class": "supported_in_domain",
        "expected_behavior": "answer",
        "group_id": "group-synthetic",
        "template_fingerprint": "template-synthetic",
    }
    view = draft_pool._draft_view(record)

    assert view["slot_id"] == record["slot_id"]
    assert view["draft_role"] == record["draft_role"]
    assert view["source_record_id"] == record["slot_id"]
    assert draft_pool.REQUIRED_DRAFT_VIEW_FIELDS == set(view)


def test_private_pool_conflict_views_retain_slot_role_identity() -> None:
    left = draft_pool._draft_view(
        {
            "draft_id": "G3D-G3S-9001-primary",
            "slot_id": "G3S-9001",
            "draft_role": "primary",
            "query_text": "Synthetic request about the same operation.",
            "class": "supported_in_domain",
            "expected_behavior": "answer",
            "group_id": "group-left",
            "template_fingerprint": "template-left",
        }
    )
    right = draft_pool._draft_view(
        {
            "draft_id": "G3D-G3S-9002-replacement",
            "slot_id": "G3S-9002",
            "draft_role": "replacement",
            "query_text": "Synthetic request about the same operation, please.",
            "class": "supported_in_domain",
            "expected_behavior": "answer",
            "group_id": "group-right",
            "template_fingerprint": "template-right",
        }
    )

    hard, review, _ = draft_pool._near_kind(left, right)
    assert hard or review
    edge = (left["slot_id"], left["draft_role"], right["slot_id"], right["draft_role"])
    assert edge == ("G3S-9001", "primary", "G3S-9002", "replacement")


def test_private_pool_same_slot_view_identity_is_available() -> None:
    primary = draft_pool._draft_view(
        {
            "draft_id": "G3D-G3S-9001-primary",
            "slot_id": "G3S-9001",
            "draft_role": "primary",
            "query_text": "Synthetic request one.",
            "class": "supported_in_domain",
            "expected_behavior": "answer",
            "group_id": "group-synthetic",
            "template_fingerprint": "template-synthetic",
        }
    )
    replacement = dict(primary)
    replacement.update(
        {
            "id": "G3D-G3S-9001-replacement",
            "draft_role": "replacement",
            "query_text": "Synthetic request two.",
        }
    )
    assert primary["slot_id"] == replacement["slot_id"]
    assert primary["draft_role"] != replacement["draft_role"]


def test_private_pool_draft_view_consumers_use_declared_fields() -> None:
    source = (ROOT / "scripts/verify_gate3_private_draft_pool.py").read_text()
    tree = ast.parse(source)
    verifier = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "validate_pool"
    )
    keys: set[str] = set()
    for node in ast.walk(verifier):
        if not isinstance(node, ast.Subscript) or not isinstance(node.value, ast.Name):
            continue
        if node.value.id not in {"left", "right", "draft", "public"}:
            continue
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            keys.add(node.slice.value)
    assert keys <= draft_pool.REQUIRED_DRAFT_VIEW_FIELDS
    assert {"id", "slot_id", "draft_role", "query_text", "template_fingerprint", "group_id"} <= keys


def test_private_pool_same_family_relation_uses_view_identity() -> None:
    left = draft_pool._draft_view(
        {
            "draft_id": "G3D-G3S-9001-primary",
            "slot_id": "G3S-9001",
            "draft_role": "primary",
            "query_text": "Synthetic request about the same operation.",
            "class": "supported_in_domain",
            "expected_behavior": "answer",
            "group_id": "group-same",
            "template_fingerprint": "template-same",
        }
    )
    right = draft_pool._draft_view(
        {
            "draft_id": "G3D-G3S-9002-replacement",
            "slot_id": "G3S-9002",
            "draft_role": "replacement",
            "query_text": "Synthetic request about the same operation, please.",
            "class": "supported_in_domain",
            "expected_behavior": "answer",
            "group_id": "group-same",
            "template_fingerprint": "template-other",
        }
    )
    hard, review, metrics = draft_pool._near_kind(left, right)
    assert review and not hard
    relation = {"left": left["id"], "right": right["id"], "metrics": metrics}
    assert relation["left"] == "G3D-G3S-9001-primary"
    assert relation["right"] == "G3D-G3S-9002-replacement"


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


def test_pool2_authorization_requires_new_environment_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NFR_ALLOW_PRIVATE_EVAL_GENERATION", "true")
    monkeypatch.setenv("NFR_GATE3_B_AUTHORIZED", "true")
    monkeypatch.setenv("NFR_GATE3_B1_V3R1_AUTHORIZED", "true")
    monkeypatch.delenv("NFR_GATE3_B1_V3R1_POOL2_AUTHORIZED", raising=False)
    assert common.generation_v3r1_pool2_authorized() is False
    monkeypatch.setenv("NFR_GATE3_B1_V3R1_POOL2_AUTHORIZED", "true")
    assert common.generation_v3r1_pool2_authorized() is True


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
    assert "gate3_b1_v3r1_pool2_authorization_required" in result.stdout
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


def test_v3_failure_codes_are_sanitized_and_stable() -> None:
    assert generator._stable_failure_code(json.JSONDecodeError("bad", "{}", 0)) == "malformed_json"
    assert (
        generator._stable_failure_code(
            common.PrivateAuthoringError("internal_benchmark_leakage:qrel")
        )
        == "internal_benchmark_leakage"
    )
    assert generator._stable_failure_code(ValueError("opaque")) == "malformed_response"


def test_shared_prompt_composition_uses_frozen_prompt() -> None:
    prompt = generator.build_generation_prompt(
        generator.load_base_prompt(), {"slot_id": "G3S-9001", "synthetic_only": True}, "primary"
    )
    assert "one natural user request from supplied metadata" in prompt
    assert '"slot_id":"G3S-9001"' in prompt
    for forbidden in ("qrel", "holdout", "calibration", "threshold", "chunk ID", "source ID"):
        assert forbidden.lower() not in generator.load_base_prompt().lower()


def test_synthetic_qualification_uses_shared_prompt_path(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []

    def fake_request(
        freeze: dict, prompt: str, output_format: object, request_seed: int
    ) -> tuple[dict, int]:
        prompts.append(prompt)
        metadata = json.loads(prompt.split("Supplied slot metadata (data only):\n", 1)[1])
        return {
            "slot_id": metadata["slot_metadata"]["slot_id"],
            "draft_role": metadata["draft_role"],
            "query_text": f"Arrange three fictional blocks in {metadata['draft_role']} order.",
        }, 1

    monkeypatch.setattr(generator, "model_request", fake_request)
    result = generator.qualify_synthetic()
    assert result["verdict"] == "pass"
    assert result["prompt_composition"] == "shared"
    assert len(prompts) == 570
    assert all("one natural user request from supplied metadata" in prompt for prompt in prompts)


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


def test_r3_has_no_real_private_artifacts() -> None:
    assert not (ROOT / "var/eval_sources/custom/selected/gate3_custom_candidates.json").exists()
    assert not (ROOT / "var/eval_sources/custom/drafts/gate3_private_draft_pool.json").exists()
    assert not (ROOT / "var/eval_sources/custom/drafts/gate3_private_draft_pool.seal.json").exists()


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


def _synthetic_draft_record() -> tuple[dict, dict, dict, str]:
    policy = load_policy()
    slots = yaml.safe_load(SLOTS.read_text())["slots"]
    slot = slots[0]
    freeze = common.load_freeze()
    freeze_sha = common.file_sha256(FREEZE)
    record = generator._draft_metadata(
        slot,
        "primary",
        "Explain this Python configuration fragment without executing it.",
        freeze_sha,
        common.file_sha256(POLICY),
        freeze["model"],
        freeze["model_digest"],
        freeze["model_tag_digest"],
    )
    return record, slot, policy, freeze_sha


def test_provenance_fields_are_separate_and_rebindable() -> None:
    record, slot, policy, freeze_sha = _synthetic_draft_record()
    assert record["generation_model"] == "qwen3:8b"
    assert record["generation_model_digest"] == common.load_freeze()["model_digest"]
    assert record["generation_model_tag_digest"] == common.load_freeze()["model_tag_digest"]
    assert record["generation_freeze_sha256"] == freeze_sha
    draft_pool.validate_record_integrity(record, slot, policy, common.load_freeze(), freeze_sha)


def test_generator_and_verifier_draft_metadata_contract_matches() -> None:
    source = ast.parse((ROOT / "scripts/generate_gate3_private_candidates.py").read_text())
    metadata_function = next(
        node
        for node in ast.walk(source)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_draft_metadata"
    )
    returns = [node for node in ast.walk(metadata_function) if isinstance(node, ast.Return)]
    assert len(returns) == 1
    returned = returns[0].value
    assert isinstance(returned, ast.Dict)
    emitted_fields = {
        key.value
        for key in returned.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    assert emitted_fields == set(draft_pool.ALLOWED_DRAFT_RECORD_FIELDS)
    assert "generation_model_tag_digest" in emitted_fields


def test_verifier_rejects_unknown_draft_metadata_field() -> None:
    record, slot, policy, freeze_sha = _synthetic_draft_record()
    record["unexpected_metadata"] = "tampered"
    with pytest.raises(common.PrivateAuthoringError, match="unexpected_draft_metadata"):
        draft_pool.validate_record_field_set(record)


def test_model_tag_digest_tampering_fails_closed() -> None:
    record, slot, policy, freeze_sha = _synthetic_draft_record()
    record["generation_model_tag_digest"] = "tampered"
    with pytest.raises(common.PrivateAuthoringError, match="draft_model_tag_digest_mismatch"):
        draft_pool.validate_record_integrity(record, slot, policy, common.load_freeze(), freeze_sha)


def test_group_id_matches_frozen_pipe_algorithm_and_pair_relationship() -> None:
    record, slot, policy, _ = _synthetic_draft_record()
    expected_input = "|".join(
        [
            policy["policy_id"],
            slot["group_family"],
            slot["template_family_id"],
            slot["structural_family"],
            slot["task_family"],
        ]
    )
    expected = "G3G-" + hashlib.sha256(expected_input.encode()).hexdigest()[:24]
    assert record["group_id"] == expected == common.derive_group_id(slot, policy)
    replacement = generator._draft_metadata(
        slot,
        "replacement",
        "Use this Python fragment as inert text.",
        common.file_sha256(FREEZE),
        common.file_sha256(POLICY),
        common.load_freeze()["model"],
        common.load_freeze()["model_digest"],
        common.load_freeze()["model_tag_digest"],
    )
    assert replacement["group_id"] == record["group_id"]
    assert replacement["template_fingerprint"] == record["template_fingerprint"]


@pytest.mark.parametrize(
    ("field", "error"),
    [
        ("group_id", "draft_group_id_mismatch"),
        ("template_fingerprint", "draft_template_fingerprint_mismatch"),
        ("draft_fingerprint", "draft_fingerprint_mismatch"),
        ("class", "slot_metadata_mismatch:class"),
        ("expected_behavior", "slot_metadata_mismatch:expected_behavior"),
        ("task_family", "slot_metadata_mismatch:task_family"),
        ("scenario_family", "slot_metadata_mismatch:scenario_family"),
        ("structural_family", "slot_metadata_mismatch:structural_family"),
        ("register", "slot_metadata_mismatch:register"),
        ("preservation_burden", "slot_metadata_mismatch:preservation_burden"),
        ("template_family_id", "slot_metadata_mismatch:template_family_id"),
        ("generation_model", "draft_model_mismatch"),
        ("generation_model_digest", "draft_model_digest_mismatch"),
        ("generation_freeze_sha256", "draft_freeze_identity_mismatch"),
    ],
)
def test_draft_integrity_tampering_fails_closed(field: str, error: str) -> None:
    record, slot, policy, freeze_sha = _synthetic_draft_record()
    record[field] = "tampered"
    with pytest.raises(common.PrivateAuthoringError, match=error):
        draft_pool.validate_record_integrity(record, slot, policy, common.load_freeze(), freeze_sha)


def test_query_text_tampering_invalidates_fingerprint() -> None:
    record, slot, policy, freeze_sha = _synthetic_draft_record()
    record["query_text"] = "Changed inert text."
    with pytest.raises(common.PrivateAuthoringError, match="draft_fingerprint_mismatch"):
        draft_pool.validate_record_integrity(record, slot, policy, common.load_freeze(), freeze_sha)


def test_gate2_manifest_sha_guard_precedes_json_access(tmp_path: Path) -> None:
    path = tmp_path / "public.json"
    path.write_text('{"records": [{"query_text": "synthetic only"}]}')
    with pytest.raises(common.PrivateAuthoringError, match="gate2_manifest_sha256_mismatch"):
        common.verify_gate2_manifest_identity(path)


def test_v3_generation_seal_contract_is_present_in_writer() -> None:
    source = (ROOT / "scripts/generate_gate3_private_candidates.py").read_text()
    for field in (
        "generation_model",
        "generation_run_version",
        "generation_activation_commit",
        "activated_generator_sha256",
        "activated_generation_freeze_sha256",
    ):
        assert f'"{field}"' in source


def test_v3_seed_algorithm_known_vector_and_diversity() -> None:
    first = common.derive_request_seed("gate3-custom-authoring-v3", "G3S-0001", "primary", 1, 17)
    assert first == 515879888
    assert first == common.derive_request_seed(
        "gate3-custom-authoring-v3", "G3S-0001", "primary", 1, 17
    )
    assert first != common.derive_request_seed(
        "gate3-custom-authoring-v3", "G3S-0001", "primary", 2, 17
    )
    assert first != common.derive_request_seed(
        "gate3-custom-authoring-v3", "G3S-0001", "replacement", 1, 17
    )
    assert common.derive_request_seed("x", "y", "z", 1, 0) != 0


def test_v3_request_options_are_local_and_base_options_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {
                    "response": json.dumps(
                        {
                            "slot_id": "G3S-9001",
                            "draft_role": "primary",
                            "query_text": "Synthetic.",
                        }
                    )
                }
            ).encode()

    def fake_urlopen(request, timeout):
        captured.append(json.loads(request.data.decode())["options"])
        return Response()

    monkeypatch.setattr(generator.urllib.request, "urlopen", fake_urlopen)
    freeze = common.load_freeze()
    original = dict(freeze["parameters"])
    generator.model_request(freeze, "synthetic", "json", 123)
    assert captured[0]["seed"] == 123
    assert freeze["parameters"] == original


def test_v3_failure_context_uses_explicit_state() -> None:
    source = (ROOT / "scripts/generate_gate3_private_candidates.py").read_text()
    assert 'locals().get("slot"' not in source
    assert '"terminal_seed": current_seed' in source


def test_v2_abort_evidence_is_sanitized() -> None:
    evidence = json.loads((ROOT / "docs/evidence/gate3-b1-v2-aborted-generation.json").read_text())
    assert evidence["terminal_slot"] is None
    assert evidence["terminal_slot_disposition"] == "unavailable_due_v2_observability_defect"
    assert evidence["accepted_draft_count"] == 0
    assert evidence["query_text_recorded"] is False


def test_shadow_shape_is_noncanonical() -> None:
    shadow_ids = [f"G3S-{9000 + i:04d}" for i in range(1, 286)]
    assert len(shadow_ids) == len(set(shadow_ids)) == 285
    assert not any(item in {f"G3S-{i:04d}" for i in range(1, 286)} for item in shadow_ids)


def _synthetic_runner_inputs() -> tuple[dict, dict]:
    policy = load_policy()
    slot = yaml.safe_load(SLOTS.read_text())["slots"][0].copy()
    slot["slot_id"] = "G3S-9001"
    return common.load_freeze(), {"policy": policy, "slot": slot}


def test_retry_classifier_has_explicit_retry_contract() -> None:
    for error in (
        common.PrivateAuthoringError("internal_benchmark_leakage"),
        common.PrivateAuthoringError("obvious_compound_request"),
        common.PrivateAuthoringError("format_safety_failure:replacement_exact_duplicate"),
        json.JSONDecodeError("bad", "{}", 0),
        jsonschema.ValidationError("bad"),
        OSError("loopback"),
    ):
        _, retryable = generator.classify_generation_error(error)
        assert retryable is True
    for error in (
        common.PrivateAuthoringError("generation_endpoint_mismatch"),
        common.PrivateAuthoringError("private_path_escape"),
    ):
        _, retryable = generator.classify_generation_error(error)
        assert retryable is False


def test_shared_attempt_runner_succeeds_on_third_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    freeze, values = _synthetic_runner_inputs()
    policy, slot = values["policy"], values["slot"]
    seeds: list[int] = []

    def fake_request(freeze_arg, prompt, output_format, request_seed):
        seeds.append(request_seed)
        if len(seeds) == 1:
            return {
                "slot_id": slot["slot_id"],
                "draft_role": "primary",
                "query_text": "Use qrel.",
            }, 1
        if len(seeds) == 2:
            raise json.JSONDecodeError("bad", "{}", 0)
        return {
            "slot_id": slot["slot_id"],
            "draft_role": "primary",
            "query_text": "Describe one fictional operation.",
        }, 1

    monkeypatch.setattr(generator, "model_request", fake_request)
    result = generator.generate_one_slot_role(freeze, policy, slot, "primary")
    assert result.attempts_used == 3
    assert result.retries_used == 2
    assert len(set(seeds)) == 3
    assert result.intermediate_error_codes == ("internal_benchmark_leakage", "malformed_json")


def test_shared_attempt_runner_stops_after_three_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    freeze, values = _synthetic_runner_inputs()
    policy, slot = values["policy"], values["slot"]
    calls: list[int] = []

    def fake_request(freeze_arg, prompt, output_format, request_seed):
        calls.append(request_seed)
        return {"slot_id": slot["slot_id"], "draft_role": "primary", "query_text": "Use qrel."}, 1

    monkeypatch.setattr(generator, "model_request", fake_request)
    with pytest.raises(generator.GenerationTerminalError) as caught:
        generator.generate_one_slot_role(freeze, policy, slot, "primary")
    error = caught.value
    assert len(calls) == 3
    assert error.slot_id == "G3S-9001"
    assert error.role == "primary"
    assert error.attempt == 3
    assert error.seed == calls[-1]
    assert error.stable_code == "internal_benchmark_leakage"


def _pair_response(prompt: str, query_text: str) -> dict:
    metadata = json.loads(prompt.split("Supplied slot metadata (data only):\n", 1)[1])
    return {
        "slot_id": metadata["slot_metadata"]["slot_id"],
        "draft_role": metadata["draft_role"],
        "query_text": query_text,
    }


def test_pair_immediate_distinct_has_no_pair_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    freeze, values = _synthetic_runner_inputs()
    calls: list[int] = []

    def fake_request(freeze_arg, prompt, output_format, request_seed):
        calls.append(request_seed)
        role = json.loads(prompt.split("Supplied slot metadata (data only):\n", 1)[1])["draft_role"]
        return _pair_response(prompt, f"Synthetic {role} request."), 1

    monkeypatch.setattr(generator, "model_request", fake_request)
    result = generator.generate_slot_pair(freeze, values["policy"], values["slot"])
    assert result.retries_used == 0
    assert result.pair_duplicate_retries == 0
    assert result.primary.attempts_used == 1
    assert result.replacement.attempts_used == 1
    assert len(calls) == 2


def test_pair_duplicate_then_distinct_retries_replacement_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    freeze, values = _synthetic_runner_inputs()
    calls: list[tuple[str, int]] = []

    def fake_request(freeze_arg, prompt, output_format, request_seed):
        metadata = json.loads(prompt.split("Supplied slot metadata (data only):\n", 1)[1])
        role = metadata["draft_role"]
        calls.append((role, request_seed))
        if role == "primary":
            return _pair_response(prompt, "Same synthetic request."), 1
        if len([role for role, _ in calls if role == "replacement"]) == 1:
            return _pair_response(prompt, "Same synthetic request."), 1
        return _pair_response(prompt, "Different synthetic request."), 1

    monkeypatch.setattr(generator, "model_request", fake_request)
    result = generator.generate_slot_pair(freeze, values["policy"], values["slot"])
    replacement_seeds = [seed for role, seed in calls if role == "replacement"]
    assert result.retries_used == 1
    assert result.pair_duplicate_retries == 1
    assert len(replacement_seeds) == 2
    assert replacement_seeds[0] != replacement_seeds[1]
    assert len([role for role, _ in calls if role == "primary"]) == 1


def test_pair_two_duplicates_then_distinct_succeeds_on_third_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    freeze, values = _synthetic_runner_inputs()
    replacement_calls = 0

    def fake_request(freeze_arg, prompt, output_format, request_seed):
        nonlocal replacement_calls
        role = json.loads(prompt.split("Supplied slot metadata (data only):\n", 1)[1])["draft_role"]
        if role == "primary":
            return _pair_response(prompt, "Same synthetic request."), 1
        replacement_calls += 1
        text = (
            "Same synthetic request." if replacement_calls < 3 else "Different synthetic request."
        )
        return _pair_response(prompt, text), 1

    monkeypatch.setattr(generator, "model_request", fake_request)
    result = generator.generate_slot_pair(freeze, values["policy"], values["slot"])
    assert result.replacement.attempts_used == 3
    assert result.retries_used == 2
    assert result.pair_duplicate_retries == 2


def test_pair_three_duplicates_terminal_without_fourth_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    freeze, values = _synthetic_runner_inputs()
    calls: list[tuple[str, int]] = []

    def fake_request(freeze_arg, prompt, output_format, request_seed):
        metadata = json.loads(prompt.split("Supplied slot metadata (data only):\n", 1)[1])
        calls.append((metadata["draft_role"], request_seed))
        return _pair_response(prompt, "Same synthetic request."), 1

    monkeypatch.setattr(generator, "model_request", fake_request)
    result = generator.generate_slot_pair(freeze, values["policy"], values["slot"])
    assert len(calls) == 4
    assert result.replacement is None
    assert result.replacement_omission == {
        "slot_id": "G3S-9001",
        "role": "replacement",
        "terminal_attempt": 3,
        "terminal_seed": calls[-1][1],
        "stable_error_code": "format_safety_failure",
        "detail_code": "replacement_exact_duplicate",
        "attempt_history": [
            {
                "attempt": attempt,
                "seed": seed,
                "stable_error_code": "format_safety_failure",
                "detail_code": "replacement_exact_duplicate",
            }
            for attempt, seed in zip((1, 2, 3), [
                common.derive_request_seed(
                    values["policy"]["policy_id"],
                    values["slot"]["slot_id"],
                    "replacement",
                    attempt,
                    values["policy"]["seed_strategy"]["base_seed"],
                )
                for attempt in (1, 2, 3)
            ], strict=True)
        ],
    }


@pytest.mark.parametrize(
    "failure_texts",
    [
        ["Use qrel.", "Same synthetic request.", "Same synthetic request."],
        [None, "Same synthetic request.", "Same synthetic request."],
        ["Same synthetic request.", "Use qrel.", "Same synthetic request."],
        ["Same synthetic request.", "Same synthetic request.", None],
    ],
)
def test_mixed_replacement_histories_fail_closed(
    monkeypatch: pytest.MonkeyPatch, failure_texts: list[str | None]
) -> None:
    freeze, values = _synthetic_runner_inputs()
    replacement_calls = 0

    def fake_request(freeze_arg, prompt, output_format, request_seed):
        nonlocal replacement_calls
        metadata = json.loads(prompt.split("Supplied slot metadata (data only):\n", 1)[1])
        if metadata["draft_role"] == "primary":
            return _pair_response(prompt, "Same synthetic request."), 1
        text = failure_texts[replacement_calls]
        replacement_calls += 1
        if text is None:
            return {"slot_id": metadata["slot_metadata"]["slot_id"], "draft_role": "replacement"}, 1
        return _pair_response(prompt, text), 1

    monkeypatch.setattr(generator, "model_request", fake_request)
    with pytest.raises(generator.GenerationTerminalError) as caught:
        generator.generate_slot_pair(freeze, values["policy"], values["slot"])
    error = caught.value
    assert error.role == "replacement"
    assert error.attempt == 3
    assert len(error.attempt_history) == 3
    assert any(
        row["stable_error_code"] != "format_safety_failure"
        or row["detail_code"] != "replacement_exact_duplicate"
        for row in error.attempt_history
    )


def test_pair_replacement_prompt_excludes_primary_text(monkeypatch: pytest.MonkeyPatch) -> None:
    freeze, values = _synthetic_runner_inputs()
    prompts: list[str] = []

    def fake_request(freeze_arg, prompt, output_format, request_seed):
        prompts.append(prompt)
        role = json.loads(prompt.split("Supplied slot metadata (data only):\n", 1)[1])["draft_role"]
        return _pair_response(prompt, f"Synthetic {role} request."), 1

    monkeypatch.setattr(generator, "model_request", fake_request)
    generator.generate_slot_pair(freeze, values["policy"], values["slot"])
    assert len(prompts) == 2
    assert "Synthetic primary request." not in prompts[1]


def test_non_retryable_generation_precondition_stops_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    freeze, values = _synthetic_runner_inputs()
    calls: list[int] = []

    def fake_request(freeze_arg, prompt, output_format, request_seed):
        calls.append(request_seed)
        raise common.PrivateAuthoringError("generation_endpoint_mismatch")

    monkeypatch.setattr(generator, "model_request", fake_request)
    with pytest.raises(common.PrivateAuthoringError, match="generation_endpoint_mismatch"):
        generator.generate_one_slot_role(freeze, values["policy"], values["slot"], "primary")
    assert len(calls) == 1


def test_shadow_and_canonical_use_same_attempt_runner() -> None:
    source = (ROOT / "scripts/generate_gate3_private_candidates.py").read_text()
    assert source.count("generate_one_slot_role(") >= 3
    assert "def classify_generation_error" in source
    assert "locals().get" not in source
