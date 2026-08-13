from __future__ import annotations

from pathlib import Path

from scripts import diagnose_gate3_minimum_global_supplements as diagnostic


def _search(edges, available):
    search = diagnostic.DeletionSearch(sorted(available), set(edges), available)
    return search


def test_zero_repair_sat() -> None:
    search = _search([], {"A": {"primary", "replacement"}})
    result = search.run(0)
    assert result["solutions"] == [()]


def test_one_repair_unsat_formula() -> None:
    available = {"A": {"primary", "replacement"}, "B": {"primary", "replacement"}}
    edges = [
        (left, role_left, right, role_right)
        for left, right in (("A", "B"),)
        for role_left in ("primary", "replacement")
        for role_right in ("primary", "replacement")
    ]
    search = _search(edges, available)
    assert not search.run(0)["solutions"]
    assert search.run(1)["solutions"]


def test_two_independent_repairs_and_minimality() -> None:
    available = {slot: {"primary", "replacement"} for slot in ("A", "B", "C", "D")}
    edges = [
        (left, role_left, right, role_right)
        for left, right in (("A", "B"), ("C", "D"))
        for role_left in ("primary", "replacement")
        for role_right in ("primary", "replacement")
    ]
    search = _search(edges, available)
    assert not search.run(0)["solutions"]
    assert not search.run(1)["solutions"]
    assert search.run(2)["solutions"]


def test_non_contradictory_core_member_is_branchable() -> None:
    available = {slot: {"primary", "replacement"} for slot in ("A", "B")}
    edges = [
        (left, role_left, right, role_right)
        for left, right in (("A", "B"),)
        for role_left in ("primary", "replacement")
        for role_right in ("primary", "replacement")
    ]
    search = _search(edges, available)
    assert any("A" in solution or "B" in solution for solution in search.run(1)["solutions"])


def test_singleton_unit_is_removed_with_slot() -> None:
    available = {"A": {"primary"}, "B": {"primary", "replacement"}}
    edges = [("A", "primary", "B", role) for role in ("primary", "replacement")]
    search = _search(edges, available)
    assert search.run(0)["solutions"] == []
    assert search.run(1)["solutions"]


def test_outputs_are_sanitized() -> None:
    source = Path(diagnostic.__file__).read_text()
    assert "model_request" not in source
    assert "ollama" not in source.lower()
    assert "print(query" not in source
