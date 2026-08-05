from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts import activate_stage2 as activation


def record(
    chunk_id: str,
    text: str,
    *,
    source_id: str = "stage2",
    doc_type: str = "approved_example",
    section_heading: str = "Example",
) -> dict[str, Any]:
    return {
        "id": chunk_id,
        "text": text,
        "metadata": {
            "source_id": source_id,
            "source_path": f"corpus/raw/{source_id}/approved_examples.md",
            "doc_type": doc_type,
            "section_heading": section_heading,
            "chunk_profile": "approved_example",
            "embedding_model": "nomic-embed-text",
            "embedding_dimension": 768,
        },
    }


def args(tmp_path: Path, **overrides: Any) -> argparse.Namespace:
    values = {
        "expected_current_count": 1,
        "expected_final_count": 2,
        "expected_b2r1_sha256": "accepted",
        "expected_plan": None,
        "expected_new_id": ["new_0"],
        "expected_new_ids_json": None,
        "expected_head": "head",
        "backup_path": str(tmp_path / "backup"),
        "harness_baseline": str(tmp_path / "harness.json"),
        "journal_path": tmp_path / "journal.json",
        "confirm_stage2_activation": True,
        "output_json": str(tmp_path / "out.json"),
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def fake_settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        project_root=tmp_path,
        embedding=SimpleNamespace(
            model=activation.EXPECTED_EMBEDDING_MODEL,
            model_digest=activation.EXPECTED_EMBEDDING_DIGEST,
            vector_dimension=activation.EXPECTED_EMBEDDING_DIMENSION,
        ),
    )


def test_preflight_plan_reports_exact_additions_without_mutation() -> None:
    current = [record("old_0", "old")]
    final = [record("old_0", "old"), record("new_0", "new")]

    plan = activation.compare_plan(
        current_records=current,
        final_records=final,
        current_bm25_ids=["old_0"],
        proposed_bm25_ids=["old_0", "new_0"],
        expected_new_ids=["new_0"],
    )

    assert plan["verdict"] == "pass"
    assert plan["would_add_ids"] == ["new_0"]
    assert plan["unchanged_ids"] == ["old_0"]
    assert plan["stale_ids"] == []


@pytest.mark.parametrize(
    ("current", "final", "current_bm25", "proposed_bm25", "expected", "finding"),
    [
        (
            [record("old_0", "old")],
            [record("old_0", "old"), record("other_0", "new")],
            ["old_0"],
            ["old_0", "other_0"],
            ["new_0"],
            "unexpected_would_add_ids",
        ),
        (
            [record("new_0", "already")],
            [record("new_0", "already")],
            ["new_0"],
            ["new_0"],
            ["new_0"],
            "unexpected_would_add_ids",
        ),
        (
            [record("stale_0", "old")],
            [record("new_0", "new")],
            ["stale_0"],
            ["new_0"],
            ["new_0"],
            "stale_ids",
        ),
        (
            [record("same_0", "old")],
            [record("same_0", "new")],
            ["same_0"],
            ["same_0"],
            [],
            "existing_document_drift",
        ),
        (
            [record("same_0", "same")],
            [record("same_0", "same", section_heading="Changed")],
            ["same_0"],
            ["same_0"],
            [],
            "existing_metadata_drift",
        ),
        (
            [record("old_0", "old")],
            [record("dup_0", "one"), record("dup_0", "two")],
            ["old_0"],
            ["dup_0"],
            ["dup_0"],
            "duplicate_ids",
        ),
        (
            [record("old_0", "old")],
            [record("one_0", "same"), record("two_0", "same")],
            ["old_0"],
            ["one_0", "two_0"],
            ["one_0", "two_0"],
            "duplicate_canonical_content",
        ),
        (
            [record("old_0", "old")],
            [record("old_0", "old"), record("new_0", "new", doc_type="evaluation_case")],
            ["old_0"],
            ["old_0", "new_0"],
            ["new_0"],
            "evaluation_case_leakage",
        ),
        (
            [record("old_0", "old")],
            [record("old_0", "old"), record("new_0", "new")],
            [],
            ["old_0", "new_0"],
            ["new_0"],
            "current_parity_mismatch",
        ),
        (
            [record("old_0", "old")],
            [record("old_0", "old"), record("new_0", "new")],
            ["old_0"],
            ["old_0"],
            ["new_0"],
            "temporary_bm25_parity_mismatch",
        ),
    ],
)
def test_plan_refuses_activation_hazards(
    current: list[dict[str, Any]],
    final: list[dict[str, Any]],
    current_bm25: list[str],
    proposed_bm25: list[str],
    expected: list[str],
    finding: str,
) -> None:
    plan = activation.compare_plan(
        current_records=current,
        final_records=final,
        current_bm25_ids=current_bm25,
        proposed_bm25_ids=proposed_bm25,
        expected_new_ids=expected,
    )

    assert plan["verdict"] == "fail"
    assert finding in plan["findings"]


