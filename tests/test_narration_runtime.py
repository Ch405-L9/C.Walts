"""Synthetic product tests for the context-aware narration runtime."""

from __future__ import annotations

from dataclasses import dataclass

from natural_flow_rag.retrieval import RetrievalResult, RetrievedChunk
from natural_flow_rag.runtime import NarrationRuntime

FIXTURES = {
    "children": 'Mia said, "Look at the puppy!" The comic rabbit giggled and jumped.',
    "horror": (
        "The corridor was dark. A whisper rose behind the locked door, and footsteps stopped."
    ),
    "geography": (
        "Geography explains how latitude shapes climate. The Andes rise along the western edge "
        "of South America."
    ),
    "technical": "Install the client, configure the API endpoint, and run the migration command.",
    "commercial": (
        "Discover the new plan today. Subscribe now for a free trial and order with one click."
    ),
    "reflective": "Looking back, I remember the quiet journey and the lessons it left with me.",
    "ambiguous": "The window stood open while the afternoon passed.",
}


def test_required_routes_are_distinct_and_deterministic() -> None:
    runtime = NarrationRuntime()
    plans = {name: runtime.plan(text) for name, text in FIXTURES.items()}

    assert plans["children"].content_profile["genre"] == "children"
    assert plans["children"].content_profile["content_mode"] == "dialogue"
    assert plans["horror"].content_profile["genre"] == "horror_suspense"
    assert plans["geography"].content_profile["domain"] == "educational"
    assert plans["geography"].content_profile["content_mode"] == "informational"
    assert plans["technical"].content_profile["domain"] == "technical"
    assert plans["technical"].content_profile["content_mode"] == "instructional"
    assert plans["commercial"].content_profile["domain"] == "commercial"
    assert plans["commercial"].content_profile["content_mode"] == "persuasive"
    assert plans["reflective"].content_profile["genre"] == "reflective"
    assert plans["reflective"].content_profile["content_mode"] == "reflective"
    assert plans["ambiguous"].content_profile["fallback_used"] is True
    assert plans["ambiguous"].delivery["voice_character_hint"] == "clear_neutral"
    assert plans["children"].delivery != plans["horror"].delivery
    assert plans["children"].to_dict() == NarrationRuntime().plan(FIXTURES["children"]).to_dict()


def test_source_text_is_preserved_and_segmented() -> None:
    text = FIXTURES["technical"]
    plan = NarrationRuntime().plan(text)
    assert plan.source_text == text
    assert plan.source_text_sha256
    assert plan.preservation == {
        "source_text_preserved": True,
        "rewrite_performed": False,
        "normalization_authorized": False,
    }
    assert len(plan.segments) == 1
    assert plan.segments[0].text == text


@dataclass
class FakeRetriever:
    result: RetrievalResult

    def search(self, query: str, k: int = 5, where: dict | None = None) -> RetrievalResult:
        return self.result


def _chunk(chunk_id: str, register: str, found_by: str = "hybrid") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text="Synthetic guidance only.",
        score=0.4,
        rank=1,
        found_by=found_by,
        dense_rank=1,
        lexical_rank=1,
        metadata={"register": register, "source_title": "synthetic fixture"},
    )


def _result(chunks: list[RetrievedChunk], lexical_error: str | None = None) -> RetrievalResult:
    return RetrievalResult(
        query="synthetic",
        chunks=chunks,
        dense_n=len(chunks),
        lexical_n=len(chunks),
        fused_n=len(chunks),
        reranked=False,
        latency_ms=1,
        lexical_error=lexical_error,
    )


def test_route_aware_retrieval_prefers_metadata_and_relaxes_safely() -> None:
    retriever = FakeRetriever(
        _result([_chunk("technical", "technical_explainer"), _chunk("general", "commercial")])
    )
    plan = NarrationRuntime(retriever).plan(FIXTURES["technical"], k=2)
    assert plan.retrieval_summary["route_filter_applied"] is True
    assert plan.retrieval_summary["route_filter_relaxed"] is True
    assert plan.retrieval_summary["retrieved_chunk_ids"][0] == "technical"


def test_lexical_degradation_is_visible() -> None:
    retriever = FakeRetriever(_result([_chunk("one", "technical_explainer")], "index unavailable"))
    plan = NarrationRuntime(retriever).plan(FIXTURES["technical"])
    assert plan.retrieval_summary["lexical_degraded"] is True
    assert plan.retrieval_summary["lexical_error_code"] == "index unavailable"


def test_educational_route_does_not_prefer_reflective_register() -> None:
    retriever = FakeRetriever(
        _result([_chunk("reflective", "reflective_narration"), _chunk("broad", "commercial")])
    )
    plan = NarrationRuntime(retriever).plan(FIXTURES["geography"], k=2)
    assert plan.retrieval_summary["retrieved_chunk_ids"] == ["reflective", "broad"]
    assert plan.retrieval_summary["route_filter_applied"] is False


def test_zero_retrieval_does_not_crash() -> None:
    plan = NarrationRuntime(FakeRetriever(_result([]))).plan(FIXTURES["ambiguous"])
    assert plan.retrieval_summary["retrieval_count"] == 0
    assert "broader_retrieval" in plan.fallbacks


def test_explicit_metadata_has_priority() -> None:
    plan = NarrationRuntime().plan(
        FIXTURES["ambiguous"],
        {"domain": "technical", "content_mode": "instructional", "register": "technical_explainer"},
    )
    assert plan.content_profile["domain"] == "technical"
    assert plan.content_profile["content_mode"] == "instructional"
    assert plan.content_profile["register"] == "technical_explainer"
    assert plan.content_profile["fallback_used"] is False


def test_runtime_does_not_reference_evaluation_material() -> None:
    plan = NarrationRuntime().plan(FIXTURES["children"])
    assert plan.retrieval_summary["retrieval_arm"] == "unavailable"
    assert "source_text" not in plan.retrieval_summary
