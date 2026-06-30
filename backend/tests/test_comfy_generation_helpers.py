"""Tests for reference image path coercion in Comfy routing helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_comfy_workflow_import import coerce_reference_image_paths, comfy_workflow_mode
from dreamforge_generation import (
    _checkpoint_is_flux_fill,
    _checkpoint_is_flux_kontext,
    clamp_flux_fill_inpaint_denoise,
)


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


def test_comfy_workflow_mode_respects_explicit_workflow_mode():
    assert (
        comfy_workflow_mode(
            input_filename=None,
            cn_type="None",
            model={"name": "sdxl.safetensors"},
            model_family="sdxl",
            checkpoint_is_flux_kontext=_is_kontext,
            workflow_mode="hires",
        )
        == "hires"
    )
    assert (
        comfy_workflow_mode(
            input_filename="main.png",
            cn_type="img2img",
            model={"name": "sdxl.safetensors"},
            model_family="sdxl",
            checkpoint_is_flux_kontext=_is_kontext,
            workflow_mode="controlnet",
        )
        == "controlnet"
    )
    assert (
        comfy_workflow_mode(
            input_filename=None,
            cn_type="None",
            model={"name": "sdxl.safetensors"},
            model_family="sdxl",
            checkpoint_is_flux_kontext=_is_kontext,
            workflow_mode="area_composition",
        )
        == "area_composition"
    )
    assert (
        comfy_workflow_mode(
            input_filename="main.png",
            cn_type="None",
            model={"name": "sdxl.safetensors"},
            model_family="sdxl",
            checkpoint_is_flux_kontext=_is_kontext,
            workflow_mode="face_detail",
        )
        == "face_detail"
    )
    assert (
        comfy_workflow_mode(
            input_filename=None,
            cn_type="reference",
            model={"name": "sdxl.safetensors"},
            model_family="sdxl",
            checkpoint_is_flux_kontext=_is_kontext,
            workflow_mode="generate",
        )
        == "ipadapter"
    )
    assert (
        comfy_workflow_mode(
            input_filename="main.png",
            cn_type="reference",
            model={"name": "z_image_turbo_nvfp4.safetensors"},
            model_family="z_image",
            checkpoint_is_flux_kontext=_is_kontext,
            workflow_mode="generate",
        )
        == "img2img"
    )
    assert (
        comfy_workflow_mode(
            input_filename="main.png",
            cn_type="reference",
            model={"name": "sdxl.safetensors"},
            model_family="sdxl",
            checkpoint_is_flux_kontext=_is_kontext,
            workflow_mode="reference",
        )
        == "img2img"
    )


def test_comfy_workflow_mode_hidream_o1_references_use_native_node():
    mode = comfy_workflow_mode(
        input_filename=None,
        cn_type="None",
        model={"name": "hidream_o1_image_dev_mxfp8.safetensors", "family": "hidream_o1"},
        model_family="hidream_o1",
        checkpoint_is_flux_kontext=_is_kontext,
        workflow_mode="ipadapter",
    )
    assert mode == "hidream_reference"


def test_checkpoint_is_flux_fill():
    assert _checkpoint_is_flux_fill(
        {"name": "flux1-fill-dev-fp8.safetensors", "engine_name": "flux1-fill-dev-fp8.safetensors"},
        "flux_fill",
    )
    assert not _checkpoint_is_flux_fill(
        {"name": "qwen-image-edit-2511-Q4_K_M.gguf"},
        "qwen_image_edit",
    )


def test_comfy_workflow_mode_inpaint():
    mode = comfy_workflow_mode(
        input_filename="main.png",
        cn_type="inpaint",
        model={"name": "flux1-fill-dev-fp8.safetensors"},
        model_family="flux_fill",
        checkpoint_is_flux_kontext=_checkpoint_is_flux_kontext,
    )
    assert mode == "inpaint"


def test_comfy_workflow_mode_qwen_edit():
    mode = comfy_workflow_mode(
        input_filename="main.png",
        cn_type="None",
        edit_type="qwen_edit",
        model={"name": "qwen-image-edit-2511-Q4_K_M.gguf"},
        model_family="qwen_image_edit",
        checkpoint_is_flux_kontext=_checkpoint_is_flux_kontext,
    )
    assert mode == "qwen_edit"


def test_clamp_flux_fill_inpaint_denoise_floors_low_strength():
    model = {"name": "flux1-fill-dev-fp8.safetensors"}
    assert clamp_flux_fill_inpaint_denoise(
        0.52,
        is_inpaint_job=True,
        model=model,
        model_family="flux_fill",
    ) == 1.0
    assert clamp_flux_fill_inpaint_denoise(
        1.0,
        is_inpaint_job=True,
        model=model,
        model_family="flux_fill",
    ) == 1.0
    assert clamp_flux_fill_inpaint_denoise(
        0.52,
        is_inpaint_job=True,
        model={"name": "sdxl.safetensors"},
        model_family="sdxl",
    ) == 0.52
