"""Local owner approval UI; never intended for transcript-producing execution."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

try:
    from scripts.gate3_private_common import PRIVATE_ROOT, resolve_private_path
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from gate3_private_common import PRIVATE_ROOT, resolve_private_path


def fingerprint(record: dict) -> str:
    value = json.dumps(
        {
            "slot_id": record.get("slot_id"),
            "draft_role": record.get("draft_role"),
            "query_text": record.get("query_text"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(value.encode()).hexdigest()


def approval_entry(
    record: dict, decision: str, reason: str, policy_sha256: str, freeze_sha256: str
) -> dict:
    if decision not in {"approve", "reject", "skip"}:
        raise ValueError("invalid_decision")
    return {
        "candidate_fingerprint": fingerprint(record),
        "slot_id": record["slot_id"],
        "draft_role": record["draft_role"],
        "decision": decision,
        "reason_code": reason,
        "reviewer_role": "owner",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "policy_sha256": policy_sha256,
        "freeze_sha256": freeze_sha256,
    }


def verify_approval(record: dict, entry: dict) -> None:
    if entry.get("candidate_fingerprint") != fingerprint(record):
        raise ValueError("approval_fingerprint_mismatch")
    if entry.get("slot_id") != record.get("slot_id") or entry.get("draft_role") != record.get(
        "draft_role"
    ):
        raise ValueError("approval_identity_mismatch")
    if entry.get("decision") not in {"approve", "reject", "skip"}:
        raise ValueError("invalid_decision")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run locally by the owner; query text is intentionally displayed only locally."
    )
    parser.add_argument(
        "--verify-path", type=Path, help="Validate a private path without displaying its contents."
    )
    parser.add_argument(
        "--pool", type=Path, help="Run local interactive review over a private draft pool."
    )
    parser.add_argument("--ledger", type=Path, help="Private approval ledger destination.")
    args = parser.parse_args()
    if args.verify_path:
        path = resolve_private_path(args.verify_path)
        print(
            json.dumps(
                {
                    "verdict": "pass",
                    "private_path": str(path.relative_to(PRIVATE_ROOT)),
                    "query_text_printed": False,
                }
            )
        )
        return 0
    if args.pool:
        if not args.ledger:
            raise SystemExit("--ledger is required with --pool")
        pool = resolve_private_path(args.pool)
        ledger = resolve_private_path(args.ledger)
        data = json.loads(pool.read_text(encoding="utf-8"))
        decisions: list[dict] = []
        for record in data.get("records", []):
            print(f"\nSlot: {record['slot_id']} | Role: {record['draft_role']}")
            print(f"Class: {record.get('class')} | Task: {record.get('task_family')}")
            print(f"Scenario: {record.get('scenario_family')}")
            print("Query:")
            print(record["query_text"])
            print("[a]pprove [r]eject [s]kip/[q]uit")
            action = input().strip().lower()[:1]
            if action == "q":
                break
            if action not in {"a", "r", "s"}:
                raise SystemExit("invalid_review_action")
            decisions.append(
                approval_entry(
                    record,
                    {"a": "approve", "r": "reject", "s": "skip"}[action],
                    "owner_local_review",
                    record["policy_sha256"],
                    record["generation_freeze_sha256"],
                )
            )
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text(
            json.dumps({"schema_version": 1, "decisions": decisions}, indent=2) + "\n"
        )
        print(
            json.dumps(
                {"verdict": "pass", "decision_count": len(decisions), "query_text_printed": True}
            )
        )
        return 0
    raise SystemExit("interactive_owner_review_requires_local_operator")


if __name__ == "__main__":
    raise SystemExit(main())
