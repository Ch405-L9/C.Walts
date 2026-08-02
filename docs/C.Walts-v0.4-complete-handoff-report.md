# C.Walts v0.4 — Complete Project Handoff Report

**Self-contained.** Written to be usable by an engineer or agent with no access
to the conversation that produced the work. Every factual claim in this document
was verified against repository files, git objects, or evidence records at the
time of writing. Where a number is derived rather than fixed, the derivation
command is given instead of the number.

**Status: Gate 1.1 complete at commit `2309426`. Gate 2 has not begun.**

---

## 1. Repository state

| Item | Value |
|---|---|
| Remote | `https://github.com/Ch405-L9/C.Walts.git` (private) |
| Current branch | `feat/narration-generalization-v0.4` |
| HEAD | `23094262c9b79a65a67c62b1af5f7d62a722acae` |
| Remote parity | `origin/feat/narration-generalization-v0.4` == HEAD; working tree clean |
| Version | `0.4.0-dev.2` (`pyproject.toml`) |
| Remote default branch | `feat/natural-flow-rag-activation` |
| `main` | **Does not exist**, locally or remotely. Never used as a working branch. |

### Immutable tags

Both are **annotated** tags. `git rev-parse <tag>` returns the *tag object*, not
the commit. Both values are given because prior records quote the tag-object sha.

| Tag | Tag object | Commit | Subject |
|---|---|---|---|
| `v0.3.0-rc.1` | `4c6a54ec484a09820aa99dc2457f25bf84d713fb` | `b3588e84e2d40681d8638e2e9706f6f81c0582bc` | v0.3.0-rc.1 — C.Walts natural-flow RAG activation |
| `v0.3.0-rc.2` | `8b0d2d7a85a9b9e905db761fbaa5ddb370244eae` | `5ece81db9ab9334246f8e58781627a159d036a68` | C.Walts v0.3.0-rc.2 — corpus quality |

Neither tag has been moved or retagged. `v0.3.0-rc.2^{commit}` is an ancestor of
HEAD; there are **18 commits** between it and HEAD.

```bash
git rev-parse v0.3.0-rc.2            # tag object  -> 8b0d2d7a...
git rev-parse v0.3.0-rc.2^{commit}   # commit      -> 5ece81db...
git merge-base --is-ancestor v0.3.0-rc.2^{commit} HEAD && echo ancestor
```

---

## 2. Commit history, chronological

Two branches. `feat/natural-flow-rag-activation` carries rc.1 → rc.2 → the
post-tag correction and is the remote default. `feat/narration-generalization-v0.4`
branches from `8a86ae3` and carries all v0.4 work.

### Branch `feat/natural-flow-rag-activation` — activation through rc.2

| SHA | Objective | Result |
|---|---|---|
| `de3bd88` | Establish a verified baseline | 52 tests, ruff clean, empty corpus, `git init` (repo did not exist) |
| `235a4d0` | Licensed corpus schema, deterministic ingestion | Content-derived chunk ids; licence required per chunk |
| `59cd9ef` | Explicit nomic embedding contract | 768-d asserted at startup; digest `0a109f422b47` pinned |
| `4cc6641` | Silence S608 in the read-only sqlite inspector | Lint clean without weakening the rule set |
| `53f1c49` | Measured hybrid retrieval pipeline | Dense + BM25 + RRF; **defect found: lexical arm was dead** (§6.1) |
| `a3e0795` | Expose retrieval over project MCP | Seven-tool surface; **defect found by fresh-session test** (§6.5) |
| `b3588e8` | End-to-end smoke validation | **Tagged `v0.3.0-rc.1`** |
| `fdbd68b` | Record the feedback write path and repository topology | Post-tag evidence |
| `883629c` | Record the verified prosody source register | In-band licence verification via JATS `<license>` |
| `0b60363` | Stop git normalising source-snapshot bytes | Checksums over snapshots became stable |
| `e0c41f6` | State §7 credibility as a measurable criterion | Tightened, not weakened; cleared the rc.1 lint warning |
| `1d62b05` | Add the verified prosody glossary corpus | 19 glossary entries; new `glossary` chunk profile |
| `c40b89e` | Add 25 before/after pairs across five registers | Corpus 48 → 101 chunks |
| `818db2c` | Gated stale-chunk deletion in `natural_flow_reindex` | **Six write gates**; `delete_stale` + `source=` refused (§6.4) |
| `4bd4032` | Record that rollback must rebuild the lexical index | The 48/97 finding written down |
| `a38eb3f` | Assert prosody probes return definitions, not questions | Regression test for evaluation-prompt outranking |
| `3da2407` | Report incomplete MCP calls as caller errors | Stopped asserting a frozen count |
| `5ece81d` | Refresh rc.2 evidence from the final verification run | **Tagged `v0.3.0-rc.2`** |
| `8a86ae3` | Correct three post-tag inaccuracies in the rc.2 record | Post-tag correction commit; branch head |

### Branch `feat/narration-generalization-v0.4` — Gate 0

| SHA | Objective | Result |
|---|---|---|
| `a333d6f` | Establish the v0.4 dataset-acquisition baseline | Version `0.4.0-dev.1` |
| `233347b` | Controlled evaluation-source acquisition | Hardened downloader/extractor; 13 adversarial properties |
| `d24e7e9` | Declare CLINC150 as CC BY 3.0 | **The licence its archive ships** (§6.9) |
| `a69675a` | Adversarial dataset archive validation | Path traversal, symlink, size cap, HTTP, licence markers |
| `b47b4c0` | Record the Gate 0 dataset inventory | Inventory + report written |
| `1cca49a` | Complete the Gate 0 report's return values | §11 return values supplied |

### Gate 0.1

| SHA | Objective | Result |
|---|---|---|
| `adc05be` | Close Gate 0 provenance and checksum gaps | Licence reconciliation recorded; `SHA256SUMS` split into `.package`/`.current`; candidate labels demoted to unapproved |

### Gate 1 — evaluation isolation

| SHA | Objective | Result |
|---|---|---|
| `a313337` | Establish the Gate 1 baseline | Version `0.4.0-dev.2` |
| `0b5c908` | Isolate evaluation fixtures from production retrieval | **Caller-filter bypass found and fixed** (§6.6) |
| `044ba5c` | Enforce the evaluation-data production boundary | 41 boundary tests |
| `bac3706` | Record Gate 1 decontamination evidence | Chroma 101 → 84; `evaluation_case` 17 → 0 |

### Gate 1.1 — operational closeout

| SHA | Objective | Result |
|---|---|---|
| `c55662b` | Baseline verification | Re-measured live rather than trusting the Gate 1 record |
| `cdb670d` | Move the negative-pattern corpus out of the evaluation tree | Path renamed; **zero chunk ids changed** (§6.13) |
| `a71e011` | Split the rollback record from the rollback procedure | Active procedure carries no frozen count (§6.12) |
| `41b7556` | Record EVAL-009 dense-coverage as a tracked release blocker | `docs/known-limitations-v0.4.md` created |
| `6bad0d8` | Prove the eleven Gate 1.1 required properties | Two clauses were genuinely uncovered and are now proved |
| `2309426` | Record the full validation run | 17/17 checks pass |

