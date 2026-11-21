"""Compute profile + VRAM estimation for DreamForge Discover & Library.

Defines:

- ``ComputeProfile``: a snapshot of the machine's compute capability
  (VRAM MB, backend, vendor, recommended DreamForge VRAM profile).
- ``VramEstimator``: per-architecture VRAM estimates used to answer
  "know whether your machine can run it" before download (plan §4).

Estimates are deliberately conservative floor values (text-to-image at
recommended resolution). They are advisory — the real gate is the
``CapabilityRegistry`` + the engine's own VRAM profile selection.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

from dreamforge_assets import DreamForgeAsset

# VRAM budget in MB per GPU tier, indexed by profile tier name.
# Sources: existing DreamForge VRAM profiles (16gb / 8gb / 5gb / no_gpu + MPS tiers).
PROFILE_VRAM_MB: dict[str, int] = {
    "32gb": 32768,
    "24gb": 24576,
    "16gb": 16384,
    "12gb": 12288,
    "8gb": 8192,
    "5gb": 5120,
    "no_gpu": 0,
    "mps_24gb": 24576,
    "mps_32gb": 32768,
    "mps_16gb": 16384,
    "mps_8gb": 8192,
    "mps_4gb": 4096,
    "auto": 0,
    "mps": 0,
}

# Estimated peak VRAM (MB) for a given architecture at default resolution.
# Conservative per-family values derived from existing per-family strategy tables
# (dreamforge_agent_tools.py MODEL_FAMILY_HINTS) and ComfyUI usage.
ARCHITECTURE_VRAM_MB: dict[str, int] = {
    "sd15": 3072,
    "sdxl": 6144,
    "sd3": 8192,
    "flux": 12288,
    "flux_kontext": 12288,
    "flux_fill": 12288,
    "flux2": 16384,
    "hidream": 8192,
    "hidream_o1": 12288,
    "qwen_image": 12288,
    "qwen_image_edit": 12288,
    "ideogram4": 12288,
    "z_image": 8192,
    "krea2": 12288,
    "minimax_h3_image": 24576,
}

# Variants that materially reduce VRAM (scale the estimate).
_VARIANT_REDUCTION: dict[str, float] = {
    "fp8": 0.75,
    "fp8_scaled": 0.75,
    "mxfp8": 0.75,
    "int8": 0.72,
    "w6a8": 0.68,
    "q8_0": 0.75,
    "q6_k": 0.65,
    "q5_k_m": 0.60,
    "q5_k_s": 0.58,
    "w4a8": 0.55,
    "fp4": 0.50,
    "q4_k_m": 0.55,
    "q4_k_s": 0.55,
    "q3_k_m": 0.5,
    "q2_k": 0.45,
    "gguf": 0.70,  # GGUF loads in Q-preserved chunks; keep conservative default
}

# Precision/quality rank for variant recommendation: higher = higher quality.
# Unknown/absent variant is treated as the highest quality (no quantization info).
VARIANT_QUALITY: dict[str, float] = {
    "": 1.0,
    "fp16": 1.0,
    "bf16": 1.0,
    "fp8": 0.85,
    "fp8_scaled": 0.85,
    "mxfp8": 0.85,
    "int8": 0.82,
    "w6a8": 0.76,
    "q8_0": 0.82,
    "q6_k": 0.74,
    "gguf": 0.7,
    "q5_k_m": 0.68,
    "q5_k_s": 0.65,
    "w4a8": 0.62,
    "q4_k_m": 0.6,
    "q4_k_s": 0.58,
    "fp4": 0.56,
    "q3_k_m": 0.5,
    "q2_k": 0.45,
}


@dataclass(frozen=True)
class ComputeProfile:
    vram_mb: int = 0
    backend: str = "cpu"
    vendor: str = "Unknown"
    device_name: str = "CPU Fallback"
    recommended_profile: str = "no_gpu"
    vram_profile: str = "auto"
    os: str = ""
    gpu_architecture: str | int | None = None
    compute_capability: str | None = None
    free_vram_mb: int | None = None
    total_ram_mb: int = 0
    available_ram_mb: int = 0
    hardware_class: str = "cpu_only"
    support_level: str = "cpu"
    confidence: str = "low"
    warnings: tuple[str, ...] = ()
    fallback_reason: str | None = None

    @property
    def has_gpu(self) -> bool:
        return self.vram_mb > 0

    @property
    def vram_gb(self) -> float:
        return round(self.vram_mb / 1024, 2)

    def can_fit(self, estimated_mb: int) -> bool:
        """Whether an estimated VRAM requirement fits this machine."""
        if not self.has_gpu:
            return False
        if self.vram_profile in ("auto", "mps"):
            return estimated_mb <= self.vram_mb
        profile_mb = PROFILE_VRAM_MB.get(self.vram_profile, self.vram_mb)
        if profile_mb <= 0:
            profile_mb = self.vram_mb
        return estimated_mb <= profile_mb

    def to_dict(self) -> dict[str, Any]:
        return {
            "vram_mb": self.vram_mb,
            "vram_gb": self.vram_gb,
            "backend": self.backend,
            "vendor": self.vendor,
            "device_name": self.device_name,
            "recommended_profile": self.recommended_profile,
            "vram_profile": self.vram_profile,
            "has_gpu": self.has_gpu,
            "os": self.os,
            "gpu_architecture": self.gpu_architecture,
            "compute_capability": self.compute_capability,
            "free_vram_mb": self.free_vram_mb,
            "total_ram_mb": self.total_ram_mb,
            "available_ram_mb": self.available_ram_mb,
            "hardware_class": self.hardware_class,
            "support_level": self.support_level,
            "confidence": self.confidence,
            "warnings": list(self.warnings),
            "fallback_reason": self.fallback_reason,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "ComputeProfile":
        data = data or {}
        return cls(
            vram_mb=int(data.get("vram_mb") or 0),
            backend=str(data.get("backend") or "cpu"),
            vendor=str(data.get("vendor") or "Unknown"),
            device_name=str(data.get("device_name") or "CPU Fallback"),
            recommended_profile=str(data.get("recommended_profile") or "no_gpu"),
            vram_profile=str(data.get("vram_profile") or "auto"),
            os=str(data.get("os") or ""),
            gpu_architecture=data.get("gpu_architecture"),
            compute_capability=data.get("compute_capability"),
            free_vram_mb=int(data["free_vram_mb"]) if data.get("free_vram_mb") is not None else None,
            total_ram_mb=int(data.get("total_ram_mb") or 0),
            available_ram_mb=int(data.get("available_ram_mb") or 0),
            hardware_class=str(data.get("hardware_class") or "cpu_only"),
            support_level=str(data.get("support_level") or "cpu"),
            confidence=str(data.get("confidence") or "low"),
            warnings=tuple(str(v) for v in (data.get("warnings") or ())),
            fallback_reason=str(data.get("fallback_reason")) if data.get("fallback_reason") else None,
        )


def detect_compute_profile(vram_profile: str = "auto") -> ComputeProfile:
    """Build a ComputeProfile from GPU detection + optional user VRAM override."""
    from dreamforge_gpu_detect import detect_gpu

    gpu = detect_gpu()
    vram_mb = int(gpu.get("vram_mb") or 0)
    profile = vram_profile if vram_profile else "auto"
    if profile in ("auto", "mps"):
        profile = str(gpu.get("recommended_profile") or "no_gpu")
    return ComputeProfile(
        vram_mb=vram_mb,
        backend=str(gpu.get("backend") or "cpu"),
        vendor=str(gpu.get("vendor") or "Unknown"),
        device_name=str(gpu.get("device_name") or "CPU Fallback"),
        recommended_profile=str(gpu.get("recommended_profile") or "no_gpu"),
        vram_profile=profile,
        os=str(gpu.get("os") or ""),
        gpu_architecture=gpu.get("gpu_architecture"),
        compute_capability=gpu.get("compute_capability"),
        free_vram_mb=gpu.get("free_vram_mb"),
        total_ram_mb=int(gpu.get("total_ram_mb") or 0),
        available_ram_mb=int(gpu.get("available_ram_mb") or 0),
        hardware_class=str(gpu.get("hardware_class") or "cpu_only"),
        support_level=str(gpu.get("support_level") or "cpu"),
        confidence=str(gpu.get("confidence") or "low"),
        warnings=tuple(str(v) for v in (gpu.get("warnings") or ())),
        fallback_reason=str(gpu.get("fallback_reason")) if gpu.get("fallback_reason") else None,
    )


class VramEstimator:
    """Estimates VRAM requirements for architectures / assets."""

    def estimate_for_architecture(
        self,
        architecture: str,
        variant: str = "",
        *,
        detail: bool = False,
        width: int | None = None,
        height: int | None = None,
        batch: int = 1,
        workflow_overhead_mb: int = 0,
        vae_mb: int = 0,
        text_encoder_mb: int = 0,
        controlnet_mb: int = 0,
        ip_adapter_mb: int = 0,
        lora_mb: int = 0,
        preview_decode_mb: int = 0,
        companion_model_mb: int = 0,
    ) -> dict[str, Any]:
        base = ARCHITECTURE_VRAM_MB.get((architecture or "").lower(), 0)
        reduction = _VARIANT_REDUCTION.get((variant or "").lower(), 1.0)
        scale = 1.0
        if width and height:
            # 1024² is the conservative baseline used by the family table.
            scale = max(0.5, min(2.5, (width * height) / (1024 * 1024)))
        companions = sum(max(0, int(value or 0)) for value in (
            workflow_overhead_mb, vae_mb, text_encoder_mb, controlnet_mb,
            ip_adapter_mb, lora_mb, preview_decode_mb, companion_model_mb,
        ))
        # Model weights stay resident as resolution/batch changes; only the
        # activation/working-set share scales. Keep the old exact baseline for
        # callers that provide no workflow context.
        if base and not any((width, height, batch != 1, companions)):
            estimated = int(base * reduction)
            model_mb = estimated
            activation_mb = 0
        elif base:
            model_mb = int(base * reduction * 0.8)
            activation_mb = int(base * reduction * 0.2)
            activation_scale = max(0.75, scale)
            estimated = model_mb + int(activation_mb * activation_scale * max(1, batch)) + companions
        else:
            model_mb = activation_mb = 0
            estimated = companions
        if not detail:
            return {"architecture": architecture, "estimated_mb": estimated}
        return {
            "architecture": architecture,
            "base_mb": base,
            "variant": variant,
            "reduction": reduction,
            "estimated_mb": estimated,
            "resolution_scale": scale,
            "batch": batch,
            "workflow_overhead_mb": workflow_overhead_mb,
            "model_mb": model_mb,
            "activation_mb": activation_mb,
            "companion_breakdown": {
                "workflow_overhead_mb": workflow_overhead_mb,
                "vae_mb": vae_mb,
                "text_encoder_mb": text_encoder_mb,
                "controlnet_mb": controlnet_mb,
                "ip_adapter_mb": ip_adapter_mb,
                "lora_mb": lora_mb,
                "preview_decode_mb": preview_decode_mb,
                "companion_model_mb": companion_model_mb,
            },
            "unknown_architecture": not bool(base),
        }

    def estimate_for_asset(self, asset: DreamForgeAsset) -> dict[str, Any]:
        variant = ""
        file_ = asset.primary_file
        if file_ is not None:
            variant = file_.variant
        return self.estimate_for_architecture(
            asset.architecture, variant, detail=True
        )


def estimate_asset_fit(
    asset: DreamForgeAsset,
    profile: ComputeProfile,
    estimator: VramEstimator | None = None,
    *,
    width: int | None = None,
    height: int | None = None,
    batch: int = 1,
    workflow_overhead_mb: int = 0,
    vae_mb: int = 0,
    text_encoder_mb: int = 0,
    controlnet_mb: int = 0,
    ip_adapter_mb: int = 0,
    lora_mb: int = 0,
    preview_decode_mb: int = 0,
    companion_model_mb: int = 0,
) -> dict[str, Any]:
    """Return a compute-aware recommendation for an asset (plan §4)."""
    estimator = estimator or VramEstimator()
    if any((width, height, batch != 1, workflow_overhead_mb, vae_mb,
            text_encoder_mb, controlnet_mb, ip_adapter_mb, lora_mb,
            preview_decode_mb, companion_model_mb)):
        file_ = asset.primary_file
        estimate = estimator.estimate_for_architecture(
            asset.architecture, file_.variant if file_ else "", detail=True,
            width=width, height=height, batch=batch,
            workflow_overhead_mb=workflow_overhead_mb,
            vae_mb=vae_mb, text_encoder_mb=text_encoder_mb,
            controlnet_mb=controlnet_mb, ip_adapter_mb=ip_adapter_mb,
            lora_mb=lora_mb, preview_decode_mb=preview_decode_mb,
            companion_model_mb=companion_model_mb,
        )
    else:
        estimate = estimator.estimate_for_asset(asset)
    fits = None if not estimate.get("base_mb") else profile.can_fit(estimate.get("estimated_mb") or 0)
    return {
        "estimated_mb": estimate.get("estimated_mb"),
        "architecture": asset.architecture,
        "variant": estimate.get("variant", ""),
        "profile": profile.to_dict(),
        "fits": fits,
        "label": "Recommended" if fits is True else "Unknown fit" if fits is None else "May exceed your VRAM",
        "companion_breakdown": estimate.get("companion_breakdown", {}),
        "workflow": estimate,
    }


def recommend_file_for_asset(
    asset: DreamForgeAsset,
    profile: ComputeProfile,
    estimator: VramEstimator | None = None,
    *,
    workflow: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Pick the best file variant for an asset's active version (plan §4).

    Preference order:
    1. A file whose estimated VRAM fits the compute profile, choosing the
       highest-quality variant that still fits (and preferring files with a
       known SHA256 for integrity verification).
    2. If nothing fits, the file whose estimate is closest to fitting.
    3. Unknown architectures (no estimate) are surfaced as unverifiable and a
       known-SHA file is preferred when present.

    Every file is returned (rated) so the UI can let the user override the
    recommended variant.
    """
    estimator = estimator or VramEstimator()
    version = asset.active_version
    if version is None or not version.files:
        return {
            "files": [],
            "recommended": None,
            "architecture": asset.architecture,
            "profile": profile.to_dict(),
        }

    rated: list[dict[str, Any]] = []
    workflow = dict(workflow or {})
    for idx, file_ in enumerate(version.files):
        est = estimator.estimate_for_architecture(
            asset.architecture, file_.variant, detail=True
            , **{key: workflow[key] for key in (
                "width", "height", "batch", "workflow_overhead_mb", "vae_mb",
                "text_encoder_mb", "controlnet_mb", "ip_adapter_mb", "lora_mb",
                "preview_decode_mb", "companion_model_mb"
            ) if key in workflow}
        )
        estimated_mb = int(est.get("estimated_mb") or 0)
        if estimated_mb:
            fits = profile.can_fit(estimated_mb)
        else:
            fits = None  # unknown architecture — cannot verify
        rated.append(
            {
                "index": idx,
                "filename": file_.filename,
                "sha256": file_.sha256,
                "size_bytes": file_.size_bytes,
                "variant": file_.variant,
                "format": file_.format,
                "estimated_mb": estimated_mb,
                "fits": fits,
                "workflow": est,
            }
        )

    def quality(entry: dict[str, Any]) -> float:
        return VARIANT_QUALITY.get((entry.get("variant") or "").lower(), 1.0)

    def prefer_sha(candidates: list[dict[str, Any]]) -> dict[str, Any]:
        for candidate in candidates:
            if candidate.get("sha256"):
                return candidate
        return candidates[0]

    recommended: dict[str, Any]
    fits_list = [f for f in rated if f.get("fits") is True]
    if fits_list:
        fits_list.sort(key=lambda f: (-quality(f), f["index"]))
        recommended = prefer_sha(fits_list)
    else:
        unknown = [f for f in rated if f.get("fits") is None]
        if unknown:
            unknown.sort(key=lambda f: (-quality(f), f["index"]))
            recommended = prefer_sha(unknown)
        else:
            rated.sort(key=lambda f: (f.get("estimated_mb") or 0, f["index"]))
            recommended = rated[0]

    return {
        "files": rated,
        "recommended": recommended,
        "architecture": asset.architecture,
        "profile": profile.to_dict(),
    }


