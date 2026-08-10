#!/usr/bin/env python3
"""Verify the narrow, version-bound Chroma vulnerability disposition."""

from __future__ import annotations

import ast
import importlib.metadata
import json
import re
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "vulnerability_exceptions.json"
SCHEMA = ROOT / "schemas" / "vulnerability_exceptions.schema.json"
EXPECTED_ADVISORY = "PYSEC-2026-311"
EXPECTED_VERSION = "1.5.8"
QUERY_TEXTS_MARKER = "query_" + "texts"
HTTP_CLIENT_MARKER = "Http" + "Client"
ASYNC_HTTP_CLIENT_MARKER = "Async" + "Http" + "Client"


class ExceptionVerificationError(RuntimeError):
    """The exception registry or its compensating controls are invalid."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExceptionVerificationError(f"invalid_json:{path}") from exc
    if not isinstance(value, dict):
        raise ExceptionVerificationError(f"json_not_object:{path}")
    return value


def _validate_registry(path: Path = CONFIG) -> dict[str, Any]:
    schema = _load_json(SCHEMA)
    registry = _load_json(path)
    schema_errors = sorted(
        Draft202012Validator.check_schema(schema) for _ in [0]
    )
    del schema_errors
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(registry),
        key=lambda error: list(error.path),
    )
    if errors:
        raise ExceptionVerificationError("registry_schema_invalid")
    entries = registry["exceptions"]
    ids = [entry["advisory_id"] for entry in entries]
    if len(ids) != len(set(ids)):
        raise ExceptionVerificationError("duplicate_advisory_exception")
    if ids != [EXPECTED_ADVISORY]:
        raise ExceptionVerificationError("unknown_or_missing_advisory_exception")
    return registry


def _call_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
            elif isinstance(node.func, ast.Name):
                names.add(node.func.id)
    return names


def verify_chroma_boundary(root: Path = ROOT) -> dict[str, Any]:
    vector_path = root / "src" / "natural_flow_rag" / "vector_store.py"
    if not vector_path.is_file():
        raise ExceptionVerificationError("vector_store_missing")
    source = vector_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(vector_path))
    except SyntaxError as exc:
        raise ExceptionVerificationError("vector_store_syntax_invalid") from exc
    calls = _call_names(tree)
    active_files = [
        *sorted((root / "src").rglob("*.py")),
        *sorted((root / "mcp").rglob("*.py")),
        *sorted((root / "scripts").rglob("*.py")),
    ]
    forbidden = {
        HTTP_CLIENT_MARKER: [],
        ASYNC_HTTP_CLIENT_MARKER: [],
        QUERY_TEXTS_MARKER: [],
        "enable_" + "tasks": [],
        "chroma" + ".server": [],
        "chroma" + " run": [],
        "Fast" + "API": [],
    }
    for path in active_files:
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            if marker in text:
                forbidden[marker].append(str(path.relative_to(root)))
    forbidden = {key: sorted(value) for key, value in forbidden.items() if value}
    if forbidden:
        raise ExceptionVerificationError(f"active_chroma_boundary_offender:{forbidden}")
    required = {
        "persistent_client": "PersistentClient" in calls and "PersistentClient" in source,
        "containment_check": "resolve_inside_project" in source,
        "explicit_get_embedding_function": bool(
            re.search(r"get_collection\(.*embedding_function=", source, re.S)
        ),
        "explicit_query_embeddings": "query_embeddings=" in source,
        "no_text_query_api": QUERY_TEXTS_MARKER not in source,
        "explicit_write_embeddings": "embeddings=" in source and ".upsert(" in source,
        "no_network_client": (
            HTTP_CLIENT_MARKER not in source
            and ASYNC_HTTP_CLIENT_MARKER not in source
        ),
    }
    if not all(required.values()):
        raise ExceptionVerificationError("vector_store_boundary_incomplete")
    rag_path = root / "config" / "rag.yaml"
    try:
        rag = yaml.safe_load(rag_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ExceptionVerificationError("rag_config_invalid") from exc
    collection = rag.get("collection", {}) if isinstance(rag, dict) else {}
    if not isinstance(collection, dict) or not collection.get("persistence_path"):
        raise ExceptionVerificationError("remote_or_uncontrolled_chroma_config")
    return {"checks": required, "active_offenders": {}, "mutation_performed": False}


def verify(
    config_path: Path = CONFIG,
    root: Path = ROOT,
    installed_version: str | None = None,
) -> dict[str, Any]:
    registry = _validate_registry(config_path)
    if installed_version is None:
        try:
            installed_version = importlib.metadata.version("chromadb")
        except importlib.metadata.PackageNotFoundError as exc:
            raise ExceptionVerificationError("chromadb_not_installed") from exc
    entry = registry["exceptions"][0]
    if installed_version != entry["exact_package_version"]:
        raise ExceptionVerificationError("chromadb_version_mismatch")
    boundary = verify_chroma_boundary(root)
    return {
        "schema_version": 1,
        "verdict": "pass",
        "advisory_id": EXPECTED_ADVISORY,
        "package": "chromadb",
        "installed_version": installed_version,
        "disposition": entry["disposition"],
        "architecture_decision": entry["architecture_decision"],
        "boundary": boundary,
        "unknown_exceptions_rejected": True,
        "mutation_performed": False,
    }


def main() -> int:
    try:
        print(json.dumps(verify(), sort_keys=True))
        return 0
    except ExceptionVerificationError as exc:
        print(json.dumps({"verdict": "fail", "error": str(exc), "mutation_performed": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