---

## 3. Architecture

### Vector store — ChromaDB

- Collection `badgr_natural_flow_v1`, persistence `./var/chroma`, space **cosine**.
- Allowlist: `badgr_natural_flow_v1`, `badgr_natural_flow_feedback_v1`. Any other
  name is refused by `assert_allowed()`.
- `resolve_inside_project()` refuses any path outside the project root. The BADGR
  Harness store at `/home/t0n34781/projects/badgr_harness/rag_db/` is therefore
  **structurally unreachable** from this code, not merely un-referenced.
- Chunk ids: `sha256(f"{source_id}:{content_hash}")[:16] + "_" + index`
  (`src/natural_flow_rag/schemas.py`). **The file path is not an input.** This is
  why the Gate 1.1 rename moved no id.

### Lexical arm — BM25

- `var/bm25/index.json`, `rank_bm25` BM25Okapi.
- `LexicalIndex` keeps its own tokenized corpus; `save()` refuses to write an
  index with no non-empty token lists and `load()` refuses to load one. Both
  refusals exist because of the defect in §6.1.
- BM25 **cannot read metadata**. Every metadata exclusion is therefore applied
  again after fusion and a third time after neighbour expansion.

### Embeddings — Ollama / nomic-embed-text

| Property | Value |
|---|---|
| Endpoint | `http://127.0.0.1:11434` |
| Model / tag | `nomic-embed-text` / `nomic-embed-text:latest` |
| Digest | `0a109f422b47` — asserted at startup |
| Dimension | **768** — measured, not quoted; asserted on startup |
| Context ceiling | 2048 tokens (hard truncation) |
| Normalisation | Ollama returns L2 norm 1.000000; no renormalisation applied |
| Policy | `explicit_embeddings_only: true` — never pass `query_texts=` to Chroma |
| Mixed models | `forbid_mixed_models: true` |

### Retrieval

Dense 24 candidates + lexical 24 candidates → **reciprocal rank fusion**
(`rrf_k: 60`) → 5 final chunks, `neighbor_chunks: 1`,
`maximum_chunks_per_document: 3`, dedupe on. Reranking is **disabled**
(deferred: ~3.98 GiB VRAM required, 2.14 GB already held).

`similarity_floor: null` — measured and deliberately left disabled. Over the
evaluation queries the top-5 cosine distances span roughly 0.114–0.426 and every
result was a useful hit; there is no separation to cut on, and `_apply_floor`
filters the dense arm only, so a floor would silently change RRF input rather
than final output.

### Retrieval filters — three distinct mechanisms

| Mechanism | Config | Behaviour |
|---|---|---|
| Hard ban | `forbid_doc_types_always: [evaluation_case]` | **Intersected** with any caller filter, never replaced by one. Applied to the dense filter, to the fused list, and again after neighbour expansion. No argument re-admits this material. |
| Intent-conditional exclusion | `exclude_doc_types_by_default: [negative_pattern]` + `contrast_intent_patterns` | Excluded for ordinary requests; re-admitted when the query asks what to avoid. |
| Demotion | `demote_doc_types: []` | Superseded at Gate 1, retained as an empty generic mechanism. Listing `evaluation_case` here would imply it is still expected in production retrieval, which is false. |

### Preservation checks

`src/natural_flow_rag/preservation.py`. `natural_flow_rewrite` accepts an
optional `candidate` and preservation-checks it; on violation it returns the
**original** text plus a warning rather than the candidate.

### MCP surface — exactly seven tools

Read-only: `natural_flow_search`, `natural_flow_collection_health`,
`natural_flow_source_inspect`, `natural_flow_analyze`, `natural_flow_rewrite`.
Write: `natural_flow_feedback`, `natural_flow_reindex`.

### Write gates

Writes require **both** `writes.allow_writes` (config) **and** `confirm=true`
(per call). `NFR_ALLOW_WRITES=true` overrides the config switch for one process.
`config/rag.yaml` currently reads `allow_writes: false`.

`natural_flow_reindex` stale deletion passes six gates in order: `confirm=true`;
`writes.allow_writes`; `dry_run=false`; `delete_stale=true`; every stale id
listed (refuses above `STALE_DELETE_LIMIT` 200); and a **verified** backup taken
before any mutation. `delete_stale` together with `source=` is refused outright
— see §6.4.

### Backup and restore

| Location | Contents | Complete restore point? |
|---|---|---|
| `var/snapshots/<STAMP>/` | Chroma DB + HNSW dirs + `bm25-index.json` + `sources.yaml` + `snapshot.json` | **Yes** |
| `var/backups/<STAMP>/` | `chroma.sqlite3` + `.sha256` only | **No** — vector store only |

`scripts/store_snapshot.py` uses `sqlite3 .backup`, not `cp`: a `cp` of a live
SQLite file can capture a torn page that hashes consistently with itself and
still will not open. Verification opens the snapshot and interrogates it —
**a hash alone is insufficient because a damaged database can still hash.**
`--restore` re-runs verification and refuses on any failure; there is no flag
that forces an unverified snapshot into production.

### Hardware constraints

12 CPUs, 31 GiB RAM, root filesystem 913 GB at **93% used, ~70 GiB free**.
`writes.minimum_free_disk_gb: 20` — writes refuse below this. Reranking is
deferred on VRAM grounds. Ollama also hosts `phi4-mini`, `qwen3:8b`,
`qwen3:14b`, `deepseek-r1:14b`.

---

## 4. Corpus — history and current state

| Milestone | Chunks |
|---|---|
| First dry run (blank-line splitting, defective) | 262 fragments, avg 23 tokens |
| After `example_separator: heading` | 48 |
| After glossary + 25 additional pairs (rc.2) | 101 |
| After Gate 1 evaluation removal | **84** |
| After Gate 1.1 rename (metadata only) | **84** |

### Current state — verified

| Metric | Value |
|---|---|
| Chroma `badgr_natural_flow_v1` | **84** |
| BM25 chunk ids | **84** |
| Chroma/BM25 id-set parity | exact — 0 only-in-Chroma, 0 only-in-BM25 |
| `badgr_natural_flow_feedback_v1` | **2** |
| `evaluation_case` chunks | **0** (metadata scan, `where` filter, and BM25) |
| BADGR Harness store MD5 | `bdcbe32b706c6ccce1f62e8e9f2d2c49` — unchanged throughout |

Composition: `approved_example` 59 (70.2%), `glossary` 19 (22.6%),
`style_rule` 5 (6.0%), `negative_pattern` 1 (1.2%). 53 distinct
`approved_example` headings, of which 9 are technical.

