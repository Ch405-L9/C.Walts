"""Gate 3 local-only generator controls; canonical generation is Gate 3-B."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from datetime import UTC, datetime
from typing import Any

import jsonschema
import yaml

try:
    from scripts.gate3_private_common import (
        AUDIT_RELATIVE,
        DRAFT_SCHEMA,
        FAILURE_AUDIT_RELATIVE,
        POLICY,
        POOL_RELATIVE,
        ROOT,
        SEAL_RELATIVE,
        SLOTS,
        PrivateAuthoringError,
        atomic_write_bytes,
        canonical_sha256,
        current_git_head,
        derive_draft_fingerprint,
        derive_group_id,
        derive_request_seed,
        derive_template_fingerprint,
        file_sha256,
        generation_authorized,
        generation_v3_authorized,
        load_freeze,
        require_loopback,
        resolve_private_path,
        verify_model_identity,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from gate3_private_common import (
        AUDIT_RELATIVE,
        DRAFT_SCHEMA,
        FAILURE_AUDIT_RELATIVE,
        POLICY,
        POOL_RELATIVE,
        ROOT,
        SEAL_RELATIVE,
        SLOTS,
        PrivateAuthoringError,
        atomic_write_bytes,
        canonical_sha256,
        current_git_head,
        derive_draft_fingerprint,
        derive_group_id,
        derive_request_seed,
        derive_template_fingerprint,
        file_sha256,
        generation_authorized,
        generation_v3_authorized,
        load_freeze,
        require_loopback,
        resolve_private_path,
        verify_model_identity,
    )


def build_generation_prompt(
    base_prompt: str, slot_metadata: dict[str, Any], draft_role: str
) -> str:
    """Compose the sole prompt path shared by qualification and Gate 3-B."""
    metadata = json.dumps(
        {"draft_role": draft_role, "slot_metadata": slot_metadata},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"{base_prompt.rstrip()}\n\nSupplied slot metadata (data only):\n{metadata}\n"


def load_base_prompt() -> str:
    return (ROOT / "config/gate3_custom_generation_prompt.txt").read_text(encoding="utf-8")


def model_request(
    freeze: dict[str, Any], prompt: str, output_format: Any, request_seed: int
) -> tuple[dict[str, Any], int]:
    options = dict(freeze["parameters"])
    options["seed"] = request_seed
    payload = {
        "model": freeze["model"],
        "prompt": prompt,
        "format": output_format,
        "stream": False,
        "think": False,
        "options": options,
    }
    request = urllib.request.Request(  # noqa: S310
        freeze["endpoint"] + "/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        response_payload = json.loads(response.read())
    return json.loads(response_payload.get("response", "")), 1


def load_metadata() -> tuple[dict[str, Any], dict[str, Any]]:
    policy = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    slots = yaml.safe_load(SLOTS.read_text(encoding="utf-8"))
    if slots.get("slot_count") != 285 or len(slots.get("slots", [])) != 285:
        raise PrivateAuthoringError("slot_count_mismatch")
    return policy, slots


def verify_freeze() -> dict[str, Any]:
    freeze = load_freeze()
    policy, slots = load_metadata()
    if policy.get("model", {}).get("name") != freeze.get("model"):
        raise PrivateAuthoringError("model_freeze_mismatch")
    if len(slots["slots"]) != 285:
        raise PrivateAuthoringError("slot_manifest_invalid")
    return {
        "verdict": "pass",
        "canonical_generation_executed": False,
        "real_draft_count": 0,
        "slot_count": 285,
    }


def synthetic_payload() -> dict[str, Any]:
    return {"slot_id": "G3S-0001", "draft_role": "primary", "query_text": "synthetic fixture only"}


def validate_draft(value: Any) -> None:
    schema = json.loads(DRAFT_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(value, schema)
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value["query_text"]):
        raise PrivateAuthoringError("control_character_in_query_text")
    text = value["query_text"]
    if re.search(
        r"\bqrel\b|\b(?:hidden\s+)?holdout\s+(?:membership|designation|split)\b",
        text,
        re.I,
    ):
        raise PrivateAuthoringError("internal_benchmark_leakage:qrel_or_holdout")
    if re.search(
        r"\bcalibration\s+(?:state|membership|split)\b|"
        r"\bthreshold\s+(?:metadata|fitting|value)\b",
        text,
        re.I,
    ):
        raise PrivateAuthoringError("internal_benchmark_leakage:calibration_or_threshold")
    if re.search(r"\b(?:chunk|source)[_ -]?id\s*[:=]", text, re.I):
        raise PrivateAuthoringError("internal_benchmark_leakage:answer_key_identifier")
    if re.search(r"\?[^?]{0,240}\b(and then|also|additionally|;|\?)\b", value["query_text"], re.I):
        raise PrivateAuthoringError("obvious_compound_request")


def _stable_failure_code(error: BaseException) -> str:
    if isinstance(error, PrivateAuthoringError):
        return str(error).split(":", 1)[0]
    if isinstance(error, jsonschema.ValidationError):
        return "schema_violation"
    if isinstance(error, json.JSONDecodeError):
        return "malformed_json"
    if isinstance(error, OSError):
        return "loopback_transport_failure"
    if isinstance(error, (ValueError, TypeError)):
        return "malformed_response"
    return type(error).__name__


def qualify_synthetic() -> dict[str, Any]:
    """Qualify the exact v3 stack on all 285 slot shapes x two roles."""
    freeze = load_freeze()
    require_loopback(freeze["endpoint"])
    slots = yaml.safe_load(SLOTS.read_text(encoding="utf-8"))["slots"]
    schema = json.loads(DRAFT_SCHEMA.read_text(encoding="utf-8"))
    metrics = {
        "cases_attempted": len(slots) * 2,
        "transport_success": 0,
        "json_parse_pass": 0,
        "schema_pass": 0,
        "atomicity_pass": 0,
        "internal_leakage_failures": 0,
        "extra_field_failures": 0,
        "inert_text_safety_failures": 0,
        "retry_count": 0,
        "successful_cases": 0,
    }
    failures: list[dict[str, str]] = []
    intermediate_errors: dict[str, int] = {}
    for index, slot in enumerate(slots, start=1):
        for role in ("primary", "replacement"):
            shadow_slot = dict(slot)
            shadow_slot["slot_id"] = f"G3S-{9000 + index:04d}"
            metadata = {
                **shadow_slot,
                "synthetic_only": True,
            }
            prompt = build_generation_prompt(load_base_prompt(), metadata, role)
            passed = False
            for attempt in range(1, 4):
                request_seed = derive_request_seed(
                    yaml.safe_load(POLICY.read_text(encoding="utf-8"))["policy_id"],
                    metadata["slot_id"], role, attempt
                )
                try:
                    value, _ = model_request(freeze, prompt, "json", request_seed)
                    metrics["transport_success"] += 1
                    metrics["json_parse_pass"] += 1
                    jsonschema.validate(value, schema)
                    metrics["schema_pass"] += 1
                    if value["slot_id"] != metadata["slot_id"] or value["draft_role"] != role:
                        raise PrivateAuthoringError("synthetic_slot_role_mismatch")
                    validate_draft(value)
                    metrics["atomicity_pass"] += 1
                    metrics["successful_cases"] += 1
                    passed = True
                    break
                except jsonschema.ValidationError as exc:
                    instance = getattr(exc, "instance", None)
                    if isinstance(instance, dict) and set(instance) - {
                        "slot_id", "draft_role", "query_text"
                    }:
                        metrics["extra_field_failures"] += 1
                except PrivateAuthoringError as exc:
                    if str(exc).startswith("internal_benchmark_leakage"):
                        metrics["internal_leakage_failures"] += 1
                    elif str(exc) == "synthetic_slot_role_mismatch":
                        metrics["inert_text_safety_failures"] += 1
                except (OSError, ValueError, TypeError):
                    pass
                if attempt == 1:
                    metrics["retry_count"] += 1
            if not passed:
                code = "qualification_failure"
                intermediate_errors[code] = intermediate_errors.get(code, 0) + 1
                failures.append({"fixture_id": metadata["slot_id"], "draft_role": role})
    if failures or metrics["successful_cases"] != metrics["cases_attempted"]:
        raise PrivateAuthoringError("synthetic_qualification_threshold_failed")
    return {
        "verdict": "pass",
        "synthetic_slot_count": len(slots),
        "synthetic_primary_count": len(slots),
        "synthetic_replacement_count": len(slots),
        "synthetic_cases_per_configuration": metrics["cases_attempted"],
        "configuration": freeze["parameters"],
        "metrics": metrics,
        "failures": failures,
        "intermediate_error_counts": intermediate_errors,
        "total_attempts": metrics["cases_attempted"] + metrics["retry_count"],
        "raw_output_printed": False,
        "canonical_generation_executed": False,
        "prompt_composition": "shared",
        "format_mode": "json",
    }


def dry_run_metadata() -> dict[str, Any]:
    policy, slots = load_metadata()
    return {
        "verdict": "pass",
        "slot_count": len(slots["slots"]),
        "class_totals": policy["classes"],
        "canonical_generation_executed": False,
        "real_draft_count": 0,
    }


def _slot_identity(
    slot: dict[str, Any], role: str, query_text: str, freeze_sha: str, policy_sha: str
) -> str:
    return derive_draft_fingerprint(slot["slot_id"], role, query_text, policy_sha, freeze_sha)


def _draft_metadata(
    slot: dict[str, Any],
    role: str,
    query_text: str,
    freeze_sha: str,
    policy_sha: str,
    model: str,
    model_digest: str,
    model_tag_digest: str | None = None,
) -> dict[str, Any]:
    policy = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    prompt_sha = file_sha256(ROOT / "config/gate3_custom_generation_prompt.txt")
    template = derive_template_fingerprint(slot, policy, prompt_sha)
    group = derive_group_id(slot, policy)
    return {
        "draft_id": f"G3D-{slot['slot_id']}-{role}",
        "slot_id": slot["slot_id"],
        "draft_role": role,
        "query_text": query_text,
        "class": slot["class"],
        "expected_behavior": slot["expected_behavior"],
        "task_family": slot["task_family"],
        "scenario_family": slot["scenario_family"],
        "structural_family": slot["structural_family"],
        "register": slot.get("register"),
        "preservation_burden": slot.get("preservation_burden"),
        "group_family": slot["group_family"],
        "group_id": group,
        "template_family_id": slot["template_family_id"],
        "template_fingerprint": template,
        "generation_model": model,
        "generation_model_digest": model_digest,
        "generation_model_tag_digest": model_tag_digest,
        "policy_sha256": policy_sha,
        "generation_freeze_sha256": freeze_sha,
        "prompt_sha256": prompt_sha,
        "draft_fingerprint": _slot_identity(slot, role, query_text, freeze_sha, policy_sha),
    }


def generate_draft_pool() -> dict[str, Any]:
    try:
        from scripts.verify_eval_split import canonical_text
    except ModuleNotFoundError:  # pragma: no cover - direct script execution
        from verify_eval_split import canonical_text

    freeze = load_freeze()
    if not generation_authorized():
        raise PrivateAuthoringError("private_generation_authorization_required")
    if not generation_v3_authorized():
        raise PrivateAuthoringError("gate3_b1_v3_authorization_required")
    model_identity = verify_model_identity(freeze)
    pool_path = resolve_private_path(POOL_RELATIVE)
    seal_path = resolve_private_path(SEAL_RELATIVE)
    audit_path = resolve_private_path(AUDIT_RELATIVE)
    if pool_path.exists():
        raise PrivateAuthoringError("draft_pool_overwrite_refused")
    policy, slots_payload = load_metadata()
    slots = sorted(slots_payload["slots"], key=lambda item: item["slot_id"])
    freeze_sha = file_sha256(ROOT / "config/gate3_generation_freeze.json")
    policy_sha = file_sha256(POLICY)
    records: list[dict[str, Any]] = []
    attempts = 0
    retries = 0
    started = datetime.now(UTC).isoformat()
    current_slot_id: str | None = None
    current_role: str | None = None
    current_attempt: int | None = None
    current_seed: int | None = None
    try:
        for slot in slots:
            for role in ("primary", "replacement"):
                current_slot_id = slot["slot_id"]
                current_role = role
                prompt = build_generation_prompt(load_base_prompt(), slot, role)
                accepted = None
                last_error_code = None
                for attempt in range(1, 4):
                    current_attempt = attempt
                    current_seed = derive_request_seed(
                        policy["policy_id"], slot["slot_id"], role, attempt,
                        policy["seed_strategy"]["base_seed"],
                    )
                    attempts += 1
                    try:
                        value, _ = model_request(freeze, prompt, "json", current_seed)
                        validate_draft(value)
                        if value["slot_id"] != slot["slot_id"] or value["draft_role"] != role:
                            raise PrivateAuthoringError("returned_slot_role_mismatch")
                        accepted = _draft_metadata(
                            slot,
                            role,
                            value["query_text"],
                            freeze_sha,
                            policy_sha,
                            freeze["model"],
                            freeze["model_digest"],
                            freeze.get("model_tag_digest"),
                        )
                        break
                    except (OSError, ValueError, TypeError, jsonschema.ValidationError) as exc:
                        last_error_code = _stable_failure_code(exc)
                        if attempt == 1:
                            retries += 1
                        if attempt == 3:
                            raise PrivateAuthoringError(
                                f"draft_generation_failed:{last_error_code}"
                            ) from exc
                if accepted is None:
                    raise PrivateAuthoringError("draft_not_accepted")
                records.append(accepted)
        by_slot = {slot["slot_id"]: [] for slot in slots}
        for record in records:
            by_slot[record["slot_id"]].append(record)
        duplicate_slots = [
            slot_id
            for slot_id, pair in by_slot.items()
            if len(pair) != 2
            or canonical_text(pair[0]["query_text"]) == canonical_text(pair[1]["query_text"])
        ]
        if duplicate_slots:
            raise PrivateAuthoringError(
                f"primary_replacement_exact_duplicate:{len(duplicate_slots)}"
            )
        payload = {
            "schema_version": 1,
            "draft_pool_id": "gate3-private-drafts-570-v0.4",
            "records": records,
        }
        encoded = (
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode()
        atomic_write_bytes(pool_path, encoded)
        pool_sha = file_sha256(pool_path)
        seal = {
            "schema_version": 1,
            "draft_pool_id": payload["draft_pool_id"],
            "draft_pool_sha256": pool_sha,
            "draft_count": len(records),
            "primary_count": sum(record["draft_role"] == "primary" for record in records),
            "replacement_count": sum(record["draft_role"] == "replacement" for record in records),
            "policy_sha256": policy_sha,
            "slot_sha256": file_sha256(SLOTS),
            "prompt_sha256": file_sha256(ROOT / "config/gate3_custom_generation_prompt.txt"),
            "schema_sha256": file_sha256(DRAFT_SCHEMA),
            "parameter_hash": freeze["parameter_hash"],
            "model_digest": freeze["model_digest"],
            "model_blob_digest": freeze["model_blob_digest"],
            "model_tag_digest": freeze["model_tag_digest"],
            "generation_run_version": freeze["generation_run_version"],
            "generation_model": freeze["model"],
            "generation_activation_commit": current_git_head(),
            "activated_generator_sha256": file_sha256(
                ROOT / "scripts/generate_gate3_private_candidates.py"
            ),
            "activated_generation_freeze_sha256": freeze_sha,
            "generation_timestamp": datetime.now(UTC).isoformat(),
            "split": False,
            "qrels": False,
            "canonical_candidate_manifest": False,
        }
        atomic_write_bytes(seal_path, (json.dumps(seal, sort_keys=True, indent=2) + "\n").encode())
        audit = {
            "schema_version": 1,
            "draft_pool_id": payload["draft_pool_id"],
            "started_at": started,
            "completed_at": datetime.now(UTC).isoformat(),
            "requested_slot_roles": 570,
            "successful_drafts": len(records),
            "attempts": attempts,
            "retries": retries,
            "policy_sha256": policy_sha,
            "slot_sha256": file_sha256(SLOTS),
            "prompt_sha256": file_sha256(ROOT / "config/gate3_custom_generation_prompt.txt"),
            "parameter_hash": freeze["parameter_hash"],
            "model": model_identity,
            "generation_run_version": freeze["generation_run_version"],
            "generation_activation_commit": current_git_head(),
            "sequential": True,
            "performance_peek": False,
            "gate2_seed_access": False,
            "verdict": "pass",
        }
        atomic_write_bytes(
            audit_path, (json.dumps(audit, sort_keys=True, indent=2) + "\n").encode()
        )
        return {
            "verdict": "pass",
            "draft_count": len(records),
            "primary_count": 285,
            "replacement_count": 285,
            "pool_sha256": pool_sha,
            "query_text_printed": False,
        }
    except BaseException as exc:
        failure_path = resolve_private_path(FAILURE_AUDIT_RELATIVE)
        failure = {
            "schema_version": 1,
            "run_version": "gate3-b1-v3",
            "run_id": canonical_sha256({"started_at": started, "policy_sha256": policy_sha}),
            "head": current_git_head(),
            "generator_sha256": file_sha256(ROOT / "scripts/generate_gate3_private_candidates.py"),
            "generation_freeze_sha256": freeze_sha,
            "policy_sha256": policy_sha,
            "terminal_slot": current_slot_id,
            "terminal_role": current_role,
            "attempt": current_attempt,
            "terminal_seed": current_seed,
            "model_tag_digest": freeze.get("model_tag_digest"),
            "model_blob_digest": freeze.get("model_blob_digest", freeze.get("model_digest")),
            "timestamp": datetime.now(UTC).isoformat(),
            "error_category": type(exc).__name__,
            "error_code": locals().get("last_error_code") or _stable_failure_code(exc),
            "raw_response_recorded": False,
            "query_text_recorded": False,
        }
        if not failure_path.exists():
            atomic_write_bytes(
                failure_path, (json.dumps(failure, sort_keys=True, indent=2) + "\n").encode()
            )
        pool_path.unlink(missing_ok=True)
        seal_path.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-freeze", action="store_true")
    parser.add_argument("--qualify-synthetic", action="store_true")
    parser.add_argument("--dry-run-metadata", action="store_true")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--confirm-gate3-private-generation", action="store_true")
    args = parser.parse_args()
    try:
        if args.generate:
            if not args.confirm_gate3_private_generation or not generation_authorized():
                raise PrivateAuthoringError("private_generation_authorization_required")
            if os.environ.get("NFR_GATE3_B1_V3_AUTHORIZED") != "true":
                raise PrivateAuthoringError("gate3_b1_v3_authorization_required")
            result = generate_draft_pool()
            print(json.dumps(result, sort_keys=True))
            return 0
        if not any((args.verify_freeze, args.qualify_synthetic, args.dry_run_metadata)):
            raise PrivateAuthoringError("select_a_gate3a_mode")
        result = (
            verify_freeze()
            if args.verify_freeze
            else qualify_synthetic()
            if args.qualify_synthetic
            else dry_run_metadata()
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, jsonschema.ValidationError) as exc:
        print(json.dumps({"verdict": "fail", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
