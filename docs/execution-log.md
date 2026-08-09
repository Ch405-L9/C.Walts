# Execution log — C.Walts natural-flow RAG activation

Required by Prompt C §14. No secrets, no raw private owner text, no full
retrieved documents. Timestamps are local host time (UTC-04).

## 2026-08-08 — Gate 1.2 Stage 4: reporting provenance v2

Stage 4 added an additive evaluation-report schema v2. Retrieval results now
retain canonical chunk identity, source/doc identity, dense rank and cosine
distance, BM25 rank and score, and fused RRF rank and score. Headings remain
presentation metadata only.

The report marks `min_distance`/`max_distance` as evidence from a separate raw
vector query. The diagnostic query recomputes the embedding and is explicitly
outside verdict and calibration inputs. Run IDs, timestamps, latency, and
listed diagnostic floating-point paths are excluded from semantic regression
projection; arm ranks, scores, identities, and verdict fields remain stable
inputs.

No retrieval configuration or ranking behavior changed. The historical tracked
evaluation report was left untouched, and no real qrels, holdout material, or
sealed evaluation wording was processed. `CW-LIM-009` remains open.

Measured results: focused provenance tests **21 passed**; complete suite **526
passed**; Ruff and diff checks passed; corpus lint, source snapshots, restore
verification, and coverage verification passed. The read-only Harness capture
and required-quiescence verify both passed with semantic drift false and the
temporary snapshot deleted. Production remained Chroma/BM25 **96/96**, exact
parity true, evaluation_case 0, feedback 2, and unchanged ID-list and semantic
digests.

## 2026-08-08 — Gate 1.2 Stage 4-R1: report contract correction

Corrected the schema-v2 volatile path to
`cases[].results[].dense.distance` and made the projection policy explicit as
`exclude_only_enumerated_volatile_paths`. Strict Draft 2020-12 UUID and
date-time format checking now rejects malformed run metadata. Verdict and
assertion fields remain semantic.

This correction did not change retrieval behavior, RRF, thresholds, corpus, or
production state. The historical evaluation report remained untouched.

Measured results: focused contract tests **28 passed**; complete suite **533
passed**; Ruff and diff checks passed. Corpus lint, restore verification, source
snapshots, coverage verification, and the required-quiescence Harness
capture/verify cycle passed with semantic drift false. No production mutation
occurred.

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

Commit `53f1c49` — `feat: add measured hybrid retrieval pipeline`. Pushed.
Rollback point: `git revert 53f1c49` restores dense-only retrieval and removes
the preservation checker; the collection is unaffected.

---

## 2026-08-01 — Checkpoint 5: MCP tools and project registration

### Completed the approved seven-tool surface

`mcp/server.py` had 4 of 7. Added:

| Tool | Write? | Notes |
|---|---|---|
| `natural_flow_analyze` | no | Measures sentence length distribution, breath grouping, noun stacking, passive share, filler, and estimated spoken duration per register. Returns numbers and cited guidance; generates no prose, matching `natural_flow_rewrite`'s existing stance. |
| `natural_flow_feedback` | **yes** | Writes to `badgr_natural_flow_feedback_v1`, a separate allowlisted collection. A judgement about a chunk can never modify the approved corpus. |
| `natural_flow_reindex` | **yes** | `dry_run` defaults to `true`. The dry run reports which content-derived ids would be added and which are stale; it does not delete. |

`natural_flow_rewrite` now accepts an optional `candidate` and preservation-checks
it. On violation it returns the **original** text plus a warning, which is Prompt
C §10's requirement made operative rather than documented.

28 MCP tests added, including: the tool set is exactly the approved seven; both
write tools refuse without `confirm` **and** independently refuse while writes
are disabled; `reindex`'s schema defaults to dry-run; and no tool's schema
exposes a filesystem path or a collection name.

### Registration

```
claude mcp add natural-flow-rag --scope project -- \
  <project>/.venv/bin/python <project>/mcp/server.py
```

`claude mcp get natural-flow-rag` → `Scope: Project config (shared via .mcp.json)`.
Unrelated registrations (`ollama`, `filesystem`, `memory`, `plugin:vercel:vercel`)
were not touched.

`claude mcp list` shows `Pending approval` for the new server. That is Claude
Code's normal handling of a `.mcp.json` server — the owner approves it once, on
first interactive use in this directory. Approval was deliberately **not**
auto-granted on the owner's behalf.

### Defect found by the fresh-session test, not by a unit test

The first headless MCP call returned `status: OK` alongside
`lexical_index_chunks: 0`. `tool_collection_health` counted `len(LEXICAL)` on an
**unloaded** index, so it reported 0 for a healthy index — and would have
reported 48 for the tokenless index that had made retrieval dense-only. The
field existed precisely to catch that failure and could not.

Health now loads the index, reports `lexical_index_error`, and returns
`DEGRADED` when the lexical count does not match the collection count. Verified:
`lexical_index_chunks: 48`, `status: OK`.

Environment note: `claude -p` initially failed with `401 API key is invalid`
because an `ANTHROPIC_API_KEY` is exported in this environment and takes
precedence over the CLI login. All headless runs therefore use
`env -u ANTHROPIC_API_KEY claude -p …`. This affects the test harness only, not
the built system.

Commit `a3e0795` — `feat: expose natural-flow retrieval over project MCP`. Pushed.

---

## 2026-08-01 — Checkpoint 6: end-to-end smoke validation and release candidate

### In-process suite — `scripts/smoke_test.py`

**42/42 checks pass.** Evidence: `docs/evidence/smoke-test.json`. Sections
11.1 environment, 11.2 static quality, 11.4 real collection after restart,
11.5 preservation, MCP surface, and 11.7 rollback.

### Fresh Claude Code processes (Prompt C §11.6)

The MCP registration lives in the implementation project, and this session's
working directory is the audit workspace, so the smoke test could not be run by
calling the tools from here. It was run as three **separate headless Claude Code
processes** with the implementation project as the working directory — which is
the honest headless reading of "fresh process" and "restart Claude Code". Raw
transcripts are committed under `docs/evidence/`.

**Session 1** (`mcp-smoke-session-1.md`) — all seven tools, writes disabled.
Health `OK` / count 48 / dim 768 / lexical 48; search returned cited results;
analyze flagged noun stacking; rewrite **rejected** a weakened candidate and
returned the original with a warning; source_inspect returned full provenance;
both write tools refused.

That session surfaced two real defects, neither of which any unit test caught:

1. **`confirm` was in the write tools' `required` schema array.** A
   schema-conforming client therefore *cannot* omit it, so the server's own
   `CONFIRMATION_REQUIRED` refusal was unreachable — the gate was being enforced
   by client-side validation, which is a weaker guarantee than the one Prompt C
   §10 asks for. `confirm` is now optional in the schema and the server enforces
   it. Two tests pin this.
2. **`k` appeared not to cap results.** A request for `k=3` returned six
   entries: three ranked plus three neighbours. Neighbour expansion is deliberate
   and additional to `k`, but the payload gave the caller no way to tell. Results
   now carry `is_neighbor`, and `strategy` reports `ranked_n`, `neighbor_n`, and
   what `k` applies to.

**Session 2** (`mcp-smoke-session-2-restart.md`) — a second, independent process
after the fix, with `NFR_ALLOW_WRITES=true` supplied through a scratch MCP config
so the write path could be exercised end to end rather than stopping at the
config gate:

| Step | Result |
|---|---|
| Health after restart | count **48**, dim 768, lexical 48, `status: OK`, `writes_allowed: true` |
| `natural_flow_reindex` with no `confirm` | `CONFIRMATION_REQUIRED` — **from the server**, proving the fix |
| `natural_flow_reindex` with `confirm: true`, no `dry_run` | `dry_run: true` unasked; `would_add_count: 0`, `stale_count: 0`, nothing written |
| Health again | count **48** — unchanged |

`would_add_count: 0` also demonstrates ingestion idempotence: content-derived
chunk ids reproduce exactly, so a re-run adds nothing.

**Session 3** (`mcp-smoke-session-3-final.md`) — final build, verifying the two
session-1 fixes over the protocol.

### Rollback (Prompt C §11.7) — executed, not described

- Backup `var/backups/20260801T124553Z/` restores and lists
  `badgr_natural_flow_v1` on a read-only open of the restored copy.
- BADGR Harness store MD5 still `bdcbe32b706c6ccce1f62e8e9f2d2c49`.
- `claude mcp list` still shows `ollama`, `filesystem`, `memory`, and the Vercel
  plugin; only `natural-flow-rag` was added.
- Removal command verified present and documented in `docs/rollback.md`.

### Environment caveat, recorded rather than hidden

`ANTHROPIC_API_KEY` is exported in this environment and is invalid; `claude -p`
fails with `401` until it is unset. Every headless run above used
`env -u ANTHROPIC_API_KEY`. This affects the test harness only.

### Release candidate

All Prompt C §12 criteria are met except the two limitations recorded in
`README.md` (no substantive prosody guidance in the corpus; 48 chunks is a small
collection). Neither is a failed test — both are stated corpus limits.

Version `0.3.0`; tag `v0.3.0-rc.1` on commit `b3588e8`.

### Post-tag evidence: the feedback write path, executed once

Up to the tag, every exercise of `natural_flow_feedback` had ended in a refusal
(no `confirm`, writes disabled, or a malformed `chunk_id`), so its **successful**
path had never run and `badgr_natural_flow_feedback_v1` did not exist. That met
Prompt D §G4, which requires only the refusal, but it left one claim unmeasured
in a build whose whole argument is that claims are measured.

Executed with `NFR_ALLOW_WRITES=true` against a real chunk id:

```
{"recorded": true, "collection": "badgr_natural_flow_feedback_v1",
 "about_chunk_id": "3feebd9110468721_4", "verdict": "useful",
 "retrieval_corpus_modified": false}
retrieval corpus count before/after: 48 48
feedback collection count: 1
collections on disk: ['badgr_natural_flow_v1', 'badgr_natural_flow_feedback_v1']
```

The judgement landed in the separate collection and the retrieval corpus was
untouched, which is the property the two-collection design exists to guarantee.

### Repository topology note

`gh repo create --source=.` was run while on the feature branch, so
`feat/natural-flow-rag-activation` is the remote's **default branch** and `main`
does not exist remotely. Promoting to `main` is a repository decision for the
owner after acceptance, not a build step, so it was deliberately not done here.

---

## C.Walts v0.4 Gate 0 — controlled dataset acquisition and inventory

Executed on branch `feat/narration-generalization-v0.4`, cut from
`8a86ae3` (the tip of `feat/natural-flow-rag-activation`), **not** from the
`v0.3.0-rc.2` tag. Branching from the tag would have silently dropped one
commit. RC2 is not retagged or modified anywhere in this phase. The exact
ancestry is stated in the Gate 0.1 section below; the earlier phrasing "three
post-tag documentation corrections" in this log and in commit `a333d6f` was
wrong on both counts and is superseded there.

### Immutable baseline, re-measured before any change

| Fact | Value |
|---|---|
| `v0.3.0-rc.2` tag object | `8b0d2d7a85a9b9e905db761fbaa5ddb370244eae` |
| `v0.3.0-rc.2^{commit}` | `5ece81db9ab9334246f8e58781627a159d036a68` |
| Branch point (`8a86ae3`) | `8a86ae310f5f88099f88a24cbb4dcc75f1bcea79` |
| Chroma `badgr_natural_flow_v1` | 101 |
| Chroma `badgr_natural_flow_feedback_v1` | 2 |
| BM25 `var/bm25/index.json` | 101 chunk_ids / 101 token rows |
| Embedding model / dimension | `nomic-embed-text` (digest `0a109f422b47`) / 768 |
| BADGR Harness store MD5 | `bdcbe32b706c6ccce1f62e8e9f2d2c49` |
| Free disk on project filesystem | 70 GiB (gate requires 20 GiB) |

Gate results at baseline:

```
scripts/corpus_lint.py        PASS — 101 chunks, 0 findings
eval/run_evaluation.py        17/17 useful hits, exact-term PASS,
                              negative contamination 0, citation failures 0,
                              preservation 10/10
pytest tests/ -q              145 passed
scripts/smoke_test.py         42/43 passed
scripts/mcp_session_check.py  23/23 passed
sha256sum -c docs/evidence/source-snapshots/SHA256SUMS   7/7 OK
sha256sum -c SHA256SUMS (delivered Gate 0 package)       12/12 OK
```

### Failure 1 — the baseline smoke suite is 42/43, and why

`scripts/smoke_test.py` §11.2 asserts `ruff passes` across the whole working
tree, and the Gate 0 package had just been extracted into it. Ruff reported six
errors, all in the three delivered Python files:

```
F401  scripts/acquire_eval_sources.py   `dataclasses.dataclass` imported but unused
S310  scripts/acquire_eval_sources.py   urllib.request.Request  (audit URL open)
S310  scripts/acquire_eval_sources.py   urllib.request.urlopen  (audit URL open)
F401  scripts/inventory_eval_sources.py `hashlib` imported but unused
UP035 scripts/inventory_eval_sources.py `typing.Iterable` -> `collections.abc`
F401  tests/test_gate0_dataset_tools.py `io` imported but unused
```

This is **not** an rc.2 regression: it is the incoming package failing the
repository's existing static-quality gate. Root cause: the package was authored
outside this repository's Ruff configuration (`select = E,F,I,B,UP,S`).

Correction: the four unused/legacy imports were removed. The two `S310` findings
were resolved with targeted `# noqa: S310` comments carrying the justification
that `assert_https()` pins the scheme on the request URL **and again** on
`response.geturl()` after redirects. `S310` was deliberately **not** added to the
project-wide `ignore` list in `pyproject.toml` — that would have weakened an
existing gate to make this phase pass, which §8 forbids. Smoke returns to 43/43.

### Deviation from the delivered package, recorded

Three files were edited after receipt, so the root `SHA256SUMS` no longer matches
for them. `SHA256SUMS` is left byte-identical to the delivery as the record of
receipt integrity (it verified 12/12 on arrival). Post-edit hashes are recorded
in `docs/dataset-acquisition-report-gate0.md`.

### Hardening 1 — a missing embedded licence must be a refusal, not a traceback

`verify_license()` called `Path.read_text()` directly, so an archive that ships
no licence file raised `FileNotFoundError`. That is an `OSError`, not an
`AcquisitionError`, so §8's "a missing embedded license is rejected" could not be
asserted as a rejection path. A `path.is_file()` check now raises
`AcquisitionError("embedded license file is missing: ...")` first.

### Hardening 2 — the dry run now prints what §5 says to review

§5 requires reviewing "the exact URLs, destination paths, archive members, and
size caps" before `--execute`. The delivered `dry_run()` printed URLs, type,
licence, and members — but no destination paths and no cap, so the gate could not
actually be performed on its own output. It now prints the size cap, the
minimum-free-disk requirement against currently free space, the manifest
destination, the archive and extraction destinations per dataset, the licence
markers, the approval flag, and the resolved on-disk target of every allowlisted
member.


### Dry run reviewed before any network access

`scripts/acquire_eval_sources.py --dry-run` printed the three official
first-party URLs (UCI archive, the Amazon MASSIVE S3 bucket, the PolyAI GitHub
repository), their destinations under `var/eval_sources/`, the 2.00 GiB cap, the
20 GiB free-disk requirement against 69.33 GiB free, and every allowlisted member
with its resolved on-disk target. No Hugging Face mirror or third-party copy
appears anywhere in the configuration. Reviewed and approved before `--execute`.

### Failure 3 — CLINC150 is CC BY 3.0, not CC BY 4.0

The first `--execute` refused CLINC150:

