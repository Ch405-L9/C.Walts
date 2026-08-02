# Changelog

All notable changes to this project. Format follows Keep a Changelog; versioning
is Semantic Versioning as required by Prompt C §4.3.

## [Unreleased] — Gate 1.1, operational closeout of Gate 1

Version stays at `0.4.0-dev.2`. Gate 1.1 resolves ambiguities Gate 1 disclosed
rather than changing what Gate 1 decided.

### Changed

- `corpus/raw/evaluation/negative/` → `corpus/raw/negative_patterns/` (`git mv`,
  byte-identical, sha256 `959d9b63…884ed`). This was the last
  production-ingestible path named "evaluation" — item 2 of the three Gate 1 left
  open. The material was never evaluation material; only the directory name
  invited that reading.

  The rename is provably inert. Chunk ids derive from `source_id` and chunk
  content, never from the file path, so the single chunk kept its id
  `9c1e63263b4b8373_0`. A dry run before the write reported **stale 0, would-add
  0, identical id sets**, which is what made the seven-step id-migration branch
  inapplicable — measured, not assumed. A metadata-refreshing reindex then
  changed exactly one field, `source_path`. `source_id`, `doc_type`, licence,
  `source_checksum`, register, dialect, chunk index/total, token count, heading
  and profile are unchanged, and the evaluation report's cosine
  min/median/max are byte-identical to the pre-move run.

  Chroma 84 → **84**, BM25 84 → **84**, id-set parity exact, feedback unchanged
  at 2, BADGR Harness store MD5 unchanged. No production `source_path` contains
  "evaluation".
- `README.md` corpus table refreshed. It still described a pre-Gate-1,
  48-chunk collection in which `evaluation_case` was 35.4% of production — stale
  and, after Gate 1, false. Now 84 chunks: approved_example 59, glossary 19,
  style_rule 5, negative_pattern 1.

### Added

- `tests/test_negative_pattern_path.py` — 24 tests, one per §2 proof: old path
  gone, new path ingestible, byte-identical material, identity preserved, chunk
  id path-independent, count still 84, no production path names "evaluation",
  negative material excluded from live positive rewrite retrieval, negative
  material still reachable for an explicit "what to avoid" request, evaluation
  directories still refused, and the `.gitignore` re-include that the move
  needed. Suite 219 → **243**.

- `docs/rollback.md` split. The rc.2 rehearsal evidence — including the measured
  48/97 desynchronisation — is frozen in `docs/history/rollback-rc2.md` under a
  header stating it must not be followed. The active `docs/rollback.md` is
  rewritten and contains **no production count at all**: every expected value is
  derived when the procedure runs. It distinguishes `var/snapshots/` (complete
  restore point) from `var/backups/` (Chroma only — restoring one alone is the
  rc.2 failure), and states that historical reports are not current-state
  manifests.

### Added

- `docs/known-limitations-v0.4.md` — tracked limitations register. Records
  **`CW-LIM-009-DENSE-COVERAGE`** as `deferred` / `severity: medium` /
  `blocks_gate2: false` / `blocks_threshold_calibration: true` /
  `blocks_release_candidate: true`, with the measurement behind it: EVAL-009
  declares three markers, two of which resolve to the *same single chunk*
  (`26e57adf05186f83_11`), and the third matches only `style_rule` chunks the
  case cannot accept. The corpus holds nine technical examples — coverage is not
  thin — but CW-021 is the only **dense nominalization chain**, which is the
  structure the query exercises. No corpus example may ever be derived from
  EVAL-009's wording; the fix belongs to the corpus-expansion phase and must add
  several independently designed dense structures. Also classifies the rc.2
  101-chunk report as accepted historical record, the 48/97 rollback rehearsal as
  accepted historical evidence, and the production path ambiguity as resolved by
  the Gate 1.1 rename (`cdb670d`).
- `tests/test_known_limitations.py` — 22 tests. Parses the register's fenced YAML
  rather than grepping prose, asserts all six required fields with their required
  values, and makes open release blockers discoverable by query — the register's
  only enforcement mechanism. Also verifies `resolved_by` is a real commit and
  that every marker EVAL-009 declares is accounted for, so retuning the case
  forces the evidence to be revisited. Suite 265 → **287**.
