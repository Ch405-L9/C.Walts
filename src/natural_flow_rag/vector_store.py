"""ChromaDB access, with the audit's B2 hazard designed out.

Background (audit finding E17): the production collections `badgr_corpus` and
`job_opportunities` hold 768-dimension vectors but record Chroma's *default*
embedding function in `collections.schema_str`. That happened because they were
created with `get_or_create_collection(name=...)` and no `embedding_function`
argument — and Chroma's signature defaults that parameter to
`DefaultEmbeddingFunction()` (384-d, MiniLM class). Any later caller using
Chroma's text-based query API would invoke a 384-d embedder against a 768-d index.

Two defences, applied together:

  1. Collections here are created with an explicit `OllamaEmbeddingFunction`
     carrying the real model name. Chroma serializes it via `get_config()`, so the
     stored schema records `nomic-embed-text` rather than "default". That class
     also refuses model changes after creation, which enforces
     `forbid_mixed_models` at the library level.
  2. Runtime always passes explicit vectors. Chroma's text-based query API is
     never used, so the recorded function is metadata and provenance, never a
     hot path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .settings import ConfigError, Settings

_MISSING = object()


class VectorStoreError(RuntimeError):
    """Vector store is unavailable, or an invariant was violated."""


@dataclass
class HealthReport:
    collection: str
    exists: bool
    count: int | None
    dimension_declared: int | None
    dimension_expected: int
    dimension_match: bool | None
    embedding_function: str | None
    space: str
    persistence_path: str
    status: str


class VectorStore:
    """Thin, deliberately narrow wrapper over a Chroma PersistentClient."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.path = settings.resolve_inside_project(
            settings.collection.persistence_path
        )
        self._client: Any = None

    # ── client ────────────────────────────────────────────────────────────────

    def _embedding_function(self) -> Any:
        from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

        cfg = self.settings.embedding
        return OllamaEmbeddingFunction(
            url=cfg.endpoint,
            model_name=cfg.model,
            timeout=cfg.timeout_seconds,
        )

    @property
    def client(self) -> Any:
        if self._client is None:
            import chromadb

            # Re-assert containment at connect time, not just at config load.
            self.settings.resolve_inside_project(self.path)
            self.path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self.path))
        return self._client

    # ── collections ───────────────────────────────────────────────────────────

    def _resolve_name(self, name: str | None) -> str:
        target = name or self.settings.collection.name
        return self.settings.collection.assert_allowed(target)

    def exists(self, name: str | None = None) -> bool:
        target = self._resolve_name(name)
        return any(c.name == target for c in self.client.list_collections())

    def get(self, name: str | None = None) -> Any:
        """Open an existing collection. Never creates."""
        target = self._resolve_name(name)
        if not self.exists(target):
            raise VectorStoreError(
                f"collection {target!r} does not exist at {self.path}. "
                f"Creation is a Gate 3 operation; run scripts/ingest.py --commit."
            )
        return self.client.get_collection(
            name=target, embedding_function=self._embedding_function()
        )

    def create(self, name: str | None = None) -> Any:
        """Create a collection. Write-gated.

        Guarded so that an accidental invocation cannot silently produce a second
        collection with a mismatched embedding contract.
        """
        target = self._resolve_name(name)
        self.settings.assert_writes_allowed(f"create_collection({target})")
        self.settings.assert_disk_headroom()

        if self.exists(target):
            raise VectorStoreError(
                f"collection {target!r} already exists — refusing to recreate. "
                f"Use scripts/rebuild.py if a rebuild is genuinely intended."
            )

        cfg = self.settings.embedding
        return self.client.create_collection(
            name=target,
            embedding_function=self._embedding_function(),
            configuration={"hnsw": {"space": self.settings.collection.space}},
            metadata={
                # Recorded so the collection self-identifies. The production
                # collections could not, which is the whole reason for this module.
                "embedding_model": cfg.model,
                "embedding_model_tag": cfg.model_tag,
                "embedding_model_digest": cfg.model_digest,
                "embedding_dimension": cfg.vector_dimension,
                "vectors_prenormalized": True,
                "created_by": "natural-language-flow-rag",
            },
        )

    # ── reads ─────────────────────────────────────────────────────────────────

    def query(
        self,
        embedding: list[float],
        n_results: int,
        where: dict[str, Any] | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Dense search by EXPLICIT vector; text-based queries are refused."""
        if len(embedding) != self.settings.embedding.vector_dimension:
            raise VectorStoreError(
                f"refusing to query with a {len(embedding)}-d vector against a "
                f"{self.settings.embedding.vector_dimension}-d collection"
            )
        collection = self.get(name)
        return collection.query(
            query_embeddings=[embedding],
            n_results=max(1, n_results),
            where=where or None,
            include=["documents", "metadatas", "distances"],
        )

    def fetch(self, ids: list[str], name: str | None = None) -> dict[str, Any]:
        if not ids:
            return {"ids": [], "documents": [], "metadatas": []}
        return self.get(name).get(ids=ids, include=["documents", "metadatas"])

    def count(self, name: str | None = None) -> int:
        return self.get(name).count()

    # ── writes ────────────────────────────────────────────────────────────────

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
        name: str | None = None,
    ) -> None:
        target = self._resolve_name(name)
        self.settings.assert_writes_allowed(f"add({target})")
        self.settings.assert_disk_headroom()

        if not (len(ids) == len(embeddings) == len(documents) == len(metadatas)):
            raise VectorStoreError("add(): ids/embeddings/documents/metadatas length mismatch")

        expected = self.settings.embedding.vector_dimension
        for index, vector in enumerate(embeddings):
            if len(vector) != expected:
                raise VectorStoreError(
                    f"add(): vector {index} has dimension {len(vector)}, expected {expected}"
                )

        self.get(target).upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )

    def delete(self, ids: list[str], name: str | None = None) -> list[str]:
        """Remove chunks by id. Write-gated, allowlisted, and never open-ended.

        The only destructive operation in this module, so it is deliberately the
        narrowest. Three refusals, each closing a way this could remove more than
        the caller meant:

          * an empty id list is refused rather than treated as a no-op, because
            `delete()` with no argument is Chroma's "delete everything" spelling
            and a caller that computed an empty stale set should not be one typo
            away from it;
          * ids not present in the collection are refused, so a mistyped or
            stale-by-a-run id set cannot partially apply;
          * the collection name goes through the same allowlist as every other
            operation, so the production stores stay unnameable.

        Returns the ids actually removed, confirmed by re-reading the collection
        rather than by trusting the call to have worked.
        """
        target = self._resolve_name(name)
        self.settings.assert_writes_allowed(f"delete({target})")

        if not ids:
            raise VectorStoreError(
                "delete(): refusing an empty id list. Chroma treats a missing id "
                "argument as 'delete the whole collection'; an empty stale set "
                "means there is nothing to do, so say so rather than calling."
            )

        unique = list(dict.fromkeys(ids))
        collection = self.get(target)
        present = set(collection.get(ids=unique, include=[])["ids"])
        missing = [i for i in unique if i not in present]
        if missing:
            raise VectorStoreError(
                f"delete(): {len(missing)} of {len(unique)} ids are not in "
                f"{target!r} (first: {missing[:3]}). Refusing a partial delete — "
                f"recompute the stale set against the current collection."
            )

        collection.delete(ids=unique)

        still_there = set(collection.get(ids=unique, include=[])["ids"])
        if still_there:
            raise VectorStoreError(
                f"delete(): {len(still_there)} ids survived the delete in {target!r}. "
                f"The collection is in an unexpected state; restore from backup."
            )
        return unique

    # ── health ────────────────────────────────────────────────────────────────

    def health(self, name: str | None = None) -> HealthReport:
        """Operational truth. Answers audit hazards B2 and R01 directly."""
        target = self._resolve_name(name)
        expected = self.settings.embedding.vector_dimension

        if not self.exists(target):
            return HealthReport(
                collection=target,
                exists=False,
                count=None,
                dimension_declared=None,
                dimension_expected=expected,
                dimension_match=None,
                embedding_function=None,
                space=self.settings.collection.space,
                persistence_path=str(self.path),
                status="NOT_CREATED",
            )

        collection = self.get(target)
        metadata = collection.metadata or {}
        declared = metadata.get("embedding_dimension")
        declared_int = int(declared) if declared is not None else None
        match = (declared_int == expected) if declared_int is not None else None

        return HealthReport(
            collection=target,
            exists=True,
            count=collection.count(),
            dimension_declared=declared_int,
            dimension_expected=expected,
            dimension_match=match,
            embedding_function=metadata.get("embedding_model"),
            space=self.settings.collection.space,
            persistence_path=str(self.path),
            status="OK" if match else "DEGRADED",
        )


def open_store(settings: Settings | None = None) -> VectorStore:
    from .settings import load_settings

    return VectorStore(settings or load_settings())


__all__ = ["VectorStore", "VectorStoreError", "HealthReport", "open_store", "ConfigError"]
