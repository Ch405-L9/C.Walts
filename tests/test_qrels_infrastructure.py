from __future__ import annotations

import hashlib

import pytest

from scripts.build_qrels_candidate_pool import build_candidate_pool, load_queries
from scripts.validate_qrels import validate_qrels


def query(query_id: str = "CWQ-CAL-0001", *, split: str = "calibration") -> dict:
    text = "technical calibration query"
    return {
        "query_id": query_id,
        "query_text": text,
        "query_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "split": split,
        "query_class": "dense",
        "group_id": "group-1",
        "expected_behavior": "retrieve grounding",
    }


def record(chunk_id: str = "a_0", source_id: str = "source-a") -> dict:
    return {
        "id": chunk_id,
        "text": "text",
        "metadata": {
            "source_id": source_id,
            "source_path": "corpus/a.md",
            "doc_type": "approved_example",
        },
    }


def test_query_identity_and_hash_validation(tmp_path) -> None:
    path = tmp_path / "queries.yaml"
    path.write_text(
        "queries:\n  - query_id: CWQ-CAL-0001\n    query_sha256: bad\n    split: calibration\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="query_sha256"):
        load_queries(path)


def test_duplicate_query_ids_refused(tmp_path) -> None:
    q = query()
    path = tmp_path / "queries.yaml"
    import yaml

    path.write_text(yaml.safe_dump({"queries": [q, q]}), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_queries(path)


def test_holdout_query_refused(tmp_path) -> None:
    import yaml

    path = tmp_path / "queries.yaml"
    path.write_text(yaml.safe_dump({"queries": [query(split="holdout")]}), encoding="utf-8")
    with pytest.raises(ValueError, match="calibration"):
        load_queries(path)


def test_union_is_deterministic_and_retains_arm_provenance() -> None:
    q = query()
    dense = [
        {"chunk_id": "b_0", "rank": 2, "score": 0.2},
        {"chunk_id": "a_0", "rank": 1, "score": 0.9},
    ]
    bm25 = [
        {"chunk_id": "a_0", "rank": 1, "score": 4.0},
        {"chunk_id": "c_0", "rank": 2, "score": 1.0},
    ]
    first = build_candidate_pool(
        query=q, dense_results=dense, bm25_results=bm25, dense_depth=2, bm25_depth=2
    )
    second = build_candidate_pool(
        query=q, dense_results=dense, bm25_results=bm25, dense_depth=2, bm25_depth=2
    )
    assert first == second
    assert {item["chunk_id"] for item in first["candidates"]} == {"a_0", "b_0", "c_0"}
    assert (
        next(item for item in first["candidates"] if item["chunk_id"] == "a_0")["discovery_arm"]
        == "dense+bm25"
    )


def test_depths_are_configurable() -> None:
    result = build_candidate_pool(
        query=query(),
        dense_results=[
            {"chunk_id": "a_0", "rank": 1, "score": 1},
            {"chunk_id": "b_0", "rank": 2, "score": 1},
        ],
        bm25_results=[{"chunk_id": "c_0", "rank": 1, "score": 1}],
        dense_depth=1,
        bm25_depth=1,
    )
    assert [item["chunk_id"] for item in result["candidates"]] == ["a_0", "c_0"]


def test_all_production_records_mode_returns_exact_fixture_set() -> None:
    ids = ["b_0", "a_0"]
    result = build_candidate_pool(
        query=query(), dense_results=[], bm25_results=[], all_production_ids=ids
    )
    assert [item["chunk_id"] for item in result["candidates"]] == ["a_0", "b_0"]
    assert all(item["discovery_arm"] == "all-production-records" for item in result["candidates"])


def judgment(**overrides):
    q = query()
    result = {
        "schema_version": 1,
        "query_id": q["query_id"],
        "query_sha256": q["query_sha256"],
        "split": "calibration",
        "query_class": q["query_class"],
        "group_id": q["group_id"],
        "expected_behavior": q["expected_behavior"],
        "chunk_id": "a_0",
        "source_id": "source-a",
        "source_path": "corpus/a.md",
        "doc_type": "approved_example",
        "relevance_grade": 2,
        "judge_role": "synthetic",
        "judgment_timestamp_utc": "2026-08-08T00:00:00Z",
        "collection_version_identity": "v0.4.0-dev.4-96",
    }
    result.update(overrides)
    return result


def test_grades_0_1_2_and_identity_pass() -> None:
    queries = [query()]
    records = [record()]
    for grade in (0, 1, 2):
        result = validate_qrels(
            judgments=[judgment(relevance_grade=grade)],
            queries=queries,
            production_records=records,
            collection_version_identity="v0.4.0-dev.4-96",
        )
        assert result["verdict"] == "pass"


@pytest.mark.parametrize(
    "bad",
    [
        {"query_sha256": "0" * 64},
        {"chunk_id": "missing_0"},
        {"relevance_grade": 3},
        {"collection_version_identity": "wrong"},
    ],
)
def test_invalid_judgment_is_refused(bad) -> None:
    result = validate_qrels(
        judgments=[judgment(**bad)],
        queries=[query()],
        production_records=[record()],
        collection_version_identity="v0.4.0-dev.4-96",
    )
    assert result["verdict"] == "fail"


def test_duplicate_judgment_is_refused() -> None:
    result = validate_qrels(
        judgments=[judgment(), judgment()],
        queries=[query()],
        production_records=[record()],
        collection_version_identity="v0.4.0-dev.4-96",
    )
    assert any(item.startswith("duplicate_judgment") for item in result["findings"])


def test_holdout_judgment_and_query_are_refused() -> None:
    q = query(split="holdout")
    result = validate_qrels(
        judgments=[judgment(split="holdout")],
        queries=[q],
        production_records=[record()],
        collection_version_identity="v0.4.0-dev.4-96",
    )
    assert result["verdict"] == "fail"
    assert result["holdout_judgment_count"] == 1


def test_source_provenance_mismatch_is_refused() -> None:
    result = validate_qrels(
        judgments=[judgment(source_id="wrong")],
        queries=[query()],
        production_records=[record()],
        collection_version_identity="v0.4.0-dev.4-96",
    )
    assert result["verdict"] == "fail"


def test_empty_real_qrels_is_valid_only_against_empty_calibration_fixture() -> None:
    result = validate_qrels(
        judgments=[],
        queries=[],
        production_records=[record()],
        collection_version_identity="v0.4.0-dev.4-96",
    )
    assert result["verdict"] == "pass"
    assert result["judgment_count"] == 0
