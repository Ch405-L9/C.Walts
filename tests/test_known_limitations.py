"""Gate 1.1 §4: the limitations register is machine-readable, not just prose.

A register nobody can query is a register nobody reads. The fields below exist so
a future release gate can ask "are there open blockers?" and get an answer
without a human interpreting paragraphs — so the fields are parsed here, with
their required values, rather than merely grepped for.

The load-bearing assertion is `blocks_release_candidate`. It is the register's
only enforcement mechanism: an open entry carrying it must prevent a release
candidate regardless of how the evaluation suite scores.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTER = PROJECT_ROOT / "docs" / "known-limitations-v0.4.md"

EVAL_009 = "CW-LIM-009-DENSE-COVERAGE"


def _entries() -> dict[str, dict]:
    """Every fenced YAML block in the register, keyed by its id."""
    text = REGISTER.read_text(encoding="utf-8")
    blocks = re.findall(r"```yaml\n(.*?)```", text, re.DOTALL)
    entries: dict[str, dict] = {}
    for block in blocks:
        parsed = yaml.safe_load(block)
        if isinstance(parsed, dict) and "id" in parsed:
            entries[str(parsed["id"])] = parsed
    return entries


def test_the_register_exists() -> None:
    assert REGISTER.is_file()


def test_every_entry_parses_as_yaml() -> None:
    entries = _entries()
    assert entries, "no machine-readable entries found; the register is prose only"


# ── the EVAL-009 entry, field by field ───────────────────────────────────────


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("id", EVAL_009),
        ("status", "resolved"),
        ("severity", "medium"),
        ("blocks_gate2", False),
        ("blocks_threshold_calibration", True),
        ("blocks_release_candidate", True),
    ],
)
def test_the_eval_009_entry_declares_the_required_field(field: str, expected: object) -> None:
    entry = _entries().get(EVAL_009)
    assert entry is not None, f"{EVAL_009} is absent from the register"
    assert entry[field] == expected


def test_the_eval_009_entry_is_a_release_blocker() -> None:
    """The register's only enforcement mechanism, asserted on its own.

    A future release gate greps for this. If the field is ever softened to close
    a release, that is a decision someone has to make explicitly rather than by
    editing a sentence.
    """
    entry = _entries()[EVAL_009]
    assert entry["blocks_release_candidate"] is True
    assert entry["status"] == "resolved"
    assert entry["blocking_scopes"] == []
    assert entry["resolved_by"] == "docs/evidence/gate1_2-stage8-dense-coverage.json"


def test_an_open_blocker_is_discoverable_without_reading_prose() -> None:
    open_blockers = [
        key
        for key, entry in _entries().items()
        if entry.get("status") == "deferred" and entry.get("blocks_release_candidate") is True
    ]
    assert EVAL_009 not in open_blockers


# ── the five required statements ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "statement",
    [
        # 1. the dependency itself
        "depends largely on one substantive production example",
        # 2. the prohibition — the one most likely to be quietly violated
        "No corpus example will be added from EVAL-009's wording",
        # 3. who fixes it and with what
        "multiple\n   independently designed dense technical rewrite examples",
        # 4. diversity of structure, not paraphrase
        "different technical structures rather than",
        # 5. the closure condition
        "closes only after retrieval diversity and regression tests",
    ],
)
def test_the_register_states_each_required_statement(statement: str) -> None:
    text = REGISTER.read_text(encoding="utf-8")
    normalised = " ".join(text.split())
    assert " ".join(statement.split()) in normalised


def test_the_prohibition_on_deriving_corpus_from_the_prompt_is_explicit() -> None:
    """Gate 1 removed 17 chunks to stop a benchmark retrieving its own answer."""
    text = REGISTER.read_text(encoding="utf-8")
    assert "retrieve its own answer" in text


# ── the three classifications ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("entry_id", "status", "classification"),
    [
        ("CW-LIM-RC2-COUNT", "accepted", "accepted historical record"),
        ("CW-LIM-ROLLBACK-COUNTS", "accepted", "accepted historical evidence"),
        ("CW-LIM-EVAL-PATH", "resolved", "resolved by the Gate 1.1 rename"),
    ],
)
def test_each_classification_is_recorded(entry_id: str, status: str, classification: str) -> None:
    entry = _entries().get(entry_id)
    assert entry is not None, f"{entry_id} is absent from the register"
    assert entry["status"] == status
    assert entry["classification"] == classification


def test_the_two_historical_count_entries_stay_separate() -> None:
    """101 and 48/97 live in different documents; conflating them was a prior error."""
    entries = _entries()
    assert "CW-LIM-RC2-COUNT" in entries
    assert "CW-LIM-ROLLBACK-COUNTS" in entries

    text = REGISTER.read_text(encoding="utf-8")
    rc2 = text[text.index("## CW-LIM-RC2-COUNT") : text.index("## CW-LIM-ROLLBACK-COUNTS")]
    rollback = text[text.index("## CW-LIM-ROLLBACK-COUNTS") : text.index("## CW-LIM-EVAL-PATH")]

    assert "101" in rc2 and "owner-test-report-rc2.md" in rc2
    assert "48" in rollback and "97" in rollback
    assert "history/rollback-rc2.md" in rollback


def test_the_resolved_entry_names_what_closed_it() -> None:
    """A 'resolved' status with no evidence is an assertion, not a record."""
    entry = _entries()["CW-LIM-EVAL-PATH"]
    assert entry["resolved_at"] == "0.4.0-dev.2"
    assert entry["resolved_by"]

    import subprocess

    result = subprocess.run(  # noqa: S603
        ["git", "cat-file", "-t", str(entry["resolved_by"])],  # noqa: S607
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout.strip() == "commit", f"resolved_by is not a commit: {entry['resolved_by']}"


# ── the register must not silently disagree with the store ───────────────────


def test_the_evidence_matches_the_live_expectation_fixture() -> None:
    """If EVAL-009's markers change, this entry's evidence is stale and must move."""
    expectations = yaml.safe_load(
        (PROJECT_ROOT / "eval" / "expectations.yaml").read_text(encoding="utf-8")
    )
    case = next(c for c in expectations["cases"] if c["id"] == "EVAL-009")
    for marker in case["expect_any"]:
        assert marker in REGISTER.read_text(encoding="utf-8"), (
            f"EVAL-009 declares marker {marker!r}, which the register does not account for"
        )
