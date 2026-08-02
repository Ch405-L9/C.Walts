from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path

import yaml

from scripts.validate_stage2_sources import validate_manifest


def write_manifest(tmp_path: Path, records: list[dict]) -> tuple[Path, Path]:
    root = tmp_path
    snapshots = root / "snapshots"
    snapshots.mkdir(exist_ok=True)
    (snapshots / "source.xml").write_text("<article>source</article>\n", encoding="utf-8")
    checksum = hashlib.sha256((snapshots / "source.xml").read_bytes()).hexdigest()
    for record in records:
        record.setdefault("checksum", checksum)
    manifest = root / "stage2_public_sources.yaml"
    manifest.write_text(yaml.safe_dump({"version": 1, "sources": records}), encoding="utf-8")
    return manifest, snapshots


def valid_record(**overrides) -> dict:
    record = {
        "source_id": "source-a",
        "title": "Useful Article",
        "authors": ["A. Author"],
        "publisher": "PLOS",
        "doi": "10.1000/example",
        "pmcid": "PMC1",
        "pmid": "1",
        "official_url": "https://doi.org/10.1000/example",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "local_snapshot_path": "snapshots/source.xml",
        "checksum_algorithm": "sha256",
        "source_format": "jats_xml",
        "extraction_locator_capability": "section and paragraph",
        "attribution_text": "Author, Useful Article, CC BY 4.0.",
        "access_date": "2026-08-02",
        "permission_basis": "article",
        "transformation_permission": "before_after_rewrite",
        "figures_excluded": True,
        "tables_excluded": True,
        "captions_excluded": True,
        "references_excluded": True,
        "supplementary_files_excluded": True,
        "embedded_third_party_quotations_excluded": True,
    }
    record.update(overrides)
    return record


def validate(tmp_path: Path, records: list[dict]) -> dict:
    manifest, snapshots = write_manifest(tmp_path, records)
    return validate_manifest(
        manifest,
        project_root=tmp_path,
        approved_roots=[snapshots],
        repository_commit="abc123",
    )


def error_codes(report: dict) -> set[str]:
    return {error["code"] for error in report["errors"]}


def substantive(report: dict) -> dict:
    out = deepcopy(report)
    out.pop("generated_at", None)
    return out


def test_complete_approved_cc_by_record_passes(tmp_path: Path) -> None:
    report = validate(tmp_path, [valid_record()])

    assert report["verdict"] == "pass"
    assert report["errors"] == []
    assert report["checksum_results"][0]["match"] is True


def test_unknown_license_fails(tmp_path: Path) -> None:
    report = validate(tmp_path, [valid_record(license="Custom open license")])

    assert "unknown_license" in error_codes(report)
    assert report["verdict"] == "fail"


def test_cc_by_nd_fails_for_transformed_rewrite_use(tmp_path: Path) -> None:
    report = validate(tmp_path, [valid_record(license="CC BY-ND 4.0")])

    assert "rejected_license" in error_codes(report)


def test_non_commercial_license_fails(tmp_path: Path) -> None:
    report = validate(tmp_path, [valid_record(license="CC BY-NC 4.0")])

    assert "rejected_license" in error_codes(report)


def test_missing_article_level_license_evidence_fails(tmp_path: Path) -> None:
    record = valid_record()
    record.pop("license_url")

    report = validate(tmp_path, [record])

    assert "missing_license_evidence" in error_codes(report)


def test_dataset_level_permission_without_article_level_proof_fails(tmp_path: Path) -> None:
    report = validate(tmp_path, [valid_record(permission_basis="dataset")])

    assert "dataset_permission_only" in error_codes(report)


def test_missing_snapshot_fails(tmp_path: Path) -> None:
    report = validate(tmp_path, [valid_record(local_snapshot_path="snapshots/missing.xml")])

    assert "missing_snapshot" in error_codes(report)


def test_checksum_mismatch_fails(tmp_path: Path) -> None:
    report = validate(tmp_path, [valid_record(checksum="0" * 64)])

    assert "checksum_mismatch" in error_codes(report)


def test_duplicate_source_id_fails(tmp_path: Path) -> None:
    report = validate(tmp_path, [valid_record(), valid_record(doi="10.1000/other")])

    assert "duplicate_source_id" in error_codes(report)


def test_duplicate_stable_article_identifier_is_detected(tmp_path: Path) -> None:
    report = validate(tmp_path, [valid_record(), valid_record(source_id="source-b")])

    assert "duplicate_stable_identifier" in error_codes(report)


def test_conflicting_license_records_fail(tmp_path: Path) -> None:
    report = validate(
        tmp_path,
        [
            valid_record(),
            valid_record(source_id="source-b", license="CC0"),
        ],
    )

    assert "conflicting_license_records" in error_codes(report)


def test_evidence_paths_outside_approved_roots_fail(tmp_path: Path) -> None:
    outside = tmp_path / "outside.xml"
    outside.write_text("<article/>", encoding="utf-8")

    report = validate(tmp_path, [valid_record(local_snapshot_path=str(outside))])

    assert "evidence_path_outside_roots" in error_codes(report)


def test_license_evidence_path_must_exist_when_provided(tmp_path: Path) -> None:
    report = validate(
        tmp_path,
        [
            valid_record(
                license_url="",
                license_evidence_path="snapshots/missing-license.txt",
            )
        ],
    )

    assert "missing_evidence_file" in error_codes(report)


def test_missing_attribution_fails(tmp_path: Path) -> None:
    report = validate(tmp_path, [valid_record(attribution_text="")])

    assert "missing_required_field" in error_codes(report)


def test_missing_extraction_locator_capability_fails(tmp_path: Path) -> None:
    report = validate(tmp_path, [valid_record(extraction_locator_capability="")])

    assert "missing_required_field" in error_codes(report)


def test_third_party_content_exclusion_declarations_are_enforced(tmp_path: Path) -> None:
    report = validate(tmp_path, [valid_record(figures_excluded=False)])

    assert "missing_exclusion_declaration" in error_codes(report)


def test_output_ordering_and_findings_are_deterministic(tmp_path: Path) -> None:
    records = [
        valid_record(source_id="z", license="Unknown"),
        valid_record(source_id="a", local_snapshot_path="snapshots/missing.xml"),
    ]

    first = substantive(validate(tmp_path, deepcopy(records)))
    second = substantive(validate(tmp_path, deepcopy(records)))

    assert first == second
    assert [error["source_id"] for error in first["errors"]] == sorted(
        error["source_id"] for error in first["errors"]
    )


def test_duplicate_secondary_article_identifier_is_detected(tmp_path: Path) -> None:
    report = validate(
        tmp_path,
        [
            valid_record(doi="10.1000/a", pmcid="PMC-SAME", pmid="1"),
            valid_record(
                source_id="source-b",
                doi="10.1000/b",
                pmcid="PMC-SAME",
                pmid="2",
            ),
        ],
    )

    assert "duplicate_stable_identifier" in error_codes(report)
