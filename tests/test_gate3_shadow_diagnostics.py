from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import diagnose_gate3_shadow_pairs as diagnostics
from scripts import generate_gate3_private_candidates as generator


def _attempt(slot_id: str, role: str) -> generator.AttemptRunResult:
    return generator.AttemptRunResult(
        value={"slot_id": slot_id, "draft_role": role, "query_text": "synthetic only"},
        attempts_used=1,
        retries_used=0,
        final_seed=17,
        intermediate_error_codes=(),
    )


def test_diagnostic_continues_all_shadow_pairs_and_writes_sanitized_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []

    def fake_pair(freeze, policy, slot):
        calls.append(slot["slot_id"])
        if slot["slot_id"] == "G3S-9007":
            raise generator.GenerationTerminalError(
                "format_safety_failure",
                slot["slot_id"],
                "replacement",
                3,
                123,
                "replacement_exact_duplicate",
            )
        return generator.SlotPairResult(
            primary=_attempt(slot["slot_id"], "primary"),
            replacement=_attempt(slot["slot_id"], "replacement"),
        )

    monkeypatch.setattr(diagnostics.generator, "generate_slot_pair", fake_pair)
    monkeypatch.setattr(diagnostics, "OUTPUT", tmp_path / "shadow_pair_diagnostic.json")
    result = diagnostics.diagnose()

    assert len(calls) == 285
    assert calls[0] == "G3S-9001"
    assert calls[-1] == "G3S-9285"
    assert result["pair_success_count"] == 284
    assert result["pair_failure_count"] == 1
    assert result["primary_success_count"] == 284
    assert result["replacement_success_count"] == 284
    assert result["total_successful_role_count"] == 568
    assert result["terminal_failure_code_counts"] == {"format_safety_failure": 1}
    assert result["terminal_failure_detail_counts"] == {"replacement_exact_duplicate": 1}
    assert result["canonical_generation_count"] == 0

    written = json.loads((tmp_path / "shadow_pair_diagnostic.json").read_text())
    assert "raw_response" not in written
    assert written["query_text_recorded"] is False
    assert written["raw_response_recorded"] is False
    assert written["failed_shadow_pairs"] == [
        {
            "shadow_slot_id": "G3S-9007",
            "failed_role": "replacement",
            "terminal_attempt": 3,
            "terminal_seed": 123,
            "stable_error_code": "format_safety_failure",
            "detail_code": "replacement_exact_duplicate",
        }
    ]


def test_diagnostic_uses_pair_runner_and_shadow_ids_only() -> None:
    source = Path(diagnostics.__file__).read_text()
    assert "generator.generate_slot_pair" in source
    assert "G3S-{9000 + index:04d}" in source
    assert "G3S-0001" not in source
    failure_section = source.split("def _failure_metadata", 1)[1].split("def diagnose", 1)[0]
    assert "query_text" not in failure_section
