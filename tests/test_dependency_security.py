from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import verify_dependency_exceptions as verifier

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "vulnerability_exceptions.json"


def test_exception_is_exactly_the_chroma_advisory() -> None:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert len(data["exceptions"]) == 1
    entry = data["exceptions"][0]
    assert entry["advisory_id"] == "PYSEC-2026-311"
    assert entry["aliases"] == ["CVE-2026-45829", "GHSA-f4j7-r4q5-qw2c"]
    assert entry["package"] == "chromadb"
    assert entry["exact_package_version"] == "1.5.8"
    assert entry["automatic_version_carryforward"] is False


def test_exception_verifier_passes_current_boundary() -> None:
    result = verifier.verify()
    assert result["verdict"] == "pass"
    assert result["mutation_performed"] is False
    assert result["boundary"]["checks"] == {
        "persistent_client": True,
        "containment_check": True,
        "explicit_get_embedding_function": True,
        "explicit_query_embeddings": True,
        "no_text_query_api": True,
        "explicit_write_embeddings": True,
        "no_network_client": True,
    }


def test_wrong_chroma_version_invalidates_exception() -> None:
    with pytest.raises(verifier.ExceptionVerificationError, match="version_mismatch"):
        verifier.verify(installed_version="1.5.9")


def test_mcp_advisories_cannot_be_added_as_exceptions(tmp_path: Path) -> None:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    data["exceptions"][0]["advisory_id"] = "PYSEC-2026-3481"
    path = tmp_path / "exceptions.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(verifier.ExceptionVerificationError):
        verifier.verify(config_path=path)


def test_unknown_advisory_is_rejected(tmp_path: Path) -> None:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    data["exceptions"][0]["advisory_id"] = "PYSEC-UNKNOWN"
    path = tmp_path / "exceptions.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(verifier.ExceptionVerificationError):
        verifier.verify(config_path=path)


def _boundary_root(tmp_path: Path, source: str) -> Path:
    root = tmp_path / "project"
    (root / "src" / "natural_flow_rag").mkdir(parents=True)
    (root / "mcp").mkdir()
    (root / "scripts").mkdir()
    (root / "config").mkdir()
    (root / "src" / "natural_flow_rag" / "vector_store.py").write_text(source, encoding="utf-8")
    (root / "config" / "rag.yaml").write_text(
        "collection:\n  persistence_path: ./var/chroma\n", encoding="utf-8"
    )
    return root


def _valid_vector_store_source() -> str:
    return """
import chromadb
class V:
    def f(self, settings, embedding, collection):
        path = settings.resolve_inside_project(settings.collection.persistence_path)
        client = chromadb.PersistentClient(path=str(path))
        ef = object()
        c = client.get_collection(name='x', embedding_function=ef)
        c.query(query_embeddings=[embedding])
        c.upsert(ids=['x'], embeddings=[embedding], documents=['x'], metadatas=[{}])
"""


def test_http_client_introduction_is_detected(tmp_path: Path) -> None:
    root = _boundary_root(tmp_path, _valid_vector_store_source())
    (root / "scripts" / "bad.py").write_text("import chromadb\nchromadb.HttpClient()\n")
    with pytest.raises(
        verifier.ExceptionVerificationError,
        match="active_chroma_boundary_offender",
    ):
        verifier.verify_chroma_boundary(root)


def test_async_client_and_server_paths_are_detected(tmp_path: Path) -> None:
    root = _boundary_root(tmp_path, _valid_vector_store_source())
    (root / "mcp" / "bad.py").write_text(
        "from chromadb import AsyncHttpClient\nfrom fastapi import FastAPI\n"
    )
    with pytest.raises(
        verifier.ExceptionVerificationError,
        match="active_chroma_boundary_offender",
    ):
        verifier.verify_chroma_boundary(root)


