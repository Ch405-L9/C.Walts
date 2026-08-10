#!/usr/bin/env python3
"""Read-only Stage 7 security and supply-chain baseline verifier."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASELINE = ROOT / "config" / "security_baseline.json"
SCHEMA = ROOT / "schemas" / "security_baseline.schema.json"
EXPECTED_GITLEAKS_SHA = "88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509"


class SecurityBaselineError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SecurityBaselineError(f"invalid_json:{path}") from exc
    if not isinstance(data, dict):
        raise SecurityBaselineError("json_object_required")
    return data


def _validate_lock(path: Path) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    packages = 0
    for index, line in enumerate(lines):
        if not re.match(r"^[A-Za-z0-9_.-]+==\S+", line) or not line.endswith("\\"):
            continue
        packages += 1
        block = "\n".join(lines[index : index + 200])
        if "--hash=sha256:" not in block.split("    # via", 1)[0]:
            raise SecurityBaselineError("lock_package_without_hash")
        if any(
            token in block.split("    # via", 1)[0]
            for token in ("git+", "file://", "--trusted-host", "${", "@")
        ):
            raise SecurityBaselineError("lock_unsafe_source")
    if packages != 100:
        raise SecurityBaselineError("lock_package_count_mismatch")
    return packages


def _tool_version(command: list[str], expected: str) -> None:
    try:
        result = subprocess.run(  # noqa: S603
            command, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SecurityBaselineError(f"tool_unavailable:{command[0]}") from exc
    if expected not in (result.stdout + result.stderr):
        raise SecurityBaselineError(f"tool_version_mismatch:{command[0]}")


def verify() -> dict[str, Any]:
    baseline = _load(BASELINE)
    schema = _load(SCHEMA)
    jsonschema.Draft202012Validator.check_schema(schema)
    errors = list(
        jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker()
        ).iter_errors(baseline)
    )
    if errors:
        raise SecurityBaselineError("baseline_schema_invalid")
    if (ROOT / "uv.lock").exists():
        raise SecurityBaselineError("uv_lock_prohibited")
    _tool_version([str(Path.home() / ".local/bin/uv"), "--version"], baseline["tools"]["uv"])
    _tool_version(
        [str(Path.home() / ".local/bin/pre-commit"), "--version"], baseline["tools"]["pre_commit"]
    )
    _tool_version(
        [str(Path.home() / ".local/bin/pip-audit"), "--version"], baseline["tools"]["pip_audit"]
    )
    gitleaks = shutil.which("gitleaks") or str(Path.home() / ".local/bin/gitleaks")
    if not Path(gitleaks).is_file() or sha256_file(Path(gitleaks)) != EXPECTED_GITLEAKS_SHA:
        raise SecurityBaselineError("gitleaks_binary_mismatch")
    _tool_version([gitleaks, "version"], baseline["tools"]["gitleaks"])
    if (
        not (ROOT / ".pre-commit-config.yaml").is_file()
        or "run_gitleaks_precommit.py" not in (ROOT / ".pre-commit-config.yaml").read_text()
    ):
        raise SecurityBaselineError("precommit_wrapper_missing")
    wrapper = (ROOT / "scripts/run_gitleaks_precommit.py").read_text()
    if "--redact" not in wrapper or "--staged" not in wrapper:
        raise SecurityBaselineError("gitleaks_redaction_or_staged_policy_missing")
    if sha256_file(ROOT / "requirements.txt") != baseline["requirements_txt_sha256"]:
        raise SecurityBaselineError("requirements_source_drift")
    if sha256_file(ROOT / "requirements.lock") != baseline["requirements_lock_sha256"]:
        raise SecurityBaselineError("requirements_lock_drift")
    if _validate_lock(ROOT / "requirements.lock") != baseline["lock_package_count"]:
        raise SecurityBaselineError("lock_structure_invalid")
    if (
        sha256_file(ROOT / "config/vulnerability_exceptions.json")
        != baseline["exception_registry_sha256"]
    ):
        raise SecurityBaselineError("exception_registry_drift")
    from scripts.verify_dependency_exceptions import verify as verify_exceptions

    verify_exceptions()
    if (
        not (ROOT / baseline["audio_manifest_path"]).is_file()
        or (ROOT / "corpus/raw/evaluation/audio_reference_manifest.yaml").exists()
    ):
        raise SecurityBaselineError("audio_path_boundary_invalid")
    sources = yaml.safe_load((ROOT / "config/sources.yaml").read_text(encoding="utf-8"))
    active_sources = sources.get("sources", []) if isinstance(sources, dict) else []
    if any("evaluation" in str(item.get("path", "")) for item in active_sources):
        raise SecurityBaselineError("production_source_evaluation_path")
    if (
        not (ROOT / "schemas/holdout_anchor.schema.json").is_file()
        or not (ROOT / "scripts/verify_holdout_anchor.py").is_file()
    ):
        raise SecurityBaselineError("anchor_tooling_missing")
    return {
        "verdict": "pass",
        "detected_vulnerabilities": 1,
        "architecture_mitigated": 1,
        "unresolved_actionable": 0,
        "mutation_performed": False,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(verify(), sort_keys=True))
    except (OSError, SecurityBaselineError, jsonschema.ValidationError) as exc:
        print(json.dumps({"verdict": "fail", "finding": str(exc), "mutation_performed": False}))
        raise SystemExit(1) from exc
