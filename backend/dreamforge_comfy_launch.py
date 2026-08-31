"""Hardware-aware ComfyUI server launch flags for DreamForge.

The flag set adapts to the *installed* hardware and PyTorch build:

* PyTorch >= 2.8 on NVIDIA (non-WSL) unlocks ComfyUI's Dynamic VRAM (comfy-aimdo).
  In that mode we must NOT pass ``--lowvram`` (it is a no-op there) and must NOT
  pass ``--disable-dynamic-vram`` (that would force the slow legacy ModelPatcher).
  Dynamic VRAM uses ``--reserve-vram`` as its headroom target, so we still tune
  reserve per VRAM tier.
* Older PyTorch (< 2.8) or non-NVIDIA falls back to the legacy memory modes
  (``--lowvram`` streaming on tight Windows tiers, ``--highvram`` on big cards).

Kitchen attention is GPU-probed before automatic selection. Experimental
``--fast`` and Sage/Flash auto-selection remain behind the benchmark gate.
"""

from __future__ import annotations

import importlib.util
import logging
from functools import lru_cache
from pathlib import Path
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
# 16 GB needs a generous reserve: large fp8 models (Flux ~11 GB UNet + ~4.7 GB
# text encoder) would otherwise full-load to ~15.7 GB and leave no room, so the
# next back-to-back generation OOM-crashes. A 3 GB reserve forces ComfyUI to
# offload the text encoder to CPU instead of pinning everything resident.
_WINDOWS_RESERVE: Final[dict[str, float]] = {
    "24gb": 1.5,
    "16gb": 3.0,
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

# Dynamic VRAM headroom (acts as a *floor* of free VRAM aimdo keeps). It can be
# tighter than the legacy reserve because aimdo offloads adaptively instead of
# over-estimating, which is the whole point of the upgrade.
_DYNAMIC_RESERVE: Final[dict[str, float]] = {
    "24gb": 1.0,
    "16gb": 1.5,
    "12gb": 1.0,
    "8gb": 0.8,
    "5gb": 0.6,
}

# --fast is experimental and quality-affecting. It is only selected
# automatically after an explicit benchmark gate; users can still opt in with
# DREAMFORGE_COMFY_FAST.
_DEFAULT_FAST_FEATURES: Final[tuple[str, ...]] = ("fp16_accumulation",)


def cuda_total_vram_gb() -> float | None:
    try:
        import torch

        if torch.cuda.is_available():
            index = int(os.environ.get("DREAMFORGE_COMFY_DEVICE_INDEX") or 0)
            return float(torch.cuda.get_device_properties(index).total_memory) / (1024**3)
    except Exception:
        return None
    return None


def torch_version_tuple() -> tuple[int, int] | None:
    """(major, minor) of the installed torch, or None if torch is unavailable."""
    try:
        import torch

        parts = torch.__version__.split("+", 1)[0].split(".")
        return (int(parts[0]), int(parts[1]))
    except Exception:
        return None


def _is_wsl() -> bool:
    if platform.system() != "Linux":
        return False
    try:
        return "microsoft" in platform.uname().release.lower()
    except Exception:
        return False


def cuda_is_nvidia() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available() and torch.version.cuda is not None)
    except Exception:
        return False


def supports_dynamic_vram() -> bool:
    """Mirror ComfyUI's gate: Dynamic VRAM needs torch >= 2.8 on NVIDIA (non-WSL).

    See engines/comfyui/main.py and comfy/cli_args.py::enables_dynamic_vram.
    """
    if os.environ.get("DREAMFORGE_DISABLE_DYNAMIC_VRAM"):
        return False
    ver = torch_version_tuple()
    if ver is None or ver < (2, 8):
        return False
    return cuda_is_nvidia() and not _is_wsl()


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


