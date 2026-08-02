"""Negative material is retrievable only when the request asks what to avoid.

Prompt D states the rule twice — negative recordings may never be positive
retrieval evidence, and negative-pattern documents may be returned only for
"what to avoid" requests. This is that rule as a filter, not as advice.
"""

from natural_flow_rag.retrieval import Retriever
from natural_flow_rag.settings import load_settings


def _retriever() -> Retriever:
    settings = load_settings()
    return Retriever(settings, store=None, embedder=None, lexical=None)  # type: ignore[arg-type]


REWRITE_QUERIES = [
    "Make this sound more natural: access is constrained by the user's permissions.",
    "Rewrite this for a calm technical voice-over.",
    "Turn this into a 15-second mobile voice-over with one CTA.",
]

CONTRAST_QUERIES = [
    "Why does this read sound robotic?",
    "What should I avoid in a device-reader style performance?",
    "Compare the negative device-reader examples with the B. Lawson target.",
]


def _excluded_doc_types(where: dict | None) -> set[str]:
    """Every doc_type a composed filter refuses, at any nesting depth."""
    if not where:
        return set()
    if "$and" in where:
        out: set[str] = set()
        for clause in where["$and"]:
            out |= _excluded_doc_types(clause)
        return out
    condition = where.get("doc_type")
    if isinstance(condition, dict) and "$ne" in condition:
        return {str(condition["$ne"])}
    return set()


def test_rewrite_requests_exclude_negative_material():
    retriever = _retriever()
    for query in REWRITE_QUERIES:
        where, excluded = retriever._default_filter(query, None)
        assert excluded, query
        assert "negative_pattern" in _excluded_doc_types(where), query


def test_contrast_requests_keep_negative_material():
    retriever = _retriever()
    for query in CONTRAST_QUERIES:
        where, excluded = retriever._default_filter(query, None)
        assert not excluded, query
        assert "negative_pattern" not in _excluded_doc_types(where), query


def test_a_caller_filter_narrows_and_is_never_allowed_to_widen():
    """CHANGED at Gate 1, and the old behaviour was the defect.

    This previously asserted `where is supplied` — a caller-supplied filter
    replaced the project's own exclusions outright, so passing any filter at all
    silently re-admitted negative material, and would have re-admitted evaluation
    material too. Gate 1 requires that an explicit caller request cannot bypass
    the boundary, so the clauses are now intersected. The caller's filter is
    still honoured; it just cannot widen the result.
    """
    retriever = _retriever()
    supplied = {"doc_type": "style_rule"}
    where, excluded = retriever._default_filter("make this natural", supplied)

    assert excluded
    assert supplied in where["$and"]
    refused = _excluded_doc_types(where)
    assert "evaluation_case" in refused
    assert "negative_pattern" in refused


def test_the_hard_boundary_survives_a_contrast_request():
    """Contrast intent re-admits negative material. It never re-admits evaluation."""
    retriever = _retriever()
    for query in CONTRAST_QUERIES:
        where, _ = retriever._default_filter(query, {"doc_type": "negative_pattern"})
        assert "evaluation_case" in _excluded_doc_types(where), query


def test_policy_is_configured_not_hardcoded():
    settings = load_settings()
    assert settings.retrieval["exclude_doc_types_by_default"] == ["negative_pattern"]
    assert "avoid" in settings.retrieval["contrast_intent_patterns"]
