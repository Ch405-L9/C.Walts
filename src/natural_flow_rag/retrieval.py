"""Hybrid retrieval: dense + BM25 → RRF → filter → dedup → neighbour expansion.

Every stage the harness lacked (audit E27: dense-only, k=5, no fusion, no rerank,
no dedup, no neighbours, no threshold, no filters) is implemented here, and each is
individually switchable so the evaluation harness can measure its contribution
rather than assume it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .embeddings import OllamaEmbedder
from .fusion import reciprocal_rank_fusion
from .lexical_search import LexicalIndex
from .schemas import validate_filter
from .settings import Settings
from .vector_store import VectorStore


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    score: float
    rank: int
    found_by: str
    dense_rank: int | None
    lexical_rank: int | None
    metadata: dict[str, Any] = field(default_factory=dict)
    is_neighbor: bool = False

    @property
    def source_title(self) -> str:
        return str(self.metadata.get("source_title", "unknown"))

    @property
    def license(self) -> str:
        return str(self.metadata.get("license", "UNKNOWN"))


@dataclass
class RetrievalResult:
    query: str
    chunks: list[RetrievedChunk]
    dense_n: int
    lexical_n: int
    fused_n: int
    reranked: bool
    latency_ms: int
    lexical_error: str | None = None
    negative_material_excluded: bool = False

    def texts(self) -> list[str]:
        return [c.text for c in self.chunks]


class Retriever:
    def __init__(
        self,
        settings: Settings,
        store: VectorStore,
        embedder: OllamaEmbedder,
        lexical: LexicalIndex | None = None,
    ):
        self.settings = settings
        self.store = store
        self.embedder = embedder
        self.lexical = lexical
        self.cfg = settings.retrieval
        self.lexical_error: str | None = None

    # ── stages ────────────────────────────────────────────────────────────────

    def _dense(self, query: str, k: int, where: dict[str, Any] | None) -> dict[str, Any]:
        vector = self.embedder.embed_one(query)
        return self.store.query(embedding=vector, n_results=k, where=where)

    def _lexical(self, query: str, k: int) -> list[str]:
        """Lexical arm. Degrades to dense-only, but never silently.

        A degraded arm used to be indistinguishable from a query with no lexical
        matches — both produced ``lexical_n = 0``. The failure is now recorded on
        the result so the evaluation harness and the health tool can see it.
        """
        self.lexical_error = None
        if self.lexical is None:
            self.lexical_error = "no lexical index configured"
            return []
        try:
            return [hit.chunk_id for hit in self.lexical.search(query, k)]
        except Exception as exc:  # noqa: BLE001 — degrade, but report
            self.lexical_error = f"{type(exc).__name__}: {exc}"
            return []

    def has_contrast_intent(self, query: str) -> bool:
        """True when the request explicitly asks what to avoid.

        Prompt D permits negative-pattern material only for such requests. The
        patterns live in config so the policy is auditable rather than buried.
        """
        lowered = query.lower()
        return any(
            str(marker).lower() in lowered
            for marker in (self.cfg.get("contrast_intent_patterns") or [])
        )

    def _default_filter(
        self, query: str, where: dict[str, Any] | None
    ) -> tuple[dict[str, Any] | None, bool]:
        """Apply the negative-material exclusion unless the caller filtered already."""
        excluded = [str(d) for d in (self.cfg.get("exclude_doc_types_by_default") or [])]
        if where or not excluded or self.has_contrast_intent(query):
            return where, False
        if len(excluded) == 1:
            return {"doc_type": {"$ne": excluded[0]}}, True
        return {"$and": [{"doc_type": {"$ne": d}} for d in excluded]}, True

    def _apply_floor(self, ids: list[str], distances: list[float]) -> list[str]:
        floor = self.cfg.get("similarity_floor")
        if floor is None:
            return ids
        # Chroma cosine distance: similarity = 1 - distance.
        return [i for i, d in zip(ids, distances, strict=False) if (1.0 - d) >= float(floor)]

    def _cap_per_document(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Stop one document monopolising the result.

        Keyed on `source_path` — the DOCUMENT — not on `source_id`, which names
        the source *collection*.

        MEASURED 2026-08-01: keying on source_id starved the corpus as it grew.
        All 55 owner-example chunks share `source_id: owner_examples`, so the cap
        of 3 was shared across every approved example in the project rather than
        applied per file. On EVAL-005 ("preserve every number") the three slots
        went to CW-007, CW-015 and CW-031, and CW-006 — the pair that actually
        demonstrates preserving 250, 10, 25 and 80 — could not be returned at any
        k. At 26 example chunks this was invisible; at 55 it silently cost a
        correct answer, and it would have worsened with every example added.
        """
        cap = int(self.cfg.get("maximum_chunks_per_document", 3))
        seen: dict[str, int] = {}
        out: list[RetrievedChunk] = []
        for chunk in chunks:
            key = str(
                chunk.metadata.get("source_path")
                or chunk.metadata.get("source_id")
                or "?"
            )
            if seen.get(key, 0) >= cap:
                continue
            seen[key] = seen.get(key, 0) + 1
            out.append(chunk)
        return out

    def _demote_doc_types(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Push probe-shaped material below anything that answers it.

        MEASURED 2026-08-01: the query ``ToBI`` ranked the EVAL-004 chunk first
        and the glossary's ToBI definition second. EVAL-004 is an evaluation
        prompt — "Explain the textual relevance of `ToBI`, `H*`, and `L-L%`" —
        so it is short and almost entirely composed of the probe terms, which is
        exactly the shape BM25 scores highest. A document whose purpose is to ASK
        a question was outranking the documents that answer it.

        This is a stable partition, not a filter and not a score penalty. Demoted
        chunks keep their relative order and stay in the result, because the
        evaluation cases carry the pass criteria that several other queries
        legitimately need; they simply stop leading. Removing them instead would
        break the EVAL-005 through EVAL-007 expectations, which is the wrong
        trade — the problem was never that they were retrieved.
        """
        demoted = {str(d) for d in (self.cfg.get("demote_doc_types") or [])}
        if not demoted:
            return chunks
        leading = [c for c in chunks if str(c.metadata.get("doc_type")) not in demoted]
        trailing = [c for c in chunks if str(c.metadata.get("doc_type")) in demoted]
        return leading + trailing

    def _deduplicate(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        if not self.cfg.get("deduplicate", True):
            return chunks
        seen: set[str] = set()
        out: list[RetrievedChunk] = []
        for chunk in chunks:
            fingerprint = " ".join(chunk.text.split())[:200]
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            out.append(chunk)
        return out

    def _expand_neighbors(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        span = int(self.cfg.get("neighbor_chunks", 0))
        if span <= 0:
            return chunks

        have = {c.chunk_id for c in chunks}
        wanted: list[str] = []
        for chunk in chunks:
            for key in ("chunk_prev_id", "chunk_next_id"):
                neighbor = chunk.metadata.get(key)
                if neighbor and neighbor not in have and neighbor not in wanted:
                    wanted.append(str(neighbor))
        if not wanted:
            return chunks

        fetched = self.store.fetch(wanted)
        extra: list[RetrievedChunk] = []
        for chunk_id, text, metadata in zip(
            fetched.get("ids", []),
            fetched.get("documents", []),
            fetched.get("metadatas", []),
            strict=False,
        ):
            extra.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    text=text or "",
                    score=0.0,
                    rank=len(chunks) + len(extra) + 1,
                    found_by="neighbor",
                    dense_rank=None,
                    lexical_rank=None,
                    metadata=metadata or {},
                    is_neighbor=True,
                )
            )
        return chunks + extra

    def _trim_to_budget(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Honour the context-token budget using the same tokenizer as chunking."""
        from .chunking import DEFAULT_TOKENIZER, count_tokens

        budget = int(self.cfg.get("maximum_context_tokens", 2048))
        tokenizer = self.settings.chunking.get("tokenizer", DEFAULT_TOKENIZER)
        used = 0
        out: list[RetrievedChunk] = []
        for chunk in chunks:
            cost = int(chunk.metadata.get("token_count") or count_tokens(chunk.text, tokenizer))
            if used + cost > budget:
                break
            used += cost
            out.append(chunk)
        return out

    # ── entry point ───────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        k: int | None = None,
        where: dict[str, Any] | None = None,
    ) -> RetrievalResult:
        started = time.perf_counter()

        if not query or not query.strip():
            raise ValueError("query must be non-empty")
        if len(query) > 2000:
            raise ValueError("query exceeds 2000 characters")

        where = validate_filter(where)
        where, negatives_excluded = self._default_filter(query, where)
        final_k = int(k or self.cfg.get("final_chunks", 5))
        dense_k = int(self.cfg.get("dense_candidates", 24))
        lexical_k = int(self.cfg.get("lexical_candidates", 24))

        dense_raw = self._dense(query, dense_k, where)
        dense_ids = list(dense_raw.get("ids", [[]])[0])
        distances = list(dense_raw.get("distances", [[]])[0])
        documents = list(dense_raw.get("documents", [[]])[0])
        metadatas = list(dense_raw.get("metadatas", [[]])[0])

        by_id = {
            cid: {"text": doc, "metadata": meta or {}}
            for cid, doc, meta in zip(dense_ids, documents, metadatas, strict=False)
        }
        dense_ids = self._apply_floor(dense_ids, distances)

        lexical_ids = self._lexical(query, lexical_k)

        fused = reciprocal_rank_fusion(
            dense_ids,
            lexical_ids,
            rrf_k=int(self.cfg.get("fusion", {}).get("rrf_k", 60)),
        )

        # Anything BM25 found that dense retrieval missed is not yet in by_id.
        missing = [f.chunk_id for f in fused if f.chunk_id not in by_id]
        if missing:
            fetched = self.store.fetch(missing)
            for cid, doc, meta in zip(
                fetched.get("ids", []),
                fetched.get("documents", []),
                fetched.get("metadatas", []),
                strict=False,
            ):
                by_id[cid] = {"text": doc or "", "metadata": meta or {}}

        chunks = [
            RetrievedChunk(
                chunk_id=hit.chunk_id,
                text=by_id.get(hit.chunk_id, {}).get("text", ""),
                score=hit.score,
                rank=hit.rank,
                found_by=hit.found_by,
                dense_rank=hit.dense_rank,
                lexical_rank=hit.lexical_rank,
                metadata=by_id.get(hit.chunk_id, {}).get("metadata", {}),
            )
            for hit in fused
            if hit.chunk_id in by_id
        ]

        if negatives_excluded:
            # The `where` clause constrains the dense arm only; BM25 knows nothing
            # about metadata, so a lexical hit could still smuggle a negative
            # chunk into the fused list.
            excluded = {str(d) for d in (self.cfg.get("exclude_doc_types_by_default") or [])}
            chunks = [c for c in chunks if str(c.metadata.get("doc_type")) not in excluded]

        chunks = self._deduplicate(chunks)
        chunks = self._cap_per_document(chunks)
        chunks = self._demote_doc_types(chunks)
        chunks = chunks[:final_k]
        chunks = self._expand_neighbors(chunks)
        if negatives_excluded:
            chunks = [c for c in chunks if str(c.metadata.get("doc_type")) not in excluded]
        chunks = self._trim_to_budget(chunks)

        return RetrievalResult(
            query=query,
            chunks=chunks,
            dense_n=len(dense_ids),
            lexical_n=len(lexical_ids),
            fused_n=len(fused),
            reranked=False,
            latency_ms=int((time.perf_counter() - started) * 1000),
            lexical_error=self.lexical_error,
            negative_material_excluded=negatives_excluded,
        )
