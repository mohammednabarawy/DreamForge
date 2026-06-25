"""Workflow builders for ComfyUI API prompt format.

NOTE: The portable workflows you pointed to are Comfy *UI graph* JSON. Comfy's API
expects a different structure:

{
  "1": {"class_type": "CheckpointLoaderSimple", "inputs": {...}},
  "2": {"class_type": "CLIPTextEncode", "inputs": {...}},
  ...
}

We generate that API format here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dreamforge_upscale_defaults import (
    UPSCALE_CFG,
    UPSCALE_DENOISE,
    UPSCALE_MASK_BLUR,
    UPSCALE_MODE_TYPE,
    UPSCALE_SAMPLER,
    UPSCALE_SCHEDULER,
    UPSCALE_SEAM_FIX_MODE,
    UPSCALE_STEPS,
    UPSCALE_TILE_HEIGHT,
    UPSCALE_TILE_PADDING,
    UPSCALE_TILE_WIDTH,
)


def _node(class_type: str, inputs: dict[str, Any]) -> dict[str, Any]:
    return {"class_type": class_type, "inputs": inputs}


def _vae_decode_node(args: dict[str, Any], samples: list[str | int] | list[Any], vae: list[str | int] | list[Any]) -> dict[str, Any]:
    width = int(args.get("width", 1024))
    height = int(args.get("height", 1024))
    pixels = width * height
    explicit = args.get("enable_vae_tiling")
    if explicit is True or (explicit is None and pixels > 1024 * 1024):
        tile_size = int(args.get("vae_tile_size") or 512)
        overlap = int(args.get("vae_tile_overlap") or 64)
        return {
            "class_type": "VAEDecodeTiled",
            "inputs": {
                "samples": samples,
                "vae": vae,
                "tile_size": tile_size,
                "overlap": overlap,
                # ComfyUI 0.24+ requires these even for image VAEs (ignored for non-video).
                "temporal_size": int(args.get("vae_temporal_size") or 64),
                "temporal_overlap": int(args.get("vae_temporal_overlap") or 8),
            },
        }
    return {"class_type": "VAEDecode", "inputs": {"samples": samples, "vae": vae}}


def _comfy_model_name(args: dict[str, Any]) -> str:
    if args.get("unet_name"):
        return str(args["unet_name"])
    name = str(args.get("relative_path") or args.get("ckpt_name") or "")
    for prefix in ("../diffusion_models/", "..\\diffusion_models\\", "../unet/", "..\\unet\\"):
        if name.lower().startswith(prefix):
            return name[len(prefix) :]
    return Path(name).name if name else name


def _model_category(args: dict[str, Any]) -> str:
    category = str(args.get("category") or "").lower()
    name = str(args.get("ckpt_name") or "").replace("\\", "/").lower()
    if category:
        return category
    if name.startswith("../diffusion_models/"):
        return "diffusion_models"
    if name.startswith("../unet/"):
        return "unet"
    return "checkpoints"


def _nunchaku_cond_nodes(
    g: dict[str, Any],
    p: dict[str, Any],
    model_out: list[Any],
    clip_out: list[Any],
    start_id: int,
) -> tuple[list[Any], list[Any], list[Any], int]:
    g[str(start_id)] = _node("CLIPTextEncode", {"clip": clip_out, "text": p["prompt"]})
    pos = [str(start_id), 0]
    g[str(start_id + 1)] = _node("CLIPTextEncode", {"clip": clip_out, "text": p["negative"]})
    neg = [str(start_id + 1), 0]
    n = start_id + 2
    if p["family"] == "flux":
        g[str(n)] = _node("FluxGuidance", {"conditioning": pos, "guidance": p["cfg"]})
        pos = [str(n), 0]
        n += 1
    return model_out, pos, neg, n


def _z_image_clip_loader_type() -> str:
    """Official Comfy Z-Image-Turbo templates use lumina2 with qwen_3_4b text encoders."""
    return "lumina2"


def _apply_z_image_model_sampling(
    model_out: list[str | int],
    g: dict[str, Any],
    start_id: int,
    args: dict[str, Any],
) -> tuple[list[str | int], int]:
    shift_value = args.get("qwen_image_shift")
    if shift_value is None:
        shift_value = args.get("lumina2_shift")
    if shift_value is None:
        shift_value = args.get("shift")
    if shift_value is None:
        shift_value = 3.0
    g[str(start_id)] = _node(
        "ModelSamplingAuraFlow",
        {"model": model_out, "shift": float(shift_value)},
    )
    return [str(start_id), 0], start_id + 1


def comfy_z_image_txt2img(args: dict[str, Any]) -> dict[str, Any]:
    """Z-Image txt2img."""
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    width = int(args.get("width", 1024))
    height = int(args.get("height", 1024))
    steps = int(args.get("steps", 20))
    cfg = float(args.get("cfg", 3.5))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "simple"))
    seed = int(args.get("seed", 0))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    model_sampled, n = _apply_z_image_model_sampling(model_out, g, n, args)
    g["2"] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    g["3"] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    g["4"] = _node("EmptySD3LatentImage", {"width": width, "height": height, "batch_size": 1})
    g["5"] = _node(
        "KSampler",
        {
            "model": model_sampled,
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["4", 0],
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": 1.0,
        },
    )
    g["6"] = _vae_decode_node(args, ["5", 0], vae_out)
    g["7"] = _node(
        "SaveImage",
        {"images": ["6", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def comfy_z_image_img2img(args: dict[str, Any]) -> dict[str, Any]:
    """Z-Image img2img — VAEEncode reference + AuraFlow sampling (official Comfy template)."""
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    image_filename = str(args["image"])
    steps = int(args.get("steps", 20))
    cfg = float(args.get("cfg", 3.5))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "simple"))
    seed = int(args.get("seed", 0))
    denoise = float(args.get("denoise", args.get("edit_strength", 0.35)))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    model_sampled, n = _apply_z_image_model_sampling(model_out, g, n, args)
    pixels = _img2img_source_pixels(g, args, image_filename, load_id="2", scale_id="20")
    g["3"] = _node("VAEEncode", {"pixels": pixels, "vae": vae_out})
    g["4"] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    g["5"] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    g["6"] = _node(
        "KSampler",
        {
            "model": model_sampled,
            "positive": ["4", 0],
            "negative": ["5", 0],
            "latent_image": ["3", 0],
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": denoise,
        },
    )
    g["7"] = _vae_decode_node(args, ["6", 0], vae_out)
    g["8"] = _node(
        "SaveImage",
        {"images": ["7", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def _apply_krea2_model_sampling(
    model_out: list[str | int],
    g: dict[str, Any],
    start_id: int,
    args: dict[str, Any],
) -> tuple[list[str | int], int]:
    """Krea 2 flow-matching timestep shift (mu pinned to 1.15 for Turbo)."""
    shift_value = args.get("krea2_shift")
    if shift_value is None:
        shift_value = args.get("shift")
    if shift_value is None:
        shift_value = 1.15
    g[str(start_id)] = _node(
        "ModelSamplingAuraFlow",
        {"model": model_out, "shift": float(shift_value)},
    )
    return [str(start_id), 0], start_id + 1


def comfy_krea2_txt2img(args: dict[str, Any]) -> dict[str, Any]:
    """Krea 2 OSS txt2img (UNETLoader + CLIPLoader krea2 + Qwen Image VAE)."""
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    width = int(args.get("width", 1024))
    height = int(args.get("height", 1024))
    steps = int(args.get("steps", 8))
    cfg = float(args.get("cfg", 1.0))
    sampler = str(args.get("sampler_name", "er_sde"))
    scheduler = str(args.get("scheduler", "simple"))
    seed = int(args.get("seed", 0))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    model_sampled, n = _apply_krea2_model_sampling(model_out, g, n, args)
    g["2"] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    g["3"] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    g["4"] = _node("EmptySD3LatentImage", {"width": width, "height": height, "batch_size": 1})
    g["5"] = _node(
        "KSampler",
        {
            "model": model_sampled,
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["4", 0],
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": 1.0,
        },
    )
    g["6"] = _vae_decode_node(args, ["5", 0], vae_out)
    g["7"] = _node(
        "SaveImage",
        {"images": ["6", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def comfy_krea2_img2img(args: dict[str, Any]) -> dict[str, Any]:
    """Krea 2 OSS img2img — VAEEncode reference + flow-matching sampling."""
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    image_filename = str(args["image"])
    steps = int(args.get("steps", 8))
    cfg = float(args.get("cfg", 1.0))
    sampler = str(args.get("sampler_name", "er_sde"))
    scheduler = str(args.get("scheduler", "simple"))
    seed = int(args.get("seed", 0))
    denoise = float(args.get("denoise", args.get("edit_strength", 0.6)))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    model_sampled, n = _apply_krea2_model_sampling(model_out, g, n, args)
    pixels = _img2img_source_pixels(g, args, image_filename, load_id="2", scale_id="20")
    g["3"] = _node("VAEEncode", {"pixels": pixels, "vae": vae_out})
    g["4"] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    g["5"] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    g["6"] = _node(
        "KSampler",
        {
            "model": model_sampled,
            "positive": ["4", 0],
            "negative": ["5", 0],
            "latent_image": ["3", 0],
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": denoise,
        },
    )
    g["7"] = _vae_decode_node(args, ["6", 0], vae_out)
    g["8"] = _node(
        "SaveImage",
        {"images": ["7", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def comfy_kandinsky5_txt2img(args: dict[str, Any]) -> dict[str, Any]:
    """Kandinsky 5 txt2img."""
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    width = int(args.get("width", 1024))
    height = int(args.get("height", 1024))
    steps = int(args.get("steps", 20))
    cfg = float(args.get("cfg", 3.5))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "simple"))
    seed = int(args.get("seed", 0))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    g["2"] = _node("CLIPTextEncodeKandinsky5", {"clip": clip_out, "text": prompt})
    g["3"] = _node("CLIPTextEncodeKandinsky5", {"clip": clip_out, "text": negative})
    g["4"] = _node("EmptyLatentImage", {"width": width, "height": height, "batch_size": 1})
    g["5"] = _node(
        "KSampler",
        {
            "model": model_out,
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["4", 0],
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": 1.0,
        },
    )
    g["6"] = _vae_decode_node(args, ["5", 0], vae_out)
    g["7"] = _node(
        "SaveImage",
        {"images": ["6", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def comfy_kandinsky5_img2img(args: dict[str, Any]) -> dict[str, Any]:
    """Kandinsky 5 img2img — VAEEncode + CLIPTextEncodeKandinsky5 + KSampler."""
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    image_filename = str(args["image"])
    steps = int(args.get("steps", 20))
    cfg = float(args.get("cfg", 3.5))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "simple"))
    seed = int(args.get("seed", 0))
    denoise = float(args.get("denoise", args.get("edit_strength", 0.75)))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    pixels = _img2img_source_pixels(g, args, image_filename, load_id="2", scale_id="20")
    g["3"] = _node("VAEEncode", {"pixels": pixels, "vae": vae_out})
    g["4"] = _node("CLIPTextEncodeKandinsky5", {"clip": clip_out, "text": prompt})
    g["5"] = _node("CLIPTextEncodeKandinsky5", {"clip": clip_out, "text": negative})
    g["6"] = _node(
        "KSampler",
        {
            "model": model_out,
            "positive": ["4", 0],
            "negative": ["5", 0],
            "latent_image": ["3", 0],
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": denoise,
        },
    )
    g["7"] = _vae_decode_node(args, ["6", 0], vae_out)
    g["8"] = _node(
        "SaveImage",
        {"images": ["7", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def _apply_user_lora_stack(
    g: dict[str, Any],
    model_out: list[str | int],
    clip_out: list[str | int] | None,
    loras: Any,
    start_id: int,
    *,
    clip_lora: bool,
) -> tuple[list[str | int], list[str | int] | None, int]:
    """Chain user-selected LoRAs after the base model loader (RuinedFooocus parity)."""
    from dreamforge_prompt.loras import resolve_lora_on_disk

    node_id = start_id
    for raw in loras or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        try:
            weight = float(raw.get("weight", 1.0))
        except (TypeError, ValueError):
            weight = 1.0
        lora_name = resolve_lora_on_disk(name)
        if not lora_name:
            continue
        if clip_lora and clip_out is not None:
            g[str(node_id)] = _node(
                "LoraLoader",
                {
                    "model": model_out,
                    "clip": clip_out,
                    "lora_name": lora_name,
                    "strength_model": weight,
                    "strength_clip": weight,
                },
            )
            model_out = [str(node_id), 0]
            clip_out = [str(node_id), 1]
        else:
            g[str(node_id)] = _node(
                "LoraLoaderModelOnly",
                {
                    "model": model_out,
                    "lora_name": lora_name,
                    "strength_model": weight,
                },
            )
            model_out = [str(node_id), 0]
        node_id += 1
    return model_out, clip_out, node_id


def _apply_easy_cache(g: dict[str, Any], model_out: list[str | int], args: dict[str, Any], i: int) -> tuple[list[str | int], int]:
    """Applies the native ComfyUI EasyCache node if requested."""
    # Some Nunchaku loaders natively handle caching internally
    if "nunchaku" in str(args.get("unet_name", "")).lower() or "svdq" in str(args.get("unet_name", "")).lower():
        return model_out, i
    
    if str(args.get("teacache", "false")).lower() == "true":
        family = str(args.get("family") or "").lower()
        threshold = 0.2 if family.startswith("sdxl") else 0.12
        g[str(i)] = _node(
            "EasyCache",
            {
                "model": model_out,
                "reuse_threshold": threshold,
                "start_percent": 0.15,
                "end_percent": 0.95,
                "verbose": False,
            }
        )
        model_out = [str(i), 0]
        i += 1
    return model_out, i


def _add_model_loader(g: dict[str, Any], args: dict[str, Any], *, start_id: int = 30):
    """Add either checkpoint or split-diffusion loaders.

    Krita AI Diffusion treats files under diffusion_models/unet as UNet-only
    weights and loads CLIP/VAE separately; only checkpoints use
    CheckpointLoaderSimple.
    """
    category = _model_category(args)
    family = str(args.get("family") or "").lower()
    model_name = _comfy_model_name(args)
    i = start_id
    clip_lora = category == "checkpoints"
    if category == "checkpoints" and family.startswith("qwen"):
        g[str(i)] = _node("CheckpointLoaderSimple", {"ckpt_name": model_name})
        model_out = [str(i), 0]
        i += 1
        clip_name = str(args.get("clip") or args.get("clip_qwen") or "qwen_2.5_vl_7b_fp8_scaled.safetensors")
        if clip_name.endswith(".gguf"):
            g[str(i)] = _node("CLIPLoaderGGUF", {"clip_name": clip_name, "type": "qwen_image"})
        else:
            g[str(i)] = _node("CLIPLoader", {"clip_name": clip_name, "type": "qwen_image"})
        clip_out = [str(i), 0]
        i += 1
        g[str(i)] = _node(
            "VAELoader",
            {"vae_name": str(args.get("vae") or "qwen_image_vae.safetensors")},
        )
        vae_out = [str(i), 0]
        i += 1
        model_out, clip_out, i = _apply_user_lora_stack(
            g, model_out, clip_out, args.get("loras"), i, clip_lora=False
        )
        model_out, i = _apply_easy_cache(g, model_out, args, i)
        return model_out, clip_out, vae_out, i
    if category in ("diffusion_models", "unet"):
        unet_name = str(args.get("unet_name") or model_name)
        if unet_name.endswith((".svdq", ".nunchaku")):
            if family.startswith("qwen"):
                g[str(i)] = _node("NunchakuQwenImageDiTLoader", {"model_name": unet_name, "cpu_offload": "auto", "num_blocks_on_gpu": 1, "use_pin_memory": "disable"})
            else:
                g[str(i)] = _node("NunchakuFluxDiTLoader", {"model_path": unet_name, "cache_threshold": 0.12 if str(args.get("teacache", "false")).lower() == "true" else 0.0})
        elif unet_name.endswith(".gguf"):
            g[str(i)] = _node("UnetLoaderGGUF", {"unet_name": unet_name})
        else:
            g[str(i)] = _node("UNETLoader", {"unet_name": unet_name, "weight_dtype": "default"})
        model_out = [str(i), 0]
        i += 1
        if family.startswith("flux"):
            g[str(i)] = _node(
                "DualCLIPLoader",
                {
                    "clip_name1": str(args.get("clip_l") or "clip_l.safetensors"),
                    "clip_name2": str(args.get("t5") or "t5xxl_fp8_e4m3fn_scaled.safetensors"),
                    "type": "flux",
                },
            )
            clip_out = [str(i), 0]
            i += 1
            g[str(i)] = _node("VAELoader", {"vae_name": str(args.get("vae") or "ae.safetensors")})
            vae_out = [str(i), 0]
            i += 1
            model_out, clip_out, i = _apply_user_lora_stack(
                g, model_out, clip_out, args.get("loras"), i, clip_lora=False
            )
            model_out, i = _apply_easy_cache(g, model_out, args, i)
            return model_out, clip_out, vae_out, i
        if family.startswith("qwen"):
            clip_name = str(args.get("clip") or args.get("clip_qwen") or "qwen_2.5_vl_7b_fp8_scaled.safetensors")
            if clip_name.endswith(".gguf"):
                g[str(i)] = _node("CLIPLoaderGGUF", {"clip_name": clip_name, "type": "qwen_image"})
            else:
                g[str(i)] = _node("CLIPLoader", {"clip_name": clip_name, "type": "qwen_image"})
            clip_out = [str(i), 0]
            i += 1
            g[str(i)] = _node(
                "VAELoader",
                {"vae_name": str(args.get("vae") or "qwen_image_vae.safetensors")},
            )
            vae_out = [str(i), 0]
            i += 1
            model_out, clip_out, i = _apply_user_lora_stack(
                g, model_out, clip_out, args.get("loras"), i, clip_lora=False
            )
            model_out, i = _apply_easy_cache(g, model_out, args, i)
            return model_out, clip_out, vae_out, i
        if family in ("hidream", "hidream_o1"):
            g[str(i)] = _node(
                "QuadrupleCLIPLoader",
                {
                    "clip_name1": str(args.get("clip_l") or "clip_l.safetensors"),
                    "clip_name2": str(args.get("clip_g") or "clip_g.safetensors"),
                    "clip_name3": str(args.get("t5") or "t5xxl_fp16.safetensors"),
                    "clip_name4": str(args.get("llama") or "llama_3.1_8b_instruct_fp8_scaled.safetensors"),
                },
            )
            clip_out = [str(i), 0]
            i += 1
            g[str(i)] = _node("VAELoader", {"vae_name": str(args.get("vae") or "ae.safetensors")})
            vae_out = [str(i), 0]
            i += 1
            model_out, clip_out, i = _apply_user_lora_stack(
                g, model_out, clip_out, args.get("loras"), i, clip_lora=False
            )
            model_out, i = _apply_easy_cache(g, model_out, args, i)
            return model_out, clip_out, vae_out, i
        if family == "krea2":
            clip_name = str(
                args.get("clip")
                or args.get("clip_qwen")
                or "qwen3vl_4b_fp8_scaled.safetensors"
            )
            if clip_name.endswith(".gguf"):
                g[str(i)] = _node("CLIPLoaderGGUF", {"clip_name": clip_name, "type": "krea2"})
            else:
                g[str(i)] = _node("CLIPLoader", {"clip_name": clip_name, "type": "krea2"})
            clip_out = [str(i), 0]
            i += 1
            g[str(i)] = _node(
                "VAELoader",
                {"vae_name": str(args.get("vae") or "qwen_image_vae.safetensors")},
            )
            vae_out = [str(i), 0]
            i += 1
            model_out, clip_out, i = _apply_user_lora_stack(
                g, model_out, clip_out, args.get("loras"), i, clip_lora=False
            )
            model_out, i = _apply_easy_cache(g, model_out, args, i)
            return model_out, clip_out, vae_out, i
        if family in ("z-image", "z_image"):
            clip_name = str(args.get("clip") or args.get("clip_qwen") or "qwen_3_4b_fp4_mixed.safetensors")
            clip_type = _z_image_clip_loader_type()
            if clip_name.endswith(".gguf"):
                g[str(i)] = _node("CLIPLoaderGGUF", {"clip_name": clip_name, "type": clip_type})
            else:
                g[str(i)] = _node("CLIPLoader", {"clip_name": clip_name, "type": clip_type})
            clip_out = [str(i), 0]
            i += 1
            g[str(i)] = _node(
                "VAELoader",
                {"vae_name": str(args.get("vae") or "ae.safetensors")},
            )
            vae_out = [str(i), 0]
            i += 1
            model_out, clip_out, i = _apply_user_lora_stack(
                g, model_out, clip_out, args.get("loras"), i, clip_lora=False
            )
            model_out, i = _apply_easy_cache(g, model_out, args, i)
            return model_out, clip_out, vae_out, i
        if family == "kandinsky5":
            g[str(i)] = _node(
                "DualCLIPLoader",
                {
                    "clip_name1": str(args.get("clip_l") or "clip_l.safetensors"),
                    "clip_name2": str(args.get("t5") or "t5xxl_fp8_e4m3fn_scaled.safetensors"),
                    "type": "kandinsky5",
                },
            )
            clip_out = [str(i), 0]
            i += 1
            g[str(i)] = _node("VAELoader", {"vae_name": str(args.get("vae") or "k5_image_vae.safetensors")})
            vae_out = [str(i), 0]
            i += 1
            model_out, clip_out, i = _apply_user_lora_stack(
                g, model_out, clip_out, args.get("loras"), i, clip_lora=False
            )
            model_out, i = _apply_easy_cache(g, model_out, args, i)
            return model_out, clip_out, vae_out, i
        raise ValueError(f"Comfy split-diffusion loader is not configured for family '{family}'")

    g[str(i)] = _node("CheckpointLoaderSimple", {"ckpt_name": model_name})
    model_out = [str(i), 0]
    clip_out = [str(i), 1]
    vae_out = [str(i), 2]
    i += 1
    model_out, clip_out, i = _apply_user_lora_stack(
        g, model_out, clip_out, args.get("loras"), i, clip_lora=True
    )
    model_out, i = _apply_easy_cache(g, model_out, args, i)
    return model_out, clip_out, vae_out, i


def _empty_latent_node(family: str, width: int, height: int) -> dict[str, Any]:
    """Pick the correct empty-latent node for the architecture.

    SD3 / HiDream use a 16-channel latent and require ``EmptySD3LatentImage``;
    a plain ``EmptyLatentImage`` (4 channels) crashes the sampler on those DiT
    backbones. SDXL/SD1.5 stay on the classic 4-channel latent.
    """
    fam = (family or "").lower()
    node_type = (
        "EmptySD3LatentImage"
        if fam in ("sd3", "hidream")
        else "EmptyLatentImage"
    )
    return _node(node_type, {"width": width, "height": height, "batch_size": 1})


def _hidream_o1_checkpoint_loader(
    g: dict[str, Any],
    args: dict[str, Any],
    *,
    start_id: int = 1,
) -> tuple[list[Any], list[Any], list[Any], int]:
    """HiDream-O1 all-in-one checkpoint (built-in CLIP + pixel VAE)."""
    ckpt = str(args["ckpt_name"])
    g[str(start_id)] = _node("CheckpointLoaderSimple", {"ckpt_name": ckpt})
    model_out: list[Any] = [str(start_id), 0]
    clip_out: list[Any] = [str(start_id), 1]
    vae_out: list[Any] = [str(start_id), 2]
    node_id = start_id + 1
    model_out, clip_out, node_id = _apply_user_lora_stack(
        g, model_out, clip_out, args.get("loras"), node_id, clip_lora=True
    )
    model_out, node_id = _apply_easy_cache(g, model_out, args, node_id)
    return model_out, clip_out, vae_out, node_id


def comfy_hidream_o1_dev_txt2img(args: dict[str, Any]) -> dict[str, Any]:
    """Native HiDream-O1 Dev txt2img (ModelNoiseScale + SamplerLCM + SamplerCustom)."""
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    width = int(args.get("width", 2048))
    height = int(args.get("height", 2048))
    steps = int(args.get("steps", 28))
    cfg = float(args.get("cfg", 1.0))
    scheduler = str(args.get("scheduler", "normal"))
    seed = int(args.get("seed", 0))
    noise_scale = float(args.get("hidream_noise_scale", 7.6))
    s_noise = float(args.get("hidream_s_noise", 1.0))
    s_noise_end = float(args.get("hidream_s_noise_end", 1.0))
    noise_clip_std = float(args.get("hidream_noise_clip_std", 2.5))
    patch_seam = bool(args.get("hidream_patch_seam_smoothing", False))
    denoise = float(args.get("denoise", 1.0))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _hidream_o1_checkpoint_loader(g, args)

    g[str(n)] = _node("ModelNoiseScale", {"model": model_out, "noise_scale": noise_scale})
    model_sampled: list[Any] = [str(n), 0]
    n += 1

    if patch_seam:
        g[str(n)] = _node(
            "HiDreamO1PatchSeamSmoothing",
            {
                "model": model_sampled,
                "start_percent": 0.8,
                "end_percent": 1.0,
                "pattern": "single_shift",
                "passes": "2",
                "blend": "average",
                "strength": 1.0,
            },
        )
        model_sampled = [str(n), 0]
        n += 1

    g[str(n)] = _node(
        "CLIPTextEncode",
        {
            "clip": clip_out,
            "text": prompt,
        },
    )
    positive = [str(n), 0]
    n += 1
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    negative_out = [str(n), 0]
    n += 1

    g[str(n)] = _node(
        "EmptyHiDreamO1LatentImage",
        {"width": width, "height": height, "batch_size": 1},
    )
    latent = [str(n), 0]
    n += 1

    g[str(n)] = _node(
        "SamplerLCM",
        {
            "s_noise": s_noise,
            "s_noise_end": s_noise_end,
            "noise_clip_std": noise_clip_std,
        },
    )
    sampler = [str(n), 0]
    n += 1

    g[str(n)] = _node(
        "BasicScheduler",
        {
            "model": model_sampled,
            "scheduler": scheduler,
            "steps": steps,
            "denoise": denoise,
        },
    )
    sigmas = [str(n), 0]
    n += 1

    g[str(n)] = _node(
        "SamplerCustom",
        {
            "model": model_sampled,
            "positive": positive,
            "negative": negative_out,
            "sampler": sampler,
            "sigmas": sigmas,
            "latent_image": latent,
            "noise_seed": seed,
            "cfg": cfg,
            "add_noise": True,
        },
    )
    samples = [str(n), 0]
    n += 1

    g[str(n)] = _vae_decode_node(args, samples, vae_out)
    decode = [str(n), 0]
    n += 1
    g[str(n)] = _node(
        "SaveImage",
        {
            "images": decode,
            "filename_prefix": str(args.get("filename_prefix", "DreamForge")),
        },
    )
    return g


def comfy_txt2img_basic(args: dict[str, Any]) -> dict[str, Any]:
    """Generic KSampler txt2img (SDXL-style checkpoints)."""
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    width = int(args.get("width", 1024))
    height = int(args.get("height", 1024))
    steps = int(args.get("steps", 30))
    cfg = float(args.get("cfg", 7.0))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "normal"))
    seed = int(args.get("seed", 0))

    # Node IDs are strings in Comfy API format.
    prompt_graph: dict[str, Any] = {}
    model_out, clip_out, vae_out, _next = _add_model_loader(prompt_graph, {**args, "ckpt_name": ckpt})
    prompt_graph["2"] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    prompt_graph["3"] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    prompt_graph["4"] = _empty_latent_node(str(args.get("family") or ""), width, height)
    prompt_graph["5"] = _node(
        "KSampler",
        {
            "model": model_out,
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["4", 0],
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": 1.0,
        },
    )
    prompt_graph["6"] = _vae_decode_node(args, ["5", 0], vae_out)
    prompt_graph["7"] = _node("SaveImage", {"images": ["6", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))})
    return prompt_graph


def comfy_flux_dev_txt2img(args: dict[str, Any]) -> dict[str, Any]:
    """Flux dev txt2img based on your `flux_dev.json` template.

