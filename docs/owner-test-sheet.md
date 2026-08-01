# Owner test sheet — C.Walts natural-flow RAG

Everything below was run before this sheet was written. Copy-paste as-is.

```bash
cd /home/t0n34781/projects/natural-language-flow-rag
```

---

## 1. Health check

```bash
.venv/bin/python -c "
import sys; sys.path.insert(0,'src')
from natural_flow_rag.vector_store import open_store
import json; print(json.dumps(open_store().health().__dict__, indent=2, default=str))"
```

Expect `count: 48`, `dimension_match: true`, `embedding_function:
nomic-embed-text`, `status: OK`.

## 2. Direct CLI query

```bash
.venv/bin/python scripts/query.py "how should a technical warning be paced when read aloud"
.venv/bin/python scripts/query.py "L-L%"
```

The second is the exact-notation path: it must return the chunk containing the
literal token, not an approximate match.

## 3. Ingestion dry run

```bash
.venv/bin/python scripts/ingest.py
```

Writes nothing. Expect 48 chunks across four sources and a manifest under
`corpus/manifests/`.

## 4. Corpus lint and evaluation

```bash
.venv/bin/python scripts/corpus_lint.py
.venv/bin/python eval/run_evaluation.py
```

Expect 0 lint failures, 12/12 useful hits, exact-term PASS, 0 contamination,
10/10 preservation.

## 5. Full smoke suite

```bash
.venv/bin/python scripts/smoke_test.py
```

42 checks. Non-zero exit means something regressed; the failing check names
itself.

## 6. MCP connection check

```bash
claude mcp list
claude mcp get natural-flow-rag
```

The server is registered at **project** scope via `.mcp.json`. The first time you
open an interactive `claude` session in this directory it will ask you to approve
the project-scoped server — approve it once, and it stays approved. Until then
`claude mcp list` shows `Pending approval`, which is Claude Code's normal
behaviour for `.mcp.json` servers and not a fault in the build.

## 7. Claude Code functional test

Open `claude` in this directory and try the five prompts below.

1. **Conversational rewrite**
   > Use natural_flow_rewrite on: "When domain-wide authority is configured the
   > service account is allowed to impersonate a user for an API request and the
   > application's access is limited by the user's permissions and the OAuth
   > scopes approved in the Admin console." Target conversational. Then give me
   > your rewrite and re-check it by passing it back as `candidate`.

2. **Voice-over rewrite**
   > Use natural_flow_rewrite with target voice_over on: "BADGR Bolt keeps words
   > centered, provides adjustable reading speed, and offers optional quizzes."
   > Cite which corpus entries you used.

3. **Rhythm analysis**
   > Use natural_flow_analyze on: "The implementation configuration
   > initialization process requires validation of all environment-specific
   > dependency resolution conditions prior to execution." Explain what the
   > numbers say about reading it aloud.

4. **Exact prosody-term lookup**
   > Use natural_flow_search for `ToBI`, `H*`, and `L-L%`. Show the exact matched
   > text and its source. Do not invent definitions.

5. **Preservation-sensitive technical rewrite**
   > Use natural_flow_rewrite on: "The administrator must rotate the exposed key
   > before the service can be re-enabled. Comprehension must stay above 80
   > percent." Then pass your rewrite back as `candidate` and show me the
   > preservation report.

Prompt 5 is the one worth watching: a rewrite that softens *must* or drops *80*
comes back **refused**, with the original text returned instead.

## 8. Write-gate check (should refuse)

```bash
.venv/bin/python -c "
import importlib.util, sys, json; sys.path.insert(0,'src')
s = importlib.util.spec_from_file_location('m','mcp/server.py')
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
print(json.dumps(m.dispatch('natural_flow_reindex', {'confirm': True}), indent=2))"
```

Expect `WRITES_DISABLED`. That refusal is the feature — writes require both
`confirm=true` and `writes.allow_writes`/`NFR_ALLOW_WRITES`.

## 9. Rollback

See `docs/rollback.md`. Shortest form:

```bash
claude mcp remove natural-flow-rag -s project
rm -rf var/chroma var/bm25
.venv/bin/python scripts/ingest.py                       # dry run
NFR_ALLOW_WRITES=true .venv/bin/python scripts/ingest.py --commit
```
