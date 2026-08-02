#!/usr/bin/env python3
"""Corpus ingestion. DRY RUN BY DEFAULT.

    python scripts/ingest.py                 # dry run — reports, writes nothing
    python scripts/ingest.py --commit        # requires Gate 3 approval + writes enabled

Refusals, by design:

  * any source absent from config/sources.yaml, or whose license_status is not
    "approved" — quarantined, never embedded;
  * any chunk carrying an empty license field;
  * any embedding whose dimension is not 768;
  * any chunk above the model's 2048-token ceiling;
  * any persistence path outside the project root;
  * a commit while free disk is below the configured floor.

Gate 3 has not been approved at the time of writing, so --commit will refuse
until writes.allow_writes is set. That refusal is the feature.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from natural_flow_rag.chunking import chunk_text  # noqa: E402
from natural_flow_rag.embeddings import OllamaEmbedder  # noqa: E402
from natural_flow_rag.lexical_search import LexicalIndex  # noqa: E402
from natural_flow_rag.loaders import discover, load  # noqa: E402
from natural_flow_rag.normalize import normalize, normalize_cmudict  # noqa: E402
from natural_flow_rag.schemas import (  # noqa: E402
    ChunkRecord,
    chunk_id,
    link_neighbors,
    sha256_text,
)
from natural_flow_rag.settings import ConfigError, load_settings, load_sources  # noqa: E402
from natural_flow_rag.vector_store import VectorStore  # noqa: E402


def approved_sources(manifest: dict) -> list[dict]:
    """Sources ingestion may read. Approval is necessary, not sufficient.

    Gate 1 added the evaluation refusals. They raise rather than skip: a source
    manifest that declares evaluation material ingestible is a configuration
    error the operator must see, not a line of output they might miss.
    """
    settings = load_settings()
    out = []
    for source in manifest.get("sources", []) or []:
        where = f"source {source.get('id')!r}"
        settings.assert_ingestible_doc_type(source.get("doc_type"), where)
        settings.resolve_ingest_path(source["path"])
        if source.get("license_status") != "approved":
            print(f"  QUARANTINED  {source.get('id')}: license_status="
                  f"{source.get('license_status')!r}")
            continue
        if not str(source.get("license", "")).strip():
            print(f"  REFUSED      {source.get('id')}: empty license field")
            continue
        out.append(source)
    return out


def build_records(settings, source: dict, root: Path) -> list[ChunkRecord]:
    profiles = settings.chunking.get("profiles", {})
    tokenizer = settings.chunking.get("tokenizer", "cl100k_base")
    hard_max = int(settings.chunking.get("hard_maximum_tokens", 2048))
    ceiling = int(settings.chunking.get("safe_target_ceiling", 1024))

    settings.assert_ingestible_doc_type(source.get("doc_type"), f"source {source['id']!r}")
    source_path = settings.resolve_ingest_path(source["path"])
    files = discover(source_path)
    if not files:
        print(f"  (empty)      {source['id']}: no files under {source['path']}")
        return []

    records: list[ChunkRecord] = []
    for path in files:
        document = load(path)
        text = (
            normalize_cmudict(document.text)
            if source.get("doc_type") == "pronunciation"
            else normalize(document.text)
        )
        checksum = sha256_text(text)

        chunks = chunk_text(
            text,
            profile=source.get("chunk_profile", "reference"),
            profiles=profiles,
            tokenizer=tokenizer,
            hard_maximum_tokens=hard_max,
            safe_target_ceiling=ceiling,
        )

        per_file: list[ChunkRecord] = []
        for chunk in chunks:
            record = ChunkRecord(
                id=chunk_id(source["id"], sha256_text(chunk.text), chunk.index),
                text=chunk.text,
                source_id=source["id"],
                source_path=str(path.relative_to(root)),
                source_title=source.get("title", source["id"]),
                license=source["license"],
                license_url=source.get("license_url"),
                source_checksum=checksum,
                chunk_index=chunk.index,
                chunk_total=len(chunks),
                chunk_profile=chunk.profile,
                embedding_model=settings.embedding.model,
                embedding_dimension=settings.embedding.vector_dimension,
                tokenizer=chunk.tokenizer,
                token_count=chunk.token_count,
                section_heading=chunk.heading,
                doc_type=source.get("doc_type"),
                dialect=source.get("dialect"),
                register=source.get("register"),
            )
            record.validate()
            per_file.append(record)

        records.extend(link_neighbors(per_file))
        print(f"  {source['id']:<18} {path.name:<40} {len(per_file):>5} chunks")

    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--commit", action="store_true",
        help="actually write. Requires Gate 3 approval and writes.allow_writes.",
    )
    parser.add_argument("--source", help="restrict to one source id")
    args = parser.parse_args()
    dry_run = not args.commit

    settings = load_settings()
    manifest = load_sources()
    root = settings.project_root

    print(f"\nnatural-language-flow-rag ingest — "
          f"{'DRY RUN' if dry_run else 'COMMIT'}  {datetime.now(UTC).isoformat()}")
    print(f"collection: {settings.collection.name}")
    print(f"persistence: {settings.resolve_inside_project(settings.collection.persistence_path)}")
    print("\nsources:")

    sources = approved_sources(manifest)
    if args.source:
        sources = [s for s in sources if s["id"] == args.source]
    if not sources:
        print("\nNothing approved to ingest.")
        return 1

    print()
    records: list[ChunkRecord] = []
    for source in sources:
        records.extend(build_records(settings, source, root))

    if not records:
        print("\nNo chunks produced. Place files under the source paths in "
              "config/sources.yaml, then re-run.")
        return 1

    tokens = sum(r.token_count for r in records)
    estimated_bytes = len(records) * settings.embedding.vector_dimension * 4

    print(f"\n  chunks:            {len(records)}")
    print(f"  tokens:            {tokens}")
    print(f"  vector bytes:      ~{estimated_bytes / 1024 / 1024:.1f} MiB "
          f"({len(records)} x {settings.embedding.vector_dimension} x 4)")
    print(f"  licenses in play:  {sorted({r.license for r in records})}")

    manifest_path = root / "corpus" / "manifests" / f"dryrun-{datetime.now(UTC):%Y%m%dT%H%M%S}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "generated": datetime.now(UTC).isoformat(),
                "dry_run": dry_run,
                "chunks": len(records),
                "tokens": tokens,
                "by_source": {
                    s["id"]: sum(1 for r in records if r.source_id == s["id"]) for s in sources
                },
                "chunk_ids": [r.id for r in records],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  manifest:          {manifest_path.relative_to(root)}")

    if dry_run:
        print("\nDRY RUN — nothing written. Re-run with --commit after Gate 3 approval.\n")
        return 0

    # ── commit path ───────────────────────────────────────────────────────────
    try:
        settings.assert_writes_allowed("ingest --commit")
        settings.assert_disk_headroom()
    except ConfigError as exc:
        print(f"\nREFUSED: {exc}\n")
        return 2

    store = VectorStore(settings)
    embedder = OllamaEmbedder(settings.embedding)
    probe = embedder.probe()
    print(f"\n  embed probe:       dim={probe.dimension} norm={probe.l2_norm:.6f} "
          f"model={probe.model}")

    if not store.exists():
        store.create()
        print(f"  created collection {settings.collection.name}")

    vectors = embedder.embed([r.text for r in records])
    store.add(
        ids=[r.id for r in records],
        embeddings=vectors,
        documents=[r.text for r in records],
        metadatas=[r.metadata() for r in records],
    )
    print(f"  wrote {len(records)} chunks; collection count = {store.count()}")

    lexical = LexicalIndex(root / "var" / "bm25" / "index.json")
    lexical.build([r.id for r in records], [r.text for r in records])
    lexical.save()
    print(f"  built BM25 index over {len(lexical)} chunks\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
