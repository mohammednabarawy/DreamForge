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
    engine_name: str = "",
    upscale_image: str | None = None,
) -> tuple[str, str, str]:
    """Mirror dreamforge_generation.py routing without loading the engine."""
    cn_sel = cn_selection
    cn_t = cn_type
    ed = edit_type
    explicit_input = input_path
    effective_input = explicit_input or upscale_image
    is_upscale_job = bool(upscale_image) and not explicit_input

    def _is_flux_kontext_model(fam: str, eng: str) -> bool:
        fam = fam or ""
        eng_l = (eng or "").lower()
        return fam == "flux_kontext" or (
            fam == "flux" and "kontext" in eng_l
        )

    if not effective_input:
        if cn_sel == "Custom...":
            cn_sel = "None"
            cn_t = "None"
        if ed in ("kontext", "inpaint", "img2img", "qwen_edit"):
            ed = "auto"
    elif cn_sel == "None" and is_upscale_job:
        cn_sel = "Custom..."
        cn_t = "upscale"
    elif cn_sel == "None" and effective_input:
        if _is_flux_kontext_model(model_family, engine_name):
            cn_sel = "None"
            cn_t = "None"
        else:
            cn_sel = "Custom..."
            if ed not in ("auto", "kontext", "None", None, ""):
                cn_t = ed
            else:
                cn_t = "img2img"
    elif effective_input and cn_sel == "Custom...":
        if is_upscale_job:
            cn_t = "upscale"
        elif _is_flux_kontext_model(model_family, engine_name):
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
        input_path=None,
        upscale_image="/tmp/a.png",
        edit_type="auto",
    )
    assert sel == "Custom..."
    assert typ == "upscale"
    assert ed == "auto"


def test_preview_title_start_sampling_maps_to_sampling_phase():
    assert generation_phase_from_preview(-1, "Start sampling ...") == GEN_SAMPLING
    assert generation_phase_from_preview(-1, "Loading base model: x") == GEN_LOADING_MODELS


def test_studio_edit_generic_kontext_label_routes_img2img_for_base_flux():
    """UI uses edit_type 'kontext' for Edit tab; only real Kontext models clear CN routing."""
    sel, typ, ed = _route_input(
        input_path="/tmp/a.png",
        cn_selection="None",
        cn_type="None",
        edit_type="kontext",
        model_family="flux",
        engine_name="flux1-dev.safetensors",
    )
    assert sel == "Custom..."
    assert typ == "img2img"
    assert ed == "kontext"


def test_studio_edit_flux_kontext_keeps_cn_none_like_pipeline():
    sel, typ, ed = _route_input(
        input_path="/tmp/a.png",
        cn_selection="None",
        cn_type="None",
        edit_type="kontext",
        model_family="flux_kontext",
    )
    assert sel == "None"
    assert typ == "None"
    assert ed == "kontext"


def test_studio_upscale_uses_upscale_image_field():
    # run_generation coalesces upscale_image into input_path before routing.
    sel, typ, _ = _route_input(
        input_path=None,
        cn_selection="None",
        upscale_image="/tmp/a.png",
    )
    assert sel == "Custom..."
    assert typ == "upscale"


def test_stale_upscale_image_does_not_override_kontext_edit():
    sel, typ, ed = _route_input(
        input_path="/tmp/edit-source.png",
        cn_selection="None",
        cn_type="None",
        edit_type="auto",
        model_family="flux_kontext",
        upscale_image="/tmp/previous-upscale-source.png",
    )
    assert sel == "None"
    assert typ == "None"
    assert ed == "auto"


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


def test_generation_dry_run_preserves_explicit_user_model(monkeypatch):
    import dreamforge_cli_direct as cli

    selected = {
        "name": "juggernautXL_v8Rundiffusion.safetensors",
        "stem": "juggernautXL_v8Rundiffusion",
        "relative_path": "juggernautXL_v8Rundiffusion.safetensors",
        "path": "/models/juggernautXL_v8Rundiffusion.safetensors",
        "size_mb": 6776,
        "category": "checkpoints",
        "engine_name": "juggernautXL_v8Rundiffusion.safetensors",
        "family": "sdxl",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="juggernautXL_v8Rundiffusion.safetensors",
            prompt="cinematic portrait",
            negative_prompt="",
            aspect_ratio=None,
            width=None,
            height=None,
            seed=1,
            image_number=4,
            output=None,
            performance="Speed",
            steps=None,
            cfg_scale=None,
            sampler=None,
            scheduler=None,
            styles=None,
            lora=[],
            input_image=None,
            upscale_image=None,
            upscale_method="RealESRGAN_x2",
            edit_type="auto",
            edit_strength=None,
            vram_profile="5gb",
            use_case="none",
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

    assert plan["model"]["name"] == "juggernautXL_v8Rundiffusion.safetensors"
    assert plan["model"]["family"] == "sdxl"


def test_dry_run_reports_companion_download_and_switch_actions(monkeypatch):
    import dreamforge_cli_direct as cli
    import dreamforge_cli_inventory as inv
    from dreamforge_model_registry import ModelCapabilities

    qwen = {
        "name": "Qwen_Image_Edit-Q3_K_M.gguf",
        "stem": "Qwen_Image_Edit-Q3_K_M",
        "relative_path": "Qwen_Image_Edit-Q3_K_M.gguf",
        "path": "/models/Qwen_Image_Edit-Q3_K_M.gguf",
        "size_mb": 9231,
        "category": "diffusion_models",
        "engine_name": "../diffusion_models/Qwen_Image_Edit-Q3_K_M.gguf",
        "family": "qwen_image_edit",
    }
    fallback = {
        "name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "engine_name": "../diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors",
        "category": "diffusion_models",
        "family": "flux_kontext",
        "estimated_vram_gb": 10.8,
        "effective_vram_profile": "16gb",
    }
    missing = [{"id": "clip_qwen25_edit_gguf", "name": "qwen_2.5_vl_7b_edit-q2_k.gguf"}]

    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: qwen)
    monkeypatch.setattr(inv, "check_model_dependencies", lambda model: missing if model["family"] == "qwen_image_edit" else [])
    monkeypatch.setattr(inv, "get_fallback_model", lambda *_args, **_kwargs: fallback)

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="Qwen_Image_Edit-Q3_K_M.gguf",
            prompt="preserve poster text",
            negative_prompt="",
            aspect_ratio=None,
            width=None,
            height=None,
            seed=1,
            image_number=1,
            output=None,
            performance="Quality",
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
            vram_profile="16gb",
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

    actions = plan["recommended_actions"]
    assert plan["ready"] is False
    assert actions[0]["action"] == "download_model_companions"
    assert actions[0]["missing"][0]["id"] == "clip_qwen25_edit_gguf"
    assert actions[1]["action"] == "switch_model"
    assert actions[1]["family"] == "flux_kontext"
    assert ModelCapabilities.QWEN_SEMANTIC_EDIT