The template uses:
- CheckpointLoaderSimple with flux1-dev-fp8.safetensors
- CLIPTextEncode (pos/neg) + FluxGuidance + KSampler cfg=1
- EmptySD3LatentImage + VAEDecode + SaveImage

We reproduce that in API prompt format.
"""
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    width = int(args.get("width", 1024))
    height = int(args.get("height", 1024))
    steps = int(args.get("steps", 20))
    guidance = float(args.get("guidance", args.get("cfg", 3.5)))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "simple"))
    seed = int(args.get("seed", 0))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, _next = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    g["4"] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    g["3"] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    g["2"] = _node("FluxGuidance", {"conditioning": ["4", 0], "guidance": guidance})
    g["5"] = _node("EmptySD3LatentImage", {"width": width, "height": height, "batch_size": 1})
    # Flux dev: cfg should be 1.0 (negative ignored); we keep cfg=1 and drive guidance via FluxGuidance node.
    g["6"] = _node(
        "KSampler",
        {
            "model": model_out,
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["5", 0],
            "seed": seed,
            "steps": steps,
            "cfg": 1.0,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": 1.0,
        },
    )
    g["7"] = _vae_decode_node(args, ["6", 0], vae_out)
    g["8"] = _node("SaveImage", {"images": ["7", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))})
    return g


def comfy_img2img_basic(args: dict[str, Any]) -> dict[str, Any]:
    """Generic img2img (VAE encode input image -> KSampler denoise).

