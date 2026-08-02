# Rollback rehearsal — C.Walts v0.3.0-rc.2 (HISTORICAL RECORD)

> ## This document is frozen. Do not follow it.
>
> **It is a record of what was executed on 2026-08-01 at `v0.3.0-rc.2`. It is
> not a current-state manifest and it is not the active rollback procedure.**
>
> The active procedure is **[`docs/rollback.md`](../rollback.md)**. Use that.
>
> Every count below — 48 chunks, 97 chunks, the commit list, the branch name,
> the backup stamp — was true when it was written and is not true now. The
> corpus has since changed size more than once, and Gate 1 (`v0.4.0-dev.2`)
> removed the evaluation cases from production entirely. A reader who copies a
> number out of this file into a verification step will be checking the wrong
> thing.
>
> It is preserved unedited because it is the only record of a *measured* failure
> mode: restoring `chroma.sqlite3` alone silently desynchronised the vector and
> lexical stores, and retrieval kept answering. That finding is why the active
> procedure restores both stores together and refuses a backup it has not
> verified. Rewriting these numbers to match the present would destroy the
> evidence and teach nothing.
>
> Split out of `docs/rollback.md` at Gate 1.1 §3, 2026-08-02, unchanged apart
> from this header.

---

Every step below was executed and verified on 2026-08-01, not merely written
down. Evidence: `docs/evidence/smoke-test.json`, section `11.7 rollback`.

Nothing here touches the BADGR Harness. Its store
(`/home/t0n34781/projects/badgr_harness/rag_db/chroma.sqlite3`) is outside this
project root and structurally unreachable from this code — `resolve_inside_project()`
refuses any path outside the project, and `assert_allowed()` refuses any
collection name outside the allowlist.

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
MCP server; `ollama`, `filesystem`, and `memory` were confirmed still registered
after the removal rehearsal.

## 2. Restore the collection from backup

```bash
ls -1 var/backups/                       # newest snapshot last
sqlite3 "file:var/backups/<STAMP>/chroma.sqlite3?mode=ro" "SELECT name FROM collections;"
sha256sum -c var/backups/<STAMP>/chroma.sqlite3.sha256

# restore
mv var/chroma var/chroma.broken.$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p var/chroma
cp var/backups/<STAMP>/chroma.sqlite3 var/chroma/chroma.sqlite3

# REQUIRED: the lexical index is not in the snapshot — see below
NFR_ALLOW_WRITES=true .venv/bin/python scripts/ingest.py --commit
```

Verified snapshot: `var/backups/20260801T124553Z/` — checksum verified, and a
read-only open of the restored copy lists `badgr_natural_flow_v1`.

### The lexical index must be rebuilt too

**Measured during the rc.2 rollback rehearsal on 2026-08-01, and the reason the
last command above is not optional.** Restoring `chroma.sqlite3` alone rolled
the vector store back from 97 chunks to 48 and left `var/bm25/index.json` still
holding all 97. Retrieval still returned results, so the failure was silent from
the caller's side.

`natural_flow_collection_health` caught it and reported `DEGRADED` with
`count: 48` against `lexical_index_chunks: 97`, which is exactly what that field
exists for. Check it after any restore:

```bash
.venv/bin/python -c "
import sys; sys.path.insert(0,'src'); sys.path.insert(0,'.')
import importlib.util
spec = importlib.util.spec_from_file_location('s','mcp/server.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
h = m.tool_collection_health()
print(h['status'], h['count'], h['lexical_index_chunks'])"
```

`OK` with the two counts equal means the restore is complete. `DEGRADED` with
them unequal means the lexical index is still describing a collection that no
longer exists.

### rc.2 rollback rehearsal — executed, not described

| Step | Result |
|---|---|
| Reindex with `delete_stale=true` | 97 written, 1 stale deleted, backup verified |
| Backup checksum re-checked from the shell | `OK` |
| Backup opened read-only | lists both collections, 48 + 1 rows |
| Restore performed | collection returned to exactly 48 |
| Query against the restored store | 6 hits, retrieval functional |
| Health after restore | `DEGRADED` — caught the stale lexical index |
| Re-applied reindex | 97 chunks, health `OK`, lexical 97 |
| Harness store MD5 throughout | `bdcbe32b706c6ccce1f62e8e9f2d2c49`, unchanged |

## 3. Or recreate the collection from source

Chunk ids are content-derived, so a rebuild reproduces the same 48 ids from the
same corpus. This is the preferred path when the corpus itself is intact:

```bash
rm -rf var/chroma var/bm25
.venv/bin/python scripts/ingest.py                       # dry run first
NFR_ALLOW_WRITES=true .venv/bin/python scripts/ingest.py --commit
.venv/bin/python scripts/smoke_test.py
```

## 4. Roll back the code

```bash
git log --oneline --decorate                 # find the checkpoint to return to
git checkout de3bd88                         # verified baseline, empty corpus
# or drop just the last checkpoint, keeping history:
git revert <sha>
```

Checkpoint commits on `feat/natural-flow-rag-activation`:

| Commit | Checkpoint |
|---|---|
| `de3bd88` | verified baseline |
| `235a4d0` | corpus schema and deterministic ingestion |
| `59cd9ef` | explicit nomic embedding contract, real collection |
| `53f1c49` | measured hybrid retrieval and evaluation |
| `a3e0795` | MCP tools and project registration |

`main` has never been used as a working branch, so the feature branch can be
abandoned without touching it.

## 5. Disable writes entirely

Writes are already off by default: `writes.allow_writes: false` in
`config/rag.yaml`, and every write path additionally requires `confirm=true`.
The ingestion commits in this build ran with `NFR_ALLOW_WRITES=true` scoped to a
single process. To be certain no environment override is in play:

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

## 7. Repository topology

The remote's default branch is `feat/natural-flow-rag-activation` — the
repository was created from that branch, and `main` does not exist remotely.
Promoting the release candidate to `main` is an owner decision after acceptance:

```bash
git branch -m feat/natural-flow-rag-activation main   # or merge, whichever you prefer
git push -u origin main
gh repo edit Ch405-L9/C.Walts --default-branch main
```

## 8. What rollback cannot lose

- The four approved MP3 references and the source bundle: never modified, held
  under `references/media/` and in the original handoff package.
- The approved corpus text: committed to the private remote.
- The Harness production store: MD5 `bdcbe32b706c6ccce1f62e8e9f2d2c49` before
  ingestion and after the full smoke suite.