- `scripts/verify_restore.py` — post-restore verification. Derives the expected
  **id set** from source discovery, or a count from a snapshot's own manifest,
  then interrogates the live store: both collections reopen, Chroma/BM25 id-set
  parity, `evaluation_case` zero checked two ways, live exact-term query, live
  production retrieval, the feedback collection separately by name, and the BADGR
  Harness checksum. Exit 0 pass / 1 mismatch / 2 unusable input.
- `tests/test_rollback_docs.py` — 22 tests. Asserts the active document holds no
  count the collection has ever had, derives its expectations, distinguishes the
  two backup kinds, and — the one that matters operationally — that every
  `docs/rollback.md §N` anchor emitted by `mcp/server.py` at runtime still
  resolves and still means what the error message claims. Suite 243 → **265**.

### Fixed

- A false statement in this project's own execution log. The Gate 1 close claimed
  `docs/rollback.md` described a 101-chunk collection; it never contained that
  number. Only `docs/owner-test-report-rc2.md` does. Corrected by a dated note
  against the original entry rather than by rewriting it.

### Notes

- The documented restore path was executed end to end, not just written:
  `--create`, `--verify`, `--restore`, then `verify_restore.py` — id set 0 absent
  / 0 unexpected. Refusal was tested with a snapshot missing its BM25 index and
  with a corrupted database; both refused with exit 2, and the live store was
  verified untouched afterwards, because `--restore` verifies before it writes.
- Historical owner reports were not rewritten to display the current count.
- `corpus/raw/evaluation/` still exists, holding only
  `audio_reference_manifest.yaml` — hashes with no audio bytes, and YAML is not a
  loader-supported type, so it is not ingestible. Moving it was outside §2's
  scope. Asserted so "the old path is gone" is never read as "the tree is gone".
- Historical records that name the old path — `prompts/checksums.sha256`, the
  execution log, prior evidence JSONs, the Gate 1 changelog entry below — are
  deliberately not rewritten. Rewriting a delivery record to match the present
  falsifies it.

## [0.4.0-dev.2] — Gate 1, evaluation isolation and retrieval decontamination

The evaluation prompts were an ingested source, and an evaluation prompt states
its own pass criterion — so retrieval could answer an evaluation query by
returning the query. Five cases did exactly that. That material is now a
regression fixture and cannot come back.

### Removed

- 17 `doc_type=evaluation_case` chunks from `badgr_natural_flow_v1` and from the
  BM25 index. Chroma 101 → **84**, BM25 101 → **84**, id-set parity exact,
  feedback collection unchanged at 2. Every removed ID is listed in
  `docs/evidence/gate1-removal-plan.json` (captured before the first change) and
  `docs/evidence/gate1-removal-result.json`.
- `cwalts_evaluation_cases` as a source in `config/sources.yaml`, replaced by a
  WITHDRAWN FROM PRODUCTION record.
- Contaminated expectation markers: EVAL-005, EVAL-006, EVAL-007 and EVAL-009
  each accepted their own prompt; EVAL-010 accepted EVAL-001's.

### Changed

- `corpus/raw/evaluation/cases/evaluation_prompts.md` →
  `eval/regression/source_documents/evaluation_prompts.md` (`git mv`,
  byte-identical). Text, EVAL ids, pass criteria and prior failure disclosures
  preserved; no ingestible copy left behind.
- `demote_doc_types` no longer lists `evaluation_case` — it is `[]`. The hard
  exclusion `forbid_doc_types_always: [evaluation_case]` supersedes it, applied
  to the dense filter, the fused list, and again after neighbour expansion.
- EVAL-009's `Pair CW-0` marker → `Pair CW-021`, `dense architecture`. A
  tightening: the prefix matched every approved pair CW-001…CW-039.
- `eval/expectations.yaml` is version 2 and carries
  `global_forbid_primary_doc_types` / `global_forbid_doc_types_anywhere`, applied
  to every retrieval case and unioned with any per-case list.

### Fixed

