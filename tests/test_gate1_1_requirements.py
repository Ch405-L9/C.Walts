"""Gate 1.1 §5: one test per required proof, plus the two that were missing.

§5 enumerates eleven properties Gate 1.1 must demonstrate. Nine were already
proved by the files written in §2, §3 and §4; this module states each of those
as a named requirement so a reviewer can walk the list without reverse-engineering
which assertion in which file covers which clause. Those tests delegate to the
same live sources rather than re-asserting weakly, so they cannot pass while the
underlying property is broken.

Two clauses were **not** genuinely covered, and are proved here for the first
time:

  §5.5  "caller filters cannot bypass mandatory exclusions" was asserted for
        evaluation_case against the live store, but for negative_pattern only at
        the filter-composition level. A composed filter that looks right and a
        retrieval that actually withholds the material are different claims.

  §5.9  "current restore verification checks both Chroma and BM25" had no test
        at all. test_rollback_docs.py asserts the *document* mentions BM25 and
        that the *tool* hard-codes no count — neither exercises the tool's
        behaviour. A verification tool that silently stopped checking the lexical
        arm would have passed every existing test while reintroducing precisely
        the rc.2 failure it exists to catch.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from natural_flow_rag.embeddings import OllamaEmbedder
from natural_flow_rag.lexical_search import LexicalIndex
from natural_flow_rag.retrieval import Retriever
from natural_flow_rag.settings import ConfigError, load_settings, load_sources
from natural_flow_rag.vector_store import VectorStore

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    """scripts/ is not a package; load by path, as the other test modules do."""
    import importlib.util

    path = PROJECT_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_{name}", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify_restore = _load_script("verify_restore")

ACTIVE_ROLLBACK = PROJECT_ROOT / "docs" / "rollback.md"
HISTORICAL_ROLLBACK = PROJECT_ROOT / "docs" / "history" / "rollback-rc2.md"
REGISTER = PROJECT_ROOT / "docs" / "known-limitations-v0.4.md"

POSITIVE_QUERY = "Rewrite this for a calm technical voice-over."
CONTRAST_QUERY = "What should I avoid in a device-reader style performance?"


def _store() -> tuple[object, VectorStore]:
    settings = load_settings()
    store = VectorStore(settings)
    if not store.exists():
        pytest.skip("production collection is not present in this working tree")
    return settings, store


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


# ── §5.1 no production path contains corpus/raw/evaluation/ ──────────────────


def test_r01_no_stored_chunk_declares_a_path_under_the_evaluation_tree() -> None:
    _, store = _store()
    records = store.get().get(include=["metadatas"])
    offenders = sorted(
        {
            str((m or {}).get("source_path"))
            for m in records["metadatas"]
            if "corpus/raw/evaluation/" in str((m or {}).get("source_path"))
        }
    )
    assert offenders == []


def test_r01_no_configured_source_declares_a_path_under_the_evaluation_tree() -> None:
    offenders = [
        s["id"]
        for s in (load_sources().get("sources", []) or [])
        if "corpus/raw/evaluation/" in str(s.get("path") or "")
    ]
    assert offenders == []


# ── §5.2 evaluation directories are excluded from ingestion ──────────────────


@pytest.mark.parametrize(
    "candidate",
    [
        "eval",
        "eval/",
        "eval/regression/source_documents/",
        "eval/calibration/",
        "eval/holdout/",
        "var/eval_sources/",
        "var/eval_sources/extracted/clinc150/",
    ],
)
def test_r02_ingestion_refuses_every_evaluation_directory(candidate: str) -> None:
    settings = load_settings()
    with pytest.raises(ConfigError, match="evaluation material"):
        settings.resolve_ingest_path(candidate)


# ── §5.3 negative-pattern material remains production corpus ─────────────────


def test_r03_the_negative_source_is_still_an_approved_production_source() -> None:
    sources = load_sources().get("sources", []) or []
    entry = next(s for s in sources if s["id"] == "cwalts_negative_patterns")
    assert entry["license_status"] == "approved"
    assert entry["doc_type"] == "negative_pattern"
    assert entry["path"] == "corpus/raw/negative_patterns/"
    assert load_settings().resolve_ingest_path(entry["path"])


def test_r03_the_negative_chunk_is_present_in_both_arms() -> None:
    """Production corpus means indexed by both arms, not merely configured."""
    _, store = _store()
    records = store.get().get(where={"doc_type": "negative_pattern"}, include=["metadatas"])
    assert records["ids"], "no negative_pattern chunk in the collection"

    index = json.loads(
        (PROJECT_ROOT / "var" / "bm25" / "index.json").read_text(encoding="utf-8")
    )
    for chunk_id in records["ids"]:
        assert chunk_id in set(index["chunk_ids"]), f"{chunk_id} is absent from BM25"


# ── §5.4 default positive requests exclude negative patterns ─────────────────


@pytest.mark.parametrize(
    "query",
    [
        POSITIVE_QUERY,
        "Make this sound more natural: access is constrained by the user's permissions.",
        "Turn this into a 15-second mobile voice-over with one CTA.",
    ],
)
def test_r04_a_default_positive_request_returns_no_negative_material(
    retriever: Retriever, query: str
) -> None:
    result = retriever.search(query, k=5)
    assert [c for c in result.chunks if str(c.metadata.get("doc_type")) == "negative_pattern"] == []


# ── §5.5 caller filters cannot bypass mandatory exclusions ───────────────────
#
# NEW. Previously proved for evaluation_case against the live store, and for
# negative_pattern only at the filter-composition level.


def test_r05_an_explicit_negative_filter_on_a_positive_request_returns_none(
    retriever: Retriever,
) -> None:
    """Asking for the excluded material by name must not produce it.

    The dense arm's filter becomes an empty intersection, but BM25 cannot read
    metadata and neighbour expansion runs afterwards, so material can still reach
    the fused list. The exclusion is re-applied after fusion and after expansion
    for exactly this reason. What must hold is the outcome, not the mechanism:
    no negative_pattern chunk is returned.
    """
    result = retriever.search(POSITIVE_QUERY, k=5, where={"doc_type": "negative_pattern"})
    leaked = [c for c in result.chunks if str(c.metadata.get("doc_type")) == "negative_pattern"]
    assert leaked == [], f"a caller filter re-admitted {len(leaked)} negative chunk(s)"


def test_r05_an_explicit_evaluation_filter_returns_none(retriever: Retriever) -> None:
    result = retriever.search(POSITIVE_QUERY, k=5, where={"doc_type": "evaluation_case"})
    assert [c for c in result.chunks if str(c.metadata.get("doc_type")) == "evaluation_case"] == []


def test_r05_the_composed_filter_intersects_rather_than_replaces() -> None:
    """The defect Gate 1 fixed: a caller filter used to be returned untouched."""
    settings = load_settings()
    retriever = Retriever(settings, store=None, embedder=None, lexical=None)  # type: ignore[arg-type]
    supplied = {"doc_type": "style_rule"}
    where, _ = retriever._default_filter(POSITIVE_QUERY, supplied)
    assert where != supplied, "the caller filter replaced the project's exclusions"
    assert "$and" in where and supplied in where["$and"]


# ── §5.6 contrast requests can retrieve negative patterns ────────────────────


@pytest.mark.parametrize(
    "query",
    [CONTRAST_QUERY, "Why does this read sound robotic? What should I avoid?"],
)
def test_r06_a_contrast_request_reaches_the_negative_material(
    retriever: Retriever, query: str
) -> None:
    result = retriever.search(query, k=10)
    negative = [c for c in result.chunks if str(c.metadata.get("doc_type")) == "negative_pattern"]
    assert negative, "contrast intent could not reach the negative material"
    assert all(
        str(c.metadata.get("source_path")).startswith("corpus/raw/negative_patterns/")
        for c in negative
    )


# ── §5.7 evaluation_case remains zero ────────────────────────────────────────


def test_r07_evaluation_case_is_zero_in_chroma_by_two_independent_surfaces() -> None:
    _, store = _store()
    collection = store.get()
    records = collection.get(include=["metadatas"])
    by_scan = sum(
        1 for m in records["metadatas"] if str((m or {}).get("doc_type")) == "evaluation_case"
    )
    by_filter = len(collection.get(where={"doc_type": "evaluation_case"})["ids"])
    assert by_scan == 0
    assert by_filter == 0


def test_r07_evaluation_case_is_zero_in_bm25() -> None:
    _, store = _store()
    records = store.get().get(include=["metadatas"])
    forbidden = {
        chunk_id
        for chunk_id, m in zip(records["ids"], records["metadatas"], strict=True)
        if str((m or {}).get("doc_type")) == "evaluation_case"
    }
    index = json.loads(
        (PROJECT_ROOT / "var" / "bm25" / "index.json").read_text(encoding="utf-8")
    )
    assert forbidden & set(index["chunk_ids"]) == set()


# ── §5.8 active rollback instructions carry no frozen count ──────────────────


def test_r08_the_active_rollback_document_states_no_collection_count() -> None:
    """Every count this collection has held, and any other bare 2-4 digit number.

    Deliberately broader than the four known counts: a number nobody recognises
    is exactly how the next stale count arrives.
    """
    import re

    text = ACTIVE_ROLLBACK.read_text(encoding="utf-8")
    text = re.sub(r"§\d+(\.\d+)*", " ", text)
    text = re.sub(r"^#+ .*$", " ", text, flags=re.MULTILINE)
    numbers = {int(m) for m in re.findall(r"(?<![\w.\-/])(\d{2,4})(?![\w.\-/%])", text)}
    assert numbers & {48, 84, 97, 101} == set(), f"frozen counts present: {sorted(numbers)}"


def test_r08_the_active_document_derives_its_expectation_instead() -> None:
    text = ACTIVE_ROLLBACK.read_text(encoding="utf-8")
    assert "--expect-from-sources" in text
    assert "--expect-from-snapshot" in text


# ── §5.9 restore verification checks BOTH Chroma and BM25 ────────────────────
#
# NEW. Nothing previously exercised the tool's behaviour.


def test_r09_the_verification_report_covers_both_stores() -> None:
    expected_ids, expected, provenance = verify_restore.expected_from_sources()
    report = verify_restore.verify(expected_ids, expected, provenance)

    assert report["production_count"] == expected
    assert report["bm25_chunk_ids"] == expected
    assert report["chroma_bm25_parity"] is True
    assert report["verified"] is True, report["failures"]


def test_r09_verification_fails_when_the_lexical_index_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Chroma-only restore must be reported as incomplete, not as success.

    This is the rc.2 failure exactly: the vector store is fine, the lexical arm
    is not, and retrieval keeps answering. Redirecting the module's project root
    at a temporary directory makes the BM25 index unreachable without touching
    the real one.
    """
    # Derive first: expected_from_sources() also resolves through PROJECT_ROOT.
    expected_ids, expected, provenance = verify_restore.expected_from_sources()
    monkeypatch.setattr(verify_restore, "PROJECT_ROOT", tmp_path)
    report = verify_restore.verify(expected_ids, expected, provenance)

    assert report["verified"] is False
    assert any("bm25" in f.lower() for f in report["failures"]), report["failures"]


