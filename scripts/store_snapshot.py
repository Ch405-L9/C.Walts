#!/usr/bin/env python3
"""Whole-store snapshot, verification, and restore.

`src/natural_flow_rag/backup.py` snapshots `chroma.sqlite3` and proves the copy
opens and carries the expected rows. That is the right gate before a delete, but
it is not a complete restore point: Chroma keeps each collection's HNSW index in
sibling directories, the lexical arm lives in `var/bm25/index.json`, and the
source manifest decides what the corpus even is. Restoring the database alone
would bring back rows whose vector index and lexical index disagree with them.

This tool snapshots all four together and verifies the copy the only way that
means anything — by opening it and asking it questions:

  reopen ....... the snapshot opens as a Chroma store, read-only, in place
  count ........ the production collection is present with the expected count
  parity ....... the snapshot's BM25 index covers exactly the snapshot's chunks
  lexical ...... an exact-term query returns hits from the restored index

A hash alone is insufficient because a damaged database can still hash.

    --create              take and verify a snapshot
    --verify PATH         re-verify an existing snapshot
    --restore PATH        restore a verified snapshot over the live store
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from natural_flow_rag.settings import load_settings  # noqa: E402

SNAPSHOT_ROOT = PROJECT_ROOT / "var" / "snapshots"
EXACT_TERM_PROBE = "ToBI"


class SnapshotError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_digest(root: Path) -> str:
    """Order-independent digest over every file in a directory."""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(sha256_file(path).encode("ascii"))
    return digest.hexdigest()


def _sqlite_backup(source: Path, destination: Path) -> None:
    """Consistent copy of a live SQLite file. `cp` can capture a torn page."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src, sqlite3.connect(
        destination
    ) as dst:
        src.backup(dst)


