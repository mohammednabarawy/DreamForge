"""Tests for edit model routing helpers."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_edit_routing import (
    controlnet_supports_sdxl_checkpoint,
    edit_routing_for_model,
    model_supports_edit,
    model_supports_img2img_edit,
    model_supports_kontext_edit,
    model_supports_qwen_edit,
    model_supports_sdxl_union_toolbox,
    pick_best_sdxl_toolbox_model,
    pick_sdxl_union_controlnet,
)


def test_kontext_edit_routing():
    model = {
        "name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "family": "flux_kontext",
    }
    assert model_supports_kontext_edit(model, "flux_kontext")
    patch = edit_routing_for_model(model, "flux_kontext")
    assert patch["edit_type"] == "kontext"


def test_qwen_edit_routing():
    model = {
        "name": "qwen-image-edit-2511-Q4_K_M.gguf",
        "family": "qwen_image_edit",
    }
    assert model_supports_qwen_edit(model, "qwen_image_edit")
    patch = edit_routing_for_model(model, "qwen_image_edit")
    assert patch["edit_type"] == "qwen_edit"


def test_flux_dev_img2img_edit_routing():
    model = {
        "name": "flux1-dev-fp8.safetensors",
        "family": "flux",
    }
    assert model_supports_img2img_edit(model, "flux")
    assert model_supports_edit(model, "flux")
    patch = edit_routing_for_model(model, "flux")
    assert patch["edit_type"] == "img2img"


def test_sdxl_union_toolbox_support():
    sdxl = {"name": "epicrealismXL_vxviLastfameRealism.safetensors", "family": "sdxl"}
    flux = {"name": "flux1-dev-fp8.safetensors", "family": "flux"}
    assert model_supports_sdxl_union_toolbox(sdxl, "sdxl")
    assert not model_supports_sdxl_union_toolbox(flux, "flux")


def test_pick_best_sdxl_toolbox_model_prefers_sdxl():
    gallery = [
        {"engine_name": "flux1-dev-fp8.safetensors", "family": "flux"},
        {"engine_name": "juggernautXL_v9.safetensors", "family": "sdxl"},
    ]
    assert pick_best_sdxl_toolbox_model(gallery) == "juggernautXL_v9.safetensors"


def test_controlnet_supports_sdxl_checkpoint():
    assert controlnet_supports_sdxl_checkpoint("xinsir-controlnet-union-sdxl-1.0-promax.safetensors")
    assert not controlnet_supports_sdxl_checkpoint("control_v11p_sd15_canny_fp16.safetensors")


def test_pick_sdxl_union_controlnet_prefers_union(monkeypatch):
    from dreamforge_edit_routing import controlnet_supports_sdxl_checkpoint, pick_sdxl_union_controlnet

    def fake_inventory():
        return {
            "categories": {
                "controlnet": [
                    {"name": "control_v11p_sd15_canny_fp16.safetensors"},
                    {"name": "controlnet-canny-sdxl.safetensors"},
                    {"name": "xinsir-controlnet-union-sdxl-1.0-promax.safetensors"},
                ]
            }
        }

    monkeypatch.setattr(
        "dreamforge_cli_inventory.list_model_inventory",
        fake_inventory,
    )
    assert pick_sdxl_union_controlnet() == "xinsir-controlnet-union-sdxl-1.0-promax.safetensors"
    assert controlnet_supports_sdxl_checkpoint("control_v11p_sd15_depth.safetensors") is False