```
ERROR: license marker verification failed for
var/eval_sources/extracted/clinc150/clinc150_uci/LICENSE:
['Attribution 4.0 International']
```

The gate worked. The archive was downloaded, extracted, and then rejected before
anything else happened. Reading the licence that UCI actually ships:

```
Creative Commons Legal Code

Attribution 3.0 Unported
```

The approved-source configuration declared `CC-BY-4.0` for all three datasets.
For CLINC150 that declaration was wrong. Root cause: the licence was taken from
the dataset's reputation rather than from the file inside the archive — the same
class of error rc.2 corrected by reading the JATS `<license>` element instead of
a publisher page.

Correction: `config/approved_eval_datasets.json` now declares `CC-BY-3.0` for
CLINC150 and requires two markers, `Creative Commons Legal Code` **and**
`Attribution 3.0 Unported`. The check was made stricter, not looser; the declared
licence was moved to match the verified evidence. `clinc150_uci/meta.txt` was
added to the extract allowlist because it carries the citation that CC BY
attribution requires (Larson et al., EMNLP-IJCNLP 2019).

**Owner decision recorded, not assumed.** CC BY 3.0 permits commercial use and
adaptation with attribution, so it supports the intended use — evaluation-query
candidates, never redistributed, never ingested. It is nonetheless a different
licence from the one the phase plan assumed, and the attribution obligation
attaches to CLINC150-derived queries. Flagged for the reviewer.

MASSIVE 1.0 and Banking77 both verified `Attribution 4.0 International` in-band
on the first attempt.

### Failure 4 — Banking77 ships a header row

`parse_banking()` counted `text,category` as a record and then raised
`InventoryError: Banking77 categories absent from categories.json: ['category']`.
Root cause: the delivered inventory tool assumed headerless CSVs.

Correction: the header is now **asserted** to equal `["text", "category"]` and
skipped. It is asserted rather than skipped blindly because a silently absent
header would cost one real record from each split, and the record counts are the
whole point of this phase.

### Correction 5 — the candidate annotation flagged two unrelated labels

The near-domain candidate rule first matched substrings, which flagged CLINC150's
`spending_history` (through "story") and `sync_device` (through a "syn" stem).
Neither has anything to do with narration. The rule now matches on
underscore-separated token prefixes, and the stem is `synonym`. CLINC150
near-domain candidates fell from 11 to 9. The rule is printed in full in the
report so a reviewer can reject it outright; it annotates, it does not select.

### Acquisition executed

Three archives, all HTTPS, all first-party. 41,749,543 bytes of archives and
7,539,821 bytes of extracted allowlisted files, 48 MB on disk under
`var/eval_sources/`, Git-ignored. Byte counts are the manifest's own
`download.bytes` values, not a rounded `du`:

| Dataset | Archive bytes | Archive SHA-256 |
|---|---:|---|
| clinc150 | 1,053,960 | `0d8ecc3e1edd7b25cabde0177544ce536ddf773844bc80ef1a75f36e7f030ea2` |
| massive_1_0_en_us | 39,500,415 | `7df623fd2d300a4d235d6ee5bd396c9a28258d3a0ccb29abdb054506eba153f8` |
| banking77 | 1,195,168 | `b8c2ba23bc1ab7b182230c378f07417c8aef735260a2fd3546faef54ecbbfa91` |

Per-file hashes, exact byte counts, and the licence markers verified inside each
archive are in `docs/dataset-acquisition-report-gate0.md`. Only the allowlisted
members were written; the CLINC150 archive also contains `data_small.json`,
`data_imbalanced.json`, `data_oos_plus.json`, and a `__MACOSX/` tree, none of
which were extracted.

### Inventory

| Dataset | Records | Structure | Duplicates | Words min/median/max |
|---|---:|---|---:|---|
| CLINC150 | 23,700 | 151 labels; 1,200 out-of-scope | 5 | 1 / 8 / 28 |
| MASSIVE 1.0 en-US | 16,521 | 18 scenarios, 60 intents | 89 | 1 / 6 / 61 |
| Banking77 | 13,083 | 77 categories | 11 | 2 / 10 / 79 |

Duplicates are reported, not removed: de-duplication is a selection decision and
selection has not happened.

### Production boundary, measured before and after

| Item | Before | After |
|---|---|---|
| Chroma `badgr_natural_flow_v1` | 101 | 101 |
| Chroma `badgr_natural_flow_feedback_v1` | 2 | 2 |
| BM25 chunk_ids / tokens | 101 / 101 | 101 / 101 |
| BADGR Harness store MD5 | `bdcbe32b706c6ccce1f62e8e9f2d2c49` | `bdcbe32b706c6ccce1f62e8e9f2d2c49` |
| Free disk | 70 GiB | 70 GiB |

No ingestion or reindex tool was called. Nothing was chunked or embedded.

### Full validation at handoff

```
pytest tests/                 172 passed  (145 at baseline + 27 adversarial)
ruff check .                  All checks passed
scripts/corpus_lint.py        PASS — no findings
eval/run_evaluation.py        17/17 useful hits, exact-term PASS,
                              contamination 0, citations 0, preservation 10/10
scripts/smoke_test.py         43/43 passed   (42/43 at baseline; see Failure 1)
scripts/mcp_session_check.py  23/23 passed
acquire_eval_sources.py --verify    all files and embedded licences verified
inventory_eval_sources.py --verify  inventory reproduces byte-for-byte
```

### Post-edit hashes of the three modified package files

The root `SHA256SUMS` records the package **as delivered** and still verifies
12/12 against that delivery for the nine unmodified files. These three were
edited during the phase, for the reasons above:

```
e77080245cd45ff21088809a69bd137cd38cd18d741d3f40ff055e05a0376dbb  scripts/acquire_eval_sources.py
5e33ce7b623a62dbc8821cab602227918a5d233ed1d71d34b8b5684798bcebc4  scripts/inventory_eval_sources.py
21453dbefb5c6bd60b3930795ce3c525bd92e65ef4de79e8b455b3c54f6d4ab3  tests/test_gate0_dataset_tools.py
```

### Stop condition

Gate 0 ends here. No query was selected, no 600-query set built, no calibration
or holdout file created, no threshold fitted, no MCP evidence status changed, no
audiobook corpus acquired, `main` not promoted, and no release candidate tagged.

### Correction 6 — the report now carries §11's return values

Review of the handoff artefact found that `docs/dataset-acquisition-report-gate0.md`
asserted the production boundary without showing it, and omitted disk use, while
`docs/owner_actions.md` sends exactly that file to the reviewer. Both are now
generated into the report rather than hand-typed: disk figures are summed from
the acquisition manifest, and the before/after store measurements come from
`docs/evidence/gate0-boundary.json`, which records the commands used. The
execution log's archive byte counts were also corrected — one was transcribed
from a rounded `du` reading rather than the manifest.

---

## C.Walts v0.4 Gate 0.1 — provenance and checksum closeout

Bounded integrity pass over the Gate 0 result. No dataset was downloaded, no
query selected, no threshold fitted, and ChromaDB, BM25, MCP behaviour, and
`main` were not touched. Version stays `0.4.0-dev.1`.

### 1. Baseline ancestry, stated exactly

The earlier description was wrong twice over: it said "three post-tag
documentation corrections", which implied three commits, and it implied the
work was documentation-only. Measured:

```
git rev-parse v0.3.0-rc.2            8b0d2d7a…  (tag object)
git rev-parse v0.3.0-rc.2^{commit}   5ece81db9ab9334246f8e58781627a159d036a68
git rev-list --count 5ece81db..8a86ae3   1
```

The record is:

- `v0.3.0-rc.2` points to commit `5ece81db`;
- the v0.4 branch was cut from `8a86ae3`;
- `8a86ae3` is **one** post-tag commit ahead of RC2 — not three;
- that single commit corrected **three inaccuracies** in the rc.2 record: the
  set-2 examples header that said "twenty-five pairs" when the file held
  twenty-seven, the A7 note in `config/sources.yaml` that still called CMUdict
  the only externally licensed material, and the owner report's failure to
  connect the §6 `demote_doc_types` change to the §7 marker updates as one
  event;
- it was **not documentation-only**. The header edit changed one corpus chunk,
  so the collection was reindexed and the evidence regenerated;
- all gates were re-run after that regeneration and passed: corpus lint 0
  failures and 0 warnings, evaluation 17/17 with exact-term PASS, contamination
  0, citation failures 0, preservation 10/10, 136 unit tests, smoke 43/43,
  fresh-session MCP 23/23, ruff clean, 101 chunks;
- the `v0.3.0-rc.2` tag itself was never moved. A pushed tag that moves is worse
  than a follow-up commit that explains itself.

### 2. CLINC150 licence reconciliation

Two authoritative sources disagree, and both are now recorded. Neither is
erased, and the more permissive one is not assumed.

| Field | Value |
|---|---|
| Archive URL | `https://archive.ics.uci.edu/static/public/570/clinc150.zip` |
| Archive SHA-256 | `0d8ecc3e1edd7b25cabde0177544ce536ddf773844bc80ef1a75f36e7f030ea2` |
| Embedded licence | `clinc150_uci/LICENSE`, SHA-256 `e6bc9e9c474700b708f568bac9e5a8a9bcb2b1dad53442f5ba449fcb848b8e76` |
| Embedded licence text | Creative Commons Legal Code — **Attribution 3.0 Unported** |
| Landing page | `https://archive.ics.uci.edu/dataset/570/clinc150`, DOI 10.24432/C5MP58 |
| Landing-page statement | "Creative Commons Attribution 4.0 International (CC BY 4.0) license" |
| Access date | 2026-08-01 |
| **Operative minimum for this archive** | **CC BY 3.0 Unported** |
| Attribution | required — Larson et al., EMNLP-IJCNLP 2019, plus the UCI DOI citation |
| Commercial use | permitted under both versions |
| Transformation | permitted under both; 3.0 requires modifications be identified |
| Redistribution | permitted under both, **not exercised** — local-only, Git-ignored |

CC BY 3.0 is designated the conservative operative minimum **for this exact
archive**. That is a statement about what this project will comply with, not a
finding that UCI's landing page is wrong. Which statement UCI intends to govern
has not been established, and a future re-acquisition may ship a 4.0 LICENSE and
must be re-checked.

Recorded in three places, all tracked: the machine-readable
`license_reconciliation` block in `config/approved_eval_datasets.json`, the
human-readable third-party section in `NOTICE`, and a rendered table in
`docs/dataset-acquisition-report-gate0.md`. The block flows through the
acquisition manifest into the inventory, so the report cannot drift from the
configuration.

`NOTICE` previously had no section for the public evaluation sources at all.
MASSIVE 1.0 and Banking77 are now credited there as well, both CC BY 4.0
verified in-band, alongside the statement that all three are evaluation-query
candidates that are never ingested — which preserves the A7 distinction between
third-party text that is INGESTED and third-party work that is CITED.

### 3. Checksum repair

`SHA256SUMS` was ambiguous: it recorded the delivery but was read as if it
described the current tree, and it fails `sha256sum -c` because files were
legitimately edited during Gate 0. Split in two:

| File | Question it answers | Regenerated? |
|---|---|---|
| `SHA256SUMS.package` | what was delivered | never |
| `SHA256SUMS.current` | what is tracked now | on every legitimate change |

`SHA256SUMS.package` is the delivered file renamed with `git mv`, byte-identical.
Its immutability is proved by pinning the SHA-256 of the file itself
(`0e7e87d2721cafdfe9bdc41fc057dad601374a0ac21be99dd09de03b480cf091`) rather than
by asserting its twelve entries still match — because four of them deliberately
do not.

`scripts/verify_gate0_integrity.py --verify` is the gate. It proves three things
and cannot knowingly fail:

1. the delivery record is unaltered, and exactly the four files with recorded
   reasons differ from it — a fifth drifting file fails the gate, and so does a
   listed file that quietly stops differing;
2. all 17 entries of `SHA256SUMS.current` match, covering every tracked Gate 0
   source, test, configuration, schema, prompt, and report;
3. raw datasets are excluded — seven paths under `var/eval_sources/` and the two
   pool directories are Git-ignored, and `git ls-files` returns nothing for them.

`SHA256SUMS.current` also verifies with plain `sha256sum -c`, which skips its
`#` comment header.

**Failure 7, caught by the new gate on its first run.** The first `--verify`
failed:

```
FAIL
  - delivered files changed without a recorded reason: ['config/approved_eval_datasets.json']
```

The known-modified set had been written from the execution log's
"three modified files" note, which had not been updated when the CLINC150
licence correction edited the configuration during Gate 0. The gate caught the
stale record on its first execution, which is the behaviour that justifies it.
The configuration is now listed with its reasons.

`CHANGELOG.md` and `docs/execution-log.md` are deliberately outside
`SHA256SUMS.current`: they are living cross-gate documents, and pinning them
would guarantee a stale checksum the moment Gate 1 opens. The exclusion is
stated in the file's own header.

**Expected behaviour for whoever opens Gate 1.** `SHA256SUMS.current` is a
tripwire by design. Editing any of the 17 covered files makes
`test_gate0_integrity_verification_passes` fail — and therefore the whole
suite — until the record is regenerated with:

```bash
.venv/bin/python scripts/verify_gate0_integrity.py --write
```

That failure is the intended signal that a Gate 0 artefact moved, not a
regression. This happened once during Gate 0.1 itself, when the integrity tests
were appended to the test module.

### 4. Duplicate counts, confirmed and unchanged

Exact case-folded, whitespace-stripped repeats, counted across all splits, n-1
per group of n identical records:

| Dataset | Duplicates |
|---|---:|
| CLINC150 | 5 |
| MASSIVE 1.0 en-US | 89 |
| Banking77 | 11 |

**None was removed.** De-duplication is a selection decision and no selection has
been made. A test now pins these three figures, so a silent change to the parser
or the sources cannot pass unnoticed.

### 5. Candidate labels demoted to unapproved proposals

The inventory keys `near_domain_candidates` and `far_domain_candidates` read as
classifications. They were not classifications; they were string-rule output.
Renamed to `mechanically_proposed_unapproved` and `not_proposed_by_the_rule`,
with `approval_status: "unapproved"` and `approved_by: null` alongside.

The report now names the five proposals a reviewer should expect to argue with,
with the reason the rule matched and the reason that may be wrong. `text` in
CLINC150 means *send a text message*, not written text, which is the clearest
demonstration that the rule is a filter and not a classifier. `change_volume` is
device loudness, not vocal delivery. `meaning_of_life` is small talk.
`tell_joke` is delivery-adjacent at best. `general_quirky` is a catch-all bucket
whose contents must be inspected per record.

Not being proposed is likewise not a judgement: the rule can miss. Both lists
stay in the JSON inventory.

Banking77 remains the one stated domain conclusion in the report, and it rests
on reading the 77 category names, not on the token rule.

---

## C.Walts v0.4 Gate 1 — evaluation isolation and production-retrieval decontamination

Objective: remove every evaluation prompt, pass criterion, and expected-answer
marker from production ChromaDB and BM25, and keep that material as a
non-ingested regression fixture. Version `0.4.0-dev.1` → `0.4.0-dev.2`.

### Baseline, re-measured before any change

Working tree clean. `HEAD` = `origin/feat/narration-generalization-v0.4` =
`adc05be`. `v0.3.0-rc.2` still `8b0d2d7a` (tag) / `5ece81db` (commit) — not moved.

| Fact | Value |
|---|---|
| Chroma `badgr_natural_flow_v1` | 101 |
| Chroma `badgr_natural_flow_feedback_v1` | 2 |
| BM25 chunk_ids / token rows | 101 / 101 |
| BADGR Harness store MD5 | `bdcbe32b706c6ccce1f62e8e9f2d2c49` |
| Free disk | 70 GiB |
| `doc_type=evaluation_case` chunks | **17** |
| Their `source_id` | `cwalts_evaluation_cases` (one only) |
| Their `source_path` | `corpus/raw/evaluation/cases/evaluation_prompts.md` (one only) |
| Expected count after removal | **84** |

