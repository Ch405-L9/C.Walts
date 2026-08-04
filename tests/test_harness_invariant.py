from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = PROJECT_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"_{name}"] = module
    spec.loader.exec_module(module)
    return module


harness = _load_script("harness_invariant")
verify_restore = _load_script("verify_restore")
smoke_test = _load_script("smoke_test")


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _create_chroma_fixture(
    path: Path,
    *,
    orphan_segment: bool = False,
    duplicate_id: bool = False,
    blank_id: bool = False,
    extra_fk_violation: bool = False,
    missing_table: str | None = None,
) -> None:
    connection = _connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE collections (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            );
            CREATE TABLE segments (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                scope TEXT NOT NULL,
                collection TEXT REFERENCES collection(id) NOT NULL
            );
            CREATE TABLE embeddings (
                id INTEGER PRIMARY KEY,
                segment_id TEXT NOT NULL,
                embedding_id TEXT NOT NULL
            );
            CREATE TABLE embedding_metadata (
                id INTEGER NOT NULL,
                key TEXT NOT NULL,
                string_value TEXT,
                int_value INTEGER,
                float_value REAL,
                bool_value INTEGER
            );
            """
        )
        if extra_fk_violation:
            connection.executescript(
                """
                CREATE TABLE other_child (
                    id INTEGER PRIMARY KEY,
                    parent TEXT REFERENCES missing_parent(id)
                );
                INSERT INTO other_child (id, parent) VALUES (1, 'missing');
                """
            )
        connection.executemany(
            "INSERT INTO collections (id, name) VALUES (?, ?)",
            [("c1", "badgr_corpus"), ("c2", "job_opportunities")],
        )
        segments = [
            ("s1", "urn:chroma:segment/vector/hnsw-local-persisted", "VECTOR", "c1"),
            ("s2", "urn:chroma:segment/metadata/sqlite", "METADATA", "c1"),
            ("s3", "urn:chroma:segment/vector/hnsw-local-persisted", "VECTOR", "c2"),
            (
                "s4",
                "urn:chroma:segment/metadata/sqlite",
                "METADATA",
                "missing" if orphan_segment else "c2",
            ),
        ]
        connection.executemany(
            "INSERT INTO segments (id, type, scope, collection) VALUES (?, ?, ?, ?)",
            segments,
        )
        rows = [(1, "s2", "doc-1"), (2, "s2", "doc-2"), (3, "s4", "job-1")]
        if duplicate_id:
            rows.append((4, "s2", "doc-1"))
        if blank_id:
            rows.append((5, "s4", ""))
        connection.executemany(
            "INSERT INTO embeddings (id, segment_id, embedding_id) VALUES (?, ?, ?)",
            rows,
        )
        for row_id, _segment_id, embedding_id in rows:
            connection.execute(
                """
                INSERT INTO embedding_metadata
                  (id, key, string_value, int_value, float_value, bool_value)
                VALUES (?, 'chroma:document', ?, NULL, NULL, NULL)
                """,
                (row_id, f"document for {embedding_id}"),
            )
            connection.execute(
                """
                INSERT INTO embedding_metadata
                  (id, key, string_value, int_value, float_value, bool_value)
                VALUES (?, 'source_id', ?, NULL, NULL, NULL)
                """,
                (row_id, "fixture"),
            )
        if missing_table:
            connection.execute(f"DROP TABLE {missing_table}")
        connection.commit()
    finally:
        connection.close()


def _capture(path: Path, **kwargs: Any) -> dict[str, Any]:
    return harness.capture(path, **kwargs)


def _mutate_metadata(path: Path, value: str) -> None:
    connection = _connect(path)
    try:
        connection.execute(
            "UPDATE embedding_metadata SET string_value=? WHERE key='source_id' AND id=1",
            (value,),
        )
        connection.commit()
    finally:
        connection.close()


def _snapshot_files(path: Path) -> list[Path]:
    return sorted(path.glob("cwalts-harness-snapshot-*.sqlite3"))


def _fake_named_temporary_file(root: Path):
    def factory(*_args: Any, **_kwargs: Any):
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"cwalts-harness-snapshot-{len(_snapshot_files(root))}.sqlite3"
        return path.open("w+b")

    return factory


class _FakeConnection:
    def __init__(
        self,
        *,
        backup_error: Exception | None = None,
        close_error: Exception | None = None,
    ) -> None:
        self.backup_error = backup_error
        self.close_error = close_error
        self.closed = False
        self.committed = False

    def backup(self, _destination: _FakeConnection) -> None:
        if self.backup_error is not None:
            raise self.backup_error

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class _CloseFailingConnection:
    def __init__(self, connection: sqlite3.Connection, close_error: Exception) -> None:
        self.connection = connection
        self.close_error = close_error

    @property
    def row_factory(self):
        return self.connection.row_factory

    @row_factory.setter
    def row_factory(self, value: object) -> None:
        self.connection.row_factory = value

    def execute(self, *args: Any, **kwargs: Any):
        return self.connection.execute(*args, **kwargs)

    def close(self) -> None:
        self.connection.close()
        raise self.close_error


def test_chroma_schema_anomaly_fixture_passes(tmp_path: Path) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    report = _capture(db)
    assert report["health"] == harness.HEALTH_ANOMALY
    assert report["known_schema_anomalies"] == [harness.KNOWN_ANOMALY]
    assert report["logical_unresolved_segment_collection_count"] == 0
    assert report["total_segments"] == 4
    assert len(report["foreign_key_check"]) == 4
    assert report["verdict"] == "pass"


def test_true_orphan_segment_fails(tmp_path: Path) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db, orphan_segment=True)
    report = _capture(db)
    assert report["logical_unresolved_segment_collection_count"] == 1
    assert report["verdict"] == "fail"


def test_additional_foreign_key_violation_fails(tmp_path: Path) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db, extra_fk_violation=True)
    report = _capture(db)
    assert report["verdict"] == "fail"
    assert "unexpected_foreign_key_check" in report["findings"]


def test_quick_check_failure_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    original = harness.analyze_connection

    def fake(connection: sqlite3.Connection) -> dict[str, Any]:
        report = original(connection)
        report["quick_check"] = [["not ok"]]
        report["unexpected_health_failures"] = ["quick_check_failed"]
        report["health"] = harness.HEALTH_FAIL
        return report

    monkeypatch.setattr(harness, "analyze_connection", fake)
    report = _capture(db)
    assert report["verdict"] == "fail"
    assert "quick_check_failed" in report["findings"]


def test_integrity_check_failure_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    original = harness.analyze_connection

    def fake(connection: sqlite3.Connection) -> dict[str, Any]:
        report = original(connection)
        report["integrity_check"] = [["broken"]]
        report["unexpected_health_failures"] = ["integrity_check_failed"]
        report["health"] = harness.HEALTH_FAIL
        return report

    monkeypatch.setattr(harness, "analyze_connection", fake)
    report = _capture(db)
    assert report["verdict"] == "fail"
    assert "integrity_check_failed" in report["findings"]


def test_missing_required_chroma_table_fails(tmp_path: Path) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db, missing_table="embedding_metadata")
    report = _capture(db)
    assert report["verdict"] == "fail"
    assert "missing_required_chroma_table" in report["findings"]


def test_duplicate_embedding_id_fails(tmp_path: Path) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db, duplicate_id=True)
    report = _capture(db)
    assert report["verdict"] == "fail"
    assert "duplicate_embedding_ids" in report["findings"]


def test_blank_embedding_id_fails(tmp_path: Path) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db, blank_id=True)
    report = _capture(db)
    assert report["verdict"] == "fail"
    assert "blank_embedding_ids" in report["findings"]


def test_capture_deletes_temporary_database_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    snapshots: list[Path] = []
    original = harness.sqlite_backup_snapshot

    def wrapped(database: Path):
        result = original(database)
        snapshots.append(result.path)
        return result

    monkeypatch.setattr(harness, "sqlite_backup_snapshot", wrapped)
    report = _capture(db)
    assert report["temporary_snapshot_deleted"] is True
    assert snapshots and not snapshots[0].exists()


def test_capture_performs_no_source_write(tmp_path: Path) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    before = (db.stat().st_mtime_ns, hashlib.sha256(db.read_bytes()).hexdigest())
    report = _capture(db)
    after = (db.stat().st_mtime_ns, hashlib.sha256(db.read_bytes()).hexdigest())
    assert before == after
    assert report["source_write_performed"] is False


def test_capture_performs_no_wal_checkpoint(tmp_path: Path) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    report = _capture(db)
    assert report["wal_checkpoint_performed"] is False


def test_capture_performs_no_vacuum_or_reindex(tmp_path: Path) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    report = _capture(db)
    assert report["vacuum_performed"] is False
    assert report["reindex_performed"] is False


def test_source_connection_failure_removes_temporary_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    temp_root = tmp_path / "tmp"
    db = tmp_path / "missing.sqlite3"
    db.write_bytes(b"not sqlite")
    monkeypatch.setattr(
        harness.tempfile,
        "NamedTemporaryFile",
        _fake_named_temporary_file(temp_root),
    )

    def fail_connect(*_args: Any, **_kwargs: Any):
        raise sqlite3.Error("source failed")

    monkeypatch.setattr(harness.sqlite3, "connect", fail_connect)

    with pytest.raises(sqlite3.Error, match="source failed"):
        harness.sqlite_backup_snapshot(db)

    assert _snapshot_files(temp_root) == []


def test_destination_connection_failure_removes_temporary_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    temp_root = tmp_path / "tmp"
    db = tmp_path / "chroma.sqlite3"
    db.write_bytes(b"source")
    source = _FakeConnection()

    def fake_connect(target: object, *_args: Any, **_kwargs: Any):
        if str(target).startswith("file:"):
            return source
        raise sqlite3.Error("destination failed")

    monkeypatch.setattr(
        harness.tempfile,
        "NamedTemporaryFile",
        _fake_named_temporary_file(temp_root),
    )
    monkeypatch.setattr(harness.sqlite3, "connect", fake_connect)

    with pytest.raises(sqlite3.Error, match="destination failed"):
        harness.sqlite_backup_snapshot(db)

    assert source.closed is True
    assert _snapshot_files(temp_root) == []


def test_sqlite_backup_failure_removes_temporary_snapshot_and_closes_connections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    temp_root = tmp_path / "tmp"
    db = tmp_path / "chroma.sqlite3"
    db.write_bytes(b"source")
    source = _FakeConnection(backup_error=sqlite3.Error("backup failed"))
    destination = _FakeConnection()

    def fake_connect(target: object, *_args: Any, **_kwargs: Any):
        return source if str(target).startswith("file:") else destination

    monkeypatch.setattr(
        harness.tempfile,
        "NamedTemporaryFile",
        _fake_named_temporary_file(temp_root),
    )
    monkeypatch.setattr(harness.sqlite3, "connect", fake_connect)

    with pytest.raises(sqlite3.Error, match="backup failed"):
        harness.sqlite_backup_snapshot(db)

    assert source.closed is True
    assert destination.closed is True
    assert _snapshot_files(temp_root) == []


@pytest.mark.parametrize(
    ("source_close_error", "destination_close_error", "expected_notes"),
    [
        (None, sqlite3.Error("destination close failed"), ["destination_close"]),
        (sqlite3.Error("source close failed"), None, ["source_close"]),
        (
            sqlite3.Error("source close failed"),
            sqlite3.Error("destination close failed"),
            ["destination_close", "source_close"],
        ),
    ],
)
def test_backup_failure_with_close_failures_still_unlinks_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_close_error: Exception | None,
    destination_close_error: Exception | None,
    expected_notes: list[str],
) -> None:
    temp_root = tmp_path / "tmp"
    db = tmp_path / "chroma.sqlite3"
    db.write_bytes(b"source")
    source = _FakeConnection(
        backup_error=sqlite3.Error("backup failed"),
        close_error=source_close_error,
    )
    destination = _FakeConnection(close_error=destination_close_error)

    def fake_connect(target: object, *_args: Any, **_kwargs: Any):
        return source if str(target).startswith("file:") else destination

    monkeypatch.setattr(
        harness.tempfile,
        "NamedTemporaryFile",
        _fake_named_temporary_file(temp_root),
    )
    monkeypatch.setattr(harness.sqlite3, "connect", fake_connect)

    with pytest.raises(sqlite3.Error, match="backup failed") as raised:
        harness.sqlite_backup_snapshot(db)

    assert raised.value.__notes__
    for expected_note in expected_notes:
        assert any(expected_note in note for note in raised.value.__notes__)
    assert source.closed is True
    assert destination.closed is True
    assert _snapshot_files(temp_root) == []


@pytest.mark.parametrize(
    ("source_close_error", "destination_close_error", "expected_notes"),
    [
        (None, sqlite3.Error("destination close failed"), ["destination_close"]),
        (sqlite3.Error("source close failed"), None, ["source_close"]),
    ],
)
def test_successful_backup_with_close_failure_fails_and_unlinks_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_close_error: Exception | None,
    destination_close_error: Exception | None,
    expected_notes: list[str],
) -> None:
    temp_root = tmp_path / "tmp"
    db = tmp_path / "chroma.sqlite3"
    db.write_bytes(b"source")
    source = _FakeConnection(close_error=source_close_error)
    destination = _FakeConnection(close_error=destination_close_error)

    def fake_connect(target: object, *_args: Any, **_kwargs: Any):
        return source if str(target).startswith("file:") else destination

    monkeypatch.setattr(
        harness.tempfile,
        "NamedTemporaryFile",
        _fake_named_temporary_file(temp_root),
    )
    monkeypatch.setattr(harness.sqlite3, "connect", fake_connect)

    with pytest.raises(harness.HarnessInvariantError) as raised:
        harness.sqlite_backup_snapshot(db)

    assert raised.value.__notes__
    for expected_note in expected_notes:
        assert any(expected_note in note for note in raised.value.__notes__)
    assert source.closed is True
    assert destination.closed is True
    assert _snapshot_files(temp_root) == []


def test_successful_backup_with_close_and_unlink_failure_reports_all_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    temp_root = tmp_path / "tmp"
    db = tmp_path / "chroma.sqlite3"
    db.write_bytes(b"source")
    source = _FakeConnection(close_error=sqlite3.Error("source close failed"))
    destination = _FakeConnection(close_error=sqlite3.Error("destination close failed"))
    unlink_attempted: list[Path] = []
    original_unlink = harness.Path.unlink

    def fake_connect(target: object, *_args: Any, **_kwargs: Any):
        return source if str(target).startswith("file:") else destination

    def failing_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
        if path.name.startswith("cwalts-harness-snapshot-"):
            unlink_attempted.append(path)
            raise OSError("unlink failed")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(
        harness.tempfile,
        "NamedTemporaryFile",
        _fake_named_temporary_file(temp_root),
    )
    monkeypatch.setattr(harness.sqlite3, "connect", fake_connect)
    monkeypatch.setattr(harness.Path, "unlink", failing_unlink)

    with pytest.raises(harness.HarnessInvariantError) as raised:
        harness.sqlite_backup_snapshot(db)

    assert source.closed is True
    assert destination.closed is True
    assert unlink_attempted
    assert any("source_close" in note for note in raised.value.__notes__)
    assert any("destination_close" in note for note in raised.value.__notes__)
    assert any("snapshot_unlink" in note for note in raised.value.__notes__)
    for leaked in _snapshot_files(temp_root):
        original_unlink(leaked)


def test_analysis_failure_after_snapshot_creation_removes_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    snapshots: list[Path] = []
    original_snapshot = harness.sqlite_backup_snapshot

    def wrapped(database: Path):
        result = original_snapshot(database)
        snapshots.append(result.path)
        return result

    monkeypatch.setattr(harness, "sqlite_backup_snapshot", wrapped)
    monkeypatch.setattr(
        harness,
        "analyze_connection",
        lambda _connection: (_ for _ in ()).throw(RuntimeError("analysis failed")),
    )

    with pytest.raises(RuntimeError, match="analysis failed"):
        _capture(db)

    assert snapshots
    assert not snapshots[0].exists()


def test_snapshot_readonly_connection_failure_removes_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    snapshot_path = tmp_path / "snapshot.sqlite3"
    snapshots = [snapshot_path]

    def fake_snapshot(_database: Path):
        snapshot_path.write_bytes(db.read_bytes())
        return harness.SnapshotResult(path=snapshot_path)

    monkeypatch.setattr(harness, "sqlite_backup_snapshot", fake_snapshot)
    def fail_snapshot_open(*_args: Any, **_kwargs: Any):
        raise sqlite3.Error("snapshot open failed")

    monkeypatch.setattr(harness.sqlite3, "connect", fail_snapshot_open)

    with pytest.raises(sqlite3.Error, match="snapshot open failed"):
        _capture(db)

    assert snapshots[0].exists() is False


def test_snapshot_unlink_failure_fails_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    snapshots: list[Path] = []
    original_snapshot = harness.sqlite_backup_snapshot
    original_unlink = harness.Path.unlink

    def wrapped(database: Path):
        result = original_snapshot(database)
        snapshots.append(result.path)
        return result

    def failing_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
        if snapshots and path == snapshots[0]:
            raise OSError("cannot remove snapshot")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(harness, "sqlite_backup_snapshot", wrapped)
    monkeypatch.setattr(harness.Path, "unlink", failing_unlink)

    report = _capture(db)

    assert report["verdict"] == "fail"
    assert report["temporary_snapshot_deleted"] is False
    assert "temporary_snapshot_cleanup_failed" in report["findings"]
    assert snapshots and snapshots[0].exists()
    original_unlink(snapshots[0])


def test_analysis_success_with_snapshot_close_failure_unlinks_and_fails_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    snapshot_path = tmp_path / "snapshot.sqlite3"
    original_connect = sqlite3.connect

    def fake_snapshot(_database: Path):
        snapshot_path.write_bytes(db.read_bytes())
        return harness.SnapshotResult(path=snapshot_path)

    def fake_connect(target: object, *_args: Any, **_kwargs: Any):
        real = original_connect(str(target).replace("file:", "").replace("?mode=ro", ""))
        return _CloseFailingConnection(real, sqlite3.Error("snapshot close failed"))

    monkeypatch.setattr(harness, "sqlite_backup_snapshot", fake_snapshot)
    monkeypatch.setattr(harness.sqlite3, "connect", fake_connect)

    report = _capture(db)

    assert report["verdict"] == "fail"
    assert report["temporary_snapshot_deleted"] is True
    assert "snapshot_connection_close_failed" in report["findings"]
    assert snapshot_path.exists() is False


def test_analysis_failure_with_snapshot_close_failure_still_unlinks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    snapshot_path = tmp_path / "snapshot.sqlite3"
    original_connect = sqlite3.connect

    def fake_snapshot(_database: Path):
        snapshot_path.write_bytes(db.read_bytes())
        return harness.SnapshotResult(path=snapshot_path)

    def fake_connect(target: object, *_args: Any, **_kwargs: Any):
        real = original_connect(str(target).replace("file:", "").replace("?mode=ro", ""))
        return _CloseFailingConnection(real, sqlite3.Error("snapshot close failed"))

    monkeypatch.setattr(harness, "sqlite_backup_snapshot", fake_snapshot)
    monkeypatch.setattr(harness.sqlite3, "connect", fake_connect)
    monkeypatch.setattr(
        harness,
        "analyze_connection",
        lambda _connection: (_ for _ in ()).throw(RuntimeError("analysis failed")),
    )

    with pytest.raises(RuntimeError, match="analysis failed") as raised:
        _capture(db)

    assert any("snapshot_connection_close" in note for note in raised.value.__notes__)
    assert snapshot_path.exists() is False


def test_analysis_failure_close_failure_and_unlink_failure_are_visible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    snapshot_path = tmp_path / "snapshot.sqlite3"
    unlink_attempted: list[Path] = []
    original_connect = sqlite3.connect
    original_unlink = harness.Path.unlink

    def fake_snapshot(_database: Path):
        snapshot_path.write_bytes(db.read_bytes())
        return harness.SnapshotResult(path=snapshot_path)

    def fake_connect(target: object, *_args: Any, **_kwargs: Any):
        real = original_connect(str(target).replace("file:", "").replace("?mode=ro", ""))
        return _CloseFailingConnection(real, sqlite3.Error("snapshot close failed"))

    def failing_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
        if path == snapshot_path:
            unlink_attempted.append(path)
            raise OSError("unlink failed")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(harness, "sqlite_backup_snapshot", fake_snapshot)
    monkeypatch.setattr(harness.sqlite3, "connect", fake_connect)
    monkeypatch.setattr(harness.Path, "unlink", failing_unlink)
    monkeypatch.setattr(
        harness,
        "analyze_connection",
        lambda _connection: (_ for _ in ()).throw(RuntimeError("analysis failed")),
    )

    with pytest.raises(RuntimeError, match="analysis failed") as raised:
        _capture(db)

    assert unlink_attempted == [snapshot_path]
    assert any("snapshot_connection_close" in note for note in raised.value.__notes__)
    assert any("snapshot_unlink" in note for note in raised.value.__notes__)
    assert snapshot_path.exists()
    original_unlink(snapshot_path)


def test_identical_capture_and_verify_pass(tmp_path: Path) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    baseline = _capture(db)
    result = harness.verify(db, baseline)
    assert result["verdict"] == "pass"
    assert result["physical_drift"] is False
    assert result["semantic_drift"] is False


def test_physical_file_only_drift_with_identical_logical_contents_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    baseline = _capture(db)
    original = harness.file_identity

    def fake_identity(path: Path) -> dict[str, Any]:
        identity = original(path)
        if path.resolve() == db.resolve():
            identity["md5"] = "different"
        return identity

    monkeypatch.setattr(harness, "file_identity", fake_identity)
    result = harness.verify(db, baseline)
    assert result["verdict"] == "pass"
    assert result["physical_drift"] is True
    assert result["semantic_drift"] is False


@pytest.mark.parametrize(
    ("mutation", "field"),
    [
        ("document", "logical_database_sha256"),
        ("metadata", "logical_database_sha256"),
        ("addition", "collections"),
        ("removal", "collections"),
        ("collection_addition", "collections"),
        ("collection_deletion", "collections"),
        ("schema", "schema_sha256"),
    ],
)
def test_semantic_changes_fail(tmp_path: Path, mutation: str, field: str) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    baseline = _capture(db)
    connection = _connect(db)
    try:
        if mutation == "document":
            connection.execute(
                """
                UPDATE embedding_metadata
                SET string_value='changed'
                WHERE key='chroma:document' AND id=1
                """
            )
        elif mutation == "metadata":
            connection.execute(
                """
                UPDATE embedding_metadata
                SET string_value='changed'
                WHERE key='source_id' AND id=1
                """
            )
        elif mutation == "addition":
            connection.execute(
                "INSERT INTO embeddings (id, segment_id, embedding_id) VALUES (99, 's2', 'doc-99')"
            )
            connection.execute(
                """
                INSERT INTO embedding_metadata (id, key, string_value)
                VALUES (99, 'chroma:document', 'new')
                """
            )
        elif mutation == "removal":
            connection.execute("DELETE FROM embedding_metadata WHERE id=1")
            connection.execute("DELETE FROM embeddings WHERE id=1")
        elif mutation == "collection_addition":
            connection.execute("INSERT INTO collections (id, name) VALUES ('c3', 'extra')")
        elif mutation == "collection_deletion":
            connection.execute("DELETE FROM collections WHERE id='c2'")
        elif mutation == "schema":
            connection.execute("CREATE TABLE added_schema (id INTEGER)")
        connection.commit()
    finally:
        connection.close()
    result = harness.verify(db, baseline)
    assert result["verdict"] == "fail"
    assert result["semantic_drift"] is True
    assert any(diff["field"] == field for diff in result["semantic_differences"])


def test_known_anomaly_signature_change_fails(tmp_path: Path) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    baseline = _capture(db)
    connection = _connect(db)
    try:
        connection.execute("ALTER TABLE segments RENAME TO old_segments")
        connection.execute(
            """
            CREATE TABLE segments (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                scope TEXT NOT NULL,
                collection TEXT NOT NULL
            )
            """
        )
        connection.execute("INSERT INTO segments SELECT * FROM old_segments")
        connection.execute("DROP TABLE old_segments")
        connection.commit()
    finally:
        connection.close()
    result = harness.verify(db, baseline)
    assert result["verdict"] == "fail"
    assert result["semantic_drift"] is True
    assert any(diff["field"] == "known_schema_anomalies" for diff in result["semantic_differences"])


def test_active_external_writer_with_require_quiescent_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    monkeypatch.setattr(
        harness,
        "find_db_holder_processes",
        lambda _database: [{"pid": os.getpid(), "paths": [str(db)], "cmdline": "pytest"}],
    )
    report = _capture(db, require_quiescent=True)
    assert report["verdict"] == "fail"
    assert "database_not_quiescent" in report["findings"]


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    [
        (
            lambda baseline, _db: baseline.update({"verdict": "fail"}),
            "baseline_verdict_failed",
        ),
        (
            lambda baseline, _db: baseline.update({"findings": ["prior_failure"]}),
            "baseline_has_findings",
        ),
        (
            lambda baseline, _db: baseline.update({"schema_version": 999}),
            "baseline_schema_version_invalid",
        ),
        (
            lambda baseline, _db: baseline.update({"mode": "verify"}),
            "baseline_mode_invalid",
        ),
        (
            lambda baseline, db: baseline.update(
                {"database_path": str(db.with_name("other.sqlite3"))}
            ),
            "baseline_database_path_mismatch",
        ),
        (
            lambda baseline, _db: baseline.update({"source_write_performed": True}),
            "baseline_reports_source_write",
        ),
        (
            lambda baseline, _db: baseline.update({"vacuum_performed": True}),
            "baseline_reports_prohibited_operation",
        ),
        (
            lambda baseline, _db: baseline.update({"temporary_snapshot_deleted": False}),
            "baseline_snapshot_not_deleted",
        ),
        (
            lambda baseline, _db: baseline.update({"logical_database_sha256": ""}),
            "baseline_semantic_digest_missing",
        ),
    ],
)
def test_invalid_baselines_are_rejected(
    tmp_path: Path,
    mutate: Any,
    expected_code: str,
) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    baseline = _capture(db, require_quiescent=True)
    mutate(baseline, db)

    result = harness.verify(db, baseline, require_quiescent=True)

    assert result["verdict"] == "fail"
    assert result["baseline_valid"] is False
    assert result["comparison_performed"] is False
    assert expected_code in result["baseline_validation_findings"]


def test_baseline_collection_inventory_failures_are_rejected(tmp_path: Path) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    baseline = _capture(db)
    baseline["duplicate_id_count"] = 1

    result = harness.verify(db, baseline)

    assert result["verdict"] == "fail"
    assert "baseline_collection_inventory_invalid" in result["baseline_validation_findings"]


def test_non_mapping_baseline_is_rejected(tmp_path: Path) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)

    result = harness.verify(db, ["not", "a", "mapping"], require_quiescent=True)

    assert result["verdict"] == "fail"
    assert result["baseline_validation_findings"] == ["baseline_not_mapping"]


def test_non_quiescent_baseline_rejected_when_quiescence_required(tmp_path: Path) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    baseline = _capture(db)
    baseline["require_quiescent"] = False
    baseline["database_quiescent"] = False
    baseline["active_db_holder_processes"] = [{"pid": 123, "paths": [str(db)], "cmdline": "writer"}]

    result = harness.verify(db, baseline, require_quiescent=True)

    assert result["verdict"] == "fail"
    assert "baseline_not_quiescent" in result["baseline_validation_findings"]


def test_current_active_writer_rejected_when_quiescence_required(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    baseline = _capture(db, require_quiescent=True)
    monkeypatch.setattr(
        harness,
        "find_db_holder_processes",
        lambda _database: [{"pid": os.getpid(), "paths": [str(db)], "cmdline": "pytest"}],
    )

    result = harness.verify(db, baseline, require_quiescent=True)

    assert result["verdict"] == "fail"
    assert result["baseline_valid"] is True
    assert result["current_capture_valid"] is False
    assert "database_not_quiescent" in result["findings"]


@pytest.mark.parametrize("sidecar", ["chroma.sqlite3-wal", "chroma.sqlite3-shm"])
def test_current_wal_or_shm_rejected_when_quiescence_required(tmp_path: Path, sidecar: str) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    baseline = _capture(db, require_quiescent=True)
    (tmp_path / sidecar).write_text("sidecar", encoding="utf-8")

    result = harness.verify(db, baseline, require_quiescent=True)

    assert result["verdict"] == "fail"
    assert result["current_capture_valid"] is False
    assert "database_not_quiescent" in result["findings"]


def test_valid_quiescent_baseline_and_current_pair_passes(tmp_path: Path) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    baseline = _capture(db, require_quiescent=True)

    result = harness.verify(db, baseline, require_quiescent=True)

    assert result["verdict"] == "pass"
    assert result["baseline_valid"] is True
    assert result["comparison_performed"] is True


def test_verify_restore_with_valid_baseline_passes_harness_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    baseline = _capture(db)
    monkeypatch.setattr(verify_restore, "HARNESS_DB", db)
    _patch_restore_fakes(tmp_path, monkeypatch)
    report = verify_restore.verify({"id1"}, 1, "fixture", harness_baseline=baseline)
    assert report["verified"] is True, report["failures"]
    assert report["harness_invariant_checked"] is True


def test_verify_restore_required_harness_uses_quiescent_comparison(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    baseline = _capture(db, require_quiescent=True)
    monkeypatch.setattr(verify_restore, "HARNESS_DB", db)
    _patch_restore_fakes(tmp_path, monkeypatch)
    calls: list[bool] = []
    original_verify = verify_restore.harness_invariant.verify

    def wrapped(
        database: Path,
        baseline_report: dict[str, Any],
        *,
        require_quiescent: bool = False,
    ):
        calls.append(require_quiescent)
        return original_verify(database, baseline_report, require_quiescent=require_quiescent)

    monkeypatch.setattr(verify_restore.harness_invariant, "verify", wrapped)

    report = verify_restore.verify(
        {"id1"},
        1,
        "fixture",
        harness_baseline=baseline,
        require_harness_invariant=True,
    )

    assert report["verified"] is True, report["failures"]
    assert calls == [True]
    assert report["harness_quiescence_required"] is True
    assert report["harness_baseline_valid"] is True
    assert report["harness_comparison_performed"] is True


def test_verify_restore_rejects_failed_harness_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    baseline = _capture(db)
    baseline["verdict"] = "fail"
    monkeypatch.setattr(verify_restore, "HARNESS_DB", db)
    _patch_restore_fakes(tmp_path, monkeypatch)

    report = verify_restore.verify({"id1"}, 1, "fixture", harness_baseline=baseline)

    assert report["verified"] is False
    assert report["harness_baseline_valid"] is False
    assert any("Harness semantic invariant failed" in failure for failure in report["failures"])


def test_verify_restore_with_semantic_harness_drift_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "chroma.sqlite3"
    _create_chroma_fixture(db)
    baseline = _capture(db)
    _mutate_metadata(db, "changed")
    monkeypatch.setattr(verify_restore, "HARNESS_DB", db)
    _patch_restore_fakes(tmp_path, monkeypatch)
    report = verify_restore.verify({"id1"}, 1, "fixture", harness_baseline=baseline)
    assert report["verified"] is False
    assert any("Harness semantic invariant failed" in failure for failure in report["failures"])


def test_verify_restore_requires_baseline_when_requested(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_restore_fakes(tmp_path, monkeypatch)
    report = verify_restore.verify({"id1"}, 1, "fixture", require_harness_invariant=True)
    assert report["verified"] is False
    assert any("no --harness-baseline" in failure for failure in report["failures"])


def test_verify_restore_without_baseline_reports_unchecked_and_does_not_use_old_md5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_restore_fakes(tmp_path, monkeypatch)
    report = verify_restore.verify({"id1"}, 1, "fixture")
    assert report["verified"] is True, report["failures"]
    assert report["harness_invariant_checked"] is False


def test_smoke_test_does_not_compare_against_failed_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "chroma.sqlite3"
    db.write_text("placeholder", encoding="utf-8")
    monkeypatch.setattr(smoke_test, "HARNESS_DB", db)
    monkeypatch.setattr(
        smoke_test.harness_invariant,
        "capture",
        lambda _database, *, require_quiescent: {
            "verdict": "fail",
            "findings": ["database_not_quiescent"],
        },
    )

    def forbidden_verify(*_args: Any, **_kwargs: Any):
        raise AssertionError("verify should not run against a failed baseline")

    monkeypatch.setattr(smoke_test.harness_invariant, "verify", forbidden_verify)

    passed, detail = smoke_test.harness_semantic_unchanged_check()

    assert passed is False
    assert detail["baseline_valid"] is False
    assert detail["comparison_performed"] is False
    assert detail["findings"] == ["database_not_quiescent"]


def test_historical_md5_is_not_an_executable_acceptance_constant() -> None:
    old = "bdcbe32b706c6ccce1f62e8e9f2" + "d2c49"
    offenders = []
    for path in [*PROJECT_ROOT.glob("scripts/*.py"), *PROJECT_ROOT.glob("tests/*.py")]:
        if path.name == "test_harness_invariant.py":
            continue
        if old in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(PROJECT_ROOT)))
    assert offenders == []


def _patch_restore_fakes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    index_path = tmp_path / "var" / "bm25" / "index.json"
    index_path.parent.mkdir(parents=True)
    index_path.write_text(json.dumps({"chunk_ids": ["id1"]}), encoding="utf-8")
    monkeypatch.setattr(verify_restore, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(verify_restore, "load_settings", lambda: _FakeSettings())
    monkeypatch.setattr(verify_restore, "VectorStore", lambda _settings: _FakeStore())
    monkeypatch.setattr(verify_restore, "LexicalIndex", _FakeLexical)
    monkeypatch.setattr(verify_restore, "OllamaEmbedder", lambda _embedding: object())
    monkeypatch.setattr(verify_restore, "Retriever", _FakeRetriever)


class _FakeCollection:
    def count(self) -> int:
        return 1

    def get(self, **kwargs: Any) -> dict[str, Any]:
        if kwargs.get("where"):
            return {"ids": []}
        return {"ids": ["id1"], "metadatas": [{"doc_type": "approved_example"}]}


class _FakeClient:
    def get_collection(self, _name: str) -> _FakeCollection:
        return _FakeCollection()


class _FakeStore:
    client = _FakeClient()

    def exists(self) -> bool:
        return True

    def get(self) -> _FakeCollection:
        return _FakeCollection()


class _FakeSettings:
    embedding = object()


class _FakeLexical:
    def __init__(self, _path: Path) -> None:
        pass

    def search(self, _query: str, _limit: int) -> list[str]:
        return ["hit"]


class _FakeChunk:
    metadata = {"doc_type": "approved_example"}


class _FakeResult:
    chunks = [_FakeChunk()]


class _FakeRetriever:
    def __init__(self, *_args: Any) -> None:
        pass

    def search(self, _query: str, k: int = 5) -> _FakeResult:
        return _FakeResult()