def assess_asset_device_compatibility(
    asset: DreamForgeAsset,
    profile: ComputeProfile,
    supported_architectures: set[str] | frozenset[str] | None = None,
    workflow: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a clear, device-aware compatibility verdict for a Discover card."""
    from dreamforge_capability_registry import SUPPORTED_ARCHITECTURES

    supported_set = (
        {a.lower() for a in supported_architectures}
        if supported_architectures is not None
        else set(SUPPORTED_ARCHITECTURES)
    )
    arch = (asset.architecture or "").strip().lower()
    rec_bundle = recommend_file_for_asset(asset, profile, workflow=workflow)
    rated_files = [dict(f) for f in (rec_bundle.get("files") or [])]

    effective_budget_mb = profile.vram_mb
    if profile.vram_profile not in ("auto", "mps"):
        prof_mb = PROFILE_VRAM_MB.get(profile.vram_profile, 0)
        if prof_mb > 0:
            effective_budget_mb = prof_mb

    is_mps = profile.backend == "mps"
    # Apple Silicon shares unified memory with macOS (~75% comfortable, ~95% tight).
    # Discrete GPUs can stream/offload slightly beyond dedicated VRAM via ComfyUI Dynamic VRAM / lowvram.
    comfort_mb = int(effective_budget_mb * (0.75 if is_mps else 0.90))
    tight_mb = int(effective_budget_mb * (0.95 if is_mps else 1.15))

    # Ground each file's memory estimate with real file size when known:
    # - Unknown architecture with known file size -> ~1.25x file size.
    # - Known architecture with large real file -> never underestimate below ~1.15x file size.
    for entry in rated_files:
        est_mb = int(entry.get("estimated_mb") or 0)
        size_bytes = int(entry.get("size_bytes") or 0)
        if size_bytes > 0:
            size_mb = size_bytes / (1024 * 1024)
            if est_mb <= 0:
                est_mb = max(512, int(size_mb * 1.25))
            else:
                est_mb = max(est_mb, int(size_mb * 1.15))
        entry["estimated_mb"] = est_mb
        if effective_budget_mb > 0 and est_mb > 0:
            entry["fits"] = est_mb <= tight_mb

    def _file_quality(entry: dict[str, Any]) -> float:
        return VARIANT_QUALITY.get((entry.get("variant") or "").lower(), 1.0)

    def _pick_best(candidates: list[dict[str, Any]]) -> dict[str, Any]:
        for c in candidates:
            if c.get("sha256"):
                return c
        return candidates[0]

    recommended = rec_bundle.get("recommended")
    if rated_files and effective_budget_mb > 0:
        comfort_fits = [f for f in rated_files if 0 < int(f.get("estimated_mb") or 0) <= comfort_mb]
        tight_fits = [f for f in rated_files if 0 < int(f.get("estimated_mb") or 0) <= tight_mb]
        if comfort_fits:
            comfort_fits.sort(key=lambda f: (-_file_quality(f), f["index"]))
            recommended = _pick_best(comfort_fits)
        elif tight_fits:
            tight_fits.sort(key=lambda f: (-_file_quality(f), f["index"]))
            recommended = _pick_best(tight_fits)
        else:
            known = [f for f in rated_files if int(f.get("estimated_mb") or 0) > 0]
            if known:
                known.sort(key=lambda f: (int(f.get("estimated_mb") or 0), f["index"]))
                recommended = known[0]

    estimated_mb = int((recommended or {}).get("estimated_mb") or 0)
    rec_variant = str((recommended or {}).get("variant") or "")
    rec_index = int((recommended or {}).get("index") or 0)

    mem_label = (
        f"{profile.vram_gb:.0f} GB unified"
        if is_mps and profile.vram_gb > 0
        else f"{profile.vram_gb:.0f} GB VRAM"
        if profile.vram_gb > 0
        else "CPU"
    )
    device_desc = f"{profile.device_name} ({mem_label})"
    est_gb_text = f"~{estimated_mb / 1024:.1f} GB" if estimated_mb > 0 else ""
    variant_text = f" ({rec_variant.upper()})" if rec_variant else ""

    if arch and arch not in supported_set:
        status = "unsupported_arch"
        label = "Unsupported arch"
        reason = f'Architecture "{arch}" is not supported by this DreamForge engine.'
    elif not profile.has_gpu or effective_budget_mb <= 0:
        status = "cpu_only"
        label = "CPU only (slow)"
        reason = f"No GPU detected ({profile.device_name}); generation will run slowly on CPU."
    elif estimated_mb <= 0:
        status = "unknown"
        label = "Check VRAM"
        reason = f"Size/architecture not specified by provider — verify against {device_desc}."
    elif estimated_mb <= comfort_mb:
        status = "compatible"
        label = "Compatible"
        reason = f"Fits {device_desc} · {est_gb_text}{variant_text}."
    elif estimated_mb <= tight_mb:
        status = "tight"
        label = "Tight fit"
        reason = (
            f"Tight fit on {device_desc} · {est_gb_text}{variant_text} "
            f"(will use memory offload; lower resolution/batch recommended)."
        )
    else:
        status = "too_large"
        label = "Exceeds VRAM"
        reason = (
            f"Needs {est_gb_text}{variant_text}, exceeding {device_desc} "
            f"(try a quantized FP8/GGUF variant or lower-memory model)."
        )

    compatible_files = sum(
        1
        for f in rated_files
        if int(f.get("estimated_mb") or 0) > 0 and int(f.get("estimated_mb") or 0) <= tight_mb
    )
    return {
        "status": status,
        "label": label,
        "reason": reason,
        "estimated_mb": estimated_mb,
        "usable_vram_mb": comfort_mb,
        "tight_vram_mb": tight_mb,
        "device_name": profile.device_name,
        "device_vram_gb": profile.vram_gb,
        "backend": profile.backend,
        "recommended_variant": rec_variant,
        "recommended_file_index": rec_index,
        "recommended": recommended,
        "file_estimates_mb": [int(f.get("estimated_mb") or 0) for f in rated_files],
        "compatible_files_count": compatible_files,
        "fits": status in {"compatible", "tight"},
    }


def recommend_file_variants_from_dict(
    asset_dict: Mapping[str, Any] | None,
    vram_profile: str = "auto",
    profile: ComputeProfile | None = None,
    workflow: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Recommendation over a raw asset dict (bridge/JSON surface)."""
    if not isinstance(asset_dict, Mapping) or not asset_dict:
        return {"ok": False, "error": "missing_asset"}
    from dreamforge_assets import DreamForgeAsset

    asset = DreamForgeAsset.from_dict(dict(asset_dict))
    compute = profile or detect_compute_profile(vram_profile)
    result = recommend_file_for_asset(asset, compute, workflow=workflow)
    return {"ok": True, **result}


# -- Env overrides for tests / headless machines -------------------------------

def _env_vram_mb() -> int | None:
    raw = os.environ.get("DREAMFORGE_TEST_VRAM_MB", "").strip()
    if raw.isdigit():
        return int(raw)
    return None


def detect_compute_profile_static(
    vram_mb: int | None = None,
    backend: str = "cuda",
    vram_profile: str = "auto",
    vendor: str = "NVIDIA",
) -> ComputeProfile:
    """Deterministic compute profile for tests and headless contexts."""
    effective_mb = vram_mb
    if effective_mb is None:
        effective_mb = _env_vram_mb() or 0
    profile = vram_profile
    if profile in ("auto", "mps") and effective_mb:
        if effective_mb >= 14000:
            profile = "16gb"
        elif effective_mb >= 7000:
            profile = "8gb"
        else:
            profile = "5gb"
    return ComputeProfile(
        vram_mb=effective_mb,
        backend=backend,
        vendor=vendor,
        device_name="Test Device",
        recommended_profile=profile if profile not in ("auto",) else "no_gpu",
        vram_profile=profile if profile not in ("auto",) else "auto",
    )