All ten baseline gates passed: 177 tests, ruff clean, `git diff --check` clean,
corpus lint PASS, evaluation 17/17 with exact-term PASS and contamination 0 and
citation failures 0 and preservation 10/10, smoke 43/43, MCP 23/23, acquisition
verify, inventory verify, Gate 0 integrity verify.

The 17 chunk IDs scheduled for removal are recorded in full, with their
headings and source checksum, in `docs/evidence/gate1-removal-plan.json`,
captured **before** any mutation so the removal set cannot be rationalised
afterwards.

### Scope note: `corpus/raw/evaluation/negative/` stays

One production source has "evaluation" in its path and is **not** evaluation
material: `cwalts_negative_patterns` at `corpus/raw/evaluation/negative/`,
`doc_type=negative_pattern`, one chunk. It is a corpus description of delivery to
avoid, required by Prompt D §D, and it is governed by the contamination rule
rather than by this gate. It is not moved and not deleted.

### Verified backup before any mutation

`scripts/store_snapshot.py` was added because the existing backup path snapshots
`chroma.sqlite3` alone. That is the right gate before a delete but not a complete
restore point: Chroma keeps each collection's HNSW index in sibling directories,
the lexical arm lives in `var/bm25/index.json`, and `config/sources.yaml` decides
what the corpus is. Restoring the database alone would bring back rows whose
vector and lexical indexes disagree with them.

| Field | Value |
|---|---|
| Snapshot | `var/snapshots/20260802T010230Z` (Git-ignored) |
| Taken (UTC) | 2026-08-02T01:02:30Z |
| Chroma tree SHA-256 | `99f03b03b10d443426846796eed9ce6813957ff5fa54dd5feaa27a8006420334` |
| `chroma.sqlite3` SHA-256 | `405f527b09f4c5fd1e0442f254e6c297ff0bff61c838b3b1acca04f603caabb1` |
| BM25 SHA-256 | `3cdf35b807aa17071cf8007165dc8882a8e74dc9c5dcd49daa30db7cc0a02b0f` |
| `sources.yaml` SHA-256 | `afecf9a7297fdec80c2fc1b006d27c766101aba40ba95fb6769b75f99d690579` |
| Collections in the copy | `badgr_natural_flow_v1` 101, `badgr_natural_flow_feedback_v1` 2 |
| BM25 chunk ids in the copy | 101 |

Verified by interrogation, not by hash: the copy was reopened, its collections
listed and counted **out of the snapshot's own SQLite file**, BM25/Chroma parity
confirmed at 101 = 101, and an exact-term query for `ToBI` run against the
restored lexical index returned 3 hits. A damaged database can still hash.

### Isolation

`corpus/raw/evaluation/cases/evaluation_prompts.md` →
`eval/regression/source_documents/evaluation_prompts.md`, moved with `git mv`
(recorded as `R100` — byte-identical, history follows it). No ingestible copy was
left behind; the source directory is gone. The original text, all fifteen EVAL
ids, every `**Pass**` block, the historical notes and the prior failure
disclosures are preserved verbatim and asserted by test.

`cwalts_evaluation_cases` was removed from `config/sources.yaml`. In its place is
a WITHDRAWN FROM PRODUCTION record explaining what the source was, why it was
withdrawn, where it went, and what now prevents its return. It is a record, not a
source entry, and nothing in it is ingestible.

### Hard boundary — three independent locks

1. **Ingestion.** `settings.resolve_ingest_path()` refuses any source path under
   `eval/` or `var/eval_sources/` before a file is discovered, and
   `assert_ingestible_doc_type()` refuses `doc_type: evaluation_case` outright.
   Both raise rather than skip, so a manifest that declares evaluation material
   is a visible configuration error rather than a line of output nobody reads.
2. **Store.** Zero `evaluation_case` records in Chroma and zero in BM25.
3. **Retrieval.** `forbid_doc_types_always: [evaluation_case]` is applied to the
   dense filter, again to the fused list because BM25 sees no metadata, and a
   third time after neighbour expansion, which pulls chunks in by adjacency
   rather than by score.

### Defect found while building lock 3: a caller filter disabled the exclusions

`_default_filter()` returned the caller's `where` clause untouched whenever one
was supplied. Passing **any** filter therefore silently disabled the
negative-pattern exclusion — and would have disabled the evaluation exclusion the
same way, which is precisely the bypass §4 forbids. Measured during the pre-delete
dry probe: `search(EVAL-009 query, where={"doc_type": {"$ne": "evaluation_case"}})`
returned the negative-pattern chunk at rank 5, which the same query without a
filter excludes.

Fixed by composing rather than replacing: the caller's clause, the hard ban, and
the negative-pattern default are intersected with `$and`. A filter narrows a
search; it cannot widen one.

`tests/test_negative_policy.py::test_an_explicit_caller_filter_is_never_overridden`
asserted the old behaviour (`assert where is supplied`). It was renamed to
`test_a_caller_filter_narrows_and_is_never_allowed_to_widen` and now asserts the
opposite. This is the one existing test Gate 1 changed, and it is recorded here
rather than quietly edited: the requirement itself changed, by mandate, and the
old assertion encoded the defect.

### The obsolete demotion rule

`demote_doc_types` held `[evaluation_case]`. It is now `[]`. Leaving it would
imply evaluation cases are still expected in production retrieval, which is false.
The mechanism is kept — generic, cheap, and a future doc_type may need ranking
demotion without exclusion — with the rc.2 rationale preserved in the config as
history.

### Controlled removal

Dry run first, through the sanctioned `natural_flow_reindex` path with
`confirm=true`, `dry_run=true`, `delete_stale=true`:

```
chunks_in_corpus        84
chunks_in_collection   101
would_add_count          0
stale_count             17
stale_listing_complete true
```

`would_add_count = 0` matters as much as the stale count: chunk ids are
content-derived, so a non-empty add list would have meant chunking had drifted
and the survivors were not the same records. No broad `source=` filter was used —
the full reindex computes `stale = existing - wanted`, which is an exact id set.
The tool refuses `delete_stale` together with `source=` for exactly this reason.

Before committing, the 17 stale ids were compared set-for-set against
`docs/evidence/gate1-removal-plan.json`, captured before any change: identical,
no extras, none missing. Every id was then re-read from the collection and
confirmed to carry `doc_type=evaluation_case`; no approved example, glossary,
style-rule or negative-pattern chunk was in the removal set.

Commit run, with writes enabled by environment variable for that single
invocation only — `config/rag.yaml` still carries `allow_writes: false`, so
writes were off again the moment the process exited:

```
written          84
deleted_count    17
collection_count 84
lexical_count    84
backup           var/backups/20260802T010613Z/chroma.sqlite3
                 sha256 85eb5716…2119, verified, reopened, 103 embedding rows
```

The tool took its own verified backup before the delete, independently of the
snapshot taken earlier. Full result: `docs/evidence/gate1-removal-result.json`.

### State after removal

| Item | Before | After |
|---|---:|---:|
| Chroma `badgr_natural_flow_v1` | 101 | **84** |
| `doc_type=evaluation_case` chunks | 17 | **0** |
| BM25 chunk ids / token rows | 101 / 101 | **84 / 84** |
| Chroma/BM25 id-set parity | exact | **exact** |
| Chroma `badgr_natural_flow_feedback_v1` | 2 | 2 |
| BADGR Harness store MD5 | `bdcbe32b…2c49` | `bdcbe32b…2c49` |

Corpus lint after removal: PASS, 84 chunks — approved_example 59 (70.2%),
glossary 19 (22.6%), style_rule 5 (6.0%), negative_pattern 1 (1.2%). Both
auxiliary classes remain under the 40% cap; removing the 17 evaluation chunks
raised the primary share rather than lowering it.

### Expectation cleanup

Five cases could pass by retrieving their own question. Markers removed:

| Case | Removed | Why it was contamination |
|---|---|---|
| EVAL-005 | `EVAL-005`, `Number preservation`, `Preservation` | all three matched only the EVAL-005/006/007 prompt headings |
| EVAL-006 | `EVAL-006`, `Obligation` | matched only `EVAL-006 — Obligation preservation` |
| EVAL-007 | `EVAL-007`, `Certainty preservation`, `Preservation` | matched only the evaluation prompts |
| EVAL-009 | `EVAL-009`, `Technical density` | matched only `EVAL-009 — Technical density` |
| EVAL-010 | `EVAL-001` | matched a *different* case's prompt |

One further change, and it is a TIGHTENING rather than a relaxation. EVAL-009
also listed `Pair CW-0`, a prefix that matches every approved pair CW-001 through
CW-039. Harmless while other markers carried the case; with the evaluation
markers gone it would have become an almost unfalsifiable marker holding the case
up on its own. It is replaced by `Pair CW-021` and `dense architecture` — the
pair that actually rewrites a dense architecture paragraph, and which ranks
first for this query.

No requirement was weakened to preserve 17/17. The stricter direction was taken
in the one place there was a choice.

### The global assertion now scores

`primary_doc_type_pass`, `primary_source_pass` and `definition_pass` were
computed per case and then never folded into the summary — a regression in any of
them would have printed 17/17 and looked clean. `expectations.yaml` gains
`global_forbid_primary_doc_types` and `global_forbid_doc_types_anywhere`, applied
to every retrieval case whether or not the case declares them and unioned with
any per-case list, so a case can add to the ban but never subtract from it. The
runner counts every declared assertion and prints `declared assertions failed`
and `evaluation-case chunks returned` in the summary.

### Evaluation after decontamination

```
useful hit @5                    17/17  (100%)
exact-term retrieval             PASS
positive-source ratio            74%
negative contamination           0
evaluation-case chunks returned  0
declared assertions failed       0
citation failures                0
preservation correct             10/10
```

Every case that previously matched its own prompt now matches production
material: EVAL-005 on `Pair CW-038`, EVAL-006 on `Pair CW-020`, EVAL-007 on
`Pair CW-036`, EVAL-009 on `Pair CW-021`, EVAL-010 on `Pair CW-001`. **No case
regressed**, so §5's honest-failure path was not needed — but the outcome was
predicted before the delete, by running every case against a filtered view of the
un-decontaminated collection, so 17/17 was not discovered after the fact.

Positive-source ratio moved 74% → 74% and latency p50 79 ms → 78 ms. The distance
distribution shifted slightly (min 0.114 → 0.144) because the removed chunks were
short and probe-shaped and had been supplying some of the closest matches.

### Rollback rehearsal

Rehearsed with the real snapshots, not simulated. The decontaminated state was
snapshotted first (`var/snapshots/20260802T011137Z`, verified) so the rehearsal
could not become a one-way trip.

**Rolled back** to the pre-Gate-1 snapshot `var/snapshots/20260802T010230Z`:

| Proof | Result |
|---|---|
| Chroma count restored | 101 |
| doc_types restored | approved_example 59, glossary 19, **evaluation_case 17**, style_rule 5, negative_pattern 1 |
| Collection available | yes, opens through the project's own client |
| BM25 count restored | 101, id-set parity with Chroma exact |
| Lexical retrieval | working |
| Exact-term retrieval | `ToBI` 3 hits, `L-L%` 3 hits, `break index` 3 hits |

The 17 evaluation chunks came back, which is the point: the rollback path is
real, and a bad Gate 1 would have been recoverable.

**Restored forward** to the Gate 1 state and re-verified: Chroma 84,
evaluation_case 0, BM25 84 with exact parity, `ToBI` still 3 lexical hits.

The final state is the decontaminated Gate 1 state, not the rollback state.

### Full validation at handoff

```
pytest tests/                    219 passed   (177 at Gate 1 baseline)
ruff check .                     All checks passed
git diff --check                 clean
scripts/corpus_lint.py           PASS — 84 chunks, no findings
eval/run_evaluation.py           17/17 useful, exact-term PASS,
                                 contamination 0, evaluation chunks returned 0,
                                 declared assertions failed 0, citations 0,
                                 preservation 10/10
scripts/smoke_test.py            43/43
scripts/mcp_session_check.py     23/23
acquire_eval_sources.py --verify all files and embedded licences verified
inventory_eval_sources.py --verify  inventory reproduces byte-for-byte
verify_gate0_integrity.py --verify  delivery record immutable, tree matches
```

Also confirmed: zero `evaluation_case` chunks in Chroma, zero in BM25, exact
Chroma/BM25 id-set parity, feedback collection unchanged at 2, BADGR Harness
store MD5 `bdcbe32b706c6ccce1f62e8e9f2d2c49` unchanged, no secrets, no raw public
dataset staged, nothing tracked under `var/`.

The `SHA256SUMS.current` tripwire did **not** fire this phase: Gate 1 touched no
file it covers. `SHA256SUMS.package` was not altered.

### Unresolved and disclosed

1. **`Pair CW-021` now carries EVAL-009 largely alone.** The other two markers
   are `dense architecture` (same chunk) and `Market Voice-Delivery Rules`, which
   does not currently rank for this query. The case is honest but thin, and it is
   thin because the corpus has exactly one worked example of rewriting a dense
   architecture paragraph. That is a corpus-coverage observation for a later
   phase, not a Gate 1 defect, and Gate 1 is explicitly forbidden from adding
   corpus material to fix it.
2. **`corpus/raw/evaluation/negative/` keeps "evaluation" in a production path.**
   It is negative-pattern corpus text, not evaluation material. A reviewer
   scanning paths will flag it; the distinction is recorded in `sources.yaml`
   and asserted in `test_production_source_paths_are_still_reachable`.
3. **The rc.2 owner report and `docs/rollback.md` still describe a 101-chunk
   collection.** They are historical records of rc.2 and were deliberately not
   rewritten; the current count lives in this log, the CHANGELOG and the
   evaluation report.

   > **Correction, 2026-08-02 (Gate 1.1 §3).** The second half of that sentence
   > was wrong. `docs/rollback.md` never contained the number 101 — it described
   > the rc.2 rehearsal at **48 and 97** chunks. Only
   > `docs/owner-test-report-rc2.md` describes 101 (lines 30 and 295), and it is
   > correctly historical. The claim is left standing above rather than edited
   > away, because a record that quietly repairs itself is not a record; this
   > note is the repair. The substance of the item — stale counts sitting in
   > documents a reader might take as current — was real, and Gate 1.1 §3
   > resolves it by splitting `docs/rollback.md` into a frozen historical record
   > and an active procedure that derives counts instead of stating them.

---

## 2026-08-02 — C.Walts v0.4 Gate 1.1 §1: baseline verification

Version held at `0.4.0-dev.2`. No query selection, no threshold fitting, no
corpus addition, no change to `main`, no tag.

Baseline HEAD `bac37064d24570a1ba13715f00722055556396e3`, equal to
`origin/feat/narration-generalization-v0.4`. Working tree clean before any
verification command ran. `v0.3.0-rc.2` still `8b0d2d7a85a9b9e905db761fbaa5ddb370244eae`.

```text
pytest tests/                    219 collected, exit 0, 0 failed
ruff check .                     All checks passed!
corpus_lint.py                   PASS — 84 chunks, no findings
eval/run_evaluation.py           17/17 useful, exact-term PASS, contamination 0,
                                 evaluation-case chunks returned 0,
                                 declared assertions failed 0, citations 0,
                                 preservation 10/10
smoke_test.py                    43/43
mcp_session_check.py             23/23
acquire_eval_sources.py --verify all files and embedded licences verified
inventory_eval_sources.py --verify  inventory reproduces byte-for-byte
store_snapshot.py --verify       post-Gate-1 snapshot verified: 84/2, parity,
                                 ToBI exact-term hits 3
verify_gate0_integrity.py --verify  PASS (re-run last, on the final tree)
sha256sum -c SHA256SUMS.current  all OK, 0 failures (re-run last)
```

