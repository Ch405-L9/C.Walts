"""Chunk identity, metadata schema, and deterministic IDs.

The harness ingestion this replaces derived chunk IDs from ``sha256(filename)[:12]``
— the *filename*, never the content (audit E25). Ingestion then skipped any file
whose IDs already existed, so an edited source was never re-ingested. Its corpus
could drift silently from its sources forever.

Here the ID carries a content hash, so a one-byte edit produces a different ID and
the change is visible in a dry run.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

REQUIRED_METADATA_KEYS = (
    "source_id",
    "source_path",
    "source_title",
    "license",
    "source_checksum",
    "chunk_index",
    "chunk_total",
    "chunk_profile",
    "embedding_model",
    "embedding_dimension",
    "ingested_at",
    "tokenizer",
    "token_count",
)

OPTIONAL_METADATA_KEYS = (
    "license_url",
    "chunk_prev_id",
    "chunk_next_id",
    "section_heading",
    "doc_type",
    "dialect",
    "register",
    "approved_by",
)

# Only these keys may be used in a retrieval filter. Anything else is rejected,
# so a generation model cannot probe arbitrary metadata.
FILTERABLE_KEYS = ("doc_type", "dialect", "register", "chunk_profile", "source_id", "license")


class SchemaError(ValueError):
    """A chunk record violates the metadata contract."""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def chunk_id(source_id: str, content_hash: str, index: int) -> str:
    """Deterministic, content-sensitive chunk identifier.

    Format ``<16 hex>_<index>``; the hex derives from source id AND chunk content,
    so identical text under two source ids stays distinguishable, and edited text
    never silently reuses an old id.
    """
    digest = hashlib.sha256(f"{source_id}:{content_hash}".encode()).hexdigest()
    return f"{digest[:16]}_{index}"


@dataclass
class ChunkRecord:
    """One embeddable unit, complete with provenance."""

    id: str
    text: str
    source_id: str
    source_path: str
    source_title: str
    license: str
    source_checksum: str
    chunk_index: int
    chunk_total: int
    chunk_profile: str
    embedding_model: str
    embedding_dimension: int
    tokenizer: str
    token_count: int
    ingested_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    license_url: str | None = None
    chunk_prev_id: str | None = None
    chunk_next_id: str | None = None
    section_heading: str | None = None
    doc_type: str | None = None
    dialect: str | None = None
    register: str | None = None
    approved_by: str | None = None

    def metadata(self) -> dict[str, Any]:
        """Chroma metadata. Nulls are dropped — Chroma rejects None values."""
        raw = asdict(self)
        raw.pop("id", None)
        raw.pop("text", None)
        return {k: v for k, v in raw.items() if v is not None}

    def validate(self) -> None:
        meta = self.metadata()
        missing = [k for k in REQUIRED_METADATA_KEYS if k not in meta]
        if missing:
            raise SchemaError(f"chunk {self.id}: missing required metadata {missing}")
        if not str(self.license).strip():
            raise SchemaError(
                f"chunk {self.id}: empty license. Unlicensed material is quarantined, "
                f"never embedded — this is a commercial-use requirement."
            )
        if self.token_count <= 0:
            raise SchemaError(f"chunk {self.id}: non-positive token_count")


def link_neighbors(records: list[ChunkRecord]) -> list[ChunkRecord]:
    """Populate prev/next ids so neighbour expansion is possible at retrieval time.

    The harness corpus stored only an ordinal and a total, which is why neighbour
    expansion was impossible there without re-deriving ids by hand.
    """
    for position, record in enumerate(records):
        record.chunk_prev_id = records[position - 1].id if position > 0 else None
        record.chunk_next_id = (
            records[position + 1].id if position + 1 < len(records) else None
        )
    return records


def validate_filter(where: dict[str, Any] | None) -> dict[str, Any] | None:
    """Reject filters touching keys outside the allowlist."""
    if not where:
        return None
    bad = [k for k in where if k not in FILTERABLE_KEYS and not k.startswith("$")]
    if bad:
        raise SchemaError(
            f"filter keys {bad} are not permitted; allowed: {list(FILTERABLE_KEYS)}"
        )
    return where
