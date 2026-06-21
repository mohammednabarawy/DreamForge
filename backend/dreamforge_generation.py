"""
Shared headless DreamForge generation for CLI and DreamForge desktop worker.
Matches DreamForge webui.py preview loop (task_result + preview.jpg).
"""
from __future__ import annotations

import base64
import gc
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
    invalid_request,
    missing_custom_node_pack,
    missing_input_image,
    missing_model_dependencies,
    out_of_memory,
)
from dreamforge_upscale_defaults import upscale_field_defaults
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


def _pid_upscale_target_size(
    src_w: int,
    src_h: int,
    *,
    requested_long_side: int = 4096,
    vram_tier: str = "16gb",
) -> tuple[int, int, float, int]:
    """Return the rounded PiD target size and effective scale.

    PiD / PixelDiT is a generative 4K upscaler. Running it at near-source
    resolution behaves like a repaint and can damage identity/text without
    adding useful detail, so callers should reject very small scales.
    """
    if src_w <= 0 or src_h <= 0:
        raise ValueError("source dimensions must be positive")

    if vram_tier == "5gb":
        max_long_side = 2048
    elif vram_tier == "8gb":
        max_long_side = 3072
    else:
        max_long_side = 4096

    long_side = max(16, int(requested_long_side or 4096))
    long_side = min(long_side, max_long_side)
    scale = max(1.0, long_side / max(src_w, src_h))
    target_w = max(16, int(round((src_w * scale) / 16) * 16))
    target_h = max(16, int(round((src_h * scale) / 16) * 16))
    return target_w, target_h, scale, max_long_side


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
    try:
        from dreamforge_comfy_install import ensure_dreamforge_comfy_backend

        ensure_dreamforge_comfy_backend(
            progress=(lambda msg, _p=progress: _report_boot(_p, msg)) if progress else None
        )
    except Exception as exc:
        repos_dir = BACKEND_ROOT / "repositories"
        comfy_dir = repos_dir / "ComfyUI"
        if not comfy_dir.is_dir() or not any(comfy_dir.iterdir()):
            _report_boot(progress, f"ERROR: Could not set up ComfyUI: {exc}")
            raise RuntimeError(f"Could not set up ComfyUI: {exc}") from exc
        _report_boot(progress, f"Warning: ComfyUI install step failed ({exc}); continuing with existing checkout.")

    comfy_dir = BACKEND_ROOT / "repositories" / "ComfyUI"
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


def _checkpoint_is_flux_fill(model: dict | None, model_family: str) -> bool:
    """True when weights are Flux.1 Fill / inpaint checkpoints."""
    fam = (model_family or "").lower()
    if fam == "flux_fill":
        return True
    blob = _routing_model_blob(model)
    fill_hints = (
        "flux1-fill",
        "flux-fill",
        "flux.1-fill",
        "flux fill",
    )
    return any(h in blob for h in fill_hints)


def _coerce_reference_image_paths(job) -> list[str]:
    from dreamforge_comfy_workflow_import import coerce_reference_image_paths

    return coerce_reference_image_paths(job)


def _comfy_workflow_mode(
    *,
    input_filename: str | None,
    cn_type: str,
    model: dict,
    model_family: str,
    workflow_mode: str | None = None,
    edit_type: str | None = None,
) -> str:
    from dreamforge_comfy_workflow_import import comfy_workflow_mode

    return comfy_workflow_mode(
        input_filename=input_filename,
        cn_type=str(cn_type or ""),
        model=model,
        model_family=model_family,
        checkpoint_is_flux_kontext=_checkpoint_is_flux_kontext,
        workflow_mode=workflow_mode,
        edit_type=edit_type,
    )


def _first_inventory_model(category: str, hints: tuple[str, ...] = ()) -> str | None:
    try:
        from dreamforge_cli_inventory import list_model_inventory

        items = list_model_inventory().get("categories", {}).get(category, [])
        if hints:
            for item in items:
                text = " ".join(str(item.get(key, "")) for key in ("name", "relative_path", "stem")).lower()
                if any(h in text for h in hints):
                    return str(item.get("name") or item.get("relative_path") or "").replace("\\", "/")
        if items:
            item = items[0]
            return str(item.get("name") or item.get("relative_path") or "").replace("\\", "/")
    except Exception:
        return None
    return None


