"""Citation formatting.

Every citation carries its license. That is not decoration: the corpus mixes
proprietary owner material with BSD-licensed CMUdict, and an answer that quotes
CMUdict without attribution breaches its terms (see NOTICE).

The harness retrieval this replaces emitted a bare source filename with no license,
no offsets, and no chunk id, so no claim could be audited back to its origin.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .retrieval import RetrievedChunk


@dataclass
class Citation:
    chunk_id: str
    source_id: str
    source_title: str
    license: str
    license_url: str | None
    chunk_index: int | None
    chunk_total: int | None
    section_heading: str | None
    found_by: str

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    def render(self) -> str:
        location = ""
        if self.chunk_index is not None and self.chunk_total is not None:
            location = f" [{self.chunk_index + 1}/{self.chunk_total}]"
        heading = f" — {self.section_heading}" if self.section_heading else ""
        return f"{self.source_title}{location}{heading} ({self.license})"


def build_citation(chunk: RetrievedChunk) -> Citation:
    meta = chunk.metadata
    return Citation(
        chunk_id=chunk.chunk_id,
        source_id=str(meta.get("source_id", "unknown")),
        source_title=str(meta.get("source_title", "unknown")),
        license=str(meta.get("license", "UNKNOWN")),
        license_url=meta.get("license_url"),
        chunk_index=meta.get("chunk_index"),
        chunk_total=meta.get("chunk_total"),
        section_heading=meta.get("section_heading"),
        found_by=chunk.found_by,
    )


def build_citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    seen: set[str] = set()
    out: list[Citation] = []
    for chunk in chunks:
        citation = build_citation(chunk)
        if citation.chunk_id in seen:
            continue
        seen.add(citation.chunk_id)
        out.append(citation)
    return out


def required_attributions(citations: list[Citation]) -> list[str]:
    """Licenses in play that require attribution in any published output."""
    return sorted({c.license for c in citations if "BSD" in c.license or "CC" in c.license})
