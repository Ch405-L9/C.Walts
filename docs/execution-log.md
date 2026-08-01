# Execution log — C.Walts natural-flow RAG activation

Required by Prompt C §14. No secrets, no raw private owner text, no full
retrieved documents. Timestamps are local host time (UTC-04).

---

## 2026-08-01 — Checkpoint 1: verified baseline

### State verification (Prompt C §1)

| State item | Expected | Observed | Action |
|---|---|---|---|
| Prompt B audit report | exists | `/home/t0n34781/workspace/natural-flow-rag-audit.md` referenced by config; not re-audited | none |
| Natural-flow project | `/home/t0n34781/projects/natural-language-flow-rag` | present | proceed |
| File count | ~34 | 34 tracked files at baseline commit | matches |
| Unit tests | ~52 pass | 52 passed | proceed |
| Ruff | passes | `All checks passed!` | proceed |
| `pip check` | n/a | `No broken requirements found.` | proceed |
| `corpus/raw/` | no usable corpus | empty | corpus supplied by C.Walts package at CP2 |
| `var/chroma/` | unpopulated | empty directory | create collection at CP3 |
| Writes | disabled | `writes.allow_writes: false` | gate honoured until CP3 |
| `badgr_natural_flow_v1` | not populated | does not exist | create at CP3 |
| MCP server | not registered | no `.mcp.json` in project | register at CP5 |
| Similarity floor | unset | `similarity_floor: null` | measure at CP4 |
| Git repository | unknown | **NOT a git repository** | `git init` performed |
| Remote | unknown | none | private `Ch405-L9/C.Walts` created |
| Ollama | reachable | reachable; `nomic-embed-text:latest` digest `0a109f422b47` | proceed |

### Handoff package verification (Prompt D §B)

- `C.Walts_Claude_Handoff_FULL.zip` (146.6 MB) extracted to
  `/home/t0n34781/workspace/natural-flow-audit/extracted/`.
- `sha256sum -c checksums.sha256`: **22/22 OK**, including the four positive
  ElevenLabs MP3 references and the 151 MB source bundle.

### Actions

| Time | Action | Result |
|---|---|---|
| 08:4x | Extract + verify FULL package | 22/22 checksums OK |
| 08:4x | Harden `.gitignore` for media/archive/db exclusion | media, `*.zip`, `var/`, `*.sqlite3` excluded |
| 08:4x | `git init -b main`; branch `feat/natural-flow-rag-activation` | on feature branch, `main` never used as working branch |
| 08:4x | Staged-binary gate: `git ls-files --cached \| grep -iE '\.(mp3\|mp4\|m4a\|wav\|zip\|sqlite3)$'` | empty — no binaries staged |

Rollback point: the pre-existing working tree is unchanged apart from
`.gitignore`, `CHANGELOG.md`, and `docs/`. Deleting `.git/` returns the project
to its pre-checkpoint state.

Commit `de3bd88` — `chore: establish verified natural-flow RAG baseline`.
Pushed to `origin/feat/natural-flow-rag-activation`.
Remote `https://github.com/Ch405-L9/C.Walts` created **private** (verified via
`gh repo view --json visibility` → `PRIVATE`).

---

## 2026-08-01 — Checkpoint 2: corpus schema and ingestion safety

### Material placed (Prompt D §B, README §5.4)

| Destination | Files | Committed? |
|---|---|---|
| `corpus/raw/owner_examples/` | before/after pairs, positive voice references, derived reference scripts | yes (private remote, owner-owned) |
| `corpus/raw/style_rules/` | market voice-delivery rules | yes |
| `corpus/raw/evaluation/cases/` | evaluation prompts EVAL-001…015 | yes |
| `corpus/raw/evaluation/negative/` | rejected/contrast delivery descriptions | yes |
| `corpus/raw/evaluation/audio_reference_manifest.yaml` | audio manifest with hashes | yes (not ingested — YAML is not a loader-supported type) |
| `references/media/positive/` | 4 approved MP3s (3.9 MB) | **no** — gitignored, local evidence only |
| `references/transcripts/` | Theological.txt, 11labs transcript, original reference_scripts.md | **no** — gitignored, unverified/third-party provenance |
| `prompts/` | Prompt C, Prompt D, README, OWNER_DECISIONS, checksums | yes |

The 151 MB source bundle was **not** copied into the project. It stays at
`/home/t0n34781/workspace/natural-flow-audit/` and is referenced by SHA-256
`4145aa44…` in the audio manifest.

Derived file: `corpus/raw/owner_examples/approved_reference_scripts.md` contains
only SCR-001 (B. Lawson introduction) and SCR-002 (technical security passage).
The Hanna reflective passage was excluded — reconstructed from an imperfect
transcript, publication provenance unestablished, evaluation-only per the
C.Walts README limitation.

### Verified incompatibility found and fixed (narrowest change)

