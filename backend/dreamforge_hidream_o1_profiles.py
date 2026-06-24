"""HiDream-O1-Image Dev performance profiles (DreamForge presets + official locks).

Official Dev default: 28 steps, CFG 1.0, LCM, no negative prompt.
Lightning (16) and Speed (22) are DreamForge preview presets; Quality matches official 28.
"""

from __future__ import annotations

from typing import Literal

PerformanceName = Literal["Lightning", "Speed", "Quality"]
Orientation = Literal["square", "portrait", "landscape"]

HIDREAM_O1_DEV_LOCKED = {
    "cfg": 1.0,
    "sampler_name": "lcm",
    "scheduler": "normal",
    "hidream_noise_scale": 7.6,
    "denoise": 1.0,
    "hidream_s_noise": 1.0,
    "hidream_s_noise_end": 1.0,
    "hidream_noise_clip_std": 2.5,
    "negative_prompt_enabled": False,
}

_HIDREAM_O1_DEV_PROFILES: dict[str, dict] = {
    "Lightning": {
        "custom_steps": 16,
        "prompt_refinement": False,
        "hidream_patch_seam_smoothing": False,
        "hidream_reference_megapixels": 1.0,
        "square": (1024, 1024),
        "portrait": (896, 1152),
        "landscape": (1152, 896),
    },
    "Speed": {
        "custom_steps": 22,
        "prompt_refinement": False,
        "hidream_patch_seam_smoothing": False,
        "hidream_reference_megapixels": 2.0,
        "square": (1536, 1536),
        "portrait": (1344, 1792),
        "landscape": (1792, 1344),
    },
    "Quality": {
        "custom_steps": 28,
        "prompt_refinement": True,
        "hidream_patch_seam_smoothing": True,
        "hidream_reference_megapixels": 4.0,
        "square": (2048, 2048),
        "portrait": (1728, 2304),
        "landscape": (2304, 1728),
    },
}


def is_hidream_o1_dev_checkpoint(model_name: str) -> bool:
    """Repackaged HiDream-O1-Image Dev / mxfp8 / fp8 checkpoints."""
    name = (model_name or "").lower()
    if "hidream" not in name or "o1" not in name:
        return False
    if "fast" in name:
        return False
    if "full" in name and "dev" not in name:
        return False
    return any(token in name for token in ("dev", "mxfp8", "fp8", "distill", "2604", "o1"))


def classify_aspect_orientation(aspect_ratio: str | None, width: int | None, height: int | None) -> Orientation:
    text = (aspect_ratio or "").lower().replace("×", "x").replace(" ", "")
    if "x" in text:
        parts = text.split("x", 1)
        try:
            w, h = int(parts[0]), int(parts[1])
            if w == h:
                return "square"
            return "portrait" if h > w else "landscape"
        except ValueError:
            pass
    if width and height:
        if width == height:
            return "square"
        return "portrait" if height > width else "landscape"
    return "square"


