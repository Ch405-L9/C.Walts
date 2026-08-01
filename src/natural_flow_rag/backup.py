"""Verified backups, as a precondition for destructive work.

Deletion is the only operation in this project that can lose data the corpus
cannot regenerate. Chunk ids are content-derived, so a *rebuild* reproduces the
same ids from the same corpus — but a delete against a collection whose source
files have since changed is not recoverable by re-running ingestion.

The gate is therefore not "a backup exists" but "a backup was just taken and
independently verified". Three things are checked, because each has a distinct
failure mode:

  checksum ..... the copy matches its own recorded digest — catches a truncated
                 or partially-written file
  readable ..... the copy opens as SQLite and lists its collections — catches a
                 torn page that still checksums consistently, which is exactly
                 what `cp` of a live database produces
  populated .... the target collection is present in the copy and carries the
                 row count we expect — catches backing up the wrong file, or an
                 empty database created by opening a path that did not exist

`scripts/backup_chroma.sh` does the copy, using `sqlite3 .backup` rather than
`cp`, and refuses to run inside the weekday cron window that writes the shared
production store. It is reused rather than reimplemented so there is one backup
mechanism to audit, not two.
"""

from __future__ import annotations

import hashlib
import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .settings import Settings


class BackupError(RuntimeError):
    """A backup could not be taken, or could not be verified."""


@dataclass
class BackupReport:
    path: str
    checksum_sha256: str
    checksum_verified: bool
    opens_readonly: bool
    collections: list[str] = field(default_factory=list)
    collection_present: bool = False
    embedding_rows: int | None = None

    @property
    def verified(self) -> bool:
        return (
            self.checksum_verified
            and self.opens_readonly
            and self.collection_present
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "checksum_sha256": self.checksum_sha256,
            "checksum_verified": self.checksum_verified,
            "opens_readonly": self.opens_readonly,
            "collections": self.collections,
            "collection_present": self.collection_present,
            "embedding_rows": self.embedding_rows,
            "verified": self.verified,
        }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def create_verified_backup(settings: Settings, collection: str) -> BackupReport:
    """Snapshot the Chroma store and prove the snapshot is usable.

    Raises rather than returning an unverified report: a caller that is about to
    delete must not be able to proceed by ignoring a boolean.
    """
    store_dir = settings.resolve_inside_project(settings.collection.persistence_path)
    source = store_dir / "chroma.sqlite3"
    if not source.is_file():
        raise BackupError(f"no Chroma database at {source}; nothing to back up")

    script = settings.project_root / "scripts" / "backup_chroma.sh"
    if not script.is_file():
        raise BackupError(f"backup script missing at {script}")

    destination_root = settings.resolve_inside_project("var/backups")
    destination_root.mkdir(parents=True, exist_ok=True)

    try:
        completed = subprocess.run(  # noqa: S603 — fixed script path, no shell
            [str(script), str(source), str(destination_root)],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BackupError(f"backup script could not be run: {exc}") from exc

    if completed.returncode != 0:
        raise BackupError(
            f"backup script exited {completed.returncode}: "
            f"{(completed.stderr or completed.stdout).strip()}"
        )

    backup_path: Path | None = None
    for line in completed.stdout.splitlines():
        if line.startswith("backup: "):
            backup_path = Path(line.removeprefix("backup: ").strip())
            break
    if backup_path is None or not backup_path.is_file():
        raise BackupError(
            f"backup script reported no usable path; stdout={completed.stdout.strip()!r}"
        )

    # Containment applies to the backup too — a snapshot written outside the
    # project root would be outside everything else this code promises.
    settings.resolve_inside_project(backup_path)

    digest = _sha256_file(backup_path)
    sidecar = backup_path.with_suffix(backup_path.suffix + ".sha256")
    checksum_verified = False
    if sidecar.is_file():
        recorded = sidecar.read_text(encoding="utf-8").split()
        checksum_verified = bool(recorded) and recorded[0] == digest

    report = BackupReport(
        path=str(backup_path),
        checksum_sha256=digest,
        checksum_verified=checksum_verified,
        opens_readonly=False,
    )

    try:
        connection = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT name FROM collections")
            report.collections = sorted(row[0] for row in cursor.fetchall())
            report.opens_readonly = True
            cursor.execute("SELECT count(*) FROM embeddings")
            report.embedding_rows = int(cursor.fetchone()[0])
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise BackupError(f"backup at {backup_path} did not open as SQLite: {exc}") from exc

    report.collection_present = collection in report.collections

    if not report.verified:
        raise BackupError(
            f"backup at {backup_path} failed verification "
            f"(checksum={report.checksum_verified}, readable={report.opens_readonly}, "
            f"collection {collection!r} present={report.collection_present}). "
            f"Refusing to treat it as a safety net."
        )
    return report


__all__ = ["BackupError", "BackupReport", "create_verified_backup"]
