from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts import acquire_eval_sources as acquire
from scripts.acquire_eval_sources import (
    AcquisitionError,
    assert_https,
    extract_tar,
    extract_zip,
    safe_member_name,
    stream_download,
    verify_license,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Enough of a CC BY 4.0 licence body for the marker check to have something real
# to find. The production check reads the licence shipped inside the archive.
LICENSE_TEXT = "Creative Commons\n\nAttribution 4.0 International\n\nbody\n"


@pytest.mark.parametrize(
    "name",
    [
        "../../escape",
        "../escape",
        "/absolute/path",
        "safe/../../escape",
        r"..\escape",
    ],
)
def test_unsafe_member_names_are_rejected(name: str) -> None:
    with pytest.raises(AcquisitionError):
        safe_member_name(name)


def test_zip_extracts_only_allowlisted_member(tmp_path: Path) -> None:
    archive = tmp_path / "sample.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("approved/data.json", "{}")
        zf.writestr("not-approved.txt", "must not extract")
    destination = tmp_path / "out"
    records = extract_zip(
        archive, destination, {"approved/data.json"}, cap_bytes=1024
    )
    assert len(records) == 1
    assert (destination / "approved/data.json").read_text() == "{}"
    assert not (destination / "not-approved.txt").exists()


def test_zip_path_traversal_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "sample.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../../escape", "bad")
    with pytest.raises(AcquisitionError):
        extract_zip(archive, tmp_path / "out", {"../../escape"}, cap_bytes=1024)


def test_tar_symlink_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "sample.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        info = tarfile.TarInfo("safe/link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tf.addfile(info)
    with pytest.raises(AcquisitionError):
        extract_tar(archive, tmp_path / "out", {"safe/link"}, cap_bytes=1024)


def test_member_size_cap_is_enforced(tmp_path: Path) -> None:
    archive = tmp_path / "sample.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("approved/large.bin", b"x" * 2048)
    with pytest.raises(AcquisitionError):
        extract_zip(
            archive,
            tmp_path / "out",
            {"approved/large.bin"},
            cap_bytes=1024,
        )


def test_zip_symlink_member_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "sample.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        info = zipfile.ZipInfo("safe/link")
        info.external_attr = (0o120777 << 16) | 0o200000
        zf.writestr(info, "/etc/passwd")
    with pytest.raises(AcquisitionError, match="symlink"):
        extract_zip(archive, tmp_path / "out", {"safe/link"}, cap_bytes=1024)


def test_tar_absolute_member_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "sample.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        info = tarfile.TarInfo("/absolute/path")
        info.size = 3
        tf.addfile(info, io.BytesIO(b"bad"))
    with pytest.raises(AcquisitionError):
        extract_tar(archive, tmp_path / "out", {"/absolute/path"}, cap_bytes=1024)


def test_missing_allowlisted_member_aborts_the_whole_extraction(tmp_path: Path) -> None:
    archive = tmp_path / "sample.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("approved/data.json", "{}")
    destination = tmp_path / "out"
    with pytest.raises(AcquisitionError, match="missing ZIP members"):
        extract_zip(
            archive,
            destination,
            {"approved/data.json", "approved/LICENSE"},
            cap_bytes=1024,
        )
    assert not (destination / "approved/data.json").exists()


# --- embedded licence verification -----------------------------------------


def test_missing_embedded_license_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(AcquisitionError, match="missing"):
        verify_license(tmp_path, "embedded:LICENSE", ["Attribution 4.0 International"])


def test_wrong_license_marker_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "LICENSE").write_text(
        "Creative Commons\n\nAttribution 3.0 Unported\n", encoding="utf-8"
    )
    with pytest.raises(AcquisitionError, match="marker verification failed"):
        verify_license(tmp_path, "embedded:LICENSE", ["Attribution 4.0 International"])


