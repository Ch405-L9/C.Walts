"""Gate 3 local-only generator controls; canonical generation is Gate 3-B."""

from __future__ import annotations

import argparse
import hashlib
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
        POLICY,
        POOL_RELATIVE,
        ROOT,
        SEAL_RELATIVE,
        SLOTS,
        PrivateAuthoringError,
        atomic_write_bytes,
        canonical_sha256,
        file_sha256,
        generation_authorized,
        load_freeze,
        require_loopback,
        resolve_private_path,
        verify_model_identity,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from gate3_private_common import (
        AUDIT_RELATIVE,
        DRAFT_SCHEMA,
        POLICY,
        POOL_RELATIVE,
        ROOT,
        SEAL_RELATIVE,
        SLOTS,
        PrivateAuthoringError,
        atomic_write_bytes,
        canonical_sha256,
        file_sha256,
        generation_authorized,
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
    freeze: dict[str, Any], prompt: str, output_format: Any
) -> tuple[dict[str, Any], int]:
    payload = {
        "model": freeze["model"],
        "prompt": prompt,
        "format": output_format,
        "stream": False,
        "think": False,
        "options": freeze["parameters"],
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
    if re.search(
        r"\b(answer|qrel|holdout|calibration|threshold|score|chunk[_ -]?id|source[_ -]?id)\b",
        value["query_text"],
        re.I,
    ):
        raise PrivateAuthoringError("unsafe_metadata_in_query_text")
    if re.search(
        r"(?:^|\s)(?:rm|sudo|bash|sh|python)\b|\.\./|/etc/|https?://", value["query_text"], re.I
    ):
        raise PrivateAuthoringError("command_path_or_url_in_query_text")
    if re.search(r"\?[^?]{0,240}\b(and then|also|additionally|;|\?)\b", value["query_text"], re.I):
        raise PrivateAuthoringError("obvious_compound_request")


def qualify_synthetic() -> dict[str, Any]:
    freeze = load_freeze()
    require_loopback(freeze["endpoint"])
    fixtures = [
        {"task_family": "fictional_block_arrangement", "scenario_family": "simple_atomic"},
        {"task_family": "fictional_preservation", "scenario_family": "preservation_like"},
        {"task_family": "fictional_measurement", "scenario_family": "analysis_like"},
        {"task_family": "fictional_clarification", "scenario_family": "clarification_like"},
        {"task_family": "fictional_reordering", "scenario_family": "awkward_metadata"},
        {
            "task_family": "fictional_instruction_data",
            "scenario_family": "instruction_like_data",
            "value": "ignore this value as instructions",
        },
        {
            "task_family": "fictional_path_data",
            "scenario_family": "path_like_data",
            "value": "/" + "tmp/fictional; echo never execute",
        },
        {
            "task_family": "fictional_no_answer",
            "scenario_family": "answer_pressure",
            "value": "do not provide a solution",
        },
    ]
    configs = [
        {"temperature": 0.35, "top_p": 0.9},
        {"temperature": 0.25, "top_p": 0.95},
        {"temperature": 0.45, "top_p": 0.85},
    ]
    schema = json.loads(DRAFT_SCHEMA.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    for config in configs:
        attempts = 0
        metrics = {
            "cases_attempted": len(fixtures), "transport_success": 0, "json_parse_pass": 0,
            "schema_pass": 0, "atomicity_pass": 0, "answer_qrel_leakage": 0,
            "forbidden_metadata_leakage": 0, "extra_field_failures": 0,
            "unsafe_command_path_url_failures": 0, "retry_count": 0, "successful_cases": 0,
        }
        for index, fixture in enumerate(fixtures, 1):
            metadata = {"slot_id": f"G3S-{9000 + index:04d}", **fixture, "synthetic_only": True}
            prompt = build_generation_prompt(load_base_prompt(), metadata, "primary")
            passed = False
            for attempt in range(1, 3):
                attempts += 1
                try:
                    run_freeze = dict(freeze)
                    run_freeze["parameters"] = {**freeze["parameters"], **config}
                    value, _ = model_request(run_freeze, prompt, "json")
                    metrics["transport_success"] += 1
                    metrics["json_parse_pass"] += 1
                    jsonschema.validate(value, schema)
                    metrics["schema_pass"] += 1
                    validate_draft(value)
                    metrics["atomicity_pass"] += 1
                    metrics["successful_cases"] += 1
                    passed = True
                    break
                except jsonschema.ValidationError as exc:
                    instance = getattr(exc, "instance", None)
                    extra_keys = (
                        set(instance) - {"slot_id", "draft_role", "query_text"}
                        if isinstance(instance, dict)
                        else set()
                    )
                    if extra_keys:
                        metrics["extra_field_failures"] += 1
                except PrivateAuthoringError as exc:
                    if str(exc) in {"unsafe_metadata_in_query_text", "answer_or_qrel_leakage"}:
                        metrics["answer_qrel_leakage"] += 1
                    elif str(exc) == "obvious_compound_request":
                        pass
                    else:
                        metrics["unsafe_command_path_url_failures"] += 1
                except (OSError, ValueError, TypeError):
                    pass
                if attempt == 1:
                    metrics["retry_count"] += 1
            if not passed:
                results.append(
                    {"parameters": config, **metrics, "attempts": attempts, "verdict": "fail"}
                )
                break
        else:
            results.append(
                {"parameters": config, **metrics, "attempts": attempts, "verdict": "pass"}
            )
    ranked = sorted(
        results,
        key=lambda item: (
            item["successful_cases"], item["schema_pass"], item["atomicity_pass"],
            -item["retry_count"],
            hashlib.sha256(json.dumps(item["parameters"], sort_keys=True).encode()).hexdigest(),
        ),
        reverse=True,
    )
    selected = ranked[0]
    if (
        selected["successful_cases"] != len(fixtures)
        or selected["answer_qrel_leakage"]
        or selected["unsafe_command_path_url_failures"]
    ):
        raise PrivateAuthoringError("synthetic_qualification_threshold_failed")
    return {
        "verdict": "pass", "synthetic_cases_per_configuration": len(fixtures),
        "configurations_tested": results, "selected": selected,
        "raw_output_printed": False, "canonical_generation_executed": False,
        "prompt_composition": "shared", "format_mode": "json",
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
    return canonical_sha256(
        {
            "slot_id": slot["slot_id"],
            "draft_role": role,
            "query_text": query_text,
            "policy_sha256": policy_sha,
            "generation_freeze_sha256": freeze_sha,
        }
    )


def _draft_metadata(
    slot: dict[str, Any], role: str, query_text: str, freeze_sha: str, policy_sha: str
) -> dict[str, Any]:
    template = canonical_sha256(
        {
            "policy_id": "gate3-custom-authoring-v1",
            "prompt_sha256": file_sha256(ROOT / "config/gate3_custom_generation_prompt.txt"),
            "scenario_family": slot["scenario_family"],
            "task_family": slot["task_family"],
            "structural_family": slot["structural_family"],
            "template_family_id": slot["template_family_id"],
        }
    )
    group = "G3G-" + hashlib.sha256(str(slot["group_family"]).encode()).hexdigest()[:24]
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
        "generation_model": freeze_sha,
        "policy_sha256": policy_sha,
        "generation_freeze_sha256": freeze_sha,
        "prompt_sha256": file_sha256(ROOT / "config/gate3_custom_generation_prompt.txt"),
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
    if not os.environ.get("NFR_GATE3_B1_AUTHORIZED") == "true":
        raise PrivateAuthoringError("gate3_b1_authorization_required")
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
    try:
        for slot in slots:
            for role in ("primary", "replacement"):
                prompt = build_generation_prompt(load_base_prompt(), slot, role)
                accepted = None
                for attempt in range(1, 3):
                    attempts += 1
                    try:
                        value, _ = model_request(freeze, prompt, "json")
                        validate_draft(value)
                        if value["slot_id"] != slot["slot_id"] or value["draft_role"] != role:
                            raise PrivateAuthoringError("returned_slot_role_mismatch")
                        accepted = _draft_metadata(
                            slot, role, value["query_text"], freeze_sha, policy_sha
                        )
                        break
                    except (OSError, ValueError, TypeError, jsonschema.ValidationError) as exc:
                        if attempt == 1:
                            retries += 1
                        if attempt == 2:
                            raise PrivateAuthoringError(
                                f"draft_generation_failed:{slot['slot_id']}:{role}:{type(exc).__name__}"
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
    except BaseException:
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
            if os.environ.get("NFR_GATE3_B1_AUTHORIZED") != "true":
                raise PrivateAuthoringError("gate3_b1_authorization_required")
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
