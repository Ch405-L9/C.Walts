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

LISTENING_FIXTURES = {
    "horror": (
        "The hallway was darker than Marcus remembered. He stopped at the foot\n"
        "of the stairs and listened, certain that something had moved above him.\n"
        "The old house answered with a single slow creak.\n\n"
        "He told himself it was only the wood settling in the cold. Then, from\n"
        "the second floor, three soft knocks sounded against the bedroom door.\n"
        "Marcus had not told anyone he was home."
    ),
    "children": (
        "Lena tightened the red scarf around her neck and climbed onto the\n"
        "little wooden boat. Her dog, Pepper, jumped in beside her and nearly\n"
        "sent both of them tumbling into the river.\n\n"
        "'Careful!' Lena laughed. Ahead, beyond the bend, the old map showed a\n"
        "tiny island marked with a golden star. Whatever was waiting there, Lena\n"
        "was determined to find it before sunset."
    ),
    "technical": (
        "A lithium-ion battery stores energy by moving lithium ions between two\n"
        "electrodes. During charging, the ions travel from the positive electrode\n"
        "through the electrolyte and enter the negative electrode.\n\n"
        "When the battery supplies power, that process reverses. The ions move\n"
        "back toward the positive electrode while electrons flow through the\n"
        "external circuit, providing electrical energy to the connected device."
    ),
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


def test_listening_fixtures_reach_existing_content_profiles_without_metadata() -> None:
    runtime = NarrationRuntime()
    horror = runtime.plan(LISTENING_FIXTURES["horror"]).content_profile
    children = runtime.plan(LISTENING_FIXTURES["children"]).content_profile
    technical = runtime.plan(LISTENING_FIXTURES["technical"]).content_profile

    assert horror["genre"] == "horror_suspense"
    assert horror["domain"] == "general"
    assert children["genre"] == "children"
    assert children["audience"] == "children"
    assert technical["domain"] == "technical"
    assert technical["content_mode"] == "instructional"
    assert all(profile["fallback_used"] is False for profile in (horror, children, technical))


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
