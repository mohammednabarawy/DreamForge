"""Load ComfyUI workflows exported via Save (API Format).

Comfy's API prompt is a flat dict keyed by node id strings:

    {"3": {"class_type": "KSampler", "inputs": {...}}, ...}

This module loads those templates and patches common DreamForge bindings.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any


def _looks_like_api_prompt(data: Any) -> bool:
    if not isinstance(data, dict) or not data:
        return False
    for value in data.values():
        if not isinstance(value, dict):
            return False
        if "class_type" not in value:
            return False
        if "inputs" not in value or not isinstance(value["inputs"], dict):
            return False
    return True


def load_api_workflow_template(path: str | Path) -> dict[str, Any]:
    """Read an API-format workflow JSON file."""
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if isinstance(data, dict) and isinstance(data.get("prompt"), dict):
        data = data["prompt"]
    if not _looks_like_api_prompt(data):
        raise ValueError(
            f"{path} is not Comfy Save (API Format) JSON "
            "(expected node dict with class_type + inputs)."
        )
    return copy.deepcopy(data)


def resolve_comfy_workflow_template(
    *,
    mode: str,
    explicit_path: str | None = None,
) -> Path | None:
    """Resolve optional API workflow template path from job or env."""
    candidates: list[str] = []
    if explicit_path:
        candidates.append(str(explicit_path).strip())
    mode_key = (mode or "auto").strip().lower()
    env_by_mode = {
        "txt2img": "DREAMFORGE_COMFY_WORKFLOW_TXT2IMG",
        "img2img": "DREAMFORGE_COMFY_WORKFLOW_IMG2IMG",
        "kontext": "DREAMFORGE_COMFY_WORKFLOW_KONTEXT",
        "inpaint": "DREAMFORGE_COMFY_WORKFLOW_INPAINT",
        "upscale": "DREAMFORGE_COMFY_WORKFLOW_UPSCALE",
    }
    mode_env = env_by_mode.get(mode_key)
    if mode_env:
        candidates.append(os.environ.get(mode_env, "").strip())
    candidates.append(os.environ.get("DREAMFORGE_COMFY_WORKFLOW_API", "").strip())
    for item in candidates:
        if not item:
            continue
        path = Path(item)
        if path.is_file():
            return path
    return None


def _set_first_matching_input(
    graph: dict[str, Any],
    *,
    class_types: tuple[str, ...],
    input_names: tuple[str, ...],
    value: Any,
) -> bool:
    for node in graph.values():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") not in class_types:
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for name in input_names:
            if name in inputs:
                inputs[name] = value
                return True
    return False


def patch_api_workflow(graph: dict[str, Any], bindings: dict[str, Any]) -> dict[str, Any]:
    """Patch a cloned API workflow with DreamForge generation bindings."""
    out = copy.deepcopy(graph)

    ckpt = bindings.get("ckpt_name")
    if ckpt:
        _set_first_matching_input(
            out,
            class_types=("CheckpointLoaderSimple",),
            input_names=("ckpt_name",),
            value=str(ckpt),
        )
    category = str(bindings.get("category") or "").lower()
    relative = bindings.get("relative_path")
    unet_name = str(relative or ckpt or "")
    for prefix in ("../diffusion_models/", "..\\diffusion_models\\", "../unet/", "..\\unet\\"):
        if unet_name.lower().startswith(prefix):
            unet_name = unet_name[len(prefix) :]
    if category in ("diffusion_models", "unet") and unet_name:
        _set_first_matching_input(
            out,
            class_types=("UNETLoader", "UnetLoaderGGUF"),
            input_names=("unet_name",),
            value=unet_name,
        )
        _set_first_matching_input(
            out,
            class_types=("DualCLIPLoader", "DualCLIPLoaderGGUF"),
            input_names=("clip_name1",),
            value=str(bindings.get("clip_l") or "clip_l.safetensors"),
        )
        _set_first_matching_input(
            out,
            class_types=("DualCLIPLoader", "DualCLIPLoaderGGUF"),
            input_names=("clip_name2",),
            value=str(bindings.get("t5") or "t5xxl_fp8_e4m3fn_scaled.safetensors"),
        )
        _set_first_matching_input(
            out,
            class_types=("VAELoader",),
            input_names=("vae_name",),
            value=str(bindings.get("vae") or "ae.safetensors"),
        )

    prompt = bindings.get("prompt")
    if prompt is not None:
        _set_first_matching_input(
            out,
            class_types=("CLIPTextEncode",),
            input_names=("text",),
            value=str(prompt),
        )

    negative = bindings.get("negative")
    if negative is not None:
        patched = False
        for node in out.values():
            if not isinstance(node, dict) or node.get("class_type") != "CLIPTextEncode":
                continue
            inputs = node.get("inputs") or {}
            text = str(inputs.get("text", "")).lower()
            if any(token in text for token in ("negative", "bad", "worst", "low quality")):
                inputs["text"] = str(negative)
                patched = True
                break
        if not patched:
            # Fall back to second CLIPTextEncode node if present.
            clip_nodes = [
                n
                for n in out.values()
                if isinstance(n, dict) and n.get("class_type") == "CLIPTextEncode"
            ]
            if len(clip_nodes) > 1:
                clip_nodes[1].setdefault("inputs", {})["text"] = str(negative)

    image = bindings.get("image")
    if image:
        _set_first_matching_input(
            out,
            class_types=("LoadImage",),
            input_names=("image",),
            value=str(image),
        )

    reference_stitch = bindings.get("reference_stitch")
    if reference_stitch:
        load_nodes = [
            node
            for node in out.values()
            if isinstance(node, dict) and node.get("class_type") == "LoadImage"
        ]
        if len(load_nodes) > 1:
            load_nodes[1].setdefault("inputs", {})["image"] = str(reference_stitch)

    mask = bindings.get("mask")
    if mask:
        load_nodes = [
            (node_id, node)
            for node_id, node in out.items()
            if isinstance(node, dict) and node.get("class_type") == "LoadImage"
        ]
        if len(load_nodes) > 1:
            _node_id, node = load_nodes[1]
            node.setdefault("inputs", {})["image"] = str(mask)
        else:
            _set_first_matching_input(
                out,
                class_types=("LoadImage",),
                input_names=("image",),
                value=str(mask),
            )

    upscale_model = bindings.get("upscale_model")
    if upscale_model:
        _set_first_matching_input(
            out,
            class_types=("UpscaleModelLoader",),
            input_names=("model_name",),
            value=str(upscale_model),
        )

    seed = bindings.get("seed")
    if seed is not None:
        _set_first_matching_input(
            out,
            class_types=("KSampler",),
            input_names=("seed",),
            value=int(seed),
        )

    steps = bindings.get("steps")
    if steps is not None:
        _set_first_matching_input(
            out,
            class_types=("KSampler",),
            input_names=("steps",),
            value=int(steps),
        )

    cfg = bindings.get("cfg")
    if cfg is not None:
        _set_first_matching_input(
            out,
            class_types=("KSampler",),
            input_names=("cfg",),
            value=float(cfg),
        )
        _set_first_matching_input(
            out,
            class_types=("FluxGuidance",),
            input_names=("guidance",),
            value=float(cfg),
        )

    denoise = bindings.get("denoise")
    if denoise is not None:
        _set_first_matching_input(
            out,
            class_types=("KSampler",),
            input_names=("denoise",),
            value=float(denoise),
        )

    width = bindings.get("width")
    height = bindings.get("height")
    if width is not None and height is not None:
        _set_first_matching_input(
            out,
            class_types=("EmptyLatentImage", "EmptySD3LatentImage"),
            input_names=("width",),
            value=int(width),
        )
        _set_first_matching_input(
            out,
            class_types=("EmptyLatentImage", "EmptySD3LatentImage"),
            input_names=("height",),
            value=int(height),
        )

    sampler = bindings.get("sampler_name")
    if sampler:
        _set_first_matching_input(
            out,
            class_types=("KSampler",),
            input_names=("sampler_name",),
            value=str(sampler),
        )

    scheduler = bindings.get("scheduler")
    if scheduler:
        _set_first_matching_input(
            out,
            class_types=("KSampler",),
            input_names=("scheduler",),
            value=str(scheduler),
        )

    grow_mask_by = bindings.get("grow_mask_by")
    if grow_mask_by is not None:
        _set_first_matching_input(
            out,
            class_types=("VAEEncodeForInpaint",),
            input_names=("grow_mask_by",),
            value=int(grow_mask_by),
        )

    prefix = bindings.get("filename_prefix")
    if prefix:
        _set_first_matching_input(
            out,
            class_types=("SaveImage",),
            input_names=("filename_prefix",),
            value=str(prefix),
        )

    return out


def build_prompt_from_template(path: str | Path, bindings: dict[str, Any]) -> dict[str, Any]:
    graph = load_api_workflow_template(path)
    return patch_api_workflow(graph, bindings)


def coerce_reference_image_paths(job) -> list[str]:
    """Extra Kontext/control reference images (Krita multi-reference conditioning)."""
    raw = getattr(job, "reference_images", None)
    if raw is None:
        raw = getattr(job, "control_images", None)
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                raw = parsed
            except json.JSONDecodeError:
                raw = [part.strip() for part in text.split(",") if part.strip()]
        else:
            raw = [part.strip() for part in text.split(",") if part.strip()]
    if not isinstance(raw, (list, tuple)):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        path = str(item or "").strip()
        if not path:
            continue
        key = path.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def comfy_workflow_mode(
    *,
    input_filename: str | None,
    cn_type: str,
    model: dict,
    model_family: str,
    checkpoint_is_flux_kontext,
    workflow_mode: str | None = None,
    edit_type: str | None = None,
) -> str:
    mode_key = str(workflow_mode or "").strip().lower()
    edit = str(edit_type or "").lower()
    if mode_key == "hires":
        return "hires"
    if mode_key in ("area_composition", "composite"):
        return "area_composition"
    if mode_key == "ipadapter":
        return "ipadapter"
    if mode_key == "face_detail" or edit == "face_detail":
        return "face_detail"
    cn = str(cn_type or "None").lower()
    controlnet_types = {
        "depth",
        "canny",
        "pose",
        "openpose",
        "lineart",
        "scribble",
        "sketch",
        "recolour",
        "controlnet",
        "controlnet_structure",
    }
    if cn == "outpaint" or edit == "outpaint" or mode_key == "outpaint":
        return "outpaint"
    if cn in controlnet_types or mode_key == "controlnet":
        return "controlnet"
    if cn == "ipadapter" or mode_key == "reference":
        return "ipadapter"
    if cn == "area_composition":
        return "area_composition"
    if input_filename:
        if cn == "upscale":
            return "upscale"
        if cn == "inpaint":
            return "inpaint"
        if checkpoint_is_flux_kontext(model, model_family):
            return "kontext"
        return "img2img"
    if (model_family or "").startswith("flux"):
        return "txt2img"
    return "txt2img"
