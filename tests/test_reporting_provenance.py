"""Synthetic coverage for Stage 4 report provenance and semantic projection."""

from __future__ import annotations

import copy
import hashlib
import uuid

import pytest
from jsonschema import ValidationError

from eval.run_evaluation import (
    REPORT_SEMANTICS,
    result_provenance,
    semantic_projection,
    validate_report_schema,
)
from natural_flow_rag.lexical_search import LexicalHit
from natural_flow_rag.retrieval import RetrievedChunk, Retriever


def chunk(
    chunk_id: str,
    *,
    heading: str = "same heading",
    dense_rank: int | None = 1,
    dense_distance: float | None = 0.12,
    lexical_rank: int | None = 1,
    bm25_score: float | None = 2.5,
    rank: int = 1,
    score: float = 0.032,
    neighbor: bool = False,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text="synthetic result",
        score=score,
        rank=rank,
        found_by="both",
        dense_rank=dense_rank,
        lexical_rank=lexical_rank,
        dense_distance=dense_distance,
        bm25_score=bm25_score,
        metadata={
            "source_id": "synthetic_source",
            "doc_type": "approved_example",
            "section_heading": heading,
        },
        is_neighbor=neighbor,
    )


def report(results: list[dict]) -> dict:
    run_id = str(uuid.uuid4())
    return {
        "schema_version": 2,
        "run": {
            "run_id": run_id,
            "generated_at": "2026-08-09T00:00:00+00:00",
            "collection": "synthetic",
            "collection_count": 2,
            "version": "0.4.0-dev.5",
            "embedding_model": "synthetic",
            "embedding_dimension": 3,
        },
        "summary": {
            "generated": "2026-08-09T00:00:00+00:00",
            "latency_ms_p50": 4,
            "latency_ms_p95": 5,
            "distance_min": 0.1,
            "distance_median": 0.2,
            "distance_max": 0.3,
            "similarity_min": 0.7,
            "similarity_max": 0.9,
            "exact_term_pass": True,
            "assertion_failures": 0,
            "evaluation_case_chunks_returned": 0,
            "negative_contamination": 0,
            "citation_failures": 0,
            "preservation_correct": 0,
            "preservation_total": 0,
        },
        "cases": [{
            "id": "SYN-001",
            "query_id": "SYN-001",
            "query_sha256": hashlib.sha256(b"synthetic query").hexdigest(),
            "latency_ms": 4,
            "min_distance": 0.1,
            "max_distance": 0.3,
            "results": results,
            "diagnostic": {
                "source": "separate_raw_vector_query",
                "metric": "cosine_distance",
                "direction": "lower_is_better",
                "query_embedding_recomputed": True,
                "verdict_input": False,
                "calibration_input": False,
                "min_distance": 0.1,
                "max_distance": 0.3,
            },
        }],
        "preservation": [],
        "report_semantics": copy.deepcopy(REPORT_SEMANTICS),
    }


def result(*chunks: RetrievedChunk) -> list[dict]:
    return result_provenance("SYN-001", list(chunks))


def test_valid_schema_v2_and_uuid_run_id() -> None:
    value = report(result(chunk("a")))
    validate_report_schema(value)
    uuid.UUID(value["run"]["run_id"])


def test_one_execution_uses_one_run_id_and_distinct_runs_differ() -> None:
    first = report(result(chunk("a"), chunk("b")))
    second = report(result(chunk("a"), chunk("b")))
    assert first["run"]["run_id"] == first["run"]["run_id"]
    assert first["run"]["run_id"] != second["run"]["run_id"]
    assert {item["query_id"] for item in first["cases"][0]["results"]} == {"SYN-001"}


@pytest.mark.parametrize(
    "path", ["schema_version", "cases.0.query_id", "cases.0.results.0.chunk_id"]
)
def test_required_identity_fields_are_required(path: str) -> None:
    value = report(result(chunk("a")))
    cursor = value
    bits = path.split(".")
    for bit in bits[:-1]:
        cursor = cursor[int(bit)] if bit.isdigit() else cursor[bit]
    cursor.pop(bits[-1])
    with pytest.raises(ValidationError):
        validate_report_schema(value)


@pytest.mark.parametrize(
    ("section", "field", "bad"),
    [("dense", "metric", "cosine_similarity"), ("bm25", "direction", "lower_is_better")],
)
def test_arm_metric_semantics_are_validated(section: str, field: str, bad: str) -> None:
    value = report(result(chunk("a")))
    value["cases"][0]["results"][0][section][field] = bad
    with pytest.raises(ValidationError):
        validate_report_schema(value)


def test_diagnostic_flags_cannot_be_enabled() -> None:
    value = report(result(chunk("a")))
    value["cases"][0]["diagnostic"]["calibration_input"] = True
    with pytest.raises(ValidationError):
        validate_report_schema(value)
    value = report(result(chunk("a")))
    value["cases"][0]["diagnostic"]["verdict_input"] = True
    with pytest.raises(ValidationError):
        validate_report_schema(value)


def test_chunk_id_is_identity_and_duplicate_headings_remain_distinct() -> None:
    values = result(chunk("a"), chunk("b"))
    assert [item["chunk_id"] for item in values] == ["a", "b"]
    assert values[0]["heading"] == values[1]["heading"]


