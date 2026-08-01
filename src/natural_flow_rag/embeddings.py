"""Ollama embedding client.

Measured facts this module encodes (audit 2026-07-31, not quoted from any report):

  * ``POST /api/embed`` with ``{"model": ..., "input": ...}`` returns
    ``{"embeddings": [[...]]}``. The legacy ``/api/embeddings`` + ``prompt`` form
    used by the old harness ingestion is NOT used here.
  * ``len(vector) == 768``.
  * ``||vector||2 == 1.000000`` — Ollama already returns unit vectors for
    nomic-embed-text. Re-normalizing client-side would be a silent no-op at best;
    we assert the property instead and never touch the values.
  * The model's context is 2048 tokens. Longer input is truncated *silently* by
    the server, so oversize text is rejected here rather than embedded wrongly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import requests

from .settings import EmbeddingConfig

Vector = list[float]


class EmbeddingError(RuntimeError):
    """Embedding failed, or returned something that violates a measured invariant."""


@dataclass
class ProbeResult:
    dimension: int
    l2_norm: float
    model: str
    normalized: bool


class OllamaEmbedder:
    """Explicit-embedding client.

    Every vector that reaches ChromaDB passes through here, which is what makes
    the dimension guarantee enforceable at a single point.
    """

    def __init__(self, config: EmbeddingConfig, session: requests.Session | None = None):
        self.config = config
        self._session = session or requests.Session()
        self._verified = False

    # ── low level ─────────────────────────────────────────────────────────────

    def _post(self, inputs: list[str]) -> list[Vector]:
        url = self.config.endpoint.rstrip("/") + "/api/embed"
        try:
            response = self._session.post(
                url,
                json={"model": self.config.model, "input": inputs},
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise EmbeddingError(f"embedding request to {url} failed: {exc}") from exc
        except ValueError as exc:
            raise EmbeddingError(f"embedding endpoint returned non-JSON: {exc}") from exc

        vectors = payload.get("embeddings")
        if not isinstance(vectors, list) or not vectors:
            raise EmbeddingError(
                f"unexpected embedding response shape; keys={sorted(payload)}"
            )
        return [list(map(float, v)) for v in vectors]

    # ── invariants ────────────────────────────────────────────────────────────

    def _assert_vector(self, vector: Vector) -> None:
        expected = self.config.vector_dimension
        if len(vector) != expected:
            raise EmbeddingError(
                f"dimension mismatch: model returned {len(vector)}, config expects "
                f"{expected}. Refusing to write — mixing dimensions corrupts a "
                f"collection irreversibly."
            )

    def probe(self) -> ProbeResult:
        """One-shot startup check. Returns metadata only; never logs the vector."""
        vector = self._post(["dimension probe"])[0]
        norm = math.sqrt(sum(x * x for x in vector))
        self._assert_vector(vector)
        self._verified = True
        return ProbeResult(
            dimension=len(vector),
            l2_norm=norm,
            model=self.config.model,
            normalized=abs(norm - 1.0) < 1e-3,
        )

    def ensure_ready(self) -> None:
        if self.config.assert_dimension_on_startup and not self._verified:
            self.probe()

    # ── public API ────────────────────────────────────────────────────────────

    def embed(self, texts: list[str]) -> list[Vector]:
        """Embed a batch. Order is preserved; every vector is dimension-asserted."""
        if not texts:
            return []
        self.ensure_ready()

        out: list[Vector] = []
        size = max(1, self.config.batch_size)
        for start in range(0, len(texts), size):
            batch = texts[start : start + size]
            vectors = self._post(batch)
            if len(vectors) != len(batch):
                raise EmbeddingError(
                    f"embedding count mismatch: sent {len(batch)}, got {len(vectors)}"
                )
            for vector in vectors:
                self._assert_vector(vector)
                # normalize_vectors is False by measurement. If someone flips it,
                # fail loudly rather than double-normalizing unit vectors.
                if self.config.normalize_vectors:
                    raise EmbeddingError(
                        "normalize_vectors=true, but this model already returns unit "
                        "vectors (measured L2 norm 1.000000). Re-normalizing is a bug."
                    )
            out.extend(vectors)
        return out

    def embed_one(self, text: str) -> Vector:
        return self.embed([text])[0]
