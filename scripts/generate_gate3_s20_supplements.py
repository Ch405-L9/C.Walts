"""Guarded, local-only canonical Supplemental-20 generator."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema
import yaml

try:
    from scripts import verify_gate3_s20_supplemental_repair as validator
    from scripts.gate3_private_common import (
        ROOT,
        atomic_write_bytes,
        derive_draft_fingerprint,
        derive_group_id,
        derive_request_seed,
        derive_template_fingerprint,
        file_sha256,
        require_loopback,
        resolve_private_path,
        verify_model_identity,
    )
    from scripts.generate_gate3_private_candidates import validate_draft
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import verify_gate3_s20_supplemental_repair as validator
    from gate3_private_common import (
        ROOT,
        atomic_write_bytes,
        derive_draft_fingerprint,
        derive_group_id,
        derive_request_seed,
        derive_template_fingerprint,
        file_sha256,
        require_loopback,
        resolve_private_path,
        verify_model_identity,
    )
    from generate_gate3_private_candidates import validate_draft


AUTHORIZATION_ENV = "NFR_GATE3_B1_S20_AUTHORIZED"
REQUIRED_COMMON_ENV = ("NFR_ALLOW_PRIVATE_EVAL_GENERATION", "NFR_GATE3_B_AUTHORIZED")
FREEZE = ROOT / "config/gate3_s20_generation_freeze.json"
POLICY = ROOT / "config/gate3_s20_supplement_policy.yaml"
BASE_POLICY = ROOT / "config/gate3_custom_authoring_policy.yaml"
BASE_PROMPT = ROOT / "config/gate3_custom_generation_prompt.txt"
PROMPT = ROOT / "config/gate3_s20_supplement_prompt.txt"
SCHEMA = ROOT / "config/gate3_s20_supplement_schema.json"
SLOTS = ROOT / "config/gate3_custom_authoring_slots.yaml"
SURFACE_ASSIGNMENT = ROOT / "config/gate3_s20_surface_assignment.json"
SURFACE_PROFILES = ROOT / "config/gate3_surface_variation_profiles.yaml"
TARGETS = ROOT / "config/gate3_s20_target_slots.json"
RETRY_FEEDBACK = ROOT / "config/gate3_s20_retry_feedback.json"
POOL_RELATIVE = "supplements/gate3_s20_supplement_pool.json"
SEAL_RELATIVE = "supplements/gate3_s20_supplement_pool.seal.json"
AUDIT_RELATIVE = "audit/gate3_s20_generation_audit.json"


def derive_supplement_seed(
    policy_id: str, slot_id: str, attempt_number: int, base_seed: int = 17
) -> int:
    return derive_request_seed(policy_id, slot_id, "supplemental", attempt_number, base_seed)


def authorization_status() -> dict[str, bool]:
    return {
        name: os.environ.get(name) == "true" for name in (*REQUIRED_COMMON_ENV, AUTHORIZATION_ENV)
    }


def _parameter_contract(freeze: dict[str, Any]) -> dict[str, Any]:
    return {
        "format_mode": freeze["format_mode"],
        "format_schema_sha256": freeze["format_schema_sha256"],
        "stream": freeze["stream"],
        "think": freeze["think"],
        "temperature": freeze["temperature"],
        "top_p": freeze["top_p"],
        "num_predict": freeze["num_predict"],
    }


def _parameter_hash(freeze: dict[str, Any]) -> str:
    encoded = json.dumps(
        _parameter_contract(freeze), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_schema(freeze: dict[str, Any]) -> dict[str, Any]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if freeze.get("format_schema_sha256") != file_sha256(SCHEMA):
        raise RuntimeError("freeze_identity_mismatch:format_schema")
    if freeze.get("parameter_hash") != _parameter_hash(freeze):
        raise RuntimeError("freeze_identity_mismatch:parameter_hash")
    return schema


def _load_retry_feedback(freeze: dict[str, Any]) -> dict[str, Any]:
    contract = json.loads(RETRY_FEEDBACK.read_text(encoding="utf-8"))
    if freeze.get("retry_feedback_contract_id") != contract.get("contract_id"):
        raise RuntimeError("freeze_identity_mismatch:retry_feedback_contract")
    if freeze.get("retry_feedback_sha256") != file_sha256(RETRY_FEEDBACK):
        raise RuntimeError("freeze_identity_mismatch:retry_feedback")
    return contract


def _load() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    policy = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    slots = yaml.safe_load(SLOTS.read_text(encoding="utf-8"))
    checks = {
        "base_policy_sha256": BASE_POLICY,
        "base_slot_sha256": SLOTS,
        "supplement_generator_sha256": Path(__file__),
        "supplement_validator_sha256": Path(validator.__file__),
        "supplement_policy_sha256": POLICY,
        "supplement_instruction_sha256": PROMPT,
        "retry_feedback_sha256": RETRY_FEEDBACK,
        "supplement_schema_sha256": SCHEMA,
        "surface_profile_sha256": SURFACE_PROFILES,
        "supplement_surface_assignment_sha256": SURFACE_ASSIGNMENT,
        "base_prompt_sha256": BASE_PROMPT,
    }
    for key, path in checks.items():
        if freeze.get(key) != file_sha256(path):
            raise RuntimeError(f"freeze_identity_mismatch:{key}")
    target = json.loads(TARGETS.read_text(encoding="utf-8"))
    if freeze.get("target_slot_ids_sha256") != target["repair_set_sha256"]:
        raise RuntimeError("freeze_identity_mismatch:target_slots")
    return freeze, policy, slots


def _install_staged_artifacts(
    staged: Path, destinations: tuple[Path, Path, Path]
) -> None:
    installed: list[Path] = []
    try:
        for destination in destinations:
            source = staged / destination.name
            if destination.exists():
                raise RuntimeError("supplement_artifact_preexists")
            source.replace(destination)
            installed.append(destination)
    except BaseException:
        for destination in installed:
            destination.unlink(missing_ok=True)
        raise


def _profile_for(slot_id: str) -> dict[str, Any]:
    profiles = yaml.safe_load(SURFACE_PROFILES.read_text(encoding="utf-8"))["profiles"]
    assignment = json.loads(SURFACE_ASSIGNMENT.read_text(encoding="utf-8"))
    profile_id = validator.target_surface_profiles()[slot_id]
    return profiles[profile_id] | {
        "profile_id": profile_id,
        "assignment_id": assignment["assignment_id"],
    }


def _prompt(
    slot: dict[str, Any], profile: dict[str, Any], retry_feedback: str | None = None
) -> str:
    metadata = json.dumps(slot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    prompt = (
        BASE_PROMPT.read_text(encoding="utf-8").rstrip()
        + "\n\nSupplemental-20 instruction layer:\n"
        + PROMPT.read_text(encoding="utf-8").rstrip()
        + "\n\nSurface realization profile (instruction):\n"
        + profile["instruction"]
        + "\n\nSupplied slot metadata (data only):\n"
        + metadata
        + "\n"
    )
    if retry_feedback:
        prompt += "\nSupplemental retry correction:\n" + retry_feedback + "\n"
    return prompt


def _model_request(
    freeze: dict[str, Any], prompt: str, seed: int, schema: dict[str, Any]
) -> dict[str, Any]:
    payload = {
        "model": freeze["model"],
        "prompt": prompt,
        "format": schema,
        "stream": freeze["stream"],
        "think": freeze["think"],
        "options": {
            "temperature": freeze["temperature"],
            "top_p": freeze["top_p"],
            "num_predict": freeze["num_predict"],
            "seed": seed,
        },
    }
    request = urllib.request.Request(  # noqa: S310
        freeze["endpoint"] + "/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        response_payload = json.loads(response.read())
    return json.loads(response_payload["response"])


def _record(slot: dict[str, Any], value: dict[str, Any], freeze: dict[str, Any]) -> dict[str, Any]:
    policy = yaml.safe_load(BASE_POLICY.read_text(encoding="utf-8"))
    query_text = value["query_text"]
    return {
        "supplement_id": f"G3S20-{slot['slot_id']}-supplemental",
        "slot_id": slot["slot_id"],
        "draft_role": "supplemental",
        "query_text": query_text,
        "class": slot["class"],
        "expected_behavior": slot["expected_behavior"],
        "task_family": slot["task_family"],
        "scenario_family": slot["scenario_family"],
        "structural_family": slot["structural_family"],
        "register": slot.get("register"),
        "preservation_burden": slot.get("preservation_burden"),
        "group_family": slot["group_family"],
        "group_id": derive_group_id(slot, policy),
        "template_family_id": slot["template_family_id"],
        "template_fingerprint": derive_template_fingerprint(
            slot, policy, freeze["base_prompt_sha256"]
        ),
        "generation_model": freeze["model"],
        "generation_model_digest": freeze["model_blob_digest"],
        "generation_model_tag_digest": freeze["model_tag_digest"],
        "supplement_policy_sha256": freeze["supplement_policy_sha256"],
        "supplement_freeze_sha256": file_sha256(FREEZE),
        "supplement_prompt_sha256": freeze["supplement_instruction_sha256"],
        "supplement_fingerprint": derive_draft_fingerprint(
            slot["slot_id"],
            "supplemental",
            query_text,
            freeze["supplement_policy_sha256"],
            file_sha256(FREEZE),
        ),
    }


def _stable_failure(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, jsonschema.ValidationError):
        details = {
            "required": "schema_required",
            "additionalProperties": "schema_additional_properties",
            "const": "schema_const",
            "pattern": "schema_pattern",
            "type": "schema_type",
            "minLength": "schema_min_length",
        }
        return "format_safety_failure", details.get(exc.validator, "schema_failure")
    if isinstance(exc, json.JSONDecodeError):
        return "format_safety_failure", "malformed_json"
    if isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError)):
        return "transport_failure", "local_model_transport"
    marker = str(exc).split(":", 1)[0]
    mapping = {
        "supplemental_exact_duplicate_gate2": ("format_safety_failure", "exact_duplicate_gate2"),
        "supplemental_gate2_exact_duplicate": ("format_safety_failure", "exact_duplicate_gate2"),
        "supplemental_exact_duplicate_same_target": (
            "format_safety_failure",
            "exact_duplicate_same_target",
        ),
        "supplemental_exact_duplicate_prior_supplement": (
            "format_safety_failure",
            "exact_duplicate_prior_supplement",
        ),
        "supplemental_pair_conflict": ("format_safety_failure", "supplement_pair_conflict"),
        "supplemental_gate2_structural_conflict": (
            "format_safety_failure",
            "supplement_gate2_conflict",
        ),
        "supplemental_structural_unsat": ("format_safety_failure", "supplemental_structural_unsat"),
        "supplement_identity_invalid": ("format_safety_failure", "identity_mismatch"),
        "supplement_same_target_conflict": ("format_safety_failure", "exact_duplicate_same_target"),
        "runtime_worktree_not_clean": ("preflight_failure", "worktree_not_clean"),
        "runtime_head_mismatch": ("preflight_failure", "head_mismatch"),
        "runtime_expected_head_invalid": ("preflight_failure", "expected_head_invalid"),
        "git_unavailable": ("preflight_failure", "git_unavailable"),
        "supplement_artifact_preexists": ("preflight_failure", "artifact_preexists"),
        "supplemental_authorization_missing": ("preflight_failure", "authorization_missing"),
        "freeze_identity_mismatch": ("preflight_failure", "freeze_identity_mismatch"),
        "prior_failure_audit_mismatch": ("preflight_failure", "prior_failure_audit_mismatch"),
    }
    return mapping.get(marker, ("internal_error", "unclassified"))


def _parse_porcelain_z(raw: bytes) -> list[tuple[str, str]]:
    """Decode only ordinary NUL-delimited porcelain records losslessly."""
    records: list[tuple[str, str]] = []
    for field in raw.split(b"\0"):
        if not field:
            continue
        if len(field) < 3 or field[2:3] != b" ":
            raise RuntimeError("runtime_worktree_not_clean")
        status = field[:2].decode("ascii", errors="strict")
        path = field[3:].decode("utf-8", errors="surrogateescape")
        if "R" in status or "C" in status:
            raise RuntimeError("runtime_worktree_not_clean")
        records.append((status, path))
    return records


def _allowed_worktree_records(records: list[tuple[str, str]]) -> bool:
    approved = {
        ("??", "C.Walts Stage 2.2B-1C Noncompliance Correction.md"),
        ("??", "C.Walts Stage 2.2B-1C Noncompliance Correction.pdf"),
    }
    return not records or len(records) == 2 and set(records) == approved


def _runtime_state(expected_head: str) -> None:
    if len(expected_head) != 40 or any(char not in "0123456789abcdef" for char in expected_head):
        raise RuntimeError("runtime_expected_head_invalid")
    git = shutil.which("git")
    if not git:
        raise RuntimeError("git_unavailable")
    for command in ([git, "rev-parse", "HEAD"], [git, "rev-parse", "@{upstream}"]):
        result = subprocess.run(  # noqa: S603
            command, cwd=ROOT, capture_output=True, text=True, check=False
        )
        if result.returncode != 0 or result.stdout.strip() != expected_head:
            raise RuntimeError("runtime_head_mismatch")
    result = subprocess.run(  # noqa: S603, S607
        [git, "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        text=False,
        check=False,
    )
    if result.returncode != 0 or not _allowed_worktree_records(_parse_porcelain_z(result.stdout)):
        raise RuntimeError("runtime_worktree_not_clean")


def _safe_audit_relative(relative: str) -> bool:
    path = PurePosixPath(relative)
    return (
        bool(relative)
        and not path.is_absolute()
        and ".." not in path.parts
        and path.parts[:1] == ("audit",)
        and path.suffix == ".json"
    )


def _verify_event2_contract(
    freeze: dict[str, Any], *, verify_history_identity: bool = True
) -> None:
    expected = {
        "generation_event_ordinal": 2,
        "run_version": "gate3-b1-v3r1-s20-event2",
        "source_version": "cwalts-custom-v0.4-gate3-v3r1-s20-event2",
        "prior_failed_activation_commit": "558988d34985d4b0c24103d6a331e939caba701c",
        "prior_failure_audit_relative": "audit/gate3_s20_generation_failure.json",
        "prior_failure_audit_sha256": (
            "b2bce6ed92f21fa7d73baab6540d104883082b44c986ea186226f8a33248e390"
        ),
        "event2_failure_audit_relative": "audit/gate3_s20_generation_failure_event2.json",
    }
    contract_items = expected.items()
    if not verify_history_identity:
        contract_items = (
            (key, value)
            for key, value in contract_items
            if key not in {"prior_failure_audit_relative", "prior_failure_audit_sha256"}
        )
    if any(freeze.get(key) != value for key, value in contract_items):
        raise RuntimeError("freeze_identity_mismatch:event_contract")
    for key in ("prior_failure_audit_relative", "event2_failure_audit_relative"):
        if not _safe_audit_relative(freeze[key]):
            raise RuntimeError("freeze_identity_mismatch:audit_path")


def _verify_event3_contract(freeze: dict[str, Any]) -> None:
    expected = {
        "generation_event_ordinal": 3,
        "run_version": "gate3-b1-v3r1-s20-event3",
        "source_version": "cwalts-custom-v0.4-gate3-v3r1-s20-event3",
        "event1_failed_activation_commit": "558988d34985d4b0c24103d6a331e939caba701c",
        "event1_failure_audit_relative": "audit/gate3_s20_generation_failure.json",
        "event1_failure_audit_sha256": (
            "b2bce6ed92f21fa7d73baab6540d104883082b44c986ea186226f8a33248e390"
        ),
        "event2_failed_activation_commit": "1c9030b0c6a12489f1879a45ba2bd2cf0923334f",
        "event2_failure_audit_relative": "audit/gate3_s20_generation_failure_event2.json",
        "event2_failure_audit_sha256": (
            "5449448fcc0e033f9ed64db0187ed1f4bdb81133378f73ad59dc7af953064cda"
        ),
        "event3_failure_audit_relative": "audit/gate3_s20_generation_failure_event3.json",
    }
    if any(freeze.get(key) != value for key, value in expected.items()):
        raise RuntimeError("freeze_identity_mismatch:event_contract")
    if not _safe_audit_relative(freeze["event3_failure_audit_relative"]):
        raise RuntimeError("freeze_identity_mismatch:audit_path")


def _guard_event2_state(freeze: dict[str, Any]) -> None:
    _verify_event2_contract(freeze, verify_history_identity=False)
    historical = resolve_private_path(freeze["prior_failure_audit_relative"])
    if not historical.exists() or file_sha256(historical) != freeze["prior_failure_audit_sha256"]:
        raise RuntimeError("prior_failure_audit_mismatch")
    for relative in (
        POOL_RELATIVE,
        SEAL_RELATIVE,
        AUDIT_RELATIVE,
        freeze["event2_failure_audit_relative"],
    ):
        if resolve_private_path(relative).exists():
            raise RuntimeError("supplement_artifact_preexists")


def _guard_event3_state(freeze: dict[str, Any]) -> None:
    for relative, digest in (
        (freeze["event1_failure_audit_relative"], freeze["event1_failure_audit_sha256"]),
        (freeze["event2_failure_audit_relative"], freeze["event2_failure_audit_sha256"]),
    ):
        historical = resolve_private_path(relative)
        if not historical.exists() or file_sha256(historical) != digest:
            raise RuntimeError("prior_failure_audit_mismatch")
    for relative in (
        POOL_RELATIVE,
        SEAL_RELATIVE,
        AUDIT_RELATIVE,
        freeze["event3_failure_audit_relative"],
    ):
        if resolve_private_path(relative).exists():
            raise RuntimeError("supplement_artifact_preexists")


def _write_failure(
    slot_id: str,
    attempt: int,
    seed: int,
    accepted: int,
    history: list[dict[str, Any]],
    expected_head: str,
    error: tuple[str, str],
    freeze: dict[str, Any],
    total_attempts: int,
    total_retries: int,
) -> None:
    payload = {
        "schema_version": 2,
        "run_version": freeze["run_version"],
        "generation_activation_commit": expected_head,
        "slot_id": slot_id,
        "terminal_attempt": attempt,
        "terminal_seed": seed,
        "stable_error_code": error[0],
        "detail_code": error[1],
        "accepted_supplement_count": accepted,
        "total_attempts": total_attempts,
        "total_retries": total_retries,
        "attempt_history": history,
        "query_text_recorded": False,
        "raw_response_recorded": False,
    }
    path = resolve_private_path(freeze["event3_failure_audit_relative"])
    atomic_write_bytes(path, (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode())


def generate(expected_head: str) -> dict[str, Any]:
    status = authorization_status()
    if not all(status.values()):
        raise RuntimeError("supplemental_authorization_missing")
    _runtime_state(expected_head)
    freeze, policy, slots_payload = _load()
    schema = _load_schema(freeze)
    retry_feedback = _load_retry_feedback(freeze)
    _verify_event3_contract(freeze)
    _guard_event3_state(freeze)
    require_loopback(freeze["endpoint"])
    verify_model_identity(
        {
            "endpoint": freeze["endpoint"],
            "model": freeze["model"],
            "model_digest": freeze["model_blob_digest"],
            "model_tag_digest": freeze["model_tag_digest"],
        }
    )
    target_ids = json.loads(TARGETS.read_text(encoding="utf-8"))["slot_ids"]
    by_id = {slot["slot_id"]: slot for slot in slots_payload["slots"]}
    accepted: list[dict[str, Any]] = []
    attempts = 0
    retries = 0
    for slot_id in target_ids:
        slot = by_id[slot_id]
        history: list[dict[str, Any]] = []
        for attempt in range(1, 4):
            seed = derive_supplement_seed(policy["supplement_policy_id"], slot_id, attempt)
            attempts += 1
            retries += int(attempt > 1)
            try:
                feedback = None
                if history and history[-1]["detail_code"] == "exact_duplicate_same_target":
                    feedback = retry_feedback["feedback"]["exact_duplicate_same_target"].get(
                        str(attempt)
                    )
                value = _model_request(
                    freeze, _prompt(slot, _profile_for(slot_id), feedback), seed, schema
                )
                jsonschema.validate(value, schema)
                if value["slot_id"] != slot_id or value["draft_role"] != "supplemental":
                    raise ValueError("supplement_identity_invalid")
                validate_draft(
                    {"slot_id": slot_id, "draft_role": "primary", "query_text": value["query_text"]}
                )
                record = _record(slot, value, freeze)
                validator.validate_supplements(accepted + [record], require_complete=False)
                accepted.append(record)
                break
            except BaseException as exc:
                error = _stable_failure(exc)
                history.append(
                    {
                        "attempt": attempt,
                        "seed": seed,
                        "stable_error_code": error[0],
                        "detail_code": error[1],
                    }
                )
                if attempt == 3:
                    targets_touched = len(accepted) + 1
                    if retries != attempts - targets_touched:
                        raise RuntimeError("failure_accounting_invariant") from None
                    _write_failure(
                        slot_id,
                        attempt,
                        seed,
                        len(accepted),
                        history,
                        expected_head,
                        error,
                        freeze,
                        attempts,
                        retries,
                    )
                    raise RuntimeError("supplement_generation_failed") from None
    if len(accepted) != 20:
        raise RuntimeError("supplement_cardinality_incomplete")
    final_result = validator.validate_supplements(accepted, require_complete=True)
    if not final_result["one_role_per_slot_feasible"]:
        raise RuntimeError("supplemental_structural_unsat")
    payload = {
        "schema_version": 1,
        "supplement_pool_id": "gate3-private-supplements-v3r1-s20-v0.4",
        "records": accepted,
    }
    encoded = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    audit = {
        "schema_version": 1,
        "run_version": freeze["run_version"],
        "generation_activation_commit": expected_head,
        "target_count": 20,
        "accepted_count": 20,
        "generation_event_ordinal": freeze["generation_event_ordinal"],
        "source_version": freeze["source_version"],
        "attempts": attempts,
        "retries": retries,
        "query_text_recorded": False,
        "performance_peek": False,
        "verdict": "pass",
    }
    audit_bytes = (json.dumps(audit, sort_keys=True, indent=2) + "\n").encode()
    seal = {
        "schema_version": 1,
        "supplement_pool_id": payload["supplement_pool_id"],
        "supplement_pool_sha256": hashlib.sha256(encoded).hexdigest(),
        "supplement_audit_sha256": hashlib.sha256(audit_bytes).hexdigest(),
        "target_frontier_id": freeze["repair_frontier_id"],
        "target_slot_ids_sha256": freeze["target_slot_ids_sha256"],
        "source_pool_sha256": freeze["source_pool_sha256"],
        "base_exact_edge_count": freeze["base_exact_edge_count"],
        "base_hard_review_edge_count": freeze["base_hard_review_edge_count"],
        "base_augmented_edge_count": freeze["base_augmented_edge_count"],
        "base_augmented_edge_sha256": freeze["base_augmented_edge_sha256"],
        "supplement_policy_sha256": freeze["supplement_policy_sha256"],
        "base_prompt_sha256": freeze["base_prompt_sha256"],
        "supplement_instruction_sha256": freeze["supplement_instruction_sha256"],
        "surface_profile_sha256": freeze["surface_profile_sha256"],
        "supplement_surface_assignment_sha256": freeze["supplement_surface_assignment_sha256"],
        "supplement_schema_sha256": freeze["supplement_schema_sha256"],
        "retry_feedback_contract_id": freeze["retry_feedback_contract_id"],
        "retry_feedback_sha256": freeze["retry_feedback_sha256"],
        "parameter_hash": freeze["parameter_hash"],
        "model": freeze["model"],
        "model_tag_digest": freeze["model_tag_digest"],
        "model_blob_digest": freeze["model_blob_digest"],
        "seed_strategy": freeze["seed_strategy"],
        "base_seed": freeze["base_seed"],
        "max_attempts": freeze["max_attempts"],
        "supplement_generator_sha256": freeze["supplement_generator_sha256"],
        "supplement_validator_sha256": freeze["supplement_validator_sha256"],
        "supplement_freeze_sha256": file_sha256(FREEZE),
        "run_version": freeze["run_version"],
        "source_version": freeze["source_version"],
        "generation_activation_commit": expected_head,
        "owner_approvals": 0,
        "performance_peek": False,
        "canonical_manifest": False,
    }
    seal_bytes = (json.dumps(seal, sort_keys=True, indent=2) + "\n").encode()
    pool_path, seal_path, audit_path = map(
        resolve_private_path, (POOL_RELATIVE, SEAL_RELATIVE, AUDIT_RELATIVE)
    )
    staging_root = resolve_private_path("staging")
    staging_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".gate3-s20-stage-", dir=staging_root))
    try:
        (staging / pool_path.name).write_bytes(encoded)
        (staging / audit_path.name).write_bytes(audit_bytes)
        (staging / seal_path.name).write_bytes(seal_bytes)
        _install_staged_artifacts(staging, (pool_path, audit_path, seal_path))
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return {"verdict": "pass", "accepted_count": 20, "attempts": attempts, "retries": retries}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--confirm-gate3-s20-generation", action="store_true")
    parser.add_argument("--expected-head")
    args = parser.parse_args()
    if args.generate and not args.confirm_gate3_s20_generation:
        raise SystemExit("supplemental_generation_confirmation_required")
    if args.generate and not args.expected_head:
        raise SystemExit("expected_head_required")
    if args.generate:
        try:
            print(json.dumps(generate(args.expected_head), sort_keys=True))
        except Exception as exc:
            stable, detail = _stable_failure(exc)
            print(
                json.dumps(
                    {"verdict": "fail", "stable_error_code": stable, "detail_code": detail},
                    sort_keys=True,
                )
            )
            return 1
    else:
        print(
            json.dumps(
                {"authorization": authorization_status(), "generation": False}, sort_keys=True
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