**Evidence.** The first dry run produced **262 chunks from 6,185 tokens** — an
average of 23 tokens per chunk, with 125 fragments from a single 1,512-word
document. Cause: the `approved_example` profile's `never_merge_separate_examples`
flag split on blank lines, so every markdown bullet became its own record. Chunks
that small cannot carry a rewrite example and would have produced meaningless
dense retrieval.

**Change.** `example_separator` added to the chunking profile contract:
`blank_line` (default, unchanged behaviour for line-oriented records such as
CMUdict) and `heading` (one record per H2 section or horizontal rule, paragraphs
inside one record packed back up to target). `approved_example` now uses
`heading`. This is the configuration change Prompt C §7 explicitly permits when
evaluation demonstrates a better setting.

**Result.** 48 chunks, 6,240 tokens, average 130 tokens per chunk. Three new
chunking tests cover both modes; 55 tests pass.

### Corpus lint (Prompt D §G1)

`scripts/corpus_lint.py` added. Result: **0 failures, 1 warning**.

| doc_type | chunks | share | class |
|---|---:|---:|---|
| approved_example | 26 | 54.2% | primary |
| evaluation_case | 17 | 35.4% | auxiliary |
| style_rule | 4 | 8.3% | primary |
| negative_pattern | 1 | 2.1% | auxiliary |

No auxiliary class exceeds the 40% cap. The single warning is
`market_voice_delivery_rules.md#3`, whose evaluation-dimension table contains the
phrase "production-ready" as scoring vocabulary — corpus text, not a claim about
this build.

### Ingestion dry run

48 chunks / 6,240 tokens / ~0.1 MiB of vectors. Single license in play:
`Proprietary — BADGRTechnologies LLC`. Manifest written to
`corpus/manifests/dryrun-20260801T124137.json`. Nothing written to the store.

Commit `235a4d0` — `feat: add licensed corpus schema and deterministic ingestion`.
Pushed. Rollback point: `git revert 235a4d0` restores the empty-corpus state; no
database existed yet at this checkpoint.

---

## 2026-08-01 — Checkpoint 3: isolated Chroma and embedding contract

### Disposable-collection proof (Prompt C §8.1)

Ran in `var/tmp/contract-probe/`, removed afterwards. Ten checks, all PASS:

| Check | Result |
|---|---|
| dimension is 768 through the project's own client | PASS (L2 norm 1.000000) |
| explicit vectors accepted | PASS |
| stored vector dimension is 768 | PASS |
| `query_texts=` and explicit query embedding agree | PASS (same id, distance delta < 1e-4) |
| persisted schema names `nomic-embed-text` | PASS |
| persisted schema is **not** Chroma's default embedder | PASS |
| schema-declared dimension is 768 | PASS |
| reopen without an embedding function still matches | PASS |
| no ONNX fallback downloaded or invoked | PASS (cache unchanged: 7 pre-existing files) |
| persistence inside the project root | PASS |

**Correction to an audit assumption, with evidence.** The audit expected the
embedding function to be recorded in `collections.config_json_str`. On ChromaDB
1.5.8 that column is `"{}"`; the record lives in `collections.schema_str` as
`"embedding_function":{"type":"known","name":"ollama","config":{"model_name":
"nomic-embed-text",...}}`. The verification script was corrected to read the
column that actually carries the contract — a check that reads the wrong column
would have passed vacuously in the other direction.

**Hazard B2 re-tested as an experiment.** A collection created with an explicit
`OllamaEmbeddingFunction` was reopened with `get_collection(name)` and **no**
embedding function — the exact mistake that made `badgr_corpus` and
`job_opportunities` unsafe. Chroma 1.5.8 reconstructs the persisted `known`
Ollama function: identical ids and identical distances to 6 decimal places, and
no ONNX model fetched. The python-side attribute still reports
`DefaultEmbeddingFunction`, so the attribute is not evidence; the query path is.

### Real collection (Prompt C §8.2)

Writes stayed **disabled in configuration**. `writes.allow_writes` is still
`false` in `config/rag.yaml`; the commit ingest ran with `NFR_ALLOW_WRITES=true`
scoped to that single process, so the MCP write tools remain gated by default.

| Item | Value |
|---|---|
| Collection | `badgr_natural_flow_v1` |
| Count | 48 |
| Dimension declared / expected / measured | 768 / 768 / 768 |
| Space | cosine |
| Persistence | `/home/t0n34781/projects/natural-language-flow-rag/var/chroma` |
| Embedding model recorded | `nomic-embed-text` |
| Health status after fresh process | `OK` |
| Free disk at write time | 71 GB (floor: 20 GB) |

`schema_str` for the real collection records `"name":"ollama"` and
`nomic-embed-text`, and contains no reference to a default or MiniLM embedder.

### Production data untouched

