"""Document loaders. Text extraction only — no normalization, no chunking."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SUPPORTED = {".txt", ".md", ".markdown", ".rst", ".dict", ".pdf"}


class LoaderError(RuntimeError):
    """A source file could not be read."""


@dataclass
class LoadedDocument:
    path: Path
    text: str
    raw_bytes: int


def load(path: Path) -> LoadedDocument:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise LoaderError(f"unsupported extension {suffix!r} for {path.name}")

    if suffix == ".pdf":
        text = _load_pdf(path)
    else:
        # CMUdict ships as latin-1; errors="replace" keeps a bad byte from
        # aborting an otherwise valid ingest, and the checksum still records it.
        text = path.read_text(encoding="utf-8", errors="replace")

    return LoadedDocument(path=path, text=text, raw_bytes=path.stat().st_size)


def _load_pdf(path: Path) -> str:
    try:
        import pdfplumber
    except ImportError as exc:
        raise LoaderError("pdfplumber is required for PDF sources") from exc

    with pdfplumber.open(path) as pdf:
        return "\n\n".join(page.extract_text() or "" for page in pdf.pages)


def discover(root: Path) -> list[Path]:
    """Every supported file under ``root``, sorted for deterministic ingestion."""
    if not root.exists():
        return []
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED and not p.name.startswith(".")
    )