Store re-measured live rather than read from the Gate 1 record: Chroma
`badgr_natural_flow_v1` 84, feedback 2, BM25 84 chunk_ids / 84 token rows, exact
id-set parity (empty both-way differences), composition approved_example 59 /
glossary 19 / style_rule 5 / negative_pattern 1. `evaluation_case` is zero by two
independent surfaces — a full metadata scan and a Chroma `where` filter. BADGR
Harness store MD5 `bdcbe32b706c6ccce1f62e8e9f2d2c49` unchanged.
`SHA256SUMS.package` self-digest still `0e7e87d2…0cf091`; not altered.

Test totals by gate: Gate 0 / 0.1 `test_gate0_dataset_tools.py` 41, Gate 1
`test_evaluation_boundary.py` 41, pre-existing rc.2 suites 137. This
environment swallows pytest's summary line, so 219 is the sum of
`--collect-only` per-file counts and "0 failed" rests on exit code 0.

### Correction made during this checkpoint

The first draft of `docs/evidence/gate1_1-baseline.json` asserted a clean
working tree as a literal. That was wrong by the time it was written:
`eval/run_evaluation.py` and `scripts/smoke_test.py` rewrite their own tracked
evidence JSONs on every run, so the verification sweep dirtied the tree it was
describing. The record now computes the git facts instead of asserting them and
carries the post-run `git status` verbatim. A mechanical diff of the changed JSON
keys yields exactly `generated`, `latency_ms`, `latency_ms_p50`,
`latency_ms_p95` — wall-clock and timing only; no count, pass flag, retrieval
result or assertion outcome moved.

`verify_gate0_integrity.py --verify` and `sha256sum -c SHA256SUMS.current` were
consequently re-run *after* every writing command, so the PASS recorded describes
the final tree rather than a pre-churn one. The tripwire did not fire: the
regenerated evidence JSONs are not among the files it covers.

Free disk 69 GiB, down from 70 at the Gate 1 close. Not a store metric and well
above the 20 GiB floor.

### Still unresolved (carried forward unchanged from Gate 1)

The three items disclosed at the Gate 1 close — thin EVAL-009 coverage,
`corpus/raw/evaluation/negative/` retaining "evaluation" in a production path,
and stale counts in documents a reader might mistake for current state — are
unchanged and remain open. (Item 3 as originally worded named
`docs/rollback.md` as describing 101 chunks; it never did. See the correction
noted against that item above. Item 2 was closed by §2 and item 3 by §3.)

Evidence: `docs/evidence/gate1_1-baseline.json`.

---

## 2026-08-02 — C.Walts v0.4 Gate 1.1 §2: rename the production negative-pattern path

Version held at `0.4.0-dev.2`. No query selection, no threshold fitting, no new
corpus material, no change to `main`, no tag.

`corpus/raw/evaluation/negative/` → `corpus/raw/negative_patterns/` via `git mv`,
detected by git as a rename (`R`), file sha256 `959d9b63…884ed` identical before
and after. This closes item 2 of the three unresolved items disclosed at the
Gate 1 close: it was the last production-ingestible directory named
"evaluation".

### The seven-step branch did not trigger, and that was measured

§2 makes the id-migration procedure conditional on source-path-derived chunk ids
changing. They do not: `schemas.chunk_id` is
`sha256(f"{source_id}:{content_hash}")[:16]_{index}` — the file path is not an
input, only `source_path` metadata is. Rather than skip the branch on a code
reading, the claim was tested. With the `git mv` and the `sources.yaml` path edit
both done — so discovery saw a consistent world — a dry-run ingest was diffed
against the live collection:

```text
wanted    84
existing  84
STALE     (existing - wanted): []
WOULD ADD (wanted - existing): []
identical id sets: True
```

`stale 0` is the number that decided it. A verified snapshot was taken first
regardless (`var/snapshots/20260802T041356Z`, re-opened and interrogated: 84/2,
BM25 84, parity, ToBI 3 hits), because the write to production was real even
though the id set was not moving.

The reindex ran with `NFR_ALLOW_WRITES=true` for that one invocation;
`config/rag.yaml` still reads `allow_writes: false`.

### What the write actually changed

Exactly one metadata field, diffed field-by-field against a pre-move capture:

| Field | Before | After |
|---|---|---|
| `source_path` | `corpus/raw/evaluation/negative/rejected_audio_contrast.md` | `corpus/raw/negative_patterns/rejected_audio_contrast.md` |

Unchanged: `id` `9c1e63263b4b8373_0`, `source_id` `cwalts_negative_patterns`,
`doc_type` `negative_pattern`, licence, `source_checksum` `d32911ca…3aae3`,
register `contrast`, dialect `en-US`, `chunk_index` 0, `chunk_total` 1,
`token_count` 379, `section_heading`, `chunk_profile` `reference`.

Chroma 84 → 84, BM25 84 → 84, id-set parity exact (both differences empty),
composition unchanged (approved_example 59 / glossary 19 / style_rule 5 /
negative_pattern 1), feedback 2, BADGR Harness MD5
`bdcbe32b706c6ccce1f62e8e9f2d2c49`. No production `source_path` contains
"evaluation". The evaluation report's cosine min/median/max came back
byte-identical (0.1439 / 0.336552 / 0.463614), which is the strongest available
evidence that the re-embed was inert.

### The five proofs

Written as `tests/test_negative_pattern_path.py` (24 tests), not asserted in
prose:

| §2 requirement | How it is proved |
|---|---|
| old path no longer exists | filesystem check plus a git-detected rename |
| new path production-ingestible | `resolve_ingest_path` resolves it; the source manifest declares it; ingest discovered 1 chunk there |
| excluded from ordinary positive retrieval | live retrieval, three rewrite queries, zero `negative_pattern` returned; evaluation report contamination 0 |
| available for explicit contrast requests | live retrieval, two "what to avoid" queries, the chunk returned **from the new path** |
| evaluation directories still non-ingestible | the `eval/` and `var/eval_sources/` refusals re-asserted here as well as in the Gate 1 file |

The contrast proof matters most: had the rename broken discovery, the chunk would
simply have stopped appearing and every exclusion test would still have passed.

### Failures and corrections during this checkpoint

1. **`.gitignore` would have swallowed the moved file.** `corpus/raw/*` is
   ignored and the tree was re-included by name; `corpus/raw/negative_patterns/`
   had no such entry. Caught before ingest by `git check-ignore`. Added the
   re-include, kept `!corpus/raw/evaluation/` for the surviving audio manifest,
   and asserted both in tests.
2. **The first "no stale references" test was too blunt.** A plain grep flagged
   `config/sources.yaml` and `tests/test_evaluation_boundary.py` — both of which
   name the old path only in prose explaining the rename. Banning that prose
   would delete the record of why the move happened. Replaced with an `ast` scan
   for the old path in string constants excluding docstrings, so a revived
   functional reference fails but a sentence does not. Verified non-vacuous with
   a deliberate offender file, which the detector caught, and which passed again
   once removed.
3. **Ruff S603/S607** on the new `git check-ignore` subprocess call. Fixed with
   per-call `# noqa`, matching the existing convention in
   `test_evaluation_boundary.py` — not by widening the project ignore list.
4. **`README.md` was stale from before Gate 1.** Its corpus table described a
   48-chunk collection in which `evaluation_case` was 35.4% of production. After
   Gate 1 that is not merely out of date, it is false. Corrected to the current
   84-chunk composition. This was a Gate 1 leftover found while doing §2's
   "update documentation", and is called out rather than folded in silently.

### Deliberately not done

`corpus/raw/evaluation/` still exists, holding only
`audio_reference_manifest.yaml`. §2 named one directory. The manifest carries
hashes with no audio bytes, YAML is not a loader-supported type, and no source
declares it, so it is not production-ingestible. Moving it would be scope creep;
a test asserts what is left so that "the old path is gone" is not misread as "the
evaluation tree is gone".

`prompts/checksums.sha256` line 7 names an even older path
(`corpus/raw/evaluation/rejected_audio_contrast.md`). It is a delivery record of
the incoming package, in the same category as `SHA256SUMS.package`, and was not
altered.

### Verification

```text
pytest tests/                    243 collected, exit 0, 0 failed (219 before)
ruff check .                     All checks passed!
git diff --check                 clean
corpus_lint.py                   PASS — 84 chunks, negative_pattern 1.2% auxiliary
eval/run_evaluation.py           17/17 useful, exact-term PASS, contamination 0,
                                 evaluation-case chunks returned 0,
                                 declared assertions failed 0, citations 0,
                                 preservation 10/10
smoke_test.py                    43/43
mcp_session_check.py             23/23
verify_gate0_integrity.py --verify  re-run last, on the final tree
sha256sum -c SHA256SUMS.current  re-run last, on the final tree
```

Evidence: `docs/evidence/gate1_1-negative-path-rename.json`.

---

## 2026-08-02 — C.Walts v0.4 Gate 1.1 §3: repair rollback documentation

Version held at `0.4.0-dev.2`. No store mutation of substance: the only writes
were a snapshot and a rehearsal restore that returned the store to the state it
was already in.

`docs/rollback.md` mixed rc.2 rehearsal evidence with live instructions, so a
reader could not tell which numbers described 2026-08-01 and which described the
store in front of them. Split:

| Document | Role |
|---|---|
| `docs/history/rollback-rc2.md` | frozen rc.2 record, `git mv` from the old file, unchanged apart from a header stating it must not be followed |
| `docs/rollback.md` | active procedure, rewritten, no production count anywhere |

### A correction to this log

The Gate 1 close listed as unresolved item 3: "the rc.2 owner report **and
`docs/rollback.md`** still describe a 101-chunk collection." The second half was
false. `docs/rollback.md` never contained the number 101 — it described the rc.2
rehearsal at 48 and 97 chunks. Only `docs/owner-test-report-rc2.md` describes
101, at lines 30 and 295, and it is correctly historical. A dated correction is
recorded against the original item rather than replacing it; a record that
quietly repairs itself is not a record. The underlying concern was real and §3
resolves it.

So §3's phrase "the historical 48/97 and 101-count evidence" spans two
documents, not one. The 48/97 evidence moved to `docs/history/rollback-rc2.md`.
The 101 evidence was already in an explicitly historical owner report and was not
touched, per the instruction not to rewrite historical owner reports.

### Counts are derived, never written down

`scripts/verify_restore.py` (new) derives the expected state instead of asserting
it. With `--expect-from-sources` it runs discovery over `config/sources.yaml` and
reproduces the **id set**, not merely a count — two stores can hold the same
number of the wrong chunks. With `--expect-from-snapshot` it reads the restoring
snapshot's own manifest, which is weaker (counts only) but correct when the
corpus itself has been rolled back.

It then interrogates the live store: both collections reopen, Chroma/BM25 id-set
parity, `evaluation_case` zero checked two ways, a live exact-term query, a live
production retrieval, the feedback collection **separately and by its own name**
`badgr_natural_flow_feedback_v1`, and the BADGR Harness store MD5.

### Executed, not merely written down

The historical document earned its authority by being executed. The replacement
was held to the same standard — the documented §2 path was run end to end:

```text
--create   var/snapshots/20260802T042956Z, verified 84/2, BM25 84, ToBI 3 hits
--verify   verified true, failures []
--restore  restored both stores, 84/2, BM25 84
verify_restore.py --expect-from-sources
           expected 84 (derived), live 84, id set 0 absent / 0 unexpected,
           parity true, evaluation_case 0, feedback 2, ToBI 3 hits,
           retrieval probe 12 chunks, harness MD5 unchanged — PASS
```

The refusal claims were tested rather than asserted:

| Damaged snapshot | Result |
|---|---|
| BM25 index removed | refused, exit 2, `snapshot carries no BM25 index` |
| database corrupted after snapshotting | refused, exit 2, `chroma tree digest does not match the snapshot manifest` |
| path outside the project root | refused, exit 2 |

In every case the live store was re-verified afterwards and was untouched:
`--restore` verifies before it writes, so a refused restore cannot leave a
half-restored store. The active document's claim that no flag forces an
unverified snapshot into production is therefore measured, not aspirational.

Exit codes were checked directly rather than through a pipe: 0 on a good
verification, 1 on a count mismatch, 2 on an unusable snapshot. The mismatch case
used a real artefact — the pre-Gate-1 snapshot, whose manifest says 101 against a
live 84 — so the failure path is exercised by data that actually exists.

### A live constraint found before it broke

`mcp/server.py` emits `docs/rollback.md §2` and `docs/rollback.md §3` inside
runtime error messages (lines 423 and 476). Renumbering the active document would
have silently broken an error message no test exercises by hand. §2 remains
"restore from backup" and §3 "rebuild from source"; a comment in the document
says why, and `tests/test_rollback_docs.py` asserts both that every cited section
exists and that it still means what the server claims.

### The two backup kinds are now distinguished

`var/snapshots/` is a complete restore point. `var/backups/` holds
`chroma.sqlite3` only — the automatic pre-delete backups taken by the write
tools. Restoring one of those alone is exactly the rc.2 failure: the lexical
index keeps describing the old collection and retrieval keeps answering. The
active document tabulates the difference and gives the `var/backups/` path its
own procedure ending in a mandatory rebuild and verification.

### Failures and corrections during this checkpoint

1. **`build_records` was guessed wrong.** The first draft of
   `verify_restore.py` called `module.build_records(settings)`. The real
   signature is `build_records(settings, source, root)`, per-source, driven by
   `approved_sources(manifest)`. Checked against `scripts/ingest.py` before
   running rather than after it failed.
2. **Discovery narrates to stdout**, which would have corrupted `--json` output.
   Wrapped in `contextlib.redirect_stdout`.
3. **A test asserted a phrase the document did not contain** — the document read
   `Chroma/BM25 **id-set** parity`, and the bold markers split the literal.
   Reworded the document rather than loosening the assertion.
4. **Ruff E501** on a long line in the new test. Split the expression.
5. **An early refusal test proved the wrong thing.** Placing the damaged snapshot
   in the scratchpad made it fail on project-root containment, not on
   verification. Moved it inside `var/snapshots/` so the intended guard was the
   one exercised, then removed it.

### Verification

```text
pytest tests/                    265 collected, exit 0, 0 failed (243 before)
ruff check .                     All checks passed!
git diff --check                 clean
corpus_lint.py                   PASS — no findings
eval/run_evaluation.py           17/17 useful, exact-term PASS, contamination 0,
                                 evaluation-case chunks returned 0,
                                 declared assertions failed 0, citations 0,
                                 preservation 10/10
smoke_test.py                    43/43
mcp_session_check.py             23/23
verify_restore.py                PASS, expectation derived from source discovery
verify_gate0_integrity.py --verify  re-run last, on the final tree
sha256sum -c SHA256SUMS.current  re-run last, on the final tree
```

Chroma 84, BM25 84, id-set parity exact, feedback 2, BADGR Harness MD5
`bdcbe32b706c6ccce1f62e8e9f2d2c49` unchanged.

Evidence: `docs/evidence/gate1_1-rollback-repair.json`.

---

## 2026-08-02 — C.Walts v0.4 Gate 1.1 §4: formal disposition of EVAL-009

Version held at `0.4.0-dev.2`. Documentation and tests only — no store
mutation, no corpus material, no change to `eval/expectations.yaml`, no
threshold work. Store re-verified unchanged afterwards.