def hidream_o1_dev_resolution(
    performance: str,
    *,
    aspect_ratio: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> tuple[int, int]:
    perf = performance if performance in _HIDREAM_O1_DEV_PROFILES else "Speed"
    orient = classify_aspect_orientation(aspect_ratio, width, height)
    profile = _HIDREAM_O1_DEV_PROFILES[perf]
    return profile[orient]


def hidream_o1_dev_family_options(performance: str) -> dict:
    """Sampling + O1 extras for model_ui_defaults / submit guards."""
    perf = performance if performance in _HIDREAM_O1_DEV_PROFILES else "Speed"
    profile = _HIDREAM_O1_DEV_PROFILES[perf]
    return {
        "custom_steps": profile["custom_steps"],
        "cfg": HIDREAM_O1_DEV_LOCKED["cfg"],
        "sampler_name": HIDREAM_O1_DEV_LOCKED["sampler_name"],
        "scheduler": HIDREAM_O1_DEV_LOCKED["scheduler"],
        "clip_skip": 1,
        "hidream_noise_scale": HIDREAM_O1_DEV_LOCKED["hidream_noise_scale"],
        "denoise": HIDREAM_O1_DEV_LOCKED["denoise"],
        "hidream_s_noise": HIDREAM_O1_DEV_LOCKED["hidream_s_noise"],
        "hidream_s_noise_end": HIDREAM_O1_DEV_LOCKED["hidream_s_noise_end"],
        "hidream_noise_clip_std": HIDREAM_O1_DEV_LOCKED["hidream_noise_clip_std"],
        "hidream_patch_seam_smoothing": profile["hidream_patch_seam_smoothing"],
        "hidream_reference_megapixels": profile["hidream_reference_megapixels"],
        "hidream_prompt_refinement": profile["prompt_refinement"],
    }


def finalize_hidream_generation_settings(
    settings: dict,
    model: dict,
    job,
) -> dict:
    """Last-chance HiDream profile enforcement before ComfyUI workflow build."""
    family = str((model or {}).get("family") or "").lower()
    if family not in ("hidream", "hidream_o1"):
        return settings
    model_name = str(
        (model or {}).get("name")
        or (model or {}).get("engine_name")
        or getattr(job, "model", "")
        or settings.get("base_model", "")
        or ""
    )
    perf = (
        getattr(job, "performance", None)
        or settings.get("performance_selection")
        or settings.get("performance")
    )
    from modules.model_ui_defaults import apply_hidream_sampling_at_submit

    return apply_hidream_sampling_at_submit(
        settings,
        model_name,
        family,
        performance=perf,
    )


def hidream_o1_manifest_warnings(model_name: str, settings: dict) -> list[str]:
    """Surface profile drift in generation manifests."""
    if not is_hidream_o1_dev_checkpoint(model_name):
        return []
    perf = str(
        settings.get("performance_selection")
        or settings.get("performance")
        or "Speed"
    ).strip()
    if perf in ("Custom...", "Custom"):
        return []
    expected = apply_hidream_o1_dev_at_submit(
        {},
        model_name,
        performance=perf,
    )
    warnings: list[str] = []
    checks = (
        ("cfg", "cfg"),
        ("steps", "steps"),
        ("sampler_name", "sampler_name"),
        ("width", "width"),
        ("height", "height"),
    )
    for key, exp_key in checks:
        actual = settings.get(key)
        want = expected.get(exp_key)
        if want is not None and actual is not None and actual != want:
            warnings.append(f"hidream_o1_{key}_expected_{want}_got_{actual}")
    return warnings


def apply_hidream_o1_dev_at_submit(
    settings: dict,
    model_name: str,
    *,
    performance: str | None = None,
) -> dict:
    if not is_hidream_o1_dev_checkpoint(model_name):
        return settings

    out = dict(settings)
    perf = str(
        performance
        or out.get("performance_selection")
        or out.get("performance")
        or "Speed"
    ).strip()
    if perf in ("Custom...", "Custom"):
        out["cfg"] = float(out.get("cfg") or HIDREAM_O1_DEV_LOCKED["cfg"])
        if out["cfg"] > 1.5:
            out["cfg"] = HIDREAM_O1_DEV_LOCKED["cfg"]
        out["negative"] = ""
        out["sampler_name"] = out.get("sampler_name") or HIDREAM_O1_DEV_LOCKED["sampler_name"]
        out["scheduler"] = out.get("scheduler") or HIDREAM_O1_DEV_LOCKED["scheduler"]
        return out

    opts = hidream_o1_dev_family_options(perf)
    w, h = hidream_o1_dev_resolution(
        perf,
        aspect_ratio=out.get("aspect_ratio"),
        width=out.get("width"),
        height=out.get("height"),
    )
    out.update(opts)
    out["steps"] = int(opts["custom_steps"])
    out["width"] = w
    out["height"] = h
    out["aspect_ratio"] = f"{w}x{h}"
    out["performance_selection"] = perf
    out["negative"] = ""
    if out.get("styles"):
        out["styles"] = []
    if not opts.get("hidream_prompt_refinement"):
        out["prompt_enhancer"] = "none"
    else:
        out["prompt_enhancer"] = str(out.get("prompt_enhancer") or "hyperprompt")
    return out