def test_text_query_api_is_detected(tmp_path: Path) -> None:
    root = _boundary_root(tmp_path, _valid_vector_store_source())
    (root / "scripts" / "bad.py").write_text("collection.query(query_texts=['x'])\n")
    with pytest.raises(
        verifier.ExceptionVerificationError,
        match="active_chroma_boundary_offender",
    ):
        verifier.verify_chroma_boundary(root)


def test_missing_explicit_embedding_function_fails(tmp_path: Path) -> None:
    source = _valid_vector_store_source().replace("name='x', embedding_function=ef", "name='x'")
    root = _boundary_root(tmp_path, source)
    with pytest.raises(verifier.ExceptionVerificationError, match="boundary_incomplete"):
        verifier.verify_chroma_boundary(root)


def test_embedding_function_must_be_on_the_same_get_collection_call(tmp_path: Path) -> None:
    source = (
        _valid_vector_store_source()
        .replace("name='x', embedding_function=ef", "name='x'")
        .replace(
            "c.query(query_embeddings=[embedding])",
            "client.create_collection(name='later', embedding_function=ef)\n"
            "        c.query(query_embeddings=[embedding])",
        )
    )
    root = _boundary_root(tmp_path, source)
    with pytest.raises(verifier.ExceptionVerificationError, match="boundary_incomplete"):
        verifier.verify_chroma_boundary(root)


def test_comments_and_dead_strings_do_not_satisfy_call_site_controls(tmp_path: Path) -> None:
    source = (
        _valid_vector_store_source()
        .replace("name='x', embedding_function=ef", "name='x'")
        .replace(
            "c.query(query_embeddings=[embedding])",
            "note = 'query_embeddings= and embedding_function= are required'\n        c.query()",
        )
    )
    root = _boundary_root(tmp_path, source)
    with pytest.raises(verifier.ExceptionVerificationError, match="boundary_incomplete"):
        verifier.verify_chroma_boundary(root)


def test_query_texts_on_the_call_fails(tmp_path: Path) -> None:
    source = _valid_vector_store_source().replace(
        "query_embeddings=[embedding]", "query_texts=['x']"
    )
    root = _boundary_root(tmp_path, source)
    with pytest.raises(verifier.ExceptionVerificationError):
        verifier.verify_chroma_boundary(root)


def test_upsert_requires_embeddings_on_the_same_call(tmp_path: Path) -> None:
    source = _valid_vector_store_source().replace("ids=['x'], embeddings=[embedding]", "ids=['x']")
    root = _boundary_root(tmp_path, source)
    with pytest.raises(verifier.ExceptionVerificationError, match="boundary_incomplete"):
        verifier.verify_chroma_boundary(root)


def test_persistent_client_requires_containment_before_construction(tmp_path: Path) -> None:
    source = _valid_vector_store_source().replace(
        "path = settings.resolve_inside_project(settings.collection.persistence_path)\n        ", ""
    )
    root = _boundary_root(tmp_path, source)
    with pytest.raises(verifier.ExceptionVerificationError, match="boundary_incomplete"):
        verifier.verify_chroma_boundary(root)


def test_persistent_client_is_required(tmp_path: Path) -> None:
    source = _valid_vector_store_source().replace(
        "chromadb.PersistentClient", "chromadb.HttpClient"
    )
    root = _boundary_root(tmp_path, source)
    with pytest.raises(verifier.ExceptionVerificationError):
        verifier.verify_chroma_boundary(root)


def test_mcp_findings_are_not_in_exception_registry() -> None:
    text = CONFIG.read_text(encoding="utf-8")
    assert "PYSEC-2026-3481" not in text
    assert "PYSEC-2026-3482" not in text
    assert "PYSEC-2026-3483" not in text


def test_verifier_is_read_only() -> None:
    before = sorted(str(p) for p in (ROOT / "config").iterdir())
    result = verifier.verify()
    after = sorted(str(p) for p in (ROOT / "config").iterdir())
    assert result["mutation_performed"] is False
    assert before == after
