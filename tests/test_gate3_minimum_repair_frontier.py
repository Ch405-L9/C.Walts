from __future__ import annotations

from pathlib import Path

from scripts import diagnose_gate3_minimum_repair_frontier as diagnostic


def test_mask_order_and_singleton_unlocking() -> None:
    state = {
        "singleton_slots": ["A", "B", "C"],
        "available": {"A": {"primary"}, "B": {"primary"}, "C": {"primary"}},
        "slot_ids": ["A", "B", "C"],
    }
    results = diagnostic._mask_results(state, set())
    assert list(results) == [f"{n:03b}" for n in range(8)]
    assert results["001"]["unlocked_slots"] == ["C"]
    assert results["100"]["unlocked_slots"] == ["A"]


def test_scc_contradictory_slot_extraction() -> None:
    slots = ["A", "B"]
    roles = {"A": {"primary"}, "B": {"primary", "replacement"}}
    edges = [("A", "primary", "B", "primary")]
    assert diagnostic._scc_contradictions(slots, edges, roles) == []
    cycle = edges + [("A", "primary", "B", "replacement")]
    assert diagnostic._scc_contradictions(slots, cycle, roles) == ["A", "B"]


def test_outputs_are_sanitized_and_bundle_shape(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(diagnostic, "OUTPUT_DIR", tmp_path)
    result = {
        "matrix": {"exact_only": {}, "augmented": {}},
        "topology": {"x": 1},
        "summary": {"y": 2},
    }
    diagnostic.write_outputs(result)
    assert all("query_text" not in path.read_text() for path in tmp_path.glob("*.json"))


def test_no_generation_symbols_in_diagnostic() -> None:
    source = Path(diagnostic.__file__).read_text()
    assert "model_request" not in source
    assert "ollama" not in source.lower()
