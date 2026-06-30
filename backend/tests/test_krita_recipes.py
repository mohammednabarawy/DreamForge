"""Tests for Krita-derived generation/edit recipes."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_krita_recipes import (
    edit_recipe,
    generation_recipe,
    qwen_model_params,
    resolve_qwen_edit_mode,
)


def test_generation_recipe_qwen_image():
    recipe = generation_recipe("qwen_image")
    assert recipe is not None
    assert recipe["cfg"] == 2.5
    assert recipe["scheduler"] == "beta"


def test_resolve_qwen_edit_mode_auto_plus_with_refs():
    assert (
        resolve_qwen_edit_mode(
            model_family="qwen_image_edit",
            requested="auto",
            extra_reference_count=1,
        )
        == "plus"
    )
    assert (
        resolve_qwen_edit_mode(
            model_family="qwen_image_edit",
            requested="single",
            extra_reference_count=2,
        )
        == "single"
    )
    assert (
        resolve_qwen_edit_mode(
            model_family="qwen_image_edit",
            requested="raw",
            extra_reference_count=0,
        )
        == "raw_plus"
    )


def test_qwen_model_params_low_vram_scale():
    params = qwen_model_params("qwen_image_edit", edit_type="qwen_edit", vram_profile="8gb")
    assert params["qwen_scale_megapixels"] == 0.75


def test_qwen_edit_recipe_prefers_local_q4_gguf_and_lightning_defaults():
    recipe = edit_recipe("qwen_image_edit", "qwen_edit")
    assert recipe is not None
    assert recipe["checkpoints"][0] == "qwen-image-edit-2511-Q4_K_M.gguf"
    assert recipe["custom_steps"] == 8
    assert recipe["cfg"] == 1.0
    assert recipe["scheduler"] == "simple"
    assert recipe["qwen_lightning_strength"] == 0.75
    assert recipe["max_reference_images"] == 3


def test_qwen_edit_recipe_lightning_4step():
    recipe = edit_recipe("qwen_image_edit", "lightning_4step")
    assert recipe is not None
    assert "qwen_image_edit_2511_fp8_e4m3fn_scaled_lightning_comfyui_4steps_v1.0.safetensors" in recipe["checkpoints"]
    assert recipe["custom_steps"] == 4
    assert recipe["cfg"] == 1.0
    assert recipe["qwen_lightning_strength"] == 1.0
    assert recipe["max_reference_images"] == 3
