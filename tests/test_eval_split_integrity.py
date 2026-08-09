from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import verify_eval_split as split


def candidate(
    number: int,
    class_name: str,
    dataset: str,
    kind: str,
    *,
    group: str | None = None,
    template: str | None = None,
    text: str | None = None,
) -> dict:
    return {
        "id": f"CWQ-SYN-{number:04d}",
        "query_text": text or hashlib.sha256(f"synthetic-record-{number:04d}".encode()).hexdigest(),
        "class": class_name,
        "expected_behavior": "grounded" if class_name == "supported_in_domain" else "abstain",
        "source_dataset": dataset,
        "source_version": "synthetic-v1",
        "source_record_id": f"record-{number:04d}",
        "source_partition": "synthetic",
        "source_intent": "synthetic-intent",
        "source_domain": "synthetic-domain",
        "group_id": group or f"group-{number:04d}",
        "template_fingerprint": template,
        "group_basis": "synthetic fixture",
        "license_ref": "synthetic-fixture",
        "provenance": {"kind": kind},
        "constraints": {},
        "notes": "synthetic only",
    }


def manifest(records: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "benchmark_version": "synthetic-v1",
        "candidate_set_id": "synthetic-600",
        "records": records,
    }


def synthetic_records() -> list[dict]:
    records: list[dict] = []
    number = 1

    def add(count: int, class_name: str, dataset: str, kind: str) -> None:
        nonlocal number
        for _ in range(count):
            records.append(candidate(number, class_name, dataset, kind))
            number += 1

    add(150, "supported_in_domain", "custom", "owner_authored")
    add(60, "near_domain_unsupported", "clinc150", "public_verbatim")
    add(45, "near_domain_unsupported", "massive_1_0_en_us", "public_verbatim")
    add(45, "near_domain_unsupported", "custom", "owner_authored")
    add(90, "far_out_of_domain", "massive_1_0_en_us", "public_verbatim")
    add(45, "far_out_of_domain", "banking77", "public_verbatim")
    add(15, "far_out_of_domain", "custom", "owner_authored")
    add(75, "ambiguous_adversarial_insufficient", "clinc150", "public_transformed")
    add(75, "ambiguous_adversarial_insufficient", "custom", "owner_authored")
    assert len(records) == 600
    return records


def test_allocation_config_and_synthetic_600_split() -> None:
    config = split.verify_config()
    assert config["verdict"] == "pass"
    result = split.generate_split(manifest(synthetic_records()))
    split_manifest = result["split_manifest"]
    assert split_manifest["record_count"] == 600
    assert split_manifest["calibration_count"] == 300
    assert split_manifest["holdout_count"] == 300
    assert result["mutation_performed"] is False
    counts: dict[tuple[str, str, str], int] = {}
    for item in split_manifest["records"]:
        key = (item["class"], item["allocation_source_key"], item["public_or_custom"])
        counts[key] = counts.get(key, 0) + 1
    assert sum(counts.values()) == 600
    assert {item["split"] for item in split_manifest["records"]} == {"calibration", "holdout"}


def test_namespace_mapping_and_mismatch_refusal() -> None:
    assert (
        split.derive_allocation_source(
            candidate(1, "near_domain_unsupported", "massive_1_0_en_us", "public_verbatim")
        )
        == "massive_en_us"
    )
    assert (
        split.derive_allocation_source(
            candidate(2, "ambiguous_adversarial_insufficient", "clinc150", "public_transformed")
        )
        == "clinc150_oos"
    )
    with pytest.raises(split.SplitIntegrityError, match="unsupported_class_source_pair"):
        split.derive_allocation_source(
            candidate(3, "supported_in_domain", "banking77", "public_verbatim")
        )
    bad = candidate(4, "near_domain_unsupported", "massive_en_us", "public_verbatim")
    with pytest.raises(split.SplitIntegrityError, match="unsupported_class_source_pair"):
        split.derive_allocation_source(bad)


def test_id_and_exact_duplicate_guards() -> None:
    records = [
        candidate(1, "supported_in_domain", "custom", "owner_authored"),
        candidate(2, "supported_in_domain", "custom", "owner_authored"),
    ]
    records[1]["id"] = records[0]["id"]
    with pytest.raises(split.SplitIntegrityError, match="duplicate_query_id"):
        split.validate_candidate_manifest(manifest(records))
    records[1]["id"] = "CWQ-SYN-0002"
    records[1]["query_text"] = f"  {records[0]['query_text']}  "
    with pytest.raises(split.SplitIntegrityError, match="duplicate_query_text"):
        split.validate_candidate_manifest(manifest(records))


def test_fingerprint_changes_when_query_mutates() -> None:
    record = candidate(1, "supported_in_domain", "custom", "owner_authored")
    before = split.record_fingerprint(record)
    record["query_text"] += " changed"
    assert split.record_fingerprint(record) != before


def test_group_template_and_mixed_stratum_refusal() -> None:
    left = candidate(1, "supported_in_domain", "custom", "owner_authored", group="shared")
    right = candidate(2, "near_domain_unsupported", "custom", "owner_authored", group="shared")
    with pytest.raises(split.SplitIntegrityError, match="mixed_stratum_leakage_cluster"):
        split.validate_candidate_manifest(manifest([left, right]))
    left = candidate(1, "supported_in_domain", "custom", "owner_authored", template="family")
    right = candidate(2, "near_domain_unsupported", "custom", "owner_authored", template="family")
    with pytest.raises(split.SplitIntegrityError, match="mixed_stratum_leakage_cluster"):
        split.validate_candidate_manifest(manifest([left, right]))


