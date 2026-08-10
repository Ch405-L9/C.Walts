"""Gate 3 local-only generator controls; canonical generation is Gate 3-B."""

from __future__ import annotations

import argparse
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
        SLOTS,
        PrivateAuthoringError,
        generation_authorized,
        load_freeze,
        require_loopback,
    )


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


def qualify_synthetic() -> dict[str, Any]:
    freeze = load_freeze()
    require_loopback(freeze["endpoint"])
    prompt = (
        "Return ONLY one JSON object with exactly these keys: slot_id, draft_role, query_text. "
        "Never use the key request or any other key. slot_id must be G3S-0001. "
        "draft_role must be exactly primary. query_text must be one synthetic atomic request "
        "about arranging fictional blocks. Do not answer it."
    )
    last_error = ""
    for attempt in range(1, 3):
        payload = {
            "model": freeze["model"],
            "prompt": prompt,
            "format": "json",
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
        try:
            with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
                response_payload = json.loads(response.read())
            value = json.loads(response_payload.get("response", ""))
            validate_draft(value)
            return {
                "verdict": "pass",
                "synthetic_cases": 1,
                "json_valid": 1,
                "schema_pass": 1,
                "attempts": attempt,
                "raw_output_printed": False,
                "canonical_generation_executed": False,
            }
        except (OSError, ValueError, TypeError, jsonschema.ValidationError) as exc:
            last_error = type(exc).__name__
    raise PrivateAuthoringError(f"synthetic_qualification_failed:{last_error}")


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
