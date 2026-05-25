#!/usr/bin/env python3
"""
Persistent DreamForge worker for DreamForge desktop.
Reads JSON lines from stdin, writes JSON events to stdout (live preview stream).
"""
from __future__ import annotations

import os

# Suppress duplicate-ObjC-class warnings from cv2/av FFmpeg dylib conflict.
# Both packages bundle different versions of libavdevice; Apple's runtime
# warns that this may cause crashes.  The env var is the sanctioned fix.
os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

# Reduce CUDA OOM fragmentation before torch is imported.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import json
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

from dreamforge_generation import boot_headless, request_stop, run_generation
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


def _normalize_vram_arg(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "gpu-only": "--gpu-only",
        "--gpu-only": "--gpu-only",
        "high": "--highvram",
        "highvram": "--highvram",
        "--highvram": "--highvram",
        "normal": "--normalvram",
        "normalvram": "--normalvram",
        "--normalvram": "--normalvram",
        "low": "--lowvram",
        "lowvram": "--lowvram",
        "--lowvram": "--lowvram",
        "no": "--novram",
        "novram": "--novram",
        "--novram": "--novram",
        "cpu": "--cpu",
        "--cpu": "--cpu",
    }
    return aliases.get(normalized)


def _desktop_worker_argv() -> list[str]:
    forced = _normalize_vram_arg(os.environ.get("DREAMFORGE_DESKTOP_VRAM_MODE"))
    if forced:
        return [forced]

    try:
        import torch
        if torch.cuda.is_available():
            total_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            if total_gb >= 10:
                return ["--normalvram"]
            if total_gb >= 6:
                return ["--lowvram"]
            return ["--novram"]
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return ["--normalvram"]
    except ImportError:
        pass
    return ["--cpu"]


def _namespace_from_dict(data: dict) -> SimpleNamespace:
    return SimpleNamespace(**data)


def serve() -> None:
    configure_stdio()
    os.environ["DREAMFORGE_HEADLESS"] = "1"
    import builtins

    _real_print = builtins.print

    def _headless_print(*args, **kwargs):
        kwargs.setdefault("file", sys.stderr)
        return _real_print(*args, **kwargs)

    builtins.print = _headless_print

    events_path = events_file_path(_ROOT)
    reset_events_file(events_path)

    try:
        emit({"type": "boot_progress", "message": "Starting GPU worker process..."}, events_path)
        _worker_argv = _desktop_worker_argv()
        emit(
            {
                "type": "boot_progress",
                "message": f"Starting engine with {' '.join(_worker_argv)}...",
            },
            events_path,
        )
        info = boot_headless(
            _worker_argv,
            progress=lambda evt: emit(evt, events_path),
        )
        emit({"type": "ready", **info}, events_path)
    except Exception as exc:
        boot_err = from_exception(exc)
        boot_err["error"] = f"boot_failed: {boot_err.get('message') or exc}"
        emit(boot_err, events_path)
        traceback.print_exc(file=sys.stderr)
        return

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
                result = run_generation(base, stream_sink=sink, job_id=job_id)
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


if __name__ == "__main__":
    serve()
