from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import yaml

from natural_flow_rag.chunking import count_tokens
from natural_flow_rag.schemas import sha256_text
from scripts.validate_stage2_candidates import (
    PASSAGE_NORMALIZATION,
    validate_candidates,
)


def write_fixture(tmp_path: Path, records: list[dict]) -> tuple[Path, Path]:
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir(exist_ok=True)
    paragraphs = "\n".join(
        f"<p>Candidate {index:02d} exact source sentence for validation.</p>"
        for index in range(1, 14)
    )
    snapshot = snapshots / "source.xml"
    snapshot.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<article>
  <front />
  <body>
    <sec>
      <title>Body</title>
      {paragraphs}
    </sec>
  </body>
</article>
""",
        encoding="utf-8",
    )
    checksum = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    manifest = tmp_path / "stage2_public_sources.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "sources": [
                    {
                        "source_id": "source-a",
                        "local_snapshot_path": "snapshots/source.xml",
                        "checksum": checksum,
                        "doi": "10.1000/source-a",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    candidates = tmp_path / "stage2_candidates.jsonl"
    candidates.write_text(
        "".join(f"{json.dumps(record, sort_keys=True)}\n" for record in records),
        encoding="utf-8",
    )
    return candidates, manifest


def candidate(candidate_id: str, family: str, paragraph: int, **overrides) -> dict:
    passage = f"Candidate {paragraph:02d} exact source sentence for validation."
    record = {
        "candidate_id": candidate_id,
        "family": family,
        "category": family,
        "exact_structure": "structure",
        "source_id": "source-a",
        "stable_article_identifier": "doi:10.1000/source-a",
        "exact_section": "Body",
        "subsection": "",
        "paragraph_ordinal": paragraph,
        "sentence_ordinal": 1,
        "deterministic_offset": f"body/sec[1]/p[{paragraph}]/s[1]",
        "first_identifying_words": "Candidate",
        "last_identifying_words": "validation.",
        "source_passage": passage,
        "source_passage_normalization": PASSAGE_NORMALIZATION,
        "source_passage_sha256": sha256_text(passage),
        "source_token_count": count_tokens(passage),
        "protected_facts": ["fact"],
        "protected_terminology": [],
        "protected_numbers_units": [],
        "protected_dates": [],
        "protected_identifiers_version_strings": [],
        "protected_negation": [],
        "protected_obligation_modality": [],
        "protected_certainty_uncertainty": [],
        "protected_conditions_exceptions_scope_limits": [],
        "factual_corruption_risk": "low",
        "spoken_delivery_risk": "low",
        "factual_preservation_review_criteria": ["preserve fact"],
        "spoken_delivery_review_criteria": ["read clearly"],
        "why_fits_structure": "fits",
        "why_not_generic": "specific",
        "dense_structure_evidence": {},
        "status_update_evidence": [],
        "eval009_accessed": False,
        "holdout_accessed": False,
        "final_rewrite_authored": False,
    }
    record.update(overrides)
    return record


def valid_records() -> list[dict]:
    families = [
        "dense",
        "dense",
        "dense",
        "dense",
        "procedural",
        "procedural",
        "numeric",
        "numeric",
        "identifier_date",
        "identifier_date",
        "technical_status",
        "technical_status",
    ]
    return [
        candidate(f"ST2-CAND-{index:03d}", family, index)
        for index, family in enumerate(families, start=1)
    ]


def validate(tmp_path: Path, records: list[dict]) -> dict:
    candidates, manifest = write_fixture(tmp_path, records)
    return validate_candidates(
        candidates,
        manifest,
        project_root=tmp_path,
        approved_roots=[tmp_path / "snapshots"],
        repository_commit="abc123",
    )


def codes(report: dict) -> set[str]:
    return {error["code"] for error in report["errors"]}


def test_valid_twelve_record_file_passes(tmp_path: Path) -> None:
    report = validate(tmp_path, valid_records())

    assert report["verdict"] == "pass"
    assert report["candidate_record_count"] == 12
    assert report["actual_allocation"] == report["expected_allocation"]


def test_missing_candidate_fails(tmp_path: Path) -> None:
    report = validate(tmp_path, valid_records()[:-1])

    assert "candidate_count_mismatch" in codes(report)
    assert "candidate_id_set_mismatch" in codes(report)


def test_thirteenth_record_fails(tmp_path: Path) -> None:
    records = valid_records()
    records.append(candidate("ST2-CAND-013", "dense", 13))

    report = validate(tmp_path, records)

    assert "candidate_count_mismatch" in codes(report)
    assert "candidate_id_set_mismatch" in codes(report)


def test_duplicate_candidate_id_fails(tmp_path: Path) -> None:
    records = valid_records()
    records[1]["candidate_id"] = records[0]["candidate_id"]

    report = validate(tmp_path, records)

    assert "duplicate_candidate_id" in codes(report)


def test_wrong_family_allocation_fails(tmp_path: Path) -> None:
    records = valid_records()
    records[0]["family"] = "numeric"

    report = validate(tmp_path, records)

    assert "allocation_mismatch" in codes(report)


def test_source_passage_mismatch_fails(tmp_path: Path) -> None:
    records = valid_records()
    records[0]["source_passage"] = "Different source sentence."
    records[0]["source_passage_sha256"] = sha256_text(records[0]["source_passage"])
    records[0]["source_token_count"] = count_tokens(records[0]["source_passage"])

    report = validate(tmp_path, records)

    assert "source_passage_mismatch" in codes(report)


def test_unresolved_locator_fails(tmp_path: Path) -> None:
    records = valid_records()
    records[0]["paragraph_ordinal"] = 99

    report = validate(tmp_path, records)

    assert "unresolved_locator" in codes(report)


def test_checksum_mismatch_fails(tmp_path: Path) -> None:
    candidates, manifest = write_fixture(tmp_path, valid_records())
    payload = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    payload["sources"][0]["checksum"] = "0" * 64
    manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    report = validate_candidates(
        candidates,
        manifest,
        project_root=tmp_path,
        approved_roots=[tmp_path / "snapshots"],
        repository_commit="abc123",
    )

    assert "checksum_mismatch" in codes(report)


def test_incorrect_passage_hash_fails(tmp_path: Path) -> None:
    records = valid_records()
    records[0]["source_passage_sha256"] = "0" * 64

    report = validate(tmp_path, records)

    assert "passage_hash_mismatch" in codes(report)


def test_incorrect_token_count_fails(tmp_path: Path) -> None:
    records = valid_records()
    records[0]["source_token_count"] += 1

    report = validate(tmp_path, records)

    assert "token_count_mismatch" in codes(report)


def test_true_eval_holdout_or_final_rewrite_flag_fails(tmp_path: Path) -> None:
    for field in ("eval009_accessed", "holdout_accessed", "final_rewrite_authored"):
        records = valid_records()
        records[0][field] = True

        report = validate(tmp_path, records)

        assert "safety_flag_not_false" in codes(report)


def test_undeclared_text_normalization_fails(tmp_path: Path) -> None:
    records = valid_records()
    records[0].pop("source_passage_normalization")

    report = validate(tmp_path, records)

    assert "undeclared_text_normalization" in codes(report)


def test_missing_source_fails(tmp_path: Path) -> None:
    records = valid_records()
    records[0]["source_id"] = "missing-source"

    report = validate(tmp_path, records)

    assert "missing_source" in codes(report)


def test_final_rewrite_text_field_fails(tmp_path: Path) -> None:
    records = deepcopy(valid_records())
    records[0]["target_text"] = "This would be a final rewrite."

    report = validate(tmp_path, records)

    assert "final_rewrite_field_present" in codes(report)
