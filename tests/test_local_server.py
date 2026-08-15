"""Mock-backed tests for the stdlib C.Walts localhost bridge."""

from __future__ import annotations

import io
import json
import logging
import sys
import threading
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

import pytest

from natural_flow_rag.runtime import NarrationRuntime
from natural_flow_rag.tts.audio import AudioSynthesisService
from natural_flow_rag.tts.base import TTSRequest, TTSResult

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import cwalts_local_server as bridge  # noqa: E402


def _wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(b"\x00\x00" * 800)
    return buffer.getvalue()


class MockAdapter:
    def __init__(self) -> None:
        self.calls: list[TTSRequest] = []
        self.first_started = threading.Event()
        self.release_first = threading.Event()

    def capabilities(self):
        return None

    def validate_configuration(self) -> None:
        return None

    def synthesize(self, request: TTSRequest) -> TTSResult:
        self.calls.append(request)
        if len(self.calls) == 1:
            self.first_started.set()
            self.release_first.wait(timeout=2)
        return TTSResult(_wav_bytes(), "audio/wav")


class MockRuntime:
    def __init__(self) -> None:
        self.metadata: list[dict | None] = []

    def plan(self, text: str, metadata: dict | None = None):
        self.metadata.append(metadata)
        return NarrationRuntime().plan(text, metadata or {"domain": "educational"})


@pytest.fixture
def running_bridge(tmp_path: Path):
    adapter = MockAdapter()
    service = AudioSynthesisService(adapter, provider="f5_local", cache_dir=tmp_path / "cache")
    state = bridge.BridgeState(
        adapter,
        MockRuntime(),
        service,
        tmp_path / "audio",
    )
    state.output_dir.mkdir()
    server = bridge.CwaltsHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        yield base, state, adapter, thread
    finally:
        server.shutdown()
        server.server_close()
        state.stop()
        thread.join(timeout=2)


def _request(base: str, method: str, path: str, payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(  # noqa: S310 - localhost test URL
        base + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        return urllib.request.urlopen(request, timeout=3)  # noqa: S310 - localhost test URL
    except urllib.error.HTTPError as exc:
        return exc


def _wait_for_status(base: str, job_id: str, expected: str) -> dict:
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        response = _request(base, "GET", f"/jobs/{job_id}")
        payload = json.loads(response.read())
        if payload["status"] == expected:
            return payload
        time.sleep(0.02)
    raise AssertionError(f"job did not reach {expected}")


def test_health_and_queued_jobs_are_single_worker(running_bridge, caplog) -> None:
    base, _state, adapter, _thread = running_bridge
    health = _request(base, "GET", "/health")
    assert health.status == 200
    health_payload = json.loads(health.read())
    assert health_payload["provider"] == "f5_local"
    assert health_payload["voice"] == "B.Lawson"

    private_marker = "server-source-marker-that-must-not-be-logged"
    with caplog.at_level(logging.INFO, logger="cwalts.local_server"):
        first = _request(base, "POST", "/narrate", {"text": private_marker})
        first_payload = json.loads(first.read())
        assert first.status == 202
        assert first_payload["status"] == "queued"
        assert adapter.first_started.wait(timeout=2)
        running = json.loads(_request(base, "GET", f"/jobs/{first_payload['job_id']}").read())
        assert running["status"] == "running"
        second = _request(base, "POST", "/narrate", {"text": "Second synthetic sentence."})
        second_payload = json.loads(second.read())
        assert second.status == 202
        queued = json.loads(_request(base, "GET", f"/jobs/{second_payload['job_id']}").read())
        assert queued["status"] == "queued"
        adapter.release_first.set()
        _wait_for_status(base, first_payload["job_id"], "completed")
        _wait_for_status(base, second_payload["job_id"], "completed")

    assert len(adapter.calls) == 2
    assert private_marker not in caplog.text

    audio = _request(base, "GET", f"/audio/{first_payload['job_id']}")
    assert audio.status == 200
    assert audio.headers["Content-Type"] == "audio/wav"
    assert audio.read(4) == b"RIFF"


def test_oversized_text_is_rejected(running_bridge) -> None:
    base, _state, _adapter, _thread = running_bridge
    response = _request(base, "POST", "/narrate", {"text": "x" * 5001})
    assert response.status == 413
    assert json.loads(response.read())["error"] == "text_too_long"


def test_optional_supported_metadata_is_forwarded_and_unknown_fields_are_ignored(
    running_bridge,
) -> None:
    base, _state, _adapter, _thread = running_bridge
    response = _request(
        base,
        "POST",
        "/narrate",
        {
            "text": "A synthetic educational sentence.",
            "metadata": {
                "domain": "educational",
                "register": "reflective_narration",
                "unknown_private_field": "ignored",
            },
        },
    )
    assert response.status == 202
    payload = json.loads(response.read())
    assert payload["status"] == "queued"
    assert _wait_for_status(base, payload["job_id"], "completed")["status"] == "completed"
    runtime = running_bridge[1].runtime
    assert runtime.metadata == [
        {"domain": "educational", "register": "reflective_narration"}
    ]
