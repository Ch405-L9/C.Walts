"""Guarded, local-only Supplemental-20 generator.

The generation entry point is frozen during PRE-R1 but is never invoked here.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path
from typing import Any

import jsonschema
import yaml

try:
    from scripts import verify_gate3_s20_supplemental_repair as validator
    from scripts.gate3_private_common import (
        ROOT,
        atomic_write_bytes,
        current_git_head,
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
        current_git_head,
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
PROMPT = ROOT / "config/gate3_s20_supplement_prompt.txt"
SCHEMA = ROOT / "config/gate3_s20_supplement_schema.json"
SLOTS = ROOT / "config/gate3_custom_authoring_slots.yaml"
SURFACE_ASSIGNMENT = ROOT / "config/gate3_s20_surface_assignment.json"
SURFACE_PROFILES = ROOT / "config/gate3_surface_variation_profiles.yaml"
POOL_RELATIVE = "supplements/gate3_s20_supplement_pool.json"
SEAL_RELATIVE = "supplements/gate3_s20_supplement_pool.seal.json"
AUDIT_RELATIVE = "audit/gate3_s20_generation_audit.json"
FAILURE_RELATIVE = "audit/gate3_s20_generation_failure.json"


def derive_supplement_seed(
    policy_id: str, slot_id: str, attempt_number: int, base_seed: int = 17
) -> int:
    return derive_request_seed(policy_id, slot_id, "supplemental", attempt_number, base_seed)


def authorization_status() -> dict[str, bool]:
    return {
        name: os.environ.get(name) == "true"
        for name in (*REQUIRED_COMMON_ENV, AUTHORIZATION_ENV)
    }


def _load() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    policy = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    slots = yaml.safe_load(SLOTS.read_text(encoding="utf-8"))
    if freeze["supplement_generator_sha256"] != file_sha256(Path(__file__)):
        raise RuntimeError("supplement_freeze_generator_hash_mismatch")
    if freeze["supplement_validator_sha256"] != file_sha256(Path(validator.__file__)):
        raise RuntimeError("supplement_freeze_validator_hash_mismatch")
    if freeze["supplement_policy_sha256"] != file_sha256(POLICY):
        raise RuntimeError("supplement_freeze_policy_hash_mismatch")
    if freeze["supplement_instruction_sha256"] != file_sha256(PROMPT):
        raise RuntimeError("supplement_freeze_prompt_hash_mismatch")
    if freeze["supplement_schema_sha256"] != file_sha256(SCHEMA):
        raise RuntimeError("supplement_freeze_schema_hash_mismatch")
    if freeze["surface_profile_sha256"] != file_sha256(SURFACE_PROFILES):
        raise RuntimeError("supplement_freeze_surface_hash_mismatch")
    if freeze["target_slot_ids_sha256"] != json.loads(TARGETS.read_text())["repair_set_sha256"]:
        raise RuntimeError("supplement_freeze_target_hash_mismatch")
    return freeze, policy, slots


TARGETS = ROOT / "config/gate3_s20_target_slots.json"


def _profile_for(slot_id: str) -> dict[str, Any]:
    profiles = yaml.safe_load(SURFACE_PROFILES.read_text(encoding="utf-8"))["profiles"]
    assignment = json.loads(SURFACE_ASSIGNMENT.read_text(encoding="utf-8"))
    return profiles[validator.target_surface_profiles()[slot_id]] | {
        "profile_id": validator.target_surface_profiles()[slot_id],
        "assignment_id": assignment["assignment_id"],
    }


def _prompt(slot: dict[str, Any], profile: dict[str, Any]) -> str:
    metadata = json.dumps(slot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (
        PROMPT.read_text(encoding="utf-8").rstrip()
        + "\n\nSurface realization profile (instruction):\n"
        + profile["instruction"]
        + "\n\nSupplied slot metadata (data only):\n"
        + metadata
        + "\n"
    )


def _model_request(freeze: dict[str, Any], prompt: str, seed: int) -> dict[str, Any]:
    payload = {
        "model": freeze["model"],
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "think": False,
        "options": {"temperature": 0.25, "top_p": 0.95, "num_predict": 96, "seed": seed},
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
            slot["slot_id"], "supplemental", query_text,
            freeze["supplement_policy_sha256"], file_sha256(FREEZE)
        ),
    }


def _failure(exc: BaseException, slot_id: str, attempt: int, seed: int, accepted: int) -> None:
    path = resolve_private_path(FAILURE_RELATIVE)
    payload = {
        "schema_version": 1,
        "run_version": "gate3-b1-v3r1-s20",
        "head": current_git_head(),
        "slot_id": slot_id,
        "attempt": attempt,
        "seed": seed,
        "stable_error_code": type(exc).__name__,
        "detail_code": str(exc).split(":", 1)[1] if ":" in str(exc) else None,
        "accepted_supplement_count": accepted,
        "query_text_recorded": False,
        "raw_response_recorded": False,
    }
    atomic_write_bytes(path, (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode())


def generate() -> dict[str, Any]:
    status = authorization_status()
    if not all(status.values()):
        raise RuntimeError("supplemental_authorization_missing")
    freeze, policy, slots_payload = _load()
    require_loopback(freeze["endpoint"])
    verify_model_identity({
        "endpoint": freeze["endpoint"],
        "model": freeze["model"],
        "model_digest": freeze["model_blob_digest"],
        "model_tag_digest": freeze["model_tag_digest"],
    })
    target_ids = json.loads(TARGETS.read_text(encoding="utf-8"))["slot_ids"]
    by_id = {slot["slot_id"]: slot for slot in slots_payload["slots"]}
    accepted: list[dict[str, Any]] = []
    attempts = 0
    retries = 0
    for slot_id in target_ids:
        slot = by_id[slot_id]
        last_error: BaseException | None = None
        for attempt in range(1, 4):
            seed = derive_supplement_seed(policy["supplement_policy_id"], slot_id, attempt)
            attempts += 1
            try:
                value = _model_request(freeze, _prompt(slot, _profile_for(slot_id)), seed)
                jsonschema.validate(value, json.loads(SCHEMA.read_text(encoding="utf-8")))
                if value["slot_id"] != slot_id or value["draft_role"] != "supplemental":
                    raise ValueError("supplement_identity_mismatch")
                validate_draft(
                    {"slot_id": slot_id, "draft_role": "primary", "query_text": value["query_text"]}
                )
                record = _record(slot, value, freeze)
                validator.validate_supplements(accepted + [record], require_complete=False)
                accepted.append(record)
                break
            except BaseException as exc:
                last_error = exc
                retries += int(attempt > 1)
                if attempt == 3:
                    _failure(exc, slot_id, attempt, seed, len(accepted))
                    raise
        if last_error is not None and len(accepted) < target_ids.index(slot_id) + 1:
            raise last_error
    payload = {
        "schema_version": 1,
        "supplement_pool_id": "gate3-private-supplements-v3r1-s20-v0.4",
        "records": accepted,
    }
    pool_path = resolve_private_path(POOL_RELATIVE)
    seal_path = resolve_private_path(SEAL_RELATIVE)
    audit_path = resolve_private_path(AUDIT_RELATIVE)
    encoded = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    atomic_write_bytes(pool_path, encoded)
    audit = {
        "schema_version": 1,
        "run_version": freeze["run_version"],
        "target_count": 20,
        "accepted_count": len(accepted),
        "attempts": attempts,
        "retries": retries,
        "query_text_recorded": False,
        "performance_peek": False,
        "verdict": "pass",
    }
    audit_bytes = (json.dumps(audit, sort_keys=True, indent=2) + "\n").encode()
    atomic_write_bytes(audit_path, audit_bytes)
    seal = {
        "schema_version": 1,
        "supplement_pool_id": payload["supplement_pool_id"],
        "supplement_pool_sha256": file_sha256(pool_path),
        "supplement_audit_sha256": file_sha256(audit_path),
        "target_slot_ids_sha256": freeze["target_slot_ids_sha256"],
        "source_pool_sha256": freeze["source_pool_sha256"],
        "supplement_policy_sha256": freeze["supplement_policy_sha256"],
        "supplement_generator_sha256": freeze["supplement_generator_sha256"],
        "supplement_validator_sha256": freeze["supplement_validator_sha256"],
        "generation_activation_commit": current_git_head(),
        "owner_approvals": 0,
        "performance_peek": False,
        "canonical_manifest": False,
    }
    atomic_write_bytes(seal_path, (json.dumps(seal, sort_keys=True, indent=2) + "\n").encode())
    return {
        "verdict": "pass",
        "accepted_count": len(accepted),
        "attempts": attempts,
        "retries": retries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--confirm-gate3-s20-generation", action="store_true")
    args = parser.parse_args()
    if args.generate and not args.confirm_gate3_s20_generation:
        raise SystemExit("supplemental_generation_confirmation_required")
    if args.generate:
        print(json.dumps(generate(), sort_keys=True))
    else:
        print(
            json.dumps(
                {"authorization": authorization_status(), "generation": False}, sort_keys=True
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
