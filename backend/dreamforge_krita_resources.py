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
    "ultimate_sd_upscale": {
        "filename": "4x-UltraSharp.pth",
        "scale": 2,
        "label": "Ultimate SD Upscale",
        "workflow": "ultimate_sd",
    },
    "default": {
        "filename": "4x-UltraSharp.pth",
        "scale": 2,
        "label": "Ultimate SD Upscale",
        "workflow": "ultimate_sd",
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
    "pid_flux1_4k": {
        "filename": "pid_flux1_1024_to_4096_4step_mxfp8.safetensors",
        "scale": 4,
        "label": "PiD / PixelDiT 4K (consumer mxfp8)",
        "workflow": "pid_flux",
    },
    "pid_flux1_4k_bf16": {
        "filename": "pid_flux1_1024_to_4096_4step_bf16.safetensors",
        "scale": 4,
        "label": "PiD / PixelDiT 4K bf16 (reference / high VRAM)",
        "workflow": "pid_flux",
    },
    "pid_flux1_4k_mxfp8": {
        "filename": "pid_flux1_1024_to_4096_4step_mxfp8.safetensors",
        "scale": 4,
        "label": "PiD / PixelDiT 4K mxfp8 (consumer)",
        "workflow": "pid_flux",
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
    "diffusion_flux_fill_dev": {
        "relative": "diffusion_models/flux1-fill-dev-fp8.safetensors",
        "url": (
            "https://huggingface.co/1038lab/FLUX.1-Fill-dev_fp8/resolve/main/"
            "FLUX.1-Fill-dev_fp8.safetensors"
        ),
        "min_bytes": 10 * 1024 * 1024 * 1024,
        "note": "FLUX.1 Fill dev FP8 — default inpaint checkpoint (~12 GB, VRAM-friendly)",
    },
    "diffusion_qwen_edit_2511_q4": {
        "relative": "diffusion_models/qwen-image-edit-2511-Q4_K_M.gguf",
        "url": (
            "https://huggingface.co/unsloth/Qwen-Image-Edit-2511-GGUF/resolve/main/"
            "qwen-image-edit-2511-Q4_K_M.gguf"
        ),
        "min_bytes": 10 * 1024 * 1024 * 1024,
        "note": "Qwen Image Edit 2511 Q4_K_M — default edit checkpoint (GGUF)",
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
        "min_bytes": 512 * 1024,
    },
    "upscaler_omnisr_3x": {
        "relative": "upscale_models/OmniSR_X3_DIV2K.safetensors",
        "url": "https://huggingface.co/Acly/Omni-SR/resolve/main/OmniSR_X3_DIV2K.safetensors",
        "min_bytes": 512 * 1024,
    },
    "upscaler_omnisr_4x": {
        "relative": "upscale_models/OmniSR_X4_DIV2K.safetensors",
        "url": "https://huggingface.co/Acly/Omni-SR/resolve/main/OmniSR_X4_DIV2K.safetensors",
        "min_bytes": 512 * 1024,
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
    },
    "pid_flux1_4k_model": {
        "relative": "diffusion_models/pid_flux1_1024_to_4096_4step_mxfp8.safetensors",
        "url": (
            "https://huggingface.co/Comfy-Org/PixelDiT/resolve/main/"
            "diffusion_models/pid_flux1_1024_to_4096_4step_mxfp8.safetensors"
        ),
        "min_bytes": 1400 * 1024 * 1024,
        "note": "PiD Flux.1 1024→4096 4-step mxfp8 upscaler checkpoint.",
    },
    "pid_flux1_4k_model_bf16": {
        "relative": "diffusion_models/pid_flux1_1024_to_4096_4step_bf16.safetensors",
        "url": (
            "https://huggingface.co/Comfy-Org/PixelDiT/resolve/main/"
            "diffusion_models/pid_flux1_1024_to_4096_4step_bf16.safetensors"
        ),
        "min_bytes": 2500 * 1024 * 1024,
        "note": "PiD Flux.1 1024→4096 4-step bf16 upscaler checkpoint.",
    },
    "pid_gemma2_text_encoder": {
        "relative": "text_encoders/gemma_2_2b_it_elm_fp8_scaled.safetensors",
        "url": (
            "https://huggingface.co/Comfy-Org/PixelDiT/resolve/main/"
            "text_encoders/gemma_2_2b_it_elm_fp8_scaled.safetensors"
        ),
        "min_bytes": 2400 * 1024 * 1024,
        "note": "Gemma 2 2B ELM text encoder for CLIPLoader type pixeldit.",
    },
    "pid_gemma2_text_encoder_bf16": {
        "relative": "text_encoders/gemma_2_2b_it_elm_bf16.safetensors",
        "url": (
            "https://huggingface.co/Comfy-Org/PixelDiT/resolve/main/"
            "text_encoders/gemma_2_2b_it_elm_bf16.safetensors"
        ),
        "min_bytes": 5000 * 1024 * 1024,
        "note": "BF16 Gemma 2 2B ELM text encoder for high-VRAM/reference PiD workflows.",
    },
    "pid_flux_vae_bf16": {
        "relative": "vae/flux-vae-bf16.safetensors",
        "url": "https://huggingface.co/Kijai/flux-fp8/resolve/main/flux-vae-bf16.safetensors",
        "min_bytes": 150 * 1024 * 1024,
        "note": "Flux VAE used to encode the source image before PiD conditioning.",
    },
    "z_image_turbo_nvfp4": {
        "relative": "diffusion_models/z_image_turbo_nvfp4.safetensors",
        "url": (
            "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/"
            "split_files/diffusion_models/z_image_turbo_nvfp4.safetensors"
        ),
        "min_bytes": 4200 * 1024 * 1024,
        "note": "Consumer Z-Image Turbo diffusion model from Comfy-Org split files.",
    },
    "z_image_turbo_bf16": {
        "relative": "diffusion_models/z_image_turbo_bf16.safetensors",
        "url": (
            "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/"
            "split_files/diffusion_models/z_image_turbo_bf16.safetensors"
        ),
        "min_bytes": 11000 * 1024 * 1024,
        "note": "BF16 Z-Image Turbo diffusion model; high VRAM/reference option.",
        "optional": True,
    },
    "z_image_qwen3_4b_fp4": {
        "relative": "text_encoders/qwen_3_4b_fp4_mixed.safetensors",
        "url": (
            "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/"
            "split_files/text_encoders/qwen_3_4b_fp4_mixed.safetensors"
        ),
        "min_bytes": 3200 * 1024 * 1024,
        "note": "Consumer Qwen 3 4B FP4 mixed text encoder for Z-Image Turbo.",
    },
    "z_image_qwen3_4b_fp8": {
        "relative": "text_encoders/qwen_3_4b_fp8_mixed.safetensors",
        "url": (
            "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/"
            "split_files/text_encoders/qwen_3_4b_fp8_mixed.safetensors"
        ),
        "min_bytes": 5200 * 1024 * 1024,
        "note": "Qwen 3 4B FP8 mixed text encoder for Z-Image Turbo.",
        "optional": True,
    },
    "z_image_ae_vae": {
        "relative": "vae/ae.safetensors",
        "url": (
            "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/"
            "split_files/vae/ae.safetensors"
        ),
        "min_bytes": 300 * 1024 * 1024,
        "note": "Official AE VAE for Z-Image Turbo split-file workflows.",
    },
    **KRITA_DOWNLOADABLE_DIFFUSION,
}

STUDIO_MODE_RESOURCES: dict[str, list[str]] = {
    # Upscale uses `_resource_ids_for_studio_mode` (method-specific upscaler only).
    "upscale": [],
    "inpaint": ["diffusion_flux_fill_dev"],
    "edit": ["diffusion_flux_kontext_fp8_scaled"],
}

STUDIO_MODE_DEFAULTS: dict[str, dict[str, str]] = {
    "inpaint": {
        "family": "flux_fill",
        "model_name": "flux1-fill-dev-fp8.safetensors",
    },
    "edit": {
        "family": "flux_kontext",
        "model_name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "performance": "Lightning",
    },
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
            "flux1-fill-dev.safetensors",
            "flux1-fill-dev-fp8.safetensors",
            "flux-fill-dev.safetensors",
            "qwen-image-edit-2511-Q4_K_M.gguf",
            "Qwen-Image-Edit-2511-Q4_K_M.gguf",
        )
    )
    return frozenset(names)


