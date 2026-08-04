# Rollback — C.Walts natural-flow RAG

Active operational procedure. Follow this document.

**No production count appears anywhere below.** Every count in this procedure is
*derived* at the moment you run it — from source discovery, or from the manifest
inside the snapshot you are restoring. This is deliberate. The corpus has changed
size more than once, and a number typed into a procedure is a number that will
eventually be wrong while still looking authoritative.

> ### Historical reports are not current-state manifests
>
> `docs/history/rollback-rc2.md`, `docs/owner-test-report-rc2.md`, the entries in
> `docs/execution-log.md`, and every file under `docs/evidence/` record what was
> true on the date they were written. They are evidence, not configuration.
>
> **Never take an expected count, id list, commit sha, or backup stamp from one
> of them.** They are correct about the past and silently wrong about the
> present. If you need to know what the store should hold right now, derive it —
> §2.3 shows how.

Nothing here touches the BADGR Harness. Its store
(`/home/t0n34781/projects/badgr_harness/rag_db/chroma.sqlite3`) is outside this
project root and structurally unreachable from this code:
`resolve_inside_project()` refuses any path outside the project, and
`assert_allowed()` refuses any collection name outside the allowlist.
The historical BADGR Harness MD5 recorded in earlier evidence is a byte-level
observation, not a permanent acceptance value. For write-capable operations,
capture a fresh semantic baseline with `scripts/harness_invariant.py` before the
operation and compare against it afterward.

<!-- Section numbering note: mcp/server.py emits "docs/rollback.md §2" and
     "docs/rollback.md §3" in live error messages. §2 must stay "restore from
     backup" and §3 must stay "rebuild from source". tests/test_rollback_docs.py
     asserts both anchors resolve. Renumber only with that test. -->

---

## 1. Remove the MCP registration

```bash
cd /home/t0n34781/projects/natural-language-flow-rag
claude mcp remove natural-flow-rag -s project
claude mcp list          # unrelated servers must still be listed
```

Re-register:

```bash
claude mcp add natural-flow-rag --scope project -- \
  /home/t0n34781/projects/natural-language-flow-rag/.venv/bin/python \
  /home/t0n34781/projects/natural-language-flow-rag/mcp/server.py
```

Registration lives in `.mcp.json` in the project. Removing it changes no other
MCP server.

## 2. Restore the store from backup

### 2.1 Choose a backup, and know which kind you have

Two kinds exist, and **they are not interchangeable**:

| Location | Contains | Safe to restore alone? |
|---|---|---|
| `var/snapshots/<STAMP>/` | Chroma database **and** its HNSW directories, `var/bm25/index.json`, `config/sources.yaml`, plus `snapshot.json` | **Yes** — this is a complete restore point |
| `var/backups/<STAMP>/` | `chroma.sqlite3` and its `.sha256` only | **No** — vector store only, no lexical index |

`var/backups/` entries are the automatic pre-delete backups taken by the write
tools. They are a real safety net for the vector store and nothing more.
Restoring one **without rebuilding the lexical index leaves the two arms
describing different collections**, and retrieval keeps answering from the stale
one. That is not hypothetical — it was measured during the rc.2 rehearsal and is
recorded in `docs/history/rollback-rc2.md`. If a `var/backups/` entry is all you
have, follow §2.5.

List and inspect candidates:

```bash
ls -1 var/snapshots/         # complete restore points, newest last
ls -1 var/backups/           # vector-store-only backups, newest last
```

### 2.2 Verify before you restore — and refuse what will not verify

```bash
.venv/bin/python scripts/store_snapshot.py --verify var/snapshots/<STAMP>
```

This does not check a hash and stop. **A damaged database still hashes.** It
opens the snapshot and interrogates it: the collection is present with the count
its own manifest claims, the snapshot's BM25 index covers exactly the snapshot's
chunks, and an exact-term query returns hits from the restored index.

**If this command fails, that snapshot is not a restore point. Do not restore
it.** `--restore` re-runs the same verification and refuses on any failure, so
there is no flag that forces an unverified snapshot into production — this is by
design, not an omission. A snapshot that will not verify is missing its BM25
index, has a digest that no longer matches its manifest, holds a collection whose
row count disagrees with its manifest, or cannot answer a lexical query. In every
one of those cases restoring it produces a store that looks alive and is wrong.