- **A caller-supplied filter disabled the project's own exclusions.**
  `_default_filter` returned the caller's `where` untouched, so passing any
  filter silently re-admitted negative material — and would have re-admitted
  evaluation material. Clauses are now intersected: a filter narrows a search, it
  cannot widen one.
- Declared assertions (`primary_doc_type_pass`, `primary_source_pass`,
  `definition_pass`) were computed and never scored. The summary now prints
  `declared assertions failed` and `evaluation-case chunks returned`.

### Added

- `scripts/store_snapshot.py` — whole-store snapshot of Chroma, its HNSW
  directories, BM25 and the source manifest together, verified by reopening and
  interrogating the copy rather than by hashing it.
- `tests/test_evaluation_boundary.py` — 41 tests, one per lock. Suite 177 → 219.

### Verified

Evaluation after decontamination: 17/17 useful hits on production material,
exact-term PASS, contamination 0, evaluation chunks returned 0, assertion
failures 0, citations 0, preservation 10/10. Corpus lint PASS at 84. Smoke 43/43,
MCP 23/23. Rollback rehearsed against the real snapshot — 101 and all 17
evaluation chunks came back, exact-term retrieval intact — then restored forward.
Harness store MD5 `bdcbe32b706c6ccce1f62e8e9f2d2c49` unchanged throughout.

## [0.4.0-dev.1]

Two gates share this development version. Gate 0.1 changed no behaviour and no
version; it closed provenance and checksum gaps left by Gate 0.

### Gate 0.1 — provenance and checksum closeout

Integrity pass over the Gate 0 result: no dataset downloaded,
no query selected, no threshold fitted, and ChromaDB, BM25, MCP behaviour, and
`main` untouched.

#### Added

- `SHA256SUMS.package` — the Gate 0 package exactly as delivered, renamed from
  `SHA256SUMS` with `git mv` and never regenerated. Four of its twelve entries no
  longer match the working tree by design.
- `SHA256SUMS.current` — checksums of the 17 tracked Gate 0 artefacts. Every
  entry must match; regenerated whenever a covered file legitimately changes, so
  it never knowingly fails. `CHANGELOG.md` and `docs/execution-log.md` are
  excluded as living cross-gate documents, stated in the file's own header.
- `scripts/verify_gate0_integrity.py` — `--verify` proves the delivery record is
  unaltered and exactly the four recorded files differ from it, that every
  current checksum matches, and that raw datasets stay Git-ignored and untracked.
  `--write` regenerates the current record. Covered by pytest.
- A `license_reconciliation` record for CLINC150 in
  `config/approved_eval_datasets.json`, carried through the acquisition manifest
  into the inventory and rendered in the report.
- A third-party `NOTICE` section for the three public evaluation sources, with
  the CLINC150 discrepancy stated in full and MASSIVE and Banking77 credited.

#### Changed

- **CLINC150 licence.** Both authoritative observations are now recorded and
  neither is erased: the archive ships CC BY 3.0 Unported, while the UCI landing
  page stated CC BY 4.0 on the 2026-08-01 access date. CC BY 3.0 is designated
  the conservative operative minimum **for this exact archive** — a compliance
  decision, not a finding that the landing page is wrong.
- **Ancestry, corrected.** `v0.3.0-rc.2` points to commit `5ece81db`; the v0.4
  branch was cut from `8a86ae3`, which is **one** commit ahead of RC2, not three.
  That commit corrected three inaccuracies and was **not** documentation-only:
  one corpus header changed, so the collection was reindexed and the evidence
  regenerated, and all gates were re-run and passed. The tag was never moved.
- **Proposed labels demoted.** `near_domain_candidates` is now
  `mechanically_proposed_unapproved`, with `approval_status: "unapproved"`. The
  report names `text`, `change_volume`, `meaning_of_life`, `tell_joke`, and
  `general_quirky` as proposals a reviewer should expect to reject or qualify —
  `text` in CLINC150 means *send a text message*.

#### Confirmed

- Exact case-folded duplicate records, none removed: CLINC150 5, MASSIVE en-US
  89, Banking77 11. Now pinned by test.
