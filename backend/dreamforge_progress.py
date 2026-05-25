"""Boot and generation phase helpers (LTX-style progress contract for DreamForge desktop)."""

from __future__ import annotations

# Boot phases (stable API for UI)
BOOT_STARTING = "starting"
BOOT_LOADING_SETTINGS = "loading_settings"
BOOT_LOADING_PYTORCH = "loading_pytorch"
BOOT_LOADING_PIPELINE = "loading_pipeline"
BOOT_READY = "ready"

# Generation phases
GEN_IDLE = "idle"
GEN_LOADING_MODELS = "loading_models"
GEN_PREPARING = "preparing"
GEN_SAMPLING = "sampling"
GEN_FINALIZING = "finalizing"
GEN_COMPLETE = "complete"
GEN_ERROR = "error"

BOOT_PHASE_LABELS: dict[str, str] = {
    BOOT_STARTING: "Starting GPU engine…",
    BOOT_LOADING_SETTINGS: "Loading DreamForge settings and paths…",
    BOOT_LOADING_PYTORCH: "Loading PyTorch{}…",
    BOOT_LOADING_PIPELINE: "Loading generation pipeline…",
    BOOT_READY: "Engine ready",
}

GEN_PHASE_LABELS: dict[str, str] = {
    GEN_IDLE: "Ready",
    GEN_LOADING_MODELS: "Loading models…",
    GEN_PREPARING: "Preparing…",
    GEN_SAMPLING: "Sampling…",
    GEN_FINALIZING: "Finalizing…",
    GEN_COMPLETE: "Complete",
    GEN_ERROR: "Generation failed",
}


def boot_phase_from_message(message: str) -> str:
    lower = (message or "").lower()
    if "pytorch" in lower or "cuda" in lower or "mps" in lower:
        return BOOT_LOADING_PYTORCH
    if "comfy" in lower or "pipeline" in lower or "still loading" in lower:
        return BOOT_LOADING_PIPELINE
    if "settings" in lower or "configuration" in lower or "paths" in lower:
        return BOOT_LOADING_SETTINGS
    if "starting" in lower or "gpu worker" in lower:
        return BOOT_STARTING
    return BOOT_LOADING_PIPELINE


def _backend_suffix() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return " and CUDA"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return " and MPS"
    except ImportError:
        pass
    return ""

def boot_label(phase: str, message: str | None = None) -> str:
    if message and message.strip():
        return message.strip()
    label = BOOT_PHASE_LABELS.get(phase, message or "Loading…")
    if phase == "loading_pytorch":
        label = label.format(_backend_suffix())
    return label


def generation_phase_from_preview(percentage: int | None, title: str | None) -> str:
    pct = int(percentage) if percentage is not None and percentage >= 0 else -1
    t = (title or "").lower()
    if "load" in t and "model" in t:
        return GEN_LOADING_MODELS
    if pct < 0:
        return GEN_PREPARING
    if pct >= 100:
        return GEN_FINALIZING
    if pct >= 0:
        return GEN_SAMPLING
    return GEN_PREPARING


def generation_label(phase: str, message: str | None = None, step: int | None = None, total: int | None = None) -> str:
    if message and message.strip():
        base = message.strip()
    else:
        base = GEN_PHASE_LABELS.get(phase, "Working…")
    if step is not None and total is not None and total > 0:
        return f"{base} ({step}/{total})"
    return base


def gpu_telemetry() -> dict:
    try:
        import torch

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return {
                "cuda_available": True,
                "gpu_name": torch.cuda.get_device_name(0),
                "vram_gb": round(float(props.total_memory) / (1024**3), 1),
            }
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return {
                "cuda_available": False,
                "mps_available": True,
                "gpu_name": "Apple MPS",
                "vram_gb": None,
            }
    except Exception:
        pass
    return {"cuda_available": False, "gpu_name": None, "vram_gb": None}
