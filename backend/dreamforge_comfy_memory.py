"""
ComfyUI memory helpers for DreamForge (large safetensors / WinError 1455).

Comfy's default safetensors path uses ``safe_open`` + ``get_tensor`` for every
weight, which reserves a large commit charge up front. The ``comfy-aimdo``
package mmap's the file instead — required for ~17 GB Flux fp8 on Windows.
"""
from __future__ import annotations

import gc
import logging
import sys
from pathlib import Path
from typing import Any, Callable

_log = logging.getLogger(__name__)

_AIMDO_INIT_ATTEMPTED = False
_AIMDO_ACTIVE = False


def _stderr(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def enable_aimdo_mmap_loading(*, force_retry: bool = False) -> bool:
    """Enable Comfy's aimdo code path in ``load_torch_file`` when possible."""
    global _AIMDO_INIT_ATTEMPTED, _AIMDO_ACTIVE
    if _AIMDO_ACTIVE:
        return True
    if _AIMDO_INIT_ATTEMPTED and not force_retry:
        return False

    _AIMDO_INIT_ATTEMPTED = True
    try:
        import comfy_aimdo.control as aimdo_control
    except ImportError:
        _stderr(
            "[DreamForge] comfy-aimdo is not installed; large Flux fp8 loads may fail "
            "with WinError 1455. Reinstall embedded Python deps or use a GGUF model."
        )
        return False

    try:
        if not aimdo_control.init():
            _stderr(
                "[DreamForge] comfy-aimdo native library failed to load; "
                "using default safetensors loader (high RAM peak)."
            )
            return False
        import comfy.memory_management as mm

        mm.aimdo_enabled = True
        _AIMDO_ACTIVE = True
        _stderr("[DreamForge] Large safetensors will load via memory-mapped I/O (comfy-aimdo).")
        return True
    except Exception as exc:
        _stderr(f"[DreamForge] Could not enable comfy-aimdo: {exc}")
        return False


def prepare_for_large_model_load() -> None:
    """Best-effort release of RAM/VRAM caches before loading a multi-GB checkpoint."""
    gc.collect(generation=2)
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            if hasattr(torch.cuda, "ipc_collect"):
                torch.cuda.ipc_collect()
    except Exception:
        pass
    try:
        import comfy.model_management as model_management

        model_management.cleanup_models()
        model_management.soft_empty_cache()
    except Exception:
        pass


def _load_safetensors_state_dict(ckpt: str) -> tuple[dict, dict]:
    """Load a safetensors file through comfy-aimdo mmap (does not use safe_open)."""
    import comfy_aimdo.control as aimdo_control

    if aimdo_control.lib is None and not aimdo_control.init():
        raise RuntimeError("comfy-aimdo is not initialized")
    import comfy.utils as comfy_utils

    return comfy_utils.load_safetensors(ckpt)


def load_diffusion_model_from_path(
    unet_path: str,
    model_options: dict[str, Any] | None = None,
    *,
    disable_dynamic: bool = False,
) -> Any:
    """
    Load a diffusion UNet from disk with the lowest practical RAM peak.

    Prefer comfy-aimdo mmap; fall back to Comfy's stock loader only for small
    files or when aimdo is unavailable.
    """
    import comfy.sd as comfy_sd

    model_options = dict(model_options or {})
    path = str(unet_path)
    prepare_for_large_model_load()
    enable_aimdo_mmap_loading()

    use_mmap = _AIMDO_ACTIVE and path.lower().endswith((".safetensors", ".sft"))
    large = use_mmap and Path(path).is_file() and Path(path).stat().st_size >= 4 * 1024 ** 3

    if large:
        try:
            sd, metadata = _load_safetensors_state_dict(path)
            _stderr(f"[DreamForge] mmap-loaded UNet weights from {Path(path).name}")
            return comfy_sd.load_diffusion_model_state_dict(
                sd,
                model_options=model_options,
                metadata=metadata,
                disable_dynamic=disable_dynamic,
            )
        except OSError as exc:
            winerr = getattr(exc, "winerror", None)
            if winerr == 1455 or "paging file" in str(exc).lower():
                raise
            _log.warning("mmap UNet load failed, falling back: %s", exc)
        except Exception as exc:
            _log.warning("mmap UNet load failed, falling back: %s", exc)

    return comfy_sd.load_diffusion_model(
        path,
        model_options=model_options,
        disable_dynamic=disable_dynamic,
    )


def set_ram_cache_release(callback: Callable[[int], int] | None, headroom_mb: int = 0) -> None:
    """Optional hook Comfy calls when it needs extra system RAM during load."""
    try:
        import comfy.memory_management as mm

        mm.set_ram_cache_release_state(callback, headroom_mb)
    except Exception:
        pass
