#!/usr/bin/env python3
"""Operation-scoped read-only invariant for the external BADGR Harness Chroma DB."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import stat
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
KNOWN_ANOMALY = "known_chroma_schema_anomaly"
HEALTH_OK = "healthy"
HEALTH_ANOMALY = "healthy_with_known_chroma_schema_anomaly"
HEALTH_FAIL = "unhealthy"
REQUIRED_CHROMA_TABLES = {
    "collections",
    "segments",
    "embeddings",
    "embedding_metadata",
}


class HarnessInvariantError(RuntimeError):
    """The Harness invariant cannot be safely measured or compared."""


@dataclass(frozen=True)
class SnapshotResult:
    path: Path
    deleted: bool = False


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm, usedforsecurity=False)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_identity(path: Path) -> dict[str, Any]:
    identity: dict[str, Any] = {"path": str(path), "exists": path.exists()}
    if not path.exists():
        return identity
    st = path.stat()
    identity.update(
        {
            "file_type": "regular" if path.is_file() else "other",
            "byte_size": st.st_size,
            "inode": st.st_ino,
            "device_id": st.st_dev,
            "owner_uid": st.st_uid,
            "group_gid": st.st_gid,
            "mode": stat.filemode(st.st_mode),
            "modified_time": datetime.fromtimestamp(st.st_mtime, UTC).isoformat(),
            "changed_time": datetime.fromtimestamp(st.st_ctime, UTC).isoformat(),
        }
    )
    if path.is_file():
        identity["md5"] = hash_file(path, "md5")
        identity["sha256"] = hash_file(path, "sha256")
        identity["sha512"] = hash_file(path, "sha512")
    return identity


def sidecar_identities(database: Path) -> dict[str, dict[str, Any]]:
    return {
        "wal": file_identity(database.with_name(f"{database.name}-wal")),
        "shm": file_identity(database.with_name(f"{database.name}-shm")),
        "journal": file_identity(database.with_name(f"{database.name}-journal")),
    }


def find_db_holder_processes(database: Path) -> list[dict[str, Any]]:
    targets = {
        database.resolve(),
        database.with_name(f"{database.name}-wal").resolve(),
        database.with_name(f"{database.name}-shm").resolve(),
        database.with_name(f"{database.name}-journal").resolve(),
    }
    holders: list[dict[str, Any]] = []
    proc = Path("/proc")
    if not proc.is_dir():
        return holders
    for pid_dir in proc.iterdir():
        if not pid_dir.name.isdigit():
            continue
        fd_dir = pid_dir / "fd"
        try:
            fds = list(fd_dir.iterdir())
        except OSError:
            continue
        matched: list[str] = []
        for fd in fds:
            try:
                target = fd.resolve()
            except OSError:
                continue
            if target in targets:
                matched.append(str(target))
        if not matched:
            continue
        try:
            cmdline = (pid_dir / "cmdline").read_bytes().replace(b"\x00", b" ").decode(
                "utf-8", errors="replace"
            ).strip()
        except OSError:
            cmdline = ""
        holders.append({"pid": int(pid_dir.name), "paths": sorted(matched), "cmdline": cmdline})
    return sorted(holders, key=lambda item: item["pid"])


def sqlite_backup_snapshot(database: Path) -> SnapshotResult:
    tmp_path: Path | None = None
    source: sqlite3.Connection | None = None
    destination: sqlite3.Connection | None = None
    try:
        tmp = tempfile.NamedTemporaryFile(
            prefix="cwalts-harness-snapshot-",
            suffix=".sqlite3",
            delete=False,
        )
        tmp_path = Path(tmp.name)
        tmp.close()
        source = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
        destination = sqlite3.connect(tmp_path)
        source.backup(destination)
        destination.commit()
        return SnapshotResult(path=tmp_path)
    except BaseException:
        if destination is not None:
            try:
                destination.close()
            finally:
                destination = None
        if source is not None:
            try:
                source.close()
            finally:
                source = None
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise
    finally:
        if destination is not None:
            destination.close()
        if source is not None:
            source.close()


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='table'")
    }


def canonical_sql(connection: sqlite3.Connection) -> list[dict[str, str]]:
    rows = connection.execute(
        """
        SELECT type, name, tbl_name, sql
        FROM sqlite_schema
        WHERE name NOT LIKE 'sqlite_%'
        ORDER BY type, name
        """
    ).fetchall()
    return [
        {
            "type": str(row[0]),
            "name": str(row[1]),
            "table": str(row[2]),
            "sql": " ".join(str(row[3] or "").split()),
        }
        for row in rows
    ]


def canonical_value(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, int):
        return f"INT:{value}"
    if isinstance(value, float):
        return f"FLOAT:{value.hex()}"
    if isinstance(value, bytes):
        return f"BLOB:{len(value)}:{sha256_bytes(value)}"
    encoded = str(value).encode("utf-8")
    return f"TEXT:{len(encoded)}:{sha256_bytes(encoded)}"


def table_order(connection: sqlite3.Connection, table: str) -> tuple[list[str], str]:
    quoted = quote_ident(table)
    rows = connection.execute(f"PRAGMA table_info({quoted})").fetchall()
    columns = [str(row[1]) for row in rows]
    pk = [str(row[1]) for row in sorted(rows, key=lambda item: item[5]) if row[5]]
    if pk:
        return columns, ", ".join(quote_ident(column) for column in pk)
    sql_row = connection.execute(
        "SELECT sql FROM sqlite_schema WHERE type='table' AND name=?", (table,)
    ).fetchone()
    sql = str(sql_row[0] or "").upper() if sql_row else ""
    if "WITHOUT ROWID" not in sql:
        return columns, "rowid"
    return columns, ""


def quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def logical_manifest(connection: sqlite3.Connection) -> dict[str, Any]:
    schema = canonical_sql(connection)
    tables = []
    for table in sorted(table_names(connection)):
        if table.startswith("sqlite_"):
            continue
        columns, order = table_order(connection, table)
        quoted = quote_ident(table)
        query = f"SELECT * FROM {quoted}"  # noqa: S608 - table name is quoted from sqlite_schema
        if order:
            query += f" ORDER BY {order}"
        row_digests = []
        for row in connection.execute(query):
            payload = {
                column: canonical_value(row[index])
                for index, column in enumerate(columns)
            }
            row_digests.append(
                sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
            )
        if not order:
            row_digests.sort()
        tables.append(
            {
                "table": table,
                "columns": columns,
                "row_count": len(row_digests),
                "content_sha256": sha256_bytes(
                    json.dumps(row_digests, sort_keys=True, separators=(",", ":")).encode()
                ),
            }
        )
    schema_sha = sha256_bytes(json.dumps(schema, sort_keys=True, separators=(",", ":")).encode())
    logical_payload = {"schema_sha256": schema_sha, "tables": tables}
    return {
        "schema_sha256": schema_sha,
        "logical_database_sha256": sha256_bytes(
            json.dumps(logical_payload, sort_keys=True, separators=(",", ":")).encode()
        ),
        "tables": tables,
    }


def metadata_value(row: sqlite3.Row) -> Any:
    for key in ("string_value", "int_value", "float_value", "bool_value"):
        if row[key] is not None:
            return bool(row[key]) if key == "bool_value" else row[key]
    return None


def collection_inventory(connection: sqlite3.Connection) -> dict[str, Any]:
    collections = []
    duplicate_count = 0
    blank_count = 0
    for collection in connection.execute("SELECT id, name FROM collections ORDER BY name"):
        collection_id = str(collection["id"])
        rows = connection.execute(
            """
            SELECT e.id AS row_id,
                   e.embedding_id,
                   m.key,
                   m.string_value,
                   m.int_value,
                   m.float_value,
                   m.bool_value
            FROM embeddings e
            JOIN segments s ON e.segment_id = s.id
            LEFT JOIN embedding_metadata m ON m.id = e.id
            WHERE s.collection = ?
            ORDER BY e.embedding_id, m.key
            """,
            (collection_id,),
        ).fetchall()
        by_id: dict[str, dict[str, Any]] = {}
        row_ids_by_embedding: dict[str, set[int]] = {}
        for row in rows:
            embedding_id = str(row["embedding_id"] or "")
            if not embedding_id:
                blank_count += 1
            row_ids_by_embedding.setdefault(embedding_id, set()).add(int(row["row_id"]))
            record = by_id.setdefault(embedding_id, {"document_sha256": None, "metadata": {}})
            key = row["key"]
            if key == "chroma:document":
                record["document_sha256"] = sha256_bytes(str(row["string_value"] or "").encode())
            elif key:
                record["metadata"][str(key)] = metadata_value(row)
        duplicates = sorted(
            embedding_id
            for embedding_id, rows_for_id in row_ids_by_embedding.items()
            if len(rows_for_id) > 1
        )
        duplicate_count += len(duplicates)
        ids = sorted(by_id)
        digest_payload = [
            {
                "id": embedding_id,
                "document_sha256": by_id[embedding_id]["document_sha256"],
                "metadata": by_id[embedding_id]["metadata"],
            }
            for embedding_id in ids
        ]
        collections.append(
            {
                "name": str(collection["name"]),
                "id": collection_id,
                "record_count": len(ids),
                "id_list_sha256": sha256_bytes((json.dumps(ids, indent=2) + "\n").encode()),
                "canonical_document_metadata_digest": sha256_bytes(
                    json.dumps(digest_payload, sort_keys=True).encode()
                ),
                "duplicate_id_count": len(duplicates),
                "blank_id_count": sum(1 for item in ids if not item),
            }
        )
    inventory_digest = sha256_bytes(json.dumps(collections, sort_keys=True).encode())
    return {
        "collections": collections,
        "collection_inventory_digest": inventory_digest,
        "duplicate_id_count": duplicate_count,
        "blank_id_count": blank_count,
    }


def analyze_connection(connection: sqlite3.Connection) -> dict[str, Any]:
    connection.row_factory = sqlite3.Row
    names = table_names(connection)
    quick_check = [list(row) for row in connection.execute("PRAGMA quick_check").fetchall()]
    integrity_check = [list(row) for row in connection.execute("PRAGMA integrity_check").fetchall()]
    foreign_key_check = [
        {
            "table": str(row[0]),
            "rowid": row[1],
            "parent": str(row[2]),
            "fk_index": row[3],
        }
        for row in connection.execute("PRAGMA foreign_key_check").fetchall()
    ]
    fk_list_segments = [
        {
            "id": row[0],
            "seq": row[1],
            "parent_table": row[2],
            "from": row[3],
            "to": row[4],
            "on_update": row[5],
            "on_delete": row[6],
            "match": row[7],
        }
        for row in connection.execute("PRAGMA foreign_key_list(segments)").fetchall()
    ] if "segments" in names else []
    required_missing = sorted(REQUIRED_CHROMA_TABLES - names)
    unresolved_segments = None
    total_segments = None
    total_embeddings = None
    embeddings_resolved = None
    if not required_missing:
        total_segments = int(connection.execute("SELECT COUNT(*) FROM segments").fetchone()[0])
        unresolved_segments = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM segments AS s
                LEFT JOIN collections AS c ON s.collection = c.id
                WHERE c.id IS NULL
                """
            ).fetchone()[0]
        )
        total_embeddings = int(connection.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0])
        embeddings_resolved = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM embeddings AS e
                JOIN segments AS s ON e.segment_id = s.id
                JOIN collections AS c ON s.collection = c.id
                """
            ).fetchone()[0]
        )

    schema_anomaly = (
        "collections" in names
        and "collection" not in names
        and any(
            item["parent_table"] == "collection"
            and item["from"] == "collection"
            and item["to"] == "id"
            for item in fk_list_segments
        )
        and foreign_key_check
        and all(
            item["table"] == "segments"
            and item["parent"] == "collection"
            and int(item["fk_index"]) == 0
            for item in foreign_key_check
        )
        and total_segments == len(foreign_key_check)
        and unresolved_segments == 0
        and quick_check == [["ok"]]
        and integrity_check == [["ok"]]
        and total_embeddings == embeddings_resolved
    )

    unexpected_fk = []
    if foreign_key_check and not schema_anomaly:
        unexpected_fk = foreign_key_check

    manifest = logical_manifest(connection) if not required_missing else {
        "schema_sha256": None,
        "logical_database_sha256": None,
        "tables": [],
    }
    inventory = collection_inventory(connection) if not required_missing else {
        "collections": [],
        "collection_inventory_digest": None,
        "duplicate_id_count": None,
        "blank_id_count": None,
    }

    unexpected_health_failures: list[str] = []
    if quick_check != [["ok"]]:
        unexpected_health_failures.append("quick_check_failed")
    if integrity_check != [["ok"]]:
        unexpected_health_failures.append("integrity_check_failed")
    if required_missing:
        unexpected_health_failures.append("missing_required_chroma_table")
    if unexpected_fk:
        unexpected_health_failures.append("unexpected_foreign_key_check")
    if unresolved_segments not in (0, None):
        unexpected_health_failures.append("unresolved_logical_segments")
    if total_embeddings != embeddings_resolved:
        unexpected_health_failures.append("unresolved_embeddings")
    if inventory.get("duplicate_id_count"):
        unexpected_health_failures.append("duplicate_embedding_ids")
    if inventory.get("blank_id_count"):
        unexpected_health_failures.append("blank_embedding_ids")

    known_anomalies = [KNOWN_ANOMALY] if schema_anomaly else []
    if unexpected_health_failures:
        health = HEALTH_FAIL
    elif schema_anomaly:
        health = HEALTH_ANOMALY
    else:
        health = HEALTH_OK

    return {
        "sqlite_library_version": sqlite3.sqlite_version,
        "quick_check": quick_check,
        "integrity_check": integrity_check,
        "foreign_key_check": foreign_key_check,
        "foreign_key_list_segments": fk_list_segments,
        "tables_present": sorted(names),
        "required_chroma_tables_missing": required_missing,
        "total_segments": total_segments,
        "collections_count": (
            int(connection.execute("SELECT COUNT(*) FROM collections").fetchone()[0])
            if "collections" in names
            else None
        ),
        "logical_unresolved_segment_collection_count": unresolved_segments,
        "total_embeddings": total_embeddings,
        "embeddings_resolved_to_recognized_collections": embeddings_resolved,
        "known_schema_anomalies": known_anomalies,
        "unexpected_health_failures": sorted(set(unexpected_health_failures)),
        "health": health,
        **manifest,
        **inventory,
    }


def capture(database: Path, *, require_quiescent: bool = False) -> dict[str, Any]:
    database = database.resolve()
    if not database.is_file():
        raise HarnessInvariantError(f"Harness database not found: {database}")
    db_identity = file_identity(database)
    sidecars = sidecar_identities(database)
    holders = find_db_holder_processes(database)
    quiescent = not holders and not sidecars["wal"]["exists"] and not sidecars["shm"]["exists"]
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "mode": "capture",
        "database_path": str(database),
        "database_identity": db_identity,
        "wal_identity": sidecars["wal"],
        "shm_identity": sidecars["shm"],
        "journal_identity": sidecars["journal"],
        "active_db_holder_processes": holders,
        "database_quiescent": quiescent,
        "require_quiescent": require_quiescent,
        "source_write_performed": False,
        "wal_checkpoint_performed": False,
        "vacuum_performed": False,
        "reindex_performed": False,
        "restore_performed": False,
        "full_documents_included": False,
        "embeddings_included": False,
        "temporary_snapshot_deleted": False,
    }
    snapshot = sqlite_backup_snapshot(database)
    connection: sqlite3.Connection | None = None
    cleanup_findings: list[str] = []
    try:
        connection = sqlite3.connect(f"file:{snapshot.path.resolve()}?mode=ro", uri=True)
        report.update(analyze_connection(connection))
    finally:
        if connection is not None:
            connection.close()
        try:
            if snapshot.path.exists():
                snapshot.path.unlink()
            report["temporary_snapshot_deleted"] = not snapshot.path.exists()
        except FileNotFoundError:
            report["temporary_snapshot_deleted"] = True
        except OSError as exc:
            report["temporary_snapshot_deleted"] = False
            cleanup_findings.append("temporary_snapshot_cleanup_failed")
            report["temporary_snapshot_cleanup_error"] = str(exc)
    findings = list(report.get("unexpected_health_failures", []))
    findings.extend(cleanup_findings)
    if require_quiescent and not quiescent:
        findings.append("database_not_quiescent")
    if not report["temporary_snapshot_deleted"]:
        findings.append("temporary_snapshot_cleanup_failed")
    report["findings"] = sorted(set(findings))
    report["verdict"] = "pass" if not findings else "fail"
    return report


SEMANTIC_KEYS = [
    "database_path",
    "schema_sha256",
    "logical_database_sha256",
    "collection_inventory_digest",
    "collections",
    "duplicate_id_count",
    "blank_id_count",
    "logical_unresolved_segment_collection_count",
    "unexpected_health_failures",
    "known_schema_anomalies",
]


def validate_baseline(
    baseline: dict[str, Any],
    database: Path,
    *,
    require_quiescent: bool,
) -> list[str]:
    if not isinstance(baseline, dict):
        return ["baseline_not_mapping"]
    findings: list[str] = []
    if baseline.get("schema_version") != SCHEMA_VERSION:
        findings.append("baseline_schema_version_invalid")
    if baseline.get("mode") != "capture":
        findings.append("baseline_mode_invalid")
    if baseline.get("verdict") != "pass":
        findings.append("baseline_verdict_failed")
    if baseline.get("findings"):
        findings.append("baseline_has_findings")
    try:
        baseline_path = Path(str(baseline.get("database_path", ""))).resolve()
    except OSError:
        baseline_path = Path()
    if baseline_path != database.resolve():
        findings.append("baseline_database_path_mismatch")
    if baseline.get("source_write_performed") is not False:
        findings.append("baseline_reports_source_write")
    prohibited = (
        "wal_checkpoint_performed",
        "vacuum_performed",
        "reindex_performed",
        "restore_performed",
    )
    if any(baseline.get(key) is not False for key in prohibited):
        findings.append("baseline_reports_prohibited_operation")
    if baseline.get("temporary_snapshot_deleted") is not True:
        findings.append("baseline_snapshot_not_deleted")
    if baseline.get("full_documents_included") is not False:
        findings.append("baseline_collection_inventory_invalid")
    if baseline.get("embeddings_included") is not False:
        findings.append("baseline_collection_inventory_invalid")
    if baseline.get("health") not in {HEALTH_OK, HEALTH_ANOMALY}:
        findings.append("baseline_health_invalid")
    if baseline.get("unexpected_health_failures"):
        findings.append("baseline_health_invalid")
    if not baseline.get("schema_sha256") or not baseline.get("logical_database_sha256"):
        findings.append("baseline_semantic_digest_missing")
    if not baseline.get("collection_inventory_digest") or not isinstance(
        baseline.get("collections"), list
    ):
        findings.append("baseline_collection_inventory_invalid")
    if baseline.get("duplicate_id_count") != 0 or baseline.get("blank_id_count") != 0:
        findings.append("baseline_collection_inventory_invalid")
    if baseline.get("logical_unresolved_segment_collection_count") != 0:
        findings.append("baseline_collection_inventory_invalid")
    if require_quiescent:
        wal = baseline.get("wal_identity") or {}
        shm = baseline.get("shm_identity") or {}
        if (
            baseline.get("require_quiescent") is not True
            or baseline.get("database_quiescent") is not True
            or baseline.get("active_db_holder_processes")
            or wal.get("exists")
            or shm.get("exists")
        ):
            findings.append("baseline_not_quiescent")
    return sorted(set(findings))


def verify(
    database: Path,
    baseline: dict[str, Any],
    *,
    require_quiescent: bool = False,
) -> dict[str, Any]:
    database = Path(database).resolve()
    baseline_validation_findings = validate_baseline(
        baseline,
        database,
        require_quiescent=require_quiescent,
    )
    baseline_valid = not baseline_validation_findings
    if not baseline_valid:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "mode": "verify",
            "database_path": str(database),
            "baseline_generated_at": baseline.get("generated_at")
            if isinstance(baseline, dict)
            else None,
            "baseline_valid": False,
            "baseline_validation_findings": baseline_validation_findings,
            "current_capture_valid": None,
            "comparison_performed": False,
            "current_capture": None,
            "physical_drift": None,
            "semantic_drift": None,
            "raw_identity_differences": [],
            "semantic_differences": [],
            "findings": baseline_validation_findings,
            "verdict": "fail",
        }
    current = capture(database, require_quiescent=require_quiescent)
    current_capture_valid = current.get("verdict") == "pass"
    semantic_differences = []
    for key in SEMANTIC_KEYS:
        if current.get(key) != baseline.get(key):
            semantic_differences.append(
                {"field": key, "baseline": baseline.get(key), "current": current.get(key)}
            )
    base_identity = baseline.get("database_identity") or {}
    current_identity = current.get("database_identity") or {}
    raw_fields = ["md5", "sha256", "sha512", "byte_size", "modified_time", "changed_time"]
    raw_differences = [
        {"field": key, "baseline": base_identity.get(key), "current": current_identity.get(key)}
        for key in raw_fields
        if base_identity.get(key) != current_identity.get(key)
    ]
    findings = []
    if current.get("verdict") != "pass":
        findings.extend(current.get("findings") or ["current_capture_failed"])
    if semantic_differences:
        findings.append("semantic_drift")
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "mode": "verify",
        "database_path": str(Path(database).resolve()),
        "baseline_generated_at": baseline.get("generated_at"),
        "baseline_valid": baseline_valid,
        "baseline_validation_findings": baseline_validation_findings,
        "current_capture_valid": current_capture_valid,
        "comparison_performed": current_capture_valid,
        "current_capture": current,
        "physical_drift": bool(raw_differences),
        "semantic_drift": bool(semantic_differences),
        "raw_identity_differences": raw_differences,
        "semantic_differences": semantic_differences,
        "findings": sorted(set(findings)),
        "verdict": "pass" if not findings else "fail",
    }
    return result


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    capture_parser = sub.add_parser("capture")
    capture_parser.add_argument("--database", required=True)
    capture_parser.add_argument("--require-quiescent", action="store_true")
    capture_parser.add_argument("--output", required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--database", required=True)
    verify_parser.add_argument("--baseline", required=True)
    verify_parser.add_argument("--require-quiescent", action="store_true")
    verify_parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        if args.command == "capture":
            report = capture(Path(args.database), require_quiescent=args.require_quiescent)
        else:
            baseline = load_json(Path(args.baseline))
            report = verify(Path(args.database), baseline, require_quiescent=args.require_quiescent)
        write_json(Path(args.output), report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report.get("verdict") == "pass" else 1
    except (HarnessInvariantError, OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        report = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "mode": args.command,
            "database_path": (
                str(Path(args.database).resolve()) if getattr(args, "database", None) else None
            ),
            "verdict": "fail",
            "findings": ["measurement_failed"],
            "error": str(exc),
        }
        if getattr(args, "output", None):
            write_json(Path(args.output), report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
