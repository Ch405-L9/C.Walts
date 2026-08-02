#!/usr/bin/env python3
"""Safely acquire allowlisted public evaluation-source datasets.

This tool never writes to ChromaDB, BM25, or corpus/raw.
It uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import ssl
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import BinaryIO

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "approved_eval_datasets.json"
VAR_ROOT = PROJECT_ROOT / "var" / "eval_sources"
RAW_ROOT = VAR_ROOT / "raw"
EXTRACTED_ROOT = VAR_ROOT / "extracted"
MANIFEST_PATH = VAR_ROOT / "manifests" / "acquisition-manifest.json"
CHUNK_SIZE = 1024 * 1024


class AcquisitionError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_member_name(name: str) -> str:
    normalized = name.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise AcquisitionError(f"unsafe archive member path: {name!r}")
    return str(pure)


def assert_https(url: str) -> None:
    if not url.lower().startswith("https://"):
        raise AcquisitionError(f"only HTTPS is permitted: {url}")


def stream_download(url: str, destination: Path, cap_bytes: int) -> dict[str, object]:
    assert_https(url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    context = ssl.create_default_context()
    request = urllib.request.Request(  # noqa: S310 — assert_https() above pins the scheme
        url,
        headers={"User-Agent": "C.Walts-dataset-audit/0.4"},
        method="GET",
    )
    digest = hashlib.sha256()
    total = 0
    with tempfile.NamedTemporaryFile(
        dir=destination.parent, prefix=destination.name + ".", suffix=".part", delete=False
    ) as temp:
        temp_path = Path(temp.name)
        try:
            # S310: the scheme is not attacker-controlled here. assert_https() runs on
            # the request URL above and again on response.geturl() below, so a redirect
            # to file:, ftp:, or plain http: is refused before a single byte is kept.
            with urllib.request.urlopen(  # noqa: S310
                request, timeout=120, context=context
            ) as response:
                final_url = response.geturl()
                assert_https(final_url)
                length = response.headers.get("Content-Length")
                if length and int(length) > cap_bytes:
                    raise AcquisitionError(
                        f"server reports {length} bytes, above cap {cap_bytes}"
                    )
                while True:
                    block = response.read(CHUNK_SIZE)
                    if not block:
                        break
                    total += len(block)
                    if total > cap_bytes:
                        raise AcquisitionError(
                            f"download exceeded cap of {cap_bytes} bytes"
                        )
                    temp.write(block)
                    digest.update(block)
                temp.flush()
                os.fsync(temp.fileno())
            os.replace(temp_path, destination)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
    return {
        "url": url,
        "final_url": final_url,
        "bytes": total,
        "sha256": digest.hexdigest(),
    }


def _copy_stream(source: BinaryIO, destination: Path, cap_bytes: int) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with tempfile.NamedTemporaryFile(
        dir=destination.parent, prefix=destination.name + ".", suffix=".part", delete=False
    ) as temp:
        temp_path = Path(temp.name)
        try:
            while True:
                block = source.read(CHUNK_SIZE)
                if not block:
                    break
                written += len(block)
                if written > cap_bytes:
                    raise AcquisitionError(
                        f"extracted member exceeded cap of {cap_bytes} bytes"
                    )
                temp.write(block)
            temp.flush()
            os.fsync(temp.fileno())
            os.replace(temp_path, destination)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
    return written


def extract_zip(
    archive: Path, destination: Path, allowlist: set[str], cap_bytes: int
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with zipfile.ZipFile(archive) as zf:
        names = {safe_member_name(info.filename): info for info in zf.infolist()}
        missing = sorted(allowlist - names.keys())
        if missing:
            raise AcquisitionError(f"missing ZIP members: {missing}")
        for member in sorted(allowlist):
            info = names[member]
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            if (unix_mode & 0o170000) == 0o120000:
                raise AcquisitionError(f"symlink ZIP member refused: {member}")
            if info.is_dir():
                raise AcquisitionError(f"directory listed as file: {member}")
            target = destination / safe_member_name(member)
            with zf.open(info, "r") as source:
                size = _copy_stream(source, target, cap_bytes)
            records.append(
                {"member": member, "bytes": size, "sha256": sha256_file(target)}
            )
    return records


def extract_tar(
    archive: Path, destination: Path, allowlist: set[str], cap_bytes: int
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with tarfile.open(archive, "r:gz") as tf:
        names = {safe_member_name(info.name): info for info in tf.getmembers()}
        missing = sorted(allowlist - names.keys())
        if missing:
            raise AcquisitionError(f"missing TAR members: {missing}")
        for member in sorted(allowlist):
            info = names[member]
            if info.issym() or info.islnk():
                raise AcquisitionError(f"link TAR member refused: {member}")
            if not info.isfile():
                raise AcquisitionError(f"non-file TAR member refused: {member}")
            source = tf.extractfile(info)
            if source is None:
                raise AcquisitionError(f"could not read TAR member: {member}")
            target = destination / safe_member_name(member)
            with source:
                size = _copy_stream(source, target, cap_bytes)
            records.append(
                {"member": member, "bytes": size, "sha256": sha256_file(target)}
            )
    return records


def verify_license(
    extracted_root: Path, license_source: str, markers: list[str]
) -> dict[str, object]:
    prefix = "embedded:"
    if not license_source.startswith(prefix):
        raise AcquisitionError(f"unsupported license source: {license_source}")
    relative = safe_member_name(license_source[len(prefix):])
    path = extracted_root / relative
    if not path.is_file():
        raise AcquisitionError(f"embedded license file is missing: {path}")
    text = path.read_text(encoding="utf-8", errors="strict")
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise AcquisitionError(
            f"license marker verification failed for {path}: {missing}"
        )
    return {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "sha256": sha256_file(path),
        "markers_verified": markers,
    }


def load_config() -> dict[str, object]:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "datasets" not in data:
        raise AcquisitionError("invalid approved dataset configuration")
    return data


def archive_suffix(archive_type: str) -> str:
    return { "zip": ".zip", "tar.gz": ".tar.gz" }[archive_type]


def dry_run(config: dict[str, object]) -> None:
    policy = dict(config["policy"])
    cap = int(policy["download_cap_bytes"])
    minimum_free_gib = int(policy["minimum_free_disk_gib"])
    free_gib = shutil.disk_usage(PROJECT_ROOT).free / 1024 ** 3
    print("DRY RUN — no network or filesystem writes")
    print(f"Size cap per download and per extracted member: {cap} bytes "
          f"({cap / 1024 ** 3:.2f} GiB)")
    print(f"Minimum free disk required: {minimum_free_gib} GiB; "
          f"currently free: {free_gib:.2f} GiB")
    print(f"Manifest destination: {MANIFEST_PATH.relative_to(PROJECT_ROOT)}")
    for name, spec_obj in config["datasets"].items():
        spec = dict(spec_obj)
        archive_type = str(spec["archive_type"])
        archive_path = RAW_ROOT / f"{name}{archive_suffix(archive_type)}"
        extracted = EXTRACTED_ROOT / name
        print(f"\n{name}")
        print(f"  Approved: {bool(spec.get('approved'))}")
        print(f"  URL: {spec['archive_url']}")
        print(f"  Type: {archive_type}")
        print(f"  Archive destination: {archive_path.relative_to(PROJECT_ROOT)}")
        print(f"  Extract destination: {extracted.relative_to(PROJECT_ROOT)}")
        print(f"  License: {spec['license']} via {spec['license_source']}")
        print(f"  License markers: {spec['license_markers']}")
        print("  Extract allowlist:")
        for member in spec["members"]:
            print(f"    - {member} -> "
                  f"{(extracted / safe_member_name(str(member))).relative_to(PROJECT_ROOT)}")


def execute(config: dict[str, object], force: bool) -> None:
    cap = int(config["policy"]["download_cap_bytes"])
    minimum_free_gib = int(config["policy"]["minimum_free_disk_gib"])
    free_bytes = shutil.disk_usage(PROJECT_ROOT).free
    required_bytes = minimum_free_gib * 1024 ** 3
    if free_bytes < required_bytes:
        raise AcquisitionError(
            f"insufficient free disk: {free_bytes / 1024 ** 3:.2f} GiB; "
            f"{minimum_free_gib} GiB required"
        )
    manifest: dict[str, object] = {
        "schema_version": 1,
        "config_sha256": sha256_file(CONFIG_PATH),
        "datasets": {},
    }
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    EXTRACTED_ROOT.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    for name, spec_obj in config["datasets"].items():
        spec = dict(spec_obj)
        if not spec.get("approved"):
            raise AcquisitionError(f"dataset is not approved: {name}")
        archive_type = str(spec["archive_type"])
        archive_path = RAW_ROOT / f"{name}{archive_suffix(archive_type)}"
        extracted = EXTRACTED_ROOT / name

        if force:
            archive_path.unlink(missing_ok=True)
            if extracted.exists():
                shutil.rmtree(extracted)

        if archive_path.exists():
            download = {
                "url": spec["archive_url"],
                "final_url": spec["archive_url"],
                "bytes": archive_path.stat().st_size,
                "sha256": sha256_file(archive_path),
                "reused_existing": True,
            }
        else:
            download = stream_download(str(spec["archive_url"]), archive_path, cap)

        allowlist = {safe_member_name(str(x)) for x in spec["members"]}
        if extracted.exists():
            shutil.rmtree(extracted)
        extracted.mkdir(parents=True, exist_ok=True)

        if archive_type == "zip":
            files = extract_zip(archive_path, extracted, allowlist, cap)
        elif archive_type == "tar.gz":
            files = extract_tar(archive_path, extracted, allowlist, cap)
        else:
            raise AcquisitionError(f"unsupported archive type: {archive_type}")

        license_result = verify_license(
            extracted, str(spec["license_source"]), list(spec["license_markers"])
        )
        manifest["datasets"][name] = {
            "version": spec["version"],
            "official_page": spec["official_page"],
            "declared_license": spec["license"],
            "download": download,
            "extracted_files": files,
            "license_verification": license_result,
        }

    temp = MANIFEST_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, MANIFEST_PATH)
    print(f"Wrote {MANIFEST_PATH.relative_to(PROJECT_ROOT)}")


def verify(config: dict[str, object]) -> None:
    if not MANIFEST_PATH.exists():
        raise AcquisitionError(f"manifest does not exist: {MANIFEST_PATH}")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("config_sha256") != sha256_file(CONFIG_PATH):
        raise AcquisitionError("configuration hash does not match manifest")
    for name, spec_obj in config["datasets"].items():
        spec = dict(spec_obj)
        entry = manifest["datasets"].get(name)
        if not entry:
            raise AcquisitionError(f"manifest missing dataset: {name}")
        archive_type = str(spec["archive_type"])
        archive = RAW_ROOT / f"{name}{archive_suffix(archive_type)}"
        if sha256_file(archive) != entry["download"]["sha256"]:
            raise AcquisitionError(f"archive checksum mismatch: {name}")
        extracted = EXTRACTED_ROOT / name
        for record in entry["extracted_files"]:
            path = extracted / safe_member_name(record["member"])
            if sha256_file(path) != record["sha256"]:
                raise AcquisitionError(f"extracted checksum mismatch: {path}")
        verify_license(
            extracted, str(spec["license_source"]), list(spec["license_markers"])
        )
    print("All acquisition files and embedded licenses verified.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--execute", action="store_true")
    modes.add_argument("--verify", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config()
        if args.dry_run:
            dry_run(config)
        elif args.execute:
            execute(config, force=args.force)
        else:
            verify(config)
        return 0
    except (AcquisitionError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