### Negative-pattern material

- Location: **`corpus/raw/negative_patterns/`** (moved from
  `corpus/raw/evaluation/negative/` at Gate 1.1 §2).
- Source id `cwalts_negative_patterns`, `doc_type: negative_pattern`,
  register `contrast`, licence Proprietary — BADGRTechnologies LLC, approved.
- One chunk, id **`9c1e63263b4b8373_0`** — unchanged by the move.
- Behaviour, measured live: an ordinary rewrite request returns **zero**
  negative chunks; an explicit "what to avoid" request returns the chunk from
  the new path; a caller filter of `{"doc_type": "negative_pattern"}` on a
  positive query returns 8 chunks and **zero** negative ones.

### Evaluation prompts are outside production

`eval/regression/source_documents/evaluation_prompts.md` — a regression fixture,
never ingested. `eval/expectations.yaml` (version 2) holds 20 cases: 17
retrieval, 3 behavioural. `config/sources.yaml` carries a
**WITHDRAWN FROM PRODUCTION** record where `cwalts_evaluation_cases` used to be.

Residual: `corpus/raw/evaluation/` still exists holding only
`audio_reference_manifest.yaml` — see unresolved item **E**.

---

## 5. Dataset acquisition record (Gate 0)

Raw archives and extracted files live under `var/eval_sources/` (48 MB), which is
Git-ignored. **No dataset row is committed anywhere.** Archive total 41,749,543
bytes; extracted total 7,539,821 bytes.

### CLINC150

| Field | Value |
|---|---|
| Version | UCI dataset 570, `data_full` |
| Archive URL | `https://archive.ics.uci.edu/static/public/570/clinc150.zip` |
| Archive SHA-256 | `0d8ecc3e1edd7b25cabde0177544ce536ddf773844bc80ef1a75f36e7f030ea2` |
| Bytes | 1,053,960 |
| Records | **23,700** |
| Splits | train 15,000 · val 3,000 · test 4,500 · oos_train 100 · oos_val 100 · oos_test 1,000 |
| OOS records | 1,200 |
| Labels | 151 (150 in-domain + `oos`) |
| Exact case-folded duplicates | **5** |
| Operative licence | **CC BY 3.0** |

Extracted: `clinc150_uci/LICENSE` (19,467 B,
`e6bc9e9c…8b8e76`), `clinc150_uci/data_full.json` (2,495,390 B,
`36923c37…8d56e0`), `clinc150_uci/meta.txt` (2,343 B, `23ecdb7e…d61c6bf`).

**The 3.0 / 4.0 discrepancy, and the conservative decision.** The UCI landing
page for dataset 570 states *Creative Commons Attribution 4.0 International
(CC BY 4.0)* as of the 2026-08-01 access date. The `LICENSE` file physically
inside the archive served from that same page is the *Creative Commons
Attribution 3.0 Unported* legal code. The acquisition tool verifies licences
**in-band** — by reading the LICENSE inside the archive — and refused the
download when the config claimed 4.0. The gate worked.

Resolution: **CC BY 3.0 is designated the operative minimum for this exact
archive**, because it is what the archive ships. This is *not* a finding that the
UCI page is wrong. Both observations are recorded in
`config/approved_eval_datasets.json` under `license_reconciliation`, with status
`unresolved_discrepancy_recorded`. Neither is erased. Any downstream use of
CLINC150-derived queries must satisfy CC BY 3.0, which additionally requires that
modifications be identified as such. Re-check on any re-acquisition: a newer
archive may carry a 4.0 LICENSE. DOI `10.24432/C5MP58`.

### MASSIVE 1.0, en-US

| Field | Value |
|---|---|
| Archive URL | `https://amazon-massive-nlu-dataset.s3.amazonaws.com/amazon-massive-dataset-1.0.tar.gz` |
| Archive SHA-256 | `7df623fd2d300a4d235d6ee5bd396c9a28258d3a0ccb29abdb054506eba153f8` |
| Bytes | 39,500,415 |
| Records (en-US) | **16,521** |
| Partitions | train 11,514 · dev 2,033 · test 2,974 (= 16,521) |
| Scenarios / intents | 18 / 60 |
| Exact case-folded duplicates | **89** |
| Licence | CC BY 4.0 |

Extracted: `1.0/LICENSE` (18,704 B, `c2e6ea01…db1d435`),
`1.0/data/en-US.jsonl` (3,904,197 B, `c70f75c6…356e407e`). **Only** `en-US.jsonl`
is used.

MASSIVE is **not** a multi-intent dataset. It contains single-shot assistant
interactions labelled by scenario and intent.

### Banking77

| Field | Value |
|---|---|
| Archive URL | `https://github.com/PolyAI-LDN/task-specific-datasets/archive/refs/heads/master.zip` |
| Archive SHA-256 | `b8c2ba23bc1ab7b182230c378f07417c8aef735260a2fd3546faef54ecbbfa91` |
| Bytes | 1,195,168 |
| Version | PolyAI master snapshot, acquired at execution time |
| Records | **13,083** |
| Partitions | train 10,003 · test 3,080 |
| Categories | **77** |
| Exact case-folded duplicates | **11** |
| Licence | CC BY 4.0 |

Extracted: `task-specific-datasets-master/LICENSE` (18,650 B, `7e7170e3…c8a2661`),
`banking_data/categories.json` (2,036 B, `53261da8…ce32b63`),
`banking_data/test.csv` (239,961 B), `banking_data/train.csv`.

**Duplicates were counted and deliberately not removed.** They are a property of
the source data and removing them would silently change what the sources are.

### Candidate labels are proposals, not selections

CLINC150 candidate labels, MASSIVE candidate scenarios and intents all carry
`approval_status: unapproved`, `approved_by: null`. They are
`mechanically_proposed_unapproved`. **No query has been selected.**

---

## 6. Defects found, with disposition

Each entry: symptom → root cause → correction → regression test → commit →
residual risk.

### 6.1 The lexical arm was dead (BM25 token persistence)

- **Symptom.** `var/bm25/index.json` held 48 chunk ids and **zero token lists**.
  Retrieval still answered. The health tool reported `lexical_index_chunks: 48`
  because it counted ids.
- **Root cause.** `LexicalIndex.save()` read the tokenized corpus back off the
  `BM25Okapi` object via `hasattr(self._bm25, "corpus")`. `rank_bm25` keeps only
  `doc_freqs` and `doc_len`, so the attribute never existed and a class-level
  empty fallback was written. On load, `BM25Okapi([])` raised
  `ZeroDivisionError`, which `Retriever._lexical` caught and turned into `[]`.
- **Consequence.** Hybrid retrieval had been running **dense-only**, and `H*` /
  `L-L%` — the exact notation BM25 exists to protect — could not be retrieved
  lexically at all. Invisible from every reporting surface.