_FILL_CHECKPOINT_NAMES = frozenset(
    {
        "flux1-fill-dev.safetensors",
        "flux1-fill-dev-fp8.safetensors",
        "flux-fill-dev.safetensors",
        "flux.1-fill-dev_fp8.safetensors",
    }
)


def _scan_diffusion_folders(
    models_root: Path | None,
    *,
    min_bytes: int,
    name_predicate,
) -> bool:
    root = Path(models_root) if models_root is not None else MODELS_ROOT
    candidates: list[Path] = []
    for sub in ("diffusion_models", "checkpoints", "unet"):
        folder = root / sub
        if folder.is_dir():
            candidates.append(folder)
    if not candidates:
        return False
    for folder in candidates:
        for weight in folder.rglob("*"):
            if weight.suffix.lower() not in (".safetensors", ".gguf", ".pt", ".pth"):
                continue
            try:
                if weight.stat().st_size < min_bytes:
                    continue
            except OSError:
                continue
            low = weight.name.lower()
            stem = weight.stem.lower()
            if name_predicate(low, stem):
                return True
    return False


def studio_inpaint_flux_fill_present(models_root: Path | None = None) -> bool:
    """True when a Flux Fill diffusion checkpoint is on disk."""
    min_bytes = int(8 * 1024 * 1024 * 1024)

    def _match(low: str, stem: str) -> bool:
        if low in _FILL_CHECKPOINT_NAMES:
            return True
        if ("flux1-fill" in stem or "flux-fill" in stem or "flux.1-fill" in stem) and "flux" in stem:
            return True
        return False

    return _scan_diffusion_folders(models_root, min_bytes=min_bytes, name_predicate=_match)


