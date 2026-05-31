#!/usr/bin/env python3
"""
Persistent DreamForge worker for DreamForge desktop.
Reads JSON lines from stdin, writes JSON events to stdout (live preview stream).

The worker boots the managed ComfyUI server once at startup; generation is
routed through Comfy API workflows (no in-process PyTorch sampling loop).
"""
from __future__ import annotations

import json
import os
import sys
import threading
import traceback
from pathlib import Path
from types import SimpleNamespace

_generation_lock = threading.Lock()
_generation_active = False

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dreamforge_comfy_server import (
    boot_managed_comfy_server,
    install_worker_signal_handlers,
    register_managed_comfy_shutdown,
    stop_managed_comfy_server,
)
from dreamforge_generation import request_stop
from dreamforge_engine import DreamForgeEngine
from dreamforge_agent_tools import normalize_generation_params
from dreamforge_errors import (
    from_exception,
    generation_in_progress,
    invalid_request,
)
from dreamforge_worker_ipc import (
    configure_stdio,
    emit,
    events_file_path,
    reset_events_file,
)


def _namespace_from_dict(data: dict) -> SimpleNamespace:
    return SimpleNamespace(**data)


def _attach_worker_file_log(log_path: Path) -> None:
    """Mirror worker stderr into worker.log for post-mortem debugging."""
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_path.open("a", encoding="utf-8", errors="replace")
    except OSError:
        return

    stderr = sys.stderr

    class _Tee:
        def write(self, data: str) -> int:
            stderr.write(data)
            try:
                log_file.write(data)
                log_file.flush()
            except OSError:
                pass
            return len(data)

        def flush(self) -> None:
            stderr.flush()
            try:
                log_file.flush()
            except OSError:
                pass

        def isatty(self) -> bool:
            return getattr(stderr, "isatty", lambda: False)()

        @property
        def encoding(self) -> str:
            return getattr(stderr, "encoding", "utf-8")

    sys.stderr = _Tee()  # type: ignore[assignment]


def _shutdown_worker(events_path: Path, *, reason: str = "shutdown") -> None:
    request_stop()
    stop_managed_comfy_server()
    emit({"type": "worker_shutdown", "reason": reason}, events_path)


def serve() -> None:
    configure_stdio()
    register_managed_comfy_shutdown()
    install_worker_signal_handlers()
    os.environ["DREAMFORGE_HEADLESS"] = "1"
    os.environ["DREAMFORGE_USE_COMFY_SERVER"] = "1"
    import builtins

    _real_print = builtins.print

    def _headless_print(*args, **kwargs):
        kwargs.setdefault("file", sys.stderr)
        return _real_print(*args, **kwargs)

    builtins.print = _headless_print

    events_path = events_file_path(_ROOT)
    reset_events_file(events_path)
    _attach_worker_file_log(events_path.parent / "worker.log")

    try:
        emit(
            {"type": "boot_progress", "message": "Starting managed ComfyUI server…"},
            events_path,
        )
        info = boot_managed_comfy_server(
            progress=lambda evt: emit(evt, events_path),
            timeout_s=120.0,
        )
        emit({"type": "ready", **info}, events_path)
    except Exception as exc:
        boot_err = from_exception(exc)
        boot_err["error"] = f"boot_failed: {boot_err.get('message') or exc}"
        emit(boot_err, events_path)
        traceback.print_exc(file=sys.stderr)
        return

    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError as exc:
                emit(invalid_request(f"invalid_json: {exc}"), events_path)
                continue

            cmd = req.get("cmd")
            job_id = req.get("job_id")

            if cmd == "ping":
                emit({"type": "pong", "job_id": job_id}, events_path)
            elif cmd == "shutdown":
                _shutdown_worker(events_path, reason="shutdown_cmd")
                break
            elif cmd == "stop":
                request_stop()
                emit({"type": "stopped", "job_id": job_id}, events_path)
            elif cmd == "generate":
                global _generation_active
                with _generation_lock:
                    if _generation_active:
                        emit(generation_in_progress(job_id=job_id), events_path)
                        continue
                    _generation_active = True

                params = normalize_generation_params(req.get("params") or {})
                base = _namespace_from_dict(params)

                def sink(evt: dict) -> None:
                    if job_id and "job_id" not in evt:
                        evt["job_id"] = job_id
                    emit(evt, events_path)

                try:
                    result = DreamForgeEngine.execute_job(params, stream_sink=sink, job_id=job_id)
                    emit(
                        {
                            "type": "finished",
                            "job_id": job_id,
                            "success": result.get("status") == "success",
                            "result": result,
                        },
                        events_path,
                    )
                except Exception as exc:
                    err = from_exception(exc, job_id=job_id)
                    emit(err, events_path)
                    emit(
                        {
                            "type": "finished",
                            "job_id": job_id,
                            "success": False,
                            "result": {"status": "error", **err},
                        },
                        events_path,
                    )
                    traceback.print_exc(file=sys.stderr)
                finally:
                    with _generation_lock:
                        _generation_active = False
            else:
                emit(invalid_request(f"unknown_cmd: {cmd}", job_id=job_id), events_path)
    finally:
        stop_managed_comfy_server()


if __name__ == "__main__":
    serve()
