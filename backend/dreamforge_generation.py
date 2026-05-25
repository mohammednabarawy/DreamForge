"""
Shared headless DreamForge generation for CLI and DreamForge desktop worker.
Matches DreamForge webui.py preview loop (task_result + preview.jpg).
"""
from __future__ import annotations

import base64
import importlib
import json

# Suppress duplicate-ObjC-class warnings from cv2/av FFmpeg conflict
import os
os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")
import random
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

from _paths import BACKEND_ROOT, COMFY_ROOT, PROJECT_ROOT, REPOS_ROOT, extend_sys_path

_RUNTIME_READY = False


def _attach_inpaint_mask(gen_data: dict, image_path: str, mask_path: str) -> None:
    """Build inpaint_view layers expected by modules/image_pipeline.py."""
    from dreamforge_paths import resolve_image_path_or_raise

    main_path = resolve_image_path_or_raise(image_path)
    mask_resolved = resolve_image_path_or_raise(mask_path)
    main = Image.open(main_path).convert("RGB")
    mask_img = Image.open(mask_resolved).convert("L")
    if mask_img.size != main.size:
        mask_img = mask_img.resize(main.size, Image.Resampling.LANCZOS)
    rgba = main.copy()
    rgba.putalpha(mask_img)
    gen_data["inpaint_toggle"] = True
    gen_data["main_view"] = str(main_path)
    gen_data["inpaint_view"] = {"layers": [np.asarray(rgba)]}

# Encourage CUDA's caching allocator to release fragmented blocks back to the
# driver: this is the single biggest knob for OOM resilience on Windows and is
# the Fooocus/Forge recommendation.  Users can still override via env.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

from dreamforge_errors import (
    disk_full,
    from_exception,
    invalid_input_image,
    missing_input_image,
    missing_model_dependencies,
    out_of_memory,
)
from dreamforge_preflight import run_preflight
from dreamforge_progress import (
    boot_label,
    boot_phase_from_message,
    generation_label,
    generation_phase_from_preview,
    gpu_telemetry,
)


def _report_boot(progress, message: str, **extra) -> None:
    if progress is None:
        return
    phase = extra.pop("phase", None) or boot_phase_from_message(message)
    payload = {
        "type": "boot_progress",
        "phase": phase,
        "message": boot_label(phase, message),
        **extra,
    }
    if callable(progress):
        progress(payload)
    else:
        emit_event(progress, payload)


def _gpu_backend_label() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "CUDA"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "MPS (Apple Silicon)"
    except ImportError:
        pass
    return "CPU"

def _ensure_deps(progress=None):
    """Install missing core dependencies and clone git repos on first launch."""
    _report_boot(progress, "Checking Python dependencies...")
    missing = []
    for pkg in ("torch", "transformers", "diffusers", "safetensors", "numpy", "PIL"):
        try:
            __import__(pkg)
        except ImportError:
            pip_name = "Pillow" if pkg == "PIL" else pkg
            missing.append(pip_name)
    if missing:
        _report_boot(progress, f"Installing missing packages: {', '.join(missing)}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing
        )

    _report_boot(progress, "Checking ComfyUI repositories...")
    repos_dir = BACKEND_ROOT / "repositories"
    comfy_dir = repos_dir / "ComfyUI"
    if not comfy_dir.is_dir() or not any(comfy_dir.iterdir()):
        _report_boot(progress, "Cloning ComfyUI repository (one-time setup)...")
        try:
            from modules.launch_util import git_clone
            git_clone(
                "https://github.com/comfyanonymous/ComfyUI",
                str(comfy_dir),
                "ComfyUI",
                hash="c9589f29b21fc5f73b6eb9d5c98d29a68cf8c392",
            )
            if not comfy_dir.is_dir() or not any(comfy_dir.iterdir()):
                raise RuntimeError("Repository clone verification failed.")
        except Exception as exc:
            _report_boot(progress, f"ERROR: Could not clone ComfyUI: {exc}")
            raise RuntimeError(f"Could not clone ComfyUI: {exc}") from exc

    deps_marker = BACKEND_ROOT / ".dreamforge_comfy_deps_ok"
    req_file = comfy_dir / "requirements.txt"
    if deps_marker.is_file():
        _report_boot(progress, "ComfyUI dependencies OK (skipped reinstall)")
    elif req_file.is_file():
        _report_boot(progress, "Installing ComfyUI Python dependencies (one-time, may take a few minutes)...")
        stop = threading.Event()

        def pip_pulse() -> None:
            tick = 0
            while not stop.wait(15.0):
                tick += 15
                _report_boot(
                    progress,
                    f"Still installing ComfyUI dependencies ({tick}s)...",
                )

        pulse = threading.Thread(target=pip_pulse, daemon=True)
        pulse.start()
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--quiet", "-r", str(req_file)]
            )
            deps_marker.write_text("ok\n", encoding="utf-8")
        finally:
            stop.set()