def studio_edit_qwen_gguf_present(models_root: Path | None = None) -> bool:
    """True when a Qwen Image Edit GGUF checkpoint is on disk."""
    min_bytes = int(8 * 1024 * 1024 * 1024)

    def _match(low: str, stem: str) -> bool:
        if low.endswith(".gguf") and "qwen" in stem and "edit" in stem:
            return True
        return False

    return _scan_diffusion_folders(models_root, min_bytes=min_bytes, name_predicate=_match)


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


PID_FLUX_COMPANION_IDS: dict[str, list[str]] = {
    "pid_flux1_4k": [
        "pid_flux1_4k_model",
        "pid_gemma2_text_encoder",
        "pid_flux_vae_bf16",
    ],
    "pid_flux1_4k_mxfp8": [
        "pid_flux1_4k_model",
        "pid_gemma2_text_encoder",
        "pid_flux_vae_bf16",
    ],
    "pid_flux1_4k_bf16": [
        "pid_flux1_4k_model_bf16",
        "pid_gemma2_text_encoder_bf16",
        "pid_flux_vae_bf16",
    ],
}

_BASIC_UPSCALE_METHODS = frozenset(
    {"fast_2x", "fast_3x", "fast_4x", "quality", "sharp", "2x", "4x"}
)


def _catalog_upscaler_entry(key: str) -> dict[str, Any] | None:
    if key in UPSCALER_CATALOG:
        return dict(UPSCALER_CATALOG[key])
    lowered = key.lower()
    for catalog_key, entry in UPSCALER_CATALOG.items():
        if catalog_key.lower() == lowered:
            return dict(entry)
    return None


def resolve_upscaler(method: str | None) -> dict[str, Any]:
    """Map studio upscale_method / cn_upscale to a concrete upscaler filename."""
    key = (method or "ultimate_sd_upscale").strip()
    # Direct filename passthrough (gallery model or pathdb key)
    if key.endswith((".pth", ".safetensors", ".pt")):
        basename = Path(key).name
        lowered = key.lower()
        if "pid_flux" in lowered or "pixeldit" in lowered:
            base = dict(UPSCALER_CATALOG["pid_flux1_4k_mxfp8"])
            base["method"] = key
            base["filename"] = basename
            base["workflow"] = "pid_flux"
            base["label"] = f"PiD / PixelDiT 4K ({basename})"
            return base
        entry = dict(UPSCALER_CATALOG["ultimate_sd_upscale"])
        entry["method"] = key
        entry["filename"] = basename
        entry["workflow"] = "ultimate_sd"
        entry["label"] = f"Ultimate SD Upscale ({basename})"
        return entry

    entry = _catalog_upscaler_entry(key)
    if entry is None:
        fallback = dict(UPSCALER_CATALOG["ultimate_sd_upscale"])
        fallback["method"] = "ultimate_sd_upscale"
        fallback["workflow"] = "ultimate_sd"
        return fallback

    catalog_key = key
    if catalog_key not in UPSCALER_CATALOG:
        for catalog_key_candidate in UPSCALER_CATALOG:
            if catalog_key_candidate.lower() == key.lower():
                catalog_key = catalog_key_candidate
                break
    entry["method"] = catalog_key
    if "workflow" not in entry:
        if catalog_key in _BASIC_UPSCALE_METHODS:
            entry["workflow"] = "basic"
        else:
            entry["workflow"] = "ultimate_sd"
    return entry


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
        "requires_hf_token": bool(source.get("requires_hf_token")),
    }


