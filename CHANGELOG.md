# Changelog

All notable changes to this project. Format follows Keep a Changelog; versioning
is Semantic Versioning as required by Prompt C §4.3.

## [Unreleased]

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
