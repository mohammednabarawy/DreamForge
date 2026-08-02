"""VRAM profile names, detection, and budget mapping (CUDA + Apple MPS)."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from typing import Final

# Apple Silicon unified-memory profiles (Inspector / CLI)
MAC_VRAM_PROFILES: Final[tuple[str, ...]] = (
    "mps_32gb",
    "mps_24gb",
    "mps_16gb",
    "mps_8gb",
    "mps_4gb",
)

CUDA_VRAM_PROFILES: Final[tuple[str, ...]] = ("32gb", "24gb", "16gb", "12gb", "8gb", "5gb")

ALL_VRAM_PROFILES: Final[tuple[str, ...]] = (
    "auto",
    "no_gpu",
    *CUDA_VRAM_PROFILES,
    *MAC_VRAM_PROFILES,
    "mps",  # legacy alias → auto-detect Mac tier
)


def _system_ram_gb() -> float | None:
    try:
        import psutil

        return float(psutil.virtual_memory().total) / (1024**3)
    except Exception:
        return None


def mps_available() -> bool:
    try:
        import torch

        return bool(
            hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        )
    except Exception:
        return False


def detect_mac_vram_profile() -> str:
    """Pick a Mac unified-memory tier from installed RAM."""
    ram_gb = _system_ram_gb()
    if ram_gb is None:
        return "mps_8gb"
    if ram_gb >= 30:
        return "mps_32gb"
    if ram_gb >= 22:
        return "mps_24gb"
    if ram_gb >= 14:
        return "mps_16gb"
    if ram_gb >= 10:
        return "mps_8gb"
    return "mps_4gb"


def profile_tier(profile: str) -> str:
    """Map any profile id to a CUDA-style tier for resolution/step caps."""
    profile = normalize_vram_profile(profile)
    if profile in {"32gb", "24gb", "mps_32gb"}:
        return "24gb"
    if profile in {"mps_24gb", "mps_16gb", "16gb"}:
        return "16gb"
    if profile in {"12gb", "mps_8gb", "mps", "8gb"}:
        return "8gb"
    if profile in {"mps_4gb", "5gb", "no_gpu"}:
        return "5gb"
    return "8gb"


# Legacy Comfy/desktop worker env (normal / low / no) → CUDA-style tier for step caps.
_DESKTOP_MODE_TIER_ALIASES: Final[dict[str, str]] = {
    "normal": "16gb",
    "normalvram": "16gb",
    "high": "16gb",
    "highvram": "16gb",
    "low": "8gb",
    "lowvram": "8gb",
    "no": "5gb",
    "novram": "5gb",
}


def normalize_vram_profile(profile: str | None) -> str:
    profile = (profile or "auto").lower()
    if profile in {"auto", "default"}:
        return detect_vram_profile()
    if profile in _DESKTOP_MODE_TIER_ALIASES:
        tier = _DESKTOP_MODE_TIER_ALIASES[profile]
        if tier == "16gb" and mps_available():
            return detect_mac_vram_profile()
        if tier == "16gb":
            return "16gb"
        if tier == "8gb":
            return "mps_8gb" if mps_available() else "8gb"
        return "mps_4gb" if mps_available() else "5gb"
    if profile == "mps":
        return detect_mac_vram_profile() if mps_available() else "8gb"
    if profile in {"low", "lowvram", "5gb"}:
        return "mps_4gb" if mps_available() else "5gb"
    if profile in {"mid", "midvram", "8gb"}:
        return "mps_8gb" if mps_available() else "8gb"
    if profile in {"high", "16gb", "rtx5060ti16"}:
        return detect_mac_vram_profile() if mps_available() else "16gb"
    if profile in {"cpu", "nogpu", "no_gpu", "none"}:
        return "no_gpu"
    if profile in MAC_VRAM_PROFILES:
        return profile
    return profile


def apply_desktop_vram_env(profile: str | None = None) -> str:
    """Resolve profile and export tier + profile ids for generation / Comfy."""
    resolved = normalize_vram_profile(
        profile or os.environ.get("DREAMFORGE_VRAM_PROFILE") or "auto"
    )
    tier = profile_tier(resolved)
    os.environ["DREAMFORGE_VRAM_PROFILE"] = resolved
    os.environ["DREAMFORGE_DESKTOP_VRAM_MODE"] = tier
    return resolved


def detect_vram_profile() -> str:
    """Best-effort local hardware profile."""
    env_profile = (os.environ.get("DREAMFORGE_VRAM_PROFILE") or "").lower()
    if env_profile and env_profile not in {"auto", "default"}:
        return normalize_vram_profile(env_profile)
    try:
        import torch

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            total_gb = props.total_memory / (1024**3)
            if total_gb >= 30:
                return "32gb"
            if total_gb >= 22:
                return "24gb"
            if total_gb >= 14:
                return "16gb"
            if total_gb >= 10.5:
                return "12gb"
            if total_gb >= 7:
                return "8gb"
            if total_gb >= 4:
                return "5gb"
            return "5gb"
        if mps_available():
            return detect_mac_vram_profile()
    except Exception:
        pass
    # PyTorch CPU wheels can still run a CUDA-backed managed Comfy install on
    # Windows; use nvidia-smi as a read-only fallback in that case.
    if shutil.which("nvidia-smi"):
        try:
            raw = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                encoding="utf-8", errors="ignore", timeout=3,
            ).splitlines()[0].strip()
            total_gb = float(raw) / 1024
            if total_gb >= 30: return "32gb"
            if total_gb >= 22: return "24gb"
            if total_gb >= 14: return "16gb"
            if total_gb >= 10.5: return "12gb"
            if total_gb >= 7: return "8gb"
            return "5gb"
        except Exception:
            pass
    if platform.system() == "Darwin" and mps_available():
        return detect_mac_vram_profile()
    return "no_gpu"


def profile_vram_budget_gb(profile: str | None) -> float | None:
    profile = normalize_vram_profile(profile)
    budgets = {
        "no_gpu": 0.0,
        "5gb": 5.0,
        "8gb": 8.0,
        "32gb": 32.0,
        "24gb": 24.0,
        "16gb": 16.0,
        "12gb": 12.0,
        "mps_4gb": 5.0,
        "mps_8gb": 8.0,
        "mps_16gb": 14.0,
        "mps_32gb": 32.0,
        "mps_24gb": 24.0,
    }
    return budgets.get(profile)


def hardware_class(
    *, vendor: str | None, backend: str | None, vram_gb: float | None,
    os_name: str | None = None, mps: bool = False,
) -> str:
    """Return the user-facing hardware bucket used by auto-optimization."""
    gb = float(vram_gb or 0)
    vendor_l = (vendor or "").lower()
    backend_l = (backend or "").lower()
    if mps or backend_l == "mps" or vendor_l == "apple":
        if gb >= 30: return "apple_silicon_32gb_plus"
        if gb >= 22: return "apple_silicon_24gb_plus"
        if gb >= 14: return "apple_silicon_16gb"
        return "apple_silicon_8gb"
    if vendor_l == "nvidia" or backend_l == "cuda":
        if gb >= 30: return "nvidia_32gb_plus"
        if gb >= 22: return "nvidia_24gb_plus"
        if gb >= 14: return "nvidia_16gb"
        if gb >= 10.5: return "nvidia_12gb"
        if gb >= 7: return "nvidia_8gb"
        return "nvidia_4_6gb"
    if vendor_l == "amd" or backend_l == "rocm":
        if (os_name or platform.system()).lower() == "linux" and gb >= 14:
            return "amd_rocm_linux_16gb_plus"
        if gb >= 14: return "amd_16gb_plus"
        if gb >= 8: return "amd_8_12gb"
        return "amd_4_8gb"
    return "cpu_only"


def lower_vram_profile(profile: str | None, *, mps: bool = False) -> str:
    """Return the next safer memory tier for a bounded OOM retry."""
    current = normalize_vram_profile(profile)
    if mps or current.startswith("mps_"):
        order = ("mps_32gb", "mps_24gb", "mps_16gb", "mps_8gb", "mps_4gb")
    else:
        order = ("32gb", "24gb", "16gb", "12gb", "8gb", "5gb", "no_gpu")
    try:
        return order[min(order.index(current) + 1, len(order) - 1)]
    except ValueError:
        return "mps_8gb" if mps else "8gb"


def comfy_launch_extra_args() -> tuple[str, ...]:
    from dreamforge_comfy_launch import comfy_launch_extra_args as _launch_args

    return _launch_args()


def comfy_launch_summary() -> str:
    from dreamforge_comfy_launch import comfy_launch_summary as _summary

    return _summary()
