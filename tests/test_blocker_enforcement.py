"""Adversarial tests for the Stage 6 fail-closed blocker boundary."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts import authorize_gate_transition as adapter
from scripts import verify_open_blockers as verifier

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ID = "CW-LIM-009-DENSE-COVERAGE"
SCOPES = list(verifier.SUPPORTED_SCOPES)


def _entry(
    blocker_id: str = CANONICAL_ID,
    *,
    status: str = "deferred",
    scopes: list[str] | None = None,
    legacy_gate2: bool = False,
) -> dict[str, object]:
    value: dict[str, object] = {
        "id": blocker_id,
        "status": status,
        "severity": "medium",
        "blocks_gate2": legacy_gate2,
        "blocks_threshold_calibration": True,
        "blocks_release_candidate": True,
        "blocking_scopes": SCOPES if scopes is None and status == "deferred" else (scopes or []),
    }
    if status == "resolved":
        value["resolved_at"] = "0.4.0-dev.9"
        value["resolved_by"] = "synthetic-evidence"
    return value


def _write_registry(path: Path, entries: list[dict[str, object]]) -> Path:
    blocks = []
    for entry in entries:
        blocks.extend(["```yaml", yaml.safe_dump(entry, sort_keys=False).rstrip(), "```", ""])
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path


def _unclosed_resolved_entry() -> dict[str, object]:
    entry = _entry("CW-LIM-OTHER", status="resolved", scopes=[])
    entry.pop("resolved_at", None)
    entry.pop("resolved_by", None)
    return entry


def test_canonical_registry_and_a2_scope_policy() -> None:
    registry = verifier.load_registry()
    entries = {entry["id"]: entry for entry in registry["entries"]}
    current = entries[CANONICAL_ID]
    assert current["status"] == "resolved"
    assert current["blocks_gate2"] is False
    assert current["blocking_scopes"] == []
    assert current["resolved_by"] == "docs/evidence/gate1_2-stage8-dense-coverage.json"
    assert verifier.list_open_blockers(registry) == []


@pytest.mark.parametrize("scope", SCOPES)
def test_current_real_scope_clears(scope: str) -> None:
    result = verifier.verify_scope(scope)
    assert result["verdict"] == "pass"


@pytest.mark.parametrize("scope", SCOPES)
def test_adapter_authorizes_current_real_scope(scope: str) -> None:
    result = adapter.authorize_gate_transition(scope)
    assert result["mutation_performed"] is False


def test_legacy_gate2_false_does_not_override_explicit_scope(tmp_path: Path) -> None:
    path = _write_registry(
        tmp_path / "registry.md",
        [_entry(status="deferred", scopes=SCOPES, legacy_gate2=False)],
    )
    with pytest.raises(verifier.BlockerRegistryError, match="open_blocker_present"):
        verifier.verify_scope("gate2_authorization", path)


def test_synthetic_closed_fixture_authorizes_all_scopes(tmp_path: Path) -> None:
    path = _write_registry(tmp_path / "registry.md", [_entry(status="resolved", scopes=[])])
    registry = verifier.load_registry(path)
    assert verifier.list_open_blockers(registry) == []
    called: list[str] = []
    for scope in SCOPES:
        result = adapter.authorize_gate_transition(
            scope,
            registry_path=path,
            stage5_checker=lambda: called.append("stage5"),
        )
        assert result["mutation_performed"] is False
    assert called == ["stage5"]


def test_gate2_blocker_refusal_precedes_stage5(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list[str] = []
    monkeypatch.setattr(adapter, "verify_scope", lambda *args: (_ for _ in ()).throw(
        verifier.BlockerRegistryError("open_blocker_present")
    ))
    with pytest.raises(adapter.AuthorizationError, match="open_blocker_present"):
        adapter.authorize_gate_transition(
            "gate2_authorization", stage5_checker=lambda: called.append("called")
        )
    assert called == []


def test_gate2_stage5_failure_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "verify_scope", lambda *args: {"verdict": "pass"})
    with pytest.raises(adapter.AuthorizationError, match="stage5_prerequisite_failed"):
        adapter.authorize_gate_transition(
            "gate2_authorization",
            stage5_checker=lambda: (_ for _ in ()).throw(
                adapter.AuthorizationError("stage5_prerequisite_failed")
            ),
        )


@pytest.mark.parametrize(
    ("entry", "code"),
    [
        ({"status": "deferred", "blocking_scopes": SCOPES}, "registry_entry_invalid"),
        (_entry("CW-LIM-OTHER", status="pendingish", scopes=[]), "registry_entry_invalid"),
        (
            _entry("CW-LIM-OTHER", status="accepted", scopes=["calibration"]),
            "accepted_blocker_has_active_scope",
        ),
        (_unclosed_resolved_entry(), "resolved_without_closure_evidence"),
        (_entry("CW-LIM-OTHER", scopes=["calibration-ish"]), "registry_entry_invalid"),
    ],
)
def test_registry_failures_are_explicit(
    tmp_path: Path, entry: dict[str, object], code: str
) -> None:
    path = _write_registry(tmp_path / "registry.md", [entry])
    with pytest.raises(verifier.BlockerRegistryError, match=code):
        verifier.load_registry(path)


def test_duplicate_id_fails_closed(tmp_path: Path) -> None:
    path = _write_registry(tmp_path / "registry.md", [_entry(), _entry()])
    with pytest.raises(verifier.BlockerRegistryError, match="duplicate_blocker_id"):
        verifier.load_registry(path)


def test_missing_registry_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(verifier.BlockerRegistryError, match="registry_missing"):
        verifier.load_registry(tmp_path / "missing.md")


def test_sorted_ids_and_exact_scope_matching(tmp_path: Path) -> None:
    entries = [
        _entry("CW-LIM-Z", scopes=["calibration"]),
        _entry("CW-LIM-A", scopes=["calibration"]),
    ]
    registry = verifier.load_registry(_write_registry(tmp_path / "registry.md", entries))
    assert verifier.list_open_blockers(registry, "calibration") == ["CW-LIM-A", "CW-LIM-Z"]
    assert verifier.list_open_blockers(registry, "gate2_authorization") == []


def test_cli_has_no_registry_override() -> None:
    result = subprocess.run(  # noqa: S603
        [
            ".venv/bin/python",
            "scripts/verify_open_blockers.py",
            "--list-open",
            "--registry",
            str(ROOT),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0


def test_cli_output_is_machine_only_and_read_only() -> None:
    result = subprocess.run(
        [".venv/bin/python", "scripts/verify_open_blockers.py", "--list-open"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["open_blocker_ids"] == []
    assert payload["mutation_performed"] is False
    assert "blocking_scopes" not in payload


def test_unsupported_transition_refuses() -> None:
    with pytest.raises(adapter.AuthorizationError, match="unsupported_authorization_scope"):
        adapter.authorize_gate_transition("not-a-scope")
