"""Shared fail-closed controls for local Gate 3 private authoring tooling."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
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
GENERATION_ACTIVATION = "gate3-b1-v3"
GENERATION_V3_AUTHORIZATION = "NFR_GATE3_B1_V3_AUTHORIZED"
FAILURE_AUDIT_RELATIVE = Path("audit/gate3_generation_failure.json")
GATE2_PUBLIC_MANIFEST = ROOT / "var/eval_sources/selected_public/gate2_public_candidates.json"
GATE2_PUBLIC_MANIFEST_SHA256 = "60d9ac4be6fc217cbfb42283c50ed86aab626dc4c4ef68dfc3f137a66721c39e"
POOL_RELATIVE = Path("drafts/gate3_private_draft_pool.json")
SEAL_RELATIVE = Path("drafts/gate3_private_draft_pool.seal.json")
AUDIT_RELATIVE = Path("audit/gate3_b1_generation_audit.json")
CONFLICT_RELATIVE = Path("audit/gate3_b1_conflict_graph.json")
READINESS_RELATIVE = Path("audit/gate3_b1_review_readiness.json")


class PrivateAuthoringError(ValueError):
    """A fail-closed private authoring violation."""


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def derive_request_seed(
    policy_id: str, slot_id: str, draft_role: str, attempt_number: int, base_seed: int = 17
) -> int:
    """Derive a stable request-local Ollama seed without mutating frozen options."""
    material = f"{policy_id}|{slot_id}|{draft_role}|{attempt_number}|{base_seed}"
    value = int.from_bytes(hashlib.sha256(material.encode("utf-8")).digest()[:4], "big")
    value &= 0x7FFFFFFF
    return value or 17


def derive_group_id(slot: dict[str, Any], policy: dict[str, Any]) -> str:
    """Derive the frozen group ID from metadata, never query text."""
    fields = (
        policy["policy_id"],
        slot["group_family"],
        slot["template_family_id"],
        slot["structural_family"],
        slot["task_family"],
    )
    return "G3G-" + hashlib.sha256("|".join(fields).encode("utf-8")).hexdigest()[:24]


def derive_template_fingerprint(
    slot: dict[str, Any], policy: dict[str, Any], prompt_sha256: str
) -> str:
    return canonical_sha256(
        {
            "policy_id": policy["policy_id"],
            "prompt_sha256": prompt_sha256,
            "scenario_family": slot["scenario_family"],
            "task_family": slot["task_family"],
            "structural_family": slot["structural_family"],
            "template_family_id": slot["template_family_id"],
        }
    )


def derive_draft_fingerprint(
    slot_id: str,
    draft_role: str,
    query_text: str,
    policy_sha256: str,
    generation_freeze_sha256: str,
) -> str:
    return canonical_sha256(
        {
            "slot_id": slot_id,
            "draft_role": draft_role,
            "query_text": query_text,
            "policy_sha256": policy_sha256,
            "generation_freeze_sha256": generation_freeze_sha256,
        }
    )


def verify_gate2_manifest_identity(path: Path = GATE2_PUBLIC_MANIFEST) -> str:
    """Hash the public manifest before any caller reads its JSON/query text."""
    actual = file_sha256(path)
    if actual != GATE2_PUBLIC_MANIFEST_SHA256:
        raise PrivateAuthoringError("gate2_manifest_sha256_mismatch")
    return actual


def current_git_head() -> str:
    git = shutil.which("git")
    if not git:
        raise PrivateAuthoringError("git_unavailable")
    result = subprocess.run(  # noqa: S603 — executable is resolved from PATH and args are fixed
        [git, "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise PrivateAuthoringError("git_head_unavailable")
    return result.stdout.strip()


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
    if freeze.get("generation_run_version") != GENERATION_ACTIVATION:
        raise PrivateAuthoringError("generation_run_version_mismatch")
    if freeze.get("model_blob_digest") != freeze.get("model_digest"):
        raise PrivateAuthoringError("model_blob_digest_binding_mismatch")
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


def generation_v2_authorized() -> bool:
    return generation_authorized() and os.environ.get(GENERATION_V3_AUTHORIZATION) == "true"


generation_v3_authorized = generation_v2_authorized


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Write a private artifact atomically, never exposing a partial canonical file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            raise PrivateAuthoringError("private_artifact_overwrite_refused")
        temporary_path.replace(path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def verify_model_identity(freeze: dict[str, Any]) -> dict[str, str]:
    """Verify the installed Ollama model without pulling or changing it."""
    import subprocess

    require_loopback(freeze["endpoint"])
    executable = shutil.which("ollama")
    if not executable:
        raise PrivateAuthoringError("ollama_missing")
    result = subprocess.run(  # noqa: S603
        [executable, "show", freeze["model"], "--modelfile"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise PrivateAuthoringError("model_identity_unavailable")
    digest = next(
        (
            line.split("sha256-", 1)[1].split()[0]
            for line in result.stdout.splitlines()
            if "sha256-" in line
        ),
        "",
    )
    actual = f"sha256-{digest}" if digest else ""
    if actual != freeze["model_digest"]:
        raise PrivateAuthoringError("model_digest_mismatch")
    tag_digest = freeze.get("model_tag_digest", "")
    if tag_digest:
        import urllib.request

        request = urllib.request.Request(  # noqa: S310
            freeze["endpoint"] + "/api/tags", headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            models = json.loads(response.read()).get("models", [])
        actual_tag = next(
            (item.get("digest", "") for item in models if item.get("name") == freeze["model"]),
            "",
        )
        if actual_tag != tag_digest:
            raise PrivateAuthoringError("model_tag_digest_mismatch")
    version = subprocess.run(  # noqa: S603
        [executable, "--version"], capture_output=True, text=True, check=False
    )
    return {
        "model": freeze["model"],
        "model_digest": actual,
        "model_blob_digest": actual,
        "model_tag_digest": tag_digest,
        "ollama_version": version.stdout.strip(),
    }


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