@lru_cache(maxsize=4)
def _kitchen_attention_usable(device_index: int) -> bool:
    """Probe the installed kernel once per device, without changing generation RNG."""
    try:
        from _paths import COMFY_ROOT
        import torch
        import comfy_kitchen

        # An external/older checkout may not understand the new CLI flag yet.
        cli = Path(COMFY_ROOT) / "comfy" / "cli_args.py"
        if "--use-ck-attention" not in cli.read_text(encoding="utf-8"):
            return False
        device = torch.device("cuda", device_index)
        if torch.version.cuda is None or not comfy_kitchen.int8_attention_is_available(device):
            return False
        with torch.inference_mode():
            dtypes = [torch.float16]
            if torch.cuda.get_device_capability(device) >= (8, 0):
                dtypes.append(torch.bfloat16)
            for dtype in dtypes:
                q = torch.arange(4096, device=device, dtype=torch.float32).sin().reshape(1, 1, 64, 64).to(dtype)
                for mask in (None, torch.ones((64, 64), device=device, dtype=torch.bool).tril()):
                    out = comfy_kitchen.int8_attention(q, q, q, attn_mask=mask)
                    baseline = torch.nn.functional.scaled_dot_product_attention(q, q, q, attn_mask=mask)
                    if not torch.isfinite(out).all() or not torch.allclose(out, baseline, atol=0.05, rtol=0.05):
                        return False
        return True
    except Exception as exc:
        logging.getLogger(__name__).warning("Kitchen attention unavailable; using the standard backend: %s", exc)
        return False


def attention_flag() -> str | None:
    """Select one backend; kitchen auto-selection requires a successful GPU probe.

    DREAMFORGE_COMFY_ATTENTION accepts kitchen/ck, pytorch, sage, flash, auto, off.
    """
    pref = (os.environ.get("DREAMFORGE_COMFY_ATTENTION") or "auto").strip().lower()
    backend = os.environ.get("DREAMFORGE_COMFY_BACKEND")
    if pref in {"pytorch", "torch", "sdpa"} or (pref in {"", "auto"} and backend == "rocm"):
        return "--use-pytorch-cross-attention"
    if pref in {"off", "none", "0", "false"}:
        return None
    if pref in {"", "auto", "kitchen", "ck", "comfy-kitchen"}:
        if backend == "cuda" and _module_available("comfy_kitchen"):
            try:
                device_index = int(os.environ.get("DREAMFORGE_COMFY_DEVICE_INDEX") or 0)
                if _kitchen_attention_usable(device_index):
                    return "--use-ck-attention"
            except ValueError:
                pass
        if pref not in {"", "auto"}:
            return "--use-pytorch-cross-attention"
    if pref in {"sage", "sageattention"} and _module_available("sageattention"):
        return "--use-sage-attention"
    if pref in {"flash", "flashattention", "flash_attn"} and _module_available("flash_attn"):
        return "--use-flash-attention"
    if pref in {"", "auto"} and fast_benchmark_gate():
        if _module_available("sageattention"):
            return "--use-sage-attention"
        if _module_available("flash_attn"):
            return "--use-flash-attention"
    return None


def fast_features() -> tuple[str, ...]:
    """--fast optimizations to enable, or empty if disabled."""
    raw = os.environ.get("DREAMFORGE_COMFY_FAST")
    if raw is None:
        return _DEFAULT_FAST_FEATURES if fast_benchmark_gate() else ()
    value = raw.strip().lower()
    if value in {"off", "none", "0", "false", ""}:
        return ()
    if value in {"all", "1", "true"}:
        return ()  # sentinel handled by caller -> bare "--fast" enables everything
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def fast_benchmark_gate() -> bool:
    """Return true only for an explicitly validated modern CUDA policy."""
    if os.environ.get("DREAMFORGE_COMFY_BACKEND", "").lower() != "cuda":
        return False
    if os.environ.get("DREAMFORGE_COMFY_FAST_BENCHMARK_OK", "").strip().lower() not in {"1", "true", "yes"}:
        return False
    raw = (os.environ.get("DREAMFORGE_COMPUTE_CAPABILITY") or "").split(".", 1)
    try:
        capability = float(f"{int(raw[0])}.{int(raw[1])}") if len(raw) == 2 else 0.0
    except ValueError:
        capability = 0.0
    return capability >= 8.0


