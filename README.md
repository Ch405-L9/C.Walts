# natural-language-flow-rag

Retrieval for natural English wording, conversational flow, and textual prosody.
Part of the BADGR local AI stack. © 2026 BADGRTechnologies LLC — proprietary.

**Status: activated, release candidate `v0.3.0-rc.1`.** The isolated collection
`badgr_natural_flow_v1` holds 48 chunks of approved C.Walts corpus at 768
dimensions, hybrid retrieval is measured, and the seven-tool MCP server is
registered at project scope. `writes.allow_writes` remains `false`: ingestion is
an explicit operator action and both write-capable MCP tools refuse by default.

Repository: `Ch405-L9/C.Walts` (**private**). Branch
`feat/natural-flow-rag-activation`.

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
eval/       expectations.yaml (written before the first run), run_evaluation.py
prompts/    Prompt C, Prompt D, and the C.Walts handoff README
references/ media/ and transcripts/ — LOCAL ONLY, never committed
scripts/    ingest.py (dry-run by default), corpus_lint.py,
            verify_embedding_contract.py, smoke_test.py, query.py, backup_chroma.sh
tests/      103 tests, all passing
var/        chroma/ · bm25/ · logs/ · backups/   (gitignored)
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
NFR_ALLOW_WRITES=true .venv/bin/python scripts/ingest.py --commit
.venv/bin/python scripts/query.py "make this sound natural" --explain
.venv/bin/python scripts/corpus_lint.py       # licence, polarity, composition gate
.venv/bin/python scripts/verify_embedding_contract.py
.venv/bin/python eval/run_evaluation.py
.venv/bin/python scripts/smoke_test.py        # 42 checks
.venv/bin/python mcp/server.py                # manual stdio run
```

## Corpus status

`badgr_natural_flow_v1` holds **48 chunks / 6,240 tokens**, all under a single
licence (`Proprietary — BADGRTechnologies LLC`):

| Source | doc_type | Chunks | Share |
|---|---|---:|---:|
| `owner_examples` — before/after pairs, positive voice references, reference scripts | approved_example | 59 | 70.2% |
| `cwalts_prosody_glossary` — prosody terms | glossary | 19 | 22.6% |
| `cwalts_style_rules` — market voice-delivery rules | style_rule | 5 | 6.0% |
| `cwalts_negative_patterns` — delivery to avoid | negative_pattern | 1 | 1.2% |

84 chunks. `cwalts_evaluation_cases` was an ingested source until **Gate 1**
(v0.4.0-dev.2), where it was removed from production and kept as a non-ingested
regression fixture under `eval/regression/`: an evaluation prompt states its own
pass criterion, so ingesting it let retrieval answer an evaluation query by
returning the query.

No auxiliary class exceeds the 40% cap (Prompt D §D). **cmudict** stays approved
in the manifest but is deliberately un-ingested — it answers "how is this word
stressed", not "make this sound natural". Everything else — Buckeye, Santa
Barbara, Common Voice, LibriSpeech, openSMILE — is `quarantined` with a reason,
and ingestion refuses all of it.

### Media and negative material

Audio, video, and archives are **never committed**. The four approved ElevenLabs
references live under `references/media/positive/` and are identified by SHA-256
in `corpus/raw/evaluation/audio_reference_manifest.yaml`. No audio bytes and no
acoustic vectors enter the text collection; an acoustic sidecar, if ever built,
must use a separate store.

Negative-pattern text lives at `corpus/raw/negative_patterns/`. It moved there
from `corpus/raw/evaluation/negative/` at **Gate 1.1** (v0.4.0-dev.2): the
material was never evaluation material, but a production-ingestible directory
named "evaluation" invited exactly the confusion Gate 1 had to undo. The bytes,
the `source_id`, the licence and the chunk id are unchanged — chunk ids derive
from source and content, not from the path.

Negative-pattern text is retrievable **only** when a request explicitly asks what
to avoid — enforced as a metadata filter
(`exclude_doc_types_by_default: [negative_pattern]`), re-applied after fusion and
after neighbour expansion because BM25 cannot see metadata.

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

## Measured results

`docs/evidence/` carries the raw JSON for all of this.

| Metric | Result |
|---|---|
| Useful hit @5 (EVAL-001…012) | 12/12 (100%) |
| Exact-term retrieval — `ToBI`, `H*`, `L-L%` | PASS (BM25 rank 1) |
| Negative-source contamination | 0 |
| Citation failures | 0 of 60 ranked chunks |
| Preservation controlled cases | 10/10 |
| Latency p50 / p95 | 83 ms / 103 ms |
| Smoke suite | 41/42 → 42/42 after the lint fix |

## Known limitations

1. **No substantive prosody guidance in the corpus.** `ToBI`, `H*`, and `L-L%`
   appear only inside `evaluation_prompts.md`, so retrieval returns the probe
   case rather than a definition. `break index` returns nothing at all. Adding a
   licensed prosody reference is the single highest-value corpus addition; the
   build deliberately did not author one, because only owner-approved material
   may be ingested.
2. **The Hanna theological passage is evaluation-only.** Reconstructed from an
   imperfect automated transcript with unestablished publication provenance. It
   is excluded from the collection and from Git, and must not be treated as an
   authoritative quotation.
3. **Tokenizer is approximate.** `cl100k_base` is GPT tokenization, not
   nomic-bert's. Recorded per chunk so a switch is detectable; caps carry margin.
4. **`rank-bm25` is unmaintained** — pinned at 0.2.2. It sits behind
   `lexical_search.py` so replacing it is a one-file change.
5. **Reranking is interfaced, not implemented.** VRAM does not support a
   cross-encoder alongside the resident embedding model.
6. **`similarity_floor` is `null`, by measurement.** Top-5 distances span
   0.114–0.426 and every result in that band was useful, so no threshold
   separates signal from noise at 48 chunks. Revisit condition is written into
   `config/rag.yaml`.
7. **Corpus size.** 48 chunks is enough to prove the pipeline and to answer
   market-delivery questions; it is not enough to claim broad coverage of English
   flow. Retrieval quality figures should be re-measured as the corpus grows.
8. **`natural_flow_reindex` reports stale chunks but does not delete them.**
   Removal stays an operator action.