- **Correction.** `LexicalIndex` keeps its own tokenized corpus; `save()` refuses
  to write an index with no non-empty token lists; `load()` refuses to load one;
  `Retriever._lexical` still degrades but records `lexical_error`.
- **Test.** Five tests including a save→load→search round trip asserting `L-L%`,
  `H*` and `ToBI` retrieve after reload (`tests/test_lexical.py`).
- **Commit.** `53f1c49`.
- **Residual risk.** Low. `break index` returns nothing lexically — the term is
  genuinely absent from the approved corpus. Recorded as a limitation, not a bug.

### 6.2 Evaluation prompts outranked the answers

- **Symptom.** The query `ToBI` ranked the EVAL-004 evaluation prompt **above**
  the glossary's ToBI definition. Measured 2026-08-01.
- **Root cause.** Evaluation prompts were an ingested production source. A prompt
  is lexically dense in the probe term and states its own pass criterion.
- **Correction (two stages).** rc.2 added `demote_doc_types: [evaluation_case]`,
  which reordered results but kept the prompts in them. Gate 1 removed the
  material from production entirely and replaced demotion with the hard ban
  `forbid_doc_types_always: [evaluation_case]`.
- **Test.** `a38eb3f` asserts prosody probes return definitions, not questions;
  `tests/test_evaluation_boundary.py` (41 tests) enforces the boundary.
- **Commit.** `a38eb3f`, then `0b5c908` / `044ba5c` / `bac3706`.
- **Residual risk.** Low. Three independent locks (ingestion refusal, zero
  records in both stores, unconditional retrieval filter), each asserted
  separately.

### 6.3 `maximum_chunks_per_document` keyed on the wrong entity

- **Symptom.** The per-document diversity cap did not constrain results as
  intended.
- **Root cause.** The cap was keyed on the **source** rather than the
  **document**, so several chunks from one file could fill the result set.
- **Correction.** Re-keyed on the document. `maximum_chunks_per_document: 3`.
- **Test.** Covered by retrieval tests and the evaluation report's per-case
  `top_headings`.
- **Commit.** rc.2 range (`CHANGELOG.md` "Changed", v0.3.0-rc.2 section).
- **Residual risk.** Low, but see unresolved item **D**: the five `style_rule`
  chunks share one heading, so a heading list is not a reliable proxy for
  document identity in reports.

### 6.4 Broad stale-deletion hazard

- **Symptom.** In testing, a reindex plan proposed deleting **48 chunks — the
  entire rest of the corpus**.
- **Root cause.** `delete_stale` combined with `source=`. A single-source reindex
  cannot see other sources' chunks, so all of them compute as stale
  (`stale = existing − wanted`).
- **Correction.** `delete_stale` together with `source=` is **refused outright**
  with `INVALID_PARAMS`, and the tool reports what it declined to do. Deletion
  additionally passes six ordered gates including a verified backup and a
  complete stale-id listing (refusing above 200).
- **Test.** `tests/test_write_gates.py`, `tests/test_mcp_tools.py`.
- **Commit.** `818db2c`.
- **Residual risk.** Low. The Gate 1 removal used a full reindex, which computes
  an exact id set, and the plan was captured before mutation.

### 6.5 Incomplete MCP call classification

- **Symptom.** The first headless MCP call returned `status: OK` alongside
  `lexical_index_chunks: 0`.
- **Root cause.** `tool_collection_health` counted `len(LEXICAL)` on an
  **unloaded** index. It reported 0 for a healthy index — and would have reported
  48 for the tokenless index of §6.1. The field existed precisely to catch that
  failure and could not.
- **Correction.** Health now loads the index, reports `lexical_index_error`, and
  returns `DEGRADED` when the lexical count does not match the collection count.
  Separately, incomplete calls are reported as caller errors rather than crashes.
- **Test.** `scripts/mcp_session_check.py` (23 checks, separate process, stdio).
- **Commit.** `a3e0795`, then `3da2407`.
- **Residual risk.** Low. Found by a fresh-session test, not a unit test — the
  fresh-session check is retained for exactly this class of defect.

### 6.6 Caller-filter exclusion bypass

- **Symptom.** Supplying **any** `where` filter silently disabled the project's
  own exclusions. Measured: an EVAL-009 query with an explicit filter returned
  the negative chunk that the unfiltered query excludes.
- **Root cause.** `_default_filter()` returned the caller's `where` untouched
  instead of composing it. The pre-Gate-1 test suite asserted this behaviour as
  correct.
- **Correction.** Clauses are now **intersected** via `$and`. The caller's filter
  is honoured but cannot widen the result. Applied to the dense filter, the fused
  list, and again after neighbour expansion.
- **Test.** `tests/test_negative_policy.py::test_a_caller_filter_narrows_and_is_never_allowed_to_widen`
  (renamed from the test that encoded the defect),
  `test_gate1_1_requirements.py::test_r05_*` (live, both doc types).
- **Commit.** `0b5c908`.
- **Residual risk.** Low. Three pre-existing tests encoded the old semantics and
  were updated with the reason recorded, not deleted.

### 6.7 EVAL-009 `Pair CW-0` marker

- **Symptom.** EVAL-009 accepted the marker `Pair CW-0`, which prefix-matches
  **every** approved pair CW-001 … CW-039. The case could pass on any of them.
- **Root cause.** A marker written as a prefix rather than an identifier.
- **Correction.** Replaced with `Pair CW-021` and `dense architecture` — a
  **tightening**, not a relaxation.
- **Test.** `test_no_expectation_names_an_evaluation_prompt_as_an_answer`;
  `test_r11_the_registered_limitation_matches_the_live_evaluation_result`.
- **Commit.** `0b5c908`.
- **Residual risk.** **Medium — this is unresolved item A.** Tightening the
  marker exposed that only one production chunk supports the case.

### 6.8 Checksum coverage gap

- **Symptom.** A single `SHA256SUMS` mixed the delivered package record with
  current-tree files, so a command used as a release gate would knowingly fail
  once any delivered file was legitimately edited.
- **Root cause.** One manifest serving two incompatible purposes.
- **Correction.** Split into **`SHA256SUMS.package`** (immutable delivery record,
  self-digest pinned at
  `0e7e87d2721cafdfe9bdc41fc057dad601374a0ac21be99dd09de03b480cf091`, with
  `KNOWN_MODIFIED_SINCE_DELIVERY` naming four files and their reasons) and
  **`SHA256SUMS.current`** (17 files, regenerable tripwire).
  `CHANGELOG.md` and `docs/execution-log.md` are deliberately excluded as living
  cross-gate documents.
- **Test.** `scripts/verify_gate0_integrity.py --verify`;
  `test_gate0_integrity_verification_passes`;
  `test_the_delivery_record_is_never_regenerated`.