def test_validate_common_refuses_wrong_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = fake_settings(tmp_path)
    plan = {
        "verdict": "pass",
        "findings": [],
        "would_add_ids": ["new_0"],
    }
    monkeypatch.setattr(
        activation,
        "git_value",
        lambda command: "wrong" if command[-1] == "--show-current" else "not-head",
    )
    monkeypatch.setattr(
        activation, "git_clean_tracked", lambda: (False, [" M config/sources.yaml"])
    )
    monkeypatch.setattr(activation, "version", lambda: "0.4.0-dev.2")
    monkeypatch.setattr(
        activation,
        "source_manifest_summary",
        lambda _path: {"approved_source_count": 5, "approved_source_ids": []},
    )
    monkeypatch.setattr(activation, "sha256_file", lambda _path: "wrong")

    findings = activation.validate_common(
        args(tmp_path),
        settings=settings,
        current_records=[],
        current_bm25_ids=[],
        final_records=[record("new_0", "new")],
        plan=plan,
    )

    assert "wrong_branch" in findings
    assert "wrong_head" in findings
    assert "wrong_version" in findings
    assert any(item.startswith("dirty_tracked_state") for item in findings)
    assert "starting_chroma_count_mismatch" in findings
    assert "starting_bm25_count_mismatch" in findings
    assert "final_record_count_mismatch" in findings
    assert "approved_source_count_mismatch" in findings
    assert "stage2_sources_missing" in findings
    assert "b2r1_sha256_mismatch" in findings


def test_activation_refuses_without_confirmation(tmp_path: Path) -> None:
    with pytest.raises(activation.ActivationError, match="confirm"):
        activation.activate(args(tmp_path, confirm_stage2_activation=False))


def test_activation_refuses_without_write_authorization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("NFR_ALLOW_WRITES", raising=False)

    with pytest.raises(activation.ActivationError, match="NFR_ALLOW_WRITES"):
        activation.activate(args(tmp_path))


def test_incomplete_journal_blocks_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NFR_ALLOW_WRITES", "true")
    journal = tmp_path / "journal.json"
    journal.write_text(json.dumps({"phase": "chroma_write_started"}), encoding="utf-8")

    with pytest.raises(activation.ActivationError, match="incomplete activation journal"):
        activation.activate(args(tmp_path, journal_path=journal))


