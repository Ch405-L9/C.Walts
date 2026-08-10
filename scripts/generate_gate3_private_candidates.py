"""Gate 3 local-only generator controls; canonical generation is Gate 3-B."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from typing import Any

import jsonschema
import yaml

try:
    from scripts.gate3_private_common import (
        DRAFT_SCHEMA,
        POLICY,
        ROOT,
        SLOTS,
        PrivateAuthoringError,
        generation_authorized,
        load_freeze,
        require_loopback,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from gate3_private_common import (
        DRAFT_SCHEMA,
        POLICY,
        ROOT,
        SLOTS,
        PrivateAuthoringError,
        generation_authorized,
        load_freeze,
        require_loopback,
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
            raise PrivateAuthoringError("canonical_generation_not_authorized_in_gate3a")
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
