# Changelog

All notable changes to this project. Format follows Keep a Changelog; versioning
is Semantic Versioning as required by Prompt C §4.3.

## [0.4.0-dev.2] — Gate 1, evaluation isolation and retrieval decontamination

In progress. Baseline recorded before any mutation: Chroma 101 (17 of them
`doc_type=evaluation_case`, all from
`corpus/raw/evaluation/cases/evaluation_prompts.md`), BM25 101, feedback 2,
Harness store MD5 `bdcbe32b706c6ccce1f62e8e9f2d2c49`, 70 GiB free. All ten
baseline gates passed. The 17 chunk IDs scheduled for removal are listed in
`docs/evidence/gate1-removal-plan.json`, captured before the first change.

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
