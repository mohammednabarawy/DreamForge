"""Named upscale presets for Enhance mode."""

from __future__ import annotations

from typing import Any

VALID_UPSCALE_PRESETS = frozenset({"1.5x", "2x", "faithful_2x", "fast_2x", "fast_4x", "detail_2x"})

UPSCALE_PRESET_PATCHES: dict[str, dict[str, Any]] = {
    "1.5x": {
        "upscale_by": 1.5,
        "upscale_denoise": 0.25,
        "upscale_tile_width": 1024,
        "upscale_tile_height": 1024,
        "steps": 20,
    },
    "2x": {
        "upscale_by": 2.0,
        "upscale_denoise": 0.25,
        "upscale_tile_width": 1024,
        "upscale_tile_height": 1024,
        "steps": 20,
    },
    "faithful_2x": {
        "upscale_by": 2.0,
        "upscale_denoise": 0.22,
        "upscale_tile_width": 1024,
        "upscale_tile_height": 1024,
        "upscale_tile_padding": 64,
        "steps": 20,
    },
    "fast_2x": {
        "upscale_by": 2.0,
        "upscale_denoise": 0.2,
        "upscale_tile_width": 768,
        "upscale_tile_height": 768,
        "steps": 12,
    },
    "fast_4x": {
        "upscale_by": 4.0,
        "upscale_denoise": 0.2,
        "upscale_tile_width": 1024,
        "upscale_tile_height": 1024,
        "upscale_tile_padding": 64,
        "steps": 4,
        "cfg": 8.0,
        "sampler_name": "euler",
        "scheduler": "normal",
    },
    "detail_2x": {
        "upscale_by": 2.0,
        "upscale_denoise": 0.33,
        "upscale_tile_width": 768,
        "upscale_tile_height": 768,
        "upscale_tile_padding": 128,
        "steps": 24,
    },
}


def normalize_upscale_preset(value: Any) -> str | None:
    key = str(value or "").strip().lower()
    return key if key in VALID_UPSCALE_PRESETS else None


def apply_upscale_preset_to_job(job) -> dict[str, Any]:
    """Return preset fields when upscale_preset is set (explicit job values win)."""
    preset_id = normalize_upscale_preset(getattr(job, "upscale_preset", None))
    if not preset_id:
        return {}
    patch = dict(UPSCALE_PRESET_PATCHES[preset_id])
    out: dict[str, Any] = {"upscale_preset": preset_id}
    for key, default in patch.items():
        attr = "cfg_scale" if key == "cfg" else "sampler" if key == "sampler_name" else key
        if getattr(job, attr, None) is None:
            out[attr] = default
    return out