def test_group_is_never_split_and_public_group_reuse_is_impossible() -> None:
    records = synthetic_records()
    records[150]["group_id"] = "g"
    records[151]["group_id"] = "g"
    checked = split.validate_candidate_manifest(manifest(records))
    generated = split.generate_split(manifest(records))
    members = {
        item["split"] for item in generated["split_manifest"]["records"] if item["group_id"] == "g"
    }
    assert len(members) == 1
    assert checked["clusters"]


def test_near_duplicate_golden_metrics_and_guards() -> None:
    clear = split.similarity_pair("alpha beta gamma", "unrelated delta epsilon")
    review = split.similarity_pair(
        "synthetic alpha beta gamma delta", "synthetic alpha beta zeta delta"
    )
    hard = split.similarity_pair(
        "synthetic alpha beta gamma delta epsilon zeta eta theta iota kappa",
        "synthetic alpha beta gamma delta epsilon zeta eta theta iota kappa lambda",
    )
    assert clear["sequence_matcher_ratio"] < 0.92
    assert review["sequence_matcher_ratio"] >= 0.85
    assert hard["sequence_matcher_ratio"] >= 0.92
    records = [
        candidate(
            1,
            "supported_in_domain",
            "custom",
            "owner_authored",
            text="same exact family phrase wording one two three four five six",
        ),
        candidate(
            2,
            "supported_in_domain",
            "custom",
            "owner_authored",
            text="same exact family phrase wording one two three four five six altered",
        ),
    ]
    assert split.inspect_near_duplicates(records)[0]["hard"] is True
    records[1]["query_text"] = "synthetic alpha beta gamma delta theta zeta"
    records[0]["query_text"] = "synthetic alpha beta gamma delta epsilon zeta"
    findings = split.inspect_near_duplicates(records)
    assert findings and findings[0]["requires_disposition"] is True


def test_disposition_cannot_override_exact_duplicate() -> None:
    records = [
        candidate(1, "supported_in_domain", "custom", "owner_authored", text="same"),
        candidate(2, "supported_in_domain", "custom", "owner_authored", text="same"),
    ]
    with pytest.raises(split.SplitIntegrityError, match="duplicate_query_text"):
        split.validate_candidate_manifest(manifest(records))


def test_deterministic_regeneration_and_timestamp_independent_identity() -> None:
    first = split.generate_split(manifest(synthetic_records()))
    second = split.generate_split(manifest(synthetic_records()))
    assert first["split_identity_sha256"] == second["split_identity_sha256"]
    assert first["split_manifest"] == second["split_manifest"]
    assert "timestamp" not in first["immutable_identity"]


def test_impossible_whole_group_quota_refused() -> None:
    records = synthetic_records()
    for record in records[:150]:
        record["group_id"] = "all"
    with pytest.raises(split.SplitIntegrityError, match="impossible_group_quota"):
        split.generate_split(manifest(records))


def test_seal_identity_and_lifecycle_are_fail_closed() -> None:
    seal = split.generate_split(manifest(synthetic_records()))
    split.verify_seal(seal)
    split.transition_lifecycle(seal, "scored_once", "a" * 64, timestamp="2026-08-09T00:00:00Z")
    split.transition_lifecycle(
        seal, "retired_regression", "b" * 64, timestamp="2026-08-09T00:00:01Z"
    )
    split.verify_seal(seal)
    with pytest.raises(split.SplitIntegrityError, match="invalid_lifecycle_transition"):
        split.transition_lifecycle(seal, "sealed_unused", "c" * 64)
    tampered = copy.deepcopy(seal)
    tampered["immutable_identity"]["record_count"] += 1
    with pytest.raises(split.SplitIntegrityError, match="seal_identity_mismatch"):
        split.verify_seal(tampered)


def test_write_authorization_and_atomic_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate_manifest = manifest(synthetic_records())
    monkeypatch.delenv("NFR_ALLOW_EVAL_WRITES", raising=False)
    with pytest.raises(split.SplitIntegrityError, match="write_authorization_required"):
        split.atomic_generate(candidate_manifest, tmp_path, confirm=True)
    monkeypatch.setenv("NFR_ALLOW_EVAL_WRITES", "true")
    result = split.atomic_generate(candidate_manifest, tmp_path, confirm=True)
    assert result["verdict"] == "pass"
    with pytest.raises(split.SplitIntegrityError, match="sealed_destination_exists"):
        split.atomic_generate(candidate_manifest, tmp_path, confirm=True)


def test_schema_validation_and_no_real_material() -> None:
    record = candidate(1, "supported_in_domain", "custom", "owner_authored")
    split.validate_schema(manifest([record]), split.load_candidate_schema())
    assert split.record_fingerprint(record)
    assert not Path("eval/holdout/private/frozen.jsonl").exists()


def test_gate0_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        split,
        "verify_gate0",
        lambda: (_ for _ in ()).throw(split.SplitIntegrityError("gate0_integrity_failed")),
    )
    with pytest.raises(split.SplitIntegrityError, match="gate0_integrity_failed"):
        split.verify_production_boundary()


def test_production_boundary_report_is_aggregate_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(split, "verify_gate0", lambda: None)

    class Settings:
        pass

    monkeypatch.setattr("natural_flow_rag.settings.load_settings", lambda: Settings())
    monkeypatch.setattr(
        "scripts.compare_reindex_plan.load_current_records",
        lambda settings: ([{"id": "x", "metadata": {"doc_type": "evaluation_case"}}], None),
    )
    monkeypatch.setattr("scripts.compare_reindex_plan.load_bm25_ids", lambda settings: ["x"])
    report = split.verify_production_boundary()
    assert report["verdict"] == "fail"
    assert "evaluation_record_in_chroma" in report["findings"]
    assert "query_text" not in json.dumps(report)
