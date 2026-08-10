from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import verify_holdout_anchor as anchor


def _seal(tmp_path: Path, state: str = "sealed_unused") -> Path:
    seal_dir = tmp_path / "sealed"
    seal_dir.mkdir()
    seal = {
        "split_identity_sha256": "a" * 64,
        "immutable_identity": {
            "benchmark_version": "synthetic-v1",
            "algorithm_id": "group-stratified-exact-subset-v1",
        },
        "lifecycle": {"state": state, "events": []},
    }
    for name, payload in (
        ("candidate_manifest.json", {}),
        ("split_manifest.json", {}),
        ("seal.json", seal),
    ):
        (seal_dir / name).write_text(json.dumps(payload), encoding="utf-8")
    return seal_dir / "seal.json"


def _allow_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(anchor, "verify_seal", lambda *args, **kwargs: None)


def test_anchor_hash_excludes_only_self_hash() -> None:
    value = {"schema_version": 1, "anchor_sha256": "ignored"}
    assert anchor.anchor_hash(value) == anchor.sha256_value({"schema_version": 1})


def test_unauthorized_anchor_write_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_verify(monkeypatch)
    with pytest.raises(anchor.AnchorError, match="write_authorization_required"):
        anchor.write_anchor(_seal(tmp_path), tmp_path / "external")


def test_anchor_write_requires_confirmation_at_cli_boundary() -> None:
    assert "--confirm-anchor-write" in Path("scripts/verify_holdout_anchor.py").read_text()


def test_anchor_payload_has_no_sensitive_membership_fields() -> None:
    text = Path("schemas/holdout_anchor.schema.json").read_text()
    for forbidden in ("query_text", "query_id", "group_id", "membership", "qrels", "scores"):
        assert forbidden not in text


def test_synthetic_anchor_chain_verifies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_verify(monkeypatch)
    seal_path = _seal(tmp_path)
    root = tmp_path / "external"
    monkeypatch.setenv("NFR_ALLOW_EVAL_WRITES", "true")
    anchor.write_anchor(seal_path, root)
    result = anchor.verify_chain(seal_path, root)
    assert result["verdict"] == "pass"
    assert result["mutation_performed"] is False


def test_split_identity_mutation_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_verify(monkeypatch)
    seal_path = _seal(tmp_path)
    root = tmp_path / "external"
    monkeypatch.setenv("NFR_ALLOW_EVAL_WRITES", "true")
    anchor.write_anchor(seal_path, root)
    path = root / "0001.json"
    data = json.loads(path.read_text())
    data["split_identity_sha256"] = "b" * 64
    data["anchor_sha256"] = anchor.anchor_hash(data)
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(anchor.AnchorError, match="anchor_split_identity_mismatch"):
        anchor.verify_chain(seal_path, root)


def test_anchor_root_inside_seal_directory_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_verify(monkeypatch)
    seal_path = _seal(tmp_path)
    monkeypatch.setenv("NFR_ALLOW_EVAL_WRITES", "true")
    with pytest.raises(anchor.AnchorError, match="anchor_root_inside_seal_directory"):
        anchor.write_anchor(seal_path, seal_path.parent / "anchors")