`/home/t0n34781/projects/badgr_harness/rag_db/chroma.sqlite3` MD5 before and
after ingestion: `bdcbe32b706c6ccce1f62e8e9f2d2c49` — unchanged.

### Rollback point

Verified backup: `var/backups/20260801T124553Z/chroma.sqlite3` (+ `.sha256`,
`sha256sum -c` OK). Recreate path: delete `var/chroma/` and re-run
`NFR_ALLOW_WRITES=true .venv/bin/python scripts/ingest.py --commit`; ingestion is
idempotent because chunk ids are content-derived.

Commits `59cd9ef` (contract + ingest) and `4cc6641` (lint fix). Both pushed.
Version `0.2.0`.

---

## 2026-08-01 — Checkpoint 4: measured hybrid retrieval and evaluation

### Defect found before measuring: the lexical arm was dead

`var/bm25/index.json` held 48 chunk ids and **zero token lists**. Cause:
`LexicalIndex.save()` read the tokenized corpus back off the `BM25Okapi` object
via `hasattr(self._bm25, "corpus")`; `rank_bm25` keeps only `doc_freqs` and
`doc_len`, so the attribute never existed and a class-level empty fallback was
written instead. On load, `BM25Okapi([])` raised `ZeroDivisionError`, and
`Retriever._lexical` caught the exception and returned `[]`.

Consequence: hybrid retrieval had been running **dense-only**, and `H*` /
`L-L%` — the exact notation BM25 exists to protect — could not be retrieved
lexically at all. The health tool reported `lexical_index_chunks: 48` because it
counted ids, so the failure was invisible from every reporting surface. No test
covered the save/load round trip.

Fixes, all narrow:

- `LexicalIndex` keeps its own tokenized corpus; `save()` refuses to write an
  index with no non-empty token lists; `load()` refuses to load one.
- `Retriever._lexical` still degrades to dense-only, but records the failure in
  `RetrievalResult.lexical_error` so the evaluation harness and health tool see
  it.
- Five new tests, including a save→load→search round trip that asserts `L-L%`,
  `H*`, and `ToBI` retrieve after a reload.

After rebuilding the index, all three probes retrieve the correct chunk
(BM25 score 9.63). `break index` returns nothing — the term is genuinely absent
from the approved corpus; recorded as a limitation, not a bug.

### Preservation checker (Prompt C §10, §11.5)

`src/natural_flow_rag/preservation.py` added: numbers, dates, backticked and
caller-supplied protected terms, obligation strength, certainty hedging, and
proper names. It detects; it never rewrites. Eleven unit tests plus the ten
controlled cases in `eval/expectations.yaml`.

### Contamination policy — measured, then enforced

The first evaluation run showed **1 negative-pattern chunk** in EVAL-009's
ranked results ("why does this sound difficult when read aloud, then rewrite
it") — a rewrite request, where Prompt D forbids negative material.

Enforced as a filter rather than as advice: `exclude_doc_types_by_default:
[negative_pattern]` with `contrast_intent_patterns` in `config/rag.yaml`. A
query without contrast intent gets `{"doc_type": {"$ne": "negative_pattern"}}`,
and because BM25 knows nothing about metadata, the exclusion is re-applied to the
fused list and again after neighbour expansion. An explicit caller filter is
never overridden. Four tests cover the policy. Contamination is now **0**, and
EVAL-011 (explicit contrast request) still retrieves the negative document.

### Results — `docs/evidence/evaluation-report.json`

| Metric | Result | Threshold (Prompt D) |
|---|---|---|
| Useful hit @5 | **12/12 (100%)** | ≥80% across EVAL-001…012 |
| Exact-term retrieval (`ToBI`, `H*`, `L-L%`) | **PASS** — lexical hit and literal text in ranked results | must pass |
| Negative-source contamination | **0** | zero |
| Positive-source ratio | 62% | — |
| Citation failures | **0/60** ranked chunks | — |
| Lexical arm degraded | **false** | — |
| Latency p50 / p95 | **83 ms / 103 ms** | — |
| Preservation cases correct | **10/10** | all pass |
| Prompt injection (EVAL-013) | detected, fenced, not executed | must pass |
| Weak-evidence fallback (EVAL-014) | corpus refutation retrieved | must pass |

Expectations were written into `eval/expectations.yaml` **before** the first run,
naming per case which corpus material a correct retrieval must surface, so the
hit rate is scored mechanically rather than judged after the fact.

### similarity_floor: measured, left disabled, reason recorded

Top-5 cosine distances across the 15 queries: min 0.114, median 0.328, max 0.426
(similarity 0.574–0.886). Every result in that band was a useful hit, so no
threshold separates signal from noise: below 0.574 a floor excludes nothing,
above it a floor starts discarding correct answers. Fitting one to 15 queries
against a 48-chunk single-topic collection would be overfitting. `similarity_floor`
therefore stays `null`, with the revisit condition written into `config/rag.yaml`.