def test_r09_verification_fails_when_the_two_arms_disagree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Desynchronised arms must fail even though both stores exist and open."""
    real = json.loads(
        (PROJECT_ROOT / "var" / "bm25" / "index.json").read_text(encoding="utf-8")
    )
    doctored = dict(real)
    doctored["chunk_ids"] = real["chunk_ids"][:-1]  # drop one, as a stale index would
    target = tmp_path / "var" / "bm25" / "index.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(doctored), encoding="utf-8")

    # Derive first: expected_from_sources() also resolves through PROJECT_ROOT.
    expected_ids, expected, provenance = verify_restore.expected_from_sources()
    monkeypatch.setattr(verify_restore, "PROJECT_ROOT", tmp_path)
    report = verify_restore.verify(expected_ids, expected, provenance)

    assert report["verified"] is False
    assert report["chroma_bm25_parity"] is False
    assert any("id sets differ" in f for f in report["failures"]), report["failures"]


def test_r09_verification_fails_on_a_stale_expected_count() -> None:
    """The derived expectation must actually be compared, not merely reported."""
    expected_ids, expected, provenance = verify_restore.expected_from_sources()
    report = verify_restore.verify(None, expected + 17, f"{provenance} (deliberately wrong)")
    assert report["verified"] is False
    assert any("expected" in f for f in report["failures"]), report["failures"]


def test_r09_the_verification_also_covers_the_other_required_checks() -> None:
    expected_ids, expected, provenance = verify_restore.expected_from_sources()
    report = verify_restore.verify(expected_ids, expected, provenance)
    assert report["evaluation_case_by_metadata"] == 0
    assert report["evaluation_case_by_where_filter"] == 0
    assert report["feedback_collection"] == "badgr_natural_flow_feedback_v1"
    assert report["feedback_count"] is not None
    assert report["exact_term_hits"] > 0
    assert report["retrieval_probe_hits"] > 0
    assert report["badgr_harness_store_md5"] == verify_restore.HARNESS_MD5


# ── §5.10 historical rollback evidence remains preserved ─────────────────────


def test_r10_the_historical_document_exists_and_is_marked_historical() -> None:
    assert HISTORICAL_ROLLBACK.is_file()
    head = HISTORICAL_ROLLBACK.read_text(encoding="utf-8")[:1500]
    assert "HISTORICAL RECORD" in head
    assert "not a current-state manifest" in head


def test_r10_the_measured_failure_evidence_survives_verbatim() -> None:
    """48/97 and the DEGRADED finding are the reason the active procedure exists."""
    text = HISTORICAL_ROLLBACK.read_text(encoding="utf-8")
    assert "48" in text
    assert "97" in text
    assert "DEGRADED" in text
    assert "lexical index" in text


def test_r10_the_historical_evidence_is_classified_in_the_register() -> None:
    text = REGISTER.read_text(encoding="utf-8")
    assert "accepted historical evidence" in text
    assert "accepted historical record" in text


# ── §5.11 EVAL-009 is registered, blocking calibration but not Gate 2 ────────


def _register_entry(entry_id: str) -> dict:
    import re

    text = REGISTER.read_text(encoding="utf-8")
    for block in re.findall(r"```yaml\n(.*?)```", text, re.DOTALL):
        parsed = yaml.safe_load(block)
        if isinstance(parsed, dict) and parsed.get("id") == entry_id:
            return parsed
    raise AssertionError(f"{entry_id} is absent from the register")


def test_r11_eval_009_blocks_calibration_but_not_gate_2() -> None:
    """The distinction §5 names explicitly, asserted as one statement."""
    entry = _register_entry("CW-LIM-009-DENSE-COVERAGE")
    assert entry["blocks_threshold_calibration"] is True
    assert entry["blocks_gate2"] is False


def test_r11_eval_009_is_registered_as_a_deferred_medium_release_blocker() -> None:
    entry = _register_entry("CW-LIM-009-DENSE-COVERAGE")
    assert entry["status"] == "deferred"
    assert entry["severity"] == "medium"
    assert entry["blocks_release_candidate"] is True


def test_r11_the_registered_limitation_matches_the_live_evaluation_result() -> None:
    """The register must describe the case that actually runs, not a stale one.

    If EVAL-009 is ever retuned so that more than one chunk carries it, this
    fails and the limitation has to be re-measured rather than left asserting a
    condition that no longer holds.
    """
    expectations = yaml.safe_load(
        (PROJECT_ROOT / "eval" / "expectations.yaml").read_text(encoding="utf-8")
    )
    case = next(c for c in expectations["cases"] if c["id"] == "EVAL-009")

    _, store = _store()
    records = store.get().get(include=["metadatas", "documents"])
    supporting = set()
    for chunk_id, meta, doc in zip(
        records["ids"], records["metadatas"], records["documents"], strict=True
    ):
        if str((meta or {}).get("doc_type")) != "approved_example":
            continue
        haystack = f"{doc}\n{(meta or {}).get('section_heading', '')}".lower()
        if any(marker.lower() in haystack for marker in case["expect_any"]):
            supporting.add(chunk_id)
    assert len(supporting) == 1, (
        f"EVAL-009 now has {len(supporting)} supporting approved_example chunks; "
        f"CW-LIM-009-DENSE-COVERAGE must be re-measured or closed"
    )
