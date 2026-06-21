"""Recommended Ultimate SD Upscale defaults (ComfyUI community workflows).

SDXL checkpoints, 1024×1024 tiles, Chess mode, ~25% denoise — see
ViewComfy / Lily's Ultimate SD Upscale guides.
"""

from __future__ import annotations

from typing import Any, Mapping

UPSCALE_METHOD = "ultimate_sd_upscale"
UPSCALE_BY = 2.0
UPSCALE_DENOISE = 0.25
UPSCALE_TILE_WIDTH = 1024
UPSCALE_TILE_HEIGHT = 1024
UPSCALE_TILE_PADDING = 64
UPSCALE_MASK_BLUR = 8
UPSCALE_SEAM_FIX_MODE = "None"
UPSCALE_MODE_TYPE = "Chess"
UPSCALE_FORCE_UNIFORM_TILES = True
UPSCALE_STEPS = 20
UPSCALE_CFG = 6.0
UPSCALE_SAMPLER = "euler"
UPSCALE_SCHEDULER = "normal"


def _pick(src: Mapping[str, Any], key: str, default: Any) -> Any:
    val = src.get(key)
    return default if val is None else val


def upscale_field_defaults(data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return upscale kwargs with community-recommended fallbacks."""
    src = data or {}
    return {
        "upscale_method": _pick(src, "upscale_method", UPSCALE_METHOD),
        "upscale_by": float(_pick(src, "upscale_by", UPSCALE_BY)),
        "upscale_denoise": float(_pick(src, "upscale_denoise", UPSCALE_DENOISE)),
        "upscale_tile_width": int(_pick(src, "upscale_tile_width", UPSCALE_TILE_WIDTH)),
        "upscale_tile_height": int(_pick(src, "upscale_tile_height", UPSCALE_TILE_HEIGHT)),
        "upscale_tile_padding": int(_pick(src, "upscale_tile_padding", UPSCALE_TILE_PADDING)),
        "upscale_mask_blur": int(_pick(src, "upscale_mask_blur", UPSCALE_MASK_BLUR)),
        "upscale_seam_fix_mode": str(_pick(src, "upscale_seam_fix_mode", UPSCALE_SEAM_FIX_MODE)),
        "upscale_mode_type": str(_pick(src, "upscale_mode_type", UPSCALE_MODE_TYPE)),
        "upscale_force_uniform_tiles": bool(
            _pick(src, "upscale_force_uniform_tiles", UPSCALE_FORCE_UNIFORM_TILES)
        ),
        "steps": int(_pick(src, "steps", UPSCALE_STEPS)),
        "cfg": float(_pick(src, "cfg", _pick(src, "cfg_scale", UPSCALE_CFG))),
        "sampler_name": str(_pick(src, "sampler_name", _pick(src, "sampler", UPSCALE_SAMPLER))),
        "scheduler": str(_pick(src, "scheduler", UPSCALE_SCHEDULER)),
    }