def _load_generation_stack(progress=None):
    """Import torch + async_worker with visible progress (slow on first launch)."""
    _report_boot(progress, f"Loading PyTorch and {_gpu_backend_label()}...")
    try:
        import torch  # noqa: F401
    except ImportError as exc:
        _report_boot(progress, f"ERROR: PyTorch not installed ({exc}). Install with: pip install torch torchvision torchaudio")
        raise

    _report_boot(progress, "Loading ComfyUI and generation modules...")
    stop = threading.Event()

    def pulse() -> None:
        tick = 0
        while not stop.wait(10.0):
            tick += 10
            _report_boot(
                progress,
                f"Still loading generation pipeline ({tick}s)... "
                "First launch can take 1-3 minutes.",
            )

    pulse_thread = threading.Thread(target=pulse, daemon=True)
    pulse_thread.start()
    try:
        return importlib.import_module("modules.async_worker")
    finally:
        stop.set()


def boot_headless(
    extra_dreamforge_argv: list[str] | None = None,
    *,
    progress=None,
) -> dict:
    """Initialize DreamForge runtime once (slow). Returns paths and status."""
    global _RUNTIME_READY
    if _RUNTIME_READY:
        return {"ready": True, "cached": True}

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    extend_sys_path()

    argv = list(extra_dreamforge_argv or [])
    if "--offline" not in argv:
        argv.append("--offline")
    sys.argv = [sys.argv[0] if sys.argv else "dreamforge_generation.py", *argv]
    os.chdir(BACKEND_ROOT)
    os.environ["DREAMFORGE_HEADLESS"] = "1"

    _ensure_deps(progress)
    _report_boot(progress, "Loading DreamForge settings and paths...")
    _report_boot(progress, "Reading configuration and model folders...")
    import shared  # noqa: F401

    class MockGradio:
        local_url = "headless"
        server_name = "localhost"
        server_port = "0"
        share = False

    shared.gradio_root = MockGradio()
    _load_generation_stack(progress)

    _RUNTIME_READY = True
    from shared import path_manager

    preview = path_manager.model_paths["temp_preview_path"]
    info = {
        "ready": True,
        "preview_path": str(preview),
        "project_root": str(PROJECT_ROOT),
        "boot_phase": "ready",
        **gpu_telemetry(),
    }
    if progress is not None:
        _report_boot(progress, "Engine ready", phase="ready")
    return info


def preview_path() -> Path:
    boot_headless()
    from shared import path_manager

    return Path(path_manager.model_paths["temp_preview_path"])


def _preview_stream_payload(product) -> dict:
    percentage, title, image_path = product
    try:
        default_preview = preview_path()
    except Exception:
        default_preview = None
    payload = {
        "type": "preview",
        "percentage": int(percentage) if percentage is not None else -1,
        "title": str(title or ""),
    }
    if default_preview:
        payload["preview_path"] = str(default_preview)
    read_path = image_path
    if not read_path:
        read_path = default_preview
    if read_path:
        path = Path(read_path)
        for _ in range(8):
            try:
                if path.is_file() and path.stat().st_size > 128:
                    raw = path.read_bytes()
                    payload["image_mime"] = "image/jpeg"
                    payload["image_b64"] = base64.b64encode(raw).decode("ascii")
                    payload["preview_path"] = str(path)
                    break
            except OSError:
                time.sleep(0.03)
    return payload


