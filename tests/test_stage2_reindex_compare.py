from __future__ import annotations

from copy import deepcopy

from scripts.compare_reindex_plan import compare_records


def record(
    chunk_id: str,
    text: str,
    *,
    source_id: str = "stage2",
    source_path: str = "corpus/raw/stage2/example.md",
    doc_type: str = "approved_example",
    license_value: str = "CC BY 4.0",
    section_heading: str = "Example",
) -> dict:
    return {
        "id": chunk_id,
        "text": text,
        "metadata": {
            "source_id": source_id,
            "source_path": source_path,
            "source_title": "Stage 2",
            "license": license_value,
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "source_checksum": "abc",
            "chunk_index": 0,
            "chunk_total": 1,
            "chunk_profile": "approved_example",
            "embedding_model": "nomic-embed-text",
            "embedding_dimension": 768,
            "tokenizer": "cl100k_base",
            "token_count": 10,
            "section_heading": section_heading,
            "doc_type": doc_type,
            "dialect": "en-US",
            "register": "technical explainer",
        },
    }


def base_report(**overrides):
    current = [record("aaa_0", "old", source_id="stage2")]
    proposed = [record("bbb_0", "new", source_id="stage2")]
    args = {
        "current_records": current,
        "proposed_records": proposed,
        "production_bm25_ids": ["aaa_0"],
        "source_scope": ["stage2"],
        "repository_commit": "abc123",
        "branch": "feat/test",
        "production_store_identity": {"collection": "test", "count": len(current)},
        "proposed_source_identity": {"source_ids": ["stage2"]},
    }
    args.update(overrides)
    return compare_records(**args)


def substantive(report: dict) -> dict:
    stripped = deepcopy(report)
    stripped.pop("generated_at", None)
    return stripped


def test_new_valid_chunks_appear_in_would_add_ids() -> None:
    report = base_report()

    assert report["would_add_ids"] == ["bbb_0"]
    assert report["mutation_performed"] is False


def test_removed_source_scoped_chunks_appear_in_stale_ids() -> None:
    report = base_report()

    assert report["stale_ids"] == ["aaa_0"]


def test_identical_chunks_appear_in_unchanged_ids() -> None:
    current = [record("same_0", "same")]
    proposed = [record("same_0", "same")]

    report = base_report(
        current_records=current,
        proposed_records=proposed,
        production_bm25_ids=["same_0"],
    )

    assert report["unchanged_ids"] == ["same_0"]
    assert report["verdict"] == "pass"


def test_duplicate_deterministic_ids_are_rejected() -> None:
    proposed = [record("dup_0", "one"), record("dup_0", "two")]

    report = base_report(proposed_records=proposed)

    assert report["duplicate_ids"] == ["dup_0"]
    assert report["verdict"] == "fail"


def test_duplicate_canonical_content_is_reported() -> None:
    proposed = [record("one_0", "same"), record("two_0", "same")]

    report = base_report(proposed_records=proposed)

    assert report["duplicate_content_groups"]
    assert report["verdict"] == "fail"


def test_duplicate_id_between_proposed_and_production_is_rejected() -> None:
    current = [record("same_0", "existing", source_id="existing")]
    proposed = [record("same_0", "new", source_id="stage2")]

    report = base_report(
        current_records=current,
        proposed_records=proposed,
        production_bm25_ids=["same_0"],
    )

    assert report["duplicate_ids"] == ["same_0"]
    assert report["verdict"] == "fail"


def test_duplicate_content_between_proposed_and_production_is_reported() -> None:
    current = [record("current_0", "same", source_id="existing")]
    proposed = [record("proposed_0", "same", source_id="stage2")]

    report = base_report(
        current_records=current,
        proposed_records=proposed,
        production_bm25_ids=["current_0"],
    )

    groups = list(report["duplicate_content_groups"].values())
    assert ["current_0", "proposed_0"] in groups
    assert report["verdict"] == "fail"


def test_existing_id_with_changed_content_is_not_unchanged() -> None:
    current = [record("same_0", "old")]
    proposed = [record("same_0", "new")]

    report = base_report(
        current_records=current,
        proposed_records=proposed,
        production_bm25_ids=["same_0"],
    )

    assert report["unchanged_ids"] == []
    assert report["content_changed_ids"] == ["same_0"]
    assert report["verdict"] == "fail"


def test_existing_id_with_relevant_metadata_change_is_reported() -> None:
    current = [record("same_0", "same")]
    proposed = [record("same_0", "same", section_heading="Changed")]

    report = base_report(
        current_records=current,
        proposed_records=proposed,
        production_bm25_ids=["same_0"],
    )

    assert report["metadata_changed_ids"] == ["same_0"]
    assert report["verdict"] == "fail"


def test_chroma_bm25_proposed_id_mismatch_fails() -> None:
    report = base_report(proposed_bm25_ids=["aaa_0"])

    assert report["proposed_id_parity"] is False
    assert report["verdict"] == "fail"


def test_evaluation_case_leakage_fails() -> None:
    proposed = [record("eval_0", "eval", doc_type="evaluation_case")]

    report = base_report(proposed_records=proposed)

    assert report["evaluation_case_count"] == 1
    assert report["verdict"] == "fail"


def test_changes_outside_allowlisted_source_scope_fail() -> None:
    proposed = [record("other_0", "other", source_id="other")]

    report = base_report(
        proposed_records=proposed,
        allowlisted_source_ids=["stage2"],
    )

    assert report["non_allowlisted_changes"] == [
        {"source_id": "other", "reason": "not in allowlisted source scope"}
    ]
    assert report["verdict"] == "fail"


def test_ambiguous_stale_id_ownership_fails_closed() -> None:
    current = [record("aaa_0", "old")]
    current[0]["metadata"].pop("source_checksum")

    report = base_report(current_records=current, production_bm25_ids=["aaa_0"])

    assert any(f["code"] == "ambiguous_stale_scope" for f in report["findings"])
    assert report["verdict"] == "fail"


def test_running_comparison_does_not_change_inputs_or_counts() -> None:
    current = [record("aaa_0", "old")]
    proposed = [record("bbb_0", "new")]
    before = deepcopy((current, proposed))

    report = base_report(
        current_records=current,
        proposed_records=proposed,
        production_bm25_ids=["aaa_0"],
    )

    assert (current, proposed) == before
    assert report["current_production_count"] == 1
    assert report["mutation_performed"] is False


def test_output_ordering_is_deterministic() -> None:
    proposed = [
        record("z_0", "z"),
        record("a_0", "a"),
        record("m_0", "m"),
    ]

    report = base_report(proposed_records=proposed)

    assert report["would_add_ids"] == ["a_0", "m_0", "z_0"]


def test_repeated_runs_produce_equivalent_substantive_json() -> None:
    first = substantive(base_report())
    second = substantive(base_report())

    assert first == second
