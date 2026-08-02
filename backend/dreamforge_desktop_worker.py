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
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

_generation_lock = threading.Lock()
_generation_active = False

_automation_cancel_requested = False

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)
# ComfyUI spawns subprocesses on macOS; avoid fork + ObjC crashes.
os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

from _paths import bootstrap_paths

bootstrap_paths()

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
from dreamforge_progress import gpu_telemetry
from dreamforge_vram_profiles import apply_desktop_vram_env
from dreamforge_comfy_launch import apply_runtime_optimization_env, comfy_launch_extra_args
from dreamforge_worker_ipc import (
    configure_stdio,
    emit,
    events_file_path,
    reset_events_file,
)


def _namespace_from_dict(data: dict) -> SimpleNamespace:
    return SimpleNamespace(**data)


def _reload_generation_modules():
    """Reload generation modules so the desktop worker picks up code changes."""
    import importlib

    import dreamforge_comfy_workflow_import
    import dreamforge_comfy_workflows
    import dreamforge_generation
    import dreamforge_krita_resources

    for mod in (
        dreamforge_comfy_workflows,
        dreamforge_comfy_workflow_import,
        dreamforge_krita_resources,
        dreamforge_generation,
    ):
        importlib.reload(mod)
    return dreamforge_generation.run_generation


def _shutdown_worker(events_path: Path, *, reason: str = "shutdown") -> None:
    request_stop()
    stop_managed_comfy_server()
    emit({"type": "worker_shutdown", "reason": reason}, events_path)


