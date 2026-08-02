"""Gate 1.1 §3: the active rollback procedure must not carry stale facts.

`docs/rollback.md` used to mix rc.2 rehearsal evidence with live instructions, so
a reader could not tell which numbers described the past and which described the
store in front of them. The rehearsal is now frozen in
`docs/history/rollback-rc2.md` and the active procedure derives every count.

These tests defend three things that would otherwise rot silently:

  no baked counts .... a production count typed into a procedure stays put while
                       the corpus changes, and reads as authoritative forever
  live anchors ....... mcp/server.py cites "docs/rollback.md §2" and "§3" in
                       runtime error messages; renumbering the document breaks
                       an error message nobody tests by hand
  the split held ..... the historical document says it is historical, the active
                       one says historical reports are not current-state
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACTIVE = PROJECT_ROOT / "docs" / "rollback.md"
HISTORICAL = PROJECT_ROOT / "docs" / "history" / "rollback-rc2.md"
SERVER = PROJECT_ROOT / "mcp" / "server.py"


# ── 1. the split exists ──────────────────────────────────────────────────────


def test_both_documents_exist() -> None:
    assert ACTIVE.is_file()
    assert HISTORICAL.is_file()


def test_the_historical_document_declares_itself_historical() -> None:
    text = HISTORICAL.read_text(encoding="utf-8")
    head = text[:1500]
    assert "HISTORICAL RECORD" in head
    assert "not a current-state manifest" in head
    assert "Do not follow it." in head


def test_the_historical_document_still_carries_its_evidence() -> None:
    """Preserved, not summarised. The measured failure is the point of keeping it."""
    text = HISTORICAL.read_text(encoding="utf-8")
    assert "48" in text and "97" in text
    assert "DEGRADED" in text


def test_the_active_document_states_that_history_is_not_a_manifest() -> None:
    text = ACTIVE.read_text(encoding="utf-8")
    assert "Historical reports are not current-state manifests" in text


def test_the_active_document_points_at_the_historical_one() -> None:
    assert "docs/history/rollback-rc2.md" in ACTIVE.read_text(encoding="utf-8")


# ── 2. no hard-coded production counts in the active procedure ───────────────


def _code_and_prose_numbers(text: str) -> set[int]:
    """Every standalone integer in the document, excluding section numbering."""
    stripped = re.sub(r"§\d+(\.\d+)*", " ", text)
    stripped = re.sub(r"^#+ \d+.*$", " ", stripped, flags=re.MULTILINE)
    stripped = re.sub(r"^## \d.*$", " ", stripped, flags=re.MULTILINE)
    return {int(m) for m in re.findall(r"(?<![\w.\-/])(\d{2,4})(?![\w.\-/%])", stripped)}


# Counts this collection has actually held. If any appears in the active
# procedure, someone has written a snapshot of the present into a document that
# outlives it.
HISTORICAL_COUNTS = {48, 97, 101, 84}


def test_the_active_document_contains_no_production_count() -> None:
    found = _code_and_prose_numbers(ACTIVE.read_text(encoding="utf-8")) & HISTORICAL_COUNTS
    assert found == set(), f"hard-coded production counts in docs/rollback.md: {sorted(found)}"


def test_the_active_document_derives_the_expected_count() -> None:
    text = ACTIVE.read_text(encoding="utf-8")
    assert "verify_restore.py --expect-from-sources" in text
    assert "--expect-from-snapshot" in text


def test_the_detector_would_catch_a_baked_count() -> None:
    """The count check must not pass because the regex matches nothing."""
    assert _code_and_prose_numbers("the collection holds 84 chunks") & HISTORICAL_COUNTS == {84}
    assert _code_and_prose_numbers("restored to 101 chunks") & HISTORICAL_COUNTS == {101}


# ── 3. the §-anchors mcp/server.py emits at runtime must resolve ─────────────


def test_every_section_cited_by_the_server_exists_in_the_active_document() -> None:
    """An error message that cites a section which no longer exists is a dead end."""
    server_text = SERVER.read_text(encoding="utf-8")
    cited = {int(n) for n in re.findall(r"rollback\.md\s*§(\d+)", server_text)}
    assert cited, "expected mcp/server.py to cite rollback sections"

    headings = {
        int(m.group(1))
        for m in re.finditer(r"^## (\d+)\.", ACTIVE.read_text(encoding="utf-8"), re.MULTILINE)
    }
    assert cited <= headings, f"server cites §{sorted(cited - headings)}, absent from rollback.md"


@pytest.mark.parametrize(
    ("section", "must_mention"),
    [(2, "backup"), (3, "source")],
)
def test_the_cited_sections_still_mean_what_the_server_says(
    section: int, must_mention: str
) -> None:
    """§2 must stay 'restore from backup' and §3 'rebuild from source'.

    The server tells an operator to go to a numbered section for a specific
    remedy. Keeping the number while changing the meaning is worse than
    renumbering.
    """
    text = ACTIVE.read_text(encoding="utf-8")
    match = re.search(rf"^## {section}\. (.+)$", text, re.MULTILINE)
    assert match, f"§{section} is missing from docs/rollback.md"
    assert must_mention in match.group(1).lower()


# ── 4. the active procedure covers every required verification ───────────────


@pytest.mark.parametrize(
    "requirement",
    [
        "store_snapshot.py --verify",
        "store_snapshot.py --restore",
        "verify_restore.py",
        "var/bm25/index.json",
        "evaluation_case",
        "badgr_natural_flow_feedback_v1",
        "BADGR Harness",
        "id-set parity",
    ],
)
def test_the_active_document_names_each_required_check(requirement: str) -> None:
    assert requirement in ACTIVE.read_text(encoding="utf-8")


def test_the_active_document_refuses_an_unverified_backup() -> None:
    text = ACTIVE.read_text(encoding="utf-8")
    assert "Do not restore" in text
    assert "no flag that forces an unverified snapshot" in text


def test_the_active_document_distinguishes_the_two_backup_kinds() -> None:
    """var/backups/ is Chroma-only; restoring it alone caused the rc.2 failure."""
    text = ACTIVE.read_text(encoding="utf-8")
    assert "var/snapshots/" in text and "var/backups/" in text
    assert "NOT OPTIONAL" in text


# ── 5. the verification tool itself ──────────────────────────────────────────


def test_the_verification_tool_hard_codes_no_expected_chunk_count() -> None:
    """It may pin the harness checksum; it may not pin the corpus size."""
    text = (PROJECT_ROOT / "scripts" / "verify_restore.py").read_text(encoding="utf-8")
    code = "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("#")
    )
    for count in HISTORICAL_COUNTS:
        assert f"= {count}" not in code, f"verify_restore.py pins a chunk count: {count}"
