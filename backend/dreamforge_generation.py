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
    GEN_PREPARING,
    GEN_SAMPLING,
    boot_label,
    boot_phase_from_message,
    generation_label,
    generation_phase_from_preview,
    gpu_telemetry,
)


def _clamp_float(value, default: float, low: float, high: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, parsed))


def _pil_to_png_bytes(image: Image.Image) -> bytes:
    from io import BytesIO

    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


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
    try:
        from dreamforge_comfy_memory import enable_aimdo_mmap_loading

        if enable_aimdo_mmap_loading():
            _report_boot(progress, "Large-model mmap loader enabled (comfy-aimdo)")
    except Exception:
        pass
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
                    payload["preview_path"] = str(path)
                    payload["has_preview"] = True
                    payload["live"] = True
                    # Inline only small step previews; large JPEGs are mmap'd by the shell.
                    if path.stat().st_size < 400_000:
                        raw = path.read_bytes()
                        payload["image_mime"] = "image/jpeg"
                        payload["image_b64"] = base64.b64encode(raw).decode("ascii")
                    break
            except OSError:
                time.sleep(0.03)
    return payload


def _routing_model_blob(model: dict | None) -> str:
    """Stable string for Flux/Kontext routing (matches Krita-style path + caption checks)."""
    if not model:
        return ""
    parts = (
        model.get("engine_name"),
        model.get("name"),
        model.get("relative_path"),
        model.get("caption"),
    )
    return " ".join(str(p) for p in parts if p).lower()


def _checkpoint_is_flux_kontext(model: dict | None, model_family: str) -> bool:
    """True when weights are Flux.1 Kontext edit models (not base Flux img2img)."""
    fam = (model_family or "").lower()
    if fam == "flux_kontext":
        return True
    blob = _routing_model_blob(model)
    if fam == "flux" and "kontext" in blob:
        return True
    # Split diffusion filenames / UI captions sometimes differ; keep explicit tokens.
    hints = (
        "flux-kontext",
        "flux_kontext",
        "flux1-kontext",
        "flux.1-kontext",
        "kontext-dev",
        "flux.1 kontext",
    )
    return fam.startswith("flux") and any(h in blob for h in hints)


def _coerce_reference_image_paths(job) -> list[str]:
    from dreamforge_comfy_workflow_import import coerce_reference_image_paths

    return coerce_reference_image_paths(job)


def _comfy_workflow_mode(
    *,
    input_filename: str | None,
    cn_type: str,
    model: dict,
    model_family: str,
) -> str:
    from dreamforge_comfy_workflow_import import comfy_workflow_mode

    return comfy_workflow_mode(
        input_filename=input_filename,
        cn_type=str(cn_type or ""),
        model=model,
        model_family=model_family,
        checkpoint_is_flux_kontext=_checkpoint_is_flux_kontext,
    )