def test_dry_run_reports_krita_kontext_recipe():
    from dreamforge_cli_direct import build_plan

    plan = build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="flux1-dev-kontext_fp8_scaled",
            prompt="change the outfit",
            negative_prompt="",
            aspect_ratio=None,
            width=None,
            height=None,
            seed=1,
            image_number=1,
            output=None,
            performance="Flux",
            steps=None,
            cfg_scale=None,
            sampler=None,
            scheduler=None,
            styles=None,
            lora=[],
            input_image="/tmp/reference.png",
            upscale_image=None,
            upscale_method="RealESRGAN_x2",
            edit_type="kontext",
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

    assert plan["settings"]["steps"] == 20
    assert plan["settings"]["cfg"] == 3.5
    assert plan["settings"]["sampler"] == "euler"
    assert plan["settings"]["scheduler"] == "simple"


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


def test_flux_kontext_uses_krita_edit_recipe(monkeypatch):
    monkeypatch.chdir(_BACKEND)
    from dreamforge_generation import _tune_edit_job_settings

    job = SimpleNamespace(
        performance="Flux",
        steps=None,
        cfg_scale=None,
        sampler=None,
        scheduler=None,
        edit_type="kontext",
        input_image="/tmp/reference.png",
        upscale_image=None,
    )

    out = _tune_edit_job_settings(
        {
            "performance_selection": "Flux",
            "steps": 16,
            "cfg": 3.0,
            "sampler_name": "euler",
            "scheduler": "beta",
            "clip_skip": 1,
        },
        job,
        "flux_kontext",
    )

    assert out["steps"] == 20
    assert out["cfg"] == 3.5
    assert out["sampler_name"] == "euler"
    assert out["scheduler"] == "simple"


def test_flux_kontext_live_preview_uses_krita_live_steps(monkeypatch):
    monkeypatch.chdir(_BACKEND)
    from dreamforge_generation import _tune_edit_job_settings

    job = SimpleNamespace(
        performance="Flux",
        steps=None,
        cfg_scale=None,
        sampler=None,
        scheduler=None,
        edit_type="kontext",
        input_image="/tmp/reference.png",
        upscale_image=None,
    )

    out = _tune_edit_job_settings(
        {
            "performance_selection": "Flux",
            "steps": 16,
            "cfg": 3.0,
            "sampler_name": "euler",
            "scheduler": "beta",
            "clip_skip": 1,
        },
        job,
        "flux_kontext",
        is_live=True,
    )

    assert out["steps"] == 8
    assert out["cfg"] == 3.5


def test_krita_recipe_catalog_exposes_comfy_install_requirements():
    from dreamforge_krita_recipes import COMFY_INSTALL_RECIPE, edit_recipe, live_sampling_params

    recipe = edit_recipe("flux_kontext", "kontext")
    assert recipe is not None
    assert "flux1-dev-kontext_fp8_scaled.safetensors" in recipe["checkpoints"]
    live = live_sampling_params("flux_kontext", "kontext")
    assert live is not None
    assert live["steps"] == 8
    required_ids = {node["id"] for node in COMFY_INSTALL_RECIPE["required_custom_nodes"]}
    assert "comfyui-inpaint-nodes" in required_ids
    assert "comfyui-tooling-nodes" in required_ids
    assert COMFY_INSTALL_RECIPE.get("comfy_version")
    assert all(node.get("version") for node in COMFY_INSTALL_RECIPE["required_custom_nodes"])


def test_edit_strength_is_clamped_for_kontext():
    from dreamforge_generation import _clamp_float

    assert _clamp_float(1.5, 1.0, 0.0, 1.0) == 1.0
    assert _clamp_float("bad", 1.0, 0.0, 1.0) == 1.0
