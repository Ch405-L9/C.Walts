# C.Walts v0.4 Gate 0
## Dataset acquisition, license verification, and inventory only

This package is the next bounded step after `v0.3.0-rc.2`.

It does **not** build the final 600-query evaluation set. It safely acquires and inventories the three approved public datasets so the final selection rules can be based on actual records rather than assumptions.

## Owner action

You do not need to download or manually prepare any dataset.

Copy or extract this package into:

```text
/home/t0n34781/projects/natural-language-flow-rag/
```

Then start Claude Code from that project and give it:

```text
Read README_START_HERE_C.Walts_v0.4_Gate0.md and execute
prompts/PF_C.Walts_v0.4_Gate0_dataset-acquisition.md exactly.

Do not modify the production collection. Stop after the Gate 0 report.
```

## What this phase does

1. Verifies that `v0.3.0-rc.2` is intact.
2. Creates `feat/narration-generalization-v0.4`.
3. Sets the development version to `0.4.0-dev.1`.
4. Runs a no-network dry run of the acquisition tool.
5. Downloads only:
   - CLINC150;
   - MASSIVE 1.0;
   - Banking77.
6. Extracts only allowlisted files.
7. Verifies embedded license markers.
8. Calculates SHA-256 hashes.
9. Produces an inventory and source manifest.
10. Runs unit tests, Ruff, existing RC2 tests, adversarial extraction tests, smoke tests, and fresh-session MCP tests.
11. Commits and pushes each logical checkpoint.
12. Stops before query selection, final splitting, threshold fitting, or Chroma/BM25 modification.

## What this phase does not do

- It does not download LibriSpeech, LibriTTS, LibriTTS-R, or audiobook audio.
- It does not create 600 prompts.
- It does not chunk any dataset.
- It does not embed evaluation queries.
- It does not ingest evaluation material into ChromaDB or BM25.
- It does not tune similarity thresholds.
- It does not change `badgr_natural_flow_v1`.
- It does not promote `main`.

## Critical terminology

The downloaded records are **evaluation-query candidates**.

Each selected query will later remain one atomic JSONL record. Evaluation queries are not corpus chunks and must never be indexed as production knowledge.
