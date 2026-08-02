"""Gate 1: evaluation material is a test input and never production knowledge.

Until v0.4.0-dev.2 the C.Walts evaluation prompts were an ingested source. An
evaluation prompt states the question AND its own pass criterion, so retrieval
could answer an evaluation query by returning the query: EVAL-005, EVAL-006,
EVAL-007 and EVAL-009 each listed their own prompt as an acceptable marker, and
EVAL-010 listed EVAL-001's. A benchmark that can retrieve its own answer key
measures nothing.

Three independent locks now hold, and each is asserted here separately, because
any one of them could be loosened without the others noticing:

  ingestion ..... refuses doc_type evaluation_case, and refuses any source path
                  under eval/ or var/eval_sources/ before a file is discovered
  store ......... the production collection and the BM25 index contain zero
                  evaluation_case records
  retrieval ..... evaluation_case is filtered unconditionally, and a
                  caller-supplied filter is intersected with that ban, never
                  substituted for it

The live-store tests skip rather than fail when the collection is absent, so a
fresh clone does not report a false failure before ingestion.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from natural_flow_rag.embeddings import OllamaEmbedder
from natural_flow_rag.lexical_search import LexicalIndex
from natural_flow_rag.retrieval import Retriever
from natural_flow_rag.settings import (
    FORBIDDEN_INGEST_DOC_TYPES,
    FORBIDDEN_INGEST_PREFIXES,
    ConfigError,
    load_settings,
    load_sources,
)
from natural_flow_rag.vector_store import VectorStore

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGRESSION_DOC = PROJECT_ROOT / "eval" / "regression" / "source_documents" / "evaluation_prompts.md"
EVALUATION_REPORT = PROJECT_ROOT / "docs" / "evidence" / "evaluation-report.json"


# ── 1. source discovery excludes every evaluation directory ──────────────────


@pytest.mark.parametrize(
    "candidate",
    [
        "eval",
        "eval/",
        "eval/regression/source_documents/",
        "eval/calibration/",
        "eval/holdout/",
        "eval/ood/",
        "var/eval_sources/",
        "var/eval_sources/extracted/clinc150/",
    ],
)
def test_ingestion_refuses_every_evaluation_directory(candidate: str) -> None:
    settings = load_settings()
    with pytest.raises(ConfigError, match="evaluation material"):
        settings.resolve_ingest_path(candidate)


def test_production_source_paths_are_still_reachable() -> None:
    """The ban must be narrow: real corpus paths still resolve."""
    settings = load_settings()
    for path in [
        "corpus/raw/owner_examples/",
        "corpus/raw/glossary/",
        "corpus/raw/style_rules/",
        # Lives under corpus/raw/evaluation/ and is NOT evaluation material: it
        # is corpus text describing delivery to avoid, required by Prompt D.
        "corpus/raw/evaluation/negative/",
    ]:
        assert settings.resolve_ingest_path(path).is_relative_to(settings.project_root)


def test_the_regression_fixture_cannot_be_discovered_by_ingestion() -> None:
    settings = load_settings()
    assert REGRESSION_DOC.is_file(), "the regression fixture must still exist"
    with pytest.raises(ConfigError):
        settings.resolve_ingest_path(REGRESSION_DOC.parent)


# ── 2. ingestion rejects the doc_type itself ─────────────────────────────────


def test_ingestion_refuses_the_evaluation_case_doc_type() -> None:
    settings = load_settings()
    with pytest.raises(ConfigError, match="may not be ingested"):
        settings.assert_ingestible_doc_type("evaluation_case", "test")
    assert "evaluation_case" in FORBIDDEN_INGEST_DOC_TYPES
    assert "eval" in FORBIDDEN_INGEST_PREFIXES


def test_a_reintroduced_evaluation_source_is_refused_at_the_manifest() -> None:
    """The failure mode this closes: someone adds the source back next year."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "nfr_ingest_under_test", PROJECT_ROOT / "scripts" / "ingest.py"
    )
    assert spec and spec.loader
    ingest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ingest)

    manifest = {
        "sources": [
            {
                "id": "cwalts_evaluation_cases",
                "path": "eval/regression/source_documents/",
                "doc_type": "evaluation_case",
                "license": "Proprietary — BADGRTechnologies LLC",
                "license_status": "approved",
            }
        ]
    }
    with pytest.raises(ConfigError):
        ingest.approved_sources(manifest)