Created `docs/known-limitations-v0.4.md`, a tracked register with four entries:
one deferred limitation and three classifications.

### CW-LIM-009-DENSE-COVERAGE — recorded as specified

```yaml
id: CW-LIM-009-DENSE-COVERAGE
status: deferred
severity: medium
blocks_gate2: false
blocks_threshold_calibration: true
blocks_release_candidate: true
```

All five required statements are recorded verbatim in intent: the single-example
dependency; the prohibition on deriving any corpus example from EVAL-009's
wording; the requirement that the corpus-expansion phase add multiple
independently designed dense technical rewrite examples; that those cover
different technical structures rather than paraphrasing one regression prompt;
and that the entry closes only after retrieval diversity and regression tests
demonstrate more than one substantive source.

### The gap was measured, not restated

Gate 1 disclosed EVAL-009 as "thin". §4 quantified it, and the measurement is
sharper than the disclosure.

EVAL-009 declares three acceptable markers. **Two of them resolve to the same
single chunk:**

| Marker | Chunks | Note |
|---|---|---|
| `Pair CW-021` | 1 | `26e57adf05186f83_11` |
| `dense architecture` | 1 | the same chunk |
| `Market Voice-Delivery Rules` | 5 | all `doc_type: style_rule` |

The measured run matched `Pair CW-021` and returned five chunks, all
`approved_example`, none `style_rule`. The third marker cannot carry the case,
because the case asserts a `style_rule` primary would be wrong. So EVAL-009
passes on exactly one chunk.

**And the gap is narrower than "few technical examples".** The corpus holds nine
technical `approved_example` headings — CW-001, CW-005, CW-018, CW-019, CW-020,
CW-021, CW-022, CW-039 and SCR-002. Technical coverage is not thin. What is
singular is the **dense nominalization chain**, the structure EVAL-009's query
exercises; CW-021 is the only production example of it, and the other eight
demonstrate different structures that do not stand in for it.

This matters for the fix: the corpus-expansion phase should not add "more
technical examples". It should add several genuinely different dense structures
— nominalization chains, stacked prepositional qualifiers, embedded conditional
clauses, passive agentless constructions — each authored independently.

### Three classifications

| Entry | Status | Classification |
|---|---|---|
| `CW-LIM-RC2-COUNT` | `accepted` | accepted historical record — `docs/owner-test-report-rc2.md` lines 30 and 295 state 101 |
| `CW-LIM-ROLLBACK-COUNTS` | `accepted` | accepted historical evidence — `docs/history/rollback-rc2.md` records 48 and 97 |
| `CW-LIM-EVAL-PATH` | `resolved` | resolved by the Gate 1.1 §2 rename, `resolved_by: cdb670d` |

The two historical-count entries are kept **separate**, because they live in
different documents and describe different numbers. Recording them as one item
is the exact conflation corrected in §3; merging them here would have
reintroduced it.

### The register is queryable, which is the only reason it works

`tests/test_known_limitations.py` (22 tests) parses the fenced YAML blocks rather
than grepping prose, and asserts each of the six required fields with its
required value. The load-bearing assertion is `blocks_release_candidate: true`:
it is the register's only enforcement mechanism, so a future release gate can ask
for open blockers and get an answer without a human interpreting paragraphs.
Confirmed working — the query returns exactly
`['CW-LIM-009-DENSE-COVERAGE']`.

Two further tests guard against the register drifting away from reality: the
`resolved_by` sha is verified to be a real commit with `git cat-file`, and every
marker EVAL-009 declares in `eval/expectations.yaml` must be accounted for in the
register, so retuning the case forces the evidence to be revisited.

### Scope held

§4 says record and classify. It does not authorize adding corpus material,
authoring evaluation queries, retuning EVAL-009's markers, or fitting thresholds.
The measurements above exist as the register's evidence and were not used as a
reason to change the case.

### Verification

```text
pytest tests/                    287 collected, exit 0, 0 failed (265 before)
ruff check .                     All checks passed!
git diff --check                 clean
verify_restore.py                PASS — 84/84, id set 0 absent / 0 unexpected,
                                 evaluation_case 0, feedback 2, harness MD5 unchanged
verify_gate0_integrity.py --verify  re-run last, on the final tree
sha256sum -c SHA256SUMS.current  re-run last, on the final tree
```

Evidence: `docs/known-limitations-v0.4.md`, `docs/evidence/gate1_1-eval009-disposition.json`.

---

## 2026-08-02 — C.Walts v0.4 Gate 1.1 §5: tests

Version held at `0.4.0-dev.2`. Tests only — no store mutation, no corpus, no
config change.

§5 lists eleven properties. Nine were already proved by §2–§4; two were not, and
claiming otherwise would have been the easy and wrong answer. `§5` is recorded
as `tests/test_gate1_1_requirements.py` (34 tests), one named requirement per
clause, so a reviewer can walk the list without reverse-engineering which
assertion in which file covers which property.

### Conformance map

| § | Requirement | Proved by |
|---|---|---|
| 5.1 | no production path contains `corpus/raw/evaluation/` | `test_r01_*` (live store metadata scan **and** source manifest) |
| 5.2 | evaluation directories excluded from ingestion | `test_r02_*`, 7 parametrised paths |
| 5.3 | negative-pattern material remains production corpus | `test_r03_*` — approved source **and** present in both arms |
| 5.4 | default positive requests exclude negative patterns | `test_r04_*`, 3 live queries |
| 5.5 | caller filters cannot bypass mandatory exclusions | `test_r05_*` — **new**, see below |
| 5.6 | contrast requests can retrieve negative patterns | `test_r06_*`, live, asserts the new path |
| 5.7 | `evaluation_case` remains zero | `test_r07_*` — Chroma two ways, BM25 |
| 5.8 | active rollback instructions carry no frozen count | `test_r08_*` |
| 5.9 | restore verification checks both Chroma and BM25 | `test_r09_*` — **new**, see below |
| 5.10 | historical rollback evidence preserved | `test_r10_*` |
| 5.11 | EVAL-009 registered, blocks calibration not Gate 2 | `test_r11_*` |

### The two clauses that were not actually covered

**§5.5 — caller filters and negative material.** The bypass was proved for
`evaluation_case` against the live store, but for `negative_pattern` only at the
filter-composition level. A composed filter that looks correct and a retrieval
that actually withholds the material are different claims. Measured directly:
a positive rewrite query carrying `where={"doc_type": "negative_pattern"}`
returns 8 chunks — `approved_example` and `style_rule` — and **zero**
`negative_pattern`. The dense arm's filter becomes an empty intersection, but
BM25 cannot read metadata and neighbour expansion runs afterwards, so material
does reach the fused list and is stripped by the post-fusion exclusion. The test
asserts the outcome rather than the mechanism.

**§5.9 — restore verification covering both stores.** This had no test at all.
`test_rollback_docs.py` asserts the *document* mentions BM25 and that the *tool*
hard-codes no count; neither exercises the tool's behaviour. A `verify_restore.py`
that silently stopped checking the lexical arm would have passed every existing
test while reintroducing exactly the rc.2 failure it exists to catch.

Now covered by five tests that call `verify_restore.verify()` directly:
the report covers both stores and passes on the live store; verification **fails**
when the lexical index is absent; **fails** when the two arms hold different id
sets; **fails** on a stale expected count; and the remaining required checks
(`evaluation_case` zero, feedback by name, exact-term, retrieval probe, harness
MD5) are all present in the report.

The failure cases redirect the module's `PROJECT_ROOT` at a temporary directory
so the real `var/bm25/index.json` is never touched. The expectation is derived
*before* the patch, because `expected_from_sources()` also resolves through
`PROJECT_ROOT` — the first draft patched first and failed with a
`FileNotFoundError` looking for `scripts/ingest.py` under the temp path.

### The new tests were mutation-tested

A test that asserts a failure path is worthless if the failure path is
unreachable. `scripts/verify_restore.py` was deliberately mutated — the
"BM25 index missing" failure replaced with `pass`, and the parity check guarded
by `if False` — and both §5.9 tests failed as intended:

```text
FAILED test_r09_verification_fails_when_the_lexical_index_is_absent
FAILED test_r09_verification_fails_when_the_two_arms_disagree
```

The file was then restored with `git checkout --` and confirmed byte-identical to
a pre-mutation copy, with the tests passing again. The mutation was never
committed.

### Not weakened to pass

No existing assertion was loosened. `test_r11_the_registered_limitation_matches_
the_live_evaluation_result` deliberately asserts EVAL-009 has **exactly one**
supporting `approved_example` chunk, so if the case is ever retuned or the corpus
gains a second dense example, the test fails and
`CW-LIM-009-DENSE-COVERAGE` must be re-measured or closed rather than left
asserting a condition that no longer holds.

### Verification

```text
pytest tests/                    321 collected, exit 0, 0 failed (287 before)
ruff check .                     All checks passed!
git diff --check                 clean
verify_restore.py                PASS — 84/84, id set 0 absent / 0 unexpected
verify_gate0_integrity.py --verify  re-run last, on the final tree
sha256sum -c SHA256SUMS.current  re-run last, on the final tree
```

Evidence: `docs/evidence/gate1_1-test-conformance.json`.

---

## 2026-08-02 — C.Walts v0.4 Gate 1.1 §6: validation

Version held at `0.4.0-dev.2`. All seventeen required checks run. All pass.

| # | Check | Result |
|---|---|---|
| 1 | full pytest | **321 passed**, exit 0 |
| 2 | Ruff | `All checks passed!` |
| 3 | `git diff --check` | clean |
| 4 | corpus lint | `PASS — no findings` |
| 5 | retrieval evaluation | 17/17 useful, exact-term PASS, positive ratio 74%, contamination 0, evaluation-case returned 0, assertions failed 0, citations 0, lexical arm degraded False, preservation 10/10 |
| 6 | smoke | 43/43 |
| 7 | fresh-session MCP | 23/23 (`scripts/mcp_session_check.py`, separate process, stdio) |
| 8 | acquisition verification | all files and embedded licences verified |
| 9 | inventory verification | inventory reproduces |
| 10 | Gate 0 integrity | PASS — delivery record immutable, tree matches, raw data excluded |
| 11 | Gate 1 boundary | 75 boundary tests pass (`test_evaluation_boundary.py` + `test_gate1_1_requirements.py`) |
| 12 | Chroma/BM25 parity | exact — 84/84, id set 0 absent / 0 unexpected |
| 13 | `evaluation_case` zero | 0 by metadata scan and by `where` filter; 0 in BM25 |
| 14 | negative-pattern behavioural | 29 tests pass; positive requests exclude, contrast retrieves |
| 15 | safe isolated restore | snapshot `var/snapshots/20260802T045559Z` created, verified by reopening, restored, re-verified |
| 16 | BADGR Harness checksum | `bdcbe32b706c6ccce1f62e8e9f2d2c49` unchanged |
| 17 | secret scan | no credential patterns in tracked content |

### The tripwire did not fire, and here is why rather than merely that

Two tracked files changed during the run — `docs/evidence/evaluation-report.json`
and `docs/evidence/smoke-test.json` — because `run_evaluation.py` and
`smoke_test.py` rewrite their own evidence on every execution.

Neither is covered by `SHA256SUMS.current`. Confirmed by grepping the manifest
rather than assuming: it lists 17 paths, and those two are not among them. So the
tripwire staying silent is correct behaviour, not a missed detection. No
regeneration was required and `SHA256SUMS.current` was not rewritten.
`SHA256SUMS.package` was not touched; its self-digest is still
`0e7e87d2721cafdfe9bdc41fc057dad601374a0ac21be99dd09de03b480cf091`.

### One real finding, investigated rather than waved through

The churn diff showed two keys beyond the usual timestamps and latency:
`detail` and `max_distance`.

`detail` is the pytest progress string captured inside `smoke-test.json`. It
changed because the suite grew from 287 to 321 tests in §5. Benign.

`max_distance` was not obviously benign and was chased down. **EVAL-008 only**,
`0.327895 → 0.322228`. Every other case is byte-identical, and within EVAL-008
the markers, headings, doc types, `useful_hit`, ranked count, neighbour count and
all pass flags are unchanged. Re-running the evaluation three times returned
`0.322228` every time, so the new value is stable rather than noisy.

Cause, established by querying the collection directly:

`min_distance` and `max_distance` are **not** computed over the fused retrieval
that produces the verdicts. `eval/run_evaluation.py` issues a *separate raw
dense query* — unfiltered, `n_results=5` — purely for similarity-floor analysis.
That query runs against Chroma's HNSW index, which is **approximate**. The
relevant candidates sit within 0.01 of one another:

```text
0.317977  approved_example  Pair CW-013
0.322228  style_rule        Market Voice-Delivery Rules   <- current raw top-5 max
0.327895  approved_example  Pair CW-010                   <- previous value
```

A 0.0057 gap is well inside the recall boundary of an approximate index, so which
of these lands in the raw top-5 can shift when the index is rebuilt or restored —
and this section performed a restore. The fused retrieval is unaffected: CW-010
still appears in the reported headings for both runs.

Two things made this harder to see than it should have been, and both are worth
recording. The five `style_rule` chunks all carry the heading *Market
Voice-Delivery Rules*, so a swap among them is invisible in `top_headings` — an
identical heading list is not proof of an identical chunk set. And `max_distance`
being sourced from a different query than the verdicts is not stated anywhere in
the report itself.

**No verdict changed and nothing is currently calibrated against these numbers:**
`similarity_floor` is `null`, and the aggregate `distance_min/median/max` came
back identical at `0.1439 / 0.336552 / 0.463614`.

It does, however, sharpen an existing entry. `CW-LIM-009-DENSE-COVERAGE` is
recorded with `blocks_threshold_calibration: true`. This is independent evidence
for that field: a similarity floor fitted to raw per-case distances would be
fitted to values that move by ~0.006 across an index restore, with no change in
retrieval quality. Threshold calibration will need to account for ANN
approximation, not just corpus coverage. Recorded here as an observation for that
phase; §6 fits nothing.

### Secret scan

No dedicated secret-scanning tool exists in this repository — worth stating
plainly rather than implying a mature gate. The scan run here was pattern-based
over all tracked content: private-key headers, `sk-`/`ghp_`/`gho_`/`xox*` tokens,
AWS key ids and secret-access-key assignments, and quoted assignments to
`api_key`/`secret`/`password`. **No matches.** An initial broader pattern
returned only the word "token" in tokenizer and `token_count` contexts.

`.env` is untracked and gitignored (`.gitignore:17`). `.env.example` is tracked
and contains variable names with empty values only, under an explicit warning
never to commit `.env`. High-entropy strings in tracked files are SHA-256 digests
and git commit shas in evidence records, which is what those files are for.

### Verification of the final tree

`verify_gate0_integrity.py --verify` and `sha256sum -c SHA256SUMS.current` were
re-run after every writing command, so the PASS recorded describes the tree as
committed, not a pre-churn one.

Evidence: `docs/evidence/gate1_1-validation.json`.

---

## 2026-08-02 — C.Walts v0.4 handoff-only closeout

Version held at `0.4.0-dev.2`. Documentation only — no store mutation, no corpus,
no config change, no test change. Gate 2 not begun.

Created `docs/C.Walts-v0.4-complete-handoff-report.md`, self-contained and usable
with no access to the conversation that produced the work. Covers the original
baseline through rc.1, rc.2, the post-tag correction, Gate 0, Gate 0.1, Gate 1
and Gate 1.1.

### Facts corrected while writing it

**Annotated tags are not commits.** Every prior report in this log quoted
`v0.3.0-rc.2` as `8b0d2d7a…`. That is the **tag object**; the commit it points to
is `5ece81db…`. Both are correct answers to different questions, and
`git rev-parse v0.3.0-rc.2` returns the former. The handoff report gives both,
with the disambiguating commands. Same for rc.1: tag object `4c6a54ec…`, commit
`b3588e84…`.