def _build_comfy_prompt_graph(
    *,
    job,
    mode: str,
    model: dict,
    model_family: str,
    settings: dict,
    prompt: str,
    negative: str,
    seed: int,
    edit_strength: float,
    cn_upscale: str,
    input_filename: str | None,
    mask_filename: str | None,
    reference_stitch_filename: str | None,
    grow_mask_by: int,
    model_loader_args: dict | None = None,
):
    from dreamforge_comfy_workflow_import import (
        build_prompt_from_template,
        resolve_comfy_workflow_template,
    )
    from dreamforge_comfy_workflows import (
        comfy_flux_dev_txt2img,
        comfy_flux_kontext_edit,
        comfy_img2img_basic,
        comfy_inpaint_basic,
        comfy_txt2img_basic,
        comfy_upscale_basic,
    )

    explicit = getattr(job, "comfy_workflow_api", None) or getattr(
        job, "comfy_workflow_path", None
    )
    template_path = resolve_comfy_workflow_template(mode=mode, explicit_path=explicit)
    ckpt_name = model.get("name") or model.get("engine_name")
    loader_args = {
        "category": model.get("category") or "checkpoints",
        "relative_path": model.get("relative_path") or model.get("name") or ckpt_name,
        "family": model_family,
        "ckpt_name": ckpt_name,
    }
    if model_loader_args:
        loader_args.update(model_loader_args)
    bindings = {
        **loader_args,
        "prompt": prompt,
        "negative": negative,
        "steps": settings["steps"],
        "cfg": settings["cfg"],
        "sampler_name": settings["sampler_name"],
        "scheduler": settings["scheduler"],
        "seed": seed,
        "denoise": edit_strength,
        "width": settings["width"],
        "height": settings["height"],
        "filename_prefix": "DreamForge",
        "upscale_model": cn_upscale,
        "grow_mask_by": grow_mask_by,
    }
    if input_filename:
        bindings["image"] = input_filename
    if mask_filename:
        bindings["mask"] = mask_filename
    if reference_stitch_filename:
        bindings["reference_stitch"] = reference_stitch_filename
    if template_path:
        return build_prompt_from_template(template_path, bindings), str(template_path)

    if input_filename:
        if mode == "upscale":
            graph = comfy_upscale_basic(
                {
                    "image": input_filename,
                    "upscale_model": cn_upscale,
                    "filename_prefix": "DreamForge",
                }
            )
        elif mode == "inpaint" and mask_filename:
            graph = comfy_inpaint_basic(
                {
                    **loader_args,
                    "image": input_filename,
                    "mask": mask_filename,
                    "prompt": prompt,
                    "negative": negative,
                    "steps": settings["steps"],
                    "cfg": settings["cfg"],
                    "sampler_name": settings["sampler_name"],
                    "scheduler": settings["scheduler"],
                    "seed": seed,
                    "denoise": edit_strength,
                    "grow_mask_by": grow_mask_by,
                    "filename_prefix": "DreamForge",
                }
            )
        elif mode == "kontext":
            graph = comfy_flux_kontext_edit(
                {
                    **loader_args,
                    "image": input_filename,
                    "reference_stitch": reference_stitch_filename or input_filename,
                    "prompt": prompt,
                    "negative": negative,
                    "steps": settings["steps"],
                    "guidance": settings["cfg"],
                    "sampler_name": settings["sampler_name"],
                    "scheduler": settings["scheduler"],
                    "seed": seed,
                    "denoise": edit_strength,
                    "filename_prefix": "DreamForge",
                }
            )
        else:
            graph = comfy_img2img_basic(
                {
                    "ckpt_name": ckpt_name,
                    **loader_args,
                    "image": input_filename,
                    "prompt": prompt,
                    "negative": negative,
                    "steps": settings["steps"],
                    "cfg": settings["cfg"],
                    "sampler_name": settings["sampler_name"],
                    "scheduler": settings["scheduler"],
                    "seed": seed,
                    "denoise": edit_strength,
                    "filename_prefix": "DreamForge",
                }
            )
    elif (model_family or "").startswith("flux"):
        graph = comfy_flux_dev_txt2img(
            {
                **loader_args,
                "prompt": prompt,
                "negative": negative,
                "width": settings["width"],
                "height": settings["height"],
                "steps": settings["steps"],
                "guidance": settings["cfg"],
                "sampler_name": settings["sampler_name"],
                "scheduler": settings["scheduler"],
                "seed": seed,
                "filename_prefix": "DreamForge",
            }
        )
    else:
        graph = comfy_txt2img_basic(
            {
                **loader_args,
                "prompt": prompt,
                "negative": negative,
                "width": settings["width"],
                "height": settings["height"],
                "steps": settings["steps"],
                "cfg": settings["cfg"],
                "sampler_name": settings["sampler_name"],
                "scheduler": settings["scheduler"],
                "seed": seed,
                "filename_prefix": "DreamForge",
            }
        )
    return graph, None


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
    from dreamforge_cli_direct import (
        _auto_settings,
        _compile_job,
        _resolve_output_paths,
        default_manifest_path,
        write_manifest,
        validate_image,
    )
    from dreamforge_cli_inventory import check_model_dependencies

    extend_sys_path()
    os.chdir(BACKEND_ROOT)

    try:
        job, model, prompt, negative, width, height, _brand_kit = _compile_job(base_args, data)
        model_family = str(model.get("family") or "").lower()
        settings = _tune_edit_job_settings(
            _apply_job_performance(
                _auto_settings(model, job, width, height, negative),
                job,
            ),
            job,
            model_family,
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

        explicit_input_path = getattr(job, "input_image", None)
        upscale_input_path = getattr(job, "upscale_image", None)
        cn_selection = getattr(job, "cn_selection", None) or "None"
        cn_type = getattr(job, "cn_type", None) or "None"
        edit_type = getattr(job, "edit_type", "auto")
        # Desktop state can briefly carry both input_image and a stale upscale_image
        # when switching modes. An explicit edit input must win so Kontext/inpaint
        # jobs do not silently become "upscale the original image".
        is_upscale_job = bool(upscale_input_path) and not explicit_input_path
        input_path = explicit_input_path or upscale_input_path
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
        elif cn_selection == "None" and is_upscale_job:
            cn_selection = "Custom..."
            cn_type = "upscale"
        elif cn_selection == "None" and input_path:
            # Studio Edit tab uses edit_type "kontext" for generic contextual edit; force Comfy
            # kontext/ReferenceLatent routing only for real Kontext checkpoints (Krita convention).
            if _checkpoint_is_flux_kontext(model, model_family):
                cn_selection = "None"
                cn_type = "None"
            else:
                cn_selection = "Custom..."
                if edit_type not in ("auto", "kontext", "None", None, ""):
                    cn_type = edit_type
                else:
                    cn_type = "img2img"
        elif input_path and cn_selection == "Custom...":
            if is_upscale_job:
                cn_type = "upscale"
            elif _checkpoint_is_flux_kontext(model, model_family):
                # cn_type img2img would skip ReferenceLatent and break Flux Kontext UNets.
                cn_selection = "None"
                cn_type = "None"
            elif edit_type not in ("auto", "None", None, ""):
                cn_type = edit_type

        if input_path:
            try:
                from dreamforge_paths import resolve_image_path_or_raise

                resolved_input_path = resolve_image_path_or_raise(input_path)
                input_path = str(resolved_input_path)
            except (FileNotFoundError, ValueError, OSError) as exc:
                err = invalid_input_image(
                    str(exc), path=str(input_path) if input_path else None, job_id=job_id
                )
                emit_event(stream_sink, err)
                return {"status": "error", **err}

        streaming = stream_sink is not None
        edit_strength = _clamp_float(
            getattr(job, "edit_strength", None),
            1.0 if _checkpoint_is_flux_kontext(model, model_family) else 0.75,
            0.0,
            1.0,
        )
        try:
            from dreamforge_krita_resources import resolve_upscaler

            upscale_info = resolve_upscaler(getattr(job, "upscale_method", None))
            cn_upscale = upscale_info["filename"]
        except ImportError:
            cn_upscale = getattr(job, "upscale_method", "OmniSR_X2_DIV2K.safetensors")
        mask_path = getattr(job, "inpaint_mask_path", None)

        if streaming:
            emit_event(
                stream_sink,
                {
                    "type": "started",
                    "job_id": job_id,
                    "title": "Submitting to ComfyUI…",
                    "percentage": 0,
                },
            )
            emit_event(
                stream_sink,
                {
                    "type": "progress",
                    "job_id": job_id,
                    "phase": "sampling",
                    "progress": 0,
                    "message": "Submitting workflow to ComfyUI…",
                },
            )

        from dreamforge_comfy_server import ensure_comfy_running
        from dreamforge_comfy_client import ComfyClient
        from dreamforge_comfy_models import (
            ComfyModelResolutionError,
            resolve_comfy_model_loader_args,
        )
        from dreamforge_krita_resources import (
            composite_inpaint_result,
            inpaint_mask_recipe_values,
            prepare_inpaint_mask_bytes,
            stitch_kontext_reference_images,
        )

        server = ensure_comfy_running(timeout_s=60.0)
        client = ComfyClient(server.base_url)

        try:
            resolved_loaders = resolve_comfy_model_loader_args(
                client,
                model=model,
                model_family=model_family,
            )
        except ComfyModelResolutionError as exc:
            err = {
                "type": "error",
                "code": "comfy_models_unavailable",
                "message": str(exc),
                "job_id": job_id,
                "recoverable": True,
                "suggestions": list(exc.suggestions),
            }
            emit_event(stream_sink, err)
            return {"status": "error", **err}

        inpaint_recipe = inpaint_mask_recipe_values(
            str(getattr(job, "edit_type", "inpaint") or "inpaint")
        )
        grow_mask_by = int(inpaint_recipe["inpaint_mask_grow_by"])
        inpaint_mask_img = None

        input_filename = None
        if input_path:
            local_name = Path(str(input_path)).name
            upload = client.upload_image(
                image_bytes=Path(str(input_path)).read_bytes(),
                filename=local_name,
                folder_type="input",
                overwrite=True,
            )
            input_filename = str(upload.get("name") or local_name)

        reference_stitch_filename = None
        extra_reference_paths = _coerce_reference_image_paths(job)
        if extra_reference_paths and input_path:
            try:
                from dreamforge_paths import resolve_image_path_or_raise

                main_img = Image.open(
                    resolve_image_path_or_raise(str(input_path))
                ).convert("RGB")
                extras = [
                    Image.open(resolve_image_path_or_raise(path)).convert("RGB")
                    for path in extra_reference_paths
                ]
                stitched = stitch_kontext_reference_images([main_img, *extras])
                stitch_name = f"{Path(str(input_path)).stem}_kontext_refs.png"
                stitch_upload = client.upload_image(
                    image_bytes=_pil_to_png_bytes(stitched),
                    filename=stitch_name,
                    folder_type="input",
                    overwrite=True,
                )
                reference_stitch_filename = str(stitch_upload.get("name") or stitch_name)
            except OSError as exc:
                err = invalid_input_image(
                    f"reference image: {exc}",
                    path=str(extra_reference_paths),
                    job_id=job_id,
                )
                emit_event(stream_sink, err)
                return {"status": "error", **err}

        mask_filename = None
        if cn_type == "inpaint" and mask_path and input_path:
            try:
                from dreamforge_paths import resolve_image_path_or_raise

                main_path = resolve_image_path_or_raise(str(input_path))
                mask_resolved = resolve_image_path_or_raise(str(mask_path))
                main_size = Image.open(main_path).size
                mask_bytes, inpaint_mask_img = prepare_inpaint_mask_bytes(
                    mask_resolved,
                    image_size=main_size,
                    grow=int(inpaint_recipe["inpaint_grow"]),
                    feather=int(inpaint_recipe["inpaint_feather"]),
                )
                mask_name = f"{Path(str(mask_path)).stem}_df_inpaint.png"
                mask_upload = client.upload_image(
                    image_bytes=mask_bytes,
                    filename=mask_name,
                    folder_type="input",
                    overwrite=True,
                )
                mask_filename = str(mask_upload.get("name") or mask_name)
            except OSError as exc:
                err = invalid_input_image(
                    f"inpaint mask: {exc}",
                    path=str(mask_path),
                    job_id=job_id,
                )
                emit_event(stream_sink, err)
                return {"status": "error", **err}

        comfy_mode = _comfy_workflow_mode(
            input_filename=input_filename,
            cn_type=str(cn_type or ""),
            model=model,
            model_family=model_family,
        )
        prompt_graph, template_used = _build_comfy_prompt_graph(
            job=job,
            mode=comfy_mode,
            model=model,
            model_family=model_family,
            settings=settings,
            prompt=prompt,
            negative=settings["negative"],
            seed=seed,
            edit_strength=edit_strength,
            cn_upscale=cn_upscale,
            input_filename=input_filename,
            mask_filename=mask_filename,
            reference_stitch_filename=reference_stitch_filename,
            grow_mask_by=grow_mask_by,
            model_loader_args=resolved_loaders,
        )

        emit_event(
            stream_sink,
            {
                "type": "progress",
                "job_id": job_id,
                "phase": "sampling",
                "progress": 0,
                "message": (
                    f"Submitting workflow to ComfyUI"
                    f"{f' ({Path(template_used).name})' if template_used else ''}…"
                ),
            },
        )
        sample_steps = int(settings.get("steps") or 20)

        def _comfy_stream_event(payload: dict) -> None:
            if not streaming:
                return
            payload = dict(payload)
            payload.setdefault("job_id", job_id)
            emit_event(stream_sink, payload)

        if streaming:
            _res, node = client.run_prompt_with_stream(
                prompt_graph,
                job_id=job_id or "",
                sample_count=sample_steps,
                node_count=1,
                timeout_s=60 * 30,
                on_event=_comfy_stream_event,
            )
        else:
            _res = client.prompt(prompt_graph)
            node = client.wait_for_outputs(_res.prompt_id, timeout_s=60 * 30, poll_s=0.5)
        outputs = node.get("outputs") or {}
        comfy_images: list[str] = []
        comfy_image_specs: list[tuple[str, str, str]] = []
        for _node_id, out in outputs.items():
            imgs = (out or {}).get("images") or []
            for img in imgs:
                filename = img.get("filename")
                subfolder = img.get("subfolder") or ""
                folder_type = img.get("type") or "output"
                if filename:
                    comfy_images.append(
                        str(Path(subfolder) / filename) if subfolder else str(filename)
                    )
                    comfy_image_specs.append((str(filename), str(subfolder), str(folder_type)))

        if not comfy_images:
            err = out_of_memory(job_id=job_id)
            err["message"] = "ComfyUI returned no output images (likely OOM or workflow mismatch)."
            emit_event(stream_sink, err)
            return {"status": "error", **err}

        comfy_out_dir = PROJECT_ROOT / "outputs" / "dreamforge" / "comfy"
        comfy_out_dir.mkdir(parents=True, exist_ok=True)
        saved_paths: list[str] = []
        for filename, subfolder, folder_type in comfy_image_specs:
            payload = client.view(filename=filename, subfolder=subfolder, folder_type=folder_type)
            stem = Path(filename).stem
            suffix = Path(filename).suffix or ".png"
            target = comfy_out_dir / f"{stem}_{int(time.time() * 1000)}{suffix}"
            target.write_bytes(payload)
            saved_paths.append(str(target))

        if cn_type == "inpaint" and input_path and inpaint_mask_img is not None and saved_paths:
            try:
                from dreamforge_paths import resolve_image_path_or_raise

                original = Image.open(
                    resolve_image_path_or_raise(str(input_path))
                ).convert("RGB")
                composited_paths: list[str] = []
                for saved in saved_paths:
                    generated = Image.open(saved).convert("RGB")
                    merged = composite_inpaint_result(
                        original, generated, inpaint_mask_img
                    )
                    merged_path = Path(saved).with_name(f"{Path(saved).stem}_composite.png")
                    merged.save(merged_path, format="PNG")
                    composited_paths.append(str(merged_path))
                saved_paths = composited_paths
            except OSError:
                pass

        images = saved_paths
        raw_images = comfy_images
        if streaming and images:
            emit_event(
                stream_sink,
                {
                    "type": "results",
                    "job_id": job_id,
                    "paths": images,
                    "raw_paths": raw_images,
                },
            )

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
                    "routing": {
                        "input_image": str(input_path) if input_path else None,
                        "upscale_image": str(upscale_input_path) if is_upscale_job else None,
                        "edit_type": edit_type,
                        "cn_selection": cn_selection,
                        "cn_type": cn_type,
                        "edit_strength": edit_strength,
                    },
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


def _tune_edit_job_settings(settings: dict, job, model_family: str) -> dict:
    """Lower latency defaults for reference / Kontext edits without overriding explicit Custom runs."""
    out = dict(settings)
    edit_type = str(getattr(job, "edit_type", "auto") or "auto").lower()
    has_input = bool(
        getattr(job, "input_image", None) or getattr(job, "upscale_image", None)
    )
    if not has_input or edit_type not in ("kontext", "inpaint", "img2img", "qwen_edit"):
        return out

    family = (model_family or "").lower()
    perf = str(getattr(job, "performance", "") or "").strip()
    custom_perf = perf in ("Custom...", "Custom")
    explicit_sampling = any(
        getattr(job, attr, None) is not None
        for attr in ("steps", "cfg_scale", "sampler", "scheduler")
    )

    try:
        from dreamforge_krita_recipes import edit_recipe

        recipe = edit_recipe(family, edit_type)
    except ImportError:
        recipe = None

    if recipe and not custom_perf:
        out["steps"] = int(recipe.get("custom_steps", out.get("steps", 20)))
        out["cfg"] = float(recipe.get("cfg", out.get("cfg", 3.5)))
        out["sampler_name"] = recipe.get("sampler_name", out.get("sampler_name"))
        out["scheduler"] = recipe.get("scheduler", out.get("scheduler"))
        out["clip_skip"] = int(recipe.get("clip_skip", out.get("clip_skip", 1)))

    if family.startswith("flux") or edit_type == "kontext":
        out["performance_selection"] = "Flux"
        if recipe and not custom_perf:
            out["steps"] = int(recipe.get("custom_steps", out.get("steps", 20)))
            out["cfg"] = float(recipe.get("cfg", out.get("cfg", 3.5)))
            out["sampler_name"] = recipe.get("sampler_name", out.get("sampler_name"))
            out["scheduler"] = recipe.get("scheduler", out.get("scheduler"))
            out["clip_skip"] = int(recipe.get("clip_skip", out.get("clip_skip", 1)))
        else:
            try:
                from modules.performance import PerformanceSettings

                opts = PerformanceSettings().get_perf_options("Flux")
                if not custom_perf:
                    out["steps"] = int(opts.get("custom_steps", out.get("steps", 20)))
                    out["cfg"] = float(opts.get("cfg", out.get("cfg", 3.0)))
                    out["sampler_name"] = opts.get("sampler_name", out.get("sampler_name"))
                    out["scheduler"] = opts.get("scheduler", out.get("scheduler"))
                    out["clip_skip"] = int(opts.get("clip_skip", out.get("clip_skip", 1)))
            except (KeyError, TypeError, ValueError):
                pass

    vram = os.environ.get("DREAMFORGE_DESKTOP_VRAM_MODE", "16gb")
    step_cap = {"5gb": 12, "8gb": 20, "16gb": 24}.get(vram, 20)
    if not custom_perf:
        out["steps"] = min(int(out.get("steps", step_cap)), step_cap)
    if explicit_sampling:
        if getattr(job, "steps", None) is not None:
            out["steps"] = int(job.steps)
        if getattr(job, "cfg_scale", None) is not None:
            out["cfg"] = float(job.cfg_scale)
        if getattr(job, "sampler", None):
            out["sampler_name"] = str(job.sampler)
        if getattr(job, "scheduler", None):
            out["scheduler"] = str(job.scheduler)
        out["performance_selection"] = "Custom..."

    return out


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
        if getattr(job, "steps", None) is not None:
            out["steps"] = int(job.steps)
        if getattr(job, "cfg_scale", None) is not None:
            out["cfg"] = float(job.cfg_scale)
        if getattr(job, "sampler", None):
            out["sampler_name"] = str(job.sampler)
        if getattr(job, "scheduler", None):
            out["scheduler"] = str(job.scheduler)
        if any(
            getattr(job, attr, None) is not None
            for attr in ("steps", "cfg_scale", "sampler", "scheduler")
        ):
            out["performance_selection"] = "Custom..."
    except (KeyError, TypeError, ValueError):
        pass
    return out


def request_stop() -> None:
    try:
        from dreamforge_comfy_client import ComfyClient
        from dreamforge_comfy_server import get_default_comfy_server

        server = get_default_comfy_server()
        if server.is_running():
            ComfyClient(server.base_url).interrupt()
    except Exception:
        pass
