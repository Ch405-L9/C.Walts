# Changelog

All notable changes to this project. Format follows Keep a Changelog; versioning
is Semantic Versioning as required by Prompt C §4.3.

## [Unreleased]

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
