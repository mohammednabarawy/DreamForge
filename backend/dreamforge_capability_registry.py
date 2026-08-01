"""CapabilityRegistry for DreamForge Discover & Library.

Wraps and extends the existing ``dreamforge_model_registry`` family→capability
maps into a registry used by Discover cards to answer:

- What architectures does DreamForge support today?
- Which capabilities does an architecture provide?
- Is an asset architecture supported by the local engine?
- Does a requested route/capability fit the current compute profile?

Every new architecture enters through this registry (plan §31.18) instead of
scattered ``if/else`` checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from dreamforge_assets import AssetKind, DreamForgeAsset, detect_architecture
from dreamforge_model_registry import (
    FAMILY_CAPABILITIES,
    ModelCapabilities,
    get_family_capabilities,
    model_capabilities_for_model,
    required_capabilities_for_request,
)

# Architectures DreamForge's engine can run today (aligned with the
# model registry's family list + known file heuristics).
SUPPORTED_ARCHITECTURES: frozenset[str] = frozenset(
    {
        "sdxl",
        "sd15",
        "sd3",
        "flux",
        "flux_kontext",
        "flux_fill",
        "flux2",
        "qwen_image",
        "qwen_image_edit",
        "hidream",
        "hidream_o1",
        "ideogram4",
        "z_image",
        "krea2",
    }
)

# Kind → capability gate used when a Discover asset requests a capability.
KIND_CAPABILITY_HINT: dict[str, str] = {
    AssetKind.CHECKPOINT.value: ModelCapabilities.TEXT_TO_IMAGE,
    AssetKind.LORA.value: ModelCapabilities.TEXT_TO_IMAGE,
    AssetKind.CONTROLNET.value: ModelCapabilities.CONTROLNET_COMPATIBLE,
    AssetKind.VAE.value: ModelCapabilities.TEXT_TO_IMAGE,
    AssetKind.UPSCALER.value: ModelCapabilities.UPSCALE,
    AssetKind.IPADAPTER.value: ModelCapabilities.IPADAPTER_COMPATIBLE,
}


@dataclass(frozen=True)
class CompatibilityVerdict:
    supported: bool
    architecture: str
    supported_architectures: tuple[str, ...]
    capability_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "supported": self.supported,
            "architecture": self.architecture,
            "supported_architectures": list(self.supported_architectures),
            "capability_notes": list(self.capability_notes),
        }


class CapabilityRegistry:
    """Registry of supported architectures and their capabilities."""

    def __init__(
        self,
        supported: set[str] | None = None,
        family_capabilities: Mapping[str, set[str]] | None = None,
    ) -> None:
        self._supported = frozenset(supported) if supported is not None else SUPPORTED_ARCHITECTURES
        self._family_capabilities: dict[str, set[str]] = {
            key: set(value) for key, value in (family_capabilities or FAMILY_CAPABILITIES).items()
        }

    @property
    def supported_architectures(self) -> tuple[str, ...]:
        return tuple(sorted(self._supported))

    def is_supported_architecture(self, architecture: str) -> bool:
        return (architecture or "").lower() in self._supported

    def capabilities_for_architecture(self, architecture: str) -> set[str]:
        arch = (architecture or "").lower()
        caps = set(self._family_capabilities.get(arch, set()))
        if arch in self._supported:
            caps.add(ModelCapabilities.TEXT_TO_IMAGE)
        return caps

    def supports_capability(self, architecture: str, capability: str) -> bool:
        return capability in self.capabilities_for_architecture(architecture)

    def register_architecture(self, architecture: str, capabilities: set[str]) -> None:
        """Entry point for new architectures (plan §31.18)."""
        arch = (architecture or "").lower()
        if not arch:
            return
        current = set(self._family_capabilities.get(arch, set()))
        current.update(capabilities)
        self._family_capabilities[arch] = current
        self._supported = frozenset(set(self._supported) | {arch})

    def architecture_for_asset(self, asset: DreamForgeAsset | None) -> str:
        if asset is None:
            return ""
        if asset.architecture:
            return asset.architecture.lower()
        file_ = asset.primary_file
        filename = file_.filename if file_ is not None else ""
        return detect_architecture(filename)

    def verdict_for_asset(self, asset: DreamForgeAsset | None) -> CompatibilityVerdict:
        """Whether a Discover asset's architecture is supported locally."""
        arch = self.architecture_for_asset(asset)
        if not arch:
            return CompatibilityVerdict(
                supported=False,
                architecture="",
                supported_architectures=self.supported_architectures,
                capability_notes=["Unknown architecture — cannot verify compatibility"],
            )
        supported = self.is_supported_architecture(arch)
        notes: list[str] = []
        if supported:
            caps = sorted(self.capabilities_for_architecture(arch))
            notes.append(f"Supported: {arch} ({', '.join(caps)})")
        else:
            notes.append(f"Unsupported architecture: {arch}")
        return CompatibilityVerdict(
            supported=supported,
            architecture=arch,
            supported_architectures=self.supported_architectures,
            capability_notes=notes,
        )

    def explain_asset_for_request(
        self,
        asset: DreamForgeAsset | None,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Compatibility summary for a Discover card given a route request."""
        params = params or {}
        arch = self.architecture_for_asset(asset)
        model_payload: dict[str, Any] = {}
        file_ = asset.primary_file if asset is not None else None
        if file_ is not None:
            model_payload["engine_name"] = file_.filename
        model_payload["family"] = arch or asset.architecture if asset else ""
        required = required_capabilities_for_request(dict(params))
        supported = model_capabilities_for_model(model_payload, arch) if arch else set()
        missing = sorted(required - supported)
        verdict = self.verdict_for_asset(asset)
        return {
            "architecture": arch,
            "supported": verdict.supported,
            "capability_notes": verdict.capability_notes,
            "required_capabilities": sorted(required),
            "supported_capabilities": sorted(supported),
            "missing_capabilities": missing,
            "compatible": verdict.supported and not missing,
        }
