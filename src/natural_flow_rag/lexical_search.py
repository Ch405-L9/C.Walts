"""BM25 lexical index.

This is the half of retrieval that protects exact notation. Dense embeddings
understand that a passage is *about* intonation; they do not reliably retrieve the
document containing the literal string ``L-L%``. The corpus for this project is
full of such tokens — ``ToBI``, ``H*``, ``L-L%``, ``break index`` — where an
approximate match is a wrong answer.

Tokenization is therefore deliberately notation-preserving: ``*``, ``%``, ``-`` and
case are all significant and are NOT stripped. A conventional
lowercase-and-strip-punctuation tokenizer would erase exactly the tokens this index
exists to protect.

``rank-bm25`` is pinned to 0.2.2 (Apache-2.0, no release since 2022-02-16). It sits
behind this interface so replacing it is a one-file change.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

# Notation-preserving token pattern. Every character class here earns its place
# against real ToBI notation, and the unit tests pin each case:
#
#   H*        pitch accent            L-L%      phrase accent + boundary tone
#   L+H*      bitonal accent          L*+H      a DIFFERENT bitonal accent
#   !H*       downstepped accent      H-        phrase accent (trailing hyphen)
#
# A conventional lowercase-and-strip-punctuation tokenizer destroys all of these,
# which would defeat the entire purpose of running BM25 alongside dense retrieval.
# Leading '!' and trailing '-'/'*'/'%' are therefore all significant.
_TOKEN = re.compile(r"!?[A-Za-z0-9](?:[A-Za-z0-9*%+!./-]*[A-Za-z0-9*%-])?")


class LexicalIndexError(RuntimeError):
    """Index is missing, stale, or unreadable."""


@dataclass
class LexicalHit:
    chunk_id: str
    score: float
    rank: int


def tokenize(text: str) -> list[str]:
    """Notation-preserving tokenizer.

    Emits both the exact-case token and a lowercase form, so ordinary prose still
    matches case-insensitively while ``H*`` and ``L-L%`` survive intact.
    """
    tokens: list[str] = []
    for match in _TOKEN.findall(text):
        tokens.append(match)
        lowered = match.lower()
        if lowered != match:
            tokens.append(lowered)
    return tokens


class LexicalIndex:
    """BM25 over the same chunk set held in the vector store."""

    def __init__(self, path: Path):
        self.path = path
        self.chunk_ids: list[str] = []
        self._tokens: list[list[str]] = []
        self._bm25 = None

    # ── build / persist ───────────────────────────────────────────────────────

    def build(self, chunk_ids: list[str], texts: list[str]) -> None:
        from rank_bm25 import BM25Okapi

        if len(chunk_ids) != len(texts):
            raise LexicalIndexError("build(): chunk_ids and texts length mismatch")
        if not chunk_ids:
            raise LexicalIndexError("build(): refusing to build an empty index")

        self.chunk_ids = list(chunk_ids)
        # Keep the tokenized corpus ourselves. rank_bm25 does NOT retain it — it
        # keeps only doc_freqs and doc_len — so reading it back off the model
        # silently yields nothing, and an index saved that way loads as empty.
        self._tokens = [tokenize(t) for t in texts]
        self._bm25 = BM25Okapi(self._tokens)

    def save(self) -> None:
        """Persist the corpus, not the pickled model.

        Rebuilding BM25 from tokens is fast and avoids pickling a third-party
        object whose format is not guaranteed stable across versions.
        """
        if self._bm25 is None:
            raise LexicalIndexError("save(): nothing built")
        tokens = [list(doc) for doc in self._corpus_tokens]
        if len(tokens) != len(self.chunk_ids) or not any(tokens):
            raise LexicalIndexError(
                f"save(): refusing to write an index with {len(self.chunk_ids)} ids and "
                f"{sum(1 for t in tokens if t)} non-empty token lists. An index saved "
                f"empty loads empty, and retrieval degrades to dense-only in silence."
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "chunk_ids": self.chunk_ids, "tokens": tokens}
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    @property
    def _corpus_tokens(self) -> list[list[str]]:
        if self._bm25 is None:
            raise LexicalIndexError("index not built")
        return self._tokens

    def load(self) -> None:
        from rank_bm25 import BM25Okapi

        if not self.path.is_file():
            raise LexicalIndexError(
                f"lexical index not found at {self.path}; run scripts/ingest.py first"
            )
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.chunk_ids = payload["chunk_ids"]
        tokens = payload["tokens"]
        if not tokens:
            raise LexicalIndexError(
                f"lexical index at {self.path} holds {len(self.chunk_ids)} ids but no "
                f"tokens; rebuild with scripts/ingest.py --commit"
            )
        self._tokens = tokens
        self._bm25 = BM25Okapi(tokens)

    # ── search ────────────────────────────────────────────────────────────────

    def search(self, query: str, k: int) -> list[LexicalHit]:
        if self._bm25 is None:
            self.load()
        scores = self._bm25.get_scores(tokenize(query))
        ordered = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        hits: list[LexicalHit] = []
        for rank, index in enumerate(ordered[: max(1, k)], start=1):
            if scores[index] <= 0:
                break
            hits.append(
                LexicalHit(chunk_id=self.chunk_ids[index], score=float(scores[index]), rank=rank)
            )
        return hits

    def __len__(self) -> int:
        return len(self.chunk_ids)
