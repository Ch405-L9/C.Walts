"""Read-only validator for synthetic or future private Gate 3 manifests."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import jsonschema

try:
    from scripts.gate3_private_common import (
        PRIVATE_ROOT,
        PrivateAuthoringError,
        forbidden_output_keys,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from gate3_private_common import PRIVATE_ROOT, PrivateAuthoringError, forbidden_output_keys

CLASS_TOTALS = {
    "supported_in_domain": 150,
    "near_domain_unsupported": 45,
    "far_out_of_domain": 15,
    "ambiguous_adversarial_insufficient": 75,
}


def validate_manifest(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        resolved.relative_to(PRIVATE_ROOT)
    except ValueError as exc:
        raise PrivateAuthoringError("manifest_outside_private_root") from exc
    data = json.loads(resolved.read_text(encoding="utf-8"))
    if "records" not in data:
        raise PrivateAuthoringError("records_missing")
    for record in data["records"]:
        if record.get("source_dataset") != "custom":
            raise PrivateAuthoringError("custom_dataset_namespace_mismatch")
        if "split" in record or "qrel" in record or "holdout" in record:
            raise PrivateAuthoringError("split_or_evaluation_fields_forbidden")
        if record.get("provenance", {}).get("kind") not in {
            "owner_authored",
            "vendor_generated_owner_approved",
        }:
            raise PrivateAuthoringError("custom_provenance_invalid")
        if forbidden_output_keys(record):
            raise PrivateAuthoringError("forbidden_record_key")
        text = str(record.get("query_text", ""))
        if re.search(
            r"\b(answer|qrel|holdout|calibration|threshold|score|chunk[_ -]?id|source[_ -]?id)\b",
            text,
            re.I,
        ):
            raise PrivateAuthoringError("answer_or_qrel_leakage")
    return {
        "verdict": "pass",
        "record_count": len(data["records"]),
        "query_text_printed": False,
        "mutation_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--draft-pool", action="store_true")
    args = parser.parse_args()
    try:
        if args.draft_pool:
            from scripts.verify_gate3_private_draft_pool import validate_pool

            print(json.dumps(validate_pool(args.manifest), sort_keys=True))
            return 0
        print(json.dumps(validate_manifest(args.manifest), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, jsonschema.ValidationError) as exc:
        print(json.dumps({"verdict": "fail", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