def serve() -> None:
    global _generation_active
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
    # worker.log is captured by the desktop shell from this process's stderr pipe.

    resolved_profile = apply_desktop_vram_env()
    apply_runtime_optimization_env()
    emit(
        {
            "type": "boot_progress",
            "message": f"VRAM profile: {resolved_profile}",
            "phase": "booting",
        },
        events_path,
    )

    try:
        emit(
            {"type": "boot_progress", "message": "Starting managed ComfyUI server…"},
            events_path,
        )
        info = boot_managed_comfy_server(
            progress=lambda evt: emit(evt, events_path),
            timeout_s=120.0,
        )
        telemetry = gpu_telemetry()
        telemetry["launch_args"] = list(comfy_launch_extra_args())
        telemetry["optimization_env"] = {
            key: os.environ.get(key)
            for key in (
                "DREAMFORGE_COMFY_BACKEND",
                "DREAMFORGE_HARDWARE_CLASS",
                "PYTORCH_ENABLE_MPS_FALLBACK",
                "TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL",
            )
            if os.environ.get(key) is not None
        }
        emit(
            {
                "type": "ready",
                **info,
                **telemetry,
                "vram_profile": resolved_profile,
                "vram_profile_hint": telemetry.get("vram_profile_hint") or resolved_profile,
            },
            events_path,
        )
    except Exception as exc:
        boot_err = from_exception(exc)
        boot_err["error"] = f"boot_failed: {boot_err.get('message') or exc}"
        emit(boot_err, events_path)
        traceback.print_exc(file=sys.stderr)
        return

    stdin_closed = False
    shutdown_requested = False
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
                shutdown_requested = True
                _shutdown_worker(events_path, reason="shutdown_cmd")
                break
            elif cmd == "stop":
                request_stop()
                emit({"type": "stopped", "job_id": job_id}, events_path)
            elif cmd == "cancel_automation":
                global _automation_cancel_requested
                _automation_cancel_requested = True
                request_stop()
                emit({"type": "automation_cancelled", "job_id": job_id}, events_path)
            elif cmd == "free_vram":
                try:
                    from dreamforge_engine import _free_comfy_vram

                    unload = bool(req.get("unload_models"))
                    _free_comfy_vram(unload_models=unload)
                    emit({"type": "vram_freed", "job_id": job_id}, events_path)
                except Exception as exc:
                    emit(
                        {
                            "type": "warning",
                            "job_id": job_id,
                            "message": f"VRAM cleanup note: {exc}",
                        },
                        events_path,
                    )
            elif cmd == "recover_comfy":
                try:
                    from dreamforge_comfy_server import restart_managed_comfy_server

                    reason = str(req.get("reason") or "recover_cmd")
                    unload = bool(req.get("unload_models"))
                    if unload:
                        from dreamforge_engine import _free_comfy_vram

                        _free_comfy_vram(unload_models=True)
                    server = restart_managed_comfy_server(timeout_s=90.0, reason=reason)
                    emit(
                        {
                            "type": "comfy_recovered",
                            "job_id": job_id,
                            "comfy_url": server.base_url,
                            "reason": reason,
                        },
                        events_path,
                    )
                except Exception as exc:
                    err = from_exception(exc, job_id=job_id)
                    emit(err, events_path)
            elif cmd == "benchmark":
                with _generation_lock:
                    if _generation_active:
                        emit(
                            {
                                "type": "benchmark_finished",
                                "job_id": job_id,
                                "success": False,
                                "result": generation_in_progress(job_id=job_id),
                            },
                            events_path,
                        )
                        continue
                    _generation_active = True
                params = req.get("params") or {}
                try:
                    from dreamforge_hardware_benchmark import run_generation_benchmark

                    result = run_generation_benchmark(
                        model=params.get("model"),
                        runs=params.get("runs", 5),
                        steps=params.get("steps", 4),
                        width=params.get("width", 512),
                        height=params.get("height", 512),
                    )
                    success = bool(
                        result.get("generation_executed")
                        and not result.get("error")
                        and result.get("summary", {}).get("all_outputs_valid")
                    )
                    emit(
                        {
                            "type": "benchmark_finished",
                            "job_id": job_id,
                            "success": success,
                            "result": result,
                        },
                        events_path,
                    )
                except Exception as exc:
                    err = from_exception(exc, job_id=job_id)
                    emit(
                        {
                            "type": "benchmark_finished",
                            "job_id": job_id,
                            "success": False,
                            "result": {"generation_executed": False, **err},
                        },
                        events_path,
                    )
                    traceback.print_exc(file=sys.stderr)
                finally:
                    with _generation_lock:
                        _generation_active = False
            elif cmd == "generate":
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
                    # Run in-process (do not use execute_job's nested queue — avoids extra
                    # threads and VRAM cleanup racing the managed Comfy server).
                    run_generation = _reload_generation_modules()

                    result = run_generation(
                        DreamForgeEngine._to_namespace(params),
                        params,
                        stream_sink=sink,
                        job_id=job_id,
                    )
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
                    try:
                        from dreamforge_engine import _free_comfy_vram

                        edit_type = str((params.get("edit_type") or params.get("cn_type") or "")).lower()
                        studio_mode = str(params.get("studio_mode") or "").lower()
                        unload = edit_type == "upscale" or studio_mode == "upscale"
                        _free_comfy_vram(unload_models=unload)
                    except Exception:
                        pass
            elif cmd == "run_automation":
                with _generation_lock:
                    if _generation_active:
                        emit(generation_in_progress(job_id=job_id), events_path)
                        continue
                    _generation_active = True

                _automation_cancel_requested = False
                spec = req.get("spec") or {}
                
                def automation_sink(evt: dict) -> None:
                    if job_id and "job_id" not in evt:
                        evt["job_id"] = job_id
                    emit(evt, events_path)

                try:
                    from dreamforge_automation import run_automation

                    result = run_automation(
                        spec,
                        stream_sink=automation_sink,
                        cancel_check=lambda: _automation_cancel_requested,
                    )
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
                    try:
                        from dreamforge_engine import _free_comfy_vram
                        _free_comfy_vram()
                    except Exception:
                        pass
            else:
                emit(invalid_request(f"unknown_cmd: {cmd}", job_id=job_id), events_path)
    except Exception as exc:
        err = from_exception(exc)
        emit({**err, "type": "worker_crashed"}, events_path)
        traceback.print_exc(file=sys.stderr)
    else:
        stdin_closed = True
    finally:
        if stdin_closed and not shutdown_requested:
            # Parent may close the pipe during a planned engine restart; brief grace
            # avoids racing a new worker spawn against Comfy teardown.
            time.sleep(0.75)
            emit(
                {
                    "type": "worker_shutdown",
                    "reason": "stdin_closed",
                    "message": "GPU worker stdin closed (engine restart or app exit)",
                },
                events_path,
            )
            print(
                "dreamforge worker: stdin closed, shutting down",
                file=sys.stderr,
            )
        stop_managed_comfy_server()


if __name__ == "__main__":
    serve()
