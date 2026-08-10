# Architecture Amendment A4: ChromaDB Security Disposition

`PYSEC-2026-311` is a real vulnerability in `chromadb==1.5.8`; it is not a
false positive, harmless finding, or fixed advisory. No patched stable version
was available in the audited advisory result at disposition time.

For C.Walts v0.4 the disposition is
`mitigated_by_enforced_non_exposure`. The exception is valid only while the
following controls remain mechanically true:

- Chroma uses local `chromadb.PersistentClient` only.
- No HTTP, async/network, FastAPI, WebSocket, SSE, Streamable HTTP, or `chroma run`
  server path is present in supported executable code.
- Collections are opened with the project-controlled embedding function.
- Queries use explicit `query_embeddings`, and writes use explicit `embeddings`.
- User input cannot configure Chroma embedding functions or remote collections.
- Persistence remains inside the project-controlled local path.

The exception is version-specific, is not carried forward automatically, and
must be invalidated if any boundary or package-version assumption changes.
