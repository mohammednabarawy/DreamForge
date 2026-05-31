from __future__ import annotations

from dreamforge_mode_contract import build_mode_contract


def test_generate_contract_preserves_user_model():
    contract = build_mode_contract(
        "generate",
        {"prompt": "product hero"},
        {"model": "my-model.safetensors", "prompt": "product hero"},
        source="local",
    )

    assert contract["model_policy"] == "preserve_user_model"
    assert contract["model_source"] == "user_selected"
    assert contract["selected_model"] == "my-model.safetensors"
    assert "model" in contract["preserved_fields"]


def test_edit_contract_marks_routed_model():
    contract = build_mode_contract(
        "edit",
        {
            "model": "flux1-dev-kontext_fp8_scaled.safetensors",
            "edit_type": "kontext",
            "input_image": "D:/image.png",
        },
        {"model": "sdxl.safetensors"},
        source="local",
    )

    assert contract["model_policy"] == "route_curated_model"
    assert contract["selected_model"] == "flux1-dev-kontext_fp8_scaled.safetensors"
    assert "model" in contract["changed_fields"]
    assert "edit_type" in contract["changed_fields"]