- **Commit.** `adc05be`.
- **Residual risk.** Low. The gate failed on its first execution because
  `config/approved_eval_datasets.json` had been edited during Gate 0 without
  being recorded — which validated it.

### 6.9 CLINC150 licence mismatch

- **Symptom.** Acquisition **refused** the CLINC150 download: the config declared
  CC BY 4.0, the archive ships CC BY 3.0 Unported.
- **Root cause.** The config trusted the landing page rather than the archive.
- **Correction.** Config corrected to `CC-BY-3.0`, the marker check made
  **stricter** (two markers: `Creative Commons Legal Code` and
  `Attribution 3.0 Unported`), and a full `license_reconciliation` block records
  both authoritative observations without erasing either.
- **Test.** `test_the_clinc150_license_discrepancy_is_recorded_not_resolved`,
  `test_wrong_license_marker_is_rejected`, `test_missing_embedded_license_is_rejected`.
- **Commit.** `d24e7e9`, extended by `adc05be`.
- **Residual risk.** **Open by design** — the discrepancy is recorded as
  unresolved. Downstream use must satisfy CC BY 3.0.

### 6.10 Banking77 header row counted as a record

- **Symptom.** Inventory raised `InventoryError`; the CSV header was counted as
  data.
- **Root cause.** No header handling in the CSV reader.
- **Correction.** The header is **asserted** to equal `["text","category"]` and
  then skipped — asserted rather than blindly discarded, so a schema change fails
  loudly.
- **Test.** `tests/test_gate0_dataset_tools.py`.
- **Commit.** `b47b4c0`.
- **Residual risk.** Low.

### 6.11 Mechanical label false positives

- **Symptom.** The near-domain candidate rule flagged `spending_history`
  (substring "story") and `sync_device` (substring "syn"). 11 candidates proposed.
- **Root cause.** Substring matching over label text.
- **Correction.** Switched to underscore-token-prefix matching with the stem
  `synonym`. 11 → 9 candidates. Separately, labels such as `meaning_of_life`,
  `tell_joke`, `text`, `change_volume`, `general_quirky` are **not** treated as
  near-domain merely because a token rule matched; each is recorded with a
  reason, and all candidates are `unapproved`.
- **Test.** `test_proposed_labels_are_marked_unapproved`.
- **Commit.** `b47b4c0`, extended by `adc05be`.
- **Residual risk.** Low. Nothing is selected; a human must approve.

### 6.12 Chroma-only rollback left a silent half-restore

- **Symptom.** Restoring `chroma.sqlite3` alone rolled the vector store back from
  **97 chunks to 48** while `var/bm25/index.json` still held all 97. **Retrieval
  kept answering**, so the failure was invisible from the caller's side.
- **Root cause.** The backup covered one of two stores. `natural_flow_collection_health`
  caught it and reported `DEGRADED` with `count: 48` against
  `lexical_index_chunks: 97`.
- **Correction.** `scripts/store_snapshot.py` snapshots Chroma **plus** its HNSW
  directories, `var/bm25/index.json` and `config/sources.yaml`, and verifies by
  reopening. `scripts/verify_restore.py` (Gate 1.1) verifies the restored live
  store against a **derived** expectation. `docs/rollback.md` was rewritten to
  restore both stores and to distinguish the two backup kinds.
- **Test.** `tests/test_rollback_docs.py` (22),
  `test_gate1_1_requirements.py::test_r09_*` (5, mutation-tested).
- **Commit.** `4bd4032`, then `a71e011`.
- **Residual risk.** Low. Refusals were tested: missing BM25 → exit 2; corrupted
  DB → exit 2; path outside project root → exit 2; stale expectation → exit 1.
  The live store was verified untouched after each.

### 6.13 Negative-pattern path ambiguity

- **Symptom.** The negative-pattern corpus lived at
  `corpus/raw/evaluation/negative/` — a production-ingestible directory named
  "evaluation", inviting the exact confusion Gate 1 spent a phase undoing.
- **Root cause.** Directory naming, not content. The material was never
  evaluation material.
- **Correction.** `git mv` to `corpus/raw/negative_patterns/`. Proven inert
  **before** the write: a dry run reported `stale 0, would-add 0, identical id
  sets`. The reindex changed exactly one field, `source_path`. The chunk kept id
  `9c1e63263b4b8373_0`; file sha256 `959d9b63…884ed` identical.
- **Test.** `tests/test_negative_pattern_path.py` (24), including live proof of
  both exclusion and contrast reachability.
- **Commit.** `cdb670d`.
- **Residual risk.** Informational only — see unresolved item **E**.

### Additional corrections worth recording

- **First dry run produced 262 chunks averaging 23 tokens** (125 fragments from
  one 1,512-word document) because `never_merge_separate_examples` split on blank
  lines. Fixed by adding `example_separator: heading`. Result: 48 chunks, avg 130
  tokens.
- **The glossary profile split definitions in half** — `break index` lost its
  0-to-4 scale to a chunk boundary. Fixed with a dedicated `glossary` profile
  (target 512, max 768) that refuses rather than splits.
- **A false statement in this project's own execution log.** The Gate 1 close
  claimed `docs/rollback.md` described a 101-chunk collection. It never contained
  that number (it described 48/97); only `docs/owner-test-report-rc2.md` states
  101. Corrected by a **dated note against the original entry**, not by rewriting
  it.
- **Environment caveat.** `claude -p` initially failed with
  `401 API key is invalid` because an `ANTHROPIC_API_KEY` is exported in this
  environment and takes precedence over the CLI login. All headless runs use
  `env -u ANTHROPIC_API_KEY claude -p …`. This affects the test harness only.

---

## 7. Current validation totals

Measured on the tree at commit `2309426`.

| Check | Result |
|---|---|
| pytest | **321 passed**, exit 0 |
| Ruff | `All checks passed!` |
| `git diff --check` | clean |
| corpus lint | `PASS — no findings` |
| retrieval evaluation | 17/17 useful @5, exact-term PASS, positive ratio 74%, contamination 0, evaluation-case returned 0, declared assertions failed 0, citation failures 0, lexical arm degraded False, preservation 10/10 |
| smoke | 43/43 |
| fresh-session MCP | 23/23 |
| acquisition verification | all files and embedded licences verified |
| inventory verification | inventory reproduces |
| Gate 0 integrity | PASS — delivery record immutable, tree matches, raw data excluded |
| Gate 1 boundary | 75 tests |
| Chroma/BM25 parity | exact, 84/84 |
| `evaluation_case` | 0 |
| negative-pattern behavioural | 29 tests |
| BADGR Harness checksum | `bdcbe32b706c6ccce1f62e8e9f2d2c49` unchanged |
| secret pattern scan | no matches |

