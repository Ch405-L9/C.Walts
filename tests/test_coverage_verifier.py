from __future__ import annotations

from copy import deepcopy

from scripts.verify_coverage import build_report, id_list_sha256


def record(index: int, *, doc_type: str = "approved_example", source_id: str = "source-a") -> dict:
    return {
        "id": f"{index:016x}_0",
        "text": f"example {index}",
        "metadata": {
            "source_id": source_id,
            "source_path": f"corpus/{source_id}.md",
            "doc_type": doc_type,
            "section_heading": f"Example {index}",
        },
    }


def taxonomy(records: list[dict], *, category: str = "technical") -> dict:
    return {
        "categories": [
            {"category_id": category, "name": "Technical", "caveat_text": "Descriptive only."}
        ],
        "assignments": [
            {
                "chunk_id": r["id"],
                "source_id": r["metadata"]["source_id"],
                "category_id": category,
                "independence_group": f"group-{r['id']}",
                "review_status": "accepted",
            }
            for r in records
        ],
    }


def report(
    records: list[dict],
    tax: dict | None = None,
    *,
    expected_count: int | None = None,
    bm25: list[str] | None = None,
):
    ids = [r["id"] for r in records]
    return build_report(
        records=records,
        bm25_ids=bm25 or ids,
        taxonomy=tax or taxonomy(records),
        expected_count=len(records) if expected_count is None else expected_count,
        expected_id_list_sha256=id_list_sha256(ids),
        generated_at="fixed",
    )


def test_exact_expected_production_count_passes() -> None:
    records = [record(i) for i in range(96)]
    result = report(records)
    assert result["verdict"] == "pass"
    assert result["categorized_record_count"] == 96
    assert result["mutation_performed"] is False


def test_old_84_record_assumption_fails_against_96_fixture() -> None:
    result = report([record(i) for i in range(96)], expected_count=84)
    assert result["verdict"] == "fail"


def test_parity_mismatch_fails() -> None:
    records = [record(i) for i in range(3)]
    result = report(records, bm25=[records[0]["id"], records[1]["id"], "unknown_0"])
    assert result["verdict"] == "fail"


def test_missing_assignment_fails() -> None:
    records = [record(i) for i in range(3)]
    tax = taxonomy(records[:-1])
    result = report(records, tax)
    assert result["uncategorized_ids"] == [records[-1]["id"]]
    assert result["verdict"] == "fail"


def test_duplicate_assignment_fails() -> None:
    records = [record(0)]
    tax = taxonomy(records)
    tax["assignments"].append(deepcopy(tax["assignments"][0]))
    result = report(records, tax)
    assert result["duplicate_assignment_ids"] == [records[0]["id"]]
    assert result["verdict"] == "fail"


def test_unknown_assignment_fails() -> None:
    records = [record(0)]
    tax = taxonomy(records)
    tax["assignments"][0]["chunk_id"] = "missing_0"
    result = report(records, tax)
    assert result["unknown_assignment_ids"] == ["missing_0"]
    assert result["verdict"] == "fail"


def test_deterministic_counts_and_repeat_report() -> None:
    records = [record(i, source_id="same") for i in range(4)]
    first = report(records)
    second = report(records)
    assert first == second
    assert first["categories"][0]["record_count"] == 4
    assert first["categories"][0]["independent_example_count"] == 4


def test_same_source_caveat_and_independence_group_are_preserved() -> None:
    records = [record(0, source_id="article"), record(1, source_id="article")]
    tax = taxonomy(records)
    tax["assignments"][1]["independence_group"] = tax["assignments"][0]["independence_group"]
    result = report(records, tax)
    category = result["categories"][0]
    assert category["source_count"] == 1
    assert category["independent_example_count"] == 1
    assert category["independent_example_count"] <= category["record_count"]


def test_three_independent_examples_only_emit_smoke_floor() -> None:
    result = report([record(i) for i in range(3)])
    category = result["categories"][0]
    assert category["smoke_floor_bucket"] == ">=3"
    assert category["smoke_floor_label"] == "smoke_test_floor"
    assert "statistically" not in category["caveat_text"].lower()


def test_below_three_has_no_statistical_claim() -> None:
    result = report([record(0), record(1)])
    category = result["categories"][0]
    assert category["smoke_floor_bucket"] == "2"
    assert category["smoke_floor_label"] is None
    assert "sufficient" not in category["caveat_text"].lower()


def test_review_required_is_surfaced() -> None:
    records = [record(0)]
    tax = taxonomy(records)
    tax["assignments"][0]["review_status"] = "review_required"
    result = report(records, tax)
    assert result["review_required_count"] == 1
    assert result["verdict"] == "fail"


def test_evaluation_case_leakage_fails() -> None:
    result = report([record(0)], taxonomy([record(0)]))
    result = build_report(
        records=[record(0, doc_type="evaluation_case")],
        bm25_ids=[record(0)["id"]],
        taxonomy=taxonomy([record(0)]),
        expected_count=1,
        expected_id_list_sha256=id_list_sha256([record(0)["id"]]),
        evaluation_case_count=1,
        generated_at="fixed",
    )
    assert result["verdict"] == "fail"