def _merge_mode_companion_missing(missing: list[dict], mode: str) -> None:
    """Append CLIP/VAE/LoRA companions for the studio mode's default model family."""
    defaults = STUDIO_MODE_DEFAULTS.get(mode)
    if not defaults:
        return
    from dreamforge_cli_inventory import check_model_dependencies
    from dreamforge_companion_download import enrich_missing_dependency

    seen = {m.get("id") for m in missing if m.get("id")}
    synthetic = {
        "family": defaults["family"],
        "name": defaults["model_name"],
    }
    performance = defaults.get("performance")
    for item in check_model_dependencies(synthetic, performance=performance):
        rid = item.get("id")
        if not rid or rid in seen:
            continue
        missing.append(enrich_missing_dependency(item))
        seen.add(rid)


def _resource_ids_for_studio_mode(
    mode: str,
    *,
    upscale_method: str | None = None,
) -> list[str]:
    """Return studio resource ids required for a mode (upscale = selected upscaler only)."""
    key = (mode or "").lower()
    if key == "upscale":
        info = resolve_upscaler(upscale_method)
        if info.get("workflow") == "pid_flux":
            method_key = str(info.get("method") or "pid_flux1_4k").lower()
            return list(
                PID_FLUX_COMPANION_IDS.get(method_key)
                or PID_FLUX_COMPANION_IDS["pid_flux1_4k"]
            )
        filename = info["filename"]
        ids: list[str] = []
        for rid, src in STUDIO_RESOURCE_SOURCES.items():
            if str(src.get("relative") or "").endswith(filename):
                ids.append(rid)
        return ids
    return list(STUDIO_MODE_RESOURCES.get(key, []))


def check_studio_resources(studio_mode: str, *, upscale_method: str | None = None) -> list[dict]:
    """Return missing downloadable assets for a studio tab."""
    mode = (studio_mode or "").lower()
    missing: list[dict] = []
    ids = _resource_ids_for_studio_mode(mode, upscale_method=upscale_method)
    if mode == "inpaint" and studio_inpaint_flux_fill_present():
        ids = [rid for rid in ids if rid != "diffusion_flux_fill_dev"]
    elif mode == "edit" and studio_edit_flux_unet_present():
        ids = [rid for rid in ids if rid != "diffusion_flux_kontext_fp8_scaled"]
    for resource_id in ids:
        entry = _resource_entry(resource_id)
        if entry.get("optional"):
            continue
        req = {"id": entry["id"], "relative": entry["relative"]}
        if companion_file_present(req, min_bytes=int(entry.get("min_bytes", 1024 * 1024))):
            continue
        missing.append(entry)
    if mode in STUDIO_MODE_DEFAULTS:
        _merge_mode_companion_missing(missing, mode)
    return missing


def check_image_prompt_resources() -> list[dict]:
    """Missing IP-Adapter + CLIP-Vision assets for Create image-prompt guidance."""
    missing: list[dict] = []
    for resource_id in ("ipadapter_sdxl_vith", "clip_vision_ipadapter_vith"):
        entry = STUDIO_RESOURCE_SOURCES.get(resource_id)
        if not entry:
            continue
        item = {"id": resource_id, **entry}
        if companion_file_present(
            {"id": resource_id, "relative": entry["relative"]},
            min_bytes=int(entry.get("min_bytes", 1024 * 1024)),
        ):
            continue
        missing.append(item)
    return missing