**MASSIVE partition counts were stated incompletely.** A first draft wrote
"train 11,514 · test 2,974 (+ dev, balance)". The dev partition is a known
number, 2,033, and 11,514 + 2,033 + 2,974 = 16,521 exactly. Corrected before
commit.

### Verified rather than recalled

The report was written from repository facts, not from memory. Spot-checks
performed against the tree before commit: the EVAL-009 supporting chunk id
(`26e57adf05186f83_11`), `STALE_DELETE_LIMIT = 200`, the rollback section
anchors emitted by `mcp/server.py` (`§2`, `§3`) against the active document's
headings, the existence of `schemas/eval_query.schema.json`,
`src/natural_flow_rag/preservation.py` and
`scripts/verify_embedding_contract.py`, all three dataset archive SHA-256 values
and extracted-member hashes, duplicate counts (CLINC150 5, MASSIVE 89,
Banking77 11), and the live store state.

### Unresolved items classified

Six, with explicit blocking fields: **A** `CW-LIM-009-DENSE-COVERAGE` (deferred;
blocks calibration and RC, not Gate 2); **B** ANN/fused-score measurement (open;
blocks calibration — the current `min_distance`/`max_distance` come from a
separate raw ANN query and must not be used for calibration; Gate 5 must
instrument the same dense, lexical and fused run that produced each verdict);
**C** dedicated secret scanning (open engineering gap; a deterministic
repository secret-scanning command is required before Gate 2 selection commits
or as the first Gate 2 prerequisite — the existing pattern scan is **not**
equivalent to a dedicated tool and is not described as one); **D** reporting
sharp edges (corrected in the handoff report, historical evidence unmodified);
**E** the residual audio manifest path (informational, non-ingestible);
**F** historical files (preserved unchanged, explicitly labelled historical).

Two forward-looking observations are recorded in the report rather than acted on,
because acting would exceed this closeout: the holdout rules in
`config/query_allocation.yaml` are prose with no enforcement, and the number of
distinct delivery structures with three or more independent examples — which
governs both `supported_in_domain` and `near_domain_unsupported` — is not
currently known.

### Validation

```text
pytest tests/                    321 passed, exit 0
ruff check .                     All checks passed!
git diff --check                 clean
corpus_lint.py                   PASS — no findings
eval/run_evaluation.py           17/17 useful, exact-term PASS, contamination 0,
                                 evaluation-case returned 0, assertions failed 0,
                                 citations 0, preservation 10/10
smoke_test.py                    43/43
mcp_session_check.py             23/23
acquire_eval_sources.py --verify all files and embedded licences verified
inventory_eval_sources.py --verify  inventory reproduces
verify_gate0_integrity.py --verify  PASS
Gate 1 boundary                  75 tests pass
verify_restore.py                PASS — 84/84, id set 0 absent / 0 unexpected,
                                 evaluation_case 0, feedback 2, harness MD5 unchanged
secret pattern scan              no matches
```

`SHA256SUMS.current` was not affected — the handoff report is a new file and none
of the 17 covered paths changed. `SHA256SUMS.package` untouched.

Evidence: `docs/C.Walts-v0.4-complete-handoff-report.md`,
`docs/evidence/gate1_1-handoff.json`.

---

## 2026-08-02 - C.Walts v0.4 Gate 1.2 Stage 0: freeze and baseline

Version held at `0.4.0-dev.2`. Stage 0 only: no corpus change, no ChromaDB or
BM25 mutation, no threshold fitting, no holdout inspection, no Gate 2 work, and
no gate renumbering.

### Owner clarification

The canonical directive is the owner-provided local-only file
`README_compass_artificat.md`. Its line 4 says it applies to
`feat/natural-flow-rag-activation @ ce4c2b3`; the owner confirmed this is a
typo. The correct target is
`feat/narration-generalization-v0.4 @ ce4c2b300a3bea940abc69e0acff3f9895d5012f`.
The directive otherwise remains controlling.

Two root files are owner-provided local-only context and must not be committed:
`FULL_c.walts_project_outside-eyes-ovrvw_context.txt` and
`README_compass_artificat.md`. To satisfy Stage 0's clean visible tree
requirement without tracking them, their exact root-relative paths were added to
`.git/info/exclude`, avoiding duplicate entries:

```text
/FULL_c.walts_project_outside-eyes-ovrvw_context.txt
/README_compass_artificat.md
```

### Baseline

`git fetch origin --quiet` completed with exit 0. After fetch:

| Fact | Value |
|---|---|
| `git status --short` | empty |
| Branch | `feat/narration-generalization-v0.4` |
| HEAD | `ce4c2b300a3bea940abc69e0acff3f9895d5012f` |
| Upstream | `ce4c2b300a3bea940abc69e0acff3f9895d5012f` |

The complete handoff report at `ce4c2b3` remains the authoritative
CURRENT_STATE. Stage 0 changed no architecture, so no handoff architecture update
was required.

### Validation

```text
.venv/bin/python -m pytest tests/ -q
  exit 0, 321 observed progress dots

.venv/bin/python scripts/verify_restore.py --expect-from-sources
  PASS - expected 84, production 84, BM25 84, id set 0 absent / 0 unexpected,
  evaluation_case 0, feedback 2, ToBI 3 hits, retrieval probe 12 chunks,
  BADGR Harness MD5 bdcbe32b706c6ccce1f62e8e9f2d2c49
```

Evidence: `docs/evidence/gate1_2-stage0-baseline.json`.

---

## 2026-08-02 - C.Walts v0.4 Gate 1.2 Stage 1: determinism instrumentation

Version held at `0.4.0-dev.2`. Stage 1 only: no corpus change, no production
ChromaDB or BM25 mutation, no threshold fitting, no holdout inspection, no Gate 2
work, and no gate renumbering. The owner clarification from Stage 0 remains in
force; `FULL_c.walts_project_outside-eyes-ovrvw_context.txt` and
`README_compass_artificat.md` stayed local-only and untracked.

### Instrument

Added `scripts/determinism_probe.py`, `tests/test_determinism_probe.py`, and
`docs/evidence/gate1_2-determinism.json`. The probe uses an exact
normalized-cosine NumPy oracle over the 84-vector production collection, embeds
five representative strings ten times each, repeats fixed-index queries, rebuilds
scratch Chroma indexes from fixed vectors, compares both sweeps to the oracle,
and removes scratch indexes before exit.

`requirements.txt` now pins `numpy==2.5.1`, the measured local dependency used by
the oracle. This is instrumentation only; the retrieval architecture did not
change, so the complete handoff report did not require an architecture update.

### Result

```text
.venv/bin/python scripts/determinism_probe.py
  determinism probe: 84 vectors, embedding_byte_stable=True, fixed_flips=0,
  rebuilt_flips=0, disposition=cosmetic_float_noise
```

Measured evidence:

| Fact | Value |
|---|---|
| Production collection | 84 vectors, 768 dimensions |
| Embedding repeat probes | 5 strings x 10 repeats |
| Embedding byte stability | `true` |
| Fixed-index recall@24 | min 1.0, mean 1.0, max 1.0 |
| Fixed-index Kendall tau | min 1.0, mean 1.0, max 1.0 |
| Fixed-index max delta to oracle | `5.31664e-07` |
| Fixed-index verdict flips | 0 |
| Rebuilt-index recall@24 | min 1.0, mean 1.0, max 1.0 |
| Rebuilt-index Kendall tau | min 1.0, mean 1.0, max 1.0 |
| Rebuilt-index max delta to oracle | `5.57523e-07` |
| Rebuilt-index verdict flips | 0 |
| Decision disposition | `cosmetic_float_noise` |
| `nomic-embed-text` | stays |
| Thresholds fit | `false` |

Disposition for Stage 1.4: the observed ANN distance wobble is cosmetic float
noise. Distance fields remain diagnostic/volatile and must not be used for
calibration inputs. Stage 4 still owns report-schema provenance, and Gate 5 still
owns threshold fitting.

### Validation

```text
.venv/bin/python -m pytest tests/test_determinism_probe.py -q
  6 passed

.venv/bin/python -m pytest tests/ -q
  exit 0, 327 observed progress dots

.venv/bin/ruff check .
  All checks passed!

git diff --check
  clean

.venv/bin/python -m json.tool docs/evidence/gate1_2-determinism.json
  exit 0

.venv/bin/python scripts/verify_restore.py --expect-from-sources
  PASS - expected 84, production 84, BM25 84, id set 0 absent / 0 unexpected,
  evaluation_case 0, feedback 2, ToBI 3 hits, retrieval probe 12 chunks,
  BADGR Harness MD5 bdcbe32b706c6ccce1f62e8e9f2d2c49

scratch index check
  no /tmp/cwalts-stage1-hnsw-* or in-tree cwalts-stage1-hnsw-* directories found

secret pattern scan
  no matches

raw dataset / holdout tracked path check
  no tracked paths under var, eval/holdout/private, or eval/sources/public_pool
```

Evidence: `docs/evidence/gate1_2-determinism.json`.

---

## 2026-08-02 - C.Walts v0.4 Gate 1.2 Stage 2.2A follow-up: independent BM25 plan parity

Version held at `0.4.0-dev.2`. Scope is the narrow parity hardening follow-up
only: no corpus remediation examples authored, no Stage 2 public-source corpus
records added, no production ChromaDB or BM25 mutation, no threshold fitting, no
holdout inspection, no Stage 3 work, no Gate 2 work, and
`CW-LIM-009-DENSE-COVERAGE` remains open.

### State verification

Before edits, branch was `feat/narration-generalization-v0.4`, HEAD/upstream
were both `e8b3a72e26d7b2327b85aea8a61813b2d6eac00b`, version was
`0.4.0-dev.2`, and the visible working tree was clean. `verify_restore.py
--expect-from-sources` passed at 84 production Chroma chunks, 84 BM25 chunks,
exact ID parity, `evaluation_case` 0, feedback collection 2, and BADGR Harness
MD5 `bdcbe32b706c6ccce1f62e8e9f2d2c49`. Initial BM25 SHA256 was
`9917cf2a20387e0a8917b5746ed8647c03b8c72bb7121b6094420bd309ab18f8`; Chroma
identity for this follow-up is tracked by read-only semantic digest because
opening the existing Chroma client can rewrite SQLite internals even for reads.

### Correction

`compare_reindex_plan.py` no longer assigns the proposed BM25 ID set from the
predicted Chroma ID set. It now derives the proposed Chroma IDs from the final
in-memory plan and separately builds a proposed BM25 index in an isolated temp
directory through `LexicalIndex.build()`, `save()`, and `load()`.

The production Chroma read path now uses SQLite `mode=ro` against
`chroma.sqlite3`; this avoids the Chroma client's read-side file churn during
comparison. The comparison command requires `--dry-run` and has no mutation
mode.

### Validation

```text
.venv/bin/python -m pytest tests/test_stage2_reindex_compare.py -q
  27 passed

.venv/bin/python -m pytest tests/test_stage2_source_validator.py -q
  18 passed

.venv/bin/python -m pytest tests/ -q
  exit 0, 377 observed progress dots

.venv/bin/python -m pytest tests/ --tb=short
  377 passed in 12.17s

.venv/bin/ruff check .
  All checks passed!

git diff --check
  clean

.venv/bin/python scripts/corpus_lint.py
  PASS - 84 chunks, no findings

.venv/bin/python scripts/verify_restore.py --expect-from-sources
  PASS - expected 84, production 84, BM25 84, id set 0 absent / 0 unexpected,
  evaluation_case 0, feedback 2, ToBI 3 hits, retrieval probe 12 chunks,
  BADGR Harness MD5 bdcbe32b706c6ccce1f62e8e9f2d2c49

valid CLI comparison fixture
  schema=pass, verdict=pass, proposed_id_parity=true,
  proposed Chroma/BM25 85/85, mutation_performed=false

missing-BM25 CLI comparison fixture
  schema=pass, verdict=fail, proposed_id_parity=false,
  proposed Chroma/BM25 85/84, mutation_performed=false

extra-BM25 CLI comparison fixture
  schema=pass, verdict=fail, proposed_id_parity=false,
  proposed Chroma/BM25 85/86, mutation_performed=false

final production identities
  Chroma semantic SHA256 367b3eeb3e9e47c7219d99f0f087d2a8b6d79c2a5aa6ffcc88e1228bab356323
  Chroma metadata rows 1666
  BM25 SHA256 9917cf2a20387e0a8917b5746ed8647c03b8c72bb7121b6094420bd309ab18f8
```

---

## 2026-08-02 - C.Walts v0.4 Gate 1.2 Stage 2.2A: pre-mutation safety tooling

Version held at `0.4.0-dev.2`. Scope is safety tooling only: no corpus
remediation examples authored, no Stage 2 public-source corpus records added, no
production ChromaDB or BM25 mutation, no threshold fitting, no holdout
inspection, no Stage 3 work, no Gate 2 work, and `CW-LIM-009-DENSE-COVERAGE`
remains open.

Owner clarification carried forward into Stage 0 evidence: local-only context
files `FULL_c.walts_project_outside-eyes-ovrvw_context.txt`,
`README_compass_artificat.md`, `README_REMEDIATION PROPOSAL.md`, and
`convo_context_for_json_build.txt` are excluded via `.git/info/exclude` and must
remain untracked/uncommitted.

### State verification

Initial verification before edits measured branch
`feat/narration-generalization-v0.4`, HEAD/upstream
`35f59d4f8f3aca71d410182b56873aa32caf419a`, version `0.4.0-dev.2`, and a clean
visible working tree after excluding owner-provided local-only context files.
`verify_restore.py --expect-from-sources` passed at 84 production Chroma chunks,
84 BM25 chunks, exact ID parity, `evaluation_case` 0, feedback collection 2, and
BADGR Harness MD5 `bdcbe32b706c6ccce1f62e8e9f2d2c49`.

### Tooling

Added `scripts/compare_reindex_plan.py`, a read-only proposed-build comparator
that reuses `scripts/ingest.py::build_records` and emits
`schemas/stage2_reindex_comparison.schema.json`.

Added `scripts/validate_stage2_sources.py`, an offline Stage 2
license/provenance validator for local source snapshots and license evidence,
emitting `schemas/stage2_source_validation.schema.json`.

### Validation

```text
.venv/bin/python -m pytest tests/test_stage2_reindex_compare.py -q
  16 passed

.venv/bin/python -m pytest tests/test_stage2_source_validator.py -q
  18 passed

.venv/bin/python -m pytest tests/ -q
  exit 0, 366 observed progress dots

.venv/bin/ruff check .
  All checks passed!

git diff --check
  clean

.venv/bin/python scripts/corpus_lint.py
  PASS - 84 chunks, no findings

.venv/bin/python scripts/verify_restore.py --expect-from-sources
  PASS - expected 84, production 84, BM25 84, id set 0 absent / 0 unexpected,
  evaluation_case 0, feedback 2, ToBI 3 hits, retrieval probe 12 chunks,
  BADGR Harness MD5 bdcbe32b706c6ccce1f62e8e9f2d2c49

valid comparison fixture
  verdict=pass, would_add=1, stale=0, unchanged=0, duplicate_ids=0,
  proposed_id_parity=true, evaluation_case_count=0, mutation_performed=false

duplicate comparison fixture
  verdict=fail, duplicate canonical content reported, mutation_performed=false

valid license/provenance fixture
  verdict=pass, checksum match=true, errors=0, warnings=0

bad-license provenance fixture
  verdict=fail, rejected_license
```

---

