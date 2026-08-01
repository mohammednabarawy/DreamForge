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
    "16gb": 16384,
    "8gb": 8192,
    "5gb": 5120,
    "no_gpu": 0,
    "mps_24gb": 24576,
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
}

# Variants that materially reduce VRAM (scale the estimate).
_VARIANT_REDUCTION: dict[str, float] = {
    "fp8": 0.75,
    "fp8_scaled": 0.75,
    "mxfp8": 0.75,
    "q4_k_m": 0.55,
    "q4_k_s": 0.55,
    "q3_k_m": 0.5,
    "q2_k": 0.45,
    "gguf": 0.75,  # GGUF loads in Q-preserved chunks; keep conservative default
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
    "gguf": 0.7,
    "q4_k_m": 0.6,
    "q4_k_s": 0.6,
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
    )


class VramEstimator:
    """Estimates VRAM requirements for architectures / assets."""

    def estimate_for_architecture(
        self,
        architecture: str,
        variant: str = "",
        *,
        detail: bool = False,
    ) -> dict[str, Any]:
        base = ARCHITECTURE_VRAM_MB.get((architecture or "").lower(), 0)
        reduction = _VARIANT_REDUCTION.get((variant or "").lower(), 1.0)
        estimated = int(base * reduction) if base else 0
        if not detail:
            return {"architecture": architecture, "estimated_mb": estimated}
        return {
            "architecture": architecture,
            "base_mb": base,
            "variant": variant,
            "reduction": reduction,
            "estimated_mb": estimated,
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
) -> dict[str, Any]:
    """Return a compute-aware recommendation for an asset (plan §4)."""
    estimator = estimator or VramEstimator()
    estimate = estimator.estimate_for_asset(asset)
    fits = profile.can_fit(estimate.get("estimated_mb") or 0)
    return {
        "estimated_mb": estimate.get("estimated_mb"),
        "architecture": asset.architecture,
        "variant": estimate.get("variant", ""),
        "profile": profile.to_dict(),
        "fits": fits,
        "label": "Recommended" if fits else "May exceed your VRAM",
    }


def recommend_file_for_asset(
    asset: DreamForgeAsset,
    profile: ComputeProfile,
    estimator: VramEstimator | None = None,
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
    for idx, file_ in enumerate(version.files):
        est = estimator.estimate_for_architecture(
            asset.architecture, file_.variant, detail=True
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


def recommend_file_variants_from_dict(
    asset_dict: Mapping[str, Any] | None,
    vram_profile: str = "auto",
    profile: ComputeProfile | None = None,
) -> dict[str, Any]:
    """Recommendation over a raw asset dict (bridge/JSON surface)."""
    if not isinstance(asset_dict, Mapping) or not asset_dict:
        return {"ok": False, "error": "missing_asset"}
    from dreamforge_assets import DreamForgeAsset

    asset = DreamForgeAsset.from_dict(dict(asset_dict))
    compute = profile or detect_compute_profile(vram_profile)
    result = recommend_file_for_asset(asset, compute)
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