def test_correct_license_marker_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(acquire, "PROJECT_ROOT", tmp_path)
    (tmp_path / "LICENSE").write_text(LICENSE_TEXT, encoding="utf-8")
    result = verify_license(
        tmp_path, "embedded:LICENSE", ["Attribution 4.0 International"]
    )
    assert result["markers_verified"] == ["Attribution 4.0 International"]
    assert result["sha256"] == hashlib.sha256(
        LICENSE_TEXT.encode("utf-8")
    ).hexdigest()


def test_license_source_outside_the_extraction_root_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(AcquisitionError):
        verify_license(tmp_path, "embedded:../../etc/passwd", ["anything"])


# --- transport ---------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://archive.ics.uci.edu/static/public/570/clinc150.zip",
        "ftp://example.invalid/data.zip",
        "file:///etc/passwd",
        "HTTP://example.invalid/data.zip",
    ],
)
def test_non_https_urls_are_rejected(url: str) -> None:
    with pytest.raises(AcquisitionError, match="only HTTPS"):
        assert_https(url)


def test_stream_download_refuses_http_before_touching_the_network(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "out.zip"
    with pytest.raises(AcquisitionError, match="only HTTPS"):
        stream_download("http://example.invalid/a.zip", destination, cap_bytes=1024)
    assert not destination.exists()


class _FakeResponse:
    """Minimal stand-in for the urlopen context manager."""

    def __init__(
        self,
        payload: bytes,
        *,
        final_url: str = "https://example.invalid/a.zip",
        content_length: str | None = None,
        fail_after: int | None = None,
    ) -> None:
        self._stream = io.BytesIO(payload)
        self._final_url = final_url
        self._fail_after = fail_after
        self._served = 0
        self.headers = {} if content_length is None else {"Content-Length": content_length}

    def geturl(self) -> str:
        return self._final_url

    def read(self, size: int) -> bytes:
        if self._fail_after is not None and self._served >= self._fail_after:
            raise ConnectionResetError("connection reset mid-transfer")
        block = self._stream.read(size)
        self._served += len(block)
        return block

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def _patch_urlopen(monkeypatch: pytest.MonkeyPatch, response: _FakeResponse) -> None:
    monkeypatch.setattr(
        acquire.urllib.request, "urlopen", lambda *a, **k: response
    )


def test_declared_content_length_above_the_cap_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_urlopen(monkeypatch, _FakeResponse(b"x" * 10, content_length="99999999"))
    destination = tmp_path / "out.zip"
    with pytest.raises(AcquisitionError, match="above cap"):
        stream_download("https://example.invalid/a.zip", destination, cap_bytes=1024)
    assert not destination.exists()
    assert list(tmp_path.iterdir()) == []


def test_streamed_bytes_above_the_cap_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_urlopen(monkeypatch, _FakeResponse(b"x" * 5000))
    destination = tmp_path / "out.zip"
    with pytest.raises(AcquisitionError, match="exceeded cap"):
        stream_download("https://example.invalid/a.zip", destination, cap_bytes=1024)
    assert not destination.exists()
    assert list(tmp_path.iterdir()) == []


def test_redirect_to_a_non_https_host_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_urlopen(
        monkeypatch,
        _FakeResponse(b"payload", final_url="http://example.invalid/redirected.zip"),
    )
    destination = tmp_path / "out.zip"
    with pytest.raises(AcquisitionError, match="only HTTPS"):
        stream_download("https://example.invalid/a.zip", destination, cap_bytes=1024)
    assert not destination.exists()


def test_interrupted_download_does_not_replace_a_verified_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "out.zip"
    destination.write_bytes(b"the verified archive")
    before = hashlib.sha256(destination.read_bytes()).hexdigest()
    _patch_urlopen(monkeypatch, _FakeResponse(b"y" * 4096, fail_after=1024))
    with pytest.raises(ConnectionResetError):
        stream_download("https://example.invalid/a.zip", destination, cap_bytes=99999)
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == before
    assert [p.name for p in tmp_path.iterdir()] == ["out.zip"]


def test_successful_download_hashes_what_it_wrote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"z" * 3000
    _patch_urlopen(monkeypatch, _FakeResponse(payload))
    destination = tmp_path / "out.zip"
    result = stream_download(
        "https://example.invalid/a.zip", destination, cap_bytes=99999
    )
    assert destination.read_bytes() == payload
    assert result["bytes"] == len(payload)
    assert result["sha256"] == hashlib.sha256(payload).hexdigest()


# --- end-to-end execute, with no network -------------------------------------


def _build_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the tool at a temporary root holding one pre-placed archive.

    execute() reuses an archive that is already present, so the whole
    download -> extract -> verify -> manifest path runs without a network call.
    """
    raw = tmp_path / "raw"
    raw.mkdir()
    archive = raw / "sample.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("pack/data.json", json.dumps({"rows": [1, 2, 3]}))
        zf.writestr("pack/LICENSE", LICENSE_TEXT)
        zf.writestr("pack/not-approved.csv", "must never be extracted")

    config = {
        "version": 1,
        "policy": {
            "https_only": True,
            "raw_root": "var/eval_sources",
            "production_ingestion_forbidden": True,
            "minimum_free_disk_gib": 0,
            "download_cap_bytes": 1048576,
        },
        "datasets": {
            "sample": {
                "approved": True,
                "version": "test-1",
                "archive_url": "https://example.invalid/sample.zip",
                "archive_type": "zip",
                "official_page": "https://example.invalid/",
                "license": "CC-BY-4.0",
                "license_source": "embedded:pack/LICENSE",
                "members": ["pack/data.json", "pack/LICENSE"],
                "license_markers": ["Attribution 4.0 International"],
            }
        },
    }
    config_path = tmp_path / "approved_eval_datasets.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    monkeypatch.setattr(acquire, "CONFIG_PATH", config_path)
    monkeypatch.setattr(acquire, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(acquire, "VAR_ROOT", tmp_path)
    monkeypatch.setattr(acquire, "RAW_ROOT", raw)
    monkeypatch.setattr(acquire, "EXTRACTED_ROOT", tmp_path / "extracted")
    monkeypatch.setattr(
        acquire, "MANIFEST_PATH", tmp_path / "manifests" / "acquisition-manifest.json"
    )
    return config_path


def test_execute_is_idempotent_and_verifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build_fixture(tmp_path, monkeypatch)
    config = acquire.load_config()

    acquire.execute(config, force=False)
    first = acquire.MANIFEST_PATH.read_text(encoding="utf-8")
    acquire.execute(config, force=False)
    second = acquire.MANIFEST_PATH.read_text(encoding="utf-8")

    assert first == second
    acquire.verify(config)

    extracted = acquire.EXTRACTED_ROOT / "sample"
    assert (extracted / "pack" / "data.json").exists()
    assert not (extracted / "pack" / "not-approved.csv").exists()


def test_verify_fails_when_an_extracted_file_is_altered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build_fixture(tmp_path, monkeypatch)
    config = acquire.load_config()
    acquire.execute(config, force=False)
    target = acquire.EXTRACTED_ROOT / "sample" / "pack" / "data.json"
    target.write_text('{"rows": [9]}', encoding="utf-8")
    with pytest.raises(AcquisitionError, match="extracted checksum mismatch"):
        acquire.verify(config)


def test_verify_fails_when_the_approved_source_config_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _build_fixture(tmp_path, monkeypatch)
    config = acquire.load_config()
    acquire.execute(config, force=False)
    config_path.write_text(
        config_path.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    with pytest.raises(AcquisitionError, match="configuration hash"):
        acquire.verify(config)


def test_an_unapproved_dataset_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _build_fixture(tmp_path, monkeypatch)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["datasets"]["sample"]["approved"] = False
    with pytest.raises(AcquisitionError, match="not approved"):
        acquire.execute(config, force=False)


def test_no_secret_shaped_value_reaches_the_dry_run_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-value-do-not-print")
    monkeypatch.setenv("HF_TOKEN", "hf_secret_value_do_not_print")
    acquire.dry_run(acquire.load_config())
    printed = capsys.readouterr().out
    assert "sk-ant-secret-value-do-not-print" not in printed
    assert "hf_secret_value_do_not_print" not in printed
    assert "huggingface" not in printed.casefold()


# --- production-boundary invariants -----------------------------------------


def test_raw_evaluation_sources_are_ignored_by_git() -> None:
    for candidate in [
        "var/eval_sources/raw/clinc150.zip",
        "var/eval_sources/extracted/clinc150/clinc150_uci/data_full.json",
        "var/eval_sources/manifests/acquisition-manifest.json",
        "eval/holdout/private/frozen.jsonl",
        "eval/sources/public_pool/pool.jsonl",
    ]:
        result = subprocess.run(  # noqa: S603
            ["git", "check-ignore", "-q", candidate],  # noqa: S607
            cwd=PROJECT_ROOT,
            check=False,
        )
        assert result.returncode == 0, f"{candidate} is not Git-ignored"


def test_no_raw_evaluation_source_is_tracked() -> None:
    tracked = subprocess.run(  # noqa: S603
        ["git", "ls-files", "var/", "eval/holdout/private", "eval/sources"],  # noqa: S607
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert tracked == []


def test_the_acquisition_tools_cannot_address_the_production_stores() -> None:
    """The boundary is structural: the tools cannot reach a production store.

    The acquisition tool never names one. The inventory tool names `var/chroma`
    and `var/bm25` only inside the prose of the report it writes, so it is held
    to the weaker but sufficient rule that it imports no store client and writes
    only under `docs/`.
    """
    acquire_source = (
        PROJECT_ROOT / "scripts" / "acquire_eval_sources.py"
    ).read_text(encoding="utf-8")
    for forbidden in ["var/chroma", "var/bm25", "badgr_natural_flow", "chromadb"]:
        assert forbidden not in acquire_source

    from scripts import inventory_eval_sources as inventory

    inventory_source = (
        PROJECT_ROOT / "scripts" / "inventory_eval_sources.py"
    ).read_text(encoding="utf-8")
    assert "chromadb" not in inventory_source
    docs = PROJECT_ROOT / "docs"
    assert inventory.REPORT_JSON.is_relative_to(docs)
    assert inventory.REPORT_MD.is_relative_to(docs)
    assert inventory.EXTRACTED.is_relative_to(PROJECT_ROOT / "var" / "eval_sources")

    assert acquire.VAR_ROOT == PROJECT_ROOT / "var" / "eval_sources"
    assert acquire.RAW_ROOT.is_relative_to(acquire.VAR_ROOT)
    assert acquire.EXTRACTED_ROOT.is_relative_to(acquire.VAR_ROOT)


def _digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_gate0_verification_leaves_the_production_stores_byte_identical() -> None:
    chroma = PROJECT_ROOT / "var" / "chroma" / "chroma.sqlite3"
    bm25 = PROJECT_ROOT / "var" / "bm25" / "index.json"
    if not chroma.is_file() or not bm25.is_file():
        pytest.skip("production stores are not present in this working tree")
    before = (_digest(chroma), _digest(bm25))
    subprocess.run(  # noqa: S603
        [".venv/bin/python", "scripts/acquire_eval_sources.py", "--dry-run"],  # noqa: S607
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    assert (_digest(chroma), _digest(bm25)) == before


def test_the_badgr_harness_production_store_is_untouched() -> None:
    """Pinned at the same MD5 scripts/smoke_test.py has asserted since CP3."""
    harness = Path("/home/t0n34781/projects/badgr_harness/rag_db/chroma.sqlite3")
    if not harness.is_file():
        pytest.skip("the BADGR Harness store is not present on this host")
    digest = hashlib.md5(harness.read_bytes(), usedforsecurity=False).hexdigest()
    assert digest == "bdcbe32b706c6ccce1f62e8e9f2d2c49"