def install_success_fakes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    embed_error: Exception | None = None,
    add_error: Exception | None = None,
    bm25_error: Exception | None = None,
) -> dict[str, Any]:
    calls: dict[str, Any] = {
        "embedded_texts": [],
        "added_ids": [],
        "deleted": False,
        "bm25_replaced_after_add": None,
    }
    current = [record("old_0", "old", source_id="existing")]
    final = [record("old_0", "old", source_id="existing"), record("new_0", "new")]
    live_after = list(final)
    settings = fake_settings(tmp_path)
    bm25_path = tmp_path / "tmp-bm25" / "index.json"
    bm25_path.parent.mkdir(parents=True, exist_ok=True)
    bm25_path.write_text(json.dumps({"chunk_ids": ["old_0", "new_0"]}), encoding="utf-8")

    monkeypatch.setattr(activation, "load_settings", lambda: settings)
    load_calls = {"count": 0}

    def fake_load_current(_settings: Any):
        load_calls["count"] += 1
        return (current if load_calls["count"] == 1 else live_after), {}

    monkeypatch.setattr(activation, "load_current_records", fake_load_current)
    monkeypatch.setattr(activation, "load_bm25_ids", lambda _settings: ["old_0"])
    monkeypatch.setattr(activation, "build_source_records", lambda _settings: final)
    monkeypatch.setattr(
        activation, "build_isolated_bm25", lambda _records, _parent: (bm25_path, ["old_0", "new_0"])
    )
    monkeypatch.setattr(activation, "validate_common", lambda *_a, **_kw: [])
    monkeypatch.setattr(activation, "find_incomplete_journals", lambda _path=None: [])

    class FakeEmbedder:
        def __init__(self, _config: Any) -> None:
            pass

        def probe(self) -> SimpleNamespace:
            return SimpleNamespace(
                model=activation.EXPECTED_EMBEDDING_MODEL,
                dimension=activation.EXPECTED_EMBEDDING_DIMENSION,
                normalized=True,
                l2_norm=1.0,
            )

        def embed(self, texts: list[str]) -> list[list[float]]:
            calls["embedded_texts"] = list(texts)
            if embed_error is not None:
                raise embed_error
            return [[0.0] * activation.EXPECTED_EMBEDDING_DIMENSION for _ in texts]

    class FakeStore:
        def __init__(self, _settings: Any) -> None:
            self.count_calls = 0

        def count(self) -> int:
            self.count_calls += 1
            return 1 if self.count_calls == 1 else 2

        def add(
            self,
            *,
            ids: list[str],
            embeddings: list[list[float]],
            documents: list[str],
            metadatas: list[dict[str, Any]],
        ) -> None:
            calls["added_ids"] = list(ids)
            assert len(embeddings) == len(documents) == len(metadatas) == 1
            if add_error is not None:
                raise add_error

        def delete(
            self, *_args: Any, **_kwargs: Any
        ) -> None:  # pragma: no cover - called only on failure
            calls["deleted"] = True

    class FakeLexical:
        def __init__(self, _path: Path) -> None:
            self.chunk_ids = ["old_0", "new_0"]

        def load(self) -> None:
            pass

    def fake_atomic(_staged: Path, _live: Path) -> None:
        calls["bm25_replaced_after_add"] = bool(calls["added_ids"])
        if bm25_error is not None:
            raise bm25_error

    monkeypatch.setattr(activation, "OllamaEmbedder", FakeEmbedder)
    monkeypatch.setattr(activation, "VectorStore", FakeStore)
    monkeypatch.setattr(activation, "LexicalIndex", FakeLexical)
    monkeypatch.setattr(activation, "atomic_replace_bm25", fake_atomic)
    monkeypatch.setattr(
        activation,
        "verify_only",
        lambda _args: {"verdict": "pass", "findings": [], "mutation_performed": False},
    )
    monkeypatch.setenv("NFR_ALLOW_WRITES", "true")
    return calls


def test_successful_activation_embeds_and_writes_only_the_twelve_delta_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = install_success_fakes(tmp_path, monkeypatch)

    report = activation.activate(args(tmp_path))

    assert report["verdict"] == "pass"
    assert report["mutation_performed"] is True
    assert calls["embedded_texts"] == ["new"]
    assert calls["added_ids"] == ["new_0"]
    assert calls["deleted"] is False
    assert calls["bm25_replaced_after_add"] is True


def test_embedding_failure_leaves_chroma_and_bm25_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = install_success_fakes(tmp_path, monkeypatch, embed_error=RuntimeError("embed down"))

    with pytest.raises(RuntimeError, match="embed down"):
        activation.activate(args(tmp_path))

    assert calls["added_ids"] == []
    assert calls["bm25_replaced_after_add"] is None


def test_chroma_failure_leaves_bm25_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = install_success_fakes(tmp_path, monkeypatch, add_error=RuntimeError("chroma down"))

    with pytest.raises(RuntimeError, match="chroma down"):
        activation.activate(args(tmp_path))

    assert calls["added_ids"] == ["new_0"]
    assert calls["bm25_replaced_after_add"] is None


def test_bm25_stage_failure_occurs_after_chroma_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = install_success_fakes(tmp_path, monkeypatch, bm25_error=RuntimeError("bm25 down"))

    with pytest.raises(RuntimeError, match="bm25 down"):
        activation.activate(args(tmp_path))

    assert calls["added_ids"] == ["new_0"]
    assert calls["bm25_replaced_after_add"] is True


def test_verify_only_performs_no_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = fake_settings(tmp_path)
    final = [record("old_0", "old", source_id="existing"), record("new_0", "new")]
    monkeypatch.setattr(activation, "load_settings", lambda: settings)
    monkeypatch.setattr(activation, "load_current_records", lambda _settings: (final, {}))
    monkeypatch.setattr(activation, "load_bm25_ids", lambda _settings: ["old_0", "new_0"])
    monkeypatch.setattr(activation, "build_source_records", lambda _settings: final)

    report = activation.verify_only(args(tmp_path, expected_current_count=2))

    assert report["verdict"] == "pass"
    assert report["mutation_performed"] is False
