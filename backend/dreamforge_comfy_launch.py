"""Hardware-aware ComfyUI server launch flags for DreamForge."""

from __future__ import annotations

import os
import platform
from typing import Final

from dreamforge_vram_profiles import (
    detect_mac_vram_profile,
    mps_available,
    normalize_vram_profile,
    profile_tier,
)

# ComfyUI reserve-vram is in GB. Windows WDDM benefits from extra headroom.
_WINDOWS_RESERVE: Final[dict[str, float]] = {
    "24gb": 1.5,
    "16gb": 2.0,
    "12gb": 1.25,
    "8gb": 1.0,
    "5gb": 0.75,
}
_DEFAULT_RESERVE: Final[dict[str, float]] = {
    "24gb": 1.25,
    "16gb": 1.5,
    "12gb": 1.0,
    "8gb": 0.75,
    "5gb": 0.5,
}


def cuda_total_vram_gb() -> float | None:
    try:
        import torch

        if torch.cuda.is_available():
            return float(torch.cuda.get_device_properties(0).total_memory) / (1024**3)
    except Exception:
        return None
    return None


def comfy_memory_tier(profile: str | None = None) -> str:
    """VRAM bucket for Comfy launch flags (may differ from generation step caps)."""
    measured = cuda_total_vram_gb()
    if measured is not None:
        if measured >= 22.0:
            return "24gb"
        if measured >= 14.0:
            return "16gb"
        if measured >= 10.0:
            return "12gb"
        if measured >= 7.0:
            return "8gb"
        return "5gb"
    return profile_tier(normalize_vram_profile(profile or os.environ.get("DREAMFORGE_VRAM_PROFILE")))


def _format_reserve_gb(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def reserve_vram_gb(*, tier: str, is_windows: bool) -> float:
    table = _WINDOWS_RESERVE if is_windows else _DEFAULT_RESERVE
    return table.get(tier, table["16gb"])


def tier_uses_lowvram(tier: str, *, is_windows: bool = False) -> bool:
    # 12 GB cards run Ultimate SD Upscale more reliably with lowvram on Windows.
    if tier in {"5gb", "8gb", "12gb"}:
        return True
    # 16 GB WDDM cards need offload headroom for dual-UNet stacks (Ideogram 4).
    return tier == "16gb" and is_windows


def comfy_launch_extra_args() -> tuple[str, ...]:
    """Map detected hardware → ComfyUI CLI memory flags."""
    profile = normalize_vram_profile(os.environ.get("DREAMFORGE_VRAM_PROFILE") or "auto")
    if profile == "no_gpu":
        return ("--cpu",)

    if mps_available():
        mac_tier = profile if profile.startswith("mps_") else detect_mac_vram_profile()
        if mac_tier in {"mps_24gb", "mps_16gb"}:
            return ("--highvram",)
        return ("--lowvram", "--reserve-vram", "0.75")

    tier = comfy_memory_tier(profile)
    is_windows = platform.system() == "Windows"
    args: list[str] = []
    if tier_uses_lowvram(tier, is_windows=is_windows):
        args.append("--lowvram")
    reserve = reserve_vram_gb(tier=tier, is_windows=is_windows)
    args.extend(("--reserve-vram", _format_reserve_gb(reserve)))
    return tuple(args)


def comfy_launch_summary() -> str:
    args = comfy_launch_extra_args()
    tier = comfy_memory_tier()
    vram = cuda_total_vram_gb()
    vram_note = f"{vram:.1f} GB VRAM" if vram is not None else f"{tier} tier"
    if not args:
        return f"ComfyUI memory mode: default ({vram_note})"
    return f"ComfyUI memory mode: {', '.join(args)} ({vram_note})"