Test files: `test_gate0_dataset_tools.py` 41 · `test_evaluation_boundary.py` 41 ·
`test_mcp_tools.py` 34 · `test_gate1_1_requirements.py` 34 ·
`test_negative_pattern_path.py` 24 · `test_known_limitations.py` 22 ·
`test_rollback_docs.py` 22 · `test_glossary_retrieval.py` 15 ·
`test_lexical.py` 15 · `test_chunking.py` 14 · `test_preservation.py` 11 ·
`test_security.py` 10 · `test_write_gates.py` 10 · `test_backup.py` 8 ·
`test_schemas.py` 6 · `test_settings.py` 5 · `test_negative_policy.py` 5 ·
`test_fusion.py` 4.

---

## 8. Backup, rollback, checksums, provenance, NOTICE, local-only data

- **Rollback.** Active procedure: `docs/rollback.md`. It contains **no production
  count**; every expectation is derived when it runs. §2 = restore from backup,
  §3 = rebuild from source — these numbers are cited by `mcp/server.py` in
  runtime error messages and are asserted by `tests/test_rollback_docs.py`.
- **Historical rollback evidence.** `docs/history/rollback-rc2.md`, frozen,
  headed *"This document is frozen. Do not follow it."*
- **Checksums.** `SHA256SUMS.package` is the immutable delivery record and must
  never be altered. `SHA256SUMS.current` is a regenerable tripwire over 17 files.
  `docs/evidence/source-snapshots/SHA256SUMS` covers the seven JATS XML source
  snapshots used for in-band licence verification of the prosody literature.
- **Provenance.** Every chunk carries `source_id`, `source_path`, `license`,
  `license_url`, `source_checksum`, `embedding_model`, `embedding_dimension`,
  `tokenizer`, `token_count`. Ingestion refuses any chunk with an empty licence
  field and any source whose `license_status` is not `approved`.
- **NOTICE.** Third-party notices for bundled and ingested material. The
  canonical ToBI labelling guidelines are **restricted to non-commercial use and
  are REFUSED**; no text from them is used. Glossary entries are grounded in
  CC BY literature describing the system.
- **Local-only, never committed.** `var/chroma` (5.4 M), `var/bm25` (124 K),
  `var/eval_sources` (48 M), `var/snapshots` (26 M), `var/backups` (10 M),
  `references/media` (3.9 M). All Git-ignored. `corpus/raw/` is tracked
  selectively: `corpus/raw/*` is ignored with explicit re-includes for
  `owner_examples/`, `style_rules/`, `negative_patterns/`, `evaluation/`,
  `glossary/`. Audio, video and archives are never committed.

---

## 9. Remaining gates

| Gate | Objective |
|---|---|
| **Gate 2** | Select **315 public records** from the three acquired datasets |
| **Gate 3** | Author **285 custom records** |
| **Gate 4** | Assemble and **seal** the 600-query evaluation system |
| **Gate 5** | Calibrate thresholds, run the locked holdout **once**, owner acceptance, release decision |

### The allocation plan — `config/query_allocation.yaml`

600 total, four classes of 150:

| Class | Calibration | Holdout |
|---|---|---|
| `supported_in_domain` (150) | custom 75 | custom 75 |
| `near_domain_unsupported` (150) | clinc150 45, massive 30 | clinc150 15, massive 15, custom 45 |
| `far_out_of_domain` (150) | massive 50, banking77 25 | massive 40, banking77 20, custom 15 |
| `ambiguous_adversarial_insufficient` (150) | clinc150_oos 75 | custom 75 |
| **Totals** | public 225 + custom 75 = **300** | public 90 + custom 210 = **300** |

Overall: **public 315, custom 285**. Schema: `schemas/eval_query.schema.json`.

Rules stated in the allocation file: evaluation records are atomic and never
chunked; they never enter ChromaDB or BM25; no group may appear in both
calibration and holdout; public holdout records must come from groups unused in
calibration; the holdout is frozen and SHA-256 hashed before its first scored
run; a holdout becomes historical regression data once it influences development.

> **These rules currently have no enforcement in code.** They are prose in a YAML
> file. Gate 1 existed because evaluation material leaked into production; these
> are the same class of invariant. A `scripts/verify_eval_split.py` — asserting
> group disjointness, pinning the frozen holdout hash the way
> `SHA256SUMS.package` is pinned, and refusing a scored run against an unfrozen
> holdout — should exist **before** any query file does. `verify_gate0_integrity.py`
> is the existing idiom to copy.

> **Coverage warning for Gate 3 and Gate 5.** 150 `supported_in_domain` queries
> must be answerable from 53 distinct `approved_example` headings. Unresolved
> item **A** shows the failure mode appears at *one example per structure*, not
> per query. The number of distinct delivery structures with ≥3 independent
> examples is **not currently known**, and both `supported_in_domain` and
> `near_domain_unsupported` depend on it. Measure that histogram before authoring.
> Separately, with only 84 chunks the `far_out_of_domain` class will pass
> trivially and discriminate little.

---

## 10. Mandatory rigor for every remaining gate

1. **Clean baseline.** Working tree clean, local == origin, all suites green, and
   store counts re-measured live before any change.
2. **Immutable tags.** `v0.3.0-rc.1` and `v0.3.0-rc.2` are never moved or
   retagged.
3. **Exact scope.** Do only the named gate. Record anything found but out of
   scope; do not fix it silently.
4. **Dry run first.** Every mutating operation runs in dry-run and the plan is
   captured to evidence *before* the write.
5. **Allowlists.** Sources, collections, archive members and paths are
   allowlisted; anything unlisted is refused, not warned about.
6. **Verified backup.** Take a snapshot and verify it **by reopening and
   interrogating it**. A hash alone is insufficient.
7. **Rollback.** Rehearse it. `docs/rollback.md` §2, then
   `scripts/verify_restore.py`.
8. **Adversarial tests.** Prove refusals, not just successes, and mutation-test
   any assertion whose failure path might be unreachable.
9. **Deterministic scripts.** Every claim reproducible by a command; no
   hand-computed numbers in reports.
10. **No weakened tests.** Never loosen an existing assertion to make a phase
    pass. If a test must change, record why it encoded the wrong behaviour.
11. **No evaluation ingestion.** `forbid_doc_types_always: [evaluation_case]` and
    the ingest-path refusals stand. Evaluation records are atomic and never
    chunked.
12. **No raw datasets committed.** They stay under Git-ignored
    `var/eval_sources/`.
13. **No holdout inspection before freezing.** Do not read, sample, or score
    against the holdout until it is sealed and hashed.
14. **No corpus adjustment based on holdout results.** Once the holdout has
    influenced development it is historical regression data, not a holdout.
15. **Secret and PII scans** before every commit.
16. **Chroma/BM25 parity** verified as an **id-set** comparison, not a count.
17. **Smoke and fresh-session MCP** checks after any change touching retrieval,
    the store, or the server.
18. **Recorded failures.** Every failure and correction goes in
    `docs/execution-log.md`. Do not squash away failure history.