def preprocess_inpaint_mask(mask_img, *, grow: int = 4, feather: int = 4, hard: bool = False):
    """Grow and soften inpaint masks (Krita grow/feather defaults, simplified)."""
    from PIL import Image, ImageFilter

    if grow > 0:
        k = max(1, grow * 2 + 1)
        mask_img = mask_img.filter(ImageFilter.MaxFilter(k))
    if not hard and feather > 0:
        mask_img = mask_img.filter(ImageFilter.GaussianBlur(radius=max(1, feather // 2)))
    return mask_img


INPAINT_CROP_STITCH_MAX_SIDE = 1536
INPAINT_CROP_STITCH_MAX_PIXELS = 1536 * 1536
INPAINT_CROP_MIN_MARGIN = 64


def mask_bounding_box(mask_img, *, threshold: int = 8) -> tuple[int, int, int, int] | None:
    """Return (left, upper, right, lower) for mask pixels above threshold."""
    binary = mask_img.convert("L").point(lambda p: 255 if p > threshold else 0)
    return binary.getbbox()


def _snap_dimension(value: int, *, align: int = 8) -> int:
    if value <= 0:
        return align
    return max(align, ((value + align - 1) // align) * align)


def plan_inpaint_crop_stitch(
    image,
    mask_img,
    *,
    max_side: int = INPAINT_CROP_STITCH_MAX_SIDE,
    max_pixels: int = INPAINT_CROP_STITCH_MAX_PIXELS,
    margin: int = INPAINT_CROP_MIN_MARGIN,
    grow: int = 0,
    feather: int = 0,
) -> dict[str, Any] | None:
    """Crop a masked region for faster inpaint when the source image is large."""
    from PIL import Image

    width, height = image.size
    if max(width, height) <= max_side and width * height <= max_pixels:
        return None
    bbox = mask_bounding_box(mask_img)
    if not bbox:
        return None
    pad = int(margin) + int(grow) + int(feather) + 16
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(width, x1 + pad)
    y1 = min(height, y1 + pad)
    crop_w = x1 - x0
    crop_h = y1 - y0
    if crop_w <= 0 or crop_h <= 0:
        return None
    if crop_w * crop_h >= int(width * height * 0.92):
        return None
    crop_w = min(width - x0, _snap_dimension(crop_w))
    crop_h = min(height - y0, _snap_dimension(crop_h))
    x1 = min(width, x0 + crop_w)
    y1 = min(height, y0 + crop_h)
    box = (x0, y0, x1, y1)
    base = image.convert("RGB")
    mask = mask_img.convert("L")
    return {
        "box": box,
        "crop_image": base.crop(box),
        "crop_mask": mask.crop(box),
    }


def inpaint_mask_has_selection(mask_img, *, threshold: int = 8) -> bool:
    """Return whether an inpaint mask contains any selected pixels."""
    return mask_bounding_box(mask_img, threshold=threshold) is not None


def describe_inpaint_context(
    image,
    mask_img,
    *,
    grow: int = 0,
    feather: int = 0,
    hard: bool = False,
    threshold: int = 8,
) -> dict[str, Any]:
    """Summarize inpaint mask/crop state for dry-run and diagnostics."""
    width, height = image.size
    mask = mask_img.convert("L")
    if mask.size != image.size:
        from PIL import Image

        mask = mask.resize(image.size, Image.Resampling.LANCZOS)

    mask_data = getattr(mask, "get_flattened_data", mask.getdata)()
    selected_pixels = sum(1 for pixel in mask_data if int(pixel) > int(threshold))
    bbox = mask_bounding_box(mask, threshold=threshold)
    crop_plan = plan_inpaint_crop_stitch(
        image,
        mask,
        grow=int(grow),
        feather=0 if hard else int(feather),
    )
    crop = {"enabled": False}
    if crop_plan:
        x0, y0, x1, y1 = crop_plan["box"]
        crop = {
            "enabled": True,
            "box": [x0, y0, x1, y1],
            "size": [x1 - x0, y1 - y0],
        }
    return {
        "schema_version": "1.0",
        "image_size": [width, height],
        "mask_size": [mask.width, mask.height],
        "mask_empty": bbox is None,
        "mask_bbox": list(bbox) if bbox else None,
        "mask_selected_pixels": selected_pixels,
        "mask_coverage": selected_pixels / max(1, width * height),
        "mask_threshold": int(threshold),
        "mask_grow": int(grow),
        "mask_feather": 0 if hard else int(feather),
        "hard_mask": bool(hard),
        "crop": crop,
    }


def stitch_inpaint_crop(full_image, crop_image, box: tuple[int, int, int, int]):
    """Paste an inpainted crop back into the full-resolution source image."""
    from PIL import Image

    x0, y0, x1, y1 = box
    result = full_image.convert("RGB").copy()
    patch = crop_image.convert("RGB")
    target_size = (x1 - x0, y1 - y0)
    if patch.size != target_size:
        patch = patch.resize(target_size, Image.Resampling.LANCZOS)
    result.paste(patch, (x0, y0))
    return result


def pil_png_bytes(image) -> bytes:
    from io import BytesIO

    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


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
    hard: bool = False,
) -> tuple[bytes, Any]:
    """Load, resize-to-image, grow/feather, and serialize an inpaint mask."""
    from io import BytesIO

    from PIL import Image

    recipe = inpaint_mask_recipe_values("inpaint")
    grow_v = int(recipe["inpaint_grow"] if grow is None else grow)
    feather_v = 0 if hard else int(recipe["inpaint_feather"] if feather is None else feather)
    mask_img = Image.open(mask_path).convert("L")
    if image_size and mask_img.size != image_size:
        mask_img = mask_img.resize(image_size, Image.Resampling.LANCZOS)
    mask_img = preprocess_inpaint_mask(mask_img, grow=grow_v, feather=feather_v, hard=hard)
    buf = BytesIO()
    mask_img.save(buf, format="PNG")
    return buf.getvalue(), mask_img


def prepare_inpaint_mask_image(
    mask_img,
    *,
    grow: int | None = None,
    feather: int | None = None,
    hard: bool = False,
) -> tuple[bytes, Any]:
    """Grow/feather an in-memory mask image and return PNG bytes + processed image."""
    from io import BytesIO

    recipe = inpaint_mask_recipe_values("inpaint")
    grow_v = int(recipe["inpaint_grow"] if grow is None else grow)
    feather_v = 0 if hard else int(recipe["inpaint_feather"] if feather is None else feather)
    processed = preprocess_inpaint_mask(
        mask_img.convert("L"),
        grow=grow_v,
        feather=feather_v,
        hard=hard,
    )
    buf = BytesIO()
    processed.save(buf, format="PNG")
    return buf.getvalue(), processed


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


def measure_inpaint_outside_mask_leakage(
    original,
    generated,
    mask_img,
    *,
    binary_threshold: int = 128,
    tolerance: int = 3,
    edge_band: int = 2,
) -> dict[str, Any]:
    """Measure how much generated output changed pixels outside the edit mask.

    Pixels within ``edge_band`` of the binary mask edge are excluded so feathered
    compositing boundaries do not count as leakage.
    """
    from PIL import Image, ImageFilter

    base = original.convert("RGB")
    over = generated.convert("RGB")
    if over.size != base.size:
        over = over.resize(base.size, Image.Resampling.LANCZOS)
    mask = mask_img.convert("L")
    if mask.size != base.size:
        mask = mask.resize(base.size, Image.Resampling.LANCZOS)

    binary = mask.point(lambda p: 255 if int(p) > binary_threshold else 0)
    if edge_band > 0:
        k = max(3, edge_band * 2 + 1)
        edge = binary.filter(ImageFilter.MaxFilter(k))
        outside = binary.point(lambda p: 0 if int(p) > 0 else 255)
        outside = Image.composite(
            Image.new("L", binary.size, 0),
            outside,
            edge.point(lambda p: 0 if int(p) > 0 else 255),
        )
    else:
        outside = binary.point(lambda p: 255 if int(p) == 0 else 0)

    base_px = list(getattr(base, "get_flattened_data", base.getdata)())
    over_px = list(getattr(over, "get_flattened_data", over.getdata)())
    outside_px = list(getattr(outside, "get_flattened_data", outside.getdata)())
    outside_count = 0
    changed_count = 0
    max_delta = 0
    for idx, keep in enumerate(outside_px):
        if int(keep) < 128:
            continue
        outside_count += 1
        br, bg, bb = base_px[idx]
        or_, og, ob = over_px[idx]
        delta = max(abs(br - or_), abs(bg - og), abs(bb - ob))
        max_delta = max(max_delta, delta)
        if delta > tolerance:
            changed_count += 1
    leakage_ratio = changed_count / max(1, outside_count)
    return {
        "outside_pixels": outside_count,
        "changed_pixels": changed_count,
        "max_channel_delta": max_delta,
        "leakage_ratio": leakage_ratio,
        "tolerance": tolerance,
        "edge_band": edge_band,
        "ok": changed_count == 0,
    }


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
