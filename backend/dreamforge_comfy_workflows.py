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

