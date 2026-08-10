#!/usr/bin/env python3
"""Verify the narrow, version-bound Chroma vulnerability disposition."""

from __future__ import annotations

import ast
import importlib.metadata
import json
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
    schema_errors = sorted(Draft202012Validator.check_schema(schema) for _ in [0])
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


def _attribute_name(node: ast.AST) -> str | None:
    """Return a dotted call name without interpreting arbitrary expressions."""
    parts: list[str] = []
    current: ast.AST | None = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return ".".join(reversed(parts)) or None


def _calls(tree: ast.AST, suffix: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and (_attribute_name(node.func) or "").endswith(suffix)
    ]


def _has_keyword(call: ast.Call, name: str) -> bool:
    return any(keyword.arg == name for keyword in call.keywords)


def _function_call_names(tree: ast.AST, suffix: str) -> list[str]:
    return [_attribute_name(call.func) or "" for call in _calls(tree, suffix)]


def _persistent_client_is_contained(tree: ast.AST) -> bool:
    """Require containment in the same function/property before client creation."""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        persistent = [
            call
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
            and (_attribute_name(call.func) or "").endswith("PersistentClient")
        ]
        if not persistent:
            continue
        containment = [
            call
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
            and (_attribute_name(call.func) or "").endswith("resolve_inside_project")
        ]
        if not containment:
            return False
        if not any(item.lineno < client.lineno for item in containment for client in persistent):
            return False
    return True


def _ast_boundary_checks(vector_tree: ast.AST) -> dict[str, bool]:
    persistent = [
        call
        for call in ast.walk(vector_tree)
        if isinstance(call, ast.Call)
        and (_attribute_name(call.func) or "").endswith("PersistentClient")
    ]
    get_calls = _calls(vector_tree, "get_collection")
    query_calls = _calls(vector_tree, "query")
    write_calls = [*_calls(vector_tree, "add"), *_calls(vector_tree, "upsert")]
    return {
        "persistent_client": bool(persistent)
        and all(_attribute_name(call.func) == "chromadb.PersistentClient" for call in persistent),
        "containment_check": bool(persistent) and _persistent_client_is_contained(vector_tree),
        "explicit_get_embedding_function": bool(get_calls)
        and all(_has_keyword(call, "embedding_function") for call in get_calls),
        "explicit_query_embeddings": bool(query_calls)
        and all(
            _has_keyword(call, "query_embeddings") and not _has_keyword(call, "query_texts")
            for call in query_calls
        ),
        "explicit_write_embeddings": bool(write_calls)
        and all(_has_keyword(call, "embeddings") for call in write_calls),
        "no_network_client": not any(
            _attribute_name(call.func)
            in {
                "chromadb.HttpClient",
                "chromadb.AsyncHttpClient",
                "chromadb.CloudClient",
                "chromadb.EphemeralClient",
            }
            for call in ast.walk(vector_tree)
            if isinstance(call, ast.Call)
        ),
    }


def _ast_forbidden_surfaces(tree: ast.AST) -> list[str]:
    offenders: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in {"chromadb.server", "chromadb.api.fastapi"}:
                offenders.add(module)
            if any(alias.name == "FastAPI" for alias in node.names):
                offenders.add("FastAPI")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {"chromadb.server", "chromadb.api.fastapi"}:
                    offenders.add(alias.name)
        elif isinstance(node, ast.Call):
            name = _attribute_name(node.func) or ""
            if name in {
                "chromadb.HttpClient",
                "chromadb.AsyncHttpClient",
                "chromadb.CloudClient",
                "chromadb.EphemeralClient",
            }:
                offenders.add(name)
            if name.endswith("enable_tasks"):
                offenders.add(name)
            if name in {
                "subprocess.run",
                "subprocess.call",
                "subprocess.check_call",
                "subprocess.Popen",
            }:
                if any(
                    isinstance(arg, ast.Constant)
                    and isinstance(arg.value, str)
                    and "chroma run" in arg.value
                    for arg in node.args
                ):
                    offenders.add("chroma run")
            if name.endswith("query") and _has_keyword(node, "query_texts"):
                offenders.add("query_texts")
    return sorted(offenders)


def verify_chroma_boundary(root: Path = ROOT) -> dict[str, Any]:
    vector_path = root / "src" / "natural_flow_rag" / "vector_store.py"
    if not vector_path.is_file():
        raise ExceptionVerificationError("vector_store_missing")
    source = vector_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(vector_path))
    except SyntaxError as exc:
        raise ExceptionVerificationError("vector_store_syntax_invalid") from exc
    active_files = [
        *sorted((root / "src").rglob("*.py")),
        *sorted((root / "mcp").rglob("*.py")),
        *sorted((root / "scripts").rglob("*.py")),
    ]
    forbidden: dict[str, list[str]] = {}
    for path in active_files:
        try:
            active_tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            raise ExceptionVerificationError(f"active_python_syntax_invalid:{path}") from exc
        for marker in _ast_forbidden_surfaces(active_tree):
            forbidden.setdefault(marker, []).append(str(path.relative_to(root)))
    forbidden = {key: sorted(value) for key, value in sorted(forbidden.items())}
    if forbidden:
        raise ExceptionVerificationError(f"active_chroma_boundary_offender:{forbidden}")
    required = _ast_boundary_checks(tree)
    required["no_text_query_api"] = "query_texts" not in _ast_forbidden_surfaces(tree)
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