- Chroma 101 and 2, BM25 101, BADGR Harness store MD5
  `bdcbe32b706c6ccce1f62e8e9f2d2c49` — unchanged after the manifest rebuild.

### Gate 0 — dataset acquisition baseline

Not a release candidate. `v0.3.0-rc.2` is untouched.

#### Added

- `config/approved_eval_datasets.json` — the only three authorised evaluation
  sources (CLINC150, MASSIVE 1.0 en-US, Banking77), their archive URLs, extract
  allowlists, and embedded-licence markers.
- `config/query_allocation.yaml` — the planned 600-query allocation. Planning
  input only; no query is selected in this phase.
- `schemas/eval_query.schema.json` — the future atomic evaluation-record schema.
  One query per JSONL record; evaluation records are never chunked.
- `docs/owner_actions.md`, `docs/repeatability_blueprint.md`.

#### Changed

- Version `0.3.0` → `0.4.0-dev.1` in `pyproject.toml` and
  `src/natural_flow_rag/__init__.py`.
- `.gitignore` now excludes `var/eval_sources/`, `eval/holdout/private/`, and
  `eval/sources/public_pool/`. Raw public datasets stay local-only.

- `scripts/acquire_eval_sources.py` — HTTPS-only, size-capped, atomically
  renamed, traversal- and symlink-refusing acquisition with in-band licence
  verification and a repeatable `--verify` manifest.
- `scripts/inventory_eval_sources.py` — aggregate inventory and report. Counts,
  label names, checksums, and licence conclusions only; no dataset rows.
- `tests/test_gate0_dataset_tools.py` — 36 adversarial tests. Suite: 145 → 172.
- `docs/evidence/dataset-inventory-gate0.json`,
  `docs/dataset-acquisition-report-gate0.md`.

#### Fixed

- CLINC150 was declared CC BY 4.0. The licence inside the UCI archive is
  **CC BY 3.0 Unported**. The declaration now matches the verified evidence and
  the marker check was tightened, not relaxed.
- The delivered inventory tool assumed headerless Banking77 CSVs; the
  `text,category` header is now asserted and excluded from the counts.
- Six Ruff findings in the incoming package were corrected at source. `S310` was
  resolved with justified per-call `noqa`, not by adding it to the project-wide
  ignore list.

#### Boundary

Acquired records are evaluation-query candidates. They are not corpus chunks and
are never written to `var/chroma/`, `var/bm25/`, or `badgr_natural_flow_v1`.
Measured before and after acquisition: Chroma 101, BM25 101, BADGR Harness store
MD5 `bdcbe32b706c6ccce1f62e8e9f2d2c49` — all unchanged.

## [Unreleased]

### Corrected after tagging rc.2

- The set-2 examples header said "twenty-five pairs" — written before CW-038 and
  CW-039 were appended in response to the EVAL-005 miss. It now says
  twenty-seven and states why the last two exist.
- The A7 note in `config/sources.yaml` still framed CMUdict as the only
  externally licensed material. Marked superseded in part: A7 still holds for
  third-party text that would be INGESTED, which CMUdict alone would be, but
  seven CC BY works now ground the glossary by citation.
- The owner report now connects §6's `demote_doc_types` change to §7's marker
  churn. One retrieval-policy change required three expectation updates, and
  that coupling should be visible to whoever plans rc.3.

All gates re-run after these edits: lint 0/0, evaluation 17/17, 136 tests,
smoke 43/43, fresh-session MCP 23/23, ruff clean, 101 chunks.

## [0.3.0-rc.2] — 2026-08-01 — release candidate `v0.3.0-rc.2`

Corpus quality. The software surface is unchanged in shape; what changed is what
the corpus can actually answer, and what it is licensed to say.

### Added

- `corpus/raw/glossary/prosody_glossary.md` — seventeen prosody terms, one chunk
  each. Owner-authored, grounded in seven CC BY 4.0 works. Three entries
  (`textual prosody`, `breath group`, `cadence`) are marked C.Walts production
  terms and say so rather than borrowing authority they do not have.
