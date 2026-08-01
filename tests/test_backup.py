"""A backup only counts if it was verified, and verification has three parts.

Checksum alone is not enough: `cp` of a live SQLite file can produce a torn page
that hashes consistently with itself and still will not open. Opening alone is
not enough either — an empty database opens fine. So the report is only
`verified` when the copy matches its digest, opens read-only, AND contains the
collection it was supposed to protect.
"""

import pytest

from natural_flow_rag.backup import BackupError, BackupReport, create_verified_backup
from natural_flow_rag.settings import load_settings


def _report(**overrides) -> BackupReport:
    base = {
        "path": "var/backups/20260801T000000Z/chroma.sqlite3",
        "checksum_sha256": "0" * 64,
        "checksum_verified": True,
        "opens_readonly": True,
        "collections": ["badgr_natural_flow_v1"],
        "collection_present": True,
        "embedding_rows": 97,
    }
    base.update(overrides)
    return BackupReport(**base)


def test_a_complete_report_is_verified():
    assert _report().verified is True


@pytest.mark.parametrize(
    "flaw",
    [
        {"checksum_verified": False},   # truncated or partially written
        {"opens_readonly": False},      # torn page; hashes fine, will not open
        {"collection_present": False},  # backed up the wrong database
    ],
)
def test_any_single_failure_makes_the_report_unverified(flaw):
    assert _report(**flaw).verified is False


def test_to_dict_exposes_the_verdict():
    payload = _report().to_dict()
    assert payload["verified"] is True
    assert payload["collections"] == ["badgr_natural_flow_v1"]


class _StubSettings:
    """Minimal stand-in — Settings is frozen, and only two members are used here."""

    def __init__(self, root):
        self.project_root = root
        self.collection = type("C", (), {"persistence_path": "var/chroma"})()

    def resolve_inside_project(self, candidate):
        return self.project_root / str(candidate)


def test_backup_refuses_when_there_is_no_database(tmp_path):
    with pytest.raises(BackupError, match="nothing to back up"):
        create_verified_backup(_StubSettings(tmp_path), "badgr_natural_flow_v1")


def test_backup_refuses_when_the_script_is_missing(tmp_path):
    settings = _StubSettings(tmp_path)
    store = tmp_path / "var" / "chroma"
    store.mkdir(parents=True)
    (store / "chroma.sqlite3").write_bytes(b"SQLite format 3\x00")
    with pytest.raises(BackupError, match="backup script missing"):
        create_verified_backup(settings, "badgr_natural_flow_v1")


def test_the_real_settings_expose_a_resolvable_store_path():
    settings = load_settings()
    resolved = settings.resolve_inside_project(settings.collection.persistence_path)
    assert resolved.is_relative_to(settings.project_root.resolve())
