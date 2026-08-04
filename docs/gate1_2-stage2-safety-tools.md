# Gate 1.2 Stage 2 Safety Tools

Stage 2.2A adds two pre-mutation guards. They are read-only and do not write
Chroma, BM25, corpus sources, backups, or evidence unless the operator explicitly
chooses an output JSON path.

## Read-only reindex comparison

```bash
.venv/bin/python scripts/compare_reindex_plan.py \
  --proposed-source-config <path-to-sources-yaml> \
  --production-store config \
  --output-json <path> \
  --dry-run
```

Optional filters:

```bash
--source <source-id>        # restrict proposed build to one source; repeatable
--allow-source <source-id>  # allowlisted source scope; repeatable
```

Exit codes:

- `0`: comparison passed.
- `1`: comparison completed and found an error condition.
- `2` or Python exception: `--dry-run` is missing, command input is invalid, or
  repository state could not be verified; treat as fail-closed.

The comparison reuses `scripts/ingest.py::build_records`, so proposed chunks use
the same chunking, normalization, metadata, and deterministic ID generation as a
production ingest. The `--dry-run` flag is required; omitting it exits before
production state is loaded, and the command has no mutation mode.

The current production Chroma records are read directly from `chroma.sqlite3`
using SQLite read-only mode. Current BM25 is read only for production parity. For
the proposed plan, the tool derives the predicted Chroma ID set from the final
in-memory record plan and separately builds a temporary BM25 index with
`LexicalIndex.build()`, `save()`, and `load()` in an isolated temp directory. It
never writes the live BM25 index or opens live Chroma through the Chroma client
during comparison. Output JSON matches
`schemas/stage2_reindex_comparison.schema.json`.

Important fields:

- `would_add_ids`: proposed deterministic IDs absent from production.
- `stale_ids`: current production IDs in the evaluated source scope that would
  disappear after an allowlisted mutation.
- `unchanged_ids`: IDs present in both states with identical canonical content
  and relevant metadata.
- `duplicate_ids`: repeated deterministic IDs in the proposed build.
- `duplicate_content_groups`: repeated canonical content digests in the proposed
  build.
- `content_changed_ids`: existing IDs whose canonical text changed.
- `metadata_changed_ids`: existing IDs whose relevant metadata changed.
- `source_scoped_current_ids` / `source_scoped_proposed_ids`: the compared ID
  scope.
- `proposed_id_parity`: whether predicted Chroma and BM25 IDs match.

The command fails on collisions, invalid proposed records, proposed Chroma/BM25
parity failure, `evaluation_case` leakage, non-allowlisted source changes, or
ambiguous stale-ID ownership. `mutation_performed` must always be `false`.

## Stage 2 source license/provenance validation

```bash
.venv/bin/python scripts/validate_stage2_sources.py \
  --manifest config/stage2_public_sources.yaml \
  --output-json <path>
```

Optional local fixture or alternate evidence roots:

```bash
--approved-root <path>  # approved snapshot/evidence root; repeatable
```

Exit codes:

- `0`: validation passed with no errors.
- `1`: validation completed and found at least one error.
- `2` or Python exception: manifest or path state could not be verified; treat
  as fail-closed.

The canonical production validation is offline. It must rely on locally preserved
source snapshots and license evidence, never network requests. Output JSON
matches `schemas/stage2_source_validation.schema.json`.

Accepted article-level licenses are:

- `CC BY 4.0`
- `CC-BY-4.0`
- `CC BY 3.0`
- `CC-BY-3.0`
- `CC0`

The validator rejects unknown or ambiguous licenses, non-commercial licenses,
`CC BY-ND` transformed sources, dataset-level permission substituted for
article-level permission, missing checksums, checksum mismatches, missing
snapshots, missing attribution, missing extraction locator capability, undeclared
third-party exclusions, duplicate source IDs, duplicate stable article IDs,
conflicting licenses or checksums for the same article, inconsistent snapshot
reuse, and evidence paths that escape approved roots.

`config/stage2_public_sources.yaml` is a Stage 2 source-audit manifest only. It
is not the production ingestion manifest; `config/sources.yaml` remains the
authority for production corpus ingestion.

## Stage 2 candidate/source exactness validation

```bash
.venv/bin/python scripts/validate_stage2_candidates.py \
  --candidates var/stage2_candidate_review/stage2_candidates.jsonl \
  --manifest config/stage2_public_sources.yaml \
  --output-json var/stage2_candidate_review/candidate_source_validation.json
```

Exit codes:

- `0`: candidate validation passed with no errors.
- `1`: validation completed and found at least one error.
- `2` or Python exception: command input or repository state could not be
  verified; treat as fail-closed.

The candidate validator checks the JSONL collection against the tracked Stage 2
audit manifest and preserved JATS snapshots. The per-record
`stage2_candidates.schema.json` shape check remains object-level only; collection
constraints are enforced by `validate_stage2_candidates.py`.