- `config/glossary_sources.yaml` — the licence audit. Title, publisher, URL,
  access date, licence, commercial-ingestion status, checksum, and
  approved/quarantined/refused status for every source considered.
- `docs/evidence/source-snapshots/` — the retrieved artefacts, with a
  `SHA256SUMS` manifest, plus a `.gitattributes` rule so git's line-ending
  normalisation cannot invalidate the checksums.
- 27 before/after pairs across the five registers, including two that
  deliberately preserve a weaker claim rather than a stronger one.
- Stale-chunk deletion in `natural_flow_reindex`, behind six gates including a
  verified backup taken before any mutation. `VectorStore.delete` refuses an
  empty id list, refuses ids that are absent, and re-reads to confirm.
- `scripts/mcp_session_check.py` — 23 checks against a genuinely fresh server
  process over the stdio protocol, complementing the in-process smoke suite.
- EVAL-016 through EVAL-020 and `tests/test_glossary_retrieval.py`.

### Changed

- §7 of the delivery rules states Professional credibility as a measurable
  criterion — a blind A/B against a human read — with explicit acceptance
  criteria. Tightened, not weakened. This clears the one rc.1 lint warning.
- `demote_doc_types` stops evaluation prompts leading a definitional lookup.
- `maximum_chunks_per_document` is keyed on the document rather than the source.
- New `glossary` chunk profile keeps a definition whole.
- The smoke suite derives the expected chunk count from the corpus instead of
  asserting a frozen 48, and checks the lexical index covers the same chunks.
- `docs/rollback.md` §2 rebuilds the lexical index and verifies with a health
  check; restoring Chroma alone left a silent half-restore.

### Fixed

- Incomplete MCP calls returned `INTERNAL_ERROR`; arguments are now bound
  against the handler signature and return `INVALID_PARAMS`.

### Known

- The canonical ToBI guidelines (Ohio State University Research Foundation) are
  non-commercial and are REFUSED, with a checksum recorded. No text from them
  appears here; the ToBI entries are grounded in CC BY literature instead.
- EVAL-005 regressed and was recovered partly by adding corpus material after
  seeing the miss. `eval/expectations.yaml` and the owner report both say so.

corpus lint 0/0 · evaluation 17/17 · preservation 10/10 · contamination 0 ·
smoke 43/43 · fresh-session MCP 23/23 · 136 tests · 101 chunks.

### Verified after tagging

- `natural_flow_feedback`'s successful write path executed once against a real
  chunk id: the record landed in `badgr_natural_flow_feedback_v1` and the
  retrieval corpus stayed at 48. Until then only its refusal paths had run.
- Documented that the remote's default branch is the RC branch and that `main`
  does not exist remotely; promotion is an owner decision.

## [0.3.0] — 2026-08-01 — release candidate `v0.3.0-rc.1`

MCP registration and end-to-end capability operational.

### Added

- Completed the approved seven-tool MCP surface: `natural_flow_analyze`
  (measurement only), `natural_flow_feedback` (write-gated, writes to the
  separate `badgr_natural_flow_feedback_v1`), and `natural_flow_reindex`
  (write-gated, dry-run by default). 28 MCP tests.
- `natural_flow_rewrite` accepts a `candidate` rewrite and preservation-checks
  it; a failing candidate is refused and the original text is returned.
- `src/natural_flow_rag/analysis.py` — sentence rhythm, breath grouping, noun
  stacking, passive share, filler, and estimated spoken duration per register.
- `scripts/smoke_test.py` — 42 checks covering Prompt C §11.1–11.5 and §11.7.
- `docs/rollback.md`, `docs/owner-test-sheet.md`, and `docs/evidence/`.
- Project-scoped MCP registration in `.mcp.json`.

### Fixed

- `natural_flow_collection_health` counted chunk ids on an **unloaded** lexical
  index, reporting 0 for a healthy index — and would have reported 48 for the
  tokenless index that made retrieval dense-only. Health now loads the index,
  reports `lexical_index_error`, and returns `DEGRADED` on a count mismatch.

### Added earlier in this cycle

- `src/natural_flow_rag/preservation.py` — detects numbers, dates, protected
  terms, obligation strength, certainty hedging, and proper names changed by a
  candidate rewrite. Detects only; never rewrites.