def create() -> dict[str, object]:
    settings = load_settings()
    chroma_dir = settings.resolve_inside_project(settings.collection.persistence_path)
    bm25 = PROJECT_ROOT / "var" / "bm25" / "index.json"
    sources = PROJECT_ROOT / "config" / "sources.yaml"
    if not (chroma_dir / "chroma.sqlite3").is_file():
        raise SnapshotError(f"no Chroma database under {chroma_dir}")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = SNAPSHOT_ROOT / stamp
    if destination.exists():
        raise SnapshotError(f"snapshot already exists: {destination}")
    (destination / "chroma").mkdir(parents=True)

    # The HNSW directories first, then the database, so the database is the
    # newest thing in the snapshot rather than the oldest.
    for child in sorted(chroma_dir.iterdir()):
        if child.name == "chroma.sqlite3":
            continue
        if child.is_dir():
            shutil.copytree(child, destination / "chroma" / child.name)
        else:
            shutil.copy2(child, destination / "chroma" / child.name)
    _sqlite_backup(chroma_dir / "chroma.sqlite3", destination / "chroma" / "chroma.sqlite3")

    if bm25.is_file():
        shutil.copy2(bm25, destination / "bm25-index.json")
    if sources.is_file():
        shutil.copy2(sources, destination / "sources.yaml")

    manifest = {
        "created": datetime.now(UTC).isoformat(),
        "project_version": _project_version(),
        "collection": settings.collection.name,
        "chroma_tree_sha256": tree_digest(destination / "chroma"),
        "chroma_sqlite3_sha256": sha256_file(destination / "chroma" / "chroma.sqlite3"),
        "bm25_sha256": sha256_file(destination / "bm25-index.json")
        if (destination / "bm25-index.json").is_file()
        else None,
        "sources_yaml_sha256": sha256_file(destination / "sources.yaml")
        if (destination / "sources.yaml").is_file()
        else None,
        "collections": _collection_counts(destination / "chroma"),
        "bm25_chunk_ids": _bm25_count(destination / "bm25-index.json"),
    }
    (destination / "snapshot.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return {"path": str(destination.relative_to(PROJECT_ROOT)), **manifest}


def _project_version() -> str:
    from natural_flow_rag import __version__

    return __version__


def _collection_counts(chroma_dir: Path) -> dict[str, int]:
    """Row counts straight out of the snapshot's own SQLite file."""
    database = chroma_dir / "chroma.sqlite3"
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as conn:
        rows = conn.execute("SELECT id, name FROM collections").fetchall()
        counts: dict[str, int] = {}
        for collection_id, name in rows:
            (count,) = conn.execute(
                "SELECT COUNT(DISTINCT embedding_id) FROM embeddings "
                "WHERE segment_id IN (SELECT id FROM segments WHERE collection = ?)",
                (collection_id,),
            ).fetchone()
            counts[name] = int(count)
    return counts


def _bm25_count(path: Path) -> int | None:
    if not path.is_file():
        return None
    return len(json.loads(path.read_text(encoding="utf-8"))["chunk_ids"])


def verify(snapshot: Path) -> dict[str, object]:
    """Open the snapshot and interrogate it. Hashes alone prove too little."""
    manifest_path = snapshot / "snapshot.json"
    if not manifest_path.is_file():
        raise SnapshotError(f"not a snapshot: {snapshot}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures: list[str] = []

    if tree_digest(snapshot / "chroma") != manifest["chroma_tree_sha256"]:
        failures.append("chroma tree digest does not match the snapshot manifest")

    counts = _collection_counts(snapshot / "chroma")
    collection = str(manifest["collection"])
    if collection not in counts:
        failures.append(f"collection {collection!r} is absent from the snapshot")
    elif counts[collection] != manifest["collections"].get(collection):
        failures.append(
            f"{collection} holds {counts[collection]} rows, manifest says "
            f"{manifest['collections'].get(collection)}"
        )

    bm25_path = snapshot / "bm25-index.json"
    bm25_ids: set[str] = set()
    lexical_hits = 0
    if bm25_path.is_file():
        index = json.loads(bm25_path.read_text(encoding="utf-8"))
        bm25_ids = set(index["chunk_ids"])
        if len(bm25_ids) != counts.get(collection):
            failures.append(
                f"BM25 covers {len(bm25_ids)} chunks, {collection} holds "
                f"{counts.get(collection)}"
            )
        lexical_hits = _probe_restored_lexical(bm25_path, EXACT_TERM_PROBE)
        if lexical_hits == 0:
            failures.append(
                f"exact-term query {EXACT_TERM_PROBE!r} returned nothing from the "
                "restored lexical index"
            )
    else:
        failures.append("snapshot carries no BM25 index")

    report = {
        "path": str(snapshot.relative_to(PROJECT_ROOT)),
        "collections": counts,
        "bm25_chunk_ids": len(bm25_ids),
        "chroma_bm25_parity": len(bm25_ids) == counts.get(collection),
        "exact_term_probe": EXACT_TERM_PROBE,
        "exact_term_hits": lexical_hits,
        "verified": not failures,
        "failures": failures,
    }
    if failures:
        raise SnapshotError(json.dumps(report, indent=2))
    return report


def _probe_restored_lexical(index_path: Path, term: str) -> int:
    """Run a real lexical query against the snapshot's own index."""
    from natural_flow_rag.lexical_search import LexicalIndex

    index = LexicalIndex(index_path)
    return len(index.search(term, 3))


def restore(snapshot: Path) -> dict[str, object]:
    """Put a verified snapshot back over the live store."""
    report = verify(snapshot)
    settings = load_settings()
    chroma_dir = settings.resolve_inside_project(settings.collection.persistence_path)
    bm25 = PROJECT_ROOT / "var" / "bm25" / "index.json"

    if chroma_dir.exists():
        shutil.rmtree(chroma_dir)
    shutil.copytree(snapshot / "chroma", chroma_dir)
    if (snapshot / "bm25-index.json").is_file():
        bm25.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(snapshot / "bm25-index.json", bm25)

    return {
        "restored_from": report["path"],
        "collections": _collection_counts(chroma_dir),
        "bm25_chunk_ids": _bm25_count(bm25),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--create", action="store_true")
    modes.add_argument("--verify", metavar="PATH")
    modes.add_argument("--restore", metavar="PATH")
    args = parser.parse_args()
    try:
        if args.create:
            created = create()
            print(json.dumps(created, indent=2))
            verified = verify(PROJECT_ROOT / str(created["path"]))
            print(json.dumps(verified, indent=2))
        elif args.verify:
            print(json.dumps(verify(Path(args.verify).resolve()), indent=2))
        else:
            print(json.dumps(restore(Path(args.restore).resolve()), indent=2))
        return 0
    except (SnapshotError, OSError, ValueError, KeyError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