The collection-level checks enforce exactly twelve records, IDs
`ST2-CAND-001` through `ST2-CAND-012`, unique IDs, allocation `4/2/2/2/2`,
known `source_id` values, snapshot existence, snapshot checksum matches,
deterministic locator resolution, exact passage text after the declared
`jats_body_text_without_bibr_xrefs_whitespace_collapse` normalization, passage
SHA-256, project tokenizer count, false safety flags, array protected fields,
nonempty source text, and absence of final rewrite text.

The command fails closed on unresolved locators, exact-text mismatches, checksum
mismatches, duplicate IDs, allocation mismatch, missing sources, undeclared text
normalization, passage hash mismatch, token-count mismatch, EVAL-009 or holdout
references, and final rewrite fields.

## Stage 2.2B gate

Before any production corpus mutation, Stage 2.2B must show:

- the exact proposed files and chunks;
- corpus lint;
- a passing dry-run reindex comparison JSON;
- would-add, stale, unchanged, duplicate, content-changed, and metadata-changed
  IDs;
- source/license/provenance validation JSON;
- candidate/source exactness validation JSON;
- a verified backup and rollback checkpoint.

These tools do not authorize mutation by themselves. They are preconditions for
owner approval immediately before the first production corpus write.

## Operation-scoped BADGR Harness invariant

`scripts/harness_invariant.py` replaces the former permanent external MD5 gate
with a read-only semantic guard for the independently operated BADGR Harness
Chroma database.

Capture a fresh baseline immediately before a controlled write-capable
operation:

```bash
.venv/bin/python scripts/harness_invariant.py capture \
  --database /home/t0n34781/projects/badgr_harness/rag_db/chroma.sqlite3 \
  --require-quiescent \
  --output var/stage2_activation/harness_baseline.json
```

Verify immediately after the operation:

```bash
.venv/bin/python scripts/harness_invariant.py verify \
  --database /home/t0n34781/projects/badgr_harness/rag_db/chroma.sqlite3 \
  --baseline var/stage2_activation/harness_baseline.json \
  --require-quiescent \
  --output var/stage2_activation/harness_postcheck.json
```

The tool opens the source database read-only, creates a temporary SQLite
backup-API snapshot for deterministic analysis, and deletes that snapshot before
exit. It does not checkpoint WAL, run `VACUUM`, run `REINDEX`, repair, restore,
stop services, or retain database bytes.

Snapshot cleanup is fail-closed. `sqlite_backup_snapshot()` owns the temporary
file until it successfully returns a usable path, so source-open,
destination-open, and backup-copy failures delete the temporary file before the
exception propagates. After a snapshot is returned, `capture()` deletes it during
normal completion and handled analysis failures. A successful capture is not
possible when the temporary snapshot still exists; cleanup failure is reported as
`temporary_snapshot_cleanup_failed`.

Connection closing is non-interrupting during cleanup. Destination close, source
close, snapshot-analysis connection close, and snapshot unlink are treated as
separate cleanup attempts. A close failure is captured as diagnostic context and
cannot skip later cleanup. When an operational error already exists, such as a
source-open or backup-copy failure, that original exception remains primary and
cleanup errors are attached as notes. When analysis succeeds but the snapshot
analysis connection fails to close, the snapshot is still unlinked and the
capture report fails with `snapshot_connection_close_failed`.

The semantic invariant covers schema SHA-256, whole logical database SHA-256,
collection inventory digest, collection names and IDs, per-collection counts,
per-collection ID sets, canonical document/metadata digests, duplicate and blank
ID counts, unresolved segment-to-collection count, health failures, and the
known Chroma schema-anomaly signature. Raw file hashes are recorded as
diagnostics; raw SQLite byte drift alone is not semantic damage.

The known Chroma anomaly is reported as `known_chroma_schema_anomaly`, not
hidden. Recognition is allowed only when the actual `collections` table exists,
singular `collection` does not, the `segments.collection` foreign key targets
`collection(id)`, every raw `foreign_key_check` row is that exact `segments`
finding, every segment resolves logically to `collections.id`, every embedding
resolves through a recognized collection, `quick_check` and `integrity_check`
return `ok`, and no duplicate or blank embedding IDs exist.

`scripts/verify_restore.py` accepts `--harness-baseline` and
`--require-harness-invariant`. Without a baseline it reports current external
fingerprints and `harness_invariant_checked: false`; it does not compare against
a historical MD5 and does not claim external immutability. Stage 2.3 must
capture a fresh baseline before activation and verify it afterward. Any semantic
Harness drift blocks success and triggers the C.Walts rollback path.

Baselines are validated before comparison. A baseline must be a passing capture
for the same database path, include no findings, report no source write or
prohibited operation, confirm its temporary snapshot was deleted, include the
semantic digests and collection inventory, and report zero duplicate IDs, blank
IDs, and unresolved segment references. When `--require-quiescent` is used, both
the baseline and current capture must be quiescent: no active holder process and
no WAL or SHM sidecar. Invalid baselines fail before any successful invariant
comparison is claimed.
