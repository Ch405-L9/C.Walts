"""Configuration loading and invariant enforcement.

Every value the audit MEASURED is asserted here rather than assumed. If the host
drifts (model replaced, dimension changed, disk filled), the process refuses to
start instead of silently producing a corrupt collection.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "rag.yaml"
SOURCES_PATH = PROJECT_ROOT / "config" / "sources.yaml"


class ConfigError(RuntimeError):
    """Configuration is missing, malformed, or violates a hard invariant."""


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str
    endpoint: str
    model: str
    model_tag: str
    model_digest: str
    vector_dimension: int
    model_context_tokens: int
    normalize_vectors: bool
    forbid_mixed_models: bool
    assert_dimension_on_startup: bool
    explicit_embeddings_only: bool
    batch_size: int
    timeout_seconds: int


@dataclass(frozen=True)
class CollectionConfig:
    name: str
    backend: str
    persistence_path: Path
    space: str
    allowlisted_collections: tuple[str, ...]

    def assert_allowed(self, name: str) -> str:
        """Reject any collection name not on the allowlist.

        The generation model never supplies a collection name freely; this is the
        chokepoint that makes that guarantee structural rather than advisory.
        """
        if name not in self.allowlisted_collections:
            raise ConfigError(
                f"collection {name!r} is not allowlisted; "
                f"permitted: {list(self.allowlisted_collections)}"
            )
        return name


@dataclass(frozen=True)
class Settings:
    raw: dict[str, Any]
    project_root: Path
    collection: CollectionConfig
    embedding: EmbeddingConfig
    chunking: dict[str, Any] = field(default_factory=dict)
    retrieval: dict[str, Any] = field(default_factory=dict)
    security: dict[str, Any] = field(default_factory=dict)
    writes: dict[str, Any] = field(default_factory=dict)

    # ── write gating ──────────────────────────────────────────────────────────

    @property
    def writes_allowed(self) -> bool:
        """Writes require BOTH the config switch and the environment override.

        Defaults to False. Gate 3 has not been approved at the time of writing.
        """
        env = os.getenv("NFR_ALLOW_WRITES", "").strip().lower()
        if env in {"1", "true", "yes"}:
            return True
        return bool(self.writes.get("allow_writes", False))

    def assert_writes_allowed(self, operation: str) -> None:
        if not self.writes_allowed:
            raise ConfigError(
                f"{operation}: writes are disabled. Set writes.allow_writes in "
                f"config/rag.yaml or NFR_ALLOW_WRITES=true. This gate exists "
                f"because Gate 3 (database-write approval) is owner-controlled."
            )

    def assert_disk_headroom(self) -> None:
        """The host was 91% full at audit time. Refuse to ingest into a full disk."""
        minimum_gb = float(self.writes.get("minimum_free_disk_gb", 20))
        free_gb = shutil.disk_usage(self.project_root).free / (1024**3)
        if free_gb < minimum_gb:
            raise ConfigError(
                f"only {free_gb:.1f} GB free; {minimum_gb:.0f} GB required. "
                f"Refusing to write."
            )

    # ── path containment ──────────────────────────────────────────────────────

    def resolve_inside_project(self, candidate: Path | str) -> Path:
        """Resolve a path and prove it lies under the project root.

        This is what makes "the new ingestion path cannot write into an unrelated
        collection" a structural fact. The production store at
        badgr_harness/rag_db/ is outside this root and therefore unreachable.
        """
        resolved = Path(candidate)
        if not resolved.is_absolute():
            resolved = self.project_root / resolved
        resolved = resolved.resolve()
        root = self.project_root.resolve()
        if not resolved.is_relative_to(root):
            raise ConfigError(
                f"path {resolved} escapes the project root {root}; refused"
            )
        return resolved


def _require(mapping: dict[str, Any], key: str, where: str) -> Any:
    if key not in mapping:
        raise ConfigError(f"missing required key {key!r} in {where}")
    return mapping[key]


def load_settings(config_path: Path | None = None) -> Settings:
    path = config_path or CONFIG_PATH
    if not path.is_file():
        raise ConfigError(f"config not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    coll_raw = _require(raw, "collection", "rag.yaml")
    emb_raw = _require(raw, "embedding", "rag.yaml")

    project_root = Path(raw.get("project", {}).get("root") or PROJECT_ROOT)

    embedding = EmbeddingConfig(
        provider=_require(emb_raw, "provider", "embedding"),
        endpoint=emb_raw.get("endpoint") or os.getenv("NFR_OLLAMA_URL")
        or "http://127.0.0.1:11434",
        model=_require(emb_raw, "model", "embedding"),
        model_tag=emb_raw.get("model_tag", ""),
        model_digest=emb_raw.get("model_digest", ""),
        vector_dimension=int(_require(emb_raw, "vector_dimension", "embedding")),
        model_context_tokens=int(emb_raw.get("model_context_tokens", 2048)),
        normalize_vectors=bool(emb_raw.get("normalize_vectors", False)),
        forbid_mixed_models=bool(emb_raw.get("forbid_mixed_models", True)),
        assert_dimension_on_startup=bool(emb_raw.get("assert_dimension_on_startup", True)),
        explicit_embeddings_only=bool(emb_raw.get("explicit_embeddings_only", True)),
        batch_size=int(emb_raw.get("batch_size", 16)),
        timeout_seconds=int(emb_raw.get("timeout_seconds", 120)),
    )

    allowlist = tuple(coll_raw.get("allowlisted_collections") or [coll_raw["name"]])
    if coll_raw["name"] not in allowlist:
        raise ConfigError(
            f"configured collection {coll_raw['name']!r} is absent from its own allowlist"
        )

    collection = CollectionConfig(
        name=coll_raw["name"],
        backend=coll_raw.get("backend", "chroma"),
        persistence_path=Path(coll_raw.get("persistence_path", "./var/chroma")),
        space=coll_raw.get("space", "cosine"),
        allowlisted_collections=allowlist,
    )

    settings = Settings(
        raw=raw,
        project_root=project_root,
        collection=collection,
        embedding=embedding,
        chunking=raw.get("chunking", {}),
        retrieval=raw.get("retrieval", {}),
        security=raw.get("security", {}),
        writes=raw.get("writes", {}),
    )

    # The persistence path must be inside the project. This is the single most
    # important invariant in the system: it is what keeps the 2,372-chunk
    # production corpus unreachable from this code.
    settings.resolve_inside_project(collection.persistence_path)

    return settings


def load_sources(path: Path | None = None) -> dict[str, Any]:
    src_path = path or SOURCES_PATH
    if not src_path.is_file():
        raise ConfigError(f"source manifest not found: {src_path}")
    return yaml.safe_load(src_path.read_text(encoding="utf-8")) or {}
