"""Studio resource catalog derived from Krita AI Diffusion manifests.

Reference: https://github.com/Acly/krita-ai-diffusion (GPL-3.0)
DreamForge stores download URLs and filenames only; logic is reimplemented here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dreamforge_cli_inventory import MODELS_ROOT, companion_file_present

# Upscaler aliases used by the desktop studio (cn_upscale / upscale_method).
UPSCALER_CATALOG: dict[str, dict[str, Any]] = {
    "default": {
        "filename": "4x_NMKD-Superscale-SP_178000_G.pth",
        "scale": 4,
        "label": "Quality 4× (NMKD)",
    },
    "quality": {
        "filename": "HAT_SRx4_ImageNet-pretrain.pth",
        "scale": 4,
        "label": "High quality 4× (HAT)",
    },
    "sharp": {
        "filename": "Real_HAT_GAN_sharper.pth",
        "scale": 4,
        "label": "Sharper 4×",
    },
    "fast_2x": {
        "filename": "OmniSR_X2_DIV2K.safetensors",
        "scale": 2,
        "label": "Fast 2× (OmniSR)",
    },
    "fast_3x": {
        "filename": "OmniSR_X3_DIV2K.safetensors",
        "scale": 3,
        "label": "Fast 3× (OmniSR)",
    },
    "fast_4x": {
        "filename": "OmniSR_X4_DIV2K.safetensors",
        "scale": 4,
        "label": "Fast 4× (OmniSR)",
    },
    # Legacy UI / powerup aliases
    "2x": {
        "filename": "OmniSR_X2_DIV2K.safetensors",
        "scale": 2,
        "label": "Fast 2× (OmniSR)",
    },
    "4x": {
        "filename": "4x_NMKD-Superscale-SP_178000_G.pth",
        "scale": 4,
        "label": "Quality 4× (NMKD)",
    },
    "4x-UltraSharp.pth": {
        "filename": "4x-UltraSharp.pth",
        "scale": 4,
        "label": "UltraSharp 4× (legacy)",
    },
}

# Downloadable studio assets (upscalers, inpaint helpers, Flux inpaint CN).
# Primary FLUX diffusion UNets referenced by DreamForge inventories and Krita/Comfy docs.
KRITA_DOWNLOADABLE_DIFFUSION: dict[str, dict[str, Any]] = {
    "diffusion_flux_kontext_fp8_scaled": {
        "relative": "diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors",
        "url": (
            "https://huggingface.co/Comfy-Org/flux1-kontext-dev_ComfyUI/resolve/main/"
            "split_files/diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors"
        ),
        "min_bytes": 10 * 1024 * 1024 * 1024,
        "note": "FLUX.1 Kontext dev FP8 (Krita AI Diffusion contextual edit)",
    },
    "diffusion_flux_dev_fp8": {
        "relative": "diffusion_models/flux1-dev-fp8.safetensors",
        "url": (
            "https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/"
            "flux1-dev-fp8.safetensors"
        ),
        "min_bytes": 10 * 1024 * 1024 * 1024,
        "note": "FLUX.1 dev FP8 img2img (when not using Kontext checkpoint)",
        "optional": True,
    },
}

STUDIO_RESOURCE_SOURCES: dict[str, dict[str, Any]] = {
    "upscaler_nmkd_4x": {
        "relative": "upscale_models/4x_NMKD-Superscale-SP_178000_G.pth",
        "url": "https://huggingface.co/gemasai/4x_NMKD-Superscale-SP_178000_G/resolve/main/4x_NMKD-Superscale-SP_178000_G.pth",
        "min_bytes": 60 * 1024 * 1024,
    },
    "upscaler_omnisr_2x": {
        "relative": "upscale_models/OmniSR_X2_DIV2K.safetensors",
        "url": "https://huggingface.co/Acly/Omni-SR/resolve/main/OmniSR_X2_DIV2K.safetensors",
        "min_bytes": 2 * 1024 * 1024,
    },
    "upscaler_omnisr_3x": {
        "relative": "upscale_models/OmniSR_X3_DIV2K.safetensors",
        "url": "https://huggingface.co/Acly/Omni-SR/resolve/main/OmniSR_X3_DIV2K.safetensors",
        "min_bytes": 2 * 1024 * 1024,
    },
    "upscaler_omnisr_4x": {
        "relative": "upscale_models/OmniSR_X4_DIV2K.safetensors",
        "url": "https://huggingface.co/Acly/Omni-SR/resolve/main/OmniSR_X4_DIV2K.safetensors",
        "min_bytes": 2 * 1024 * 1024,
    },
    "inpaint_mat_default": {
        "relative": "inpaint/MAT_Places512_G_fp16.safetensors",
        "url": "https://huggingface.co/Acly/MAT/resolve/main/MAT_Places512_G_fp16.safetensors",
        "min_bytes": 100 * 1024 * 1024,
        "optional": True,
    },
    "controlnet_flux_inpaint": {
        "relative": "controlnet/FLUX.1-dev-Controlnet-Inpainting-Beta.safetensors",
        "url": "https://huggingface.co/alimama-creative/FLUX.1-dev-Controlnet-Inpainting-Beta/resolve/main/diffusion_pytorch_model.safetensors",
        "min_bytes": 900 * 1024 * 1024,
        "optional": True,
    },
    "controlnet_depth_sd15": {
        "relative": "controlnet/control_lora_rank128_v11f1p_sd15_depth_fp16.safetensors",
        "url": "https://huggingface.co/comfyanonymous/ControlNet-v1-1_fp16_safetensors/resolve/main/control_lora_rank128_v11f1p_sd15_depth_fp16.safetensors",
        "min_bytes": 60 * 1024 * 1024,
        "optional": True,
    },
    "controlnet_pose_sd15": {
        "relative": "controlnet/control_lora_rank128_v11p_sd15_openpose_fp16.safetensors",
        "url": "https://huggingface.co/comfyanonymous/ControlNet-v1-1_fp16_safetensors/resolve/main/control_lora_rank128_v11p_sd15_openpose_fp16.safetensors",
        "min_bytes": 60 * 1024 * 1024,
        "optional": True,
    },
    "controlnet_canny_sd15": {
        "relative": "controlnet/control_v11p_sd15_canny_fp16.safetensors",
        "url": "https://huggingface.co/comfyanonymous/ControlNet-v1-1_fp16_safetensors/resolve/main/control_v11p_sd15_canny_fp16.safetensors",
        "min_bytes": 60 * 1024 * 1024,
        "optional": True,
    },
    "controlnet_sdxl_union": {
        "relative": "controlnet/xinsir-controlnet-union-sdxl-1.0-promax.safetensors",
        "url": "https://huggingface.co/xinsir/controlnet-union-sdxl-1.0/resolve/main/diffusion_pytorch_model_promax.safetensors",
        "min_bytes": 2 * 1024 * 1024 * 1024,
        "optional": True,
    },
    "clip_vision_ipadapter_vith": {
        "relative": "clip_vision/clip-vision_vit-h.safetensors",
        "url": "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors",
        "min_bytes": 1 * 1024 * 1024 * 1024,
        "optional": True,
    },
    "ipadapter_sdxl_vith": {
        "relative": "ipadapter/ip-adapter_sdxl_vit-h.safetensors",
        "url": "https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter_sdxl_vit-h.safetensors",
        "min_bytes": 500 * 1024 * 1024,
        "optional": True,
    },
    "ipadapter_sd15": {
        "relative": "ipadapter/ip-adapter_sd15.safetensors",
        "url": "https://huggingface.co/h94/IP-Adapter/resolve/main/models/ip-adapter_sd15.safetensors",
        "min_bytes": 50 * 1024 * 1024,
        "optional": True,
    },
    "upscaler_ultrasharp_legacy": {
        "relative": "upscale_models/4x-UltraSharp.pth",
        "url": "https://huggingface.co/lokCX/4x-Ultrasharp/resolve/main/4x-UltraSharp.pth",
        "min_bytes": 60 * 1024 * 1024,
        "optional": True,
    },
    **KRITA_DOWNLOADABLE_DIFFUSION,
}

STUDIO_MODE_RESOURCES: dict[str, list[str]] = {
    "upscale": ["upscaler_omnisr_2x", "upscaler_nmkd_4x"],
    "inpaint": ["inpaint_mat_default", "controlnet_flux_inpaint"],
    # Kontext FP8 is the recommended Krita-aligned contextual editor; FLUX dev FP8 remains optional for img2img.
    "edit": ["diffusion_flux_kontext_fp8_scaled"],
}


def _krita_known_diffusion_basenames() -> frozenset[str]:
    from dreamforge_krita_recipes import EDIT_RECIPES

    names: set[str] = set()
    for blocks in EDIT_RECIPES.values():
        for ck in blocks.get("checkpoints", ()):
            if isinstance(ck, str) and ck.endswith(".safetensors"):
                names.add(Path(ck).name.lower())
    names.update(
        bn.lower()
        for bn in (
            "flux1-dev-kontext_fp8_scaled.safetensors",
        )
    )
    return frozenset(names)


_EDIT_RECIPE_BASE_NAMES = _krita_known_diffusion_basenames()


def studio_edit_flux_unet_present(models_root: Path | None = None) -> bool:
    """Any Krita-listed FLUX Kontext/dev UNET present on disk.

    Users may place large Flux weights under either `diffusion_models/` (Comfy-style)
    or `checkpoints/` (DreamForge-style). Either location is acceptable for Edit mode.
    """
    root = Path(models_root) if models_root is not None else MODELS_ROOT
    candidates: list[Path] = []
    dm = root / "diffusion_models"
    if dm.is_dir():
        candidates.append(dm)
    ckpt = root / "checkpoints"
    if ckpt.is_dir():
        candidates.append(ckpt)
    if not candidates:
        return False
    min_gb = int(900 * 1024 * 1024)
    for folder in candidates:
        for weight in folder.rglob("*.safetensors"):
            try:
                if weight.stat().st_size < min_gb:
                    continue
            except OSError:
                continue
            if weight.name.lower() in _EDIT_RECIPE_BASE_NAMES:
                return True
            stem = weight.stem.lower()
            if ("kontext" in stem or "flux1-fill" in stem or "flux.1-fill" in stem) and (
                "flux" in stem or "flux1" in stem
            ):
                return True
    return False


def resolve_upscaler(method: str | None) -> dict[str, Any]:
    """Map studio upscale_method / cn_upscale to a concrete upscaler filename."""
    key = (method or "fast_2x").strip()
    if key in UPSCALER_CATALOG:
        entry = dict(UPSCALER_CATALOG[key])
        entry["method"] = key
        return entry
    # Direct filename passthrough (gallery model or pathdb key)
    if key.endswith((".pth", ".safetensors", ".pt")):
        return {"method": key, "filename": key, "scale": None, "label": key}
    return {**UPSCALER_CATALOG["fast_2x"], "method": "fast_2x"}


def upscaler_path(method: str | None) -> Path | None:
    """Resolve upscaler file on disk, without downloading."""
    info = resolve_upscaler(method)
    filename = info["filename"]
    direct = MODELS_ROOT / "upscale_models" / filename
    if direct.is_file():
        return direct
    # Legacy pathdb / controlnet.json entry (4x-UltraSharp.pth)
    try:
        from shared import path_manager

        resolved = path_manager.get_file_path(filename)
        if resolved is not None:
            return Path(resolved)
    except Exception:
        pass
    return None


def _resource_entry(resource_id: str) -> dict[str, Any]:
    source = STUDIO_RESOURCE_SOURCES[resource_id]
    relative = source["relative"]
    path = MODELS_ROOT / relative
    return {
        "id": resource_id,
        "relative": relative,
        "expected_path": str(path),
        "url": source.get("url"),
        "min_bytes": source.get("min_bytes", 1024 * 1024),
        "optional": bool(source.get("optional")),
        "note": source.get("note", ""),
    }


def check_studio_resources(studio_mode: str, *, upscale_method: str | None = None) -> list[dict]:
    """Return missing downloadable assets for a studio tab."""
    mode = (studio_mode or "").lower()
    missing: list[dict] = []
    ids = list(STUDIO_MODE_RESOURCES.get(mode, []))
    if mode == "upscale":
        info = resolve_upscaler(upscale_method)
        filename = info["filename"]
        for rid, src in STUDIO_RESOURCE_SOURCES.items():
            if src["relative"].endswith(filename):
                if rid not in ids:
                    ids.append(rid)
    if mode == "edit" and studio_edit_flux_unet_present():
        return []
    for resource_id in ids:
        entry = _resource_entry(resource_id)
        if entry.get("optional"):
            continue
        req = {"id": entry["id"], "relative": entry["relative"]}
        if companion_file_present(req, min_bytes=int(entry.get("min_bytes", 1024 * 1024))):
            continue
        missing.append(entry)
    return missing


def preprocess_inpaint_mask(mask_img, *, grow: int = 4, feather: int = 4):
    """Grow and soften inpaint masks (Krita grow/feather defaults, simplified)."""
    from PIL import Image, ImageFilter

    if grow > 0:
        k = max(1, grow * 2 + 1)
        mask_img = mask_img.filter(ImageFilter.MaxFilter(k))
    if feather > 0:
        mask_img = mask_img.filter(ImageFilter.GaussianBlur(radius=max(1, feather // 2)))
    return mask_img


def inpaint_mask_recipe_values(edit_type: str = "inpaint") -> dict[str, int]:
    """Return grow/feather/mask_grow defaults from Krita edit recipes."""
    try:
        from dreamforge_krita_recipes import edit_recipe
    except ImportError:
        edit_recipe = None
    recipe = edit_recipe("", edit_type) if edit_recipe else None
    return {
        "inpaint_grow": int((recipe or {}).get("inpaint_grow", 4)),
        "inpaint_feather": int((recipe or {}).get("inpaint_feather", 4)),
        "inpaint_mask_grow_by": int((recipe or {}).get("inpaint_mask_grow_by", 20)),
    }


def prepare_inpaint_mask_bytes(
    mask_path: str | Path,
    *,
    image_size: tuple[int, int] | None = None,
    grow: int | None = None,
    feather: int | None = None,
) -> tuple[bytes, Any]:
    """Load, resize-to-image, grow/feather, and serialize an inpaint mask."""
    from io import BytesIO

    from PIL import Image

    recipe = inpaint_mask_recipe_values("inpaint")
    grow_v = int(recipe["inpaint_grow"] if grow is None else grow)
    feather_v = int(recipe["inpaint_feather"] if feather is None else feather)
    mask_img = Image.open(mask_path).convert("L")
    if image_size and mask_img.size != image_size:
        mask_img = mask_img.resize(image_size, Image.Resampling.LANCZOS)
    mask_img = preprocess_inpaint_mask(mask_img, grow=grow_v, feather=feather_v)
    buf = BytesIO()
    mask_img.save(buf, format="PNG")
    return buf.getvalue(), mask_img


def composite_inpaint_result(original, generated, mask_img):
    """Composite generated pixels back onto the source using a soft mask."""
    from PIL import Image

    base = original.convert("RGBA")
    over = generated.convert("RGBA")
    mask = mask_img.convert("L")
    if over.size != base.size:
        over = over.resize(base.size, Image.Resampling.LANCZOS)
    if mask.size != base.size:
        mask = mask.resize(base.size, Image.Resampling.LANCZOS)
    return Image.composite(over, base, mask).convert("RGB")


def stitch_kontext_reference_images(images: list[Any]):
    """Horizontally stitch reference images (Krita flux_k image_stitch behavior)."""
    from PIL import Image

    if not images:
        raise ValueError("stitch_kontext_reference_images requires at least one image")
    if len(images) == 1:
        return images[0].convert("RGB")
    target_h = max(im.height for im in images)
    resized = []
    for im in images:
        rgb = im.convert("RGB")
        if rgb.height != target_h:
            scale = target_h / max(1, rgb.height)
            rgb = rgb.resize(
                (max(1, int(rgb.width * scale)), target_h),
                Image.Resampling.LANCZOS,
            )
        resized.append(rgb)
    total_w = sum(im.width for im in resized)
    canvas = Image.new("RGB", (total_w, target_h))
    x = 0
    for im in resized:
        canvas.paste(im, (x, 0))
        x += im.width
    return canvas
