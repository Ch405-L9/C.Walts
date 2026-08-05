#!/usr/bin/env python3
"""Controlled add-only activation for Gate 1.2 Stage 2 public examples."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from natural_flow_rag.embeddings import OllamaEmbedder  # noqa: E402
from natural_flow_rag.lexical_search import LexicalIndex  # noqa: E402
from natural_flow_rag.schemas import ChunkRecord  # noqa: E402
from natural_flow_rag.settings import (  # noqa: E402
    Settings,
    load_settings,
    load_sources,
)
from natural_flow_rag.vector_store import VectorStore  # noqa: E402
from scripts.compare_reindex_plan import (  # noqa: E402
    canonical_content_digest,
    load_bm25_ids,
    load_current_records,
    relevant_metadata,
)
from scripts.ingest import approved_sources, build_records  # noqa: E402

SCHEMA_VERSION = 1
EXPECTED_BRANCH = "feat/narration-generalization-v0.4"
EXPECTED_VERSION = "0.4.0-dev.3"
EXPECTED_EMBEDDING_MODEL = "nomic-embed-text"
EXPECTED_EMBEDDING_DIGEST = "0a109f422b47"
EXPECTED_EMBEDDING_DIMENSION = 768
JOURNAL_DIR = ROOT / "var" / "stage2_activation" / "journals"
STAGE2_SOURCE_IDS = {
    "labphon-11-ipra",
    "labphon-29-new-methods",
    "labphon-32-introducing-apt",
    "labphon-48-seoul-korean-focus",
    "pmc11592126-silent-reading-rhythm",
    "pmc12452892-prosodic-meaning",
    "pmc12468771-l2-prosody-perception",
    "pmc12641984-ci-auditory-environment",
    "pmc8092678-prosodic-boundaries",
    "pmc9887997-intonational-categories",
}


class ActivationError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git_value(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()  # noqa: S603,S607


def git_clean_tracked() -> tuple[bool, list[str]]:
    status = subprocess.check_output(  # noqa: S603
        ["git", "status", "--porcelain"],  # noqa: S607
        cwd=ROOT,
        text=True,
    )
    dirty = [line for line in status.splitlines() if not line.startswith("?? ")]
    return not dirty, dirty


def version() -> str:
    for line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if line.startswith("version"):
            return line.split("=", 1)[1].strip().strip('"')
    raise ActivationError("pyproject.toml has no version")


def load_expected_ids(args: argparse.Namespace) -> list[str]:
    ids = list(args.expected_new_id or [])
    if args.expected_new_ids_json:
        payload = json.loads(Path(args.expected_new_ids_json).read_text(encoding="utf-8"))
        ids.extend(payload["ids"] if isinstance(payload, dict) else payload)
    return sorted(set(map(str, ids)))


def record_payload(record: ChunkRecord) -> dict[str, Any]:
    return {"id": record.id, "text": record.text, "metadata": record.metadata()}


def build_source_records(
    settings: Settings, manifest_path: Path | None = None
) -> list[dict[str, Any]]:
    manifest = load_sources(manifest_path)
    records: list[dict[str, Any]] = []
    for source in approved_sources(manifest):
        records.extend(record_payload(record) for record in build_records(settings, source, ROOT))
    return sorted(records, key=lambda record: str(record["id"]))


def source_manifest_summary(path: Path) -> dict[str, Any]:
    manifest = load_sources(path)
    approved = [
        source
        for source in manifest.get("sources", []) or []
        if source.get("license_status") == "approved"
    ]
    return {
        "approved_source_count": len(approved),
        "approved_source_ids": sorted(str(source["id"]) for source in approved),
    }


def duplicate_content_groups(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_digest: dict[str, list[str]] = defaultdict(list)
    for record in records:
        by_digest[canonical_content_digest(str(record.get("text", "")))].append(str(record["id"]))
    return {digest: sorted(ids) for digest, ids in sorted(by_digest.items()) if len(set(ids)) > 1}


def semantic_digest(records: list[dict[str, Any]]) -> str:
    payload = []
    for record in records:
        payload.append(
            {
                "id": str(record["id"]),
                "content_digest": canonical_content_digest(str(record.get("text", ""))),
                "metadata": relevant_metadata(record.get("metadata", {}) or {}),
            }
        )
    return sha256_text(json.dumps(sorted(payload, key=lambda row: row["id"]), sort_keys=True))


def id_list_sha256(ids: list[str]) -> str:
    return sha256_text(json.dumps(sorted(ids), indent=2) + "\n")


def build_isolated_bm25(records: list[dict[str, Any]], temp_parent: Path) -> tuple[Path, list[str]]:
    temp_parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix="stage2-bm25-", dir=temp_parent))
    index_path = tmp_dir / "index.json"
    lexical = LexicalIndex(index_path)
    lexical.build(
        [str(record["id"]) for record in records], [str(record["text"]) for record in records]
    )
    lexical.save()
    with index_path.open("rb") as handle:
        os.fsync(handle.fileno())
    reloaded = LexicalIndex(index_path)
    reloaded.load()
    return index_path, sorted(reloaded.chunk_ids)


def atomic_replace_bm25(staged_index: Path, live_index: Path) -> None:
    live_index.parent.mkdir(parents=True, exist_ok=True)
    replacement = live_index.with_name(f".{live_index.name}.stage2-{os.getpid()}")
    shutil.copy2(staged_index, replacement)
    with replacement.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(replacement, live_index)
    try:
        directory_fd = os.open(str(live_index.parent), os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def compare_plan(
    *,
    current_records: list[dict[str, Any]],
    final_records: list[dict[str, Any]],
    current_bm25_ids: list[str],
    proposed_bm25_ids: list[str],
    expected_new_ids: list[str],
) -> dict[str, Any]:
    current_by_id = {str(record["id"]): record for record in current_records}
    final_by_id = {str(record["id"]): record for record in final_records}
    final_id_counts = Counter(str(record["id"]) for record in final_records)
    duplicate_ids = sorted([chunk_id for chunk_id, count in final_id_counts.items() if count > 1])
    would_add = sorted(set(final_by_id) - set(current_by_id))
    stale = sorted(set(current_by_id) - set(final_by_id))
    unchanged: list[str] = []
    content_changed: list[str] = []
    metadata_changed: list[str] = []
    for chunk_id in sorted(set(current_by_id) & set(final_by_id)):
        current = current_by_id[chunk_id]
        final = final_by_id[chunk_id]
        same_content = canonical_content_digest(str(current["text"])) == canonical_content_digest(
            str(final["text"])
        )
        same_metadata = relevant_metadata(current.get("metadata", {}) or {}) == relevant_metadata(
            final.get("metadata", {}) or {}
        )
        if same_content and same_metadata:
            unchanged.append(chunk_id)
        else:
            if not same_content:
                content_changed.append(chunk_id)
            if not same_metadata:
                metadata_changed.append(chunk_id)
    dup_content = duplicate_content_groups(final_records)
    evaluation_ids = sorted(
        str(record["id"])
        for record in final_records
        if str((record.get("metadata") or {}).get("doc_type")) == "evaluation_case"
    )
    final_ids = sorted(final_by_id)
    findings = []
    if set(current_bm25_ids) != set(current_by_id):
        findings.append("current_parity_mismatch")
    if sorted(proposed_bm25_ids) != final_ids:
        findings.append("temporary_bm25_parity_mismatch")
    if would_add != expected_new_ids:
        findings.append("unexpected_would_add_ids")
    if stale:
        findings.append("stale_ids")
    if duplicate_ids:
        findings.append("duplicate_ids")
    if dup_content:
        findings.append("duplicate_canonical_content")
    if content_changed:
        findings.append("existing_document_drift")
    if metadata_changed:
        findings.append("existing_metadata_drift")
    if evaluation_ids:
        findings.append("evaluation_case_leakage")
    return {
        "current_count": len(current_records),
        "final_count": len(final_records),
        "current_ids": sorted(current_by_id),
        "final_ids": final_ids,
        "would_add_ids": would_add,
        "unchanged_ids": unchanged,
        "stale_ids": stale,
        "duplicate_ids": duplicate_ids,
        "duplicate_content_groups": dup_content,
        "content_changed_ids": content_changed,
        "metadata_changed_ids": metadata_changed,
        "evaluation_case_ids": evaluation_ids,
        "current_id_list_sha256": id_list_sha256(sorted(current_by_id)),
        "final_id_list_sha256": id_list_sha256(final_ids),
        "current_semantic_digest": semantic_digest(current_records),
        "final_semantic_digest": semantic_digest(final_records),
        "proposed_chroma_bm25_parity": sorted(proposed_bm25_ids) == final_ids,
        "findings": sorted(set(findings)),
        "verdict": "pass" if not findings else "fail",
    }


def find_incomplete_journals(journal_path: Path | None = None) -> list[Path]:
    candidates = [journal_path] if journal_path else sorted(JOURNAL_DIR.glob("*.json"))
    out = []
    for path in candidates:
        if not path or not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            out.append(path)
            continue
        if payload.get("phase") != "complete":
            out.append(path)
    return out


def update_journal(path: Path, payload: dict[str, Any], phase: str) -> None:
    payload["phase"] = phase
    payload["phase_updated_at"] = utc_now()
    write_json(path, payload)
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def validate_common(
    args: argparse.Namespace,
    *,
    settings: Settings,
    current_records: list[dict[str, Any]],
    current_bm25_ids: list[str],
    final_records: list[dict[str, Any]],
    plan: dict[str, Any],
) -> list[str]:
    findings: list[str] = []
    if git_value(["branch", "--show-current"]) != EXPECTED_BRANCH:
        findings.append("wrong_branch")
    if args.expected_head and git_value(["rev-parse", "HEAD"]) != args.expected_head:
        findings.append("wrong_head")
    if version() != EXPECTED_VERSION:
        findings.append("wrong_version")
    clean, dirty = git_clean_tracked()
    if not clean:
        findings.append(f"dirty_tracked_state:{dirty[:3]}")
    if len(current_records) != args.expected_current_count:
        findings.append("starting_chroma_count_mismatch")
    if len(current_bm25_ids) != args.expected_current_count:
        findings.append("starting_bm25_count_mismatch")
    if set(current_bm25_ids) != {str(record["id"]) for record in current_records}:
        findings.append("starting_parity_mismatch")
    if len(final_records) != args.expected_final_count:
        findings.append("final_record_count_mismatch")
    if plan["verdict"] != "pass":
        findings.extend(plan["findings"])
    summary = source_manifest_summary(ROOT / "config" / "sources.yaml")
    if summary["approved_source_count"] != 15:
        findings.append("approved_source_count_mismatch")
    if not STAGE2_SOURCE_IDS.issubset(set(summary["approved_source_ids"])):
        findings.append("stage2_sources_missing")
    if settings.embedding.model != EXPECTED_EMBEDDING_MODEL:
        findings.append("embedding_model_mismatch")
    if settings.embedding.model_digest != EXPECTED_EMBEDDING_DIGEST:
        findings.append("embedding_digest_mismatch")
    if settings.embedding.vector_dimension != EXPECTED_EMBEDDING_DIMENSION:
        findings.append("embedding_dimension_mismatch")
    if (
        args.expected_b2r1_sha256
        and sha256_file(ROOT / "var/stage2_authoring/stage2_b2r1_review_bundle.zip")
        != args.expected_b2r1_sha256
    ):
        findings.append("b2r1_sha256_mismatch")
    if args.expected_plan:
        expected_plan = json.loads(Path(args.expected_plan).read_text(encoding="utf-8"))
        if sorted(expected_plan.get("would_add_ids", [])) != plan["would_add_ids"]:
            findings.append("expected_plan_would_add_mismatch")
    return sorted(set(findings))


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    settings = load_settings()
    expected_ids = load_expected_ids(args)
    current_records, _ = load_current_records(settings)
    current_bm25_ids = load_bm25_ids(settings)
    final_records = build_source_records(settings)
    temp_index, proposed_bm25_ids = build_isolated_bm25(
        final_records,
        settings.project_root / "var" / "tmp",
    )
    shutil.rmtree(temp_index.parent, ignore_errors=True)
    plan = compare_plan(
        current_records=current_records,
        final_records=final_records,
        current_bm25_ids=current_bm25_ids,
        proposed_bm25_ids=proposed_bm25_ids,
        expected_new_ids=expected_ids,
    )
    findings = validate_common(
        args,
        settings=settings,
        current_records=current_records,
        current_bm25_ids=current_bm25_ids,
        final_records=final_records,
        plan=plan,
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "mode": "preflight",
        "mutation_performed": False,
        "branch": git_value(["branch", "--show-current"]),
        "head": git_value(["rev-parse", "HEAD"]),
        "version": version(),
        "plan": plan,
        "model_contract": {
            "model": settings.embedding.model,
            "model_digest": settings.embedding.model_digest,
            "dimension": settings.embedding.vector_dimension,
        },
        "findings": findings,
        "verdict": "pass" if not findings else "fail",
    }
    return report


def verify_only(args: argparse.Namespace) -> dict[str, Any]:
    settings = load_settings()
    expected_ids = load_expected_ids(args)
    current_records, _ = load_current_records(settings)
    current_bm25_ids = load_bm25_ids(settings)
    final_records = build_source_records(settings)
    new_ids = sorted(set(str(record["id"]) for record in current_records) & set(expected_ids))
    plan = compare_plan(
        current_records=final_records,
        final_records=current_records,
        current_bm25_ids=current_bm25_ids,
        proposed_bm25_ids=current_bm25_ids,
        expected_new_ids=[],
    )
    findings: list[str] = []
    if len(current_records) != args.expected_final_count:
        findings.append("post_chroma_count_mismatch")
    if len(current_bm25_ids) != args.expected_final_count:
        findings.append("post_bm25_count_mismatch")
    if set(current_bm25_ids) != {str(record["id"]) for record in current_records}:
        findings.append("post_parity_mismatch")
    if sorted(expected_ids) != new_ids:
        findings.append("expected_new_ids_absent")
    if plan["content_changed_ids"] or plan["metadata_changed_ids"] or plan["stale_ids"]:
        findings.append("source_equivalence_mismatch")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "mode": "verify-only",
        "mutation_performed": False,
        "current_count": len(current_records),
        "bm25_count": len(current_bm25_ids),
        "exact_parity": set(current_bm25_ids) == {str(record["id"]) for record in current_records},
        "accepted_new_ids_present": new_ids,
        "plan": plan,
        "findings": sorted(set(findings)),
        "verdict": "pass" if not findings else "fail",
    }


def activate(args: argparse.Namespace) -> dict[str, Any]:
    if not args.confirm_stage2_activation:
        raise ActivationError("--confirm-stage2-activation is required for --activate")
    if os.getenv("NFR_ALLOW_WRITES", "").strip().lower() not in {"1", "true", "yes"}:
        raise ActivationError("NFR_ALLOW_WRITES=true is required for --activate")
    if not args.backup_path:
        raise ActivationError("--backup-path is required for --activate")
    if find_incomplete_journals(args.journal_path):
        raise ActivationError("incomplete activation journal exists")

    settings = load_settings()
    expected_ids = load_expected_ids(args)
    current_records, _ = load_current_records(settings)
    current_bm25_ids = load_bm25_ids(settings)
    final_records = build_source_records(settings)
    temp_index, proposed_bm25_ids = build_isolated_bm25(
        final_records,
        settings.project_root / "var" / "bm25",
    )
    plan = compare_plan(
        current_records=current_records,
        final_records=final_records,
        current_bm25_ids=current_bm25_ids,
        proposed_bm25_ids=proposed_bm25_ids,
        expected_new_ids=expected_ids,
    )
    findings = validate_common(
        args,
        settings=settings,
        current_records=current_records,
        current_bm25_ids=current_bm25_ids,
        final_records=final_records,
        plan=plan,
    )
    if findings:
        shutil.rmtree(temp_index.parent, ignore_errors=True)
        raise ActivationError(f"activation preconditions failed: {findings}")

    journal_path = (
        args.journal_path or JOURNAL_DIR / f"stage2-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    )
    journal = {
        "activation_id": journal_path.stem,
        "created_at": utc_now(),
        "branch": git_value(["branch", "--show-current"]),
        "content_commit": git_value(["rev-parse", "HEAD"]),
        "accepted_b2r1_sha256": args.expected_b2r1_sha256,
        "backup_path": str(Path(args.backup_path).resolve()),
        "harness_baseline_path": str(Path(args.harness_baseline).resolve())
        if args.harness_baseline
        else None,
        "starting_chroma_count": len(current_records),
        "starting_bm25_count": len(current_bm25_ids),
        "starting_id_list_sha256": plan["current_id_list_sha256"],
        "starting_semantic_digest": plan["current_semantic_digest"],
        "expected_additions": expected_ids,
    }
    update_journal(journal_path, journal, "pre_write")

    final_by_id = {str(record["id"]): record for record in final_records}
    additions = [final_by_id[chunk_id] for chunk_id in expected_ids]
    update_journal(journal_path, journal, "embeddings_ready")
    embedder = OllamaEmbedder(settings.embedding)
    probe = embedder.probe()
    if probe.dimension != EXPECTED_EMBEDDING_DIMENSION or probe.model != EXPECTED_EMBEDDING_MODEL:
        raise ActivationError("embedding probe mismatch")
    vectors = embedder.embed([str(record["text"]) for record in additions])
    if any(len(vector) != EXPECTED_EMBEDDING_DIMENSION for vector in vectors):
        raise ActivationError("embedding dimension mismatch")

    store = VectorStore(settings)
    before_count = store.count()
    update_journal(journal_path, journal, "chroma_write_started")
    store.add(
        ids=[str(record["id"]) for record in additions],
        embeddings=vectors,
        documents=[str(record["text"]) for record in additions],
        metadatas=[record["metadata"] for record in additions],
    )
    after_count = store.count()
    if before_count != args.expected_current_count or after_count != args.expected_final_count:
        raise ActivationError(f"Chroma count postcondition failed: {before_count}->{after_count}")
    live_records, _ = load_current_records(settings)
    live_by_id = {str(record["id"]): record for record in live_records}
    if not set(expected_ids).issubset(live_by_id):
        raise ActivationError("accepted additions missing from live Chroma")
    for record in current_records:
        live = live_by_id.get(str(record["id"]))
        if live is None:
            raise ActivationError(f"prior id disappeared: {record['id']}")
        if canonical_content_digest(str(record["text"])) != canonical_content_digest(
            str(live["text"])
        ):
            raise ActivationError(f"prior document changed: {record['id']}")
        if relevant_metadata(record.get("metadata", {}) or {}) != relevant_metadata(
            live.get("metadata", {}) or {}
        ):
            raise ActivationError(f"prior metadata changed: {record['id']}")
    update_journal(journal_path, journal, "chroma_write_verified")

    update_journal(journal_path, journal, "bm25_replace_started")
    live_index = settings.project_root / "var" / "bm25" / "index.json"
    atomic_replace_bm25(temp_index, live_index)
    shutil.rmtree(temp_index.parent, ignore_errors=True)
    reloaded = LexicalIndex(live_index)
    reloaded.load()
    if sorted(reloaded.chunk_ids) != sorted(live_by_id):
        raise ActivationError("live BM25/Chroma parity failed after replacement")
    update_journal(journal_path, journal, "bm25_replace_verified")

    update_journal(journal_path, journal, "complete")
    report = verify_only(args)
    report.update(
        {
            "mode": "activate",
            "mutation_performed": True,
            "journal_path": str(journal_path),
            "embedded_text_count": len(additions),
            "chroma_ids_written": expected_ids,
            "bm25_replaced": True,
            "embedding_probe": {
                "model": probe.model,
                "dimension": probe.dimension,
                "normalized": probe.normalized,
                "l2_norm": probe.l2_norm,
            },
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--activate", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    parser.add_argument("--expected-current-count", type=int, default=84)
    parser.add_argument("--expected-final-count", type=int, default=96)
    parser.add_argument("--expected-b2r1-sha256", required=False)
    parser.add_argument("--expected-plan")
    parser.add_argument("--expected-new-id", action="append")
    parser.add_argument("--expected-new-ids-json")
    parser.add_argument("--expected-head")
    parser.add_argument("--backup-path")
    parser.add_argument("--harness-baseline")
    parser.add_argument("--journal-path", type=Path)
    parser.add_argument("--confirm-stage2-activation", action="store_true")
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    try:
        if args.preflight:
            report = preflight(args)
        elif args.verify_only:
            report = verify_only(args)
        else:
            report = activate(args)
    except Exception as exc:  # noqa: BLE001 - command must emit JSON on refusal
        report = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "mode": "activate"
            if args.activate
            else "preflight"
            if args.preflight
            else "verify-only",
            "mutation_performed": False,
            "verdict": "fail",
            "findings": ["command_failed"],
            "error": str(exc),
        }
    output = Path(args.output_json)
    write_json(output, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("verdict") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