Requires the input image to already exist in Comfy's input directory, and the
workflow to reference it by filename.
"""
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    image_filename = str(args["image"])  # filename in Comfy input dir
    steps = int(args.get("steps", 30))
    cfg = float(args.get("cfg", 7.0))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "normal"))
    seed = int(args.get("seed", 0))
    denoise = float(args.get("denoise", args.get("edit_strength", 0.6)))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, _next = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    pixels = _img2img_source_pixels(g, args, image_filename, load_id="2", scale_id="20")
    g["3"] = _node("VAEEncode", {"pixels": pixels, "vae": vae_out})
    g["4"] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    g["5"] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    g["6"] = _node(
        "KSampler",
        {
            "model": model_out,
            "positive": ["4", 0],
            "negative": ["5", 0],
            "latent_image": ["3", 0],
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": denoise,
        },
    )
    g["7"] = _vae_decode_node(args, ["6", 0], vae_out)
    g["8"] = _node("SaveImage", {"images": ["7", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))})
    return g


def comfy_flux_img2img(args: dict[str, Any]) -> dict[str, Any]:
    """Flux img2img — VAEEncode reference + FluxGuidance + cfg=1 KSampler.

    Flux is guidance-distilled: the prompt strength lives in the ``FluxGuidance``
    node (default 3.5) and the KSampler ``cfg`` must stay at 1.0, otherwise the
    output washes out. ``denoise`` (edit_strength) controls how much of the
    source image is preserved (0.3-0.5 subtle, 0.6-0.8 moderate). The generic
    img2img builder omits FluxGuidance, so Flux/Flux2/Chroma need this path.
    """
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    image_filename = str(args["image"])
    steps = int(args.get("steps", 20))
    guidance = float(args.get("guidance", args.get("cfg", 3.5)))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "simple"))
    seed = int(args.get("seed", 0))
    denoise = float(args.get("denoise", args.get("edit_strength", 0.75)))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, _next = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    pixels = _img2img_source_pixels(g, args, image_filename, load_id="2", scale_id="20")
    g["3"] = _node("VAEEncode", {"pixels": pixels, "vae": vae_out})
    g["4"] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    g["5"] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    g["6"] = _node("FluxGuidance", {"conditioning": ["4", 0], "guidance": guidance})
    g["7"] = _node(
        "KSampler",
        {
            "model": model_out,
            "positive": ["6", 0],
            "negative": ["5", 0],
            "latent_image": ["3", 0],
            "seed": seed,
            "steps": steps,
            "cfg": 1.0,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": denoise,
        },
    )
    g["8"] = _vae_decode_node(args, ["7", 0], vae_out)
    g["9"] = _node(
        "SaveImage",
        {"images": ["8", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def comfy_flux_kontext_edit(args: dict[str, Any]) -> dict[str, Any]:
    """Flux Kontext-style edit graph (ReferenceLatent + FluxKontextImageScale).

    This mirrors Krita/Comfy conventions for Kontext:
    - resize source with FluxKontextImageScale
    - VAE encode reference (optionally from a stitched multi-reference image)
    - inject reference latent into positive + negative conditioning
    - sample from reference latent with denoise strength
    """
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    image_filename = str(args["image"])
    reference_filename = str(args.get("reference_stitch") or image_filename)
    steps = int(args.get("steps", 20))
    guidance = float(args.get("guidance", args.get("cfg", 3.5)))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "simple"))
    seed = int(args.get("seed", 0))
    denoise = float(args.get("denoise", args.get("edit_strength", 1.0)))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, _next = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    g["2"] = _node("LoadImage", {"image": image_filename, "upload": "image"})
    g["3"] = _node("FluxKontextImageScale", {"image": ["2", 0]})
    g["4"] = _node("VAEEncode", {"pixels": ["3", 0], "vae": vae_out})
    if reference_filename != image_filename:
        g["13"] = _node("LoadImage", {"image": reference_filename, "upload": "image"})
        g["14"] = _node("FluxKontextImageScale", {"image": ["13", 0]})
        ref_latent_src = ["14", 0]
    else:
        ref_latent_src = ["3", 0]
    g["15"] = _node("VAEEncode", {"pixels": ref_latent_src, "vae": vae_out})
    g["5"] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    g["6"] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    g["7"] = _node("FluxGuidance", {"conditioning": ["5", 0], "guidance": guidance})
    g["8"] = _node("ReferenceLatent", {"conditioning": ["7", 0], "latent": ["15", 0]})
    g["9"] = _node("ReferenceLatent", {"conditioning": ["6", 0], "latent": ["15", 0]})
    g["10"] = _node(
        "KSampler",
        {
            "model": model_out,
            "positive": ["8", 0],
            "negative": ["9", 0],
            "latent_image": ["4", 0],
            "seed": seed,
            "steps": steps,
            "cfg": 1.0,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": denoise,
        },
    )
    g["11"] = _vae_decode_node(args, ["10", 0], vae_out)
    g["12"] = _node(
        "SaveImage",
        {"images": ["11", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def _apply_qwen_model_sampling(model_out: list[str | int], g: dict[str, Any], start_id: int, args: dict[str, Any]):
    """AuraFlow + CFGNorm prep used by native Comfy Qwen workflows."""
    shift_value = args.get("shift")
    if shift_value is None:
        shift_value = args.get("qwen_image_shift")
    if shift_value is None:
        shift_value = 3.1
    strength_value = args.get("cfg_norm_strength")
    if strength_value is None:
        strength_value = args.get("qwen_cfg_norm_strength")
    if strength_value is None:
        strength_value = 1.0
    shift = float(shift_value)
    strength = float(strength_value)
    g[str(start_id)] = _node("ModelSamplingAuraFlow", {"model": model_out, "shift": shift})
    g[str(start_id + 1)] = _node("CFGNorm", {"model": [str(start_id), 0], "strength": strength})
    return [str(start_id + 1), 0]


def _resolve_qwen_lightning_lora_name(args: dict[str, Any]) -> str | None:
    """Match Krita/Comfy Qwen-Edit Lightning LoRAs when present under models/loras/."""
    explicit = args.get("qwen_lightning_lora")
    if explicit:
        return str(explicit)
    if not args.get("use_qwen_lightning_lora"):
        return None
    try:
        steps = int(args.get("steps") or 4)
    except (TypeError, ValueError):
        steps = 4
    four_step = (
        "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
        "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-fp32.safetensors",
        "Qwen-Image-Edit-2509-Lightning-4steps-V1.0-fp32.safetensors",
        "Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors",
        "Qwen-Image-Edit-Lightning-4steps-V1.0.safetensors",
    )
    eight_step = (
        "Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors",
        "Qwen-Image-Edit-2511-Lightning-8steps-V1.0-fp32.safetensors",
        "Qwen-Image-Edit-2509-Lightning-8steps-V1.0-fp32.safetensors",
        "Qwen-Image-Edit-Lightning-8steps-V1.0-bf16.safetensors",
        "Qwen-Image-Edit-Lightning-8steps-V1.0.safetensors",
        "Qwen-Image-Lightning-8steps-V2.0-bf16.safetensors",
    )
    preferred = (*eight_step, *four_step) if steps >= 8 else (*four_step, *eight_step)
    try:
        from dreamforge_paths import MODELS_ROOT

        lora_dir = MODELS_ROOT / "loras"
        if not lora_dir.is_dir():
            return None
        on_disk = {
            path.name.lower(): path.name
            for path in lora_dir.iterdir()
            if path.suffix.lower() in (".safetensors", ".gguf")
        }
        for name in preferred:
            hit = on_disk.get(name.lower())
            if hit:
                return hit
        for name in on_disk.values():
            low = name.lower()
            if "qwen" in low and "edit" in low and "lightning" in low:
                return name
    except Exception:
        return None
    return None


def _apply_qwen_lightning_lora(
    model_out: list[str | int],
    g: dict[str, Any],
    start_id: int,
    args: dict[str, Any],
) -> tuple[list[str | int], int]:
    lora_name = _resolve_qwen_lightning_lora_name(args)
    if not lora_name:
        return model_out, start_id
    g[str(start_id)] = _node(
        "LoraLoaderModelOnly",
        {
            "model": model_out,
            "lora_name": lora_name,
            "strength_model": float(args.get("qwen_lightning_strength", 1.0)),
        },
    )
    return [str(start_id), 0], start_id + 1


def _maybe_scale_qwen_pixels(
    g: dict[str, Any],
    image_out: list[str | int],
    start_id: int,
    args: dict[str, Any],
) -> tuple[list[str | int], int]:
    raw = args.get("qwen_scale_megapixels", 1.0)
    if raw is None:
        raw = 1.0
    try:
        megapixels = float(raw)
    except (TypeError, ValueError):
        megapixels = 1.0
    if megapixels <= 0:
        megapixels = 1.0
    g[str(start_id)] = _node(
        "ImageScaleToTotalPixels",
        {
            "image": image_out,
            "upscale_method": str(args.get("qwen_scale_method", "bicubic")),
            "megapixels": megapixels,
            "resolution_steps": int(args.get("qwen_resolution_steps", 64)),
        },
    )
    return [str(start_id), 0], start_id + 1


def _img2img_target_megapixels(args: dict[str, Any]) -> float:
    """Megapixel budget for an img2img source resize.

    Derived from the requested output resolution when available so the source is
    sampled near the user's target size; otherwise defaults to ~1 MP. Clamped to
    a sane range so a stray huge resolution can't OOM the sampler.
    """
    try:
        width = int(args.get("width") or 0)
        height = int(args.get("height") or 0)
    except (TypeError, ValueError):
        width = height = 0
    if width > 0 and height > 0:
        mp = (width * height) / 1_000_000.0
    else:
        mp = 1.0
    return max(0.25, min(mp, 4.0))


def _img2img_source_pixels(
    g: dict[str, Any],
    args: dict[str, Any],
    image_filename: str,
    *,
    load_id: str,
    scale_id: str,
) -> list[str | int]:
    """LoadImage + aspect-preserving resize snapped to a multiple of 64.

    DiT families patchify the latent (Flux/Z-Image/Lumina stride 16, HiDream-O1
    stride 32) and crash on dimensions that aren't divisible by their patch size
    when a raw photo is fed at native resolution (e.g. 2586x2062). Scaling the
    source to the requested megapixel budget with ``resolution_steps=64`` keeps
    the aspect ratio (so faces aren't cropped) while guaranteeing the encoded
    latent is always divisible, which leading local-gen apps do for img2img.
    """
    g[load_id] = _node("LoadImage", {"image": image_filename, "upload": "image"})
    g[scale_id] = _node(
        "ImageScaleToTotalPixels",
        {
            "image": [load_id, 0],
            "upscale_method": "lanczos",
            "megapixels": _img2img_target_megapixels(args),
            "resolution_steps": 64,
        },
    )
    return [scale_id, 0]


def _qwen_edit_sampler_nodes(
    g: dict[str, Any],
    *,
    start_id: int,
    model_sampled: list[str | int],
    pos: list[str | int],
    neg: list[str | int],
    latent: list[str | int],
    args: dict[str, Any],
) -> int:
    steps = int(args.get("steps", 20))
    cfg = float(args.get("cfg", 2.5))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "beta"))
    seed = int(args.get("seed", 0))
    denoise = float(args.get("denoise", args.get("edit_strength", 1.0)))
    g[str(start_id)] = _node(
        "KSampler",
        {
            "model": model_sampled,
            "positive": pos,
            "negative": neg,
            "latent_image": latent,
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": denoise,
        },
    )
    samp = str(start_id)
    decode = str(start_id + 1)
    save = str(start_id + 2)
    g[decode] = _vae_decode_node(args, [samp, 0], args["_vae_out"])
    g[save] = _node(
        "SaveImage",
        {"images": [decode, 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return start_id + 3


def comfy_qwen_image_edit(args: dict[str, Any]) -> dict[str, Any]:
    """Qwen-Image-Edit via TextEncodeQwenImageEdit (Comfy native / Krita qwen_e)."""
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    image_filename = str(args["image"])
    steps = int(args.get("steps", 20))
    cfg = float(args.get("cfg", 2.5))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "beta"))
    seed = int(args.get("seed", 0))
    denoise = float(args.get("denoise", args.get("edit_strength", 1.0)))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    model_out, n = _apply_qwen_lightning_lora(model_out, g, n, args)
    model_sampled = _apply_qwen_model_sampling(model_out, g, n, args)
    n += 2
    g["1"] = _node("LoadImage", {"image": image_filename, "upload": "image"})
    image_out, n = _maybe_scale_qwen_pixels(g, ["1", 0], n, args)
    g[str(n)] = _node(
        "TextEncodeQwenImageEdit",
        {"clip": clip_out, "image": image_out, "prompt": prompt},
    )
    pos = [str(n), 0]
    n += 1
    g[str(n)] = _node(
        "TextEncodeQwenImageEdit",
        {"clip": clip_out, "image": image_out, "prompt": negative},
    )
    neg = [str(n), 0]
    n += 1
    g[str(n)] = _node("VAEEncode", {"pixels": image_out, "vae": vae_out})
    latent = [str(n), 0]
    n += 1
    args_with_vae = {**args, "_vae_out": vae_out}
    _qwen_edit_sampler_nodes(
        g,
        start_id=n,
        model_sampled=model_sampled,
        pos=pos,
        neg=neg,
        latent=latent,
        args={
            **args_with_vae,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "seed": seed,
            "denoise": denoise,
        },
    )
    return g


def comfy_qwen_image_edit_plus(args: dict[str, Any]) -> dict[str, Any]:
    """Qwen-Image-Edit Plus via TextEncodeQwenImageEditPlus (up to 3 images)."""
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    image_list = [str(x) for x in (args.get("images") or []) if x]
    if not image_list and args.get("image"):
        image_list = [str(args["image"])]
    if not image_list:
        raise ValueError("comfy_qwen_image_edit_plus requires at least one image")

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    model_out, n = _apply_qwen_lightning_lora(model_out, g, n, args)
    model_sampled = _apply_qwen_model_sampling(model_out, g, n, args)
    n += 2

    image_links: dict[str, list[str | int]] = {}
    for index, filename in enumerate(image_list[:3], start=1):
        node_id = str(n)
        g[node_id] = _node("LoadImage", {"image": filename, "upload": "image"})
        image_links[f"image{index}"] = [node_id, 0]
        n += 1

    main_key = "image1"
    if main_key in image_links:
        scaled, n = _maybe_scale_qwen_pixels(g, image_links[main_key], n, args)
        image_links[main_key] = scaled

    def _encode_plus(text: str) -> list[str | int]:
        nonlocal n
        inputs: dict[str, Any] = {
            "clip": clip_out,
            "prompt": text,
        }
        for key in ("image1", "image2", "image3"):
            if key in image_links:
                inputs[key] = image_links[key]
        g[str(n)] = _node("TextEncodeQwenImageEditPlus", inputs)
        out = [str(n), 0]
        n += 1
        return out

    pos = _encode_plus(prompt)
    neg = _encode_plus(negative)
    g[str(n)] = _node("VAEEncode", {"pixels": image_links["image1"], "vae": vae_out})
    latent = [str(n), 0]
    n += 1
    _qwen_edit_sampler_nodes(
        g,
        start_id=n,
        model_sampled=model_sampled,
        pos=pos,
        neg=neg,
        latent=latent,
        args={**args, "_vae_out": vae_out, "ckpt_name": ckpt},
    )
    return g


def comfy_qwen_image_txt2img(args: dict[str, Any]) -> dict[str, Any]:
    """Qwen-Image txt2img (EmptySD3LatentImage + standard CLIP encode)."""
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    width = int(args.get("width", 1024))
    height = int(args.get("height", 1024))
    steps = int(args.get("steps", 20))
    cfg = float(args.get("cfg", 2.5))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "beta"))
    seed = int(args.get("seed", 0))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    model_out, n = _apply_qwen_lightning_lora(model_out, g, n, args)
    model_sampled = _apply_qwen_model_sampling(model_out, g, n, args)
    n += 2
    g["2"] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    g["3"] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    g["4"] = _node("EmptySD3LatentImage", {"width": width, "height": height, "batch_size": 1})
    g["5"] = _node(
        "KSampler",
        {
            "model": model_sampled,
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["4", 0],
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": 1.0,
        },
    )
    g["6"] = _vae_decode_node(args, ["5", 0], vae_out)
    g["7"] = _node(
        "SaveImage",
        {"images": ["6", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def _ideogram4_graph_params(args: dict[str, Any]) -> dict[str, Any]:
    """Shared Ideogram 4 loader / scheduler fields for txt2img, img2img, and inpaint."""
    cond_unet = str(
        args.get("unet_name")
        or args.get("relative_path")
        or args.get("ckpt_name")
        or "ideogram4_fp8_scaled.safetensors"
    )
    return {
        "cond_unet": cond_unet,
        "uncond_unet": str(
            args.get("unet_unconditional") or "ideogram4_unconditional_fp8_scaled.safetensors"
        ),
        "clip_name": str(args.get("clip") or "qwen3vl_8b_fp8_scaled.safetensors"),
        "vae_name": str(args.get("vae") or "flux2-vae.safetensors"),
        "prompt": str(args.get("prompt", "")),
        "width": int(args.get("width", 1024)),
        "height": int(args.get("height", 1024)),
        "steps": int(args.get("steps", 20)),
        "mu": float(args.get("ideogram4_mu", 0.0)),
        "std": float(args.get("ideogram4_std", 1.75)),
        "dual_cfg": float(args.get("dual_cfg", args.get("cfg", 7.0))),
        "cfg_override": float(args.get("cfg_override", 3.0)),
        "cfg_override_start": float(args.get("cfg_override_start", 0.7)),
        "cfg_override_end": float(args.get("cfg_override_end", 1.0)),
        "seed": int(args.get("seed", 0)),
        "denoise": float(args.get("denoise", args.get("edit_strength", 1.0))),
        "grow_mask_by": int(args.get("grow_mask_by", args.get("inpaint_mask_grow_by", 0))),
        "filename_prefix": str(args.get("filename_prefix", "DreamForge")),
    }


def _ideogram4_build_dual_unet_guider(g: dict[str, Any], p: dict[str, Any]) -> tuple[list[Any], list[Any]]:
    """Dual-UNet + CLIP + DualModelGuider stack (nodes 1–7). Returns (guider, cond_model)."""
    g["1"] = _node("UNETLoader", {"unet_name": p["cond_unet"], "weight_dtype": "default"})
    g["2"] = _node(
        "CFGOverride",
        {
            "model": ["1", 0],
            "cfg": p["cfg_override"],
            "start_percent": p["cfg_override_start"],
            "end_percent": p["cfg_override_end"],
        },
    )
    g["3"] = _node("UNETLoader", {"unet_name": p["uncond_unet"], "weight_dtype": "default"})
    g["4"] = _node(
        "CLIPLoader",
        {"clip_name": p["clip_name"], "type": "ideogram4", "device": "default"},
    )
    g["5"] = _node("CLIPTextEncode", {"clip": ["4", 0], "text": p["prompt"]})
    g["6"] = _node("ConditioningZeroOut", {"conditioning": ["5", 0]})
    g["7"] = _node(
        "DualModelGuider",
        {
            "model": ["2", 0],
            "model_negative": ["3", 0],
            "positive": ["5", 0],
            "negative": ["6", 0],
            "cfg": p["dual_cfg"],
        },
    )
    return ["7", 0], ["2", 0]


def _ideogram4_build_sampler_decode_save(
    g: dict[str, Any],
    *,
    p: dict[str, Any],
    guider: list[Any],
    cond_model: list[Any],
    latent_link: list[Any],
    vae_link: list[Any],
    start_id: int,
) -> None:
    """Ideogram4Scheduler → AddNoise → SamplerCustomAdvanced → VAEDecode → SaveImage."""
    sched_id = str(start_id)
    split_id = str(start_id + 1)
    noise_id = str(start_id + 2)
    sampler_sel_id = str(start_id + 3)
    add_noise_id = str(start_id + 4)
    sample_id = str(start_id + 5)
    decode_id = str(start_id + 6)
    save_id = str(start_id + 7)
    extend_id = str(start_id + 8)
    denoise = max(0.0, min(1.0, float(p.get("denoise", 1.0))))

    g[sched_id] = _node(
        "Ideogram4Scheduler",
        {
            "steps": p["steps"],
            "width": p["width"],
            "height": p["height"],
            "mu": p["mu"],
            "std": p["std"],
        },
    )
    # Bypasses the Ideogram 4 safety filter by removing the sudden sigma drop
    g[extend_id] = _node(
        "ExtendIntermediateSigmas",
        {
            "sigmas": [sched_id, 0],
            "steps": 2,
            "start_at_sigma": -1.0,
            "end_at_sigma": 12.0,
            "spacing": "linear",
        },
    )
    g[split_id] = _node(
        "SplitSigmasDenoise",
        {"sigmas": [extend_id, 0], "denoise": denoise},
    )
    g[noise_id] = _node("RandomNoise", {"noise_seed": p["seed"]})
    g[sampler_sel_id] = _node("KSamplerSelect", {"sampler_name": "euler"})
    g[add_noise_id] = _node(
        "AddNoise",
        {
            "model": cond_model,
            "noise": [noise_id, 0],
            "sigmas": [split_id, 0],
            "latent_image": latent_link,
        },
    )
    g[sample_id] = _node(
        "SamplerCustomAdvanced",
        {
            "noise": [noise_id, 0],
            "guider": guider,
            "sampler": [sampler_sel_id, 0],
            "sigmas": [split_id, 1],
            "latent_image": [add_noise_id, 0],
        },
    )
    g[decode_id] = _vae_decode_node(p, [sample_id, 0], vae_link)
    g[save_id] = _node(
        "SaveImage",
        {"images": [decode_id, 0], "filename_prefix": p["filename_prefix"]},
    )


def comfy_ideogram4_txt2img(args: dict[str, Any]) -> dict[str, Any]:
    """Ideogram 4 dual-UNet txt2img (matches Comfy Ideogram v4 subgraph)."""
    p = _ideogram4_graph_params(args)
    g: dict[str, Any] = {}
    guider, _cond_model = _ideogram4_build_dual_unet_guider(g, p)
    g["8"] = _node(
        "EmptyFlux2LatentImage",
        {"width": p["width"], "height": p["height"], "batch_size": 1},
    )
    g["9"] = _node(
        "Ideogram4Scheduler",
        {
            "steps": p["steps"],
            "width": p["width"],
            "height": p["height"],
            "mu": p["mu"],
            "std": p["std"],
        },
    )
    g["16"] = _node(
        "ExtendIntermediateSigmas",
        {
            "sigmas": ["9", 0],
            "steps": 2,
            "start_at_sigma": -1.0,
            "end_at_sigma": 12.0,
            "spacing": "linear",
        },
    )
    g["10"] = _node("RandomNoise", {"noise_seed": p["seed"]})
    g["11"] = _node("KSamplerSelect", {"sampler_name": "euler"})
    g["12"] = _node(
        "SamplerCustomAdvanced",
        {
            "noise": ["10", 0],
            "guider": guider,
            "sampler": ["11", 0],
            "sigmas": ["16", 0],
            "latent_image": ["8", 0],
        },
    )
    g["13"] = _node("VAELoader", {"vae_name": p["vae_name"]})
    g["14"] = _vae_decode_node(args, ["12", 0], ["13", 0])
    g["15"] = _node(
        "SaveImage",
        {"images": ["14", 0], "filename_prefix": p["filename_prefix"]},
    )
    return g


def comfy_ideogram4_img2img(args: dict[str, Any]) -> dict[str, Any]:
    """Ideogram 4 img2img: VAEEncode source image → SplitSigmasDenoise → dual-UNet sampler."""
    image = str(args.get("image") or "")
    if not image:
        raise ValueError("comfy_ideogram4_img2img requires args['image']")

    p = _ideogram4_graph_params(args)
    g: dict[str, Any] = {}
    guider, cond_model = _ideogram4_build_dual_unet_guider(g, p)
    g["8"] = _node("VAELoader", {"vae_name": p["vae_name"]})
    g["9"] = _node("LoadImage", {"image": image, "upload": "image"})
    g["10"] = _node("VAEEncode", {"pixels": ["9", 0], "vae": ["8", 0]})
    _ideogram4_build_sampler_decode_save(
        g,
        p=p,
        guider=guider,
        cond_model=cond_model,
        latent_link=["10", 0],
        vae_link=["8", 0],
        start_id=11,
    )
    return g


def comfy_ideogram4_inpaint(args: dict[str, Any]) -> dict[str, Any]:
    """Ideogram 4 inpaint: VAEEncodeForInpaint → SplitSigmasDenoise → dual-UNet sampler."""
    image = str(args.get("image") or "")
    mask = str(args.get("mask") or "")
    if not image:
        raise ValueError("comfy_ideogram4_inpaint requires args['image']")
    if not mask:
        raise ValueError("comfy_ideogram4_inpaint requires args['mask']")

    p = _ideogram4_graph_params(args)
    g: dict[str, Any] = {}
    guider, cond_model = _ideogram4_build_dual_unet_guider(g, p)
    g["8"] = _node("VAELoader", {"vae_name": p["vae_name"]})
    g["9"] = _node("LoadImage", {"image": image, "upload": "image"})
    g["10"] = _node("LoadImage", {"image": mask, "upload": "image"})
    g["11"] = _node("ImageToMask", {"image": ["10", 0], "channel": "red"})
    g["12"] = _node(
        "VAEEncodeForInpaint",
        {
            "pixels": ["9", 0],
            "mask": ["11", 0],
            "vae": ["8", 0],
            "grow_mask_by": p["grow_mask_by"],
        },
    )
    _ideogram4_build_sampler_decode_save(
        g,
        p=p,
        guider=guider,
        cond_model=cond_model,
        latent_link=["12", 0],
        vae_link=["8", 0],
        start_id=13,
    )
    return g


def comfy_flux_fill_inpaint(args: dict[str, Any]) -> dict[str, Any]:
    """Flux.1 Fill inpaint via InpaintModelConditioning + DifferentialDiffusion.

    Matches ComfyUI's official Flux Fill blueprint: guidance lives in FluxGuidance;
    KSampler runs at cfg=1.
    """
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", "")).strip()
    image_filename = str(args["image"])
    mask_filename = str(args["mask"])
    steps = int(args.get("steps", 20))
    guidance = float(args.get("guidance", args.get("cfg", 30.0)))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "normal"))
    seed = int(args.get("seed", 0))
    denoise = float(args.get("denoise", args.get("edit_strength", 1.0)))
    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, _next = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    g["2"] = _node("LoadImage", {"image": image_filename, "upload": "image"})
    g["3"] = _node("LoadImage", {"image": mask_filename, "upload": "image"})
    g["4"] = _node("ImageToMask", {"image": ["3", 0], "channel": "red"})
    # Mask grow/feather is applied in prepare_inpaint_mask_bytes before upload.
    mask_link: list[str | int] = ["4", 0]
    g["6"] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    if negative:
        g["7"] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
        negative_out: list[str | int] = ["7", 0]
    else:
        g["7"] = _node("ConditioningZeroOut", {"conditioning": ["6", 0]})
        negative_out = ["7", 0]
    g["8"] = _node("FluxGuidance", {"conditioning": ["6", 0], "guidance": guidance})
    g["9"] = _node(
        "InpaintModelConditioning",
        {
            "positive": ["8", 0],
            "negative": negative_out,
            "vae": vae_out,
            "pixels": ["2", 0],
            "mask": mask_link,
            "noise_mask": True,
        },
    )
    g["10"] = _node("DifferentialDiffusion", {"model": model_out})
    g["11"] = _node(
        "KSampler",
        {
            "model": ["10", 0],
            "positive": ["9", 0],
            "negative": ["9", 1],
            "latent_image": ["9", 2],
            "seed": seed,
            "steps": steps,
            "cfg": 1.0,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": denoise,
        },
    )
    g["12"] = _vae_decode_node(args, ["11", 0], vae_out)
    g["13"] = _node(
        "SaveImage",
        {"images": ["12", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def comfy_inpaint_basic(args: dict[str, Any]) -> dict[str, Any]:
    """Standard VAEEncodeForInpaint + KSampler workflow."""
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    image_filename = str(args["image"])
    mask_filename = str(args["mask"])
    steps = int(args.get("steps", 30))
    cfg = float(args.get("cfg", 7.0))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "normal"))
    seed = int(args.get("seed", 0))
    denoise = float(args.get("denoise", args.get("edit_strength", 1.0)))
    grow_mask_by = int(args.get("grow_mask_by", args.get("inpaint_mask_grow_by", 0)))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, _next = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    g["2"] = _node("LoadImage", {"image": image_filename, "upload": "image"})
    g["3"] = _node("LoadImage", {"image": mask_filename, "upload": "image"})
    g["4"] = _node("ImageToMask", {"image": ["3", 0], "channel": "red"})
    g["5"] = _node(
        "VAEEncodeForInpaint",
        {
            "pixels": ["2", 0],
            "mask": ["4", 0],
            "vae": vae_out,
            "grow_mask_by": grow_mask_by,
        },
    )
    g["6"] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    g["7"] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})

    g["8"] = _node(
        "KSampler",
        {
            "model": model_out,
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": denoise,
        },
    )
    g["9"] = _vae_decode_node(args, ["8", 0], vae_out)
    g["10"] = _node(
        "SaveImage",
        {"images": ["9", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def comfy_upscale_basic(args: dict[str, Any]) -> dict[str, Any]:
    """Simple model-based upscale path."""
    image_filename = str(args["image"])
    upscale_model = str(args["upscale_model"])
    g: dict[str, Any] = {}
    g["1"] = _node("LoadImage", {"image": image_filename, "upload": "image"})
    g["2"] = _node("UpscaleModelLoader", {"model_name": upscale_model})
    g["3"] = _node("ImageUpscaleWithModel", {"image": ["1", 0], "upscale_model": ["2", 0]})
    g["4"] = _node(
        "SaveImage",
        {"images": ["3", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def comfy_ultimate_sd_upscale(args: dict[str, Any]) -> dict[str, Any]:
    """Ultimate SD Upscale tiled img2img path.

    The source image is first loaded, then UltimateSDUpscale performs the
    upscaling and tiled redraw with the selected DreamForge model.
    """
    image_filename = str(args["image"])
    prompt = str(
        args.get("prompt")
        or (
            "faithful high-resolution upscale of the source image, preserve the original "
            "composition, subject, identity, colors, lighting, and layout"
        )
    )
    negative = str(args.get("negative") or "low quality, blurry, deformed, watermark")
    seed = int(args.get("seed", 0))
    steps = int(args.get("steps", UPSCALE_STEPS))
    cfg = float(args.get("cfg", UPSCALE_CFG))
    sampler = str(args.get("sampler_name", UPSCALE_SAMPLER))
    scheduler = str(args.get("scheduler", UPSCALE_SCHEDULER))
    denoise = float(args.get("upscale_denoise", args.get("denoise", UPSCALE_DENOISE)))
    upscale_by = float(args.get("upscale_by", 2.0))
    tile_width = int(args.get("upscale_tile_width", args.get("tile_width", UPSCALE_TILE_WIDTH)))
    tile_height = int(args.get("upscale_tile_height", args.get("tile_height", UPSCALE_TILE_HEIGHT)))
    mask_blur = int(args.get("upscale_mask_blur", args.get("mask_blur", UPSCALE_MASK_BLUR)))
    tile_padding = int(args.get("upscale_tile_padding", args.get("tile_padding", UPSCALE_TILE_PADDING)))
    seam_fix_mode = str(args.get("upscale_seam_fix_mode", args.get("seam_fix_mode", UPSCALE_SEAM_FIX_MODE)))
    seam_fix_denoise = float(args.get("upscale_seam_fix_denoise", args.get("seam_fix_denoise", 1.0)))
    seam_fix_width = int(args.get("upscale_seam_fix_width", args.get("seam_fix_width", 64)))
    seam_fix_mask_blur = int(
        args.get("upscale_seam_fix_mask_blur", args.get("seam_fix_mask_blur", 8))
    )
    seam_fix_padding = int(args.get("upscale_seam_fix_padding", args.get("seam_fix_padding", 16)))
    force_uniform_tiles = bool(args.get("upscale_force_uniform_tiles", args.get("force_uniform_tiles", True)))
    tiled_decode = bool(args.get("upscale_tiled_decode", args.get("tiled_decode", False)))
    batch_size = int(args.get("batch_size", 1))
    mode_type = str(args.get("upscale_mode_type", args.get("mode_type", UPSCALE_MODE_TYPE)))
    upscale_model = str(args.get("upscale_model") or "4x-UltraSharp.pth")

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, args, start_id=1)
    g[str(n)] = _node("LoadImage", {"image": image_filename, "upload": "image"})
    image_out = [str(n), 0]
    n += 1
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    pos = [str(n), 0]
    n += 1
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    neg = [str(n), 0]
    n += 1
    g[str(n)] = _node("UpscaleModelLoader", {"model_name": upscale_model})
    upscale_model_out = [str(n), 0]
    n += 1
    g[str(n)] = _node(
        "UltimateSDUpscale",
        {
            "image": image_out,
            "model": model_out,
            "positive": pos,
            "negative": neg,
            "vae": vae_out,
            "upscale_model": upscale_model_out,
            "upscale_by": upscale_by,
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": denoise,
            "mode_type": mode_type,
            "tile_width": tile_width,
            "tile_height": tile_height,
            "mask_blur": mask_blur,
            "tile_padding": tile_padding,
            "seam_fix_mode": seam_fix_mode,
            "seam_fix_denoise": seam_fix_denoise,
            "seam_fix_width": seam_fix_width,
            "seam_fix_mask_blur": seam_fix_mask_blur,
            "seam_fix_padding": seam_fix_padding,
            "force_uniform_tiles": force_uniform_tiles,
            "tiled_decode": tiled_decode,
            "batch_size": batch_size,
        },
    )
    upscale_out = [str(n), 0]
    n += 1
    g[str(n)] = _node(
        "SaveImage",
        {"images": upscale_out, "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def comfy_pid_flux_upscale(args: dict[str, Any]) -> dict[str, Any]:
    """PiD / PixelDiT generative upscale path from the ComfyUI PixelDiT workflow."""
    image_filename = str(args["image"])
    prompt = str(
        args.get("prompt")
        or (
            "faithful high-resolution upscale of the source image, preserve the original "
            "composition, subject, identity, colors, lighting, and layout"
        )
    )
    negative = str(args.get("negative") or "low quality, blurry, deformed, watermark")
    width = int(args.get("width") or 4096)
    height = int(args.get("height") or 4096)
    seed = int(args.get("seed", 0))
    steps = int(args.get("steps", 4))
    cfg = float(args.get("cfg", 1.0))
    denoise = float(args.get("denoise", 1.0))
    degrade_sigma = float(args.get("degrade_sigma", 0.0))
    sampler = str(args.get("sampler", "lcm"))
    scheduler = str(args.get("scheduler", "simple"))
    pid_model = str(args.get("pid_model") or "pid_flux1_1024_to_4096_4step_mxfp8.safetensors")
    clip_name = str(args.get("clip") or "gemma_2_2b_it_elm_fp8_scaled.safetensors")
    source_vae = str(args.get("source_vae") or args.get("vae") or "flux-vae-bf16.safetensors")
    pixel_vae = str(args.get("pixel_vae") or "pixel_space")

    g: dict[str, Any] = {}
    g["1"] = _node("LoadImage", {"image": image_filename, "upload": "image"})
    g["2"] = _node("VAELoader", {"vae_name": source_vae})
    g["3"] = _node("VAEEncode", {"pixels": ["1", 0], "vae": ["2", 0]})
    g["4"] = _node("UNETLoader", {"unet_name": pid_model, "weight_dtype": "default"})
    g["5"] = _node("CLIPLoader", {"clip_name": clip_name, "type": "pixeldit", "device": "default"})
    g["6"] = _node("CLIPTextEncode", {"clip": ["5", 0], "text": prompt})
    g["7"] = _node("PiDConditioning", {
        "positive": ["6", 0],
        "latent": ["3", 0],
        "latent_format": "flux",
        "degrade_sigma": degrade_sigma,
    })
    g["8"] = _node("CLIPTextEncode", {"clip": ["5", 0], "text": negative})
    g["9"] = _node(
        "EmptyChromaRadianceLatentImage",
        {"width": width, "height": height, "batch_size": 1},
    )
    g["10"] = _node("KSamplerSelect", {"sampler_name": sampler})
    g["11"] = _node("BasicScheduler", {
        "scheduler": scheduler,
        "steps": steps,
        "denoise": denoise,
        "model": ["4", 0],
    })
    g["12"] = _node("SamplerCustom", {
        "model": ["4", 0],
        "positive": ["7", 0],
        "negative": ["8", 0],
        "sampler": ["10", 0],
        "sigmas": ["11", 0],
        "latent_image": ["9", 0],
        "add_noise": True,
        "noise_seed": seed,
        "cfg": cfg,
    })
    g["13"] = _node("VAELoader", {"vae_name": pixel_vae})
    g["14"] = _node("VAEDecode", {"samples": ["12", 0], "vae": ["13", 0]})
    g["15"] = _node(
        "SaveImage",
        {"images": ["14", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def _sampler_inputs(
    *,
    model_out,
    positive,
    negative,
    latent,
    seed: int,
    steps: int,
    cfg: float,
    sampler: str,
    scheduler: str,
    denoise: float,
) -> dict[str, Any]:
    return {
        "model": model_out,
        "positive": positive,
        "negative": negative,
        "latent_image": latent,
        "seed": seed,
        "steps": steps,
        "cfg": cfg,
        "sampler_name": sampler,
        "scheduler": scheduler,
        "denoise": denoise,
    }


def comfy_controlnet_basic(args: dict[str, Any]) -> dict[str, Any]:
    """Structure-preserving txt2img/img2img with ControlNetApplyAdvanced."""
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    control_image = str(args.get("control_image") or args.get("image") or "")
    controlnet_model = str(args.get("controlnet_model") or args.get("cn_model") or "")
    if not controlnet_model:
        raise ValueError("controlnet_model is required for ControlNet workflows")
    width = int(args.get("width", 1024))
    height = int(args.get("height", 1024))
    steps = int(args.get("steps", 30))
    cfg = float(args.get("cfg", 7.0))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "normal"))
    seed = int(args.get("seed", 0))
    denoise = float(args.get("denoise", args.get("edit_strength", 1.0)))
    strength = float(args.get("cn_strength", args.get("controlnet_strength", 1.0)))
    start = float(args.get("cn_start", args.get("controlnet_start", 0.0)))
    end = float(args.get("cn_stop", args.get("controlnet_end", 1.0)))
    image_filename = args.get("image")

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    g["2"] = _node("LoadImage", {"image": control_image, "upload": "image"})
    g[str(n)] = _node("ControlNetLoader", {"control_net_name": controlnet_model})
    cn_out = [str(n), 0]
    n += 1
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    pos = [str(n), 0]
    n += 1
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    neg = [str(n), 0]
    n += 1
    g[str(n)] = _node(
        "ControlNetApplyAdvanced",
        {
            "positive": pos,
            "negative": neg,
            "control_net": cn_out,
            "image": ["2", 0],
            "strength": strength,
            "start_percent": start,
            "end_percent": end,
        },
    )
    pos_cn, neg_cn = [str(n), 0], [str(n), 1]
    n += 1
    if image_filename:
        g[str(n)] = _node("LoadImage", {"image": str(image_filename), "upload": "image"})
        img_node = str(n)
        n += 1
        g[str(n)] = _node("VAEEncode", {"pixels": [img_node, 0], "vae": vae_out})
        latent = [str(n), 0]
        n += 1
    else:
        g[str(n)] = _node("EmptyLatentImage", {"width": width, "height": height, "batch_size": 1})
        latent = [str(n), 0]
        n += 1
    g[str(n)] = _node(
        "KSampler",
        _sampler_inputs(
            model_out=model_out,
            positive=pos_cn,
            negative=neg_cn,
            latent=latent,
            seed=seed,
            steps=steps,
            cfg=cfg,
            sampler=sampler,
            scheduler=scheduler,
            denoise=denoise if image_filename else 1.0,
        ),
    )
    samp = str(n)
    n += 1
    g[str(n)] = _vae_decode_node(args, [samp, 0], vae_out)
    dec = str(n)
    g[str(n + 1)] = _node(
        "SaveImage",
        {"images": [dec, 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def comfy_outpaint_basic(args: dict[str, Any]) -> dict[str, Any]:
    """Pad canvas then inpaint the expanded region (Comfy ImagePadForOutpaint pattern)."""
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    image_filename = str(args["image"])
    left = int(args.get("outpaint_left", 0))
    top = int(args.get("outpaint_top", 0))
    right = int(args.get("outpaint_right", 0))
    bottom = int(args.get("outpaint_bottom", 0))
    direction = str(args.get("outpaint_direction") or "").lower()
    amount = int(args.get("outpaint_amount", 128))
    if direction == "left":
        left = max(left, amount)
    elif direction == "right":
        right = max(right, amount)
    elif direction == "top":
        top = max(top, amount)
    elif direction == "bottom":
        bottom = max(bottom, amount)
    elif not any((left, top, right, bottom)):
        right = amount
    feather = int(args.get("outpaint_feathering", args.get("feather", 40)))
    steps = int(args.get("steps", 30))
    cfg = float(args.get("cfg", 7.0))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "normal"))
    seed = int(args.get("seed", 0))
    denoise = float(args.get("denoise", args.get("edit_strength", 1.0)))
    grow_mask_by = int(args.get("grow_mask_by", args.get("inpaint_mask_grow_by", 0)))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    g["2"] = _node("LoadImage", {"image": image_filename, "upload": "image"})
    g["3"] = _node(
        "ImagePadForOutpaint",
        {
            "image": ["2", 0],
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
            "feathering": feather,
        },
    )
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    pos = [str(n), 0]
    n += 1
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    neg = [str(n), 0]
    n += 1
    g[str(n)] = _node(
        "VAEEncodeForInpaint",
        {
            "pixels": ["3", 0],
            "mask": ["3", 1],
            "vae": vae_out,
            "grow_mask_by": grow_mask_by,
        },
    )
    latent = [str(n), 0]
    n += 1
    g[str(n)] = _node(
        "KSampler",
        _sampler_inputs(
            model_out=model_out,
            positive=pos,
            negative=neg,
            latent=latent,
            seed=seed,
            steps=steps,
            cfg=cfg,
            sampler=sampler,
            scheduler=scheduler,
            denoise=denoise,
        ),
    )
    samp = str(n)
    n += 1
    g[str(n)] = _vae_decode_node(args, [samp, 0], vae_out)
    dec = str(n)
    g[str(n + 1)] = _node(
        "SaveImage",
        {"images": [dec, 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def comfy_hires_two_pass(args: dict[str, Any]) -> dict[str, Any]:
    """Generate smaller first pass, upscale latent, refine with low denoise."""
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    width = int(args.get("width", 1024))
    height = int(args.get("height", 1024))
    scale = float(args.get("hires_first_pass_scale", 0.5))
    first_w = int(args.get("hires_first_width") or max(512, int(width * scale)))
    first_h = int(args.get("hires_first_height") or max(512, int(height * scale)))
    first_steps = int(args.get("hires_first_steps", args.get("steps", 20)))
    second_steps = int(args.get("hires_second_steps", max(12, int(args.get("steps", 20)) // 2)))
    cfg = float(args.get("cfg", 7.0))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "normal"))
    seed = int(args.get("seed", 0))
    second_denoise = float(args.get("hires_denoise", 0.35))
    upscale_method = str(args.get("hires_latent_upscale_method", "nearest-exact"))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    pos = [str(n), 0]
    n += 1
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    neg = [str(n), 0]
    n += 1
    g[str(n)] = _node("EmptyLatentImage", {"width": first_w, "height": first_h, "batch_size": 1})
    latent1 = [str(n), 0]
    n += 1
    g[str(n)] = _node(
        "KSampler",
        _sampler_inputs(
            model_out=model_out,
            positive=pos,
            negative=neg,
            latent=latent1,
            seed=seed,
            steps=first_steps,
            cfg=cfg,
            sampler=sampler,
            scheduler=scheduler,
            denoise=1.0,
        ),
    )
    samp1 = str(n)
    n += 1
    g[str(n)] = _node(
        "LatentUpscale",
        {
            "samples": [samp1, 0],
            "upscale_method": upscale_method,
            "width": width,
            "height": height,
            "crop": "disabled",
        },
    )
    latent2 = [str(n), 0]
    n += 1
    g[str(n)] = _node(
        "KSampler",
        _sampler_inputs(
            model_out=model_out,
            positive=pos,
            negative=neg,
            latent=latent2,
            seed=seed,
            steps=second_steps,
            cfg=cfg,
            sampler=sampler,
            scheduler=scheduler,
            denoise=second_denoise,
        ),
    )
    samp2 = str(n)
    n += 1
    g[str(n)] = _vae_decode_node(args, [samp2, 0], vae_out)
    dec = str(n)
    g[str(n + 1)] = _node(
        "SaveImage",
        {"images": [dec, 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def _normalize_ipadapter_slots(args: dict[str, Any]) -> list[dict[str, Any]]:
    raw = args.get("reference_slots")
    if isinstance(raw, list) and raw:
        out: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            image = str(item.get("image") or item.get("path") or "").strip()
            if not image:
                continue
            out.append(
                {
                    "image": image,
                    "weight": float(
                        item.get("weight", args.get("ipadapter_weight", args.get("reference_weight", 0.75)))
                    ),
                    "stop_at": float(item.get("stop_at", item.get("end_at", 1.0))),
                }
            )
        if out:
            return out
    reference_image = str(args.get("reference_image") or args.get("image") or "")
    if reference_image:
        return [
            {
                "image": reference_image,
                "weight": float(
                    args.get("ipadapter_weight", args.get("reference_weight", 0.75))
                ),
                "stop_at": 1.0,
            }
        ]
    return []


def _comfy_ipadapter_from_slots(args: dict[str, Any], slots: list[dict[str, Any]]) -> dict[str, Any]:
    """Chain IPAdapterAdvanced nodes for one or more image-prompt slots."""
    if not slots:
        raise ValueError("reference image is required for IPAdapter workflows")
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    ipadapter_model = str(args.get("ipadapter_model") or args.get("ip_adapter_model") or "")
    clip_vision = str(args.get("clip_vision") or args.get("clip_vision_model") or "")
    if not ipadapter_model or not clip_vision:
        raise ValueError("ipadapter_model and clip_vision are required for IPAdapter workflows")
    width = int(args.get("width", 1024))
    height = int(args.get("height", 1024))
    steps = int(args.get("steps", 30))
    cfg = float(args.get("cfg", 7.0))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "normal"))
    seed = int(args.get("seed", 0))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    g[str(n)] = _node("CLIPVisionLoader", {"clip_name": clip_vision})
    clip_vis = [str(n), 0]
    n += 1
    g[str(n)] = _node("IPAdapterModelLoader", {"ipadapter_file": ipadapter_model})
    ipa = [str(n), 0]
    n += 1
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    pos = [str(n), 0]
    n += 1
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    neg = [str(n), 0]
    n += 1

    model_ipa = model_out
    for index, slot in enumerate(slots):
        g[str(n)] = _node(
            "LoadImage",
            {"image": str(slot["image"]), "upload": "image"},
        )
        image_ref = [str(n), 0]
        n += 1
        g[str(n)] = _node(
            "IPAdapterAdvanced",
            {
                "model": model_ipa,
                "ipadapter": ipa,
                "clip_vision": clip_vis,
                "image": image_ref,
                "weight": float(slot.get("weight", 0.75)),
                "weight_type": "linear",
                "combine_embeds": "concat",
                "start_at": 0.0,
                "end_at": float(slot.get("stop_at", 1.0)),
                "embeds_scaling": "V only",
            },
        )
        model_ipa = [str(n), 0]
        n += 1

    g[str(n)] = _node("EmptyLatentImage", {"width": width, "height": height, "batch_size": 1})
    latent = [str(n), 0]
    n += 1
    g[str(n)] = _node(
        "KSampler",
        _sampler_inputs(
            model_out=model_ipa,
            positive=pos,
            negative=neg,
            latent=latent,
            seed=seed,
            steps=steps,
            cfg=cfg,
            sampler=sampler,
            scheduler=scheduler,
            denoise=1.0,
        ),
    )
    samp = str(n)
    n += 1
    g[str(n)] = _vae_decode_node(args, [samp, 0], vae_out)
    dec = str(n)
    g[str(n + 1)] = _node(
        "SaveImage",
        {"images": [dec, 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def comfy_ipadapter_controlnet_hybrid(args: dict[str, Any]) -> dict[str, Any]:
    """Image-prompt slots + structure ControlNet in one txt2img graph."""
    ipa_slots = _normalize_ipadapter_slots(args)
    structure = args.get("structure_slot") or {}
    if not ipa_slots:
        raise ValueError("image-prompt slots are required for hybrid IP-Adapter + ControlNet")
    control_image = str(
        structure.get("image")
        or structure.get("path")
        or args.get("control_image")
        or ""
    )
    controlnet_model = str(args.get("controlnet_model") or args.get("cn_model") or "")
    if not control_image or not controlnet_model:
        raise ValueError("structure_slot and controlnet_model are required for hybrid workflows")

    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    ipadapter_model = str(args.get("ipadapter_model") or args.get("ip_adapter_model") or "")
    clip_vision = str(args.get("clip_vision") or args.get("clip_vision_model") or "")
    if not ipadapter_model or not clip_vision:
        raise ValueError("ipadapter_model and clip_vision are required for IPAdapter workflows")
    width = int(args.get("width", 1024))
    height = int(args.get("height", 1024))
    steps = int(args.get("steps", 30))
    cfg = float(args.get("cfg", 7.0))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "normal"))
    seed = int(args.get("seed", 0))
    cn_strength = float(
        structure.get("weight", args.get("cn_strength", args.get("controlnet_strength", 1.0)))
    )
    cn_stop = float(
        structure.get("stop_at", args.get("cn_stop", args.get("controlnet_end", 1.0)))
    )

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    g[str(n)] = _node("CLIPVisionLoader", {"clip_name": clip_vision})
    clip_vis = [str(n), 0]
    n += 1
    g[str(n)] = _node("IPAdapterModelLoader", {"ipadapter_file": ipadapter_model})
    ipa = [str(n), 0]
    n += 1
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    pos = [str(n), 0]
    n += 1
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    neg = [str(n), 0]
    n += 1

    model_ipa = model_out
    for slot in ipa_slots:
        g[str(n)] = _node("LoadImage", {"image": str(slot["image"]), "upload": "image"})
        image_ref = [str(n), 0]
        n += 1
        g[str(n)] = _node(
            "IPAdapterAdvanced",
            {
                "model": model_ipa,
                "ipadapter": ipa,
                "clip_vision": clip_vis,
                "image": image_ref,
                "weight": float(slot.get("weight", 0.75)),
                "weight_type": "linear",
                "combine_embeds": "concat",
                "start_at": 0.0,
                "end_at": float(slot.get("stop_at", 1.0)),
                "embeds_scaling": "V only",
            },
        )
        model_ipa = [str(n), 0]
        n += 1

    g[str(n)] = _node("LoadImage", {"image": control_image, "upload": "image"})
    control_ref = [str(n), 0]
    n += 1
    g[str(n)] = _node("ControlNetLoader", {"control_net_name": controlnet_model})
    cn_out = [str(n), 0]
    n += 1
    g[str(n)] = _node(
        "ControlNetApplyAdvanced",
        {
            "positive": pos,
            "negative": neg,
            "control_net": cn_out,
            "image": control_ref,
            "strength": cn_strength,
            "start_percent": 0.0,
            "end_percent": cn_stop,
        },
    )
    pos_cn, neg_cn = [str(n), 0], [str(n), 1]
    n += 1
    g[str(n)] = _node("EmptyLatentImage", {"width": width, "height": height, "batch_size": 1})
    latent = [str(n), 0]
    n += 1
    g[str(n)] = _node(
        "KSampler",
        _sampler_inputs(
            model_out=model_ipa,
            positive=pos_cn,
            negative=neg_cn,
            latent=latent,
            seed=seed,
            steps=steps,
            cfg=cfg,
            sampler=sampler,
            scheduler=scheduler,
            denoise=1.0,
        ),
    )
    samp = str(n)
    n += 1
    g[str(n)] = _vae_decode_node(args, [samp, 0], vae_out)
    dec = str(n)
    g[str(n + 1)] = _node(
        "SaveImage",
        {"images": [dec, 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def comfy_ipadapter_faceid_reference(args: dict[str, Any]) -> dict[str, Any]:
    """Face identity via IP-Adapter FaceID + InsightFace (ComfyUI_IPAdapter_plus)."""
    reference_image = str(args.get("reference_image") or args.get("image") or "")
    if not reference_image:
        raise ValueError("reference image is required for FaceID workflows")
    faceid_model = str(
        args.get("ipadapter_faceid_model")
        or args.get("ipadapter_model")
        or args.get("ip_adapter_model")
        or ""
    )
    if not faceid_model:
        raise ValueError("ipadapter_faceid_model is required for FaceID workflows")

    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    width = int(args.get("width", 1024))
    height = int(args.get("height", 1024))
    steps = int(args.get("steps", 30))
    cfg = float(args.get("cfg", 7.0))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "normal"))
    seed = int(args.get("seed", 0))
    weight = float(args.get("ipadapter_weight", args.get("reference_weight", 0.75)))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    g[str(n)] = _node(
        "IPAdapterUnifiedLoaderFaceID",
        {
            "model": model_out,
            "preset": "FACEID",
            "lora_strength": 0.6,
            "provider": "CPU",
            "ipadapter_file": faceid_model,
        },
    )
    loader_model = [str(n), 0]
    loader_ipa = [str(n), 1]
    n += 1
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    pos = [str(n), 0]
    n += 1
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    neg = [str(n), 0]
    n += 1
    g[str(n)] = _node("LoadImage", {"image": reference_image, "upload": "image"})
    image_ref = [str(n), 0]
    n += 1
    g[str(n)] = _node(
        "IPAdapterFaceID",
        {
            "model": loader_model,
            "ipadapter": loader_ipa,
            "image": image_ref,
            "weight": weight,
            "weight_faceidv2": 1.0,
            "weight_type": "linear",
            "combine_embeds": "concat",
            "start_at": 0.0,
            "end_at": 1.0,
        },
    )
    model_faceid = [str(n), 0]
    n += 1
    g[str(n)] = _node("EmptyLatentImage", {"width": width, "height": height, "batch_size": 1})
    latent = [str(n), 0]
    n += 1
    g[str(n)] = _node(
        "KSampler",
        _sampler_inputs(
            model_out=model_faceid,
            positive=pos,
            negative=neg,
            latent=latent,
            seed=seed,
            steps=steps,
            cfg=cfg,
            sampler=sampler,
            scheduler=scheduler,
            denoise=1.0,
        ),
    )
    samp = str(n)
    n += 1
    g[str(n)] = _vae_decode_node(args, [samp, 0], vae_out)
    dec = str(n)
    g[str(n + 1)] = _node(
        "SaveImage",
        {"images": [dec, 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def comfy_ipadapter_reference(args: dict[str, Any]) -> dict[str, Any]:
    """Reference/style guidance via ComfyUI_IPAdapter_plus (guarded at runtime)."""
    structure_slot = args.get("structure_slot")
    slots = _normalize_ipadapter_slots(args)
    if structure_slot and slots:
        return comfy_ipadapter_controlnet_hybrid(args)
    return _comfy_ipadapter_from_slots(args, slots)


def comfy_face_detail_basic(args: dict[str, Any]) -> dict[str, Any]:
    """Face/hand detail repair via Impact Pack FaceDetailer + Impact Subpack detectors."""
    ckpt = str(args["ckpt_name"])
    image = str(args.get("image") or args.get("input_image") or "")
    if not image:
        raise ValueError("image is required for face detail workflows")
    detail_target = str(args.get("detail_target") or "face").lower()
    bbox_model = str(args.get("bbox_model") or args.get("bbox_detector_model") or "")
    if not bbox_model:
        bbox_model = "bbox/hand_yolov8s.pt" if detail_target == "hand" else "bbox/face_yolov8m.pt"
    prompt = str(
        args.get("detail_prompt")
        or args.get("prompt")
        or ("detailed hands, natural fingers" if detail_target == "hand" else "detailed face, sharp eyes, natural skin")
    )
    negative = str(args.get("negative") or "blurry, deformed, low quality, bad anatomy")
    steps = int(args.get("steps", 20))
    cfg = float(args.get("cfg", 8.0))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "normal"))
    seed = int(args.get("seed", 0))
    denoise = float(args.get("detail_denoise", args.get("denoise", args.get("edit_strength", 0.5))))
    sam_model = str(args.get("sam_model") or args.get("sam_model_name") or "").strip()

    g: dict[str, Any] = {}
    g["1"] = _node("LoadImage", {"image": image, "upload": "image"})
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": prompt})
    pos = [str(n), 0]
    n += 1
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    neg = [str(n), 0]
    n += 1
    g[str(n)] = _node("UltralyticsDetectorProvider", {"model_name": bbox_model})
    bbox_det = [str(n), 0]
    n += 1
    face_inputs: dict[str, Any] = {
        "image": ["1", 0],
        "model": model_out,
        "clip": clip_out,
        "vae": vae_out,
        "guide_size": float(args.get("guide_size", 512)),
        "guide_size_for": True,
        "max_size": float(args.get("max_size", 1024)),
        "seed": seed,
        "steps": steps,
        "cfg": cfg,
        "sampler_name": sampler,
        "scheduler": scheduler,
        "positive": pos,
        "negative": neg,
        "denoise": denoise,
        "feather": int(args.get("feather", 5)),
        "noise_mask": True,
        "force_inpaint": True,
        "bbox_threshold": float(args.get("bbox_threshold", 0.5)),
        "bbox_dilation": int(args.get("bbox_dilation", 10)),
        "bbox_crop_factor": float(args.get("bbox_crop_factor", 3.0)),
        "sam_detection_hint": str(args.get("sam_detection_hint", "center-1")),
        "sam_dilation": int(args.get("sam_dilation", 0)),
        "sam_threshold": float(args.get("sam_threshold", 0.93)),
        "sam_bbox_expansion": int(args.get("sam_bbox_expansion", 0)),
        "sam_mask_hint_threshold": float(args.get("sam_mask_hint_threshold", 0.7)),
        "sam_mask_hint_use_negative": str(args.get("sam_mask_hint_use_negative", "False")),
        "drop_size": int(args.get("drop_size", 10)),
        "bbox_detector": bbox_det,
        "wildcard": str(args.get("wildcard", "")),
        "cycle": int(args.get("cycle", 1)),
    }
    if sam_model:
        g[str(n)] = _node("SAMLoader", {"model_name": sam_model, "device_mode": "AUTO"})
        face_inputs["sam_model_opt"] = [str(n), 0]
        n += 1
    g[str(n)] = _node("FaceDetailer", face_inputs)
    enhanced = [str(n), 0]
    g[str(n + 1)] = _node(
        "SaveImage",
        {"images": enhanced, "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def _parse_region_specs(args: dict[str, Any]) -> list[dict[str, Any]]:
    raw = args.get("region_prompts") or args.get("composition_regions") or args.get("regions_or_layers")
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("["):
            import json

            raw = json.loads(text)
        else:
            return [{"prompt": text, "x": 0, "y": 0, "width": 512, "height": 512}]
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list) or not raw:
        bg = str(args.get("region_prompt") or args.get("prompt") or "")
        fg = str(args.get("foreground_prompt") or "subject, detailed")
        return [
            {"prompt": bg, "x": 0, "y": 0, "width": 1024, "height": 1024},
            {"prompt": fg, "x": 256, "y": 128, "width": 512, "height": 768},
        ]
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            out.append({"prompt": item, "x": 0, "y": 0, "width": 512, "height": 512})
            continue
        if isinstance(item, dict):
            out.append(
                {
                    "prompt": str(item.get("prompt") or item.get("text") or ""),
                    "x": int(item.get("x", 0)),
                    "y": int(item.get("y", 0)),
                    "width": int(item.get("width", 512)),
                    "height": int(item.get("height", 512)),
                }
            )
    return out or [{"prompt": str(args.get("prompt", "")), "x": 0, "y": 0, "width": 1024, "height": 1024}]


def comfy_area_composition(args: dict[str, Any]) -> dict[str, Any]:
    """Regional prompts via ConditioningSetArea + ConditioningCombine."""
    ckpt = str(args["ckpt_name"])
    negative = str(args.get("negative", ""))
    width = int(args.get("width", 1024))
    height = int(args.get("height", 1024))
    steps = int(args.get("steps", 30))
    cfg = float(args.get("cfg", 7.0))
    sampler = str(args.get("sampler_name", "euler"))
    scheduler = str(args.get("scheduler", "normal"))
    seed = int(args.get("seed", 0))
    regions = _parse_region_specs(args)

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": negative})
    negative_cond = [str(n), 0]
    n += 1
    combined: list[str] | None = None
    for index, region in enumerate(regions):
        g[str(n)] = _node("CLIPTextEncode", {"clip": clip_out, "text": str(region["prompt"])})
        enc = str(n)
        n += 1
        g[str(n)] = _node(
            "ConditioningSetArea",
            {
                "conditioning": [enc, 0],
                "width": int(region["width"]),
                "height": int(region["height"]),
                "x": int(region["x"]),
                "y": int(region["y"]),
                "strength": 1.0,
            },
        )
        area = str(n)
        n += 1
        if combined is None:
            combined = [area, 0]
            continue
        g[str(n)] = _node("ConditioningCombine", {"conditioning_1": combined, "conditioning_2": [area, 0]})
        combined = [str(n), 0]
        n += 1
    positive = combined or [str(n - 1), 0]
    g[str(n)] = _node("EmptyLatentImage", {"width": width, "height": height, "batch_size": 1})
    latent = [str(n), 0]
    n += 1
    g[str(n)] = _node(
        "KSampler",
        _sampler_inputs(
            model_out=model_out,
            positive=positive,
            negative=negative_cond,
            latent=latent,
            seed=seed,
            steps=steps,
            cfg=cfg,
            sampler=sampler,
            scheduler=scheduler,
            denoise=1.0,
        ),
    )
    samp = str(n)
    n += 1
    g[str(n)] = _vae_decode_node(args, [samp, 0], vae_out)
    dec = str(n)
    g[str(n + 1)] = _node(
        "SaveImage",
        {"images": [dec, 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g
