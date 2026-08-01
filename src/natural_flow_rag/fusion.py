"""Reciprocal-rank fusion.

RRF combines ranked lists without needing their scores to be comparable — which
matters here because cosine distance and BM25 relevance are on unrelated scales
and normalizing them against each other would be arbitrary.

    score(d) = sum over lists of  1 / (k + rank(d))

``k`` damps the influence of top positions; 60 is the conventional value and is
what the audit baseline specifies. Deterministic and dependency-free, so it is
exhaustively unit-testable against a hand-computed fixture.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FusedHit:
    chunk_id: str
    score: float
    rank: int
    dense_rank: int | None = None
    lexical_rank: int | None = None

    @property
    def found_by(self) -> str:
        if self.dense_rank is not None and self.lexical_rank is not None:
            return "both"
        if self.dense_rank is not None:
            return "dense"
        return "lexical"


def reciprocal_rank_fusion(
    dense_ids: list[str],
    lexical_ids: list[str],
    *,
    rrf_k: int = 60,
    limit: int | None = None,
) -> list[FusedHit]:
    """Fuse two ranked id lists. Inputs are ordered best-first."""
    if rrf_k <= 0:
        raise ValueError("rrf_k must be positive")

    dense_rank = {cid: i for i, cid in enumerate(dense_ids, start=1)}
    lexical_rank = {cid: i for i, cid in enumerate(lexical_ids, start=1)}

    scores: dict[str, float] = {}
    for rank_map in (dense_rank, lexical_rank):
        for chunk_id, rank in rank_map.items():
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)

    # Sort by score, then by best available rank, then by id — fully deterministic.
    def sort_key(chunk_id: str) -> tuple[float, int, str]:
        best = min(
            dense_rank.get(chunk_id, 10**9),
            lexical_rank.get(chunk_id, 10**9),
        )
        return (-scores[chunk_id], best, chunk_id)

    ordered = sorted(scores, key=sort_key)
    if limit is not None:
        ordered = ordered[:limit]

    return [
        FusedHit(
            chunk_id=chunk_id,
            score=scores[chunk_id],
            rank=position,
            dense_rank=dense_rank.get(chunk_id),
            lexical_rank=lexical_rank.get(chunk_id),
        )
        for position, chunk_id in enumerate(ordered, start=1)
    ]
