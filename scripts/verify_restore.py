#!/usr/bin/env python3
"""Post-restore verification. Proves a restored store is usable, not merely present.

`store_snapshot.py --restore` already refuses to restore a snapshot it cannot
verify, and what it puts back covers both stores. This tool answers the question
that comes *after* that: is the live store now correct?

The distinction matters because the rc.2 rehearsal (see
`docs/history/rollback-rc2.md`) found a restore that looked successful from every
angle a caller could see — retrieval still returned results — while the vector
store held 48 chunks and the lexical index still described 97. Nothing failed.
It was simply wrong.

So every check here interrogates the live store rather than trusting a hash or a
previous report:

  derived count .. the expected count is DERIVED, from source discovery or from
                   the restoring snapshot's own manifest, never hard-coded. A
                   number written into a procedure is a number that goes stale.
  reopen ......... both collections open and answer, by name
  parity ......... Chroma's id set and BM25's id set are equal, not merely
                   equinumerous — the rc.2 failure had matching-looking counts
                   for a while
  evaluation ..... zero evaluation_case records survive the restore, checked
                   two ways, because restoring an old backup is the one
                   operation that can undo Gate 1
  lexical ........ an exact-term query returns hits from the live index
  retrieval ...... a real production query returns useful, on-corpus chunks
  feedback ....... checked separately and by its own name; it is a different
                   collection with a different lifecycle
  harness ........ optional operation-scoped semantic comparison for the external
                   BADGR Harness store. Without a fresh baseline, this reports
                   current fingerprints but does not claim external immutability.

Exit status is 0 only if every check passes.

    --expect-from-sources     derive the expected count by running discovery
    --expect-from-snapshot P  derive it from snapshot P's manifest
    --harness-baseline P      compare the external Harness store to a fresh
                              operation-scoped semantic baseline
    --require-harness-invariant
                              fail closed unless --harness-baseline is supplied
    --json                    machine-readable report
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import harness_invariant  # noqa: E402

from natural_flow_rag.embeddings import OllamaEmbedder  # noqa: E402
from natural_flow_rag.lexical_search import LexicalIndex  # noqa: E402
from natural_flow_rag.retrieval import Retriever  # noqa: E402
from natural_flow_rag.settings import load_settings  # noqa: E402
from natural_flow_rag.vector_store import VectorStore  # noqa: E402

HARNESS_DB = Path("/home/t0n34781/projects/badgr_harness/rag_db/chroma.sqlite3")
FEEDBACK_COLLECTION = "badgr_natural_flow_feedback_v1"
EXACT_TERM_PROBE = "ToBI"
RETRIEVAL_PROBE = "Make this sound more natural: access is constrained by the user's permissions."
FORBIDDEN_DOC_TYPE = "evaluation_case"


class RestoreVerificationError(RuntimeError):
    pass


def expected_from_sources() -> tuple[set[str] | None, int, str]:
    """Derive the expected chunk ids by running discovery over the corpus.

    This is the strongest available authority when the corpus is intact. Chunk
    ids are derived from source id and chunk content, so discovery reproduces
    exactly the id set a correct store holds — which means the restore can be
    checked against an id set rather than a count. Two stores can hold the same
    number of the wrong chunks.

    Nothing is written: this is the dry-run ingest code path, called directly.
    """
    import contextlib
    import importlib.util
    import io

    spec = importlib.util.spec_from_file_location("_ingest", PROJECT_ROOT / "scripts" / "ingest.py")
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RestoreVerificationError("cannot load scripts/ingest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    settings = load_settings()
    manifest = module.load_sources()
    root = settings.project_root

    records = []
    # build_records() narrates to stdout; keep the report clean.
    with contextlib.redirect_stdout(io.StringIO()):
        for source in module.approved_sources(manifest):
            records.extend(module.build_records(settings, source, root))

    ids = {r.id for r in records}
    return ids, len(ids), "source discovery over config/sources.yaml"


def expected_from_snapshot(path: Path) -> tuple[set[str] | None, int, str]:
    """Derive the expected count from the snapshot that was restored.

    Weaker than source discovery — the snapshot manifest records counts, not an
    id list — but it is the right authority when the corpus on disk has itself
    been rolled back or is not trusted.
    """
    manifest_path = path / "snapshot.json"
    if not manifest_path.is_file():
        raise RestoreVerificationError(f"not a snapshot: {path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    collection = str(manifest["collection"])
    count = manifest["collections"].get(collection)
    if count is None:
        raise RestoreVerificationError(f"snapshot manifest has no count for {collection!r}")
    return None, int(count), f"snapshot manifest {path.name}"


def verify(
    expected_ids: set[str] | None,
    expected: int,
    provenance: str,
    *,
    harness_baseline: dict[str, Any] | None = None,
    require_harness_invariant: bool = False,
) -> dict[str, Any]:
    settings = load_settings()
    store = VectorStore(settings)
    failures: list[str] = []

    if not store.exists():
        raise RestoreVerificationError(
            "the production collection does not exist; the restore did not complete"
        )

    collection = store.get()
    records = collection.get(include=["metadatas"])
    chroma_ids = set(records["ids"])
    live = collection.count()

    if live != expected:
        failures.append(
            f"production collection holds {live} chunks, expected {expected} "
            f"derived from {provenance}"
        )

    missing: list[str] = []
    unexpected: list[str] = []
    if expected_ids is not None:
        missing = sorted(expected_ids - chroma_ids)
        unexpected = sorted(chroma_ids - expected_ids)
        if missing or unexpected:
            failures.append(
                f"the restored id set does not match {provenance}: "
                f"{len(missing)} expected chunks absent, {len(unexpected)} unexpected "
                f"chunks present. A matching count would not have caught this."
            )

    # ── lexical index and id-set parity ──────────────────────────────────────
    index_path = PROJECT_ROOT / "var" / "bm25" / "index.json"
    if not index_path.is_file():
        failures.append("var/bm25/index.json is missing; only the vector store was restored")
        bm25_ids: set[str] = set()
    else:
        bm25_ids = set(json.loads(index_path.read_text(encoding="utf-8"))["chunk_ids"])

    only_chroma = sorted(chroma_ids - bm25_ids)
    only_bm25 = sorted(bm25_ids - chroma_ids)
    if only_chroma or only_bm25:
        failures.append(
            f"Chroma/BM25 id sets differ: {len(only_chroma)} only in Chroma, "
            f"{len(only_bm25)} only in BM25. This is the rc.2 failure mode — "
            f"retrieval will still answer, from a stale index."
        )

    # ── evaluation material must not come back with an old backup ────────────
    by_metadata = sum(
        1 for m in records["metadatas"] if str((m or {}).get("doc_type")) == FORBIDDEN_DOC_TYPE
    )
    by_filter = len(collection.get(where={"doc_type": FORBIDDEN_DOC_TYPE})["ids"])
    if by_metadata or by_filter:
        failures.append(
            f"{max(by_metadata, by_filter)} {FORBIDDEN_DOC_TYPE} chunks are present. "
            f"A pre-Gate-1 backup was restored; the collection is contaminated."
        )

    # ── feedback collection, separately and by name ──────────────────────────
    feedback_count: int | None = None
    try:
        feedback_count = store.client.get_collection(FEEDBACK_COLLECTION).count()
    except Exception as exc:  # noqa: BLE001 - any failure here is a real finding
        failures.append(f"feedback collection {FEEDBACK_COLLECTION!r} did not reopen: {exc}")

    # ── live lexical and live retrieval ──────────────────────────────────────
    lexical_hits = 0
    retrieval_hits = 0
    retrieval_doc_types: list[str] = []
    if index_path.is_file():
        lexical = LexicalIndex(index_path)
        lexical_hits = len(lexical.search(EXACT_TERM_PROBE, 3))
        if lexical_hits == 0:
            failures.append(
                f"exact-term query {EXACT_TERM_PROBE!r} returned nothing from the live index"
            )

        try:
            retriever = Retriever(settings, store, OllamaEmbedder(settings.embedding), lexical)
            result = retriever.search(RETRIEVAL_PROBE, k=5)
            retrieval_hits = len(result.chunks)
            retrieval_doc_types = [str(c.metadata.get("doc_type")) for c in result.chunks]
            if retrieval_hits == 0:
                failures.append("production retrieval returned no chunks")
            if any(dt == FORBIDDEN_DOC_TYPE for dt in retrieval_doc_types):
                failures.append("production retrieval returned evaluation material")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"production retrieval failed: {exc}")

    # ── external Harness store: operation-scoped semantic invariant ──────────
    harness_md5 = None
    harness_sha256 = None
    harness_invariant_checked = False
    harness_invariant_report: dict[str, Any] | None = None
    if HARNESS_DB.is_file():
        try:
            identity = harness_invariant.file_identity(HARNESS_DB)
            harness_md5 = identity.get("md5")
            harness_sha256 = identity.get("sha256")
        except OSError as exc:
            failures.append(f"BADGR Harness fingerprints could not be measured: {exc}")

    if require_harness_invariant and harness_baseline is None:
        failures.append(
            "BADGR Harness invariant was required but no --harness-baseline was supplied"
        )
    elif harness_baseline is not None:
        harness_invariant_checked = True
        try:
            harness_invariant_report = harness_invariant.verify(HARNESS_DB, harness_baseline)
        except Exception as exc:  # noqa: BLE001
            failures.append(
                f"BADGR Harness invariant could not be verified: {exc}"
            )
        else:
            if harness_invariant_report.get("verdict") != "pass":
                failures.append(
                    "BADGR Harness semantic invariant failed: "
                    f"{harness_invariant_report.get('findings')}"
                )

    return {
        "expected_count": expected,
        "expected_count_derived_from": provenance,
        "expected_id_set_checked": expected_ids is not None,
        "ids_expected_but_absent": missing[:10],
        "ids_present_but_unexpected": unexpected[:10],
        "production_count": live,
        "bm25_chunk_ids": len(bm25_ids),
        "chroma_bm25_parity": not (only_chroma or only_bm25),
        "ids_only_in_chroma": only_chroma[:10],
        "ids_only_in_bm25": only_bm25[:10],
        f"{FORBIDDEN_DOC_TYPE}_by_metadata": by_metadata,
        f"{FORBIDDEN_DOC_TYPE}_by_where_filter": by_filter,
        "feedback_collection": FEEDBACK_COLLECTION,
        "feedback_count": feedback_count,
        "exact_term_probe": EXACT_TERM_PROBE,
        "exact_term_hits": lexical_hits,
        "retrieval_probe_hits": retrieval_hits,
        "retrieval_doc_types": retrieval_doc_types,
        "badgr_harness_store_md5": harness_md5,
        "badgr_harness_store_sha256": harness_sha256,
        "harness_invariant_checked": harness_invariant_checked,
        "harness_invariant_report": harness_invariant_report,
        "verified": not failures,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--expect-from-sources",
        action="store_true",
        help="derive the expected count by running discovery over the corpus",
    )
    source.add_argument(
        "--expect-from-snapshot",
        metavar="PATH",
        help="derive the expected count from a snapshot's own manifest",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument(
        "--harness-baseline",
        metavar="PATH",
        help="operation-scoped Harness baseline captured by scripts/harness_invariant.py",
    )
    parser.add_argument(
        "--require-harness-invariant",
        action="store_true",
        help="fail closed unless --harness-baseline is supplied",
    )
    args = parser.parse_args()

    try:
        if args.expect_from_snapshot:
            expected_ids, expected, provenance = expected_from_snapshot(
                Path(args.expect_from_snapshot).resolve()
            )
        else:
            expected_ids, expected, provenance = expected_from_sources()
        harness_baseline = (
            json.loads(Path(args.harness_baseline).read_text(encoding="utf-8"))
            if args.harness_baseline
            else None
        )
        report = verify(
            expected_ids,
            expected,
            provenance,
            harness_baseline=harness_baseline,
            require_harness_invariant=args.require_harness_invariant,
        )
    except (RestoreVerificationError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("Restore verification")
        print(f"  expected count      {report['expected_count']}  ({provenance})")
        print(f"  production count    {report['production_count']}")
        if report["expected_id_set_checked"]:
            print(
                f"  id set vs source    "
                f"{len(report['ids_expected_but_absent'])} absent / "
                f"{len(report['ids_present_but_unexpected'])} unexpected"
            )
        print(f"  BM25 chunk ids      {report['bm25_chunk_ids']}")
        print(f"  id-set parity       {report['chroma_bm25_parity']}")
        print(f"  evaluation_case     {report[f'{FORBIDDEN_DOC_TYPE}_by_metadata']}")
        print(f"  feedback ({FEEDBACK_COLLECTION})  {report['feedback_count']}")
        print(f"  exact term {EXACT_TERM_PROBE!r}    {report['exact_term_hits']} hits")
        print(f"  retrieval probe     {report['retrieval_probe_hits']} chunks")
        print(f"  harness store MD5   {report['badgr_harness_store_md5']}")
        print(f"  harness invariant   {report['harness_invariant_checked']}")
        print()
        for failure in report["failures"]:
            print(f"  FAIL  {failure}")
        print("PASS — the restored store is complete and usable." if report["verified"] else "FAIL")

    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
