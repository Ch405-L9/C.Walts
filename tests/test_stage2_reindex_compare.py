from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

from scripts.compare_reindex_plan import (
    build_isolated_bm25_ids,
    compare_records,
    final_plan_records,
    proposed_chroma_ids_from_records,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare_reindex_plan.py"
VALID_FIXTURE = ROOT / "tests" / "fixtures" / "stage2_compare" / "valid_sources.yaml"
CHROMA_DIR = ROOT / "var" / "chroma"
BM25_INDEX = ROOT / "var" / "bm25" / "index.json"


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
    source_scope = ["stage2"]
    args = {
        "current_records": current,
        "proposed_records": proposed,
        "production_bm25_ids": ["aaa_0"],
        "source_scope": source_scope,
        "repository_commit": "abc123",
        "branch": "feat/test",
        "production_store_identity": {"collection": "test", "count": len(current)},
        "proposed_source_identity": {"source_ids": source_scope},
    }
    args.update(overrides)
    if "proposed_bm25_ids" not in args:
        final_records = final_plan_records(
            current_records=args["current_records"],
            proposed_records=args["proposed_records"],
            source_scope=set(args["source_scope"]),
        )
        args["proposed_bm25_ids"] = proposed_chroma_ids_from_records(final_records)
    return compare_records(**args)


def substantive(report: dict) -> dict:
    stripped = deepcopy(report)
    stripped.pop("generated_at", None)
    return stripped


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for candidate in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(str(candidate.relative_to(path)).encode())
        digest.update(candidate.read_bytes())
    return digest.hexdigest()


def run_cli(tmp_path: Path, *args: str, expected_returncode: int = 0) -> tuple[dict, str]:
    output = tmp_path / f"comparison-{len(list(tmp_path.glob('comparison-*.json')))}.json"
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(SCRIPT),
            "--proposed-source-config",
            str(VALID_FIXTURE.relative_to(ROOT)),
            "--output-json",
            str(output),
            *args,
        ],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == expected_returncode, result.stderr + result.stdout
    return json.loads(output.read_text(encoding="utf-8")), result.stdout


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


def test_isolated_lexical_build_produces_exact_proposed_parity(tmp_path: Path) -> None:
    current = [record("aaa_0", "old")]
    proposed = [record("bbb_0", "new")]
    final_records = final_plan_records(
        current_records=current,
        proposed_records=proposed,
        source_scope={"stage2"},
    )

    chroma_ids = proposed_chroma_ids_from_records(final_records)
    bm25_ids = build_isolated_bm25_ids(final_records, temp_root=tmp_path)

    assert bm25_ids == chroma_ids


def test_isolated_lexical_build_omission_fails_parity(tmp_path: Path) -> None:
    final_records = [record("aaa_0", "old"), record("bbb_0", "new")]
    bm25_ids = build_isolated_bm25_ids(
        final_records,
        temp_root=tmp_path,
        omit_ids={"bbb_0"},
    )

    report = base_report(
        current_records=[record("aaa_0", "old")],
        proposed_records=[record("bbb_0", "new")],
        production_bm25_ids=["aaa_0"],
        proposed_bm25_ids=bm25_ids,
    )

    assert report["proposed_id_parity"] is False
    assert report["mutation_performed"] is False
    assert report["verdict"] == "fail"


def test_isolated_lexical_build_extra_id_fails_parity(tmp_path: Path) -> None:
    final_records = [record("bbb_0", "new")]
    bm25_ids = build_isolated_bm25_ids(
        final_records,
        temp_root=tmp_path,
        extra_ids={"extra_0"},
    )

    report = base_report(
        current_records=[record("aaa_0", "old")],
        proposed_records=[record("bbb_0", "new")],
        production_bm25_ids=["aaa_0"],
        proposed_bm25_ids=bm25_ids,
    )

    assert report["proposed_id_parity"] is False
    assert report["mutation_performed"] is False
    assert report["verdict"] == "fail"


def test_cli_path_independently_builds_proposed_chroma_and_bm25_ids(tmp_path: Path) -> None:
    report, stdout = run_cli(tmp_path, "--dry-run")

    assert "mutation_performed=False" in stdout
    assert report["proposed_id_parity"] is True
    assert report["proposed_chroma_ids"] == report["proposed_bm25_ids"]
    assert report["would_add_ids"]
    assert report["mutation_performed"] is False


def test_cli_path_detects_missing_bm25_id(tmp_path: Path) -> None:
    valid, _ = run_cli(tmp_path, "--dry-run")
    omitted = valid["would_add_ids"][0]

    report, _ = run_cli(
        tmp_path,
        "--dry-run",
        "--simulate-bm25-omit-id",
        omitted,
        expected_returncode=1,
    )

    assert report["proposed_id_parity"] is False
    assert omitted in set(report["proposed_chroma_ids"]) - set(report["proposed_bm25_ids"])
    assert report["mutation_performed"] is False
    assert report["verdict"] == "fail"


def test_cli_path_detects_extra_bm25_id(tmp_path: Path) -> None:
    report, _ = run_cli(
        tmp_path,
        "--dry-run",
        "--simulate-bm25-extra-id",
        "extra_fixture_0",
        expected_returncode=1,
    )

    assert report["proposed_id_parity"] is False
    assert "extra_fixture_0" in set(report["proposed_bm25_ids"]) - set(
        report["proposed_chroma_ids"]
    )
    assert report["mutation_performed"] is False
    assert report["verdict"] == "fail"


def test_lexical_build_failure_fails_closed(tmp_path: Path) -> None:
    report, _ = run_cli(
        tmp_path,
        "--dry-run",
        "--simulate-bm25-build-failure",
        expected_returncode=1,
    )

    assert any(finding["code"] == "proposed_bm25_build_failed" for finding in report["findings"])
    assert report["proposed_id_parity"] is False
    assert report["mutation_performed"] is False
    assert report["verdict"] == "fail"


def test_cli_omits_dry_run_refuses_before_output(tmp_path: Path) -> None:
    output = tmp_path / "no-dry-run.json"
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(SCRIPT),
            "--proposed-source-config",
            str(VALID_FIXTURE.relative_to(ROOT)),
            "--output-json",
            str(output),
        ],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "--dry-run is required" in result.stderr
    assert not output.exists()


def test_isolated_lexical_build_does_not_modify_live_bm25(tmp_path: Path) -> None:
    before = file_digest(BM25_INDEX)

    run_cli(tmp_path, "--dry-run")

    assert file_digest(BM25_INDEX) == before


def test_comparison_does_not_modify_live_chroma(tmp_path: Path) -> None:
    before = tree_digest(CHROMA_DIR)

    run_cli(tmp_path, "--dry-run")

    assert tree_digest(CHROMA_DIR) == before


def test_repeated_valid_cli_runs_produce_equivalent_substantive_json(
    tmp_path: Path,
) -> None:
    first, _ = run_cli(tmp_path, "--dry-run")
    second, _ = run_cli(tmp_path, "--dry-run")

    assert substantive(first) == substantive(second)