def emit_event(sink, payload: dict) -> None:
    if sink is None:
        return
    if callable(sink):
        sink(payload)
        return
    path = Path(sink)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        handle.flush()


def run_generation(
    base_args,
    data=None,
    *,
    stream_sink=None,
    job_id: str | None = None,
) -> dict:
    """Run one generation; stream_sink is filepath or callable for JSON events."""
    boot_headless()
    import modules.async_worker as worker
    from dreamforge_cli_direct import (
        _auto_settings,
        _compile_job,
        _load_input_image,
        _parse_loras,
        _resolve_output_paths,
        default_manifest_path,
        write_manifest,
        validate_image,
    )
    from dreamforge_cli_inventory import check_model_dependencies

    try:
        job, model, prompt, negative, width, height, _brand_kit = _compile_job(base_args, data)
        settings = _apply_job_performance(
            _auto_settings(model, job, width, height, negative),
            job,
        )
        if getattr(job, "clip_skip", None) is not None:
            try:
                settings["clip_skip"] = int(job.clip_skip)
            except (TypeError, ValueError):
                pass
        seed = int(getattr(job, "seed", -1))
        if seed == -1:
            seed = random.randint(0, 2**31 - 1)

        missing_deps = check_model_dependencies(model)
        if missing_deps:
            err = missing_model_dependencies(missing_deps, job_id=job_id)
            emit_event(stream_sink, err)
            return {"status": "error", **err}

        # Preflight: cheap checks that prevent wasted boot/sample time.
        preflight = run_preflight(model, job_id=job_id)
        for warning_evt in preflight.warnings:
            emit_event(stream_sink, warning_evt)
        if preflight.has_errors:
            first_err = preflight.errors[0]
            emit_event(stream_sink, first_err)
            return {"status": "error", **first_err}

        input_path = getattr(job, "input_image", None) or getattr(job, "upscale_image", None)
        cn_selection = getattr(job, "cn_selection", None) or "None"
        cn_type = getattr(job, "cn_type", None) or "None"
        edit_type = getattr(job, "edit_type", "auto")
        model_family = str(model.get("family") or "").lower()
        use_case = str(getattr(job, "use_case", "none") or "none").lower()

        if not input_path:
            if cn_selection == "Custom...":
                cn_selection = "None"
                cn_type = "None"
            if edit_type in ("kontext", "inpaint", "img2img", "qwen_edit"):
                edit_type = "auto"
            needs_reference = model_family in ("flux_kontext", "qwen_image_edit")
            if needs_reference:
                err = missing_input_image(job_id=job_id)
                emit_event(stream_sink, err)
                return {"status": "error", **err}
        elif cn_selection == "None" and getattr(job, "upscale_image", None):
            cn_selection = "Custom..."
            cn_type = "upscale"
        elif cn_selection == "None" and input_path:
            if edit_type == "kontext" or model_family == "flux_kontext":
                cn_selection = "None"
                cn_type = "None"
            else:
                cn_selection = "Custom..."
                if edit_type != "auto":
                    cn_type = edit_type
                else:
                    cn_type = "img2img"
        elif input_path and cn_selection == "Custom...":
            if getattr(job, "upscale_image", None):
                cn_type = "upscale"
            elif edit_type == "kontext" or model_family == "flux_kontext":
                # img2img blocks Flux Kontext auto-routing in the pipeline.
                cn_selection = "None"
                cn_type = "None"
            elif edit_type not in ("auto", "None", None, ""):
                cn_type = edit_type

        loaded_input_image = None
        if input_path:
            try:
                from dreamforge_paths import resolve_image_path_or_raise

                resolved_input_path = resolve_image_path_or_raise(input_path)
                input_path = str(resolved_input_path)
                loaded_input_image = _load_input_image(input_path)
            except (FileNotFoundError, ValueError, OSError) as exc:
                err = invalid_input_image(
                    str(exc), path=str(input_path) if input_path else None, job_id=job_id
                )
                emit_event(stream_sink, err)
                return {"status": "error", **err}

        streaming = stream_sink is not None
        gen_data = {
            "task_type": "process",
            "image_total": int(getattr(job, "image_number", 1) or 1),
            "image_number": int(getattr(job, "image_number", 1) or 1),
            "generate_forever": int(getattr(job, "image_number", 1) or 1) == 0,
            "base_model_name": model["engine_name"],
            "prompt": prompt,
            "negative": settings["negative"],
            "style_selection": settings["styles"],
            "cfg": settings["cfg"],
            "custom_steps": settings["steps"],
            "performance_selection": settings.get("performance_selection", "Custom..."),
            "aspect_ratios_selection": "Custom...",
            "custom_width": settings["width"],
            "custom_height": settings["height"],
            "sampler_name": settings["sampler_name"],
            "scheduler": settings["scheduler"],
            "clip_skip": settings["clip_skip"],
            "loras": _parse_loras(getattr(job, "lora", [])),
            "cn_selection": cn_selection,
            "cn_type": cn_type,
            "cn_edge_low": 0.1,
            "cn_edge_high": 0.9,
            "cn_start": 0.0,
            "cn_stop": 1.0,
            "cn_strength": 0.75,
            "cn_upscale": getattr(job, "upscale_method", "2x"),
            "seed": seed,
            "input_image": loaded_input_image,
        }
        if not streaming:
            gen_data["silent"] = True

        lora_keywords = getattr(job, "lora_keywords", None)
        if lora_keywords:
            gen_data["lora_keywords"] = str(lora_keywords)
        if getattr(job, "auto_negative_prompt", None) or getattr(job, "auto_negative", None):
            gen_data["auto_negative"] = True

        mask_path = getattr(job, "inpaint_mask_path", None)
        if mask_path and cn_type == "inpaint" and input_path:
            try:
                _attach_inpaint_mask(gen_data, str(input_path), str(mask_path))
            except OSError as exc:
                err = invalid_input_image(
                    f"inpaint mask: {exc}",
                    path=str(mask_path),
                    job_id=job_id,
                )
                emit_event(stream_sink, err)
                return {"status": "error", **err}

        if streaming:
            emit_event(
                stream_sink,
                {
                    "type": "started",
                    "job_id": job_id,
                    "title": "Loading models…",
                    "percentage": 0,
                },
            )
            emit_event(
                stream_sink,
                {
                    "type": "progress",
                    "job_id": job_id,
                    "phase": "loading_models",
                    "progress": 0,
                    "message": "Loading models…",
                },
            )

        task_id = worker.add_task(gen_data)
        finished = False
        flag = None
        product = None

        def _oom_payload() -> dict:
            free_gb = None
            try:
                import torch  # local import; torch is loaded by this point
                if torch.cuda.is_available():
                    free, _total = torch.cuda.mem_get_info()
                    free_gb = free / (1024 ** 3)
                    torch.cuda.empty_cache()
            except Exception:
                pass
            return out_of_memory(
                free_gb=free_gb,
                vram_profile=os.environ.get("DREAMFORGE_DESKTOP_VRAM_MODE"),
                job_id=job_id,
            )

        while not finished:
            try:
                flag, product = worker.task_result(task_id)
            except MemoryError as exc:
                err = _oom_payload()
                err.setdefault("details", {})["exception"] = f"MemoryError: {exc}"
                emit_event(stream_sink, err)
                return {"status": "error", **err}
            except OSError as exc:
                if getattr(exc, "errno", None) == 28:  # ENOSPC
                    err = disk_full(str(exc), path=getattr(exc, "filename", None), job_id=job_id)
                else:
                    err = from_exception(exc, job_id=job_id)
                emit_event(stream_sink, err)
                return {"status": "error", **err}
            except Exception as exc:  # pragma: no cover - covered by from_exception logic
                if "out of memory" in str(exc).lower() or "OutOfMemoryError" in type(exc).__name__:
                    err = _oom_payload()
                    err.setdefault("details", {})["exception"] = f"{type(exc).__name__}: {exc}"
                else:
                    err = from_exception(exc, job_id=job_id)
                emit_event(stream_sink, err)
                return {"status": "error", **err}

            if flag is None:
                time.sleep(0.08)
                continue
            if flag == "preview":
                evt = _preview_stream_payload(product)
                if job_id:
                    evt["job_id"] = job_id
                emit_event(stream_sink, evt)
                pct = evt.get("percentage")
                title = evt.get("title")
                phase = generation_phase_from_preview(
                    int(pct) if pct is not None else None,
                    str(title) if title else None,
                )
                progress_pct = max(0, min(100, int(pct))) if pct is not None and int(pct) >= 0 else 0
                emit_event(
                    stream_sink,
                    {
                        "type": "progress",
                        "job_id": job_id,
                        "phase": phase,
                        "progress": progress_pct,
                        "message": generation_label(phase, str(title) if title else None),
                    },
                )
            elif flag == "results":
                raw_images = [str(p) for p in (product or [])]
                images = _resolve_output_paths(raw_images, getattr(job, "output", None))
                done_evt = {
                    "type": "results",
                    "job_id": job_id,
                    "paths": images,
                    "raw_paths": raw_images,
                }
                emit_event(stream_sink, done_evt)
                finished = True
            else:
                err = from_exception(
                    RuntimeError(f"Worker returned flag: {flag}"),
                    job_id=job_id,
                )
                emit_event(stream_sink, err)
                return {"status": "error", **err}

        validation = []
        if getattr(job, "validate_output", False):
            validation = [
                validate_image(
                    path,
                    settings["width"],
                    settings["height"],
                    check_fake_text=getattr(job, "check_fake_text", False),
                )
                for path in images
            ]

        manifest_path = None
        if not getattr(job, "no_manifest", False):
            manifest_path = getattr(job, "manifest_path", None) or default_manifest_path(
                images,
                str(PROJECT_ROOT / "outputs"),
            )
            if not Path(manifest_path).is_absolute():
                manifest_path = str(PROJECT_ROOT / manifest_path)
            manifest_path = write_manifest(
                manifest_path,
                {
                    "schema_version": "1.1",
                    "prompt": prompt,
                    "negative_prompt": settings["negative"],
                    "seed": seed,
                    "model": model,
                    "settings": settings,
                    "images": images,
                    "raw_images": raw_images,
                    "validation": validation,
                },
            )

        return {
            "status": "success",
            "images": [{"path": path} for path in images],
            "seed": seed,
            "model": model,
            "settings": settings,
            "validation": validation,
            "manifest": manifest_path,
        }
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        err = from_exception(exc, job_id=job_id)
        emit_event(stream_sink, err)
        return {"status": "error", **err}


