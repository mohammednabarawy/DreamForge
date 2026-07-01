"""Route matrix: studio_mode × reference_role × model_family → comfy_mode."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import pytest

from dreamforge_auto_enhance import apply_auto_enhance_to_job
from dreamforge_comfy_workflow_import import comfy_workflow_mode
from dreamforge_feature_surfaces import COMFY_MODE_GRAPH_BUILDERS
from dreamforge_identity import apply_identity_to_job
from dreamforge_inpaint_intent import resolve_inpaint_intent_params
from dreamforge_upscale_presets import apply_upscale_preset_to_job
from dreamforge_vary_image import apply_vary_amount_to_job
from dreamforge_workflow_routing import (
    checkpoint_is_flux_kontext,
    resolve_comfy_workflow_mode,
    resolve_input_routing,
)


def _route_comfy_mode(job, *, model: dict, family: str, studio_mode: str) -> str:
    route = resolve_input_routing(
        job,
        model=model,
        model_family=family,
        studio_mode=studio_mode,
    )
    return resolve_comfy_workflow_mode(
        route,
        model=model,
        model_family=family,
        input_filename=route.input_path,
    )


ROUTE_MATRIX = [
    {
        "id": "generate_txt2img",
        "studio_mode": "generate",
        "job": {},
        "model": {"name": "z_image.safetensors"},
        "family": "z_image",
        "input": None,
        "expected": "txt2img",
    },
    {
        "id": "generate_restyle_img2img",
        "studio_mode": "generate",
        "job": {
            "reference_role": "restyle",
            "workflow_mode": "generate",
            "input_image": "/tmp/ref.png",
            "cn_type": "img2img",
        },
        "model": {"name": "z_image.safetensors"},
        "family": "z_image",
        "input": "/tmp/ref.png",
        "expected": "img2img",
    },
    {
        "id": "generate_image_prompt",
        "studio_mode": "generate",
        "job": {
            "reference_role": "image_prompt",
            "reference_image": "/tmp/ref.png",
        },
        "model": {"name": "sdxl.safetensors"},
        "family": "sdxl",
        "input": "/tmp/ref.png",
        "expected": "ipadapter",
    },
    {
        "id": "generate_structure_controlnet",
        "studio_mode": "generate",
        "job": {
            "reference_role": "structure",
            "reference_image": "/tmp/struct.png",
            "structure_type": "canny",
        },
        "model": {"name": "sdxl.safetensors"},
        "family": "sdxl",
        "input": "/tmp/struct.png",
        "expected": "controlnet",
    },
    {
        "id": "edit_kontext",
        "studio_mode": "edit",
        "job": {
            "reference_role": "source_edit",
            "input_image": "/tmp/src.png",
            "edit_type": "kontext",
        },
        "model": {"name": "flux1-dev-kontext_fp8_scaled.safetensors"},
        "family": "flux_kontext",
        "input": "/tmp/src.png",
        "expected": "kontext",
    },
    {
        "id": "edit_photo_restore",
        "studio_mode": "edit",
        "job": {
            "edit_task": "photo_restore",
            "input_image": "/tmp/old.png",
            "edit_type": "auto",
        },
        "model": {"name": "epicrealismXL.safetensors"},
        "family": "sdxl",
        "input": "/tmp/old.png",
        "expected": "photo_restore",
    },
    {
        "id": "edit_outfit_transfer",
        "studio_mode": "edit",
        "job": {
            "edit_task": "outfit_transfer",
            "input_image": "/tmp/person.png",
            "reference_images": ["/tmp/outfit.png"],
            "reference_role": "source_edit",
            "edit_type": "qwen_edit",
        },
        "model": {"name": "qwen-image-edit-2511-Q4_K_M.gguf"},
        "family": "qwen_image_edit",
        "input": "/tmp/person.png",
        "expected": "qwen_edit",
    },
    {
        "id": "edit_cutout_compose",
        "studio_mode": "edit",
        "job": {
            "edit_task": "cutout_compose",
            "input_image": "/tmp/subject.png",
            "reference_images": ["/tmp/background.png"],
            "reference_role": "source_edit",
            "edit_type": "qwen_edit",
        },
        "model": {"name": "qwen-image-edit-2511-Q4_K_M.gguf"},
        "family": "qwen_image_edit",
        "input": "/tmp/subject.png",
        "expected": "cutout_compose",
    },
    {
        "id": "inpaint_fill",
        "studio_mode": "inpaint",
        "job": {
            "reference_role": "inpaint",
            "input_image": "/tmp/src.png",
            "inpaint_mask_path": "/tmp/mask.png",
            "inpaint_intent": "default",
        },
        "model": {"name": "flux1-fill-dev-fp8.safetensors"},
        "family": "flux_fill",
        "input": "/tmp/src.png",
        "expected": "inpaint",
    },
    {
        "id": "upscale_mode",
        "studio_mode": "upscale",
        "job": {
            "reference_role": "upscale",
            "upscale_image": "/tmp/src.png",
            "upscale_preset": "2x",
        },
        "model": {"name": "sdxl.safetensors"},
        "family": "sdxl",
        "input": "/tmp/src.png",
        "expected": "upscale",
    },
    {
        "id": "face_detail_auto_enhance",
        "studio_mode": "upscale",
        "job": {
            "enhance_target": "face",
            "upscale_image": "/tmp/portrait.png",
        },
        "model": {"name": "sdxl.safetensors"},
        "family": "sdxl",
        "input": "/tmp/portrait.png",
        "expected": "face_detail",
        "preprocess": lambda job: apply_auto_enhance_to_job(job),
    },
    {
        "id": "identity_preserve_face",
        "studio_mode": "generate",
        "job": {
            "preserve_character": True,
            "input_image": "/tmp/face.png",
            "reference_image": "/tmp/face.png",
        },
        "model": {"name": "flux1-dev-kontext_fp8_scaled.safetensors"},
        "family": "flux_kontext",
        "input": "/tmp/face.png",
        "expected": "kontext",
        "preprocess": lambda job: apply_identity_to_job(job),
    },
]


@pytest.mark.parametrize("case", ROUTE_MATRIX, ids=[c["id"] for c in ROUTE_MATRIX])
def test_route_matrix_comfy_mode(case, monkeypatch):
    if case["id"] == "identity_preserve_face":
        monkeypatch.setattr(
            "dreamforge_identity._pick_kontext_checkpoint",
            lambda: "flux1-dev-kontext_fp8_scaled.safetensors",
        )
    job = SimpleNamespace(**case["job"])
    preprocess = case.get("preprocess")
    if preprocess:
        preprocess(job)
    mode = _route_comfy_mode(
        job,
        model=case["model"],
        family=case["family"],
        studio_mode=case["studio_mode"],
    )
    assert mode == case["expected"]


@pytest.mark.parametrize("mode,builder", sorted(COMFY_MODE_GRAPH_BUILDERS.items()))
def test_comfy_graph_builder_symbols_exist(mode, builder):
    import dreamforge_comfy_workflows as workflows

    assert hasattr(workflows, builder), f"{mode} -> {builder}"


def test_vary_amount_maps_to_img2img():
    job = SimpleNamespace(vary_amount="subtle", input_image="/tmp/out.png")
    patch = apply_vary_amount_to_job(job)
    for key, value in patch.items():
        setattr(job, key, value)
    mode = _route_comfy_mode(
        job,
        model={"name": "z_image.safetensors"},
        family="z_image",
        studio_mode="generate",
    )
    assert mode == "img2img"


def test_upscale_preset_applies_fields():
    job = SimpleNamespace(upscale_preset="fast_2x")
    patch = apply_upscale_preset_to_job(job)
    assert patch["upscale_by"] == 2.0
    assert patch["steps"] == 12


@pytest.mark.parametrize(
    "intent",
    ["default", "improve_detail", "modify_content"],
)
def test_inpaint_intent_presets(intent):
    job = SimpleNamespace(inpaint_intent=intent)
    params = resolve_inpaint_intent_params(job)
    assert "edit_strength" in params


def test_feature_surface_audit_clean():
    from dreamforge_feature_surfaces import (
        audit_frontend_surface_tokens,
        run_feature_surface_audit,
    )

    issues = run_feature_surface_audit() + audit_frontend_surface_tokens()
    assert not issues, "\n".join(issues)
