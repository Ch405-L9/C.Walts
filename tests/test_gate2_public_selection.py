from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import jsonschema
import pytest
import yaml

from scripts import build_gate2_public_candidates as selector
from scripts import verify_eval_acquisition as acquisition

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config/gate2_public_selection_policy.yaml"
SCHEMA = ROOT / "schemas/gate2_public_selection_policy.schema.json"


def load_policy() -> dict:
    data = yaml.safe_load(POLICY.read_text())
    jsonschema.validate(data, json.loads(SCHEMA.read_text()))
    return data


def test_gate2_policy_is_complete_and_pre_split() -> None:
    policy = load_policy()
    assert policy["quotas"]["public_total"] == 315
    assert policy["provenance_kind"] == "public_verbatim"
    assert policy["no_split"] is True
    assert (
        sum(sum(value.values()) for key, value in policy["quotas"].items() if key != "public_total")
        == 315
    )
    assert policy["acquisition_to_allocation"]["clinc150_oos"] == "clinc150"


def test_label_maps_are_complete_against_local_metadata() -> None:
    policy = load_policy()
    inventory = selector.structure()
    assert set(policy["label_policy"]["clinc150"]) == {
        label
        for part in ("train", "val", "test")
        for label in inventory["clinc150"]["partitions"][part]
    }
    assert set(policy["label_policy"]["massive_1_0_en_us"]) == set(
        inventory["massive_1_0_en_us"]["counts"]["intent"]
    )
    assert set(policy["label_policy"]["banking77"]) == set(
        inventory["banking77"]["train"]["category_counts"]
    )
    assert set(policy["label_policy"]["clinc150_oos"]) == {"oos_train", "oos_val", "oos_test"}
    for dataset, mapping in policy["expected_behavior_by_label"].items():
        eligible = {
            label
            for label, disposition in policy["label_policy"][dataset].items()
            if disposition != "ineligible_for_gate2_public"
        }
        assert set(mapping) == eligible


def test_license_and_partition_contract() -> None:
    registry = json.loads((ROOT / "config/approved_eval_datasets.json").read_text())
    assert registry["datasets"]["clinc150"]["license"] == "CC-BY-3.0"
    assert registry["datasets"]["massive_1_0_en_us"]["license"] == "CC-BY-4.0"
    assert registry["datasets"]["banking77"]["license"] == "CC-BY-4.0"
    assert load_policy()["partition_policy"] == {
        "clinc150": ["train", "val", "test"],
        "massive_1_0_en_us": ["train", "dev", "test"],
        "banking77": ["train", "test"],
    }


def test_acquisition_verification_is_read_only() -> None:
    assert acquisition.main.__name__ == "main"
    result = __import__("subprocess").run(
        [str(ROOT / ".venv/bin/python"), "scripts/verify_eval_acquisition.py", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "pass"
    assert payload["mutation_performed"] is False
    assert payload["network_used"] is False


def test_group_and_id_contract() -> None:
    policy = load_policy()
    assert policy["id_namespace"]["pattern"] == r"^CWQ-PUB-[0-9]{4}$"
    assert policy["group_policy"]["format"] == "G2-<dataset-short>-<sha256-prefix>"
    assert (
        hashlib.sha256(POLICY.read_bytes()).hexdigest()
        == hashlib.sha256(POLICY.read_bytes()).hexdigest()
    )


def test_selector_has_no_retrieval_dependencies_or_query_mode() -> None:
    source = (ROOT / "scripts/build_gate2_public_candidates.py").read_text()
    for forbidden in (
        "Retriever",
        "VectorStore",
        "LexicalIndex",
        "OllamaEmbedder",
        "query(",
        "search(",
    ):
        assert forbidden not in source
    result = __import__("subprocess").run(
        [str(ROOT / ".venv/bin/python"), "scripts/build_gate2_public_candidates.py", "--select"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "reserved_for_gate2_b" in result.stderr + result.stdout


def test_source_text_is_not_in_policy_or_schema() -> None:
    for path in (POLICY, SCHEMA):
        text = path.read_text()
        assert "query_text:" not in text
        assert not re.search(r"\b(what|how|why|where)\s+\w+\s+\w+", text, re.IGNORECASE)


@pytest.mark.parametrize(
    "class_name,behavior",
    [
        ("near_domain_unsupported", "request_clarification"),
        ("far_out_of_domain", "abstain"),
        ("ambiguous_adversarial_insufficient", "request_clarification"),
    ],
)
def test_expected_behavior_is_frozen_by_class(class_name: str, behavior: str) -> None:
    assert load_policy()["expected_behavior"][class_name] == behavior
