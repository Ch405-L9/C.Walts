#!/usr/bin/env python3
"""Fail-closed inspection and authorization for the limitation register."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs" / "known-limitations-v0.4.md"
SCHEMA_PATH = ROOT / "schemas" / "blocker_registry.schema.json"
SCOPE_POLICY = "explicit_blocking_scopes_v1"
SUPPORTED_SCOPES = (
    "gate2_authorization",
    "calibration",
    "rc_creation",
    "release_promotion",
)
CANONICAL_BLOCKER_ID = "CW-LIM-009-DENSE-COVERAGE"
STATUS_VALUES = {"deferred", "accepted", "resolved"}
BLOCK_PATTERN = re.compile(r"```yaml\n(.*?)```", re.DOTALL)


class BlockerRegistryError(ValueError):
    """A machine-readable blocker registry failure."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


def _registry_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError as exc:
        raise BlockerRegistryError("registry_missing") from exc
    except OSError as exc:
        raise BlockerRegistryError("registry_read_failed") from exc


def _load_schema() -> dict[str, Any]:
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BlockerRegistryError("registry_schema_missing") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise BlockerRegistryError("registry_schema_invalid") from exc
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        raise BlockerRegistryError("registry_schema_invalid") from exc
    return schema


def _read_entries(path: Path) -> tuple[list[dict[str, Any]], str]:
    digest = _registry_sha256(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise BlockerRegistryError("registry_missing") from exc
    except OSError as exc:
        raise BlockerRegistryError("registry_read_failed") from exc

    entries: list[dict[str, Any]] = []
    try:
        blocks = BLOCK_PATTERN.findall(text)
    except re.error as exc:  # pragma: no cover - constant pattern
        raise BlockerRegistryError("registry_yaml_invalid") from exc
    for block in blocks:
        try:
            parsed = yaml.safe_load(block)
        except yaml.YAMLError as exc:
            raise BlockerRegistryError("registry_yaml_invalid") from exc
        if not isinstance(parsed, dict):
            raise BlockerRegistryError("registry_entry_invalid")
        if not parsed.get("id"):
            raise BlockerRegistryError("registry_entry_invalid")
        entries.append(parsed)
    if not entries:
        raise BlockerRegistryError("registry_entry_invalid")
    return entries, digest


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    """Parse and validate the canonical register without changing it."""
    entries, digest = _read_entries(path)
    ids = [str(entry["id"]) for entry in entries]
    if len(ids) != len(set(ids)):
        raise BlockerRegistryError("duplicate_blocker_id")

    payload = {
        "schema_version": 1,
        "scope_policy": SCOPE_POLICY,
        "entries": entries,
    }
    schema = _load_schema()
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(payload), key=str)
    if errors:
        raise BlockerRegistryError("registry_entry_invalid")

    for entry in entries:
        status = entry.get("status")
        scopes = entry.get("blocking_scopes")
        if status not in STATUS_VALUES:
            raise BlockerRegistryError("unknown_blocker_status")
        if not isinstance(scopes, list) or len(scopes) != len(set(scopes)):
            raise BlockerRegistryError("blocking_scope_invalid")
        if status in {"accepted", "resolved"} and scopes:
            code = (
                "accepted_blocker_has_active_scope"
                if status == "accepted"
                else "resolved_blocker_has_active_scope"
            )
            raise BlockerRegistryError(code)
        if status == "resolved" and not entry.get("resolved_at"):
            raise BlockerRegistryError("resolved_without_closure_evidence")
        if status == "resolved" and not entry.get("resolved_by"):
            raise BlockerRegistryError("resolved_without_closure_evidence")
        if (
            entry["id"] == CANONICAL_BLOCKER_ID
            and status == "deferred"
            and set(scopes) != set(SUPPORTED_SCOPES)
        ):
            raise BlockerRegistryError("canonical_blocker_scope_mismatch")
    return {
        "schema_version": 1,
        "scope_policy": SCOPE_POLICY,
        "entries": entries,
        "registry_sha256": digest,
    }


def list_open_blockers(registry: dict[str, Any], scope: str | None = None) -> list[str]:
    if scope is not None and scope not in SUPPORTED_SCOPES:
        raise BlockerRegistryError("unsupported_authorization_scope")
    result = []
    for entry in registry["entries"]:
        if entry["status"] != "deferred":
            continue
        if scope is None or scope in entry["blocking_scopes"]:
            result.append(str(entry["id"]))
    return sorted(result)


def report(
    registry: dict[str, Any], mode: str, scope: str | None, verdict: str, ids: list[str]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "scope": scope,
        "mode": mode,
        "verdict": verdict,
        "open_blocker_count": len(ids),
        "open_blocker_ids": ids,
        "registry_path": str(REGISTRY_PATH.relative_to(ROOT)),
        "registry_sha256": registry["registry_sha256"],
        "scope_policy": SCOPE_POLICY,
        "mutation_performed": False,
    }


def verify_scope(scope: str, path: Path = REGISTRY_PATH) -> dict[str, Any]:
    if scope not in SUPPORTED_SCOPES:
        raise BlockerRegistryError("unsupported_authorization_scope")
    registry = load_registry(path)
    ids = list_open_blockers(registry, scope)
    if ids:
        raise BlockerRegistryError("open_blocker_present", ",".join(ids))
    return report(registry, "authorization", scope, "pass", ids)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--list-open", action="store_true")
    modes.add_argument("--verify-scope")
    parser.add_argument("--scope")
    args = parser.parse_args()
    try:
        registry = load_registry()
        if args.verify_scope:
            if args.scope is not None:
                raise BlockerRegistryError("unsupported_authorization_scope")
            result = verify_scope(args.verify_scope)
        else:
            result_scope = args.scope
            ids = list_open_blockers(registry, result_scope)
            result = report(registry, "inspection", result_scope, "pass", ids)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except BlockerRegistryError as exc:
        print(
            json.dumps(
                {"verdict": "fail", "finding": exc.code, "mutation_performed": False},
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