19. **Logical commits and push verification.** Confirm HEAD == origin and the
    tree is clean after pushing.

Additionally: run `verify_gate0_integrity.py --verify` and
`sha256sum -c SHA256SUMS.current` **last**, after every writing command, so the
recorded PASS describes the final tree.

---

## 11. Operator commands

### Validation — full sweep

```bash
cd /home/t0n34781/projects/natural-language-flow-rag
.venv/bin/python -m pytest tests/ -q
.venv/bin/ruff check .
git diff --check
.venv/bin/python scripts/corpus_lint.py
.venv/bin/python eval/run_evaluation.py
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/mcp_session_check.py
.venv/bin/python scripts/acquire_eval_sources.py --verify
.venv/bin/python scripts/inventory_eval_sources.py --verify
.venv/bin/python scripts/verify_gate0_integrity.py --verify   # run last
sha256sum -c SHA256SUMS.current                                # run last
```

### Startup and prerequisites

```bash
curl -s http://127.0.0.1:11434/api/tags | head -c 200   # Ollama reachable
ollama list | grep nomic-embed-text                      # model present
.venv/bin/python scripts/verify_embedding_contract.py    # 768-d, digest pinned
df -BG . | tail -1                                       # must exceed 20 GiB free
```

### API-key loading

No API key is required to run this system; embeddings are local via Ollama.
For headless Claude Code runs used by the MCP session check, the exported
`ANTHROPIC_API_KEY` **must be unset** or it takes precedence over the CLI login:

```bash
env -u ANTHROPIC_API_KEY claude -p "…"
```

`.env` is Git-ignored; `.env.example` lists variable names with empty values.

### Dataset checks

```bash
.venv/bin/python scripts/acquire_eval_sources.py --dry-run   # URLs, caps, destinations
.venv/bin/python scripts/acquire_eval_sources.py --verify    # hashes + embedded licences
.venv/bin/python scripts/inventory_eval_sources.py --verify  # inventory reproduces
cat var/eval_sources/manifests/acquisition-manifest.json
```

### Production counts and parity

```bash
.venv/bin/python scripts/verify_restore.py --expect-from-sources
```

Derives the expected **id set** from source discovery and checks: production
count, id-set match, BM25 parity, `evaluation_case` zero (two ways), feedback
collection by name, live exact-term query, live retrieval probe, and the BADGR
Harness checksum. Exit 0 pass / 1 mismatch / 2 unusable input.

### Backup and restore

```bash
.venv/bin/python scripts/store_snapshot.py --create
.venv/bin/python scripts/store_snapshot.py --verify  var/snapshots/<STAMP>
.venv/bin/python scripts/store_snapshot.py --restore var/snapshots/<STAMP>
.venv/bin/python scripts/verify_restore.py --expect-from-sources
```

If only a `var/backups/<STAMP>/` entry exists (Chroma only), the lexical index
**must** be rebuilt — see `docs/rollback.md` §2.5.

### Disabling writes

```bash
unset NFR_ALLOW_WRITES
grep -n 'allow_writes' config/rag.yaml      # must read false
```

### Secret scan (current, pattern-based — see unresolved item C)

```bash
git grep -nIE '(BEGIN [A-Z ]*PRIVATE KEY|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16})' -- .
git ls-files | grep -iE '\.env$|credential|\.pem$|\.key$|id_rsa'
```

---

## 12. Evidence index

**active** = current-state, safe to rely on · **historical** = true when written,
must not be used as current state · **tracked** = in git · **local-only** =
present on disk, Git-ignored, not reproducible from the repository alone.

### Active, tracked

| Path | Contents |
|---|---|
| `docs/rollback.md` | Active rollback procedure. No frozen counts. |
| `docs/known-limitations-v0.4.md` | Limitations register. Machine-readable YAML blocks. |
| `docs/evidence/evaluation-report.json` | Latest evaluation run. Regenerated every run. |
| `docs/evidence/smoke-test.json` | Latest smoke run. Regenerated every run. |
| `docs/evidence/mcp-fresh-session.json` | Latest fresh-session MCP check. |
| `docs/evidence/embedding-contract.json` | 768-d / digest contract proof. |
| `docs/evidence/gate1_1-validation.json` | Gate 1.1 §6 full validation. |
| `docs/evidence/gate1_1-baseline.json` | Gate 1.1 §1 baseline. |
| `docs/evidence/gate1_1-negative-path-rename.json` | Gate 1.1 §2 rename evidence. |
| `docs/evidence/gate1_1-rollback-repair.json` | Gate 1.1 §3 rollback split. |
| `docs/evidence/gate1_1-eval009-disposition.json` | Gate 1.1 §4 EVAL-009 disposition. |
| `docs/evidence/gate1_1-test-conformance.json` | Gate 1.1 §5 conformance map. |
| `config/sources.yaml` | Source manifest. Authority for what is ingestible. |
| `config/rag.yaml` | Runtime configuration. |
| `config/approved_eval_datasets.json` | The only three authorised datasets + licence reconciliation. |
| `config/query_allocation.yaml` | The 600-query plan. |
| `schemas/eval_query.schema.json` | Future evaluation-record schema. |
| `SHA256SUMS.current` | Regenerable tripwire, 17 files. |
| `NOTICE` | Third-party notices. |
| `docs/prosody-source-register.md` | Verified prosody sources; ToBI guidelines refused. |
| `docs/owner-test-sheet.md` | Owner-facing test sheet. |
| `docs/repeatability_blueprint.md`, `docs/owner_actions.md` | Gate 0 package docs. |

### Historical, tracked — never use as current state

| Path | Why preserved |
|---|---|
| `docs/history/rollback-rc2.md` | The measured 48/97 desynchronisation. The reason the active procedure exists. |
| `docs/owner-test-report-rc2.md` | Owner acceptance record at rc.2. States 101 chunks (lines 30, 295). |
| `SHA256SUMS.package` | Immutable delivery record. **Never alter.** |
| `prompts/checksums.sha256` | Delivery record of the incoming package; names pre-Gate-1 paths. |
| `docs/evidence/gate0-boundary.json`, `gate1-boundary.json` | Store state at those gates (101, then 101→84). |
| `docs/evidence/gate1-removal-plan.json`, `gate1-removal-result.json` | The 17 removed chunk ids, captured before mutation. |
| `docs/evidence/dataset-inventory-gate0.json` | Gate 0 inventory; store counts of 101 are historical. |
| `docs/dataset-acquisition-report-gate0.md` | Gate 0 report; store counts of 101 are historical. |
| `docs/evidence/mcp-smoke-session-{1,2,3}*.md` | rc.2-era MCP session transcripts. |
| `docs/execution-log.md` | Append-only. Contains corrections against earlier entries; read them. |

### Cross-gate living documents (deliberately outside `SHA256SUMS.current`)

`CHANGELOG.md`, `docs/execution-log.md`.