- `eval/expectations.yaml` and `eval/run_evaluation.py` — expectations written
  before the first run so the useful-hit rate is scored mechanically. Results:
  12/12 useful hit @5, exact-term PASS, 0 contamination, 0 citation failures,
  10/10 preservation, 83 ms p50.
- Negative-material retrieval policy: `exclude_doc_types_by_default` and
  `contrast_intent_patterns`. Negative-pattern chunks are reachable only when a
  request explicitly asks what to avoid.

### Fixed

- **The BM25 index persisted zero tokens**, so hybrid retrieval had been running
  dense-only and `H*` / `L-L%` could not be retrieved lexically. `rank_bm25` does
  not retain its corpus; `save()` was reading it back off the model and writing
  an empty list. The index now carries its own tokens, refuses to save or load
  empty, and a save→load→search round-trip test covers it.
- `Retriever` records `lexical_error` instead of silently degrading to
  dense-only.

### Measured

- `similarity_floor` stays `null`. Top-5 cosine distances span 0.114–0.426 and
  every result in that band was a useful hit, so no threshold separates signal
  from noise at 48 chunks. Revisit condition recorded in `config/rag.yaml`.

## [0.2.0] — 2026-08-01

Isolated collection, ingestion, and the embedding contract are operational.

### Added

- `scripts/verify_embedding_contract.py` — Prompt C §8.1 proof in a disposable
  collection under `var/tmp/`, deleted after evidence capture. All ten checks
  pass; evidence at `docs/evidence/embedding-contract.json`.
- `badgr_natural_flow_v1` created and populated: 48 chunks, 768 dimensions,
  cosine space, persisted at `var/chroma/` and verified to survive a process
  restart. BM25 index built over the same 48 chunks.
- First verified backup at `var/backups/20260801T124553Z/`.
- C.Walts approved corpus placed under `corpus/raw/`: 12 before/after rewrite
  pairs, four positive voice-reference descriptions, two delivery-ready
  reference scripts, the market voice-delivery rules, EVAL-001…015, and the
  negative-pattern descriptions. 48 chunks, 6,240 tokens.
- `scripts/corpus_lint.py` — Prompt D §G1 gate: manifest coverage, unique ids,
  license labels and statuses, secret scan, binary exclusion, duplicate
  detection, polarity (no negative material labelled positive), and the §D
  composition report with its 40% auxiliary cap.
- `example_separator` chunking-profile option with `heading` and `blank_line`
  modes, plus three tests covering both.
- Four approved MP3 references and the unverified transcripts placed locally
  under `references/` and excluded from Git by policy.

### Changed

- `approved_example` chunk profile now splits on H2/rule boundaries rather than
  blank lines. Measured: the old behaviour produced 262 chunks averaging 23
  tokens; the new one produces 48 averaging 130.

## [0.1.0] — 2026-08-01

### Added

- Verified baseline of the natural-language-flow RAG implementation carried over
  from the Prompt B read-only audit: settings/invariant enforcement, Ollama
  explicit-embedding client, Chroma wrapper with the B2 default-embedder hazard
  designed out, chunking, normalization, BM25 lexical index, RRF fusion,
  citations, injection scanning, ingestion script (dry-run by default), and the
  MCP stdio server skeleton.
- Git repository initialized and connected to the private remote
  `Ch405-L9/C.Walts` (C.Walts handoff README §Canonical project decision).
- `.gitignore` hardened for the C.Walts media policy: audio, video, and archive
  binaries are local-only and are never committed; owner-authored C.Walts corpus
  text is explicitly re-included because the remote is private and
  BADGRTechnologies LLC owns the material.
- `docs/execution-log.md` (Prompt C §14) and this changelog.

### Verified at baseline

- 52 unit and refusal-path tests pass.
- `ruff check .` passes.
- `python -m pip check` reports no broken requirements.
- Ollama reachable; `nomic-embed-text:latest` present with digest `0a109f422b47`.
- `badgr_natural_flow_v1` not yet created; `var/chroma/` empty; writes disabled.
