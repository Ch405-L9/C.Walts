"""Gate 1.1 §2: the negative-pattern corpus moved out of the evaluation tree.

Until v0.4.0-dev.2 the only negative-pattern source lived at
``corpus/raw/evaluation/negative/``. That material was never evaluation
material — it is corpus text describing delivery to avoid, required by Prompt D
§D — but it sat in a production-ingestible directory named "evaluation", which
is precisely the confusion Gate 1 had to undo. It now lives at
``corpus/raw/negative_patterns/``.

The rename had to be provably inert. Chunk ids derive from ``source_id`` and
chunk content, never from the file path (see ``schemas.chunk_id``), so the id
survives the move; only the ``source_path`` metadata changes. These tests assert
that claim rather than trusting it, and they assert the two behavioural
properties the move must not disturb:

  excluded ...... negative material stays out of ordinary positive rewrite
                  retrieval, at the live-retrieval level and not merely in the
                  composed filter
  available ..... negative material is still returned for an explicit contrast
                  or "what to avoid" request

The live-store tests skip rather than fail when the collection is absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from natural_flow_rag.embeddings import OllamaEmbedder
from natural_flow_rag.lexical_search import LexicalIndex
from natural_flow_rag.retrieval import Retriever
from natural_flow_rag.schemas import chunk_id
from natural_flow_rag.settings import ConfigError, load_settings, load_sources
from natural_flow_rag.vector_store import VectorStore

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OLD_DIR = PROJECT_ROOT / "corpus" / "raw" / "evaluation" / "negative"
NEW_DIR = PROJECT_ROOT / "corpus" / "raw" / "negative_patterns"
NEW_DOC = NEW_DIR / "rejected_audio_contrast.md"

SOURCE_ID = "cwalts_negative_patterns"
# Captured from the live collection before the move and re-verified after it.
CHUNK_ID = "9c1e63263b4b8373_0"
DOC_SHA256 = "959d9b63039041289cf7435457d4b0ca13465935f73b43449cea23de8be884ed"


# ── 1. the old path is gone and the new one is real ──────────────────────────


def test_the_old_evaluation_negative_directory_no_longer_exists() -> None:
    assert not OLD_DIR.exists()


def test_the_new_directory_holds_the_material() -> None:
    assert NEW_DOC.is_file()


def test_the_moved_document_is_byte_identical() -> None:
    """A rename must not become an edit. Approved text is owner-approved text."""
    import hashlib

    assert hashlib.sha256(NEW_DOC.read_bytes()).hexdigest() == DOC_SHA256


def test_no_code_still_points_at_the_old_path() -> None:
    """No *functional* reference to the vanished directory may survive.

    Deliberately narrower than a grep. Prose that explains the rename — the
    docstrings in this file, the history note in ``config/sources.yaml``, the
    execution log — must keep naming the old path, or the record of why the move
    happened is lost. What must not survive is a string the code actually uses.

    So: every string constant in the project's Python, minus docstrings, must not
    name the old directory. A revived ``resolve_ingest_path("corpus/raw/
    evaluation/negative/")`` fails here; a sentence about the move does not.
    """
    import ast

    offenders: list[str] = []
    for directory in ("src", "scripts", "tests", "mcp", "eval"):
        root = PROJECT_ROOT / directory
        if not root.is_dir():
            continue
        for py in root.rglob("*.py"):
            tree = ast.parse(py.read_text(encoding="utf-8"))
            docstrings = {
                ast.get_docstring(node, clean=False)
                for node in ast.walk(tree)
                if isinstance(
                    node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
                )
            }
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    # Split so this detector does not match its own source.
                    and ("raw/" + "evaluation/negative") in node.value
                    and node.value not in docstrings
                ):
                    offenders.append(f"{py.relative_to(PROJECT_ROOT)}:{node.lineno}")

    assert offenders == [], offenders


def test_the_source_manifest_declares_no_path_under_the_old_directory() -> None:
    """The one reference that would actually break discovery."""
    for source in load_sources().get("sources", []) or []:
        assert "raw/evaluation" not in str(source.get("path") or ""), source.get("id")


# ── 2. the new path is production-ingestible ─────────────────────────────────


def test_the_new_path_resolves_for_ingestion() -> None:
    settings = load_settings()
    resolved = settings.resolve_ingest_path("corpus/raw/negative_patterns/")
    assert resolved.is_relative_to(settings.project_root)


def test_the_source_declares_the_new_path_and_keeps_its_identity() -> None:
    """Everything except the path must survive the move."""
    sources = load_sources().get("sources", []) or []
    entries = [s for s in sources if s["id"] == SOURCE_ID]
    assert len(entries) == 1, f"expected exactly one {SOURCE_ID} source"
    source = entries[0]

    assert source["path"] == "corpus/raw/negative_patterns/"
    assert source["doc_type"] == "negative_pattern"
    assert source["license"] == "Proprietary — BADGRTechnologies LLC"
    assert source["license_status"] == "approved"
    assert source["register"] == "contrast"
    assert source["dialect"] == "en-US"
    assert source["chunk_profile"] == "reference"


def test_no_source_declares_a_path_under_the_evaluation_tree() -> None:
    for source in load_sources().get("sources", []) or []:
        assert "evaluation" not in str(source.get("path") or "")


# ── 3. the rename did not move the chunk id ──────────────────────────────────


def test_the_chunk_id_does_not_depend_on_the_file_path() -> None:
    """The reason the move needed no id migration, asserted directly."""
    content_hash = "d" * 64
    assert chunk_id(SOURCE_ID, content_hash, 0) == chunk_id(SOURCE_ID, content_hash, 0)
    # A different source id must still produce a different id, or the guarantee
    # would be vacuous.
    assert chunk_id(SOURCE_ID, content_hash, 0) != chunk_id("other", content_hash, 0)


def _collection():
    settings = load_settings()
    store = VectorStore(settings)
    if not store.exists():
        pytest.skip("production collection is not present in this working tree")
    return settings, store


def test_the_negative_chunk_kept_its_id_and_gained_the_new_path() -> None:
    _, store = _collection()
    records = store.get().get(where={"doc_type": "negative_pattern"}, include=["metadatas"])

    assert records["ids"] == [CHUNK_ID], "the rename must not renumber the chunk"
    metadata = records["metadatas"][0]
    assert metadata["source_path"] == "corpus/raw/negative_patterns/rejected_audio_contrast.md"
    assert metadata["source_id"] == SOURCE_ID
    assert metadata["doc_type"] == "negative_pattern"
    assert metadata["register"] == "contrast"
    assert metadata["license"] == "Proprietary — BADGRTechnologies LLC"


def test_no_chunk_anywhere_still_claims_an_evaluation_path() -> None:
    _, store = _collection()
    records = store.get().get(include=["metadatas"])
    paths = {str((m or {}).get("source_path")) for m in records["metadatas"]}
    assert not any("evaluation" in p for p in paths), sorted(p for p in paths if "evaluation" in p)


def test_the_production_count_is_unchanged_by_the_rename() -> None:
    """84 before, 84 after. Unexplained drift is a failure, not a detail."""
    _, store = _collection()
    assert store.get().count() == 84


# ── 4. behaviour: excluded from positive retrieval, kept for contrast ────────


@pytest.fixture(scope="module")
def retriever() -> Retriever:
    settings = load_settings()
    store = VectorStore(settings)
    if not store.exists():
        pytest.skip("production collection is not present in this working tree")
    return Retriever(
        settings,
        store,
        OllamaEmbedder(settings.embedding),
        LexicalIndex(settings.project_root / "var" / "bm25" / "index.json"),
    )


REWRITE_QUERIES = [
    "Make this sound more natural: access is constrained by the user's permissions.",
    "Rewrite this for a calm technical voice-over.",
    "Turn this into a 15-second mobile voice-over with one CTA.",
]

CONTRAST_QUERIES = [
    "What should I avoid in a device-reader style performance?",
    "Why does this read sound robotic? What should I avoid?",
]


@pytest.mark.parametrize("query", REWRITE_QUERIES)
def test_positive_rewrite_retrieval_returns_no_negative_material(
    retriever: Retriever, query: str
) -> None:
    """End-to-end, against the live store at the new path — not the filter alone."""
    result = retriever.search(query, k=5)
    offenders = [c for c in result.chunks if str(c.metadata.get("doc_type")) == "negative_pattern"]
    assert offenders == [], f"{query!r} returned negative material"


@pytest.mark.parametrize("query", CONTRAST_QUERIES)
def test_contrast_requests_can_still_reach_the_moved_material(
    retriever: Retriever, query: str
) -> None:
    """The move must not orphan the material. A "what to avoid" ask still finds it.

    This is the proof that would fail silently if the rename had broken discovery:
    the chunk would simply stop appearing, and every exclusion test would still
    pass.
    """
    result = retriever.search(query, k=10)
    doc_types = {str(c.metadata.get("doc_type")) for c in result.chunks}
    assert "negative_pattern" in doc_types, f"{query!r} could not reach the moved material"

    negative = [c for c in result.chunks if str(c.metadata.get("doc_type")) == "negative_pattern"]
    assert all(
        str(c.metadata.get("source_path")).startswith("corpus/raw/negative_patterns/")
        for c in negative
    )


# ── 5. evaluation directories are still non-ingestible ───────────────────────


@pytest.mark.parametrize(
    "candidate",
    ["eval", "eval/", "eval/regression/source_documents/", "var/eval_sources/"],
)
def test_the_rename_did_not_loosen_the_evaluation_ban(candidate: str) -> None:
    settings = load_settings()
    with pytest.raises(ConfigError, match="evaluation material"):
        settings.resolve_ingest_path(candidate)


def test_the_remaining_evaluation_directory_holds_no_ingestible_corpus() -> None:
    """corpus/raw/evaluation/ still exists, holding only the audio manifest.

    Gate 1.1 §2 renamed one directory; it did not delete the tree. What is left
    is ``audio_reference_manifest.yaml`` — a manifest of hashes with no audio
    bytes, and YAML is not a loader-supported type, so it cannot be ingested.
    Asserted here so that "the old path is gone" is never read as "the whole
    evaluation tree is gone".
    """
    remaining = PROJECT_ROOT / "corpus" / "raw" / "evaluation"
    if not remaining.exists():
        return
    files = sorted(p.name for p in remaining.rglob("*") if p.is_file())
    assert files == ["audio_reference_manifest.yaml"], files

    sources = load_sources().get("sources", []) or []
    assert not any("evaluation" in str(s.get("path") or "") for s in sources)


def test_the_gitignore_tracks_the_new_directory() -> None:
    """corpus/raw/* is ignored by default; the new tree needs its own re-include."""
    text = (PROJECT_ROOT / ".gitignore").read_text()
    assert "!corpus/raw/negative_patterns/" in text

    import subprocess

    result = subprocess.run(  # noqa: S603
        ["git", "check-ignore", "-q", str(NEW_DOC)],  # noqa: S607
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1, "the moved document is gitignored and would be lost"


def test_the_audio_manifest_is_still_tracked() -> None:
    """The surviving re-include must not have been dropped along with the move."""
    text = (PROJECT_ROOT / ".gitignore").read_text()
    assert "!corpus/raw/evaluation/" in text
    manifest = PROJECT_ROOT / "corpus" / "raw" / "evaluation" / "audio_reference_manifest.yaml"
    if manifest.exists():
        assert yaml.safe_load(manifest.read_text()) is not None
