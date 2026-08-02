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
`v0.3.0-rc.2` tag. HEAD carries rc.2 plus the three post-tag documentation
corrections; branching from the tag would have silently dropped them. RC2 is not
retagged or modified anywhere in this phase.

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