If no snapshot verifies, go to §3 and rebuild from source. A rebuild from an
intact corpus is always safer than a restore from a backup you cannot trust.

### 2.3 Restore

```bash
.venv/bin/python scripts/store_snapshot.py --restore var/snapshots/<STAMP>
```

Restores **both** stores together — the Chroma database with its HNSW
directories, and `var/bm25/index.json`. Restoring them together is the whole
point; see §2.1.

### 2.4 Verify the restored store — all of it

```bash
.venv/bin/python scripts/verify_restore.py --expect-from-sources
```

Exit status 0 means every one of these passed:

| Check | Why it is here |
|---|---|
| **expected count derived from source discovery** | chunk ids are content- and source-derived, so discovery reproduces exactly the id set a correct store holds. No number is read from any document. |
| **expected *id set* matches, not just the count** | two stores can hold the same number of the wrong chunks |
| both collections reopen | a store that cannot be opened has not been restored |
| Chroma/BM25 id-set parity (not just equal counts) | equal counts are not enough; the rc.2 failure passed a count check before it was caught |
| `evaluation_case` count is zero, checked two ways | restoring a pre-Gate-1 backup is the one operation that can silently undo Gate 1 and re-contaminate the benchmark |
| exact lexical retrieval returns hits | proves the lexical arm is live, not merely present |
| production retrieval returns chunks | proves the dense arm and fusion work end to end |
| feedback collection, separately and by name | a different collection with a different lifecycle; it must not be assumed healthy because the corpus is |
| BADGR Harness invariant | checked only when a fresh operation baseline is supplied; otherwise current fingerprints are reported and external immutability is explicitly not claimed |

For a restore-sensitive or write-capable operation, capture and require a fresh
Harness invariant:

```bash
.venv/bin/python scripts/harness_invariant.py capture \
  --database /home/t0n34781/projects/badgr_harness/rag_db/chroma.sqlite3 \
  --require-quiescent \
  --output var/<operation>/harness_baseline.json

.venv/bin/python scripts/verify_restore.py --expect-from-sources \
  --harness-baseline var/<operation>/harness_baseline.json \
  --require-harness-invariant
```

The Harness guard is read-only. It uses SQLite's backup API for a temporary
analysis snapshot, deletes that snapshot, and compares schema, logical database
digest, collection inventory, per-collection ID sets, and canonical
document/metadata digests. Raw SQLite byte drift alone is diagnostic; semantic
drift, collection loss, record loss, unresolved segment references, corruption,
or an unexpected foreign-key finding fails closed.

Temporary snapshot cleanup is part of the invariant. If source-open,
destination-open, backup-copy, analysis, or unlink cleanup fails, the guard does
not report a successful capture. `verify_restore.py --require-harness-invariant`
also requires the supplied baseline and the current capture to be quiescent.
Failed, malformed, wrong-path, source-writing, prohibited-operation, or
non-quiescent baselines are rejected before semantic comparison.

The current BADGR Harness Chroma schema has a known upstream anomaly:
`segments.collection` references singular `collection(id)` while the actual
parent table is `collections`. The guard reports that anomaly only when every
segment value resolves logically to `collections.id`, all embeddings resolve
through recognized collections, `quick_check` and `integrity_check` return `ok`,
and no additional foreign-key finding appears.

If the corpus on disk is itself untrusted or was rolled back with the code, derive
the expectation from the snapshot instead:

```bash
.venv/bin/python scripts/verify_restore.py --expect-from-snapshot var/snapshots/<STAMP>
```

That path is weaker — a snapshot manifest records counts, not an id list — so
prefer `--expect-from-sources` whenever the corpus is intact.

Then confirm the two arms agree from the server's own point of view:

```bash
.venv/bin/python scripts/mcp_session_check.py
.venv/bin/python scripts/smoke_test.py
```

### 2.5 If all you have is a `var/backups/` entry

Vector store only. The lexical index must be rebuilt or the restore is
incomplete:

