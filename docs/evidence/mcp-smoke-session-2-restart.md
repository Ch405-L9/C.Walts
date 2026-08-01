Warning: no stdin data received in 3s, proceeding without it. If piping from a slow command, redirect stdin explicitly: < /dev/null to skip, or wait longer.
Restart check done. Raw results above, in order:

**1. `natural_flow_collection_health`**
```json
{
  "collection": "badgr_natural_flow_v1",
  "exists": true,
  "count": 48,
  "dimension_declared": 768,
  "dimension_expected": 768,
  "dimension_measured": 768,
  "dimension_match": true,
  "embedding_model": "nomic-embed-text",
  "vector_l2_norm": 1.0,
  "space": "cosine",
  "persistence_path": "/home/t0n34781/projects/natural-language-flow-rag/var/chroma",
  "lexical_index_chunks": 48,
  "lexical_index_error": null,
  "ollama_reachable": true,
  "writes_allowed": true,
  "status": "OK"
}
```
`writes_allowed: true`.

**2. `natural_flow_reindex` (no confirm arg)** — exact refusal:
```json
{
  "error": {
    "code": "CONFIRMATION_REQUIRED",
    "message": "natural_flow_reindex requires confirm=true"
  }
}
```

**3. `natural_flow_reindex` (confirm=true, no dry_run)**
```json
{
  "dry_run": true,
  "sources": ["cmudict", "owner_examples", "cwalts_style_rules", "cwalts_evaluation_cases", "cwalts_negative_patterns"],
  "chunks_in_corpus": 48,
  "chunks_in_collection": 48,
  "would_add": [],
  "would_add_count": 0,
  "stale_in_collection": [],
  "stale_count": 0,
  "note": "Nothing written. Call again with dry_run=false to commit."
}
```
`dry_run: true`. Nothing written — `would_add_count: 0`, `stale_count: 0`, note say nothing written.

**4. `natural_flow_collection_health` again** — `count: 48`
```json
{
  "collection": "badgr_natural_flow_v1",
  "exists": true,
  "count": 48,
  "dimension_declared": 768,
  "dimension_expected": 768,
  "dimension_measured": 768,
  "dimension_match": true,
  "embedding_model": "nomic-embed-text",
  "vector_l2_norm": 1.0,
  "space": "cosine",
  "persistence_path": "/home/t0n34781/projects/natural-language-flow-rag/var/chroma",
  "lexical_index_chunks": 48,
  "lexical_index_error": null,
  "ollama_reachable": true,
  "writes_allowed": true,
  "status": "OK"
}
```

---

Collection survive restart: yes — 48 chunks, dim 768 match, lexical index 48, status OK.
Reindex refuse without confirm: yes — `CONFIRMATION_REQUIRED`, "natural_flow_reindex requires confirm=true".
Reindex default dry run, wrote nothing: yes — `dry_run: true` unasked, count stay 48 before and after.
