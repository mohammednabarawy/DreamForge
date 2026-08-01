from dreamforge_assets import (
    AssetFile,
    AssetKind,
    AssetVersion,
    DreamForgeAsset,
    Provenance,
)
from dreamforge_capability_registry import (
    CapabilityRegistry,
    SUPPORTED_ARCHITECTURES,
)
from dreamforge_model_registry import ModelCapabilities


def _asset(architecture="", filename="model.safetensors", kind=AssetKind.CHECKPOINT):
    return DreamForgeAsset(
        id="civitai:1",
        architecture=architecture,
        kind=kind,
        versions=[AssetVersion(id="v1", files=[AssetFile(filename=filename, sha256="a" * 64)])],
        provenance=Provenance(provider="civitai", provider_asset_id="1"),
    )


def test_supported_architectures_include_current_families():
    registry = CapabilityRegistry()
    assert "sdxl" in registry.supported_architectures
    assert "flux" in registry.supported_architectures
    assert registry.is_supported_architecture("sdxl")
    assert registry.is_supported_architecture("SDXL")  # case-insensitive
    assert not registry.is_supported_architecture("midjourney")


def test_verdict_supported_for_known_architecture():
    registry = CapabilityRegistry()
    verdict = registry.verdict_for_asset(_asset(architecture="sdxl"))
    assert verdict.supported is True
    assert verdict.architecture == "sdxl"
    assert any("Supported" in note for note in verdict.capability_notes)


def test_verdict_unsupported_for_unknown_architecture():
    registry = CapabilityRegistry()
    verdict = registry.verdict_for_asset(_asset(architecture="nothing"))
    assert verdict.supported is False
    assert any("Unsupported" in note for note in verdict.capability_notes)
    # Registered on the fly via the extension point (plan §31.18).
    registry.register_architecture("nothing", {ModelCapabilities.TEXT_TO_IMAGE})
    assert registry.is_supported_architecture("nothing")


def test_verdict_unknown_when_no_architecture_and_no_heuristic():
    registry = CapabilityRegistry()
    verdict = registry.verdict_for_asset(_asset(architecture="", filename="mystery.bin"))
    assert verdict.supported is False
    assert any("Unknown architecture" in note for note in verdict.capability_notes)


def test_architecture_detected_from_filename_when_missing():
    registry = CapabilityRegistry()
    assert registry.architecture_for_asset(_asset(architecture="", filename="sd_xl_base.safetensors")) == "sdxl"
    assert registry.architecture_for_asset(None) == ""


def test_capabilities_inherit_from_family_map():
    registry = CapabilityRegistry()
    caps = registry.capabilities_for_architecture("flux")
    assert ModelCapabilities.TEXT_TO_IMAGE in caps
    # Supported arch always gains text-to-image.
    caps_sdxl = registry.capabilities_for_architecture("sdxl")
    assert ModelCapabilities.TEXT_TO_IMAGE in caps_sdxl


def test_register_architecture_adds_support_and_capabilities():
    registry = CapabilityRegistry()
    registry.register_architecture("kling", {ModelCapabilities.IMAGE_TO_IMAGE})
    assert registry.is_supported_architecture("kling")
    assert ModelCapabilities.IMAGE_TO_IMAGE in registry.capabilities_for_architecture("kling")
    assert ModelCapabilities.TEXT_TO_IMAGE in registry.capabilities_for_architecture("kling")


def test_explain_asset_for_request_marks_compatible():
    registry = CapabilityRegistry()
    report = registry.explain_asset_for_request(
        _asset(architecture="sdxl", filename="juggernautxl.safetensors"),
        {"edit_type": "text_to_image"},
    )
    assert report["architecture"] == "sdxl"
    assert report["supported"] is True
    assert report["compatible"] is True
    assert report["missing_capabilities"] == []


def test_explain_asset_for_request_reports_missing_capability():
    registry = CapabilityRegistry()
    # Base flux lacks the native INPAINT capability (see FAMILY_CAPABILITIES).
    report = registry.explain_asset_for_request(
        _asset(architecture="flux", filename="flux1-dev.safetensors"),
        {"edit_type": "inpaint", "inpaint_mask_path": "/tmp/mask.png"},
    )
    assert report["supported"] is True
    assert report["compatible"] is False
    assert ModelCapabilities.INPAINT in report["missing_capabilities"]