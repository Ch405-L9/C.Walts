#!/usr/bin/env python3
"""Wrapper for the Stage 2.3 write window.

The wrapper keeps the write-capable activation process isolated from rollback
handling. If activation or the immediate Harness postcheck fails, this process
restores the C.Walts stores from the fresh pre-activation backup.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from natural_flow_rag.settings import load_settings  # noqa: E402
from scripts.activate_stage2 import (  # noqa: E402
    EXPECTED_BRANCH,
    id_list_sha256,
    load_expected_ids,
    semantic_digest,
    write_json,
)
from scripts.compare_reindex_plan import load_bm25_ids, load_current_records  # noqa: E402

HARNESS_DB = Path("/home/t0n34781/projects/badgr_harness/rag_db/chroma.sqlite3")


class WrapperError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def run_command(
    argv: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path = ROOT,
    output_stdout: Path | None = None,
    output_stderr: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(  # noqa: S603
        argv,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if output_stdout is not None:
        output_stdout.parent.mkdir(parents=True, exist_ok=True)
        output_stdout.write_text(result.stdout, encoding="utf-8")
    if output_stderr is not None:
        output_stderr.parent.mkdir(parents=True, exist_ok=True)
        output_stderr.write_text(result.stderr, encoding="utf-8")
    return result


def verify_backup(backup_path: Path) -> dict[str, Any]:
    required = [
        backup_path / "chroma" / "chroma.sqlite3",
        backup_path / "bm25.index.json",
        backup_path / "sources.yaml",
        backup_path / "NOTICE",
        backup_path / "rag.yaml",
        backup_path / "backup_manifest.json",
        backup_path / "SHA256SUMS",
    ]
    missing = [str(path) for path in required if not path.exists()]
    checksum = run_command(["sha256sum", "-c", "SHA256SUMS"], cwd=backup_path)
    return {
        "backup_path": str(backup_path),
        "missing": missing,
        "checksum_exit_code": checksum.returncode,
        "checksum_stdout": checksum.stdout,
        "checksum_stderr": checksum.stderr,
        "verdict": "pass" if not missing and checksum.returncode == 0 else "fail",
    }


def restore_from_backup(backup_path: Path) -> dict[str, Any]:
    settings = load_settings()
    chroma_target = settings.chroma.path
    bm25_target = settings.project_root / "var" / "bm25" / "index.json"
    if not (backup_path / "chroma").is_dir():
        raise WrapperError(f"backup Chroma directory missing: {backup_path / 'chroma'}")
    if not (backup_path / "bm25.index.json").is_file():
        raise WrapperError(f"backup BM25 index missing: {backup_path / 'bm25.index.json'}")
    shutil.rmtree(chroma_target, ignore_errors=True)
    shutil.copytree(backup_path / "chroma", chroma_target)
    bm25_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path / "bm25.index.json", bm25_target)
    current_records, _ = load_current_records(settings)
    bm25_ids = load_bm25_ids(settings)
    return {
        "restored_chroma_count": len(current_records),
        "restored_bm25_count": len(bm25_ids),
        "restored_exact_parity": sorted(record["id"] for record in current_records)
        == sorted(bm25_ids),
        "restored_id_list_sha256": id_list_sha256(
            [str(record["id"]) for record in current_records]
        ),
        "restored_semantic_digest": semantic_digest(current_records),
    }


def verify_restored_state(
    backup_path: Path,
    *,
    expected_current_count: int,
    expected_id_list_sha256: str | None,
    expected_semantic_digest: str | None,
) -> dict[str, Any]:
    restored = restore_from_backup(backup_path)
    findings: list[str] = []
    if restored["restored_chroma_count"] != expected_current_count:
        findings.append("restored_chroma_count_mismatch")
    if restored["restored_bm25_count"] != expected_current_count:
        findings.append("restored_bm25_count_mismatch")
    if not restored["restored_exact_parity"]:
        findings.append("restored_parity_mismatch")
    if expected_id_list_sha256 and restored["restored_id_list_sha256"] != expected_id_list_sha256:
        findings.append("restored_id_list_hash_mismatch")
    if (
        expected_semantic_digest
        and restored["restored_semantic_digest"] != expected_semantic_digest
    ):
        findings.append("restored_semantic_digest_mismatch")
    restored["findings"] = findings
    restored["verdict"] = "pass" if not findings else "fail"
    return restored


def capture_harness_baseline(output: Path) -> subprocess.CompletedProcess[str]:
    return run_command(
        [
            sys.executable,
            str(ROOT / "scripts" / "harness_invariant.py"),
            "capture",
            "--database",
            str(HARNESS_DB),
            "--require-quiescent",
            "--output",
            str(output),
        ]
    )


def verify_harness_baseline(baseline: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return run_command(
        [
            sys.executable,
            str(ROOT / "scripts" / "harness_invariant.py"),
            "verify",
            "--database",
            str(HARNESS_DB),
            "--baseline",
            str(baseline),
            "--require-quiescent",
            "--output",
            str(output),
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-path", required=True, type=Path)
    parser.add_argument("--harness-baseline", required=True, type=Path)
    parser.add_argument("--harness-postcheck", required=True, type=Path)
    parser.add_argument("--expected-current-count", type=int, required=True)
    parser.add_argument("--expected-final-count", type=int, required=True)
    parser.add_argument("--expected-b2r1-sha256", required=True)
    parser.add_argument("--expected-plan", required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-new-id", action="append")
    parser.add_argument("--expected-new-ids-json")
    parser.add_argument("--activation-output", required=True, type=Path)
    parser.add_argument("--activation-stdout", required=True, type=Path)
    parser.add_argument("--activation-stderr", required=True, type=Path)
    parser.add_argument("--journal-path", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--confirm-stage2-activation", action="store_true")
    args = parser.parse_args()

    started_at = utc_now()
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": started_at,
        "branch": subprocess.check_output(
            ["git", "branch", "--show-current"],  # noqa: S607
            cwd=ROOT,
            text=True,
        ).strip(),  # noqa: S603
        "expected_branch": EXPECTED_BRANCH,
        "backup_path": str(args.backup_path.resolve()),
        "harness_baseline": str(args.harness_baseline),
        "harness_postcheck": str(args.harness_postcheck),
        "activation_output": str(args.activation_output),
        "rollback_performed": False,
        "mutation_performed": False,
        "findings": [],
    }
    try:
        backup_report = verify_backup(args.backup_path)
        report["backup_verification"] = backup_report
        if backup_report["verdict"] != "pass":
            raise WrapperError("fresh backup verification failed")

        baseline = capture_harness_baseline(args.harness_baseline)
        report["harness_baseline_exit_code"] = baseline.returncode
        if baseline.returncode != 0:
            raise WrapperError("Harness baseline capture failed")

        env = os.environ.copy()
        env["NFR_ALLOW_WRITES"] = "true"
        activation_argv = [
            sys.executable,
            str(ROOT / "scripts" / "activate_stage2.py"),
            "--activate",
            "--confirm-stage2-activation",
            "--expected-current-count",
            str(args.expected_current_count),
            "--expected-final-count",
            str(args.expected_final_count),
            "--expected-b2r1-sha256",
            args.expected_b2r1_sha256,
            "--expected-plan",
            args.expected_plan,
            "--expected-head",
            args.expected_head,
            "--backup-path",
            str(args.backup_path),
            "--harness-baseline",
            str(args.harness_baseline),
            "--journal-path",
            str(args.journal_path),
            "--output-json",
            str(args.activation_output),
        ]
        for chunk_id in load_expected_ids(args):
            activation_argv.extend(["--expected-new-id", chunk_id])
        activation = run_command(
            activation_argv,
            env=env,
            output_stdout=args.activation_stdout,
            output_stderr=args.activation_stderr,
        )
        report["activation_command"] = activation_argv
        report["activation_exit_code"] = activation.returncode
        if activation.returncode != 0:
            raise WrapperError("Stage 2 activation subprocess failed")
        report["mutation_performed"] = True

        postcheck = verify_harness_baseline(args.harness_baseline, args.harness_postcheck)
        report["harness_postcheck_exit_code"] = postcheck.returncode
        if postcheck.returncode != 0:
            raise WrapperError("Harness postcheck failed")

        report["finished_at"] = utc_now()
        report["verdict"] = "pass"
    except Exception as exc:  # noqa: BLE001 - wrapper must preserve failure evidence
        report["findings"].append(str(exc))
        try:
            restore_report = verify_restored_state(
                args.backup_path,
                expected_current_count=args.expected_current_count,
                expected_id_list_sha256=None,
                expected_semantic_digest=None,
            )
            report["rollback_performed"] = True
            report["rollback_report"] = restore_report
        except Exception as restore_exc:  # noqa: BLE001
            report["rollback_error"] = str(restore_exc)
        report["finished_at"] = utc_now()
        report["verdict"] = "fail"
    write_json(args.output_json, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("verdict") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
