#!/usr/bin/env python3
"""Verify the Gate 0 checksum records and the raw-dataset exclusion boundary.

Two checksum files exist and they answer different questions.

``SHA256SUMS.package`` is the record of the Gate 0 package **as delivered**. It
is a historical artefact and is never regenerated. Three of its twelve entries
no longer match the working tree, by design: both acquisition scripts and the
test module were edited during Gate 0 for lint compliance, two hardening
changes, and the adversarial suite. A bare ``sha256sum -c`` on it therefore
fails, which is why it is not used as a gate. Its immutability is proved
instead by pinning the digest of the file itself, and its remaining nine entries
are still verified — if a fourth delivered file drifts, this script fails.

``SHA256SUMS.current`` covers the Gate 0 implementation as it stands now. Every
entry must match. This is the release gate, and it is regenerated with --write
whenever a covered file legitimately changes, so it never knowingly fails.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SUMS = PROJECT_ROOT / "SHA256SUMS.package"
CURRENT_SUMS = PROJECT_ROOT / "SHA256SUMS.current"

# The digest of SHA256SUMS.package itself. This is what makes the delivery
# record immutable: the file may not be edited, reordered, or extended.
PACKAGE_SUMS_SHA256 = "0e7e87d2721cafdfe9bdc41fc057dad601374a0ac21be99dd09de03b480cf091"

# Files delivered in the Gate 0 package that were edited afterwards. Every
# reason is recorded in docs/execution-log.md.
KNOWN_MODIFIED_SINCE_DELIVERY = {
    # Lint compliance, a missing-licence refusal path, a dry run that prints
    # what section 5 says to review, and the licence-reconciliation passthrough.
    "scripts/acquire_eval_sources.py",
    # Lint, the Banking77 header assertion, the candidate annotation, the
    # provenance and boundary sections of the report.
    "scripts/inventory_eval_sources.py",
    # The adversarial suite and the Gate 0.1 integrity tests.
    "tests/test_gate0_dataset_tools.py",
    # CLINC150 redeclared CC BY 3.0 to match the licence inside the archive,
    # meta.txt added to the extract allowlist for the required citation, and the
    # licence-reconciliation record added at Gate 0.1.
    "config/approved_eval_datasets.json",
}

# The Gate 0 implementation: source, tests, configuration, schema, prompt, and
# reports. CHANGELOG.md and docs/execution-log.md are deliberately excluded —
# they are living cross-gate documents, and pinning them would guarantee a
# stale checksum the moment Gate 1 opens.
CURRENT_FILES = (
    "CLAUDE_LAUNCHER.txt",
    "GITIGNORE_ADDITIONS.txt",
    "README_START_HERE_C.Walts_v0.4_Gate0.md",
    "SHA256SUMS.package",
    "config/approved_eval_datasets.json",
    "config/query_allocation.yaml",
    "docs/dataset-acquisition-report-gate0.md",
    "docs/evidence/dataset-inventory-gate0.json",
    "docs/evidence/gate0-boundary.json",
    "docs/owner_actions.md",
    "docs/repeatability_blueprint.md",
    "prompts/PF_C.Walts_v0.4_Gate0_dataset-acquisition.md",
    "schemas/eval_query.schema.json",
    "scripts/acquire_eval_sources.py",
    "scripts/inventory_eval_sources.py",
    "scripts/verify_gate0_integrity.py",
    "tests/test_gate0_dataset_tools.py",
)

CURRENT_HEADER = (
    "# C.Walts v0.4 Gate 0 — checksums of the CURRENT tracked implementation.\n"
    "# Regenerate with: .venv/bin/python scripts/verify_gate0_integrity.py --write\n"
    "# Verify with:     .venv/bin/python scripts/verify_gate0_integrity.py --verify\n"
    "#\n"
    "# SHA256SUMS.package is the separate, immutable record of the package as\n"
    "# delivered. Four of its twelve entries no longer match the working tree by\n"
    "# design; the reasons are in docs/execution-log.md and in the\n"
    "# KNOWN_MODIFIED_SINCE_DELIVERY set in scripts/verify_gate0_integrity.py.\n"
    "#\n"
    "# CHANGELOG.md and docs/execution-log.md are excluded on purpose: they are\n"
    "# living cross-gate documents, not Gate 0 artefacts.\n"
)

# Raw evaluation sources must never be tracked and must stay ignored.
MUST_BE_IGNORED = (
    "var/eval_sources/raw/clinc150.zip",
    "var/eval_sources/raw/massive_1_0_en_us.tar.gz",
    "var/eval_sources/raw/banking77.zip",
    "var/eval_sources/extracted/clinc150/clinc150_uci/data_full.json",
    "var/eval_sources/manifests/acquisition-manifest.json",
    "eval/holdout/private/frozen.jsonl",
    "eval/sources/public_pool/pool.jsonl",
)

MUST_BE_UNTRACKED = ("var/", "eval/holdout/private", "eval/sources")


class IntegrityError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_sums(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        digest, _, name = line.partition("  ")
        if not digest or not name:
            raise IntegrityError(f"malformed checksum line in {path.name}: {line!r}")
        entries[name.strip()] = digest.strip()
    return entries


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def check_package_record(failures: list[str]) -> None:
    if not PACKAGE_SUMS.exists():
        failures.append(f"missing delivery record: {PACKAGE_SUMS.name}")
        return
    actual = sha256_file(PACKAGE_SUMS)
    if actual != PACKAGE_SUMS_SHA256:
        failures.append(
            f"{PACKAGE_SUMS.name} has been altered: expected "
            f"{PACKAGE_SUMS_SHA256}, found {actual}"
        )
    entries = parse_sums(PACKAGE_SUMS)
    drifted: set[str] = set()
    for name, expected in entries.items():
        path = PROJECT_ROOT / name
        if not path.is_file():
            failures.append(f"delivered file is gone: {name}")
            continue
        if sha256_file(path) != expected:
            drifted.add(name)
    unexpected = drifted - KNOWN_MODIFIED_SINCE_DELIVERY
    if unexpected:
        failures.append(
            "delivered files changed without a recorded reason: "
            f"{sorted(unexpected)}"
        )
    healed = KNOWN_MODIFIED_SINCE_DELIVERY - drifted
    if healed:
        failures.append(
            "files recorded as modified since delivery now match the package "
            f"record; the record of why is stale: {sorted(healed)}"
        )
    print(
        f"  {PACKAGE_SUMS.name}: digest pinned; "
        f"{len(entries) - len(drifted)}/{len(entries)} delivered files unchanged, "
        f"{len(drifted)} modified with recorded reasons"
    )


def check_current_record(failures: list[str]) -> None:
    if not CURRENT_SUMS.exists():
        failures.append(f"missing current record: {CURRENT_SUMS.name}")
        return
    entries = parse_sums(CURRENT_SUMS)
    missing_from_record = set(CURRENT_FILES) - set(entries)
    if missing_from_record:
        failures.append(
            f"{CURRENT_SUMS.name} does not cover: {sorted(missing_from_record)}"
        )
    for name, expected in sorted(entries.items()):
        path = PROJECT_ROOT / name
        if not path.is_file():
            failures.append(f"tracked Gate 0 file is missing: {name}")
            continue
        actual = sha256_file(path)
        if actual != expected:
            failures.append(
                f"checksum mismatch: {name}\n    recorded {expected}\n    actual   {actual}"
            )
    print(f"  {CURRENT_SUMS.name}: {len(entries)} files checked")


def check_exclusion_boundary(failures: list[str]) -> None:
    for candidate in MUST_BE_IGNORED:
        if git("check-ignore", "-q", candidate).returncode != 0:
            failures.append(f"raw evaluation path is not Git-ignored: {candidate}")
    tracked = git("ls-files", *MUST_BE_UNTRACKED)
    if tracked.returncode != 0:
        failures.append(f"git ls-files failed: {tracked.stderr.strip()}")
    elif tracked.stdout.split():
        failures.append(
            f"raw evaluation sources are tracked: {tracked.stdout.split()}"
        )
    print(
        f"  exclusion boundary: {len(MUST_BE_IGNORED)} paths ignored, "
        "nothing tracked under var/ or the pool directories"
    )


def write_current() -> None:
    lines = [CURRENT_HEADER]
    for name in CURRENT_FILES:
        path = PROJECT_ROOT / name
        if not path.is_file():
            raise IntegrityError(f"cannot checksum a missing file: {name}")
        lines.append(f"{sha256_file(path)}  {name}\n")
    CURRENT_SUMS.write_text("".join(lines), encoding="utf-8")
    print(f"Wrote {CURRENT_SUMS.name} covering {len(CURRENT_FILES)} files.")


def verify() -> int:
    failures: list[str] = []
    print("Gate 0 integrity")
    check_package_record(failures)
    check_current_record(failures)
    check_exclusion_boundary(failures)
    if failures:
        print("\nFAIL")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("\nPASS — delivery record immutable, current tree matches, raw data excluded.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--verify", action="store_true")
    modes.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        if args.write:
            write_current()
            return 0
        return verify()
    except (IntegrityError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
