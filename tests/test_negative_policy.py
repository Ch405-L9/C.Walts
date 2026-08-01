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


def test_rewrite_requests_exclude_negative_material():
    retriever = _retriever()
    for query in REWRITE_QUERIES:
        where, excluded = retriever._default_filter(query, None)
        assert excluded, query
        assert where == {"doc_type": {"$ne": "negative_pattern"}}


def test_contrast_requests_keep_negative_material():
    retriever = _retriever()
    for query in CONTRAST_QUERIES:
        where, excluded = retriever._default_filter(query, None)
        assert not excluded, query
        assert where is None


def test_an_explicit_caller_filter_is_never_overridden():
    retriever = _retriever()
    supplied = {"doc_type": "style_rule"}
    where, excluded = retriever._default_filter("make this natural", supplied)
    assert where is supplied
    assert not excluded


def test_policy_is_configured_not_hardcoded():
    settings = load_settings()
    assert settings.retrieval["exclude_doc_types_by_default"] == ["negative_pattern"]
    assert "avoid" in settings.retrieval["contrast_intent_patterns"]