### Local-only — Git-ignored, not reproducible from the repo alone

| Path | Contents |
|---|---|
| `var/chroma/` | Production Chroma store (5.4 M). |
| `var/bm25/index.json` | Lexical index (124 K). |
| `var/eval_sources/` | Raw + extracted datasets and the acquisition manifest (48 M). |
| `var/snapshots/` | Whole-store snapshots (26 M). |
| `var/backups/` | Chroma-only tool backups (10 M). |
| `references/media/` | Approved audio references (3.9 M). |
| `.env` | Never committed. |

Source snapshots at `docs/evidence/source-snapshots/` (7 JATS XML + `SHA256SUMS`)
are **tracked** — they are the in-band licence evidence for the prosody
literature.

---

## 13. Unresolved items — exact classifications

### A. `CW-LIM-009-DENSE-COVERAGE`

```yaml
id: CW-LIM-009-DENSE-COVERAGE
status: deferred
blocks_gate2: false
blocks_threshold_calibration: true
blocks_release_candidate: true
```

EVAL-009 declares three markers. Two of them — `Pair CW-021` and
`dense architecture` — resolve to the **same single chunk**
`26e57adf05186f83_11`. The third, `Market Voice-Delivery Rules`, matches five
chunks that are all `doc_type: style_rule`, which the case cannot accept because
it asserts an `approved_example` primary. The case therefore passes on exactly
one chunk.

The corpus holds **nine** technical `approved_example` headings, so technical
coverage is not thin. What is singular is the **dense nominalization chain** —
the structure EVAL-009's query exercises. CW-021 is the only example of it.

**No corpus example may ever be derived from EVAL-009's wording.** The
corpus-expansion phase must add multiple *independently designed* dense technical
rewrite examples covering *different* structures. Closes only when retrieval
diversity and regression tests demonstrate more than one substantive source; a
count of corpus files is not evidence.

### B. ANN / fused-score measurement

```yaml
id: ANN-FUSED-SCORE-MEASUREMENT
status: open
blocks_gate2: false
blocks_threshold_calibration: true
blocks_release_candidate: false
```

`min_distance` and `max_distance` in `docs/evidence/evaluation-report.json` come
from a **separate raw ANN query** — `store.query(embedding=vector, n_results=k)`
in `eval/run_evaluation.py`, unfiltered — issued purely for similarity-floor
analysis. **They are not the scores that produced any verdict**, and they must
not be used for calibration.

Measured instability: EVAL-008's `max_distance` moved `0.327895 → 0.322228`
across an index restore with **no** change to any verdict, marker, heading,
doc type or pass flag, and was then stable across three reruns. The candidates
sit within 0.006 of each other — inside the recall boundary of an approximate
HNSW index.

**Gate 5 must instrument the same dense, lexical and fused run that produced each
verdict.** Before fitting anything, determine whether the wobble is fundamental
or configuration: raise `ef_search` or use exact search for the calibration run,
then establish a noise floor by repeated runs, then fit with margin ≥ several ×
that noise. `similarity_floor` is currently `null`; nothing is calibrated against
these numbers today.

### C. Dedicated secret scanning

```yaml
id: SECRET-SCANNING-GAP
status: open_engineering_gap
required_before: gate2_selection_commits
```

**No dedicated secret-scanning tool exists in this repository.** The scan used
through Gate 1.1 is a `git grep` pattern scan. It returned no matches, and `.env`
is untracked and ignored, but **the pattern scan is not equivalent to a dedicated
tool and must not be described as such.**

Requirement: a deterministic repository secret-scanning command (for example
`gitleaks detect --no-git` or `detect-secrets scan`, pinned and wired into a
pre-commit hook and the validation sweep) **before the first Gate 2 selection
commit, or as the first Gate 2 prerequisite.**

### D. Reporting sharp edges

```yaml
id: REPORTING-IDENTITY-AMBIGUITY
status: open
scope: reporting_only
```

Two descriptions that have been misleading and are corrected here:

1. **`top_headings` equality does not prove identical chunk identity.** The five
   `style_rule` chunks all carry the heading `Market Voice-Delivery Rules`, so an
   identical heading list is consistent with a *different* chunk set. Any report
   asserting result stability must include **chunk ids or source ids**, not
   headings.
2. **Evaluation reports must distinguish raw ANN diagnostic queries from the
   fused, verdict-producing retrieval.** The current report does not, which is
   how item B was initially hard to see.

Corrected in this report. **Historical evidence files are not modified** — the
descriptions are fixed going forward, not retroactively rewritten.

### E. `corpus/raw/evaluation/audio_reference_manifest.yaml`

```yaml
id: RESIDUAL-AUDIO-MANIFEST-PATH
status: informational
blocks_gate2: false
```

`corpus/raw/evaluation/` still exists holding only this one file. It is a
manifest of SHA-256 hashes with **no audio bytes**. YAML is not a loader-supported
type, and **no source in `config/sources.yaml` declares it**, so it is not
ingestible. Covered by
`test_the_remaining_evaluation_directory_holds_no_ingestible_corpus`, which
asserts it is the only remaining file. **No immediate move required.**

### F. Historical files

```yaml
id: HISTORICAL-RECORDS-PRESERVED
status: intentional
```

`docs/owner-test-report-rc2.md` (states 101 chunks),
`docs/history/rollback-rc2.md` (states 48 and 97), `SHA256SUMS.package`, and
`prompts/checksums.sha256` are **preserved unchanged and labelled historical**.
Rewriting a delivery or acceptance record to match the present falsifies it.
They are classified in `docs/known-limitations-v0.4.md` as
`CW-LIM-RC2-COUNT` (accepted historical record) and `CW-LIM-ROLLBACK-COUNTS`
(accepted historical evidence).

> One further correction, recorded rather than erased: the Gate 1 close named
> `docs/rollback.md` as describing 101 chunks. It never did. Only the rc.2 owner
> report does. See the dated note in `docs/execution-log.md`.

---

## 14. Exact first command for Gate 2

Gate 2 selects 315 public records. Before any selection, re-establish the
baseline:

```bash
cd /home/t0n34781/projects/natural-language-flow-rag && \
git status --porcelain && \
git fetch origin --quiet && \
git rev-parse HEAD origin/feat/narration-generalization-v0.4 && \
.venv/bin/python -m pytest tests/ -q && \
.venv/bin/python scripts/verify_restore.py --expect-from-sources
```

Expected: empty `git status`, both SHAs `23094262c9b79a65a67c62b1af5f7d62a722acae`,
321 tests passing, and `PASS` with 84/84 and `evaluation_case 0`.

Do not begin selection until unresolved item **C** is closed — a deterministic
secret-scanning command is a Gate 2 prerequisite. Consider building
`scripts/verify_eval_split.py` (see §9) before the first query file exists.

---

*End of handoff report.*
