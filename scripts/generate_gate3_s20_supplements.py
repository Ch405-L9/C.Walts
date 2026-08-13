"""Guarded Supplemental-20 generation entry point; generation is disabled in PRE."""

from __future__ import annotations

import argparse
import hashlib
import os

AUTHORIZATION_ENV = "NFR_GATE3_B1_S20_AUTHORIZED"
REQUIRED_COMMON_ENV = ("NFR_ALLOW_PRIVATE_EVAL_GENERATION", "NFR_GATE3_B_AUTHORIZED")


def derive_supplement_seed(
    policy_id: str, slot_id: str, attempt_number: int, base_seed: int = 17
) -> int:
    material = f"{policy_id}|{slot_id}|supplemental|{attempt_number}|{base_seed}"
    value = int.from_bytes(hashlib.sha256(material.encode("utf-8")).digest()[:4], "big")
    value &= 0x7FFFFFFF
    return value or 17


def authorization_status() -> dict[str, bool]:
    return {
        AUTHORIZATION_ENV: os.environ.get(AUTHORIZATION_ENV) == "true",
        **{name: os.environ.get(name) == "true" for name in REQUIRED_COMMON_ENV},
    }


def generate() -> None:
    status = authorization_status()
    if not all(status.values()):
        raise RuntimeError("supplemental_authorization_missing")
    raise RuntimeError("supplemental_generation_not_enabled_in_preparation_build")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    args = parser.parse_args()
    if args.generate:
        generate()
    print({"authorization": authorization_status(), "generation": False})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
