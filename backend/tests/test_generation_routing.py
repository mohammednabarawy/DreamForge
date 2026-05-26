"""Unit tests for input-image routing rules (no GPU)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_progress import (
    GEN_LOADING_MODELS,
    GEN_SAMPLING,
    generation_phase_from_preview,
)


def _route_input(
    *,
    input_path: str | None,
    cn_selection: str = "None",
    cn_type: str = "None",
    edit_type: str = "auto",
    model_family: str = "",
    upscale_image: str | None = None,
) -> tuple[str, str, str]:
    """Mirror dreamforge_generation.py routing without loading the engine."""
    cn_sel = cn_selection
    cn_t = cn_type
    ed = edit_type

    if not input_path:
        if cn_sel == "Custom...":
            cn_sel = "None"
            cn_t = "None"
        if ed in ("kontext", "inpaint", "img2img", "qwen_edit"):
            ed = "auto"
    elif cn_sel == "None" and upscale_image:
        cn_sel = "Custom..."
        cn_t = "upscale"
    elif cn_sel == "None" and input_path:
        if ed == "kontext" or model_family == "flux_kontext":
            cn_sel = "None"
            cn_t = "None"
        else:
            cn_sel = "Custom..."
            cn_t = ed if ed not in ("auto", "None", None, "") else "img2img"
    elif input_path and cn_sel == "Custom...":
        if upscale_image:
            cn_t = "upscale"
        elif ed == "kontext" or model_family == "flux_kontext":
            cn_sel = "None"
            cn_t = "None"
        elif ed not in ("auto", "None", None, ""):
            cn_t = ed

    return cn_sel, cn_t, ed


def test_txt2img_clears_custom_cn():
    sel, typ, ed = _route_input(input_path=None)
    assert sel == "None"
    assert typ == "None"
    assert ed == "auto"


def test_reference_enables_img2img():
    sel, typ, _ = _route_input(input_path="/tmp/a.png", cn_selection="None")
    assert sel == "Custom..."
    assert typ == "img2img"


def test_flux_kontext_keeps_cn_none():
    sel, typ, _ = _route_input(
        input_path="/tmp/a.png",
        edit_type="kontext",
        model_family="flux_kontext",
    )
    assert sel == "None"
    assert typ == "None"


def test_qwen_edit_routes_to_qwen_control_type():
    sel, typ, ed = _route_input(
        input_path="/tmp/a.png",
        cn_selection="Custom...",
        cn_type="img2img",
        edit_type="qwen_edit",
        model_family="qwen_image_edit",
    )
    assert sel == "Custom..."
    assert typ == "qwen_edit"
    assert ed == "qwen_edit"


def test_inpaint_routes_to_inpaint_control_type():
    sel, typ, ed = _route_input(
        input_path="/tmp/a.png",
        cn_selection="Custom...",
        cn_type="img2img",
        edit_type="inpaint",
    )
    assert sel == "Custom..."
    assert typ == "inpaint"
    assert ed == "inpaint"


def test_upscale_image_routes_to_upscale_control_type():
    sel, typ, ed = _route_input(
        input_path="/tmp/a.png",
        upscale_image="/tmp/a.png",
        edit_type="auto",
    )
    assert sel == "Custom..."
    assert typ == "upscale"
    assert ed == "auto"


def test_preview_title_start_sampling_maps_to_sampling_phase():
    assert generation_phase_from_preview(-1, "Start sampling ...") == GEN_SAMPLING
    assert generation_phase_from_preview(-1, "Loading base model: x") == GEN_LOADING_MODELS


def test_studio_edit_kontext_uses_cn_none():
    """Studio Edit tab + reference attach should not force img2img ControlNet."""
    sel, typ, ed = _route_input(
        input_path="/tmp/a.png",
        cn_selection="None",
        cn_type="None",
        edit_type="kontext",
    )
    assert sel == "None"
    assert typ == "None"
    assert ed == "kontext"


def test_studio_upscale_uses_upscale_image_field():
    # run_generation coalesces upscale_image into input_path before routing.
    sel, typ, _ = _route_input(
        input_path="/tmp/a.png",
        cn_selection="None",
        upscale_image="/tmp/a.png",
    )
    assert sel == "Custom..."
    assert typ == "upscale"


def test_dry_run_accepts_explicit_qwen_edit_model_name():
    from dreamforge_cli_direct import build_plan

    plan = build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="qwen-image-edit",
            prompt="preserve Arabic poster text",
            negative_prompt="",
            aspect_ratio=None,
            width=None,
            height=None,
            seed=1,
            image_number=1,
            output=None,
            performance="Speed",
            steps=None,
            cfg_scale=None,
            sampler=None,
            scheduler=None,
            styles=None,
            lora=[],
            input_image="/tmp/reference.png",
            upscale_image=None,
            upscale_method="RealESRGAN_x2",
            edit_type="qwen_edit",
            edit_strength=None,
            vram_profile="auto",
            use_case="image_edit",
            brand_kit=None,
            subject=None,
            composition=None,
            lighting=None,
            camera=None,
            brand_colors=None,
            materials=None,
            visual_style=None,
            validate_output=False,
            no_manifest=False,
        )
    )

    assert plan["model"]["family"] == "qwen_image_edit"
    assert plan["input_image"] == "/tmp/reference.png"


def test_performance_presets_do_not_override_explicit_sampling(monkeypatch):
    monkeypatch.chdir(_BACKEND)
    from dreamforge_generation import _apply_job_performance, _tune_edit_job_settings

    job = SimpleNamespace(
        performance="Flux",
        steps=2,
        cfg_scale=2.5,
        sampler="euler",
        scheduler="normal",
        edit_type="kontext",
        input_image="/tmp/reference.png",
        upscale_image=None,
    )

    out = _apply_job_performance(
        {
            "performance_selection": "Flux",
            "steps": 20,
            "cfg": 3.0,
            "sampler_name": "euler",
            "scheduler": "beta",
            "clip_skip": 1,
        },
        job,
    )
    out = _tune_edit_job_settings(out, job, "flux_kontext")

    assert out["steps"] == 2
    assert out["cfg"] == 2.5
    assert out["scheduler"] == "normal"
    assert out["performance_selection"] == "Custom..."


def test_edit_strength_is_clamped_for_kontext():
    from dreamforge_generation import _clamp_float

    assert _clamp_float(1.5, 0.98, 0.0, 1.0) == 1.0
    assert _clamp_float("bad", 0.98, 0.0, 1.0) == 0.98
