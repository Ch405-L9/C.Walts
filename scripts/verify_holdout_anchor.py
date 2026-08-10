#!/usr/bin/env python3
"""Verify or explicitly write a non-sensitive external Stage 5 seal anchor."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path.home() / ".local" / "state" / "cwalts" / "holdout-anchors"
sys.path.insert(0, str(ROOT))
from scripts.verify_eval_split import load_manifest, sha256_value, verify_seal  # noqa: E402


class AnchorError(ValueError):
    pass


def _schema() -> dict[str, Any]:
    return json.loads((ROOT / "schemas" / "holdout_anchor.schema.json").read_text())


def anchor_hash(anchor: dict[str, Any]) -> str:
    payload = {key: value for key, value in anchor.items() if key != "anchor_sha256"}
    return sha256_value(payload)


def _validate(anchor: dict[str, Any]) -> None:
    validator = jsonschema.Draft202012Validator(
        _schema(), format_checker=jsonschema.FormatChecker()
    )
    errors = list(validator.iter_errors(anchor))
    if errors:
        raise AnchorError("anchor_schema_invalid")
    if anchor["anchor_sha256"] != anchor_hash(anchor):
        raise AnchorError("anchor_hash_invalid")


def _files(root: Path) -> list[Path]:
    return sorted(root.glob("*.json"), key=lambda path: int(path.stem))


def verify_chain(seal_path: Path, anchor_root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    seal_dir = seal_path.parent.resolve()
    anchor_root = anchor_root.resolve()
    if anchor_root == seal_dir or anchor_root.is_relative_to(seal_dir):
        raise AnchorError("anchor_root_inside_seal_directory")
    verify_seal(load_manifest(seal_path), seal_dir=seal_dir)
    files = _files(anchor_root)
    if not files:
        raise AnchorError("anchor_missing")
    previous_hash: str | None = None
    previous_state: str | None = None
    expected_sequence = 1
    latest: dict[str, Any] | None = None
    for path in files:
        anchor = json.loads(path.read_text())
        _validate(anchor)
        if anchor["sequence"] != expected_sequence:
            raise AnchorError("anchor_sequence_gap")
        if anchor["prior_anchor_sha256"] != previous_hash:
            raise AnchorError("anchor_prior_mismatch")
        if previous_state is not None and (
            (previous_state, anchor["lifecycle_state"])
            not in {("sealed_unused", "scored_once"), ("scored_once", "retired_regression")}
        ):
            raise AnchorError("anchor_lifecycle_rollback")
        previous_hash = anchor["anchor_sha256"]
        previous_state = anchor["lifecycle_state"]
        expected_sequence += 1
        latest = anchor
    seal = load_manifest(seal_path)
    if latest["split_identity_sha256"] != seal["split_identity_sha256"]:
        raise AnchorError("anchor_split_identity_mismatch")
    if latest["benchmark_version"] != seal["immutable_identity"]["benchmark_version"]:
        raise AnchorError("anchor_benchmark_mismatch")
    if latest["lifecycle_state"] != seal["lifecycle"]["state"]:
        raise AnchorError("anchor_lifecycle_state_mismatch")
    events = seal["lifecycle"].get("events", [])
    tip = events[-1]["event_hash"] if events else "0" * 64
    if latest["lifecycle_event_tip_sha256"] != tip:
        raise AnchorError("anchor_event_tip_mismatch")
    return {
        "verdict": "pass",
        "sequence": latest["sequence"],
        "lifecycle_state": latest["lifecycle_state"],
        "mutation_performed": False,
    }


def write_anchor(seal_path: Path, anchor_root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    if os.environ.get("NFR_ALLOW_EVAL_WRITES") != "true":
        raise AnchorError("write_authorization_required")
    if anchor_root.resolve() == seal_path.parent.resolve() or anchor_root.resolve().is_relative_to(
        seal_path.parent.resolve()
    ):
        raise AnchorError("anchor_root_inside_seal_directory")
    verify_seal(load_manifest(seal_path), seal_dir=seal_path.parent)
    seal = load_manifest(seal_path)
    files = _files(anchor_root) if anchor_root.exists() else []
    previous = json.loads(files[-1].read_text()) if files else None
    current_state = seal["lifecycle"]["state"]
    if previous and current_state == previous["lifecycle_state"]:
        raise AnchorError("same_state_anchor_refused")
    if previous and current_state not in {
        "scored_once" if previous["lifecycle_state"] == "sealed_unused" else "retired_regression"
    }:
        raise AnchorError("anchor_lifecycle_rollback")
    events = seal["lifecycle"].get("events", [])
    anchor = {
        "schema_version": 1,
        "benchmark_version": seal["immutable_identity"]["benchmark_version"],
        "algorithm_id": seal["immutable_identity"]["algorithm_id"],
        "sequence": len(files) + 1,
        "split_identity_sha256": seal["split_identity_sha256"],
        "lifecycle_state": current_state,
        "lifecycle_event_tip_sha256": events[-1]["event_hash"] if events else "0" * 64,
        "prior_anchor_sha256": previous["anchor_sha256"] if previous else None,
        "created_at": datetime.now(UTC).isoformat(),
    }
    anchor["anchor_sha256"] = anchor_hash(anchor)
    _validate(anchor)
    anchor_root.mkdir(parents=True, exist_ok=True)
    path = anchor_root / f"{anchor['sequence']:04d}.json"
    path.write_text(json.dumps(anchor, indent=2, sort_keys=True) + "\n")
    return {"verdict": "pass", "sequence": anchor["sequence"], "mutation_performed": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--write", type=Path)
    parser.add_argument("--anchor-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--confirm-anchor-write", action="store_true")
    args = parser.parse_args()
    try:
        if bool(args.verify) == bool(args.write):
            raise AnchorError("one_anchor_mode_required")
        if args.write and not args.confirm_anchor_write:
            raise AnchorError("anchor_write_confirmation_required")
        result = (
            verify_chain(args.verify, args.anchor_root)
            if args.verify
            else write_anchor(args.write, args.anchor_root)
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, AnchorError, jsonschema.ValidationError) as exc:
        print(json.dumps({"verdict": "fail", "finding": str(exc), "mutation_performed": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
