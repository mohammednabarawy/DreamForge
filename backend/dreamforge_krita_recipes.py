"""Krita AI Diffusion-derived edit recipes and dependency metadata.

Source inspiration: https://github.com/Acly/krita-ai-diffusion
Krita's working edit path is ComfyUI-first: architecture-specific recipes,
reference latents for edit models, and explicit dependency manifests.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


EDIT_RECIPES: dict[str, dict[str, Any]] = {
    "flux_kontext": {
        "name": "Flux Kontext",
        "checkpoints": [
            "svdq-fp4_r32-flux.1-kontext-dev.safetensors",
            "svdq-int4_r32-flux.1-kontext-dev.safetensors",
            "flux1-dev-kontext_fp8_scaled.safetensors",
            "flux1-kontext-dev-fp8-e4m3fn.safetensors",
            "flux1-kontext-dev.safetensors",
        ],
        "custom_steps": 20,
        "cfg": 3.5,
        "sampler_name": "euler",
        "scheduler": "simple",
        "clip_skip": 1,
        "edit_strength": 1.0,
        "live_steps": 8,
        "live_cfg": 3.5,
    },
    "flux_inpaint": {
        "name": "Flux Inpaint / Fill",
        "checkpoints": [
            "flux1-fill-dev",
            "flux fill",
            "flux.1-fill",
            "flux1-dev",
            "flux fill dev",
        ],
        "custom_steps": 20,
        "cfg": 30.0,
        "sampler_name": "euler",
        "scheduler": "simple",
        "clip_skip": 1,
        "edit_strength": 1.0,
        "inpaint_grow": 4,
        "inpaint_feather": 4,
        "inpaint_mask_grow_by": 20,
        "live_steps": 8,
        "live_cfg": 30.0,
    },
    "qwen_image_edit": {
        "name": "Qwen Edit",
        "checkpoints": [
            "Qwen-Image-Edit",
            "qwen_image_edit_2509_bf16.safetensors",
            "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
            "qwen_image_edit_bf16.safetensors",
            "qwen_image_edit_fp8_e4m3fn.safetensors",
            "Qwen_Image_Edit-Q5_1.gguf",
        ],
        "custom_steps": 20,
        "cfg": 2.5,
        "sampler_name": "euler",
        "scheduler": "beta",
        "clip_skip": 1,
        "edit_strength": 1.0,
        "qwen_image_shift": 3.1,
        "qwen_scale_megapixels": 1.0,
        "max_reference_images": 2,
        "live_steps": 10,
        "live_cfg": 1.0,
    },
}

GENERATION_RECIPES: dict[str, dict[str, Any]] = {
    "qwen_image": {
        "name": "Qwen Image",
        "checkpoints": [
            "qwen_image_fp8_e4m3fn.safetensors",
            "qwen_image_bf16.safetensors",
            "Qwen-Image",
        ],
        "custom_steps": 20,
        "cfg": 2.5,
        "sampler_name": "euler",
        "scheduler": "beta",
        "clip_skip": 1,
        "qwen_image_shift": 3.1,
        "live_steps": 6,
        "live_cfg": 1.8,
    },
}


# Pinned Comfy/custom-node SHAs aligned with Krita AI Diffusion 1.50.0 resources.py
COMFY_INSTALL_RECIPE: dict[str, Any] = {
    "comfy_url": "https://github.com/comfyanonymous/ComfyUI",
    "comfy_version": "025e6792ee64181ddce8a84411e0c7311e00b179",
    "krita_resources_version": "1.50.0",
    "required_custom_nodes": [
        {
            "id": "comfyui_controlnet_aux",
            "url": "https://github.com/Fannovel16/comfyui_controlnet_aux",
            "version": "83463c2e4b04e729268e57f638b4212e0da4badc",
            "nodes": ["InpaintPreprocessor", "DepthAnythingV2Preprocessor"],
        },
        {
            "id": "ComfyUI_IPAdapter_plus",
            "url": "https://github.com/cubiq/ComfyUI_IPAdapter_plus",
            "version": "b188a6cb39b512a9c6da7235b880af42c78ccd0d",
            "nodes": ["IPAdapterModelLoader", "IPAdapter"],
        },
        {
            "id": "comfyui-tooling-nodes",
            "url": "https://github.com/Acly/comfyui-tooling-nodes",
            "version": "a1e51904dec9a73b92865b512aa417f10938d608",
            "nodes": ["ETN_LoadImageCache", "ETN_SaveImageCache", "ETN_Translate"],
        },
        {
            "id": "comfyui-inpaint-nodes",
            "url": "https://github.com/Acly/comfyui-inpaint-nodes",
            "version": "12937559e1aea4bb073e9e82f915d1dab92f248b",
            "nodes": [
                "INPAINT_LoadFooocusInpaint",
                "INPAINT_ShrinkMask",
                "INPAINT_StabilizeMask",
                "INPAINT_ColorMatch",
            ],
        },
    ],
    "optional_custom_nodes": [
        {
            "id": "ComfyUI-GGUF",
            "url": "https://github.com/city96/ComfyUI-GGUF",
            "version": "01f8845bf30d89fff293c7bd50187bc59d9d53ea",
            "reason": "GGUF edit checkpoints such as Qwen Image Edit.",
        },
        {
            "id": "ComfyUI-nunchaku",
            "url": "https://github.com/nunchaku-tech/ComfyUI-nunchaku",
            "version": "90999af9c26e4a40927fb26c028ece8875ac25b3",
            "reason": "SVDQ/Nunchaku quantized Flux and Qwen edit checkpoints.",
        },
        {
            "id": "ComfyUI-Impact-Pack",
            "url": "https://github.com/ltdrdata/ComfyUI-Impact-Pack",
            "reason": "FaceDetailer and SAMLoader for optional face/hand detail repair.",
        },
        {
            "id": "ComfyUI-Impact-Subpack",
            "url": "https://github.com/ltdrdata/ComfyUI-Impact-Subpack",
            "reason": "UltralyticsDetectorProvider bbox/segm models for FaceDetailer.",
        },
    ],
}


def default_live_sampling_params() -> dict[str, Any]:
    """Krita Style live_sampler_steps / live_cfg_scale defaults for streaming runs."""
    from dreamforge_comfy_ws import DEFAULT_LIVE_SAMPLING

    return dict(DEFAULT_LIVE_SAMPLING)


def live_sampling_params(
    model_family: str,
    edit_type: str = "auto",
) -> dict[str, Any] | None:
    """Krita-style fast preview sampling (live_steps / live_cfg) for streaming runs."""
    recipe = edit_recipe(model_family, edit_type)
    if recipe and "live_steps" in recipe:
        return {
            "steps": int(recipe["live_steps"]),
            "cfg": float(recipe.get("live_cfg", recipe.get("cfg", 3.5))),
            "sampler_name": recipe.get("sampler_name"),
            "scheduler": recipe.get("scheduler"),
        }
    return default_live_sampling_params()


def edit_recipe(model_family: str, edit_type: str = "auto") -> dict[str, Any] | None:
    family = (model_family or "").lower()
    kind = (edit_type or "auto").lower()
    if kind == "inpaint":
        return deepcopy(EDIT_RECIPES["flux_inpaint"])
    # FLUX Kontext recipe only when the checkpoint family is Kontext — not for base FLUX img2img
    # (the UI labels generic edits as edit_type \"kontext\").
    if family == "flux_kontext":
        return deepcopy(EDIT_RECIPES["flux_kontext"])
    if family == "qwen_image_edit" or kind == "qwen_edit":
        return deepcopy(EDIT_RECIPES["qwen_image_edit"])
    return None


def generation_recipe(model_family: str) -> dict[str, Any] | None:
    family = (model_family or "").lower()
    if family == "qwen_image":
        return deepcopy(GENERATION_RECIPES["qwen_image"])
    return None


def resolve_qwen_edit_mode(
    *,
    model_family: str,
    requested: str | None,
    extra_reference_count: int,
) -> str:
    """Return 'single' or 'plus' for Qwen edit graph selection."""
    family = (model_family or "").lower()
    if family != "qwen_image_edit":
        return "single"
    mode = str(requested or "auto").lower()
    if mode == "plus":
        return "plus"
    if mode == "single":
        return "single"
    if extra_reference_count > 0:
        return "plus"
    return "single"


def qwen_model_params(
    model_family: str,
    *,
    edit_type: str = "auto",
    vram_profile: str | None = None,
) -> dict[str, Any]:
    """Merged Qwen defaults (edit or txt2img) with optional low-VRAM scale hints."""
    family = (model_family or "").lower()
    recipe = edit_recipe(family, edit_type) if family == "qwen_image_edit" else generation_recipe(family)
    if not recipe and family.startswith("qwen"):
        recipe = deepcopy(GENERATION_RECIPES.get("qwen_image", {}))
    out = dict(recipe or {})
    profile = str(vram_profile or "auto").lower()
    if profile in ("8gb", "5gb", "midvram", "lowvram"):
        out["qwen_scale_megapixels"] = 0.75 if profile in ("8gb", "midvram") else 0.55
    return out
