from dreamforge_model_registry import (
    ModelCapabilities,
    explain_model_capability_match,
    model_capabilities_for_model,
)


def test_model_capabilities_recognize_edit_family_hints():
    qwen_caps = model_capabilities_for_model(
        {"engine_name": "Qwen_Image_Edit-Q3_K_M.gguf"},
        "qwen_image",
    )
    assert ModelCapabilities.QWEN_SEMANTIC_EDIT in qwen_caps
    assert ModelCapabilities.IMAGE_TO_IMAGE in qwen_caps

    kontext_caps = model_capabilities_for_model(
        {"engine_name": "flux1-dev-kontext_fp8_scaled.safetensors"},
        "flux",
    )
    assert ModelCapabilities.KONTEXT_EDIT in kontext_caps
    assert ModelCapabilities.IMAGE_TO_IMAGE in kontext_caps

    fill_caps = model_capabilities_for_model(
        {"engine_name": "flux-fill-dev.safetensors"},
        "flux",
    )
    assert ModelCapabilities.FLUX_FILL_INPAINT in fill_caps
    assert ModelCapabilities.INPAINT in fill_caps


def test_model_capability_explanation_for_inpaint_route():
    report = explain_model_capability_match(
        {"edit_type": "inpaint", "inpaint_mask_path": "/tmp/mask.png"},
        {"engine_name": "flux-fill-dev.safetensors", "family": "flux"},
        "flux",
    )
    assert report["compatible"] is True
    assert report["missing"] == []
    assert ModelCapabilities.INPAINT in report["required"]


def test_model_capability_explanation_accepts_sdxl_inpaint():
    report = explain_model_capability_match(
        {"edit_type": "inpaint", "inpaint_mask_path": "/tmp/mask.png"},
        {"engine_name": "juggernautxl_inpaint.safetensors", "family": "sdxl"},
        "sdxl",
    )
    assert report["compatible"] is True
    assert report["missing"] == []


def test_model_capability_explanation_reports_incompatible_inpaint_model():
    report = explain_model_capability_match(
        {"edit_type": "inpaint", "inpaint_mask_path": "/tmp/mask.png"},
        {"engine_name": "qwen-image.safetensors", "family": "qwen_image"},
        "qwen_image",
    )
    assert report["compatible"] is False
    assert ModelCapabilities.INPAINT in report["missing"]
