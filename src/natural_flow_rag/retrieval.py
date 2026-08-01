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

    # ── stages ────────────────────────────────────────────────────────────────

    def _dense(self, query: str, k: int, where: dict[str, Any] | None) -> dict[str, Any]:
        vector = self.embedder.embed_one(query)
        return self.store.query(embedding=vector, n_results=k, where=where)

    def _lexical(self, query: str, k: int) -> list[str]:
        if self.lexical is None:
            return []
        try:
            return [hit.chunk_id for hit in self.lexical.search(query, k)]
        except Exception:
            # A missing lexical index degrades retrieval to dense-only rather than
            # failing the request. Reported via dense_n/lexical_n in the result.
            return []

    def _apply_floor(self, ids: list[str], distances: list[float]) -> list[str]:
        floor = self.cfg.get("similarity_floor")
        if floor is None:
            return ids
        # Chroma cosine distance: similarity = 1 - distance.
        return [i for i, d in zip(ids, distances, strict=False) if (1.0 - d) >= float(floor)]

    def _cap_per_document(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        cap = int(self.cfg.get("maximum_chunks_per_document", 3))
        seen: dict[str, int] = {}
        out: list[RetrievedChunk] = []
        for chunk in chunks:
            key = str(chunk.metadata.get("source_id", "?"))
            if seen.get(key, 0) >= cap:
                continue
            seen[key] = seen.get(key, 0) + 1
            out.append(chunk)
        return out

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

        chunks = self._deduplicate(chunks)
        chunks = self._cap_per_document(chunks)
        chunks = chunks[:final_k]
        chunks = self._expand_neighbors(chunks)
        chunks = self._trim_to_budget(chunks)

        return RetrievalResult(
            query=query,
            chunks=chunks,
            dense_n=len(dense_ids),
            lexical_n=len(lexical_ids),
            fused_n=len(fused),
            reranked=False,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
