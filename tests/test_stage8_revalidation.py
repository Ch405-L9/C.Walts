from __future__ import annotations

import json
from pathlib import Path

from scripts.verify_gate1_2_exit import evaluate_round, load_protocol, load_taxonomy, sha256

ROOT = Path(__file__).resolve().parents[1]


def test_frozen_protocol_contract():
    protocol = load_protocol()
    assert protocol["retrieval_k"] == 5
    assert protocol["rounds"] == 3
    assert [p["id"] for p in protocol["probes"]] == [
        "S8-DENSE-01", "S8-DENSE-02", "S8-DENSE-03", "S8-DENSE-04"
    ]
    assert protocol["tuning_permitted"] is False


def test_protocol_has_stable_hash():
    path = ROOT / "config" / "stage8_dense_coverage_probes.yaml"
    assert len(sha256(path)) == 64


def test_taxonomy_has_independence_groups():
    taxonomy = load_taxonomy()
    assert taxonomy
    assert all(row.get("independence_group") for row in taxonomy.values())


def test_closure_requires_two_independent_primary_groups():
    hit_a = {"qualifying": True, "independence_group": "a", "evaluation_case": False}
    hit_b = {"qualifying": True, "independence_group": "b", "evaluation_case": False}
    passing = [[hit_a], [hit_b], [hit_a], [hit_b]]
    assert evaluate_round(passing)["passed"] is True
    failing = [[hit_a]] * 4
    assert evaluate_round(failing)["passed"] is False


def test_exit_schema_is_strict():
    schema = json.loads((ROOT / "schemas" / "gate1_2_exit.schema.json").read_text())
    assert schema["additionalProperties"] is False
    assert "STAGE8_PASS_GATE1_2_EXIT_BLOCKED" in schema["properties"]["final_owner_result"]["enum"]
