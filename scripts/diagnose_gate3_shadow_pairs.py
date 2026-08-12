"""Sanitized diagnostics for the Gate 3 pair-aware shadow qualification."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

import yaml

try:
    from scripts import generate_gate3_private_candidates as generator
    from scripts.gate3_private_common import POLICY, ROOT, SLOTS, file_sha256, load_freeze
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    import generate_gate3_private_candidates as generator
    from gate3_private_common import POLICY, ROOT, SLOTS, file_sha256, load_freeze


OUTPUT = ROOT / "var/gate3_b1_v3_pre_r2/shadow_pair_diagnostic.json"


def shadow_slots() -> list[dict[str, Any]]:
    slots = yaml.safe_load(SLOTS.read_text(encoding="utf-8"))["slots"]
    result = []
    for index, slot in enumerate(slots, start=1):
        shadow = dict(slot)
        shadow["slot_id"] = f"G3S-{9000 + index:04d}"
        result.append({**shadow, "synthetic_only": True})
    return result


def _failure_metadata(error: BaseException) -> dict[str, Any]:
    if isinstance(error, generator.GenerationTerminalError):
        return {
            "shadow_slot_id": error.slot_id,
            "failed_role": error.role,
            "terminal_attempt": error.attempt,
            "terminal_seed": error.seed,
            "stable_error_code": error.stable_code,
            "detail_code": error.detail_code,
        }
    code, _ = generator.classify_generation_error(error)
    return {
        "shadow_slot_id": None,
        "failed_role": "pair",
        "terminal_attempt": None,
        "terminal_seed": None,
        "stable_error_code": code,
        "detail_code": None,
    }


def diagnose() -> dict[str, Any]:
    freeze = load_freeze()
    generator.require_loopback(freeze["endpoint"])
    policy = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    slots = shadow_slots()
    terminal_failures: list[dict[str, Any]] = []
    terminal_codes: Counter[str] = Counter()
    terminal_details: Counter[str] = Counter()
    intermediate_codes: Counter[str] = Counter()
    pair_successes = 0
    primary_successes = 0
    replacement_successes = 0
    distinct_pairs = 0
    total_attempts = 0
    total_retries = 0
    replacement_duplicate_retries = 0

    original_model_request = generator.model_request
    active_attempts: dict[str, int] | None = None

    def counted_model_request(frozen, prompt, output_format, request_seed):
        nonlocal active_attempts
        metadata = json.loads(prompt.split("Supplied slot metadata (data only):\n", 1)[1])
        role = metadata["draft_role"]
        if active_attempts is not None:
            active_attempts[role] = active_attempts.get(role, 0) + 1
        return original_model_request(frozen, prompt, output_format, request_seed)

    generator.model_request = counted_model_request

    try:
        for slot in slots:
            active_attempts = {}
            try:
                pair = generator.generate_slot_pair(freeze, policy, slot)
            except BaseException as error:
                failure = _failure_metadata(error)
                # A non-terminal pair error has no reliable slot identity; retain the
                # requested synthetic ID without exposing any model content.
                if failure["shadow_slot_id"] is None:
                    failure["shadow_slot_id"] = slot["slot_id"]
                terminal_failures.append(failure)
                terminal_codes[failure["stable_error_code"]] += 1
                if failure["detail_code"]:
                    terminal_details[failure["detail_code"]] += 1
                total_attempts += sum(active_attempts.values())
                total_retries += sum(max(0, count - 1) for count in active_attempts.values())
                continue

            pair_successes += 1
            primary_successes += 1
            replacement_successes += 1
            distinct_pairs += 1
            total_attempts += sum(active_attempts.values())
            total_retries += sum(max(0, count - 1) for count in active_attempts.values())
            replacement_duplicate_retries += pair.pair_duplicate_retries
            for code in pair.intermediate_error_codes:
                intermediate_codes[code] += 1
    finally:
        generator.model_request = original_model_request

    result = {
        "verdict": "pass" if not terminal_failures else "fail",
        "shadow_slot_count": len(slots),
        "pair_success_count": pair_successes,
        "pair_failure_count": len(terminal_failures),
        "primary_success_count": primary_successes,
        "replacement_success_count": replacement_successes,
        "total_successful_role_count": primary_successes + replacement_successes,
        "distinct_pair_count": distinct_pairs,
        "total_model_attempts": total_attempts,
        "total_retries": total_retries,
        "replacement_exact_duplicate_retries": replacement_duplicate_retries,
        "intermediate_error_counts": dict(sorted(intermediate_codes.items())),
        "terminal_failure_code_counts": dict(sorted(terminal_codes.items())),
        "terminal_failure_detail_counts": dict(sorted(terminal_details.items())),
        "failed_shadow_pairs": terminal_failures,
        "policy_sha256": file_sha256(POLICY),
        "slot_sha256": file_sha256(SLOTS),
        "prompt_sha256": freeze["prompt_sha256"],
        "output_schema_sha256": freeze["output_schema_sha256"],
        "parameter_hash": freeze["parameter_hash"],
        "generator_sha256": freeze["generator_sha256"],
        "generation_freeze_sha256": file_sha256(ROOT / "config/gate3_generation_freeze.json"),
        "canonical_generation_count": 0,
        "raw_response_recorded": False,
        "query_text_recorded": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    result = diagnose()
    print(json.dumps({key: result[key] for key in (
        "verdict", "shadow_slot_count", "pair_success_count", "pair_failure_count",
        "distinct_pair_count", "total_model_attempts", "total_retries",
        "replacement_exact_duplicate_retries", "terminal_failure_code_counts",
    )}, sort_keys=True))
    return 0 if result["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