def fast_args() -> list[str]:
    raw = os.environ.get("DREAMFORGE_COMFY_FAST")
    if raw is not None and raw.strip().lower() in {"all", "1", "true"}:
        return ["--fast"]
    features = fast_features()
    if not features:
        return []
    return ["--fast", *features]


def _speed_args() -> list[str]:
    """--fast + accelerated attention, independent of the VRAM mode."""
    args = fast_args()
    attn = attention_flag()
    if attn:
        args.append(attn)
    return args


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


def reserve_vram_gb(*, tier: str, is_windows: bool, dynamic: bool = False) -> float:
    if dynamic:
        return _DYNAMIC_RESERVE.get(tier, _DYNAMIC_RESERVE["16gb"])
    table = _WINDOWS_RESERVE if is_windows else _DEFAULT_RESERVE
    return table.get(tier, table["16gb"])


def tier_uses_lowvram(tier: str, *, is_windows: bool = False) -> bool:
    """Whether Comfy should stream weights (slow but safe on tight VRAM)."""
    return comfy_launch_memory_mode(tier, is_windows=is_windows) == "lowvram"


def comfy_launch_memory_mode(tier: str, *, is_windows: bool = False) -> str:
    """Legacy (pre-Dynamic-VRAM) memory mode for a VRAM tier.

    On Windows, ComfyUI's "usable VRAM" estimate is inflated by WDDM shared
    memory, so on 16 GB it may full-load a large text encoder (e.g. Ideogram4's
    ~10 GB Qwen3VL TE) and then OOM-crash during the DiT/VAE stages. Stream
    weights (lowvram) on 16 GB Windows to stay stable with the large modern
    model families; keep the faster default elsewhere where the estimate holds.

    This path is only used when Dynamic VRAM is NOT available (torch < 2.8 or
    non-NVIDIA). With Dynamic VRAM, aimdo manages offload adaptively instead.
    """
    if tier == "24gb":
        return "highvram"
    if tier == "16gb":
        return "lowvram" if is_windows else "normalvram"
    if tier in {"5gb", "8gb", "12gb"}:
        return "lowvram"
    return "normalvram"


def comfy_launch_extra_args() -> tuple[str, ...]:
    """Map detected hardware + PyTorch build → ComfyUI CLI flags."""
    profile = normalize_vram_profile(os.environ.get("DREAMFORGE_VRAM_PROFILE") or "auto")
    if profile == "no_gpu":
        return ("--cpu",)

    if mps_available():
        mac_tier = profile if profile.startswith("mps_") else detect_mac_vram_profile()
        reserve = "2.5" if mac_tier in {"mps_32gb", "mps_24gb"} else "2" if mac_tier == "mps_16gb" else "1.5"
        # MPS uses unified memory; --highvram can starve the OS and is not a
        # useful analogue of CUDA highvram. Let Comfy's smart offload decide.
        return ("--reserve-vram", reserve)

    device_index = os.environ.get("DREAMFORGE_COMFY_DEVICE_INDEX")
    device_args = ["--cuda-device", device_index] if device_index is not None else []

    if os.environ.get("DREAMFORGE_COMFY_BACKEND") == "rocm":
        tier = comfy_memory_tier(profile)
        reserve = reserve_vram_gb(tier=tier, is_windows=platform.system() == "Windows")
        args = [*device_args, "--lowvram", "--reserve-vram", _format_reserve_gb(reserve), "--use-pytorch-cross-attention"]
        return tuple(args)

    tier = comfy_memory_tier(profile)
    is_windows = platform.system() == "Windows"

    if supports_dynamic_vram():
        # Dynamic VRAM (comfy-aimdo) path: let aimdo manage offload. Do NOT pass
        # --lowvram (no-op here) or --highvram/--disable-dynamic-vram (would turn
        # Dynamic VRAM off). --reserve-vram feeds aimdo's headroom target.
        reserve = reserve_vram_gb(tier=tier, is_windows=is_windows, dynamic=True)
        args = [*device_args, "--reserve-vram", _format_reserve_gb(reserve)]
        args.extend(_speed_args())
        return tuple(args)

    # Legacy path (torch < 2.8 or non-NVIDIA): estimate-based model loading.
    mode = comfy_launch_memory_mode(tier, is_windows=is_windows)
    if mode == "normalvram":
        # Emit no memory flags so ComfyUI uses its default smart memory mgmt.
        return tuple([*device_args, *_speed_args()])
    args = list(device_args)
    if mode == "highvram":
        args.append("--highvram")
    elif mode == "lowvram":
        args.append("--lowvram")
    reserve = reserve_vram_gb(tier=tier, is_windows=is_windows)
    args.extend(("--reserve-vram", _format_reserve_gb(reserve)))
    args.extend(_speed_args())
    return tuple(args)


