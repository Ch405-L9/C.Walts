from __future__ import annotations

import zipfile
from pathlib import Path

from scripts import diagnose_gate3_custom_exact_topology as diagnostic


def test_exact_pair_math_and_edge_ordering() -> None:
    assert sum(n * (n - 1) // 2 for n in (2, 3, 4)) == 10
    assert diagnostic._edge_key(("G3S-0002", "replacement", "G3S-0001", "primary")) == (
        "G3S-0001",
        "primary",
        "G3S-0002",
        "replacement",
    )


def test_digest_discards_canonical_text() -> None:
    record = {"query_text": "Synthetic private text."}
    digest = diagnostic._record_digest(record)
    assert len(digest) == 64
    assert "Synthetic private text." not in digest


def test_metadata_projection_has_no_query_text() -> None:
    record = {
        "slot_id": "G3S-0001",
        "draft_role": "primary",
        "class": "supported_in_domain",
        "task_family": "synthetic",
        "scenario_family": "synthetic",
        "group_id": "group",
        "template_fingerprint": "template",
    }
    projected = diagnostic._metadata(record, "a" * 64, {"G3S-0001"})
    assert "query_text" not in projected
    assert projected["digest"] == "a" * 64


def test_bundle_shape_is_exact_and_sanitized(tmp_path: Path, monkeypatch) -> None:
    result = {
        "topology": {
            "pool_sha256": "a" * 64,
            "duplicate_group_count": 1,
            "duplicate_group_size_histogram": {"2": 1},
            "duplicate_affected_record_count": 2,
            "duplicate_excess_record_count": 1,
            "max_duplicate_group_size": 2,
            "primary_primary_exact_count": 1,
            "primary_replacement_exact_count": 0,
            "replacement_replacement_exact_count": 0,
            "singleton_affected_count": 0,
            "singleton_to_two_role_exact_edge_count": 0,
            "singleton_to_singleton_exact_edge_count": 0,
            "duplicate_groups_with_one_singleton": 0,
            "duplicate_groups_with_multiple_singletons": 0,
            "forced_singleton_exact_conflict": False,
            "exact_unique_incompatibility_edge_count": 1,
            "existing_hard_review_edge_count": 0,
            "augmented_unique_edge_count": 1,
            "exact_only_feasible": True,
            "exact_only_proof_sha256": "b" * 64,
            "augmented_one_role_per_slot_feasible": True,
            "augmented_feasibility_proof_sha256": "c" * 64,
        },
        "feasibility": {"query_text_included": False, "selection_witness_included": False},
    }
    monkeypatch.setattr(diagnostic, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(diagnostic, "BUNDLE", tmp_path / "bundle.zip")
    diagnostic.write_bundle(result, "synthetic")
    with zipfile.ZipFile(tmp_path / "bundle.zip") as archive:
        names = archive.namelist()
        assert len(names) == 18
        assert "SHA256SUMS" in names
        payload = b"".join(archive.read(name) for name in names)
        assert b"Synthetic private text." not in payload
