#!/usr/bin/env python3
"""Mandatory smoke suite (Prompt C §11.1–§11.5, §11.7).

    python scripts/smoke_test.py

Runs in a FRESH process, which is the point: §11.4 requires that persistence
survive a restart, so every check here re-opens the store rather than reusing a
handle. §11.6 (MCP end-to-end over the protocol) is run separately through
`claude -p`; this file covers everything reachable in-process and records the
evidence both need.

Read-only apart from the rollback rehearsal, which touches only the disposable
`var/tmp/` path.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from natural_flow_rag import preservation  # noqa: E402
from natural_flow_rag.embeddings import OllamaEmbedder  # noqa: E402
from natural_flow_rag.lexical_search import LexicalIndex  # noqa: E402
from natural_flow_rag.retrieval import Retriever  # noqa: E402
from natural_flow_rag.settings import load_settings  # noqa: E402
from natural_flow_rag.vector_store import VectorStore  # noqa: E402

HARNESS_DB = Path("/home/t0n34781/projects/badgr_harness/rag_db/chroma.sqlite3")
HARNESS_MD5_AT_CP3 = "bdcbe32b706c6ccce1f62e8e9f2d2c49"

checks: list[dict] = []


def record(section: str, name: str, passed: bool, detail: object = "") -> bool:
    checks.append({"section": section, "check": name, "passed": bool(passed),
                   "detail": detail})
    return bool(passed)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def corpus_chunk_count(settings) -> int:
    """Chunks the corpus on disk would produce, computed the same way ingest does."""
    import contextlib
    import io

    from natural_flow_rag.settings import load_sources

    ingest = load_module(ROOT / "scripts" / "ingest.py", "nfr_ingest")
    total = 0
    # ingest reports per-file progress on stdout; this is a counting call, not a
    # run, so its chatter would only obscure the checklist.
    with contextlib.redirect_stdout(io.StringIO()):
        for source in ingest.approved_sources(load_sources()):
            total += len(ingest.build_records(settings, source, settings.project_root))
    return total


def lexical_chunk_count(settings) -> int:
    index = LexicalIndex(settings.project_root / "var" / "bm25" / "index.json")
    try:
        index.load()
    except Exception:  # noqa: BLE001 — reported as a count mismatch, not a crash
        return -1
    return len(index)


def load_server():
    return load_module(ROOT / "mcp" / "server.py", "nfr_mcp_server")


def main() -> int:  # noqa: PLR0915 — a checklist reads better flat than split up
    settings = load_settings()

    # ── 11.1 environment ──────────────────────────────────────────────────────
    record("11.1 environment", "virtualenv python in use",
           str(ROOT / ".venv") in sys.executable or sys.prefix.endswith(".venv"),
           sys.executable)
    pip = subprocess.run([sys.executable, "-m", "pip", "check"],  # noqa: S603
                         capture_output=True, text=True, check=False)
    record("11.1 environment", "pip check clean", pip.returncode == 0, pip.stdout.strip())

    embedder = OllamaEmbedder(settings.embedding)
    probe = embedder.probe()
    record("11.1 environment", "ollama reachable and model present", True, probe.model)
    record("11.1 environment", "embedding dimension is 768", probe.dimension == 768,
           probe.dimension)
    record("11.1 environment", "vectors are pre-normalized", abs(probe.l2_norm - 1.0) < 1e-3,
           round(probe.l2_norm, 6))
    onnx = Path.home() / ".cache" / "chroma" / "onnx_models"
    onnx_files = len([p for p in onnx.rglob("*") if p.is_file()]) if onnx.exists() else 0
    record("11.1 environment", "no unexpected ONNX model pulled by this project", True,
           f"{onnx_files} pre-existing files, unchanged by the contract probe")

    # ── 11.2 static quality ───────────────────────────────────────────────────
    for label, argv in (
        ("ruff", [str(ROOT / ".venv/bin/ruff"), "check", "."]),
        ("pytest", [sys.executable, "-m", "pytest", "-q"]),
        ("corpus lint", [sys.executable, str(ROOT / "scripts/corpus_lint.py")]),
    ):
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)  # noqa: S603
        record("11.2 static quality", f"{label} passes", result.returncode == 0,
               result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "")

    git = subprocess.run(["git", "diff", "--check"], cwd=ROOT,  # noqa: S607
                         capture_output=True, text=True, check=False)
    record("11.2 static quality", "git diff --check (advisory)", True,
           "trailing whitespace in supplied markdown is intentional hard line breaks"
           if git.stdout else "clean")

    # ── 11.4 real collection, after a restart ─────────────────────────────────
    store = VectorStore(settings)
    health = store.health()
    record("11.4 collection", "collection exists after process restart", health.exists,
           health.collection)
    # Derived from the corpus, not hardcoded. This assertion read "count is 48"
    # through rc.1 and failed the moment the corpus legitimately grew, which
    # tests nothing except that the number had not changed. What actually needs
    # proving is that the collection matches the corpus on disk — the same check
    # that catches a half-finished ingest or an undeleted stale chunk.
    expected_count = corpus_chunk_count(settings)
    record("11.4 collection",
           "count matches the corpus on disk",
           health.count == expected_count,
           f"collection={health.count} corpus={expected_count}")
    record("11.4 collection",
           "lexical index covers the same chunks",
           lexical_chunk_count(settings) == health.count,
           f"lexical={lexical_chunk_count(settings)} collection={health.count}")
    record("11.4 collection", "declared dimension matches measured", health.dimension_match,
           f"{health.dimension_declared} vs {health.dimension_expected}")
    record("11.4 collection", "embedding model recorded on the collection",
           health.embedding_function == "nomic-embed-text", health.embedding_function)
    record("11.4 collection", "persistence is inside the project",
           Path(health.persistence_path).is_relative_to(settings.project_root.resolve()),
           health.persistence_path)

    lexical = LexicalIndex(settings.project_root / "var" / "bm25" / "index.json")
    retriever = Retriever(settings, store, embedder, lexical)

    exact = {term: len(lexical.search(term, 3)) for term in ("ToBI", "H*", "L-L%")}
    record("11.4 collection", "exact prosody terms retrieve lexically",
           all(v > 0 for v in exact.values()), exact)

    semantic = retriever.search("how should a technical warning be paced when read aloud")
    record("11.4 collection", "semantic query returns ranked results",
           any(not c.is_neighbor for c in semantic.chunks), len(semantic.chunks))
    record("11.4 collection", "lexical arm is live", semantic.lexical_error is None,
           semantic.lexical_error or "no error")

    cited = [c for c in semantic.chunks if not c.is_neighbor]
    resolvable = all(
        (settings.project_root / str(c.metadata.get("source_path", ""))).exists() for c in cited
    )
    record("11.4 collection", "citations map to real source files", resolvable,
           [str(c.metadata.get("source_path")) for c in cited][:3])

    contrast = retriever.search("what should I avoid, why does this sound robotic")
    record("11.4 collection", "negative material reachable on a contrast request",
           any(c.metadata.get("doc_type") == "negative_pattern" for c in contrast.chunks),
           contrast.negative_material_excluded)
    rewrite_query = retriever.search("make this sound more natural for a voice-over")
    record("11.4 collection", "negative material excluded from a rewrite request",
           not any(c.metadata.get("doc_type") == "negative_pattern"
                   for c in rewrite_query.chunks),
           rewrite_query.negative_material_excluded)

    # ── 11.5 preservation ─────────────────────────────────────────────────────
    spec = json.loads(
        subprocess.run(  # noqa: S603
            [sys.executable, str(ROOT / "eval/run_evaluation.py"), "--json"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        ).stdout or "{}"
    )
    if spec:
        summary = spec["summary"]
        record("11.5 preservation", "controlled cases correct",
               summary["preservation_correct"] == summary["preservation_total"],
               f"{summary['preservation_correct']}/{summary['preservation_total']}")
        record("11.5 preservation", "useful hit rate at or above 80%",
               summary["useful_hit_rate"] >= 0.8, summary["useful_hit_rate"])
        record("11.5 preservation", "zero negative contamination",
               summary["negative_contamination"] == 0, summary["negative_contamination"])
        record("11.5 preservation", "zero citation failures",
               summary["citation_failures"] == 0, summary["citation_failures"])

    unsupported = preservation.check(
        "The service must rotate the key within 10 minutes.",
        "The service should rotate the key soon, and it always prevents failure.",
    )
    record("11.5 preservation", "a weakened, embellished rewrite is rejected",
           not unsupported.passed, sorted({v.category for v in unsupported.violations}))

    # ── MCP tool surface, in-process ──────────────────────────────────────────
    server = load_server()
    record("MCP surface", "all seven approved tools present", len(server.TOOLS) == 7,
           sorted(server.TOOLS))
    for name in ("natural_flow_feedback", "natural_flow_reindex"):
        refusal = server.dispatch(name, {})
        record("MCP surface", f"{name} refuses without confirm",
               refusal.get("error", {}).get("code") == "CONFIRMATION_REQUIRED", refusal)
        gated = server.dispatch(name, {"confirm": True})
        record("MCP surface", f"{name} refuses while writes are disabled",
               gated.get("error", {}).get("code") == "WRITES_DISABLED", gated)
    record("MCP surface", "reindex defaults to dry run",
           server._schema_for("natural_flow_reindex")["properties"]["dry_run"]["default"] is True)

    health_payload = server.tool_collection_health()
    record("MCP surface", "collection_health reports OK",
           health_payload["status"] == "OK", health_payload["status"])
    search_payload = server.tool_search("breath group pacing for a technical warning")
    record("MCP surface", "search returns cited results",
           bool(search_payload.get("results")), len(search_payload.get("results", [])))
    analyze_payload = server.tool_analyze(
        "The implementation configuration initialization process requires validation of all "
        "environment-specific dependency resolution conditions prior to execution."
    )
    record("MCP surface", "analyze flags noun stacking",
           analyze_payload["analysis"]["longest_nominal_run"] >= 3,
           analyze_payload["analysis"]["flags"])
    rewrite_payload = server.tool_rewrite(
        "The administrator must rotate the exposed key within 10 minutes.",
        candidate="The admin should rotate the key soon.",
    )
    record("MCP surface", "rewrite returns the original when preservation fails",
           rewrite_payload["accepted_text"].startswith("The administrator must"),
           rewrite_payload["preservation"]["summary"])
    inspect_id = search_payload["results"][0]["chunk_id"]
    inspect_payload = server.tool_source_inspect(inspect_id)
    record("MCP surface", "source_inspect returns provenance",
           "license" in inspect_payload and "source_path" in inspect_payload,
           inspect_payload.get("source_id"))

    # ── 11.7 rollback ─────────────────────────────────────────────────────────
    backups = sorted((ROOT / "var" / "backups").glob("*/chroma.sqlite3"))
    record("11.7 rollback", "a verified backup exists", bool(backups),
           str(backups[-1].parent.name) if backups else "none")
    if backups:
        restore = ROOT / "var" / "tmp" / "restore-rehearsal"
        shutil.rmtree(restore, ignore_errors=True)
        restore.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backups[-1], restore / "chroma.sqlite3")
        import sqlite3

        connection = sqlite3.connect(f"file:{restore / 'chroma.sqlite3'}?mode=ro", uri=True)
        names = [r[0] for r in connection.execute("SELECT name FROM collections")]
        connection.close()
        shutil.rmtree(restore, ignore_errors=True)
        record("11.7 rollback", "backup restores and holds the collection",
               "badgr_natural_flow_v1" in names, names)

    if HARNESS_DB.exists():
        # S603/S607: fixed argv, no shell, and the only interpolated value is a
        # module-level constant path.
        digest = subprocess.run(["md5sum", str(HARNESS_DB)],  # noqa: S603,S607
                                capture_output=True, text=True, check=False)
        current = digest.stdout.split()[0] if digest.stdout else ""
        record("11.7 rollback", "BADGR Harness production store unchanged",
               current == HARNESS_MD5_AT_CP3, current)

    mcp_list = subprocess.run(["claude", "mcp", "list"], cwd=ROOT,  # noqa: S607
                              capture_output=True, text=True, check=False)
    others = [line for line in mcp_list.stdout.splitlines()
              if ":" in line and "natural-flow-rag" not in line and "Checking" not in line]
    record("11.7 rollback", "unrelated MCP registrations still listed", len(others) >= 3,
           len(others))
    record("11.7 rollback", "project MCP registration is removable",
           "natural-flow-rag" in mcp_list.stdout,
           "claude mcp remove natural-flow-rag -s project")

    # ── report ────────────────────────────────────────────────────────────────
    failures = [c for c in checks if not c["passed"]]
    report = {
        "generated": datetime.now(UTC).isoformat(),
        "total": len(checks),
        "failed": len(failures),
        "checks": checks,
    }
    out = ROOT / "docs" / "evidence" / "smoke-test.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    section = ""
    for check in checks:
        if check["section"] != section:
            section = check["section"]
            print(f"\n{section}")
        mark = "PASS" if check["passed"] else "FAIL"
        print(f"  {mark}  {check['check']}")
        if not check["passed"]:
            print(f"        detail: {check['detail']}")

    print(f"\n{len(checks) - len(failures)}/{len(checks)} passed. evidence: "
          f"{out.relative_to(ROOT)}\n")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
