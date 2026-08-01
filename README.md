# natural-language-flow-rag

Retrieval for natural English wording, conversational flow, and textual prosody.
Part of the BADGR local AI stack. © 2026 BADGRTechnologies LLC — proprietary.

**Status: Gate 2 complete. Gates 3 and 4 are NOT approved.** The code is written,
installed, and tested. No collection exists, nothing has been ingested, and no MCP
server is registered. `writes.allow_writes` is `false` and every write path refuses.

---

## Why this exists separately

The audit at `/home/t0n34781/workspace/natural-flow-rag-audit.md` found the existing
harness RAG had no license tracking, no checksum-based ingestion, no lexical index,
no neighbour references, and collections that could not identify their own embedding
model. Its data also lives in a world-writable SQLite file that a weekday cron job
writes to every morning.

This project reuses the same *runtime* — ChromaDB 1.5.8, Ollama, `nomic-embed-text`,
768 dimensions, cosine — in a **separate persistence directory**, so nothing here can
reach `badgr_harness/rag_db/`. That containment is enforced in code and pinned by
tests, not by convention.

## Measured facts this is built on

Everything below was measured on this host during the read-only audit of
2026-07-31. None of it is quoted from a research report.

| Fact | Value | Consequence |
|---|---|---|
| Embedding dimension | **768** | Asserted on every vector; a mismatch refuses |
| Vector L2 norm | **1.000000** | Ollama pre-normalizes — `normalize_vectors: false` |
| Model context | **2048 tokens** | Hard ceiling; longer input is refused, not truncated |
| Endpoint | `POST /api/embed` | Modern form; the harness used the legacy `/api/embeddings` |
| ChromaDB | **1.5.8** | Matches the version that wrote the existing stores |
| GPU | RX 6500 XT, ~3.98 GiB VRAM | Cross-encoder reranking disabled by default |
| Disk | 91% full, ~79 GB free | Ingestion refuses below 20 GB free |

## Layout

```
config/     rag.yaml (runtime), sources.yaml (license manifest)
corpus/     raw/ (gitignored) · normalized/ · manifests/ · quarantine/
src/        the library
mcp/        stdio server — NOT registered
scripts/    ingest.py (dry-run by default), query.py, backup_chroma.sh
tests/      52 tests, all passing
var/        chroma/ · bm25/ · logs/ · backups/   (gitignored, currently empty)
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests/ -q
```

## Usage

```bash
.venv/bin/python scripts/ingest.py            # dry run — reports, writes nothing
.venv/bin/python scripts/ingest.py --commit   # refuses until Gate 3 is approved
.venv/bin/python scripts/query.py "make this sound natural" --explain
.venv/bin/python mcp/server.py                # manual stdio run; not registered
```

## Corpus status

`config/sources.yaml` currently approves two sources, and both directories are
**empty**:

- **cmudict** — BSD-style license, verified against the official repository on
  2026-07-31. Commercial use permitted; the required notice is reproduced verbatim
  in `NOTICE`. It supplies lexical stress patterns only.
- **owner_examples** — BADGR-authored copy and preferred rewrites. No license
  decision needed; BADGRTechnologies LLC owns the material.

> **Read this before ingesting.** CMUdict is a pronunciation dictionary. It answers
> *"how is this word stressed"*. It contains no prose about rhythm, cadence,
> information flow, or emphasis, and **cannot on its own answer "make this sound
> natural."** `owner_examples` is the source that carries flow knowledge. Until
> files are placed there, this system will retrieve pronunciations, not phrasing.

Everything else — Buckeye, Santa Barbara, Common Voice, LibriSpeech, openSMILE — is
listed under `quarantined` with the reason, and ingestion refuses all of it.

## Safety properties, each pinned by a test

- Writes require **both** `writes.allow_writes` and an explicit `confirm`.
- Collection names are allowlisted; `badgr_corpus` is **not nameable**, not merely
  unwritten.
- The persistence path is proven to resolve inside the project root.
- A vector whose dimension is not 768 is refused before it reaches Chroma.
- Collections are created with an explicit `OllamaEmbeddingFunction`, so the stored
  schema records `nomic-embed-text` instead of Chroma's 384-d default.
- Retrieved text is fenced as untrusted data and scanned for injection patterns.
- Ingestion refuses any chunk with an empty `license` field.

## Known limitations

1. **Tokenizer is approximate.** `cl100k_base` is GPT tokenization, not
   nomic-bert's. Counts are recorded per chunk (`tokenizer` metadata) so a switch
   is detectable, and the caps carry margin. Open decision A4.
2. **`rank-bm25` is unmaintained** — pinned at 0.2.2, no release since 2022-02-16.
   It sits behind `lexical_search.py` so replacing it is a one-file change.
3. **Reranking is not implemented**, only interfaced. VRAM does not support a
   cross-encoder alongside the resident embedding model.
4. **`similarity_floor` is `null`** deliberately. It must come from measurement.
5. **Nothing has been executed end-to-end** against a real collection, because that
   requires Gate 3. Tests cover units and refusal paths, not live retrieval quality.
