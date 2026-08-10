#!/usr/bin/env python3
"""Read-only verification of the approved local Gate 2 acquisition."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    cfg = json.loads((ROOT / "config/approved_eval_datasets.json").read_text())
    manifest_path = ROOT / "var/eval_sources/manifests/acquisition-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    expected = {"clinc150", "massive_1_0_en_us", "banking77"}
    if set(manifest.get("datasets", {})) != expected:
        raise SystemExit("acquisition_dataset_set_mismatch")
    results = []
    for name in sorted(expected):
        spec = cfg["datasets"][name]
        item = manifest["datasets"][name]
        archive_names = {
            "clinc150": "clinc150.zip",
            "massive_1_0_en_us": "massive_1_0_en_us.tar.gz",
            "banking77": "banking77.zip",
        }
        archive = ROOT / "var/eval_sources/raw" / archive_names[name]
        if not archive.exists():
            raise SystemExit(f"archive_missing:{name}")
        if sha256(archive) != item["download"]["sha256"]:
            raise SystemExit(f"archive_hash_mismatch:{name}")
        if item["version"] != spec["version"] or item["declared_license"] != spec["license"]:
            raise SystemExit(f"metadata_mismatch:{name}")
        for member in item["extracted_files"]:
            path = ROOT / "var/eval_sources/extracted" / name / member["member"]
            if not path.exists() or sha256(path) != member["sha256"]:
                raise SystemExit(f"member_hash_mismatch:{name}:{member['member']}")
        results.append(
            {
                "dataset": name,
                "version": item["version"],
                "archive_sha256": item["download"]["sha256"],
                "members_verified": len(item["extracted_files"]),
                "license_verified": bool(item.get("license_verification")),
            }
        )
    payload = {
        "schema_version": 1,
        "verdict": "pass",
        "mutation_performed": False,
        "network_used": False,
        "datasets": results,
    }
    print(
        json.dumps(payload, sort_keys=True, indent=2)
        if args.json
        else "acquisition verification: pass"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
