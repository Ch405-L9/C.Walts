# Rollback — C.Walts natural-flow RAG

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
```

Verified snapshot: `var/backups/20260801T124553Z/` — checksum verified, and a
read-only open of the restored copy lists `badgr_natural_flow_v1`.

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
