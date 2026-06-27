"""Tests for edit model routing helpers."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_edit_routing import (
    edit_routing_for_model,
    model_supports_edit,
    model_supports_img2img_edit,
    model_supports_kontext_edit,
    model_supports_qwen_edit,
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
