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


def _system_ram_gb() -> float | None:
    """Total physical RAM in GB, or None if unknown."""
    try:
        import psutil  # type: ignore

        return psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        pass
    try:
        import ctypes

        class _MEMORYSTATUSEX(ctypes.Structure):  # Windows fallback
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        info = _MEMORYSTATUSEX()
        info.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(info))  # type: ignore[attr-defined]
        return info.ullTotalPhys / (1024 ** 3)
    except Exception:
        return None


def _has_directml() -> bool:
    try:
        import torch_directml  # type: ignore  # noqa: F401

        return True
    except Exception:
        return False


def _gpu_vendor() -> str | None:
    """Best-effort GPU vendor string when CUDA is available."""
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        name = torch.cuda.get_device_name(0).lower()
        if "nvidia" in name or "geforce" in name or "rtx" in name or "gtx" in name or "tesla" in name or "quadro" in name:
            return "nvidia"
        if "amd" in name or "radeon" in name:
            return "amd"
        if "intel" in name or "arc" in name:
            return "intel"
        return name
    except Exception:
        return None


def _desktop_worker_argv() -> list[str]:
    """Pick a sensible set of worker CLI flags from detected hardware.

    Priority:
      1. ``DREAMFORGE_DESKTOP_VRAM_MODE`` (forced profile from the UI).
      2. ``DREAMFORGE_CPU_ONLY=1`` -> ``--cpu``.
      3. Auto-detect CUDA / MPS / DirectML, with a system-RAM-aware fallback.

    Additional helper flags such as ``--cpu-vae`` are appended on 6-8 GB
    NVIDIA cards because Flux/SDXL VAE decode is a known OOM spike there.
    Users can disable that via ``DREAMFORGE_NO_CPU_VAE=1``.

    Power users can append arbitrary extra flags via
    ``DREAMFORGE_EXTRA_WORKER_ARGS`` (space separated, e.g.
    ``"--cache-none --reserve-vram 1"``).
    """
    extras: list[str] = []
    raw_extra = os.environ.get("DREAMFORGE_EXTRA_WORKER_ARGS", "").strip()
    if raw_extra:
        extras.extend(raw_extra.split())

    if os.environ.get("DREAMFORGE_CPU_ONLY") in {"1", "true", "yes"}:
        return ["--cpu", *extras]

    forced = _normalize_vram_arg(os.environ.get("DREAMFORGE_DESKTOP_VRAM_MODE"))
    if forced:
        argv = [forced]
        # For aggressive low-VRAM modes, also push the VAE to CPU unless the
        # user opted out. Tiny speed hit, but prevents the classic VAE OOM
        # spike on 6-8 GB cards while decoding 1024px.
        if forced in {"--lowvram", "--novram"} and os.environ.get("DREAMFORGE_NO_CPU_VAE") not in {"1", "true", "yes"}:
            argv.append("--cpu-vae")
        argv.extend(extras)
        return argv

    try:
        import torch
    except ImportError:
        return ["--cpu", *extras]

    if torch.cuda.is_available():
        try:
            total_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        except Exception:
            total_gb = 0.0
        sys_ram = _system_ram_gb()
        # If the user has very little system RAM, even a healthy GPU will
        # struggle to load Flux + T5 + VAE. Bias toward --lowvram / --cpu-vae.
        ram_tight = sys_ram is not None and sys_ram < 16

        # Reserve a sliver of VRAM for the OS / desktop compositor unless the
        # user already provided their own --reserve-vram via extras.
        reserve_args: list[str] = []
        if not any(a == "--reserve-vram" for a in extras):
            if total_gb < 6:
                reserve_args = ["--reserve-vram", "0.3"]
            elif total_gb < 12:
                reserve_args = ["--reserve-vram", "0.6"]
            else:
                reserve_args = ["--reserve-vram", "1.0"]

        if total_gb >= 14:
            return ["--normalvram", *reserve_args, *extras]
        if total_gb >= 10:
            return ["--normalvram", *reserve_args, *extras]
        if total_gb >= 8:
            argv = ["--lowvram"]
            if ram_tight or os.environ.get("DREAMFORGE_NO_CPU_VAE") not in {"1", "true", "yes"}:
                argv.append("--cpu-vae")
            argv.extend(reserve_args)
            argv.extend(extras)
            return argv
        if total_gb >= 6:
            argv = ["--lowvram", "--cpu-vae"]
            argv.extend(reserve_args)
            argv.extend(extras)
            return argv
        # < 6 GB VRAM: very aggressive offload.
        return ["--novram", "--cpu-vae", *reserve_args, *extras]

    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return ["--normalvram", *extras]

    if os.name == "nt" and _has_directml():
        # Falls back through Comfy's directml path; Comfy decides offload.
        return ["--directml", *extras]

    return ["--cpu", *extras]


def _namespace_from_dict(data: dict) -> SimpleNamespace:
    return SimpleNamespace(**data)


def serve() -> None:
    configure_stdio()
    os.environ["DREAMFORGE_HEADLESS"] = "1"
    try:
        from dreamforge_comfy_memory import enable_aimdo_mmap_loading

        enable_aimdo_mmap_loading()
    except Exception:
        pass
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
