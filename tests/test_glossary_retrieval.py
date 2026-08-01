"""The rc.2 acceptance tests: a prosody probe must return a DEFINITION.

The rc.1 limitation these exist to close: `cwalts_evaluation_cases` was the only
approved document containing ToBI, H* and L-L%, so the exact-term test passed by
retrieving an evaluation prompt — the question — rather than an answer. Passing
because the probe is in the corpus is not retrieval working.

Every assertion here therefore checks three things together, because any one
alone can be satisfied by the wrong document:

  the term's OWN glossary entry is returned    not a passing mention elsewhere
  it is substantive                            not a heading with a sentence
  it cites an approved source                  traceable to the licence audit

These run against the live collection. They skip rather than fail when it is
absent, so a fresh clone does not report a false failure before ingestion.
"""

from __future__ import annotations

import pytest

from natural_flow_rag.embeddings import OllamaEmbedder
from natural_flow_rag.lexical_search import LexicalIndex
from natural_flow_rag.retrieval import Retriever
from natural_flow_rag.settings import load_settings
from natural_flow_rag.vector_store import VectorStore

GLOSSARY_SOURCE = "cwalts_prosody_glossary"
EVALUATION_SOURCE = "cwalts_evaluation_cases"

# Term, query, and the floor below which the entry is a mention rather than a
# definition. Floors are per-term because the entries differ in how much they
# genuinely have to say, not set to one number that flatters the shortest.
PROBES = [
    ("ToBI", "What is ToBI?", 900),
    ("H*", "What does the pitch accent `H*` mean?", 700),
    ("L-L%", "What does `L-L%` mean and what is it made of?", 800),
    ("break index", "What is a break index and what range does it use?", 900),
]


@pytest.fixture(scope="module")
def retriever():
    settings = load_settings()
    store = VectorStore(settings)
    if not store.exists():
        pytest.skip("collection not built; run scripts/ingest.py --commit first")
    try:
        store.count()
    except Exception as exc:  # noqa: BLE001 — an unavailable store is a skip
        pytest.skip(f"collection unavailable: {exc}")
    embedder = OllamaEmbedder(settings.embedding)
    try:
        embedder.probe()
    except Exception as exc:  # noqa: BLE001 — Ollama down is a skip, not a failure
        pytest.skip(f"Ollama unavailable: {exc}")
    lexical = LexicalIndex(settings.project_root / "var" / "bm25" / "index.json")
    return Retriever(settings, store, embedder, lexical)


def _ranked(retriever, query, k=5):
    return [c for c in retriever.search(query, k=k).chunks if not c.is_neighbor]


def _entry_for(chunks, term):
    return next(
        (
            c for c in chunks
            if str(c.metadata.get("section_heading", "")).strip() == term
            and str(c.metadata.get("source_id")) == GLOSSARY_SOURCE
        ),
        None,
    )


@pytest.mark.parametrize(("term", "query", "floor"), PROBES)
def test_probe_returns_that_term_s_own_definition(retriever, term, query, floor):
    entry = _entry_for(_ranked(retriever, query), term)
    assert entry is not None, (
        f"{query!r} returned no glossary entry headed {term!r}. A mention of the "
        f"term somewhere else in the corpus is not a definition of it."
    )
    assert len(entry.text) >= floor, (
        f"the {term!r} entry is {len(entry.text)} characters, below the {floor} "
        f"floor for a substantive definition"
    )


@pytest.mark.parametrize(("term", "query", "floor"), PROBES)
def test_the_definition_cites_an_approved_source(retriever, term, query, floor):
    entry = _entry_for(_ranked(retriever, query), term)
    assert entry is not None
    assert "**Grounded in:**" in entry.text, (
        f"the {term!r} entry names no source; every glossary entry must be "
        f"traceable to config/glossary_sources.yaml"
    )
    assert entry.metadata.get("license"), "chunk carries no licence metadata"
    assert entry.metadata.get("source_path"), "chunk carries no resolvable source path"


@pytest.mark.parametrize(("term", "query", "floor"), PROBES)
def test_an_evaluation_prompt_is_never_the_primary_result(retriever, term, query, floor):
    """The rc.1 failure mode, asserted directly.

    Evaluation cases are not banned from the results — they carry pass criteria
    other queries legitimately need. They must simply never LEAD for a
    definitional lookup, or the corpus is answering a question with the question.
    """
    ranked = _ranked(retriever, query)
    assert ranked, f"{query!r} returned nothing"
    primary = ranked[0]
    assert str(primary.metadata.get("source_id")) != EVALUATION_SOURCE, (
        f"{query!r} ranked an evaluation prompt first "
        f"({primary.metadata.get('section_heading')!r})"
    )
    assert str(primary.metadata.get("doc_type")) != "evaluation_case"


def test_the_glossary_leads_the_combined_probe(retriever):
    """EVAL-004's query, which is the one rc.1 passed for the wrong reason."""
    ranked = _ranked(retriever, "Explain the textual relevance of `ToBI`, `H*`, and `L-L%`.")
    assert ranked
    assert str(ranked[0].metadata.get("source_id")) == GLOSSARY_SOURCE


def test_exact_notation_survives_into_the_returned_text(retriever):
    """Dense retrieval alone loses these; the BM25 arm is what protects them."""
    for term in ("ToBI", "H*", "L-L%"):
        joined = " ".join(c.text for c in _ranked(retriever, term))
        assert term in joined, f"{term!r} did not appear literally in any ranked chunk"


def test_negative_material_stays_out_of_a_definitional_lookup(retriever):
    for _term, query, _floor in PROBES:
        types = {str(c.metadata.get("doc_type")) for c in _ranked(retriever, query)}
        assert "negative_pattern" not in types, f"{query!r} leaked negative material"