def test_no_live_source_declares_evaluation_material() -> None:
    manifest = load_sources()
    for source in manifest.get("sources", []) or []:
        assert source.get("doc_type") not in FORBIDDEN_INGEST_DOC_TYPES, source.get("id")
        assert not str(source.get("path", "")).startswith("eval/"), source.get("id")


# ── 3 & 4. the stores contain zero evaluation records ────────────────────────


def _collection():
    settings = load_settings()
    store = VectorStore(settings)
    if not store.exists():
        pytest.skip("production collection is not present in this working tree")
    return settings, store


def test_chroma_contains_no_evaluation_case_chunk() -> None:
    _, store = _collection()
    records = store.get().get(include=["metadatas"])
    offending = [
        chunk_id
        for chunk_id, meta in zip(records["ids"], records["metadatas"], strict=True)
        if str((meta or {}).get("doc_type")) == "evaluation_case"
    ]
    assert offending == []


def test_bm25_contains_no_evaluation_case_chunk() -> None:
    settings, store = _collection()
    index_path = settings.project_root / "var" / "bm25" / "index.json"
    if not index_path.is_file():
        pytest.skip("no lexical index in this working tree")
    lexical_ids = set(json.loads(index_path.read_text(encoding="utf-8"))["chunk_ids"])

    records = store.get().get(include=["metadatas"])
    by_id = dict(zip(records["ids"], records["metadatas"], strict=True))
    assert not [
        cid for cid in lexical_ids
        if str((by_id.get(cid) or {}).get("doc_type")) == "evaluation_case"
    ]
    # Parity: BM25 must describe exactly the collection, or the two arms
    # disagree about what exists.
    assert lexical_ids == set(records["ids"])


def test_no_chunk_still_points_at_the_moved_evaluation_document() -> None:
    _, store = _collection()
    records = store.get().get(include=["metadatas"])
    paths = {str((m or {}).get("source_path")) for m in records["metadatas"]}
    assert "corpus/raw/evaluation/cases/evaluation_prompts.md" not in paths
    assert not any(p.startswith("eval/") for p in paths)


# ── 5. retrieval cannot return evaluation material ───────────────────────────


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


EVALUATION_SHAPED_QUERIES = [
    "What is the minimum release threshold for this project?",
    "EVAL-005 number preservation pass criteria",
    "Explain the textual relevance of `ToBI`, `H*`, and `L-L%`.",
    "What are the pass criteria for the obligation preservation case?",
]


@pytest.mark.parametrize("query", EVALUATION_SHAPED_QUERIES)
def test_retrieval_never_returns_evaluation_material(retriever: Retriever, query: str) -> None:
    result = retriever.search(query, k=5)
    for chunk in result.chunks:
        assert str(chunk.metadata.get("doc_type")) != "evaluation_case"
        assert not str(chunk.metadata.get("source_path", "")).startswith("eval/")


@pytest.mark.parametrize("query", EVALUATION_SHAPED_QUERIES[:2])
def test_an_explicit_caller_filter_cannot_re_admit_evaluation_material(
    retriever: Retriever, query: str
) -> None:
    """The bypass §4 forbids: asking for it directly must still not return it."""
    result = retriever.search(query, k=5, where={"doc_type": "evaluation_case"})
    assert all(
        str(c.metadata.get("doc_type")) != "evaluation_case" for c in result.chunks
    )


def test_the_ban_is_configured_and_supersedes_the_old_demotion() -> None:
    settings = load_settings()
    assert settings.retrieval["forbid_doc_types_always"] == ["evaluation_case"]
    # The obsolete control must not still imply evaluation cases are expected in
    # production retrieval.
    assert "evaluation_case" not in (settings.retrieval.get("demote_doc_types") or [])


# ── 6-11. the evaluation result itself ───────────────────────────────────────


@pytest.fixture(scope="module")
def report() -> dict:
    if not EVALUATION_REPORT.is_file():
        pytest.skip("no evaluation report; run eval/run_evaluation.py")
    return json.loads(EVALUATION_REPORT.read_text(encoding="utf-8"))


def _case(report: dict, case_id: str) -> dict:
    return next(c for c in report["cases"] if c["id"] == case_id)


@pytest.mark.parametrize("case_id", ["EVAL-016", "EVAL-017", "EVAL-018",
                                     "EVAL-019", "EVAL-020"])
def test_prosody_probes_return_a_substantive_definition(report: dict, case_id: str) -> None:
    """The rc.1 defect these close: passing by retrieving the question."""
    case = _case(report, case_id)
    assert case["definition_pass"], case
    assert case["definition_chars"] >= 600
    assert case["definition_cites_source"]
    assert case.get("primary_doc_type") != "evaluation_case"