## 2026-08-02 - C.Walts v0.4 Gate 1.2 Stage 1 follow-up: disposition hardening

Version held at `0.4.0-dev.2`. Follow-up hardening only: no corpus change, no
production ChromaDB or BM25 mutation, no threshold fitting, no holdout
inspection, no Stage 2 work, and no gate renumbering.

### Correction

Extracted the Stage 1.4 decision logic into `decide_stage1_disposition()`. The
probe now returns `cosmetic_float_noise` only when all seven named criteria pass:

| Criterion | Regenerated value |
|---|---|
| Embedding byte stability | `true` |
| Fixed-index minimum recall@dense_k | 1.0 |
| Rebuilt-index minimum recall@dense_k | 1.0 |
| Fixed-index minimum Kendall tau | 1.0 |
| Rebuilt-index minimum Kendall tau | 1.0 |
| Fixed-index verdict flips | 0 |
| Rebuilt-index verdict flips | 0 |

Failure routing is explicit: embedding instability returns
`embedding_instability_detected`, oracle recall/ranking disagreement returns
`ann_oracle_rank_disagreement`, and remaining verdict instability returns
`ranking_or_verdict_instability_detected`.

### Result

Regenerated `docs/evidence/gate1_2-determinism.json`. The measured conclusion
remained unchanged under the complete criteria:

```text
.venv/bin/python scripts/determinism_probe.py
  determinism probe: 84 vectors, embedding_byte_stable=True, fixed_flips=0,
  rebuilt_flips=0, disposition=cosmetic_float_noise
```

### Validation

```text
.venv/bin/python -m pytest tests/test_determinism_probe.py -q
  11 passed

.venv/bin/python -m pytest tests/ -q
  exit 0, 332 observed progress dots

.venv/bin/ruff check .
  All checks passed!

git diff --check
  clean

.venv/bin/python scripts/verify_restore.py --expect-from-sources
  PASS - expected 84, production 84, BM25 84, id set 0 absent / 0 unexpected,
  evaluation_case 0, feedback 2, ToBI 3 hits, retrieval probe 12 chunks,
  BADGR Harness MD5 bdcbe32b706c6ccce1f62e8e9f2d2c49
```

---

## 2026-08-02 - C.Walts v0.4 Gate 1.2 Stage 2.2B-1D: source-evidence promotion

Version held at `0.4.0-dev.2`. This task promoted approved source evidence and
hardened candidate exactness validation only. No final before/after rewrites were
authored, no production corpus files were created, `config/sources.yaml` was not
modified, Chroma/BM25 were not mutated, holdout/EVAL-009 material was not
inspected, thresholds were not fit, and Gate 2/Stage 3 work did not begin.

### State

Initial verification measured branch `feat/narration-generalization-v0.4`,
HEAD/upstream `04f928d0995ea599e464f97e18c2c0fb763a0b08`, no tracked or staged
diff, version `0.4.0-dev.2`, production Chroma count 84, BM25 count 84, exact
production parity, `evaluation_case` 0, feedback collection 2, embedding
`nomic-embed-text` dimension 768, BADGR Harness MD5
`bdcbe32b706c6ccce1f62e8e9f2d2c49`, and 8 tracked `corpus/raw` files. The only
visible untracked files were owner-provided Stage 2.2B-1C directive files.

### Input Bundle

Accepted B1C review bundle:

```text
c5f03b3a8e3aea5d696989b2073dcd32f0f8830709b2ae2aa6528396465a2511  var/stage2_candidate_review/stage2_b1c_review_bundle.zip
sha256sum -c SHA256SUMS
  all 8 listed review artifacts OK
```

### Source Evidence

Promoted exactly three approved local-only snapshots byte-for-byte into
`docs/evidence/source-snapshots/`:

```text
a7cdf2534af6139a1c3ceceebf6655acc8b9b6c9482d120e8e0f760ec994157f  PMC12452892.jats.xml
d4a44a49bb17d3ae28ae1ceac223bfd27cb272d6d66a11b969e4de0ee6886628  PMC9887997.jats.xml
582455ffdf439f5c521b05114fb82dc07597cefdd442703fe259505537d4e349  PMC12641984.jats.xml
```

`config/stage2_public_sources.yaml` was created as a tracked Stage 2 source-audit
manifest for the ten qualified public sources. It is not a production ingestion
manifest and does not alter `config/sources.yaml`.

### Candidate Exactness

Added `scripts/validate_stage2_candidates.py`, which validates the 12 candidate
records against the tracked source audit manifest and preserved JATS snapshots.
The per-record JSON Schema remains object-level; the script enforces collection
count, ID uniqueness, allocation, source membership, source checksums, locator
resolution, exact passage text, passage hash, tokenizer count, safety flags, and
absence of final rewrite text.

`ST2-CAND-004` was corrected to exact JATS text from
`docs/evidence/source-snapshots/PMC12468771.jats.xml`. The same exactness pass
also corrected `ST2-CAND-001` and `ST2-CAND-003`, which were detected as
paraphrased by the new validator.

### Validation

```text
.venv/bin/python -m pytest tests/test_stage2_candidate_validator.py -q
  14 passed

.venv/bin/python -m pytest tests/ --tb=short
  391 passed in 11.68s

.venv/bin/ruff check .
  All checks passed!

git diff --check
  clean

.venv/bin/python scripts/corpus_lint.py
  PASS - 84 chunks, no findings

.venv/bin/python scripts/verify_restore.py --expect-from-sources
  PASS - expected 84, production 84, BM25 84, id set 0 absent / 0 unexpected,
  evaluation_case 0, feedback 2, ToBI 3 hits, retrieval probe 12 chunks,
  BADGR Harness MD5 bdcbe32b706c6ccce1f62e8e9f2d2c49

sha256sum -c docs/evidence/source-snapshots/SHA256SUMS
  all 10 source snapshots OK

.venv/bin/python scripts/validate_stage2_sources.py --manifest config/stage2_public_sources.yaml
  verdict=pass, sources=10, errors=0, warnings=0

.venv/bin/python scripts/validate_stage2_candidates.py --manifest config/stage2_public_sources.yaml
  verdict=pass, records=12, errors=0, warnings=0

stage2_candidate_duplicates.json
  verdict=pass, production_records=84, bm25_ids=84, exact_parity=true,
  blank_source_ids=0, feedback_records_included=0
```

---

## Gate 1.2 Stage 2.3-H1 — BADGR Harness invariant correction

Stage 2.3 activation remained blocked. This safety-tooling correction removed
the permanent historical BADGR Harness MD5 gate and replaced it with an
operation-scoped semantic guard.

Starting state was verified at commit
`87d5fd3771d484582fce9b80750ae21ad615e6f6`, branch
`feat/narration-generalization-v0.4`, version `0.4.0-dev.2`, with C.Walts
production Chroma 84, BM25 84, exact parity true, `evaluation_case` 0, feedback
2, ID-list SHA-256
`9d2ef292de32f63347c20fceb15e90fb7e861c533c7ab1e9ac2211086babcc8f`, semantic
digest `4c11c53aac587bd6f5cc219e03b14d56d6debe27ea6a0ed57b4a7a322e0d645e`,
`config/sources.yaml`
`cc3d97b0cda06495a8147e92cd3e376762fcad035aa355d2d008449bc7b8f4ef`, and
`NOTICE` `af7629f4260abf1556029990951e46ac9ed842f5526bd44478ae4ea3bf5aca29`.
All ten source-snapshot checksums passed.

The accepted B2R1 bundle
`aa24cfc7f9119c40b9b9c64ac718713a12ead8e5b391a0693d877441564bf689` and H0 drift
bundle `d219b57b8ff058b7f2d887e5cedf6f603d4504bc8984b023f65c19f3e6463a97`
were verified before implementation.

The H0 `CORRUPTION_OR_DAMAGE` classification was corrected to
`INSUFFICIENT_HISTORICAL_EVIDENCE`. The current database health is
`HEALTHY_WITH_KNOWN_CHROMA_SCHEMA_ANOMALY`: Chroma migrations create
`collections`, while `segments.collection` references singular `collection(id)`.
The raw `PRAGMA foreign_key_check` rows remain visible and are recognized only
because every segment resolves logically to `collections.id`, unresolved segment
count is 0, all 2,617 embeddings resolve to recognized collections,
`quick_check` is `ok`, and `integrity_check` is `ok`.

Added `scripts/harness_invariant.py` and focused tests. `scripts/verify_restore.py`
now reports `harness_invariant_checked: false` when no fresh baseline is supplied
and no longer compares against the historical MD5. With `--harness-baseline`, it
uses the operation-scoped semantic comparison and fails on Harness semantic
drift. The historical MD5 remains historical byte-level evidence only; it is not
a permanent acceptance value.

Live Harness read-only cycle:

```text
harness_invariant.py capture --require-quiescent
  verdict=pass
  health=healthy_with_known_chroma_schema_anomaly
  logical_unresolved_segment_collection_count=0
  total_embeddings=2617
  embeddings_resolved_to_recognized_collections=2617

harness_invariant.py verify --require-quiescent
  verdict=pass
  physical_drift=false
  semantic_drift=false
```

No BADGR Harness write occurred; no WAL checkpoint, VACUUM, REINDEX, restore,
service stop, or restart occurred. No C.Walts Chroma/BM25 mutation occurred.
Stage 2.3 activation, Stage 3, Gate 2, holdout inspection, EVAL-009 inspection,
and threshold fitting remained blocked. CW-LIM-009 remains open.

Validation:

```text
.venv/bin/python -m pytest tests/test_harness_invariant.py
  28 passed in 6.89s

.venv/bin/python -m pytest tests/ --tb=short
  419 passed in 18.48s

.venv/bin/ruff check .
  All checks passed!

git diff --check
  clean

.venv/bin/python scripts/verify_restore.py --expect-from-sources
  PASS - expected 84, production 84, BM25 84, id set 0 absent / 0 unexpected,
  evaluation_case 0, feedback 2, ToBI 3 hits, retrieval probe 12 chunks,
  harness_invariant_checked false

.venv/bin/python scripts/verify_restore.py --expect-from-sources \
  --harness-baseline var/harness_gate_correction/current_harness_capture.json \
  --require-harness-invariant --json
  verified=true, harness_invariant_checked=true, harness verdict=pass,
  semantic_drift=false

sha256sum -c docs/evidence/source-snapshots/SHA256SUMS
  all 10 source snapshots OK

.venv/bin/python scripts/validate_stage2_sources.py --manifest config/stage2_public_sources.yaml
  verdict=pass, sources=10, errors=0, warnings=0

.venv/bin/python scripts/validate_stage2_candidates.py --manifest config/stage2_public_sources.yaml
  verdict=pass, records=12, errors=0, warnings=0

.venv/bin/python scripts/corpus_lint.py
  10 expected pre-activation manifest-coverage findings for ignored local
  Stage 2 proposed files under corpus/raw/stage2_public_examples/
```

---

## Gate 1.2 Stage 2.3-H1R2 — Harness snapshot close-safety

Stage 2.3 activation remained blocked. This follow-up fixed the remaining
close-failure cleanup defect in the H1R Harness invariant.

Starting state was verified at commit
`a99f44e01910d611d53190072de1a498a2eb72eb`, branch
`feat/narration-generalization-v0.4`, version `0.4.0-dev.2`, with C.Walts
production Chroma 84, BM25 84, exact parity true, `evaluation_case` 0, feedback
2, `config/sources.yaml`
`cc3d97b0cda06495a8147e92cd3e376762fcad035aa355d2d008449bc7b8f4ef`, and
`NOTICE` `af7629f4260abf1556029990951e46ac9ed842f5526bd44478ae4ea3bf5aca29`.
The accepted H1R review bundle
`68266c5d2f2a2395ecc971f4341e2e12a41258e74737ade52333612f635f4006` was
verified before implementation.

Corrected defect:

- `sqlite_backup_snapshot()` close cleanup can no longer skip later cleanup.
  Destination close, source close, and unlink are all attempted; source-open,
  destination-open, and backup-copy exceptions remain primary, with close/unlink
  errors attached as diagnostic notes.
- Successful backup followed by source-close or destination-close failure now
  fails without returning `SnapshotResult` and still attempts unlink.
- `capture()` now attempts snapshot-analysis connection close and snapshot
  unlink independently. A close failure after successful analysis yields a fail
  verdict with `snapshot_connection_close_failed`; a close failure after analysis
  failure is attached to the original analysis exception.

Live Harness read-only cycle:

```text
harness_invariant.py capture --require-quiescent
  verdict=pass
  health=healthy_with_known_chroma_schema_anomaly
  temporary_snapshot_deleted=true
  logical_unresolved_segment_collection_count=0
  total_embeddings=2617
  embeddings_resolved_to_recognized_collections=2617

harness_invariant.py verify --require-quiescent
  verdict=pass
  baseline_valid=true
  current_capture_valid=true
  comparison_performed=true
  physical_drift=false
  semantic_drift=false
```

No BADGR Harness write occurred; no WAL checkpoint, VACUUM, REINDEX, restore,
service stop, or restart occurred. No retained temporary Harness snapshot was
found. No C.Walts Chroma/BM25 mutation occurred. Stage 2.3 activation, Stage 3,
Gate 2, holdout inspection, EVAL-009 inspection, and threshold fitting remained
blocked. CW-LIM-009 remains open.

Validation:

```text
.venv/bin/python -m pytest tests/test_harness_invariant.py -q
  62 passed

.venv/bin/python -m pytest tests/ --tb=short
  453 passed in 23.43s

.venv/bin/ruff check .
  All checks passed!

git diff --check
  clean

.venv/bin/python scripts/verify_restore.py --expect-from-sources --json
  verified=true, production_count=84, bm25_chunk_ids=84,
  chroma_bm25_parity=true, evaluation_case=0, feedback=2,
  harness_invariant_checked=false

.venv/bin/python scripts/verify_restore.py --expect-from-sources \
  --harness-baseline var/harness_gate_close_safety/current_harness_capture.json \
  --require-harness-invariant --json
  verified=true, harness_invariant_checked=true, harness_quiescence_required=true,
  harness_baseline_valid=true, harness_comparison_performed=true,
  semantic_drift=false

.venv/bin/python scripts/validate_stage2_sources.py --manifest config/stage2_public_sources.yaml
  verdict=pass, sources=10, errors=0, warnings=0

.venv/bin/python scripts/validate_stage2_candidates.py --manifest config/stage2_public_sources.yaml
  verdict=pass, records=12, errors=0, warnings=0

sha256sum -c SHA256SUMS  # run from docs/evidence/source-snapshots/
  all 10 source snapshots OK

.venv/bin/python scripts/corpus_lint.py
  10 expected pre-activation manifest-coverage findings for ignored local
  Stage 2 proposed files under corpus/raw/stage2_public_examples/
```

## 2026-08-04 — Gate 1.2 Stage 2.3 controlled activation preparation

Accepted starting checkpoint:
`f12886c04a85d1da60a2244c08bb4fa5408e11ce`.

Accepted B2R1 package:
`aa24cfc7f9119c40b9b9c64ac718713a12ead8e5b391a0693d877441564bf689`.

Accepted H1R2 Harness package:
`cb817e0c29e4bc90922f9b2723a8d2267c04f3720b07edba639fd53896483f85`.

Version prepared for activation: `0.4.0-dev.3`.

Pre-change state was verified on
`feat/narration-generalization-v0.4`: C.Walts Chroma 84, BM25 84, exact parity
true, `evaluation_case` 0, feedback 2, embedding model `nomic-embed-text`,
digest `0a109f422b47`, dimension 768, `config/sources.yaml` SHA-256
`cc3d97b0cda06495a8147e92cd3e376762fcad035aa355d2d008449bc7b8f4ef`, and
NOTICE SHA-256
`af7629f4260abf1556029990951e46ac9ed842f5526bd44478ae4ea3bf5aca29`.

