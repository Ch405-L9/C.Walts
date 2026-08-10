#!/usr/bin/env python3
"""Run the pinned, redacted Gitleaks staged scan for the local hook."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

EXPECTED_VERSION = "8.30.1"


def _gitleaks() -> str:
    candidates = [shutil.which("gitleaks"), str(Path.home() / ".local" / "bin" / "gitleaks")]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise RuntimeError("gitleaks_missing")


def main() -> int:
    try:
        executable = _gitleaks()
        version = subprocess.run(  # noqa: S603
            [executable, "version"], capture_output=True, text=True, check=True
        ).stdout.strip()
        if EXPECTED_VERSION not in version:
            raise RuntimeError("gitleaks_version_mismatch")
        command = [
            executable,
            "git",
            "--pre-commit",
            "--redact",
            "--staged",
            "--verbose",
        ]
        return subprocess.run(command, check=False).returncode  # noqa: S603
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"gitleaks hook refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
