"""Resolve ComfyUI loader inputs against object_info and on-disk companions."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from dreamforge_cli_inventory import (
    MODEL_DEPENDENCIES,
    MODELS_ROOT,
    check_model_dependencies,
    companion_file_present,
)


def _object_info_options(object_info: dict[str, Any], node_class: str, input_name: str) -> list[str]:
    node = object_info.get(node_class) or {}
    inputs = node.get("input") or {}
    cfg = (inputs.get("required") or {}).get(input_name)
    if cfg is None:
        cfg = (inputs.get("optional") or {}).get(input_name)
    if cfg is None:
        return []
    choices = cfg[0] if isinstance(cfg, (list, tuple)) and cfg else cfg
    if isinstance(choices, list):
        return [str(item) for item in choices]
    return []


def _basename_match(wanted: str, choices: list[str]) -> str | None:
    if not wanted or not choices:
        return None
    name = Path(str(wanted)).name
    if name in choices:
        return name
    lower = name.lower()
    for choice in choices:
        if choice.lower() == lower:
            return choice
    stem = Path(name).stem.lower()
    for choice in choices:
        if Path(choice).stem.lower() == stem:
            return choice
    return None


def _flux_companion_basenames_on_disk(family: str) -> dict[str, str]:
    """Map flux loader keys to basenames of files present under MODELS_ROOT."""
    dep_family = family if family in MODEL_DEPENDENCIES else "flux"
    out: dict[str, str] = {}
    for req in MODEL_DEPENDENCIES.get(dep_family, MODEL_DEPENDENCIES.get("flux", [])):
        if req.get("optional") or not companion_file_present(req):
            continue
        relative = str(req.get("relative") or "")
        basename = Path(relative).name
        req_id = str(req.get("id") or "")
        if "clip_l" in req_id or basename.startswith("clip_l"):
            out["clip_l"] = basename
        elif "t5" in req_id or "t5xxl" in basename.lower():
            out["t5"] = basename
        elif "vae" in req_id or basename in ("ae.safetensors", "flux_vae.safetensors"):
            out["vae"] = basename
    return out


def _qwen_companion_basenames_on_disk(family: str) -> dict[str, str]:
    """Map Qwen loader keys to companion basenames on disk."""
    dep_families = []
    if family in MODEL_DEPENDENCIES:
        dep_families.append(family)
    if "qwen_image" not in dep_families:
        dep_families.append("qwen_image")
    out: dict[str, str] = {}
    for dep_family in dep_families:
        for req in MODEL_DEPENDENCIES.get(dep_family, []):
            if req.get("optional") or not companion_file_present(req):
                continue
            relative = str(req.get("relative") or "")
            basename = Path(relative).name
            req_id = str(req.get("id") or "")
            if "vae" in req_id or "vae" in basename.lower():
                out["vae"] = basename
            elif "clip" in req_id or "qwen" in basename.lower():
                out["clip"] = basename
    return out


def _hidream_companion_basenames_on_disk(family: str) -> dict[str, str]:
    """Map HiDream split-loader keys to companion basenames on disk."""
    out: dict[str, str] = {}
    for req in MODEL_DEPENDENCIES.get("hidream", []) + MODEL_DEPENDENCIES.get("hidream_o1", []):
        if req.get("optional") or not companion_file_present(req):
            continue
        relative = str(req.get("relative") or "")
        basename = Path(relative).name
        req_id = str(req.get("id") or "")
        if "clip_l" in req_id or basename.startswith("clip_l"):
            out["clip_l"] = basename
        elif "clip_g" in req_id or basename.startswith("clip_g"):
            out["clip_g"] = basename
        elif "t5" in req_id or "t5xxl" in basename.lower():
            out["t5"] = basename
        elif "llama" in req_id or "llama" in basename.lower():
            out["llama"] = basename
        elif "vae" in req_id or basename in ("ae.safetensors", "flux_vae.safetensors"):
            out["vae"] = basename
    if not out.get("vae"):
        for alt in ("ae.safetensors",):
            if companion_file_present({"relative": f"vae/{alt}"}):
                out["vae"] = alt
                break
    return out


class ComfyModelResolutionError(RuntimeError):
    """Raised when Comfy cannot load required weights for a workflow."""

    def __init__(self, message: str, *, missing: list[str] | None = None, suggestions: list[str] | None = None):
        super().__init__(message)
        self.missing = list(missing or [])
        self.suggestions = list(suggestions or [])


def resolve_comfy_model_loader_args(
    client: Any,
    *,
    model: dict[str, Any],
    model_family: str,
) -> dict[str, Any]:
    """Return workflow args with Comfy-valid loader names (unet/clip/vae/checkpoint)."""
    object_info = client.object_info()
    category = str(model.get("category") or "checkpoints").lower()
    rel = str(model.get("relative_path") or model.get("name") or "")
    family = str(model_family or model.get("family") or "").lower()
    basename = Path(rel).name

    args: dict[str, Any] = {
        "category": category,
        "relative_path": basename,
        "family": family,
        "ckpt_name": model.get("name") or basename,
    }

    if category not in ("diffusion_models", "unet"):
        ckpt_choices = _object_info_options(object_info, "CheckpointLoaderSimple", "ckpt_name")
        matched = _basename_match(str(args["ckpt_name"]), ckpt_choices)
        if matched:
            args["ckpt_name"] = matched
        elif ckpt_choices and basename not in ckpt_choices:
            raise ComfyModelResolutionError(
                f"Checkpoint '{basename}' is not visible to ComfyUI. "
                f"Place it under {MODELS_ROOT / 'checkpoints'} and restart the GPU engine.",
                missing=[basename],
                suggestions=[
                    f"Models root: {MODELS_ROOT}",
                    "Restart GPU engine after adding files.",
                ],
            )
        return args

    unet_choices = _object_info_options(object_info, "UNETLoader", "unet_name")
    matched_unet = _basename_match(basename, unet_choices)
    if not matched_unet:
        matched_unet = basename

    args["unet_name"] = matched_unet
    args["relative_path"] = matched_unet
    args["ckpt_name"] = matched_unet

    problems: list[str] = []
    if not unet_choices:
        problems.append(
            f"ComfyUI reports no UNet/diffusion_models files (expected '{basename}' under "
            f"{Path(MODELS_ROOT).resolve() / 'diffusion_models'} or {Path(MODELS_ROOT).resolve() / 'unet'})."
        )
    elif matched_unet not in unet_choices:
        problems.append(
            f"UNet '{basename}' is on disk for DreamForge but ComfyUI cannot see it "
            f"(got {len(unet_choices)} file(s) in diffusion_models/unet)."
        )

    if family.startswith("flux"):
        on_disk = _flux_companion_basenames_on_disk(family)
        clip1_choices = _object_info_options(object_info, "DualCLIPLoader", "clip_name1")
        clip2_choices = _object_info_options(object_info, "DualCLIPLoader", "clip_name2")
        vae_choices = _object_info_options(object_info, "VAELoader", "vae_name")

        clip_l = _basename_match(on_disk.get("clip_l", "clip_l.safetensors"), clip1_choices)
        t5 = _basename_match(on_disk.get("t5", "t5xxl_fp8_e4m3fn_scaled.safetensors"), clip2_choices)
        vae = _basename_match(on_disk.get("vae", "ae.safetensors"), vae_choices)
        if not vae and "pixel_space" in vae_choices:
            vae = "pixel_space"

        if clip_l:
            args["clip_l"] = clip_l
        elif on_disk.get("clip_l"):
            problems.append(
                f"CLIP-L '{on_disk['clip_l']}' exists under {Path(MODELS_ROOT).resolve()} but ComfyUI clip/text_encoders list is empty."
            )
        elif not clip1_choices:
            problems.append("ComfyUI reports no CLIP/text encoder files for DualCLIPLoader.")

        if t5:
            args["t5"] = t5
        elif on_disk.get("t5"):
            problems.append(
                f"T5 '{on_disk['t5']}' exists under {Path(MODELS_ROOT).resolve()} but ComfyUI does not list it for DualCLIPLoader."
            )

        if vae:
            args["vae"] = vae
        elif on_disk.get("vae"):
            problems.append(
                f"VAE '{on_disk['vae']}' exists under {MODELS_ROOT} but ComfyUI vae list is: {vae_choices!r}."
            )
        elif not vae_choices:
            problems.append("ComfyUI reports no VAE files.")

        missing_deps = check_model_dependencies(model)
        if missing_deps:
            for item in missing_deps[:4]:
                problems.append(f"Missing companion: {item.get('relative')} — {item.get('note', '')}")

    elif family.startswith("qwen"):
        on_disk = _qwen_companion_basenames_on_disk(family)
        clip_choices = _object_info_options(object_info, "CLIPLoader", "clip_name")
        clip_choices += _object_info_options(object_info, "CLIPLoaderGGUF", "clip_name")
        vae_choices = _object_info_options(object_info, "VAELoader", "vae_name")
        default_clip = on_disk.get("clip", "qwen_2.5_vl_7b_fp8_scaled.safetensors")
        clip = _basename_match(default_clip, clip_choices)
        vae = _basename_match(on_disk.get("vae", "qwen_image_vae.safetensors"), vae_choices)
        if clip:
            args["clip"] = clip
        elif on_disk.get("clip"):
            problems.append(
                f"Qwen CLIP '{on_disk['clip']}' exists under {Path(MODELS_ROOT).resolve()} "
                "but ComfyUI does not list it for CLIPLoader."
            )
        elif not clip_choices:
            problems.append("ComfyUI reports no Qwen text encoder files for CLIPLoader.")
        if vae:
            args["vae"] = vae
        elif on_disk.get("vae"):
            problems.append(
                f"Qwen VAE '{on_disk['vae']}' exists under {MODELS_ROOT} but ComfyUI vae list is: {vae_choices!r}."
            )
        elif not vae_choices:
            problems.append("ComfyUI reports no VAE files for Qwen workflows.")
        missing_deps = check_model_dependencies(model)
        if missing_deps:
            for item in missing_deps[:4]:
                problems.append(f"Missing companion: {item.get('relative')} — {item.get('note', '')}")

    elif family in ("hidream", "hidream_o1"):
        on_disk = _hidream_companion_basenames_on_disk(family)
        quad = _object_info_options(object_info, "QuadrupleCLIPLoader", "clip_name1")
        vae_choices = _object_info_options(object_info, "VAELoader", "vae_name")
        clip_l = _basename_match(on_disk.get("clip_l", "clip_l.safetensors"), quad)
        if clip_l:
            args["clip_l"] = clip_l
        vae = _basename_match(on_disk.get("vae", "ae.safetensors"), vae_choices)
        if vae:
            args["vae"] = vae
        elif not vae_choices:
            problems.append("ComfyUI reports no VAE files for HiDream workflows.")

    if problems:
        models_root = Path(MODELS_ROOT).resolve()
        family_label = family or "model"
        companion_hint = "Install required companion weights and restart the GPU engine."
        if family.startswith("flux"):
            companion_hint = "Install Flux companions under vae/, text_encoders/, and clip/ if missing."
        elif family.startswith("qwen"):
            companion_hint = (
                "Install qwen_2.5_vl_7b_fp8_scaled.safetensors under text_encoders/ or clip/ "
                "and qwen_image_vae.safetensors under vae/."
            )
        elif family.startswith("hidream"):
            companion_hint = (
                "HiDream split loaders need clip_l, clip_g, t5xxl, llama text encoders and ae.safetensors, "
                "or use a full checkpoint under checkpoints/."
            )
        suggestions = [
            f"Models folder resolves to: {models_root}",
            "Stop any other ComfyUI on port 8188, then click Restart GPU engine.",
            companion_hint,
        ]
        raise ComfyModelResolutionError(
            f"Cannot run this {family_label} workflow in ComfyUI until models are visible to the managed server.\n"
            + "\n".join(f"- {p}" for p in problems),
            missing=problems,
            suggestions=suggestions,
        )

    return args


def verify_comfy_model_paths_loaded(
    client: Any,
    *,
    models_root: Path | None = None,
) -> None:
    """Fail fast at boot when Comfy cannot see weights that exist on disk."""
    root = Path(models_root or MODELS_ROOT).resolve()
    object_info = client.object_info()
    unet_choices = _object_info_options(object_info, "UNETLoader", "unet_name")
    te_choices = _object_info_options(object_info, "DualCLIPLoader", "clip_name1")

    diffusion_dir = root / "diffusion_models"
    on_disk_unets = (
        list(diffusion_dir.glob("*.safetensors")) + list((root / "unet").glob("*.safetensors"))
        if diffusion_dir.is_dir() or (root / "unet").is_dir()
        else []
    )
    te_dir = root / "text_encoders"
    on_disk_te = list(te_dir.glob("*.safetensors")) if te_dir.is_dir() else []

    problems: list[str] = []
    if on_disk_unets and not unet_choices:
        problems.append(
            f"Found {len(on_disk_unets)} UNet file(s) under {root} but ComfyUI lists none "
            f"(likely attached to a foreign Comfy without DreamForge extra_model_paths)."
        )
    if on_disk_te and not te_choices:
        problems.append(
            f"Found {len(on_disk_te)} text encoder file(s) under {te_dir} but ComfyUI lists none."
        )

    if problems:
        raise ComfyModelResolutionError(
            "Managed ComfyUI started but cannot see DreamForge models.\n"
            + "\n".join(f"- {p}" for p in problems),
            missing=problems,
            suggestions=[
                f"Resolved models root: {root}",
                "Close other ComfyUI instances, then Restart GPU engine in DreamForge.",
            ],
        )