def test_all_arm_provenance_is_retained_once() -> None:
    value = result(chunk("a"))[0]
    assert value["dense"] == {
        "present": True,
        "rank": 1,
        "distance": 0.12,
        "metric": "cosine_distance",
        "direction": "lower_is_better",
    }
    assert value["bm25"]["rank"] == 1
    assert value["bm25"]["score"] == 2.5
    assert value["bm25"]["direction"] == "higher_is_better"
    assert value["fused"]["rank"] == 1
    assert value["fused"]["score"] == 0.032
    assert value["fused"]["rrf_k"] == 60


def test_retriever_retains_raw_arm_values_without_changing_fusion_inputs() -> None:
    class Settings:
        retrieval = {
            "dense_candidates": 2,
            "lexical_candidates": 2,
            "final_chunks": 2,
            "fusion": {"rrf_k": 60},
            "forbid_doc_types_always": [],
            "exclude_doc_types_by_default": [],
            "contrast_intent_patterns": [],
            "deduplicate": True,
            "maximum_chunks_per_document": 3,
            "demote_doc_types": [],
            "neighbor_chunks": 0,
            "maximum_context_tokens": 2048,
        }
        chunking = {}

    class Store:
        def query(self, *, embedding, n_results, where):
            return {
                "ids": [["dense-a", "both"]],
                "documents": [["a", "b"]],
                "metadatas": [[
                    {"source_id": "source-a", "doc_type": "approved_example", "token_count": 1},
                    {"source_id": "source-b", "doc_type": "approved_example", "token_count": 1},
                ]],
                "distances": [[0.11, 0.22]],
            }

        def fetch(self, ids):
            return {"ids": [], "documents": [], "metadatas": []}

    class Embedder:
        def embed_one(self, query):
            return [0.0]

    class Lexical:
        def search(self, query, k):
            return [LexicalHit("both", 3.5, 1), LexicalHit("lexical-only", 1.5, 2)]

    result = Retriever(Settings(), Store(), Embedder(), Lexical()).search("synthetic", k=2)
    both = next(item for item in result.chunks if item.chunk_id == "both")
    assert both.dense_distance == 0.22
    assert both.bm25_score == 3.5
    assert both.dense_rank == 2
    assert both.lexical_rank == 1
    assert [item.chunk_id for item in result.chunks] == ["both", "dense-a"]


def test_neighbor_has_no_fabricated_arm_provenance() -> None:
    value = report(
        result(chunk("n", neighbor=True, dense_rank=None, lexical_rank=None))
    )["cases"][0]
    item = value["results"][0]
    assert item["is_neighbor"] is True
    assert item["dense"]["present"] is False
    assert item["bm25"]["present"] is False
    assert item["fused"]["present"] is False
    validate_report_schema(report([item]))


def test_run_id_and_execution_fields_are_excluded_but_identity_is_not() -> None:
    first = report(result(chunk("a")))
    second = copy.deepcopy(first)
    second["run"]["run_id"] = str(uuid.uuid4())
    second["run"]["generated_at"] = "2026-08-10T00:00:00+00:00"
    second["summary"]["latency_ms_p50"] = 99
    second["cases"][0]["results"][0]["dense"]["distance"] = 0.91
    assert semantic_projection(first) == semantic_projection(second)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda v: v["cases"][0]["results"][0]["dense"].update(rank=2),
        lambda v: v["cases"][0]["results"][0]["bm25"].update(score=9.0),
        lambda v: v["cases"][0]["results"][0]["fused"].update(rank=2),
        lambda v: v["cases"][0]["results"][0].update(chunk_id="different"),
        lambda v: v["cases"][0]["results"][0].update(source_id="different_source"),
        lambda v: v["cases"][0]["results"][0].update(doc_type="style_rule"),
    ],
)
def test_stable_provenance_changes_change_semantic_projection(mutation) -> None:
    first = report(result(chunk("a")))
    second = copy.deepcopy(first)
    mutation(second)
    assert semantic_projection(first) != semantic_projection(second)


def test_legacy_named_fields_remain_available() -> None:
    value = report(result(chunk("a")))
    value["summary"].update(
        exact_term_pass=True,
        assertion_failures=0,
        evaluation_case_chunks_returned=0,
        negative_contamination=0,
        citation_failures=0,
        preservation_correct=0,
        preservation_total=0,
    )
    value["cases"][0].update(id="SYN-001", top_headings=["same heading"], useful_hit=True)
    validate_report_schema(value)
    assert value["cases"][0]["id"] == value["cases"][0]["query_id"]
    assert value["cases"][0]["top_headings"] == ["same heading"]


def test_report_semantics_is_explicit_and_no_real_query_is_needed() -> None:
    value = report(result(chunk("a")))
    assert value["report_semantics"]["canonical_result_identity"] == "chunk_id"
    assert value["report_semantics"]["heading_role"] == "display_only"
    assert value["cases"][0]["diagnostic"]["query_embedding_recomputed"] is True
    assert value["cases"][0]["diagnostic"]["verdict_input"] is False
    assert value["cases"][0]["diagnostic"]["calibration_input"] is False