Fresh pre-activation backup:
`var/backups/stage2-3-pre-activation-20260805T024507Z/`.

Backup result:

```text
fresh_backup_report.json         verdict=pass, Chroma 84, BM25 84,
                                 exact parity true, evaluation_case 0,
                                 feedback 2
fresh_rollback_smoke_test.json   verdict=pass, isolated restore Chroma 84,
                                 BM25 84, exact parity true,
                                 evaluation_case 0, feedback 2
```

Prepared tracked activation content:

- ten accepted Stage 2 public-source `approved_examples.md` files copied
  byte-for-byte from the B2R1 package;
- exactly ten approved public-source entries appended to `config/sources.yaml`;
- accepted ten-source CC BY attribution block appended once to NOTICE;
- dedicated add-only activation tool and wrapper added;
- focused activation tests added.

The exact accepted Stage 2 deterministic IDs remain:

```text
00c8de5cea3d7264_1
34b2313e2e1d6a27_0
3803c58ef7081395_0
4be038e8819e8c1e_0
5c2a189e56a20f08_0
80d2e5225b05e9e1_0
8de17b0cbff6c2cb_0
d4ed381978ee9df0_0
de2924affb966cdc_0
df50d16e51c460fc_1
e70d3e8ae1737bcb_0
f3340055575f6517_0
```

This preparation did not inspect EVAL-009 or holdout material, did not fit
thresholds, did not begin Stage 3 or Gate 2, and did not close `CW-LIM-009`.
Final activation measurements are recorded separately after the live 84-to-96
transition.

## 2026-08-04 — Gate 1.2 Stage 2.3 live activation completed

Content commit:
`d8c5f54bf1bcf756205eb6a701203c197b987927`.

Activation command:

```text
.venv/bin/python scripts/run_stage2_activation.py --confirm-stage2-activation
```

The wrapper verified the fresh backup, captured a quiescent BADGR Harness
baseline, ran the write-capable activation subprocess with `NFR_ALLOW_WRITES`
scoped to that subprocess, and immediately verified the Harness baseline
afterward.

Measured live results:

```text
activation_report.json             verdict=pass, mutation_performed=true,
                                   embedded_text_count=12,
                                   bm25_replaced=true
harness_postcheck.json             verdict=pass, baseline_valid=true,
                                   comparison_performed=true,
                                   physical_drift=false,
                                   semantic_drift=false
post_activation_verification.json  verdict=pass, Chroma 96, BM25 96,
                                   exact parity true
post_activation_state.json         verdict=pass, evaluation_case 0,
                                   feedback 2, prior IDs retained 84,
                                   prior content/metadata changes 0
live_retrieval_verification.json   verdict=pass, required Stage 2 source
                                   coverage retrieved for all families
live_reindex_equivalence.json      verdict=pass, would_add 0, stale 0,
                                   unchanged 96, mutation_performed=false
post_activation_corpus_lint.json   total_chunks=96, failures=0, warnings=0
post_activation_restore_verification.json
                                   verified=true, production_count=96,
                                   bm25_chunk_ids=96, parity=true,
                                   harness_invariant_checked=true,
                                   semantic_drift=false
```

Post-activation validation:

```text
.venv/bin/python -m pytest tests/ --tb=short
  473 passed in 23.37s

.venv/bin/ruff check .
  All checks passed!

git diff --check
  clean

.venv/bin/python scripts/validate_stage2_sources.py
  verdict=pass, sources=10, errors=0, warnings=0

.venv/bin/python scripts/validate_stage2_candidates.py
  verdict=pass, records=12, errors=0, warnings=0

.venv/bin/python var/stage2_authoring/validate_authored_records.py
  verdict=pass, records=12, errors=0, warnings=0

.venv/bin/python var/stage2_authoring/validate_authored_records.py --self-test
  verdict=pass, cases=8, failures=0

sha256sum -c SHA256SUMS  # run from docs/evidence/source-snapshots/
  all 10 source snapshots OK
```

Activation evidence frozen at:
`docs/evidence/gate1_2-stage2-activation.json`.

No BADGR Harness write occurred; no permanent Harness MD5 gate was reintroduced.
No holdout content or EVAL-009 wording was inspected, no threshold fitting was
performed, no Stage 3 implementation or Gate 2 work began, and `CW-LIM-009`
remains open.

---

## Gate 1.2 Stage 2.3-R1 — Activation audit correction

Stage 2.3 was not re-run. The live 96/96 production state from the accepted
activation remained frozen while R1 corrected audit evidence and closed missing
failure-path test coverage.

Starting live state:

```text
branch: feat/narration-generalization-v0.4
HEAD/upstream: e956c4d635b8a3e44b95ca509a050a56e570f059
version: 0.4.0-dev.3
Chroma: 96
BM25: 96
exact parity: true
evaluation_case: 0
feedback: 2
approved production sources: 15
```

Semantic-digest reconciliation:

```text
historical directive digest: 4c11c53aac587bd6f5cc219e03b14d56d6debe27ea6a0ed57b4a7a322e0d645e
activation backup digest:    462cbd6fe89a73c35c2655b86fcd65e7c99b824dab00c79a60217179e5454ee6
```

Both preserved 84-record backups produce `4c11…` with the B2 authoring digest
algorithm and `462c…` with the Stage 2.3 activation digest algorithm. The 84 IDs,
documents, full metadata, and reindex-relevant metadata compare equal. The
discrepancy is algorithmic, not corpus drift.

Reconstructed historical pre-activation regression used an isolated local clone
of content commit `d8c5f54bf1bcf756205eb6a701203c197b987927`, with the preserved
84-record backup copied under that clone and its local `config/rag.yaml` pointed
at the clone path. Live 96/96 production was not touched.

```text
pytest tests/ --tb=short
  472 passed, 1 skipped in 24.01s

pytest tests/test_stage2_activation.py --tb=short
  20 passed in 0.16s

ruff check .
  All checks passed!

git diff --check
  clean

validate_stage2_sources.py
  verdict=pass, sources=10, errors=0, warnings=0

validate_stage2_candidates.py
  verdict=pass, records=12, errors=0, warnings=0

validate_authored_records.py
  verdict=pass, records=12, errors=0, warnings=0

validate_authored_records.py --self-test
  verdict=pass, cases=8, failures=0

compare_reindex_plan.py --dry-run
  verdict=pass, current=84, proposed=96, would_add=12,
  stale=0, unchanged=84, duplicate_ids=0, duplicate_content=0,
  content_changed=0, metadata_changed=0, mutation_performed=false

activate_stage2.py --preflight
  verdict=pass, current=84, final=96, mutation_performed=false
```

Corrective test commit
`65ee89bf01f0131739dc4868fce8b507d43a3c79` adds wrapper/failure-path coverage
and supporting rollback hash assertions:

- Harness baseline capture failure prevents activation and rollback.
- Harness postcheck failure invokes rollback after the activation subprocess has
  exited.
- Activation subprocess failure preserves stdout/stderr evidence and returns
  nonzero after rollback.
- Rollback verification checks original ID-list and semantic digest values.
- `NFR_ALLOW_WRITES=true` is scoped to the activation subprocess.
- Successful wrapper fixture reaches 96/96 without rollback.

Final R1 read-only verification:

```text
pytest tests/test_stage2_activation.py --tb=short
  25 passed in 0.25s

pytest tests/ --tb=short
  478 passed in 24.53s

ruff check .
  All checks passed!

git diff --check
  clean

corpus_lint.py --json
  total_chunks=96, failures=0, warnings=0

verify_restore.py --expect-from-sources --require-harness-invariant
  verified=true, production_count=96, bm25_chunk_ids=96,
  chroma_bm25_parity=true, harness_invariant_checked=true,
  harness_baseline_valid=true, harness_comparison_performed=true,
  harness semantic drift=false

activate_stage2.py --verify-only
  verdict=pass, current=96, bm25=96, exact_parity=true,
  mutation_performed=false

compare_reindex_plan.py --dry-run
  verdict=pass, current=96, proposed=96, would_add=0, stale=0,
  unchanged=96, mutation_performed=false

sha256sum -c SHA256SUMS  # from docs/evidence/source-snapshots/
  all 10 source snapshots OK
```

The published evidence commit
`e956c4d635b8a3e44b95ca509a050a56e570f059` included
`tests/test_negative_pattern_path.py`, outside the original evidence-commit
allowlist. R1 documents this as a procedural deviation: the change was
technically correct, changed test semantics only, and removed an obsolete
hard-coded 84-count assumption after the legitimate 84-to-96 activation. No
production behavior changed and no history rewrite was performed.

Tracked R1 evidence:
`docs/evidence/gate1_2-stage2_3-r1-correction.json`.

No Stage 2.3 reactivation occurred. R1 `mutation_performed=false`; no C.Walts
record was added, deleted, replaced, re-embedded, or re-upserted. No BADGR
Harness write occurred. No holdout content or EVAL-009 wording was inspected, no
threshold fitting was performed, no Stage 3 implementation or Gate 2 work began,
and `CW-LIM-009` remains open.

---

## Gate 1.2 Stage 2.3-H1R — Harness invariant failure-path hardening

Stage 2.3 activation remained blocked. This follow-up hardened the accepted H1
Harness invariant without changing C.Walts production state or the external
BADGR Harness database.

Starting state was verified at commit
`a3eb2746b8ea62e9864c3971d306acf4caa3e88b`, branch
`feat/narration-generalization-v0.4`, version `0.4.0-dev.2`, with C.Walts
production Chroma 84, BM25 84, exact parity true, `evaluation_case` 0, feedback
2, `config/sources.yaml`
`cc3d97b0cda06495a8147e92cd3e376762fcad035aa355d2d008449bc7b8f4ef`, and
`NOTICE` `af7629f4260abf1556029990951e46ac9ed842f5526bd44478ae4ea3bf5aca29`.
The H1 review bundle
`cfb8b08323d975911fe2e172d754f4e164e5dd3abba9b4d5e9f3e1f6ba1bfeb6` was
verified before implementation.

Corrected defects:

- `sqlite_backup_snapshot()` now deletes its temporary SQLite file on
  source-open failure, destination-open failure, and backup-copy failure before
  propagating the original exception.
- `capture()` now deletes returned snapshots on analysis or snapshot-open
  failure and fails closed with `temporary_snapshot_cleanup_failed` if unlink
  cleanup cannot be confirmed.
- `verify()` now validates baselines before semantic comparison and rejects
  failed, malformed, wrong-path, source-writing, prohibited-operation,
  non-quiescent, or incomplete baselines.
- `verify_restore.py --require-harness-invariant` requires quiescent baseline
  and current Harness measurements.
- `smoke_test.py` no longer compares the Harness store against a failed or empty
  baseline capture.

Live Harness read-only cycle:

```text
harness_invariant.py capture --require-quiescent
  verdict=pass
  health=healthy_with_known_chroma_schema_anomaly
  temporary_snapshot_deleted=true
  logical_unresolved_segment_collection_count=0
  total_embeddings=2617
  embeddings_resolved_to_recognized_collections=2617

harness_invariant.py verify --require-quiescent
  verdict=pass
  baseline_valid=true
  current_capture_valid=true
  comparison_performed=true
  physical_drift=false
  semantic_drift=false
```

No BADGR Harness write occurred; no WAL checkpoint, VACUUM, REINDEX, restore,
service stop, or restart occurred. No retained temporary Harness snapshot was
found. No C.Walts Chroma/BM25 mutation occurred. Stage 2.3 activation, Stage 3,
Gate 2, holdout inspection, EVAL-009 inspection, and threshold fitting remained
blocked. CW-LIM-009 remains open.

Validation:

```text
.venv/bin/python -m pytest tests/test_harness_invariant.py -q
  53 passed

.venv/bin/python -m pytest tests/ --tb=short
  444 passed in 23.14s

.venv/bin/ruff check .
  All checks passed!

git diff --check
  clean

.venv/bin/python scripts/verify_restore.py --expect-from-sources --json
  verified=true, production_count=84, bm25_chunk_ids=84,
  chroma_bm25_parity=true, evaluation_case=0, feedback=2,
  harness_invariant_checked=false

.venv/bin/python scripts/verify_restore.py --expect-from-sources \
  --harness-baseline var/harness_gate_hardening/current_harness_capture.json \
  --require-harness-invariant --json
  verified=true, harness_invariant_checked=true, harness_quiescence_required=true,
  harness_baseline_valid=true, harness_comparison_performed=true,
  semantic_drift=false

.venv/bin/python scripts/validate_stage2_sources.py --manifest config/stage2_public_sources.yaml
  verdict=pass, sources=10, errors=0, warnings=0

.venv/bin/python scripts/validate_stage2_candidates.py --manifest config/stage2_public_sources.yaml
  verdict=pass, records=12, errors=0, warnings=0

sha256sum -c SHA256SUMS  # run from docs/evidence/source-snapshots/
  all 10 source snapshots OK

.venv/bin/python scripts/corpus_lint.py
  10 expected pre-activation manifest-coverage findings for ignored local
  Stage 2 proposed files under corpus/raw/stage2_public_examples/
```
# Gate 1.2 Stage 3A — Architecture Ordering Amendment A1

2026-08-08: Stage 3A implementation begins from the accepted Stage 3-P bundle
`86925b434df8eecc00854aafaa78e10e7516dbfb2d4e9129aa10069b7674827e`.
Architecture Ordering Amendment A1 supersedes the impossible pre-Gate-2
populated-qrels exit criterion. This work measures the exact frozen 96-record
production corpus and adds qrels schemas, validation, deterministic
dense/BM25 candidate-pool infrastructure, and synthetic tests only. The
canonical query universe remains absent, so real qrels population is deferred
to Gate 4 after split validation and holdout sealing. No evaluation query,
holdout text, EVAL-009 wording, or threshold was accessed.

Implementation result: architecture commit `08416ec9503ff08d5c41c34ceef1db49eefeedb2`
and implementation commit `36ac9cbed5b626d00b1b4b5b7838e0f1833102db` passed the
focused and complete suites (`12 + 15` focused tests; `505 passed` complete),
Ruff, diff check, source and candidate validators, corpus lint, restore
verification, and the read-only Harness capture/verify cycle. Coverage measured
96 Chroma records and 96 BM25 records with exact parity, all 96 assignments,
zero review-required records, and the expected production ID-list hash. Real
qrels were not created; population remains deferred to Gate 4.

# Gate 1.2 Stage 5 — Split-integrity verifier

2026-08-09: Stage 5 implementation uses the accepted planning bundle
`57d70029aa7a1502344b2d8ee779b2006f49d96ccb6c8fcc7db5b2d3e5d5e66f`. Commit
`73a7c853e5d1f0752c7f849f822a00f49f811a66` adds candidate and private split
schemas, explicit allocation/acquisition namespace mapping, group/template
leakage clustering, exact whole-cluster subset allocation, duplicate and
near-duplicate guards, logical seal identity, lifecycle checks, write
authorization, atomic private output, and Gate 0-backed non-ingestion checks.

Synthetic validation produced exactly 600 records, 300 calibration records,
300 holdout records, 315 public records, 285 custom records, four class totals
of 150, exact configured cells, and deterministic repeated membership. The
focused Stage 5 suite passed 15 tests; the complete suite passed 548 tests;
Ruff, diff check, corpus lint, Gate 0, Stage 3 coverage, and read-only Harness
capture/verify passed. No real candidate universe, split, holdout, qrels, or
evaluation query was created or accessed. Production remained 96/96 with exact
parity and unchanged ID/semantic digests. CW-LIM-009 remains open.
