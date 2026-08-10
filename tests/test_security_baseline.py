from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import verify_security_baseline as baseline

ROOT = Path(__file__).resolve().parents[1]


def test_security_baseline_passes() -> None:
    result = baseline.verify()
    assert result["verdict"] == "pass"
    assert result["detected_vulnerabilities"] == 1
    assert result["architecture_mitigated"] == 1
    assert result["unresolved_actionable"] == 0
    assert result["mutation_performed"] is False


def test_a3_and_no_uv_lock() -> None:
    data = json.loads((ROOT / "config/security_baseline.json").read_text())
    assert data["requirements_source"] == "requirements.txt"
    assert not (ROOT / "uv.lock").exists()
    assert (ROOT / "requirements.lock").is_file()


def test_baseline_detects_lock_hash_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = json.loads((ROOT / "config/security_baseline.json").read_text())
    data["requirements_lock_sha256"] = "0" * 64
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(baseline, "BASELINE", path)
    with pytest.raises(baseline.SecurityBaselineError, match="requirements_lock_drift"):
        baseline.verify()


def test_wrapper_requires_redaction_and_staged_scan() -> None:
    wrapper = (ROOT / "scripts/run_gitleaks_precommit.py").read_text()
    assert "--redact" in wrapper
    assert "--staged" in wrapper
    assert "Path.home()" in wrapper


def test_baseline_has_single_permitted_advisory() -> None:
    data = json.loads((ROOT / "config/security_baseline.json").read_text())
    assert data["audit"]["permitted_advisory"] == "PYSEC-2026-311"
    assert data["audit"]["detected_vulnerabilities"] == 1
    assert data["audit"]["architecture_mitigated"] == 1
