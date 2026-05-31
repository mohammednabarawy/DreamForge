"""Tests for Krita-derived generation/edit recipes."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_krita_recipes import (
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


def test_qwen_model_params_low_vram_scale():
    params = qwen_model_params("qwen_image_edit", edit_type="qwen_edit", vram_profile="8gb")
    assert params["qwen_scale_megapixels"] == 0.75
