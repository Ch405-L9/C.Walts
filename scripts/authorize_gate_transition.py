#!/usr/bin/env python3
"""Authorize supported Gate 1.2 transitions after blocker checks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT / "scripts"))
    from verify_open_blockers import (  # type: ignore[no-redef]
        REGISTRY_PATH,
        SUPPORTED_SCOPES,
        BlockerRegistryError,
        verify_scope,
    )
else:
    from scripts.verify_open_blockers import (
        REGISTRY_PATH,
        SUPPORTED_SCOPES,
        BlockerRegistryError,
        verify_scope,
    )


class AuthorizationError(ValueError):
    """A supported transition cannot be authorized."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def run_stage5_prerequisites() -> None:
    commands = [
        [sys.executable, "scripts/verify_eval_split.py", "--verify-config"],
        [sys.executable, "scripts/verify_eval_split.py", "--verify-production-boundary"],
    ]
    for command in commands:
        result = subprocess.run(  # noqa: S603
            command, cwd=ROOT, capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            raise AuthorizationError("stage5_prerequisite_failed")


def authorize_gate_transition(
    scope: str,
    *,
    registry_path: Path = REGISTRY_PATH,
    stage5_checker: Callable[[], None] | None = None,
) -> dict[str, object]:
    if scope not in SUPPORTED_SCOPES:
        raise AuthorizationError("unsupported_authorization_scope")
    try:
        result = verify_scope(scope, registry_path)
    except BlockerRegistryError as exc:
        raise AuthorizationError(exc.code) from exc
    if scope == "gate2_authorization":
        (stage5_checker or run_stage5_prerequisites)()
    return {
        "schema_version": 1,
        "scope": scope,
        "verdict": "authorized",
        "blocker_result": result,
        "mutation_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transition", required=True, choices=SUPPORTED_SCOPES)
    args = parser.parse_args()
    try:
        print(json.dumps(authorize_gate_transition(args.transition), indent=2, sort_keys=True))
        return 0
    except AuthorizationError as exc:
        print(
            json.dumps(
                {"verdict": "refused", "finding": exc.code, "mutation_performed": False},
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
