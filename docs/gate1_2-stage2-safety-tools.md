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
  --manifest <path-to-stage2_public_sources.yaml> \
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

## Stage 2.2B gate

Before any production corpus mutation, Stage 2.2B must show:

- the exact proposed files and chunks;
- corpus lint;
- a passing dry-run reindex comparison JSON;
- would-add, stale, unchanged, duplicate, content-changed, and metadata-changed
  IDs;
- source/license/provenance validation JSON;
- a verified backup and rollback checkpoint.

These tools do not authorize mutation by themselves. They are preconditions for
owner approval immediately before the first production corpus write.