def apply_runtime_optimization_env() -> dict[str, str]:
    """Export conservative backend knobs before the managed Comfy child starts."""
    try:
        from dreamforge_gpu_detect import detect_gpu

        detected = detect_gpu()
    except Exception:
        detected = {}
    backend = str(detected.get("backend") or "cpu")
    os.environ["DREAMFORGE_COMFY_BACKEND"] = backend
    os.environ["DREAMFORGE_HARDWARE_CLASS"] = str(detected.get("hardware_class") or "cpu_only")
    sources = set(detected.get("detection_sources") or ())
    selected_index = detected.get("selected_device_index")
    if backend in {"cuda", "rocm"} and selected_index is not None and sources.intersection({"torch.cuda", "nvidia-smi"}):
        os.environ["DREAMFORGE_COMFY_DEVICE_INDEX"] = str(int(selected_index))
    else:
        os.environ.pop("DREAMFORGE_COMFY_DEVICE_INDEX", None)
    if detected.get("compute_capability"):
        os.environ["DREAMFORGE_COMPUTE_CAPABILITY"] = str(detected["compute_capability"])
    if backend == "mps":
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    elif backend == "rocm":
        os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")
    return {k: os.environ[k] for k in ("DREAMFORGE_COMFY_BACKEND", "DREAMFORGE_HARDWARE_CLASS")}


def comfy_launch_summary() -> str:
    args = comfy_launch_extra_args()
    tier = comfy_memory_tier()
    vram = cuda_total_vram_gb()
    vram_note = f"{vram:.1f} GB VRAM" if vram is not None else f"{tier} tier"
    dyn = "Dynamic VRAM" if supports_dynamic_vram() else "legacy VRAM"
    if not args:
        return f"ComfyUI memory mode: default ({dyn}, {vram_note})"
    return f"ComfyUI memory mode: {', '.join(args)} ({dyn}, {vram_note})"


def apply_small_image_attention_policy(graph: dict, *, mode: str, family: str,
                                       width: int, height: int, kitchen_enabled: bool,
                                       object_info: dict) -> bool:
    """Keep small SD text-to-image jobs on native SDPA, without restarting Comfy.

    Matched RTX 5060 Ti runs showed no gain from kitchen at these sizes.
    Explicit backend choices and user-authored attention patches remain authoritative.
    """
    pref = (os.environ.get("DREAMFORGE_COMFY_ATTENTION") or "auto").strip().lower()
    if (pref not in {"", "auto"} or not kitchen_enabled or mode != "txt2img"
            or family not in {"sd15", "sdxl"} or min(width, height) <= 0
            or width * height > 768 * 768 or "ModelAttentionBackend" not in object_info
            or any(n.get("class_type") == "ModelAttentionBackend" for n in graph.values())):
        return False
    next_id = max([int(key) for key in graph if str(key).isdigit()] + [0]) + 1
    changed = False
    for node in list(graph.values()):
        if node.get("class_type") != "KSampler":
            continue
        model = node["inputs"]["model"]
        graph[str(next_id)] = {"class_type": "ModelAttentionBackend", "inputs": {
            "model": model, "attention": "pytorch attention",
        }}
        node["inputs"]["model"] = [str(next_id), 0]
        next_id += 1
        changed = True
    return changed
