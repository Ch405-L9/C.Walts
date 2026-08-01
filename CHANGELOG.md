# Changelog

All notable changes to this project. Format follows Keep a Changelog; versioning
is Semantic Versioning as required by Prompt C §4.3.

## [Unreleased]

### Added

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
