#!/usr/bin/env python3
"""Small localhost bridge for the existing C.Walts narration runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import queue
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from natural_flow_rag.runtime import NarrationRuntime  # noqa: E402
from natural_flow_rag.settings import load_settings  # noqa: E402
from natural_flow_rag.tts.audio import AudioSynthesisService  # noqa: E402
from natural_flow_rag.tts.f5_local import LocalF5Adapter, LocalF5Config  # noqa: E402

LOGGER = logging.getLogger("cwalts.local_server")
MAX_TEXT_CHARS = 5000


@dataclass
class Job:
    job_id: str
    text: str
    metadata: dict[str, str] | None = None
    status: str = "queued"
    output_path: Path | None = None
    error_class: str | None = None


class BridgeState:
    """Owns the single adapter, in-memory jobs, queue, and worker."""

    def __init__(
        self,
        adapter: Any,
        runtime: Any,
        service: AudioSynthesisService,
        output_dir: Path,
        voice_id: str = "B.Lawson",
        model_id: str = "F5TTS_v1_Base",
    ):
        self.adapter = adapter
        self.runtime = runtime
        self.service = service
        self.output_dir = output_dir
        self.voice_id = voice_id
        self.model_id = model_id
        self.jobs: dict[str, Job] = {}
        self.jobs_lock = threading.Lock()
        self.work_queue: queue.Queue[str | None] = queue.Queue()
        self.busy = False
        self.busy_lock = threading.Lock()
        self.worker = threading.Thread(
            target=self._worker_loop, name="cwalts-f5-worker", daemon=True
        )
        self.worker.start()

    @property
    def queue_depth(self) -> int:
        return self.work_queue.qsize()

    def submit(self, text: str, metadata: dict[str, str] | None = None) -> Job:
        job = Job(str(uuid.uuid4()), text, metadata)
        with self.jobs_lock:
            self.jobs[job.job_id] = job
        self.work_queue.put(job.job_id)
        _log_job(job, "queued")
        return job

    def get(self, job_id: str) -> Job | None:
        with self.jobs_lock:
            return self.jobs.get(job_id)

    def stop(self) -> None:
        self.work_queue.put(None)
        self.worker.join(timeout=2)

    def _worker_loop(self) -> None:
        while True:
            job_id = self.work_queue.get()
            if job_id is None:
                self.work_queue.task_done()
                return
            job = self.get(job_id)
            if job is None:
                self.work_queue.task_done()
                continue
            with self.jobs_lock:
                job.status = "running"
            with self.busy_lock:
                self.busy = True
            started = time.monotonic()
            _log_job(job, "running")
            try:
                plan = self.runtime.plan(job.text, job.metadata)
                output_path = self.output_dir / f"{job.job_id}.wav"
                self.service.synthesize(
                    plan,
                    output_path,
                    self.voice_id,
                    self.model_id,
                    "wav",
                )
                with self.jobs_lock:
                    job.output_path = output_path
                    job.status = "completed"
                _log_job(job, "completed", time.monotonic() - started)
            except Exception as exc:  # noqa: BLE001 - job boundary records only class
                with self.jobs_lock:
                    job.status = "failed"
                    job.error_class = type(exc).__name__
                _log_job(job, "failed", time.monotonic() - started)
            finally:
                with self.busy_lock:
                    self.busy = False
                self.work_queue.task_done()


def _log_job(job: Job, state: str, duration: float | None = None) -> None:
    fields = {
        "job_id": job.job_id,
        "text_sha256": hashlib.sha256(job.text.encode("utf-8")).hexdigest(),
        "state": state,
    }
    if duration is not None:
        fields["generation_seconds"] = round(duration, 3)
    if job.error_class:
        fields["error_class"] = job.error_class
    LOGGER.info("job %s", json.dumps(fields, sort_keys=True))


class CwaltsHandler(BaseHTTPRequestHandler):
    server: CwaltsHTTPServer

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    @property
    def state(self) -> BridgeState:
        return self.server.bridge_state

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            with self.state.busy_lock:
                busy = self.state.busy
            self._json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "provider": "f5_local",
                    "voice": self.state.voice_id,
                    "compute": "cpu",
                    "queue_depth": self.state.queue_depth,
                    "busy": busy,
                },
            )
            return
        if self.path.startswith("/jobs/"):
            job = self.state.get(self.path.removeprefix("/jobs/"))
            if job is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "job_not_found"})
            else:
                self._json(HTTPStatus.OK, {"job_id": job.job_id, "status": job.status})
            return
        if self.path.startswith("/audio/"):
            job = self.state.get(self.path.removeprefix("/audio/"))
            if job is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "job_not_found"})
            elif job.status != "completed" or job.output_path is None:
                self._json(HTTPStatus.CONFLICT, {"error": "audio_not_ready", "status": job.status})
            else:
                data = job.output_path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/narrate":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            if length < 0 or length > MAX_TEXT_CHARS + 100:
                raise ValueError("invalid_body_size")
            payload = json.loads(self.rfile.read(length))
            text = payload.get("text") if isinstance(payload, dict) else None
            if not isinstance(text, str) or not text.strip():
                raise ValueError("text_required")
            if len(text) > MAX_TEXT_CHARS:
                self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "text_too_long"})
                return
        except (ValueError, json.JSONDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json_or_text"})
            return
        metadata = payload.get("metadata") if isinstance(payload, dict) else None
        if isinstance(metadata, dict):
            allowed = {"domain", "genre", "audience", "register", "content_mode"}
            metadata = {
                key: value
                for key, value in metadata.items()
                if key in allowed and isinstance(value, str)
            }
        else:
            metadata = None
        job = self.state.submit(text, metadata)
        self._json(HTTPStatus.ACCEPTED, {"job_id": job.job_id, "status": "queued"})

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class CwaltsHTTPServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], state: BridgeState):
        self.bridge_state = state
        super().__init__(address, CwaltsHandler)


def build_production_state() -> BridgeState:
    settings = load_settings()
    from natural_flow_rag.embeddings import OllamaEmbedder
    from natural_flow_rag.lexical_search import LexicalIndex
    from natural_flow_rag.retrieval import Retriever
    from natural_flow_rag.vector_store import VectorStore

    retriever = Retriever(
        settings,
        VectorStore(settings),
        OllamaEmbedder(settings.embedding),
        LexicalIndex(settings.project_root / "var" / "bm25" / "index.json"),
    )
    config = LocalF5Config.from_env()
    adapter = LocalF5Adapter(config)
    adapter.validate_configuration()
    runtime = NarrationRuntime(retriever)
    service = AudioSynthesisService(
        adapter, provider="f5_local", cache_dir=ROOT / "var/audio_cache"
    )
    return BridgeState(
        adapter,
        runtime,
        service,
        ROOT / "var/audio/server",
        config.voice_name,
        config.model_id,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.port < 1 or args.port > 65535:
        parser.error("port must be between 1 and 65535")
    state = build_production_state()
    state.output_dir.mkdir(parents=True, exist_ok=True)
    server = CwaltsHTTPServer(("127.0.0.1", args.port), state)
    try:
        LOGGER.info("C.Walts local bridge listening on 127.0.0.1:%s", args.port)
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
        state.stop()
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
