"""Tests for reference image path coercion in Comfy routing helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_comfy_workflow_import import coerce_reference_image_paths, comfy_workflow_mode


def _is_kontext(model, model_family: str) -> bool:
    fam = (model_family or "").lower()
    if fam == "flux_kontext":
        return True
    return fam == "flux" and "kontext" in str(model.get("name", "")).lower()


def test_coerce_reference_images_from_list():
    job = SimpleNamespace(reference_images=["/a.png", "/b.png", "/a.png"])
    assert coerce_reference_image_paths(job) == ["/a.png", "/b.png"]


def test_coerce_reference_images_from_csv_string():
    job = SimpleNamespace(reference_images="/a.png, /b.png")
    assert coerce_reference_image_paths(job) == ["/a.png", "/b.png"]


def test_comfy_workflow_mode_kontext():
    mode = comfy_workflow_mode(
        input_filename="main.png",
        cn_type="None",
        model={"name": "flux1-kontext-dev.safetensors", "family": "flux_kontext"},
        model_family="flux_kontext",
        checkpoint_is_flux_kontext=_is_kontext,
    )
    assert mode == "kontext"