def test_the_combined_prosody_probe_answers_from_the_glossary(report: dict) -> None:
    """EVAL-004 asks for all three notations at once and has no single owning
    entry, so it is scored on the lexical arm plus the source of its primary
    result — which used to be the evaluation prompt itself."""
    case = _case(report, "EVAL-004")
    assert case["exact_term_pass"], case["exact_terms"]
    assert case["primary_doc_type"] != "evaluation_case"
    assert case["primary_source_id"] == "cwalts_prosody_glossary"
    assert case["forbidden_doc_types_returned"] == []


@pytest.mark.parametrize("case_id", ["EVAL-005", "EVAL-006", "EVAL-007"])
def test_preservation_cases_pass_on_production_material(report: dict, case_id: str) -> None:
    case = _case(report, case_id)
    assert case["useful_hit"], case
    assert not case["matched_marker"].startswith("EVAL-"), (
        f"{case_id} matched {case['matched_marker']!r} — an evaluation marker"
    )
    assert case["forbidden_doc_types_returned"] == []


def test_exact_term_retrieval_still_passes(report: dict) -> None:
    assert report["summary"]["exact_term_pass"]


def test_no_declared_assertion_failed(report: dict) -> None:
    assert report["summary"]["assertion_failures"] == 0, report["summary"]["failed_assertions"]


def test_no_evaluation_chunk_was_returned_anywhere(report: dict) -> None:
    assert report["summary"]["evaluation_case_chunks_returned"] == 0


def test_contamination_citations_and_preservation_hold(report: dict) -> None:
    summary = report["summary"]
    assert summary["negative_contamination"] == 0
    assert summary["citation_failures"] == 0
    assert summary["preservation_correct"] == summary["preservation_total"] == 10


def test_no_expectation_names_an_evaluation_prompt_as_an_answer() -> None:
    """The marker cleanup, asserted rather than trusted to review."""
    spec = yaml.safe_load(
        (PROJECT_ROOT / "eval" / "expectations.yaml").read_text(encoding="utf-8")
    )
    assert spec["global_forbid_primary_doc_types"] == ["evaluation_case"]
    for case in spec["cases"]:
        for marker in case.get("expect_any") or []:
            assert not str(marker).upper().startswith("EVAL-"), (
                f"{case['id']} accepts {marker!r}, an evaluation prompt, as an answer"
            )


# ── 12. the regression fixture stays usable ──────────────────────────────────


def test_the_regression_fixture_is_intact_and_readable() -> None:
    text = REGRESSION_DOC.read_text(encoding="utf-8")
    for case_id in [f"EVAL-{n:03d}" for n in range(1, 16)]:
        assert case_id in text, f"{case_id} lost in the move"
    assert "Minimum release threshold" in text
    # The pass criteria travelled with the prompts: each case keeps its **Pass**
    # block, which is the part that made this material unsafe to ingest.
    assert text.count("**Pass**") >= 12
    assert "**Prompt**" in text


def test_the_expectations_fixture_is_executable_and_never_ingested() -> None:
    spec = yaml.safe_load(
        (PROJECT_ROOT / "eval" / "expectations.yaml").read_text(encoding="utf-8")
    )
    assert spec["collection"] == "badgr_natural_flow_v1"
    assert len(spec["cases"]) >= 17
    assert len(spec["preservation_cases"]) == 10
    settings = load_settings()
    with pytest.raises(ConfigError):
        settings.resolve_ingest_path("eval/expectations.yaml")


# ── 14 & 15. snapshots and the Gate 0 protections ────────────────────────────


def test_snapshot_restore_recreates_chroma_and_bm25_consistently() -> None:
    """Verification opens the snapshot and interrogates it; a hash is not enough."""
    snapshots = sorted((PROJECT_ROOT / "var" / "snapshots").glob("*/snapshot.json"))
    if not snapshots:
        pytest.skip("no snapshot in this working tree")
    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            ".venv/bin/python", "scripts/store_snapshot.py",
            "--verify", str(snapshots[-1].parent),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["verified"]
    assert payload["chroma_bm25_parity"]
    assert payload["exact_term_hits"] > 0


def test_gate0_protections_are_still_intact() -> None:
    result = subprocess.run(  # noqa: S603
        [".venv/bin/python", "scripts/verify_gate0_integrity.py", "--verify"],  # noqa: S607
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
