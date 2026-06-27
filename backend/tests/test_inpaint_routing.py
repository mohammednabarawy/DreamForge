"""Tests for inpaint model routing helpers."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_inpaint_routing import (
    model_supports_inpaint,
    model_supports_native_inpaint,
    model_supports_flux_fill_inpaint,
    pick_best_inpaint_model,
    inpaint_workflow_kind,
)


def test_flux_fill_is_inpaint_capable():
    model = {
        "name": "FLUX.1-Fill-dev_fp8.safetensors",
        "family": "flux_fill",
        "engine_name": "FLUX.1-Fill-dev_fp8.safetensors",
    }
    assert model_supports_flux_fill_inpaint(model, "flux_fill")
    assert model_supports_inpaint(model, "flux_fill")
    assert inpaint_workflow_kind(model, "flux_fill") == "flux_fill"


def test_sdxl_inpaint_checkpoint_is_native_capable():
    model = {
        "name": "juggernautxl_inpaint.safetensors",
        "family": "sdxl",
        "engine_name": "juggernautxl_inpaint.safetensors",
    }
    assert model_supports_native_inpaint(model, "sdxl")
    assert model_supports_inpaint(model, "sdxl")
    assert inpaint_workflow_kind(model, "sdxl") == "native_inpaint"


def test_pick_best_inpaint_model_prefers_flux_fill_fp8():
    gallery = [
        {
            "name": "juggernautxl_inpaint.safetensors",
            "family": "sdxl",
            "engine_name": "juggernautxl_inpaint.safetensors",
        },
        {
            "name": "FLUX.1-Fill-dev_fp8.safetensors",
            "family": "flux_fill",
            "engine_name": "FLUX.1-Fill-dev_fp8.safetensors",
        },
    ]
    assert pick_best_inpaint_model(gallery) == "FLUX.1-Fill-dev_fp8.safetensors"
