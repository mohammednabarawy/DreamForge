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


def _node(class_type: str, inputs: dict[str, Any]) -> dict[str, Any]:
    return {"class_type": class_type, "inputs": inputs}


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
    if category in ("diffusion_models", "unet"):
        unet_name = str(args.get("unet_name") or model_name)
        if unet_name.endswith(".gguf"):
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
            return model_out, clip_out, vae_out, i
        raise ValueError(f"Comfy split-diffusion loader is not configured for family '{family}'")

    g[str(i)] = _node("CheckpointLoaderSimple", {"ckpt_name": model_name})
    return [str(i), 0], [str(i), 1], [str(i), 2], i + 1


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
    prompt_graph["4"] = _node("EmptyLatentImage", {"width": width, "height": height, "batch_size": 1})
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
    prompt_graph["6"] = _node("VAEDecode", {"samples": ["5", 0], "vae": vae_out})
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
    g["7"] = _node("VAEDecode", {"samples": ["6", 0], "vae": vae_out})
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
    g["2"] = _node("LoadImage", {"image": image_filename, "upload": "image"})
    g["3"] = _node("VAEEncode", {"pixels": ["2", 0], "vae": vae_out})
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
    g["7"] = _node("VAEDecode", {"samples": ["6", 0], "vae": vae_out})
    g["8"] = _node("SaveImage", {"images": ["7", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))})
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
    g["11"] = _node("VAEDecode", {"samples": ["10", 0], "vae": vae_out})
    g["12"] = _node(
        "SaveImage",
        {"images": ["11", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def _apply_qwen_model_sampling(model_out: list[str | int], g: dict[str, Any], start_id: int, args: dict[str, Any]):
    """AuraFlow + CFGNorm prep used by native Comfy Qwen workflows."""
    shift = float(args.get("shift", args.get("qwen_image_shift", 3.1)))
    strength = float(
        args.get("cfg_norm_strength", args.get("qwen_cfg_norm_strength", 1.0))
    )
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
    preferred = (
        "Qwen-Image-Edit-2509-Lightning-4steps-V1.0-fp32.safetensors",
        "Qwen-Image-Edit-2509-Lightning-8steps-V1.0-fp32.safetensors",
        "Qwen-Image-Edit-Lightning-4steps-V1.0.safetensors",
        "Qwen-Image-Edit-Lightning-8steps-V1.0.safetensors",
    )
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
    raw = args.get("qwen_scale_megapixels")
    if raw is None:
        return image_out, start_id
    try:
        megapixels = float(raw)
    except (TypeError, ValueError):
        return image_out, start_id
    if megapixels <= 0:
        return image_out, start_id
    g[str(start_id)] = _node(
        "ImageScaleToTotalPixels",
        {
            "image": image_out,
            "upscale_method": str(args.get("qwen_scale_method", "bicubic")),
            "megapixels": megapixels,
            "resolution_steps": int(args.get("qwen_resolution_steps", 1)),
        },
    )
    return [str(start_id), 0], start_id + 1


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
    g[decode] = _node("VAEDecode", {"samples": [samp, 0], "vae": args["_vae_out"]})
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
    model_sampled = _apply_qwen_model_sampling(model_out, g, n, args)
    n += 2
    model_sampled, n = _apply_qwen_lightning_lora(model_sampled, g, n, args)
    g["1"] = _node("LoadImage", {"image": image_filename, "upload": "image"})
    image_out, n = _maybe_scale_qwen_pixels(g, ["1", 0], n, args)
    g[str(n)] = _node(
        "TextEncodeQwenImageEdit",
        {"clip": clip_out, "vae": vae_out, "image": image_out, "prompt": prompt},
    )
    pos = [str(n), 0]
    n += 1
    g[str(n)] = _node(
        "TextEncodeQwenImageEdit",
        {"clip": clip_out, "vae": vae_out, "image": image_out, "prompt": negative},
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
    model_sampled = _apply_qwen_model_sampling(model_out, g, n, args)
    n += 2
    model_sampled, n = _apply_qwen_lightning_lora(model_sampled, g, n, args)

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
            "vae": vae_out,
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
    model_sampled = _apply_qwen_model_sampling(model_out, g, n, args)
    n += 2
    model_sampled, n = _apply_qwen_lightning_lora(model_sampled, g, n, args)
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
    g["6"] = _node("VAEDecode", {"samples": ["5", 0], "vae": vae_out})
    g["7"] = _node(
        "SaveImage",
        {"images": ["6", 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
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
    g["9"] = _node("VAEDecode", {"samples": ["8", 0], "vae": vae_out})
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
    g[str(n)] = _node("VAEDecode", {"samples": [samp, 0], "vae": vae_out})
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
    g[str(n)] = _node("VAEDecode", {"samples": [samp, 0], "vae": vae_out})
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
    g[str(n)] = _node("VAEDecode", {"samples": [samp2, 0], "vae": vae_out})
    dec = str(n)
    g[str(n + 1)] = _node(
        "SaveImage",
        {"images": [dec, 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


def comfy_ipadapter_reference(args: dict[str, Any]) -> dict[str, Any]:
    """Reference/style guidance via ComfyUI_IPAdapter_plus (guarded at runtime)."""
    ckpt = str(args["ckpt_name"])
    prompt = str(args.get("prompt", ""))
    negative = str(args.get("negative", ""))
    reference_image = str(args.get("reference_image") or args.get("image") or "")
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
    weight = float(args.get("ipadapter_weight", args.get("reference_weight", 0.75)))

    g: dict[str, Any] = {}
    model_out, clip_out, vae_out, n = _add_model_loader(g, {**args, "ckpt_name": ckpt})
    g["2"] = _node("LoadImage", {"image": reference_image, "upload": "image"})
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
    g[str(n)] = _node(
        "IPAdapterAdvanced",
        {
            "model": model_out,
            "ipadapter": ipa,
            "clip_vision": clip_vis,
            "image": ["2", 0],
            "weight": weight,
            "weight_type": "linear",
            "combine_embeds": "concat",
            "start_at": 0.0,
            "end_at": 1.0,
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
    g[str(n)] = _node("VAEDecode", {"samples": [samp, 0], "vae": vae_out})
    dec = str(n)
    g[str(n + 1)] = _node(
        "SaveImage",
        {"images": [dec, 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g


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
    g[str(n)] = _node("VAEDecode", {"samples": [samp, 0], "vae": vae_out})
    dec = str(n)
    g[str(n + 1)] = _node(
        "SaveImage",
        {"images": [dec, 0], "filename_prefix": str(args.get("filename_prefix", "DreamForge"))},
    )
    return g