_GENERIC_SDXL_PRESETS = frozenset({"Speed", "Quality", "Lightning", "Lcm", "Pony XL"})
_FAMILY_PRESETS = frozenset({"Flux", "HiDream", "HiDream Full", "SD3"})


def _coerce_performance_preset(requested: str | None, family_preset: str | None) -> str | None:
    """Avoid applying SDXL Speed/Quality presets to Flux, HiDream, SD3, etc."""
    if not requested:
        return family_preset
    if requested in _GENERIC_SDXL_PRESETS and family_preset in _FAMILY_PRESETS:
        return family_preset
    return requested


def _apply_job_performance(settings: dict, job) -> dict:
    """Honor DreamForge performance dropdown (Speed, Quality, Flux, …)."""
    out = dict(settings)
    family_preset = out.get("performance_selection")
    requested = getattr(job, "performance", None)
    perf = _coerce_performance_preset(
        requested if requested else None,
        family_preset if isinstance(family_preset, str) else None,
    )
    if not perf:
        return out
    out["performance_selection"] = perf
    if perf == "Custom...":
        return out
    try:
        from modules.performance import PerformanceSettings

        opts = PerformanceSettings().get_perf_options(perf)
        out["steps"] = int(opts.get("custom_steps", out["steps"]))
        out["cfg"] = float(opts.get("cfg", out["cfg"]))
        out["sampler_name"] = opts.get("sampler_name", out["sampler_name"])
        out["scheduler"] = opts.get("scheduler", out["scheduler"])
        out["clip_skip"] = int(opts.get("clip_skip", out.get("clip_skip", 1)))
    except (KeyError, TypeError, ValueError):
        pass
    return out


def request_stop() -> None:
    boot_headless()
    import modules.async_worker as worker

    worker.interrupt_dreamforge_processing = True
