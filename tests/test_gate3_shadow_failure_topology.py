from __future__ import annotations

from pathlib import Path

from scripts import diagnose_gate3_shadow_pairs as diagnostics
from scripts import reconcile_gate3_shadow_failure_topology as topology


def test_reconciliation_reuses_committed_shadow_mapping_and_corrects_accounting(
    tmp_path: Path,
) -> None:
    source = Path(diagnostics.__file__).read_text(encoding="utf-8")
    assert "def shadow_slots" in source
    result = topology.reconcile(topology.DIAGNOSTIC)
    assert result["actual_primary_success_count"] == 285
    assert result["actual_replacement_success_count"] == 260
    assert result["actual_successful_role_count"] == 545
    assert result["terminal_primary_failure_count"] == 0
    assert result["terminal_replacement_failure_count"] == 25
    assert result["failed_shadow_slot_count"] == 25
    assert result["failure_topology_classification"] == "BROAD_ROLE_DIVERSITY_FAILURE"


def test_reconciliation_accounting_and_denominators() -> None:
    result = topology.reconcile()
    assert result["terminal_failure_retry_contribution"] == 50
    assert result["recovered_duplicate_retry_contribution"] == 15
    assert result["retry_arithmetic"] == "50 + 15 = 65"
    assert sum(item["total_slots"] for item in result["class_distribution"].values()) == 285
    assert sum(item["failed_slots"] for item in result["class_distribution"].values()) == 25
    for key in ("task_family_distribution", "scenario_family_distribution"):
        assert sum(item["failed_slots"] for item in result[key].values()) == 25


def test_reconciliation_is_sanitized_and_does_not_define_model_calls() -> None:
    source = Path(topology.__file__).read_text(encoding="utf-8")
    assert "model_request" not in source
    assert '"query_text":' not in source
    assert '"raw_response":' not in source
    result = topology.reconcile()
    assert result["ollama_model_calls"] == 0
    assert result["shadow_generation_replay_count"] == 0
    assert result["query_text_recorded"] is False
    assert result["raw_response_recorded"] is False


def test_failed_ids_resolve_once_and_historical_pool_is_preserved() -> None:
    result = topology.reconcile()
    assert result["failed_shadow_slot_count"] == 25
    assert result["canonical_pool_present"] is False
    assert result["canonical_manifest_present"] is False
    assert Path("var/eval_sources/custom/drafts/gate3_private_draft_pool.json").exists()
    assert not Path("var/eval_sources/custom/selected/gate3_custom_candidates.json").exists()


def test_bundle_has_exact_sanitized_shape(tmp_path: Path, monkeypatch) -> None:
    result = topology.reconcile()
    bundle = tmp_path / "bundle.zip"
    monkeypatch.setattr(topology, "BUNDLE", bundle)
    topology.write_bundle(result, commit="synthetic")
    import zipfile

    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        assert len(names) == 11
        assert names.count("SHA256SUMS") == 1
        assert all('"query_text":' not in archive.read(name).decode("utf-8") for name in names)
        assert all('"raw_response":' not in archive.read(name).decode("utf-8") for name in names)
