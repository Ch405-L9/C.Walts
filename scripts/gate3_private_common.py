"""Shared fail-closed controls for local Gate 3 private authoring tooling."""

from __future__ import annotations

import hashlib
import json
import os
import socket
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = (ROOT / "var/eval_sources/custom").resolve()
POLICY = ROOT / "config/gate3_custom_authoring_policy.yaml"
SLOTS = ROOT / "config/gate3_custom_authoring_slots.yaml"
PROMPT = ROOT / "config/gate3_custom_generation_prompt.txt"
DRAFT_SCHEMA = ROOT / "schemas/gate3_generated_draft.schema.json"
FREEZE = ROOT / "config/gate3_generation_freeze.json"
GENERATOR = ROOT / "scripts/generate_gate3_private_candidates.py"


class PrivateAuthoringError(ValueError):
    """A fail-closed private authoring violation."""


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def resolve_private_path(relative: str | Path) -> Path:
    raw = Path(relative)
    if raw.is_absolute() or any(part in {"..", ""} for part in raw.parts):
        raise PrivateAuthoringError("private_path_traversal")
    current = PRIVATE_ROOT
    for part in raw.parts:
        current = current / part
        if current.is_symlink():
            raise PrivateAuthoringError("private_symlink_component")
    candidate = current.resolve()
    try:
        candidate.relative_to(PRIVATE_ROOT)
    except ValueError as exc:
        raise PrivateAuthoringError("private_path_escape") from exc
    if candidate.exists() and candidate.is_symlink():
        raise PrivateAuthoringError("private_symlink_destination")
    if str(candidate).startswith(str(ROOT / "corpus")):
        raise PrivateAuthoringError("corpus_destination_forbidden")
    if (
        candidate.exists()
        and candidate.is_file()
        and not str(candidate).startswith(str(PRIVATE_ROOT))
    ):
        raise PrivateAuthoringError("private_destination_forbidden")
    return candidate


def require_loopback(endpoint: str) -> None:
    from urllib.parse import urlparse

    parsed = urlparse(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise PrivateAuthoringError("non_loopback_generation_endpoint")
    try:
        socket.gethostbyname(parsed.hostname or "")
    except socket.gaierror as exc:
        raise PrivateAuthoringError("generation_endpoint_unresolvable") from exc


def load_freeze() -> dict[str, Any]:
    if not FREEZE.exists():
        raise PrivateAuthoringError("generation_freeze_missing")
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    if freeze.get("endpoint") != "http://127.0.0.1:11434":
        raise PrivateAuthoringError("generation_endpoint_mismatch")
    require_loopback(freeze["endpoint"])
    for key, path in (
        ("policy_sha256", POLICY),
        ("slot_sha256", SLOTS),
        ("prompt_sha256", PROMPT),
        ("output_schema_sha256", DRAFT_SCHEMA),
        ("generator_sha256", GENERATOR),
    ):
        if freeze.get(key) != file_sha256(path):
            raise PrivateAuthoringError(f"freeze_hash_mismatch:{key}")
    return freeze


def generation_authorized() -> bool:
    return (
        os.environ.get("NFR_ALLOW_PRIVATE_EVAL_GENERATION") == "true"
        and os.environ.get("NFR_GATE3_B_AUTHORIZED") == "true"
    )


def forbidden_output_keys(value: Any) -> set[str]:
    forbidden = {
        "answer",
        "expected_answer",
        "relevant_chunk",
        "qrel",
        "score",
        "threshold",
        "calibration",
        "holdout",
        "split",
        "source_id",
    }
    if not isinstance(value, dict):
        return set()
    return forbidden.intersection(value)