def _build_ideogram4_comfy_graph_bundle(
    *,
    job,
    mode: str,
    settings: dict,
    prompt: str,
    seed: int,
    edit_strength: float,
    loader_args: dict,
    input_filename: str | None,
    mask_filename: str | None,
    grow_mask_by: int,
    edit_type: str | None = None,
) -> tuple[dict, str]:
    from dreamforge_prompt.ideogram4 import ideogram4_scheduler_params
    from dreamforge_prompt.ideogram4_workflows import (
        build_ideogram4_comfy_graph,
        resolve_ideogram4_uncond_unet,
        resolve_ideogram4_workflow_kind,
    )
    from dreamforge_vram_profiles import profile_tier

    vram_tier = profile_tier(
        getattr(job, "vram_profile", None)
        or os.environ.get("DREAMFORGE_VRAM_PROFILE")
        or "auto"
    )
    kind = resolve_ideogram4_workflow_kind(
        workflow_mode=mode,
        input_filename=input_filename,
        mask_filename=mask_filename,
        edit_type=edit_type,
    )
    from dreamforge_prompt.ideogram4 import resolve_input_image_dimensions
    from dreamforge_prompt.ideogram4_workflows import (
        IDEOGRAM4_WORKFLOW_IMG2IMG,
        IDEOGRAM4_WORKFLOW_INPAINT,
    )

    sched_w, sched_h = int(settings["width"]), int(settings["height"])
    if kind in (IDEOGRAM4_WORKFLOW_INPAINT, IDEOGRAM4_WORKFLOW_IMG2IMG):
        sched_w, sched_h = resolve_input_image_dimensions(job, sched_w, sched_h)
    sched = ideogram4_scheduler_params(
        settings,
        job=job,
        width=sched_w,
        height=sched_h,
        vram_tier=vram_tier,
    )
    graph_args = {
        **loader_args,
        "prompt": prompt,
        "width": sched["width"],
        "height": sched["height"],
        "steps": sched["steps"],
        "ideogram4_mu": sched["mu"],
        "ideogram4_std": sched["std"],
        "dual_cfg": sched["dual_cfg"],
        "cfg_override": sched.get("cfg_override", 3.0),
        "cfg_override_start": sched.get("cfg_override_start", 0.9),
        "cfg_override_end": sched.get("cfg_override_end", 1.0),
        "unet_unconditional": resolve_ideogram4_uncond_unet(vram_tier=vram_tier),
        "enable_vae_tiling": vram_tier in {"16gb", "8gb", "5gb"},
        "seed": seed,
        "denoise": edit_strength,
        "grow_mask_by": grow_mask_by,
        "filename_prefix": "DreamForge",
    }
    if input_filename:
        graph_args["image"] = input_filename
    if mask_filename:
        graph_args["mask"] = mask_filename
    for key, setting_key in (
        ("cfg_override", "ideogram4_cfg_override"),
        ("cfg_override_start", "ideogram4_cfg_override_start"),
        ("cfg_override_end", "ideogram4_cfg_override_end"),
    ):
        val = settings.get(setting_key)
        if val is not None:
            graph_args[key] = val
    return build_ideogram4_comfy_graph(kind, graph_args), f"ideogram4/{kind}"


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
    qwen_reference_filenames: list[str] | None = None,
):
    from dreamforge_comfy_workflow_import import (
        build_prompt_from_template,
        resolve_comfy_workflow_template,
    )
    from dreamforge_comfy_workflows import (
        comfy_area_composition,
        comfy_controlnet_basic,
        comfy_feature_extraction,
        comfy_flux_dev_txt2img,
        comfy_flux_kontext_edit,
        comfy_face_detail_basic,
        comfy_hires_two_pass,
        comfy_img2img_basic,
        comfy_inpaint_basic,
        comfy_ipadapter_reference,
        comfy_ultimate_sd_upscale,
        comfy_outpaint_basic,
        comfy_qwen_image_edit,
        comfy_qwen_image_edit_plus,
        comfy_qwen_image_txt2img,
        comfy_pid_flux_upscale,
        comfy_txt2img_basic,
        comfy_upscale_basic,
        comfy_z_image_txt2img,
        comfy_kandinsky5_txt2img,
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
    loras = list(settings.get("comfy_loras") or [])
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
        **{
            k: v
            for k, v in upscale_field_defaults(
                {
                    "upscale_by": getattr(job, "upscale_by", None),
                    "upscale_denoise": getattr(job, "upscale_denoise", None),
                    "upscale_tile_width": getattr(job, "upscale_tile_width", None),
                    "upscale_tile_height": getattr(job, "upscale_tile_height", None),
                    "upscale_mask_blur": getattr(job, "upscale_mask_blur", None),
                    "upscale_tile_padding": getattr(job, "upscale_tile_padding", None),
                    "upscale_seam_fix_mode": getattr(job, "upscale_seam_fix_mode", None),
                    "upscale_mode_type": getattr(job, "upscale_mode_type", None),
                    "upscale_force_uniform_tiles": getattr(job, "upscale_force_uniform_tiles", None),
                    "upscale_tiled_decode": getattr(job, "upscale_tiled_decode", None),
                    "steps": settings.get("steps"),
                    "cfg": settings.get("cfg"),
                    "sampler_name": settings.get("sampler_name"),
                    "scheduler": settings.get("scheduler"),
                }
            ).items()
            if k.startswith("upscale_") or k in ("steps", "cfg", "sampler_name", "scheduler")
        },
        "upscale_seam_fix_denoise": getattr(job, "upscale_seam_fix_denoise", 1.0),
        "upscale_seam_fix_width": getattr(job, "upscale_seam_fix_width", 64),
        "upscale_seam_fix_mask_blur": getattr(job, "upscale_seam_fix_mask_blur", 8),
        "upscale_seam_fix_padding": getattr(job, "upscale_seam_fix_padding", 16),
        "upscale_tiled_decode": getattr(job, "upscale_tiled_decode", False),
        "grow_mask_by": grow_mask_by,
        "loras": loras,
    }
    if input_filename:
        bindings["image"] = input_filename
    if mask_filename:
        bindings["mask"] = mask_filename
    if reference_stitch_filename:
        bindings["reference_stitch"] = reference_stitch_filename
    controlnet_model = bindings.get("controlnet_model")
    if controlnet_model:
        bindings["controlnet_model"] = controlnet_model
    if template_path:
        return build_prompt_from_template(template_path, bindings), str(template_path)

    common = {
        **loader_args,
        "prompt": prompt,
        "negative": negative,
        "steps": settings["steps"],
        "cfg": settings["cfg"],
        "sampler_name": settings["sampler_name"],
        "scheduler": settings["scheduler"],
        "seed": seed,
        "filename_prefix": "DreamForge",
        "width": settings["width"],
        "height": settings["height"],
        "loras": loras,
    }

    if model_family == "ideogram4" and mode != "upscale":
        return _build_ideogram4_comfy_graph_bundle(
            job=job,
            mode=mode,
            settings=settings,
            prompt=prompt,
            seed=seed,
            edit_strength=edit_strength,
            loader_args=loader_args,
            input_filename=input_filename,
            mask_filename=mask_filename,
            grow_mask_by=grow_mask_by,
            edit_type=getattr(job, "edit_type", None),
        )

    if mode == "hires":
        graph = comfy_hires_two_pass(
            {
                **common,
                "hires_denoise": float(getattr(job, "hires_denoise", 0.35) or 0.35),
                "hires_first_pass_scale": float(getattr(job, "hires_first_pass_scale", 0.5) or 0.5),
                "hires_first_width": getattr(job, "hires_first_width", None),
                "hires_first_height": getattr(job, "hires_first_height", None),
                "hires_first_steps": getattr(job, "hires_first_steps", None),
                "hires_second_steps": getattr(job, "hires_second_steps", None),
                "hires_latent_upscale_method": getattr(job, "hires_latent_upscale_method", "nearest-exact"),
            }
        )
    elif mode == "area_composition":
        graph = comfy_area_composition(
            {
                **common,
                "region_prompts": getattr(job, "region_prompts", None)
                or getattr(job, "region_prompts_json", None)
                or getattr(job, "composition_regions", None),
                "region_prompt": getattr(job, "region_prompt", None),
                "foreground_prompt": getattr(job, "foreground_prompt", None),
            }
        )
    elif mode == "ipadapter":
        ref_name = getattr(job, "reference_image", None) or input_filename
        graph = comfy_ipadapter_reference(
            {
                **common,
                "reference_image": ref_name,
                "ipadapter_model": getattr(job, "ipadapter_model", None)
                or _first_inventory_model("ipadapter"),
                "clip_vision": getattr(job, "clip_vision", None)
                or _first_inventory_model("clip_vision", ("vit", "clip-vision")),
                "ipadapter_weight": getattr(job, "ipadapter_weight", getattr(job, "reference_weight", 0.75)),
            }
        )
    elif mode == "face_detail" and input_filename:
        graph = comfy_face_detail_basic(
            {
                **common,
                "image": input_filename,
                "detail_prompt": getattr(job, "detail_prompt", None) or prompt,
                "detail_target": getattr(job, "detail_target", "face"),
                "bbox_model": getattr(job, "bbox_model", None)
                or getattr(job, "bbox_detector_model", None),
                "sam_model": getattr(job, "sam_model", None)
                or getattr(job, "sam_model_name", None),
                "detail_denoise": getattr(job, "detail_denoise", edit_strength),
                "denoise": edit_strength,
            }
        )
    elif mode == "controlnet":
        graph = comfy_controlnet_basic(
            {
                **common,
                "image": input_filename,
                "control_image": getattr(job, "control_image", None) or input_filename,
                "controlnet_model": getattr(job, "controlnet_model", None)
                or _first_inventory_model("controlnet", (str(getattr(job, "cn_type", "") or "").lower(),)),
                "cn_strength": getattr(job, "cn_strength", getattr(job, "controlnet_strength", 1.0)),
                "cn_start": getattr(job, "cn_start", getattr(job, "controlnet_start", 0.0)),
                "cn_stop": getattr(job, "cn_stop", getattr(job, "controlnet_end", 1.0)),
                "denoise": edit_strength if input_filename else 1.0,
            }
        )
    elif mode == "extract" and input_filename:
        graph = comfy_feature_extraction(
            {
                "image": input_filename,
                "extraction_type": getattr(job, "extraction_type", settings.get("extraction_type", "canny")),
                "filename_prefix": "DreamForge_Extract",
            }
        )
    elif mode == "outpaint" and input_filename:
        graph = comfy_outpaint_basic(
            {
                **common,
                "image": input_filename,
                "denoise": edit_strength,
                "grow_mask_by": grow_mask_by,
                "outpaint_left": int(getattr(job, "outpaint_left", 0) or 0),
                "outpaint_top": int(getattr(job, "outpaint_top", 0) or 0),
                "outpaint_right": int(getattr(job, "outpaint_right", 0) or 0),
                "outpaint_bottom": int(getattr(job, "outpaint_bottom", 0) or 0),
                "outpaint_direction": getattr(job, "outpaint_direction", None),
                "outpaint_amount": int(getattr(job, "outpaint_amount", 128) or 128),
                "outpaint_feathering": int(getattr(job, "outpaint_feathering", 40) or 40),
            }
        )
    elif input_filename:
        if mode == "upscale":
            graph = comfy_ultimate_sd_upscale({**common, "image": input_filename})
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
        elif (model_family or "").startswith("qwen") and (
            model_family == "qwen_image_edit" or mode == "qwen_edit" or model_family == "qwen_image"
        ):
            from dreamforge_krita_recipes import resolve_qwen_edit_mode

            qwen_common = {
                **loader_args,
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
            for key in (
                "qwen_image_shift",
                "qwen_scale_megapixels",
                "use_qwen_lightning_lora",
                "qwen_lightning_lora",
                "qwen_lightning_strength",
            ):
                if settings.get(key) is not None:
                    qwen_common[key] = settings[key]
            edit_mode = resolve_qwen_edit_mode(
                model_family="qwen_image_edit",
                requested=getattr(job, "qwen_edit_mode", None),
                extra_reference_count=len(qwen_reference_filenames or []),
            )
            if edit_mode == "plus":
                images = [input_filename, *(qwen_reference_filenames or [])][:3]
                graph = comfy_qwen_image_edit_plus({**qwen_common, "images": images})
            else:
                # Qwen single-image edit only accepts one image input. Extra references
                # are only valid through the Plus node; do not stitch uploaded Comfy
                # filenames into a fake local path.
                graph = comfy_qwen_image_edit({**qwen_common, "image": input_filename})
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
    elif (model_family or "").startswith("qwen"):
        qwen_txt2img = {
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
        if settings.get("qwen_image_shift") is not None:
            qwen_txt2img["qwen_image_shift"] = settings["qwen_image_shift"]
        graph = comfy_qwen_image_txt2img(qwen_txt2img)
    elif (model_family or "").startswith("flux") or model_family == "chroma":
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
    elif model_family in ("kandinsky", "kandinsky5"):
        graph = comfy_kandinsky5_txt2img(
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
    elif model_family in ("z-image", "z_image"):
        graph = comfy_z_image_txt2img(
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


_COMFY_RECOVER_CODES = frozenset(
    {
        "comfy_server_crashed",
        "virtual_memory_low",
        "out_of_memory",
        "generation_failed",
    }
)


def _free_comfy_vram_for_retry(client) -> None:
    try:
        client.free_memory(unload_models=True, free_memory=True)
    except Exception:
        pass
    gc.collect()
    time.sleep(0.5)


def _comfy_job_unload_models(*, cn_type: str | None, comfy_mode: str | None) -> bool:
    mode = str(comfy_mode or cn_type or "").lower()
    return mode == "upscale"


def _run_comfy_workflow_once(
    client,
    prompt_graph: dict,
    *,
    streaming: bool,
    job_id: str | None,
    sample_steps: int,
    stream_sink,
    on_event,
):
    from dreamforge_comfy_client import COMFY_EXECUTION_TIMEOUT_S

    if streaming:
        from dreamforge_comfy_ws import count_comfy_prompt_nodes, guess_sample_count_from_prompt

        stream_sample_count = guess_sample_count_from_prompt(
            prompt_graph,
            fallback=sample_steps,
        )
        return client.run_prompt_with_stream(
            prompt_graph,
            job_id=job_id or "",
            sample_count=stream_sample_count,
            node_count=count_comfy_prompt_nodes(prompt_graph),
            timeout_s=COMFY_EXECUTION_TIMEOUT_S,
            on_event=on_event,
        )
    res = client.prompt(prompt_graph)
    node = client.wait_for_outputs(
        res.prompt_id,
        timeout_s=COMFY_EXECUTION_TIMEOUT_S,
        poll_s=0.5,
    )
    return res, node


def _run_comfy_workflow_with_retry(
    client,
    prompt_graph: dict,
    *,
    streaming: bool,
    job_id: str | None,
    sample_steps: int,
    stream_sink,
    on_event,
):
    from dreamforge_comfy_client import ComfyExecutionError, ComfyHungError, is_comfy_oom_error

    last_exc: BaseException | None = None
    for attempt in range(2):
        try:
            return _run_comfy_workflow_once(
                client,
                prompt_graph,
                streaming=streaming,
                job_id=job_id,
                sample_steps=sample_steps,
                stream_sink=stream_sink,
                on_event=on_event,
            )
        except (ComfyExecutionError, ComfyHungError, TimeoutError) as exc:
            last_exc = exc
            if attempt == 0 and is_comfy_oom_error(exc):
                emit_event(
                    stream_sink,
                    {
                        "type": "progress",
                        "job_id": job_id,
                        "phase": "sampling",
                        "progress": 0,
                        "message": "GPU memory full — freeing VRAM and retrying once…",
                    },
                )
                _free_comfy_vram_for_retry(client)
                continue
            raise
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Comfy workflow failed without an exception")


def _maybe_recover_comfy_after_failure(exc: BaseException, err: dict) -> None:
    """Restart managed ComfyUI when the subprocess died or a prompt hung."""
    from dreamforge_comfy_client import ComfyHungError

    code = str(err.get("code") or err.get("error") or "")
    msg = str(exc).lower()
    should_recover = (
        code in _COMFY_RECOVER_CODES
        or isinstance(exc, ComfyHungError)
        or any(
            hint in msg
            for hint in (
                "comfyui server became unreachable",
                "connection refused",
                "winerror 10061",
                "actively refused",
                "paging file is too small",
                "os error 1455",
                "stalled for",
            )
        )
    )
    if not should_recover:
        return
    try:
        from dreamforge_comfy_server import (
            get_default_comfy_server,
            recover_managed_comfy_server,
            restart_managed_comfy_server,
        )

        server = get_default_comfy_server()
        server.discard_dead_process()
        reason = code or type(exc).__name__
        if isinstance(exc, ComfyHungError):
            restart_managed_comfy_server(timeout_s=90.0, reason=reason)
            return
        if server.is_running():
            return
        recover_managed_comfy_server(timeout_s=90.0, reason=reason)
    except Exception as recover_exc:
        print(f"[DreamForge] ComfyUI auto-recover failed: {recover_exc}", file=sys.stderr)


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
    from dreamforge_cli_inventory import (
        check_model_dependencies,
        ensure_model_companions_downloaded,
        model_fallback_actions,
    )
    from dreamforge_model_registry import required_capabilities_for_request

    extend_sys_path()
    os.chdir(BACKEND_ROOT)

    try:
        job, model, prompt, negative, width, height, _brand_kit = _compile_job(base_args, data)
        model_family = str(model.get("family") or "").lower()
        settings = _apply_ideogram4_family_settings(
            _apply_qwen_family_settings(
                _tune_edit_job_settings(
                    _apply_job_performance(
                        _auto_settings(model, job, width, height, negative),
                        job,
                        model_family,
                    ),
                    job,
                    model_family,
                    is_live=stream_sink is not None,
                ),
                job,
                model_family,
                is_live=stream_sink is not None,
            ),
            job,
            model_family,
        )
        if getattr(job, "clip_skip", None) is not None:
            try:
                settings["clip_skip"] = int(job.clip_skip)
            except (TypeError, ValueError):
                pass

        from dreamforge_prompt import prepare_generation_prompts

        prepared = prepare_generation_prompts(job, model, prompt, negative, settings)
        prompt = prepared["prompt"]
        negative = prepared["negative"]
        settings = dict(settings)
        settings["negative"] = negative
        settings["comfy_loras"] = prepared.get("comfy_loras") or []
        settings["prompt_pipeline"] = {
            "prompt_enhancer": prepared.get("prompt_enhancer"),
            "expansion_available": prepared.get("expansion_available"),
            "styles_applied": prepared.get("styles_applied", []),
            "parsed_lora_count": len(prepared.get("loras") or []),
            "comfy_lora_count": len(settings["comfy_loras"]),
            "ideogram4_prompt_mode": prepared.get("ideogram4_prompt_mode"),
            "prompt_format": prepared.get("prompt_format"),
        }
        if prepared.get("prompt_prepare_error"):
            from dreamforge_errors import invalid_request

            err = invalid_request(str(prepared["prompt_prepare_error"]), job_id=job_id)
            emit_event(stream_sink, err)
            return {"status": "error", **err}

        seed = int(getattr(job, "seed", -1))
        if seed == -1:
            seed = random.randint(0, 2**31 - 1)

        missing_deps = check_model_dependencies(
            model,
            performance=getattr(job, "performance", None),
        )
        if missing_deps:
            download_out = ensure_model_companions_downloaded(
                model,
                progress_cb=lambda count: emit_event(
                    stream_sink,
                    {
                        "type": "progress",
                        "job_id": job_id,
                        "phase": "download",
                        "message": f"Downloading {count} required companion file(s)…",
                    },
                ),
            )
            missing_deps = list(download_out.get("missing") or [])
            if download_out.get("downloaded"):
                emit_event(
                    stream_sink,
                    {
                        "type": "progress",
                        "job_id": job_id,
                        "phase": "download",
                        "message": f"Downloaded {download_out['downloaded']} companion file(s).",
                    },
                )
        if missing_deps:
            err = missing_model_dependencies(
                missing_deps,
                job_id=job_id,
                actions=model_fallback_actions(
                    model,
                    required_capabilities_for_request(vars(job)),
                    getattr(job, "vram_profile", "auto"),
                    getattr(job, "performance", "Quality"),
                ),
            )
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

        from dreamforge_workflow_executor import (
            execute_workflow_plan,
            should_execute_workflow_plan,
        )

        if should_execute_workflow_plan(job, data):
            return execute_workflow_plan(
                base_args=base_args,
                data=data,
                job=job,
                stream_sink=stream_sink,
                job_id=job_id,
            )

        if not os.environ.get("DREAMFORGE_IN_ARABIC_PIPELINE"):
            from dreamforge_arabic_composite import (
                arabic_composite_requested,
                run_arabic_text_composite_job,
            )

            if arabic_composite_requested(job):
                return run_arabic_text_composite_job(
                    job=job,
                    base_args=base_args,
                    model=model,
                    prompt=prompt,
                    negative=negative,
                    width=width,
                    height=height,
                    seed=seed,
                    stream_sink=stream_sink,
                    job_id=job_id,
                )

        explicit_input_path = getattr(job, "input_image", None)
        upscale_input_path = getattr(job, "upscale_image", None)
        cn_selection = getattr(job, "cn_selection", None) or "None"
        cn_type = getattr(job, "cn_type", None) or "None"
        edit_type = getattr(job, "edit_type", "auto")
        workflow_mode = getattr(job, "workflow_mode", None) or getattr(job, "comfy_workflow_mode", None)
        inpaint_mask_path = getattr(job, "inpaint_mask_path", None)
        is_inpaint_job = (
            str(edit_type or "").lower() == "inpaint"
            or str(cn_type or "").lower() == "inpaint"
            or bool(inpaint_mask_path)
        )
        if is_inpaint_job:
            edit_type = "inpaint"
            cn_selection = "Custom..."
            cn_type = "inpaint"
            if not _checkpoint_is_flux_fill(model, model_family) and (
                model_family or ""
            ).lower() != "ideogram4":
                from dreamforge_errors import invalid_request

                model_label = model.get("name") or model.get("engine_name") or model_family
                err = invalid_request(
                    "Inpaint requires a Flux Fill checkpoint "
                    f"(flux1-fill-dev-fp8.safetensors); got {model_label}. "
                    "Use Inpaint mode or download Flux Fill from Settings.",
                    job_id=job_id,
                )
                emit_event(stream_sink, err)
                return {"status": "error", **err}
        # Desktop state can briefly carry both input_image and a stale upscale_image
        # when switching modes. An explicit edit input must win so Kontext/inpaint
        # jobs do not silently become "upscale the original image".
        is_upscale_job = bool(upscale_input_path) and not explicit_input_path
        input_path = explicit_input_path or upscale_input_path
        style = str(getattr(job, "style", "none") or "none").lower()

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
            wm = str(workflow_mode or "").lower()
            if (
                _checkpoint_is_flux_kontext(model, model_family)
                or edit_type == "kontext"
                or (wm == "generate" and edit_type == "kontext")
            ):
                cn_selection = "None"
                cn_type = "None"
            elif (
                (model_family or "").lower() == "qwen_image_edit" or edit_type == "qwen_edit"
            ) and not is_inpaint_job:
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

        if is_upscale_job or str(cn_type or "").lower() == "upscale":
            from dreamforge_model_library_cache import get_cached_model_gallery
            from dreamforge_upscale_routing import (
                is_upscale_compatible_checkpoint,
                resolve_upscale_checkpoint_model,
            )

            allow_upscale_override = bool(
                getattr(job, "user_picked_model", False)
                and getattr(job, "advanced_mode", False)
            )
            gallery, _cache_hit = get_cached_model_gallery()
            route_msg = None
            if allow_upscale_override:
                if stream_sink is not None and not is_upscale_compatible_checkpoint(model):
                    emit_event(
                        stream_sink,
                        {
                            "type": "progress",
                            "job_id": job_id,
                            "phase": "preflight",
                            "progress": 1,
                            "message": (
                                f"Pro Enhance: using your selected checkpoint "
                                f"({model.get('engine_name') or model.get('name') or 'custom'}) "
                                f"instead of auto SDXL routing."
                            ),
                        },
                    )
            else:
                model, route_msg = resolve_upscale_checkpoint_model(model, gallery)
                model_family = str(model.get("family") or "").lower()
            if route_msg and stream_sink is not None:
                emit_event(
                    stream_sink,
                    {
                        "type": "progress",
                        "job_id": job_id,
                        "phase": "preflight",
                        "progress": 1,
                        "message": route_msg,
                    },
                )
            if not allow_upscale_override and not is_upscale_compatible_checkpoint(model):
                from dreamforge_errors import invalid_request

                err = invalid_request(
                    route_msg
                    or "Ultimate SD Upscale requires an SDXL checkpoint (EpicRealism XL, Juggernaut XL, etc.).",
                    job_id=job_id,
                    suggestions=[
                        "Install an SDXL realism checkpoint under models/checkpoints",
                        "Switch to Enhance mode and let DreamForge auto-select SDXL",
                        "Flux, Z-Image, and Ideogram checkpoints are not compatible with Ultimate SD Upscale",
                    ],
                )
                emit_event(stream_sink, err)
                return {"status": "error", **err}

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
        default_edit_strength = 1.0
        if not _checkpoint_is_flux_kontext(model, model_family) and (
            model_family or ""
        ).lower() != "qwen_image_edit":
            default_edit_strength = 0.75
        edit_strength = _clamp_float(
            getattr(job, "edit_strength", None),
            default_edit_strength,
            0.0,
            1.0,
        )
        try:
            from dreamforge_krita_resources import resolve_upscaler

            cn_override = getattr(job, "cn_upscale", None)
            if cn_override and str(cn_override).strip():
                cn_upscale = str(cn_override).strip()
            else:
                upscale_info = resolve_upscaler(getattr(job, "upscale_method", None))
                cn_upscale = upscale_info["filename"]
        except ImportError:
            cn_upscale = getattr(job, "cn_upscale", None) or "4x-UltraSharp.pth"
        mask_path = inpaint_mask_path

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

        if str(cn_type or "").lower() == "upscale":
            from dreamforge_cli_inventory import check_studio_resources
            from dreamforge_workflow_planner import custom_node_pack_present

            if not custom_node_pack_present("ComfyUI_UltimateSDUpscale"):
                from dreamforge_errors import missing_custom_node_pack

                err = missing_custom_node_pack(
                    "ComfyUI_UltimateSDUpscale",
                    job_id=job_id,
                    nodes=("UltimateSDUpscale",),
                )
                emit_event(stream_sink, err)
                return {"status": "error", **err}
            missing_upscale_assets = check_studio_resources(
                "upscale",
                upscale_method=str(getattr(job, "upscale_method", None) or "ultimate_sd_upscale"),
            )
            if missing_upscale_assets:
                err = missing_model_dependencies(missing_upscale_assets, job_id=job_id)
                emit_event(stream_sink, err)
                return {"status": "error", **err}

        server = ensure_comfy_running(timeout_s=60.0)
        client = ComfyClient(server.base_url)

        def _resolve_loaders():
            return resolve_comfy_model_loader_args(
                client,
                model=model,
                model_family=model_family,
            )

        try:
            resolved_loaders = _resolve_loaders()
        except ComfyModelResolutionError as first_exc:
            ensure_model_companions_downloaded(
                model,
                progress_cb=lambda count: emit_event(
                    stream_sink,
                    {
                        "type": "progress",
                        "job_id": job_id,
                        "phase": "download",
                        "message": f"Downloading {count} companion file(s) for ComfyUI…",
                    },
                ),
            )
            try:
                resolved_loaders = _resolve_loaders()
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

        def _job_inpaint_int(name: str, recipe_key: str) -> int:
            value = getattr(job, name, None)
            if value is not None:
                return int(value)
            return int(inpaint_recipe[recipe_key])

        grow_mask_by = _job_inpaint_int("inpaint_mask_grow_by", "inpaint_mask_grow_by")
        inpaint_grow = _job_inpaint_int("inpaint_grow", "inpaint_grow")
        inpaint_feather = _job_inpaint_int("inpaint_feather", "inpaint_feather")
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
        qwen_reference_filenames: list[str] = []
        extra_reference_paths = _coerce_reference_image_paths(job)
        if extra_reference_paths and input_path:
            if model_family == "qwen_image_edit":
                try:
                    from dreamforge_paths import resolve_image_path_or_raise

                    for ref_path in extra_reference_paths[:2]:
                        resolved = resolve_image_path_or_raise(str(ref_path))
                        ref_local_name = Path(resolved).name
                        ref_upload = client.upload_image(
                            image_bytes=Path(resolved).read_bytes(),
                            filename=ref_local_name,
                            folder_type="input",
                            overwrite=True,
                        )
                        qwen_reference_filenames.append(
                            str(ref_upload.get("name") or ref_local_name)
                        )
                except OSError as exc:
                    err = invalid_input_image(
                        f"reference image: {exc}",
                        path=str(extra_reference_paths),
                        job_id=job_id,
                    )
                    emit_event(stream_sink, err)
                    return {"status": "error", **err}
            else:
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

        reference_filename = input_filename
        ref_only_path = getattr(job, "reference_image", None)
        if ref_only_path:
            try:
                from dreamforge_paths import resolve_image_path_or_raise

                resolved_ref_path = resolve_image_path_or_raise(str(ref_only_path))
                ref_local_name = Path(resolved_ref_path).name
                if not reference_filename or str(ref_only_path) != str(input_path or ""):
                    ref_upload = client.upload_image(
                        image_bytes=Path(resolved_ref_path).read_bytes(),
                        filename=ref_local_name,
                        folder_type="input",
                        overwrite=True,
                    )
                    reference_filename = str(ref_upload.get("name") or ref_local_name)
                job.reference_image = reference_filename
            except (FileNotFoundError, ValueError, OSError) as exc:
                err = invalid_input_image(
                    f"reference image: {exc}",
                    path=str(ref_only_path),
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
                    grow=inpaint_grow,
                    feather=inpaint_feather,
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
            workflow_mode=str(workflow_mode or "") or None,
            edit_type=str(edit_type or "") or None,
        )
        if comfy_mode == "ipadapter":
            from dreamforge_workflow_planner import custom_node_pack_present

            if not custom_node_pack_present("ComfyUI_IPAdapter_plus"):
                from dreamforge_errors import missing_custom_node_pack

                err = missing_custom_node_pack(
                    "ComfyUI_IPAdapter_plus",
                    job_id=job_id,
                    nodes=("IPAdapterModelLoader", "IPAdapterAdvanced"),
                )
                emit_event(stream_sink, err)
                return {"status": "error", **err}
            missing_ipadapter_models: list[str] = []
            if not (getattr(job, "ipadapter_model", None) or _first_inventory_model("ipadapter")):
                missing_ipadapter_models.append("ipadapter_model")
            if not (
                getattr(job, "clip_vision", None)
                or getattr(job, "clip_vision_model", None)
                or _first_inventory_model("clip_vision", ("vit", "clip-vision"))
            ):
                missing_ipadapter_models.append("clip_vision")
            if missing_ipadapter_models:
                from dreamforge_workflow_planner import _recommended_actions

                missing = [
                    {
                        "kind": item,
                        "name": (
                            "ip-adapter_sdxl_vit-h.safetensors"
                            if item == "ipadapter_model"
                            else "clip-vision_vit-h.safetensors"
                        ),
                    }
                    for item in missing_ipadapter_models
                ]
                err = missing_model_dependencies(
                    missing,
                    job_id=job_id,
                    actions=_recommended_actions(
                        missing_models=missing_ipadapter_models,
                        missing_node_packs=[],
                        optional_nodes=[],
                        template_ids=["reference_ipadapter"],
                        current_settings=vars(job),
                    ),
                )
                emit_event(stream_sink, err)
                return {"status": "error", **err}
        if comfy_mode == "face_detail":
            from dreamforge_workflow_planner import custom_node_pack_present

            missing_packs = [
                pack
                for pack in ("ComfyUI-Impact-Pack", "ComfyUI-Impact-Subpack")
                if not custom_node_pack_present(pack)
            ]
            if missing_packs:
                from dreamforge_errors import missing_custom_node_pack

                err = missing_custom_node_pack(
                    missing_packs[0],
                    job_id=job_id,
                    nodes=("UltralyticsDetectorProvider", "FaceDetailer", "SAMLoader"),
                )
                emit_event(stream_sink, err)
                return {"status": "error", **err}
            if not input_filename:
                err = invalid_input_image(
                    "face detail repair requires an input image",
                    path=str(getattr(job, "input_image", "") or ""),
                    job_id=job_id,
                )
                emit_event(stream_sink, err)
                return {"status": "error", **err}
        if model_family == "ideogram4":
            from dreamforge_comfy_ideogram4 import missing_ideogram4_nodes
            from dreamforge_prompt.ideogram4_workflows import (
                ideogram4_workflow_supported,
                ideogram4_workflow_unsupported_error,
                resolve_ideogram4_workflow_kind,
            )

            ig_kind = resolve_ideogram4_workflow_kind(
                workflow_mode=str(workflow_mode or ""),
                input_filename=input_filename or reference_filename,
                mask_filename=mask_filename,
                edit_type=str(edit_type or ""),
            )
            try:
                object_info = client.object_info(timeout_s=30.0)
            except Exception:
                object_info = None
            if not ideogram4_workflow_supported(ig_kind, object_info=object_info):
                missing = missing_ideogram4_nodes(object_info or {}, ig_kind) if object_info else None
                err = ideogram4_workflow_unsupported_error(
                    ig_kind,
                    job_id=job_id,
                    missing_nodes=missing,
                )
                emit_event(stream_sink, err)
                return {"status": "error", **err}
            for warning in settings.get("ideogram4_scheduler_warnings") or []:
                emit_event(
                    stream_sink,
                    {
                        "type": "progress",
                        "job_id": job_id,
                        "phase": "preflight",
                        "progress": 4,
                        "message": str(warning),
                    },
                )
        if comfy_mode == "upscale":
            try:
                object_info = client.object_info(timeout_s=30.0)
            except Exception:
                object_info = {}

            required_nodes = {"UltimateSDUpscale", "UpscaleModelLoader"}
            missing_nodes = sorted(node for node in required_nodes if node not in object_info)
            if missing_nodes:
                try:
                    from dreamforge_comfy_install import ensure_dreamforge_comfy_backend
                    from dreamforge_comfy_server import restart_managed_comfy_server

                    emit_event(
                        stream_sink,
                        {
                            "type": "progress",
                            "job_id": job_id,
                            "phase": "preflight",
                            "progress": 3,
                            "message": "Installing Ultimate SD Upscale support and restarting ComfyUI...",
                        },
                    )
                    ensure_dreamforge_comfy_backend(optional_nodes=True)
                    server = restart_managed_comfy_server(timeout_s=90.0, reason="upscale_nodes")
                    client = ComfyClient(server.base_url)
                    object_info = client.object_info(timeout_s=30.0)
                    missing_nodes = sorted(node for node in required_nodes if node not in object_info)
                except Exception:
                    pass
            if missing_nodes:
                err = missing_custom_node_pack(
                    "ComfyUI_UltimateSDUpscale",
                    job_id=job_id,
                    nodes=missing_nodes,
                )
                emit_event(stream_sink, err)
                return {"status": "error", **err}

        prompt_graph, template_used = _build_comfy_prompt_graph(
            job=job,
            mode=comfy_mode,
            model=model,
            model_family=model_family,
            settings=settings,
            prompt=prompt,
            negative=negative,
            seed=seed,
            edit_strength=edit_strength,
            cn_upscale=cn_upscale,
            input_filename=input_filename or reference_filename,
            mask_filename=mask_filename,
            reference_stitch_filename=reference_stitch_filename,
            grow_mask_by=grow_mask_by,
            model_loader_args=resolved_loaders,
            qwen_reference_filenames=qwen_reference_filenames or None,
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

        if model_family == "ideogram4":
            try:
                client.free_memory(unload_models=True, free_memory=True)
            except Exception:
                pass

        if streaming:
            _res, node = _run_comfy_workflow_with_retry(
                client,
                prompt_graph,
                streaming=True,
                job_id=job_id,
                sample_steps=sample_steps,
                stream_sink=stream_sink,
                on_event=_comfy_stream_event,
            )
        else:
            _res, node = _run_comfy_workflow_with_retry(
                client,
                prompt_graph,
                streaming=False,
                job_id=job_id,
                sample_steps=sample_steps,
                stream_sink=stream_sink,
                on_event=None,
            )
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

        template_id = getattr(job, "template_id", None) or (
            (data or {}).get("template_id") if isinstance(data, dict) else None
        )
        post_upscale_method = getattr(job, "post_upscale", None) or (
            (data or {}).get("post_upscale") if isinstance(data, dict) else None
        )

        primary_result = {
            "status": "success",
            "images": [{"path": path} for path in images],
            "seed": seed,
            "model": model,
            "settings": settings,
            "validation": validation,
        }

        chain_steps = None
        from dreamforge_pipeline_chain import (
            first_image_path,
            run_post_upscale_chain,
            should_run_post_upscale,
        )

        job_data = data if isinstance(data, dict) else None
        if should_run_post_upscale(job, job_data, primary_result=primary_result):
            primary_result = run_post_upscale_chain(
                primary_result,
                base_args=base_args,
                data=job_data,
                stream_sink=stream_sink,
                job_id=job_id,
            )
            chain_steps = primary_result.get("chain_steps")
            chained_path = first_image_path(primary_result)
            if chained_path:
                images = [chained_path]

        manifest_path = None
        if not getattr(job, "no_manifest", False):
            manifest_path = getattr(job, "manifest_path", None) or default_manifest_path(
                images,
                str(PROJECT_ROOT / "outputs"),
            )
            if not Path(manifest_path).is_absolute():
                manifest_path = str(PROJECT_ROOT / manifest_path)
            from dreamforge_edit_lineage import build_edit_lineage

            routing = {
                "input_image": str(input_path) if input_path else None,
                "upscale_image": str(upscale_input_path) if is_upscale_job else None,
                "edit_type": edit_type,
                "cn_selection": cn_selection,
                "cn_type": cn_type,
                "edit_strength": edit_strength,
            }
            if post_upscale_method:
                routing["post_upscale"] = str(post_upscale_method)
                routing["chain"] = ["primary", "upscale"]

            manifest_payload: dict = {
                "schema_version": "1.2",
                "template_id": template_id,
                "prompt": prompt,
                "negative_prompt": settings["negative"],
                "seed": seed,
                "model": model,
                "settings": settings,
                "routing": routing,
                "lineage": build_edit_lineage(
                    job=job,
                    data=job_data,
                    input_image=str(input_path) if input_path else None,
                    upscale_image=str(upscale_input_path) if is_upscale_job else None,
                    inpaint_mask=str(mask_path) if mask_path else None,
                    edit_type=edit_type,
                    output_images=images,
                    chain_steps=chain_steps,
                    template_id=str(template_id) if template_id else None,
                    post_upscale=str(post_upscale_method) if post_upscale_method else None,
                ),
                "images": images,
                "raw_images": raw_images,
                "validation": validation,
            }
            if job_data and job_data.get("automation_id"):
                manifest_payload["automation"] = {
                    "automation_id": job_data.get("automation_id"),
                    "type": job_data.get("automation_type"),
                    "index": job_data.get("automation_index"),
                    "total": job_data.get("automation_total"),
                }

            manifest_path = write_manifest(manifest_path, manifest_payload)

        from dreamforge_engine import _free_comfy_vram

        if _comfy_job_unload_models(cn_type=str(cn_type), comfy_mode=str(comfy_mode)):
            _free_comfy_vram(unload_models=True)

        return {
            **primary_result,
            "manifest": manifest_path,
        }
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        err = from_exception(exc, job_id=job_id)
        _maybe_recover_comfy_after_failure(exc, err)
        emit_event(stream_sink, err)
        return {"status": "error", **err}


_GENERIC_SDXL_PRESETS = frozenset({"Speed", "Quality", "Lightning", "Lcm", "Pony XL"})
_FAMILY_PRESETS = frozenset({"Flux", "HiDream", "HiDream Full", "SD3"})
_UNIFIED_PERFORMANCE_PRESETS = frozenset({"Lightning", "Speed", "Quality", "Custom..."})


def _apply_ideogram4_family_settings(
    settings: dict,
    job,
    model_family: str,
) -> dict:
    """Apply Ideogram 4 quality mode scheduler presets."""
    if (model_family or "").lower() != "ideogram4":
        return settings
    from dreamforge_prompt.ideogram4 import ideogram4_scheduler_params
    from dreamforge_prompt.ideogram4_presets import apply_ideogram4_aspect_preset
    from dreamforge_vram_profiles import profile_tier

    out = dict(settings)
    vram_tier = profile_tier(
        getattr(job, "vram_profile", None)
        or os.environ.get("DREAMFORGE_VRAM_PROFILE")
        or "auto"
    )
    aspect = apply_ideogram4_aspect_preset(out, job=job, vram_tier=vram_tier)
    out["width"] = int(aspect["width"])
    out["height"] = int(aspect["height"])
    out["ideogram4_aspect_preset"] = aspect["ideogram4_aspect_preset"]
    sched = ideogram4_scheduler_params(
        out,
        job=job,
        width=out["width"],
        height=out["height"],
        vram_tier=vram_tier,
    )
    out["steps"] = int(sched["steps"])
    out["cfg"] = float(sched["dual_cfg"])
    out["sampler_name"] = "euler"
    out["scheduler"] = "simple"
    out["ideogram4_mode"] = sched["mode"]
    out["ideogram4_mu"] = sched["mu"]
    out["ideogram4_std"] = sched["std"]
    out["ideogram4_cfg_override"] = sched.get("cfg_override")
    out["ideogram4_cfg_override_start"] = sched.get("cfg_override_start")
    out["ideogram4_cfg_override_end"] = sched.get("cfg_override_end")
    out["enable_vae_tiling"] = vram_tier in {"16gb", "8gb", "5gb"}
    out["ideogram4_scheduler_warnings"] = list(sched.get("warnings") or [])
    return out


def _apply_qwen_family_settings(
    settings: dict,
    job,
    model_family: str,
    *,
    is_live: bool = False,
) -> dict:
    """Apply Qwen txt2img/edit recipe defaults and advanced overrides."""
    family = (model_family or "").lower()
    if not family.startswith("qwen"):
        return settings

    out = dict(settings)
    edit_type = str(getattr(job, "edit_type", "auto") or "auto").lower()
    has_input = bool(getattr(job, "input_image", None) or getattr(job, "upscale_image", None))
    custom_perf = str(getattr(job, "performance", "") or "").strip() in ("Custom...", "Custom")
    explicit_sampling = any(
        getattr(job, attr, None) is not None
        for attr in ("steps", "cfg_scale", "sampler", "scheduler")
    )

    try:
        from dreamforge_krita_recipes import edit_recipe, generation_recipe, qwen_model_params

        params = qwen_model_params(
            family,
            edit_type=edit_type,
            vram_profile=getattr(job, "vram_profile", "auto"),
        )
        recipe_family = "qwen_image_edit" if has_input and family.startswith("qwen") else family
        recipe = edit_recipe(recipe_family, "qwen_edit") if has_input else generation_recipe(family)
    except ImportError:
        params = {}
        recipe = None

    if recipe and not custom_perf and not explicit_sampling:
        out["steps"] = int(recipe.get("custom_steps", out.get("steps", 20)))
        out["cfg"] = float(recipe.get("cfg", out.get("cfg", 2.5)))
        out["sampler_name"] = recipe.get("sampler_name", out.get("sampler_name"))
        out["scheduler"] = recipe.get("scheduler", out.get("scheduler"))
        out["clip_skip"] = int(recipe.get("clip_skip", out.get("clip_skip", 1)))

    if getattr(job, "qwen_image_shift", None) is not None:
        out["qwen_image_shift"] = float(job.qwen_image_shift)
    elif params.get("qwen_image_shift") is not None:
        out["qwen_image_shift"] = float(params["qwen_image_shift"])
    elif family.startswith("qwen"):
        out.setdefault("qwen_image_shift", 3.1)

    if getattr(job, "qwen_scale_megapixels", None) is not None:
        out["qwen_scale_megapixels"] = float(job.qwen_scale_megapixels)
    elif (
        params.get("qwen_scale_megapixels") is not None
        and has_input
        and family.startswith("qwen")
    ):
        out["qwen_scale_megapixels"] = float(params["qwen_scale_megapixels"])

    perf = str(getattr(job, "performance", "") or "").strip().lower()
    model_name = " ".join(
        str(getattr(job, attr, "") or "")
        for attr in ("model", "engine_name", "relative_path")
    ).lower()
    from dreamforge_cli_inventory import qwen_fused_lightning_model, qwen_lightning_lora_requested
    from dreamforge_prompt.pipeline import _qwen_edit_needs_quality_pass

    fused_lightning = qwen_fused_lightning_model(model_name)
    lightning_requested = qwen_lightning_lora_requested(perf) or fused_lightning
    prompt_text = str(getattr(job, "prompt", "") or "")
    global_edit = has_input and family.startswith("qwen") and _qwen_edit_needs_quality_pass(prompt_text)

    if has_input and family.startswith("qwen") and lightning_requested and not global_edit:
        if not fused_lightning:
            out["use_qwen_lightning_lora"] = True
        if perf == "lightning":
            out["qwen_lightning_strength"] = 0.75
            if getattr(job, "qwen_scale_megapixels", None) is None:
                out.setdefault("qwen_scale_megapixels", 1.25)
        elif perf in ("speed", "lcm"):
            out["qwen_lightning_strength"] = 1.0
        if not custom_perf:
            if perf == "lightning":
                out["steps"] = 8
            else:
                out["steps"] = 4
            out["cfg"] = 1.0
            out["sampler_name"] = "euler"
            out["scheduler"] = "simple"

    if global_edit:
        if not custom_perf:
            out["use_qwen_lightning_lora"] = False
            out["steps"] = 20
            out["cfg"] = 2.5
            out["sampler_name"] = "euler"
            out["scheduler"] = "beta"
            out["escalation_reason"] = "Global edit detected (outfit + scene/pose) -> Quality pass escalated"
    elif perf == "quality" and has_input and family.startswith("qwen"):
        if not custom_perf:
            out["use_qwen_lightning_lora"] = False
            out["steps"] = 20
            out["cfg"] = 2.5
            out["sampler_name"] = "euler"
            out["scheduler"] = "beta"

    return out


def _coerce_performance_preset(requested: str | None, family_preset: str | None) -> str | None:
    """Avoid applying SDXL Speed/Quality presets to Flux, HiDream, SD3, etc."""
    if not requested:
        return family_preset
    if requested in _GENERIC_SDXL_PRESETS and family_preset in _FAMILY_PRESETS:
        return family_preset
    return requested


def _tune_edit_job_settings(
    settings: dict,
    job,
    model_family: str,
    *,
    is_live: bool = False,
) -> dict:
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
        out["performance_selection"] = perf if perf in _UNIFIED_PERFORMANCE_PRESETS else "Lightning"
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

    try:
        from dreamforge_vram_profiles import profile_tier

        tier = profile_tier(
            os.environ.get("DREAMFORGE_VRAM_PROFILE")
            or os.environ.get("DREAMFORGE_DESKTOP_VRAM_MODE")
            or "auto"
        )
    except Exception:
        tier = os.environ.get("DREAMFORGE_DESKTOP_VRAM_MODE", "16gb")
    step_cap = {"5gb": 12, "8gb": 20, "16gb": 24}.get(tier, 20)
    if not custom_perf:
        out["steps"] = min(int(out.get("steps", step_cap)), step_cap)

    if is_live and not explicit_sampling:
        try:
            from dreamforge_krita_recipes import live_sampling_params

            live = live_sampling_params(family, edit_type)
        except ImportError:
            live = None
        if live:
            out["steps"] = int(live["steps"])
            out["cfg"] = float(live["cfg"])
            if live.get("sampler_name"):
                out["sampler_name"] = live["sampler_name"]
            if live.get("scheduler"):
                out["scheduler"] = live["scheduler"]

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

    # Flux Fill inpaint needs high CFG (≈30). Custom... performance from a prior Kontext
    # edit must not leave Kontext-style CFG on the job.
    if edit_type == "inpaint" and recipe:
        if getattr(job, "cfg_scale", None) is None:
            out["cfg"] = float(
                recipe.get("live_cfg" if is_live else "cfg", recipe.get("cfg", 30.0))
            )
        if getattr(job, "steps", None) is None:
            step_key = "live_steps" if is_live else "custom_steps"
            if step_key in recipe:
                out["steps"] = int(recipe[step_key])
        if getattr(job, "sampler", None) is None:
            out["sampler_name"] = recipe.get("sampler_name", out.get("sampler_name", "euler"))
        if getattr(job, "scheduler", None) is None:
            out["scheduler"] = recipe.get("scheduler", out.get("scheduler", "simple"))

    return out


def _apply_job_performance(settings: dict, job, model_family: str = "") -> dict:
    """Honor unified performance names while preserving legacy family presets."""
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
        if perf in {"Lightning", "Speed", "Quality"} and model_family:
            from modules.model_ui_defaults import family_performance_settings

            model_name = str(getattr(job, "model", "") or out.get("base_model", "") or "")
            opts = family_performance_settings(model_family, model_name, perf)
        else:
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