```bash
sha256sum -c var/backups/<STAMP>/chroma.sqlite3.sha256
sqlite3 "file:var/backups/<STAMP>/chroma.sqlite3?mode=ro" "SELECT name FROM collections;"

mv var/chroma var/chroma.broken.$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p var/chroma
cp var/backups/<STAMP>/chroma.sqlite3 var/chroma/chroma.sqlite3

# NOT OPTIONAL — without this the lexical index still describes the old collection
NFR_ALLOW_WRITES=true .venv/bin/python scripts/ingest.py --commit

.venv/bin/python scripts/verify_restore.py --expect-from-sources
```

The `--commit` step rebuilds `var/bm25/index.json` from the restored corpus. The
verification step is what proves it worked; do not skip it because the restore
"looked fine". In the rc.2 rehearsal it looked fine.

## 3. Or rebuild the store from source

Chunk ids are derived from source id and chunk content, never from file paths, so
a rebuild from an intact corpus reproduces exactly the same ids. **This is the
preferred path whenever `corpus/raw/` is intact** — it depends on the corpus and
the configuration rather than on a backup being trustworthy.

```bash
rm -rf var/chroma var/bm25
.venv/bin/python scripts/ingest.py                       # dry run first — read the counts
NFR_ALLOW_WRITES=true .venv/bin/python scripts/ingest.py --commit
.venv/bin/python scripts/verify_restore.py --expect-from-sources
.venv/bin/python scripts/smoke_test.py
```

Read the dry-run output before committing. It reports the chunk count per source
and writes the full id list to `corpus/manifests/dryrun-<STAMP>.json`. That
manifest is the current-state record — not any document under `docs/`.

## 4. Roll back the code

```bash
git log --oneline --decorate         # find the checkpoint to return to
git revert <sha>                     # drop one change, keeping history
git checkout <sha>                   # or return to a specific checkpoint
```

Derive checkpoints from the log rather than from a table here; a hard-coded
commit list goes stale exactly like a hard-coded count. Tagged releases are the
stable anchors:

```bash
git tag --list -n1
```

`v0.3.0-rc.2` is immutable and must never be retagged or moved.

**Code and store roll back independently.** Returning the code to an earlier
commit does not change `var/chroma` or `var/bm25`, and restoring an old store
does not change the code. If you roll the code back across an ingestion change,
re-run §2.4 — and if the corpus itself moved with the code, derive the
expectation from the snapshot rather than from source discovery.

## 5. Disable writes entirely

Writes are off by default: `writes.allow_writes: false` in `config/rag.yaml`, and
every write path additionally requires `confirm=true`. Ingestion commits run with
`NFR_ALLOW_WRITES=true` scoped to a single process. To be certain no environment
override is in play:

```bash
unset NFR_ALLOW_WRITES
grep -n 'allow_writes' config/rag.yaml      # must read false
```

## 6. Remove accumulated feedback

`natural_flow_feedback` writes to `badgr_natural_flow_feedback_v1`, never to the
retrieval corpus. Dropping it loses no corpus data:

```bash
.venv/bin/python -c "
import sys; sys.path.insert(0,'src')
from natural_flow_rag.vector_store import open_store
s = open_store(); s.client.delete_collection('badgr_natural_flow_feedback_v1')
print('feedback collection removed; retrieval corpus count =', s.count())"
```

Note that `verify_restore.py` will then report the feedback collection as failing
to reopen. That is correct: it is checked separately precisely so its absence is
visible rather than assumed.

## 7. Repository topology

Promoting a release candidate to `main` is an owner decision after acceptance.
Check the current topology rather than assuming it:

```bash
git branch --show-current
git branch -r
gh repo view --json defaultBranchRef
```

## 8. What rollback cannot lose

- The approved media references and the source bundle: never modified, held
  under `references/media/` and in the original handoff package.
- The approved corpus text: committed to the private remote.
- The evaluation regression fixtures under `eval/regression/`: never ingested, so
  no store operation can affect them.
- The BADGR Harness production store: outside this project root. It is checked
  by operation-scoped semantic capture/verify when a fresh baseline is supplied;
  without that baseline, restore verification reports fingerprints but does not
  claim external immutability.

## 9. Historical record

The rc.2 rollback rehearsal — including the measured 48/97 desynchronisation that
this procedure exists to prevent — is preserved verbatim in
**`docs/history/rollback-rc2.md`**. Read it to understand *why* §2 restores both
stores and refuses unverified backups. Do not follow its commands or reuse its
counts.
