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
from dreamforge_generation import _build_comfy_prompt_graph, _pid_upscale_target_size


def _route_input(
    *,
    input_path: str | None,
    cn_selection: str = "None",
    cn_type: str = "None",
    edit_type: str = "auto",
    model_family: str = "",
    engine_name: str = "",
    upscale_image: str | None = None,
    workflow_mode: str | None = None,
    reference_role: str | None = None,
) -> tuple[str, str, str]:
    """Resolve cn_selection/cn_type/edit_type via the central workflow router."""
    from dreamforge_workflow_routing import resolve_input_routing

    model = {"engine_name": engine_name, "name": engine_name, "family": model_family}
    job = SimpleNamespace(
        input_image=input_path,
        upscale_image=upscale_image,
        cn_selection=cn_selection,
        cn_type=cn_type,
        edit_type=edit_type,
        workflow_mode=workflow_mode,
        reference_role=reference_role,
        inpaint_mask_path=None,
    )
    route = resolve_input_routing(job, model=model, model_family=model_family)
    return route.cn_selection, route.cn_type, route.edit_type


def test_generate_explicit_restyle_routes_z_image_img2img():
    """Phase 6: Create + reference + Z-Image stays img2img, not edit/upscale."""
    sel, typ, ed = _route_input(
        input_path="/tmp/ref.png",
        reference_role="restyle",
        workflow_mode="generate",
        cn_selection="None",
        cn_type="None",
        edit_type="auto",
        upscale_image="/tmp/stale-upscale.png",
        model_family="z_image",
        engine_name="z_image_turbo_nvfp4.safetensors",
    )
    assert sel == "Custom..."
    assert typ == "img2img"
    assert ed == "auto"


def test_reference_cn_type_with_input_routes_img2img():
    sel, typ, _ = _route_input(
        input_path="/tmp/ref.png",
        cn_selection="Custom...",
        cn_type="reference",
        model_family="z_image",
        engine_name="z_image_turbo_nvfp4.safetensors",
    )
    assert sel == "Custom..."
    assert typ == "img2img"


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


def test_z_image_img2img_graph_uses_dedicated_builder():
    graph, _template = _build_comfy_prompt_graph(
        job=SimpleNamespace(),
        mode="img2img",
        model={"name": "z_image_turbo_nvfp4.safetensors", "category": "diffusion_models"},
        model_family="z_image",
        settings={
            "steps": 8,
            "cfg": 1.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "width": 1024,
            "height": 1024,
            "comfy_loras": [],
            "qwen_image_shift": 3.0,
        },
        prompt="portrait in sunlight",
        negative="",
        seed=42,
        edit_strength=0.35,
        cn_upscale="",
        input_filename="ref.png",
        mask_filename=None,
        reference_stitch_filename=None,
        grow_mask_by=0,
        model_loader_args={
            "ckpt_name": "z_image_turbo_nvfp4.safetensors",
            "relative_path": "z_image_turbo_nvfp4.safetensors",
            "category": "diffusion_models",
            "family": "z_image",
        },
    )
    assert any(n.get("class_type") == "VAEEncode" for n in graph.values())
    clip = next(n for n in graph.values() if n.get("class_type") == "CLIPLoader")
    assert clip["inputs"]["type"] == "lumina2"
    aura = next(n for n in graph.values() if n.get("class_type") == "ModelSamplingAuraFlow")
    assert aura["inputs"]["shift"] == 3.0


def test_flux_img2img_graph_uses_flux_guidance():
    graph, _template = _build_comfy_prompt_graph(
        job=SimpleNamespace(),
        mode="img2img",
        model={"name": "flux1-dev.safetensors", "category": "diffusion_models"},
        model_family="flux",
        settings={
            "steps": 20,
            "cfg": 3.5,
            "sampler_name": "euler",
            "scheduler": "simple",
            "width": 1024,
            "height": 1024,
            "comfy_loras": [],
        },
        prompt="a knight in a forest",
        negative="",
        seed=7,
        edit_strength=0.7,
        cn_upscale="",
        input_filename="ref.png",
        mask_filename=None,
        reference_stitch_filename=None,
        grow_mask_by=0,
        model_loader_args={
            "ckpt_name": "flux1-dev.safetensors",
            "relative_path": "flux1-dev.safetensors",
            "category": "diffusion_models",
            "family": "flux",
        },
    )
    assert any(n.get("class_type") == "VAEEncode" for n in graph.values())
    guidance = next(n for n in graph.values() if n.get("class_type") == "FluxGuidance")
    assert guidance["inputs"]["guidance"] == 3.5
    sampler = next(n for n in graph.values() if n.get("class_type") == "KSampler")
    assert sampler["inputs"]["cfg"] == 1.0
    assert sampler["inputs"]["denoise"] == 0.7


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


def test_qwen_single_edit_with_extra_references_uses_main_uploaded_image_only():
    graph, _template = _build_comfy_prompt_graph(
        job=SimpleNamespace(qwen_edit_mode="single"),
        mode="qwen_edit",
        model={"name": "qwen-image-edit-2511-Q4_K_M.gguf", "category": "diffusion_models"},
        model_family="qwen_image_edit",
        settings={
            "steps": 8,
            "cfg": 1.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "width": 768,
            "height": 768,
            "comfy_loras": [],
        },
        prompt="make the jacket blue",
        negative="",
        seed=123,
        edit_strength=1.0,
        cn_upscale="",
        input_filename="main.png",
        mask_filename=None,
        reference_stitch_filename=None,
        grow_mask_by=0,
        model_loader_args={
            "ckpt_name": "qwen-image-edit-2511-Q4_K_M.gguf",
            "relative_path": "qwen-image-edit-2511-Q4_K_M.gguf",
            "category": "diffusion_models",
            "family": "qwen_image_edit",
        },
        qwen_reference_filenames=["ref_a.png", "ref_b.png"],
    )

    load_nodes = [node for node in graph.values() if node.get("class_type") == "LoadImage"]
    assert [node["inputs"]["image"] for node in load_nodes] == ["main.png"]
    assert not any(
        node.get("class_type") == "TextEncodeQwenImageEditPlus"
        for node in graph.values()
    )


def test_qwen_raw_edit_mode_uses_reference_latents():
    graph, _template = _build_comfy_prompt_graph(
        job=SimpleNamespace(qwen_edit_mode="raw"),
        mode="qwen_edit",
        model={"name": "qwen-image-edit-2511-Q4_K_M.gguf", "category": "diffusion_models"},
        model_family="qwen_image_edit",
        settings={
            "steps": 8,
            "cfg": 1.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "width": 1536,
            "height": 1024,
            "comfy_loras": [],
        },
        prompt="preserve composition while changing the outfit",
        negative="",
        seed=123,
        edit_strength=1.0,
        cn_upscale="",
        input_filename="main.png",
        mask_filename=None,
        reference_stitch_filename=None,
        grow_mask_by=0,
        model_loader_args={
            "ckpt_name": "qwen-image-edit-2511-Q4_K_M.gguf",
            "relative_path": "qwen-image-edit-2511-Q4_K_M.gguf",
            "category": "diffusion_models",
            "family": "qwen_image_edit",
        },
        qwen_reference_filenames=["pose.png", "style.png"],
    )

    plus_nodes = [node for node in graph.values() if node.get("class_type") == "TextEncodeQwenImageEditPlus"]
    assert len(plus_nodes) == 2
    assert not any("image1" in node["inputs"] for node in plus_nodes)
    assert sum(1 for node in graph.values() if node.get("class_type") == "ReferenceLatent") == 6


def test_hidream_o1_image_prompt_routes_to_native_reference_node():
    graph, _template = _build_comfy_prompt_graph(
        job=SimpleNamespace(
            _resolved_reference_slots=[
                {"path": "/a.png", "role": "image_prompt", "image": "a.png"},
                {"path": "/b.png", "role": "image_prompt", "image": "b.png"},
            ]
        ),
        mode="hidream_reference",
        model={
            "name": "hidream_o1_image_dev_mxfp8.safetensors",
            "category": "checkpoints",
        },
        model_family="hidream_o1",
        settings={
            "steps": 28,
            "cfg": 1.0,
            "sampler_name": "lcm",
            "scheduler": "normal",
            "width": 2048,
            "height": 2048,
            "comfy_loras": [],
        },
        prompt="make them stand together",
        negative="",
        seed=123,
        edit_strength=1.0,
        cn_upscale="",
        input_filename=None,
        mask_filename=None,
        reference_stitch_filename=None,
        grow_mask_by=0,
        model_loader_args={
            "ckpt_name": "hidream_o1_image_dev_mxfp8.safetensors",
            "relative_path": "hidream_o1_image_dev_mxfp8.safetensors",
            "category": "checkpoints",
            "family": "hidream_o1",
        },
    )

    class_types = {node["class_type"] for node in graph.values() if isinstance(node, dict)}
    assert "HiDreamO1ReferenceImages" in class_types
    assert "IPAdapterAdvanced" not in class_types
    assert [node["inputs"]["image"] for node in graph.values() if node.get("class_type") == "LoadImage"] == [
        "a.png",
        "b.png",
    ]


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


def test_pid_upscale_method_builds_pixeldit_workflow():
    graph, _template = _build_comfy_prompt_graph(
        job=SimpleNamespace(upscale_method="pid_flux1_4k"),
        mode="upscale",
        model={"name": "ignored.safetensors", "category": "checkpoints"},
        model_family="",
        settings={
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "width": 4096,
            "height": 4096,
            "comfy_loras": [],
        },
        prompt="restore the photo with crisp natural details",
        negative="",
        seed=123,
        edit_strength=1.0,
        cn_upscale="pid_flux1_1024_to_4096_4step_mxfp8.safetensors",
        input_filename="source.png",
        mask_filename=None,
        reference_stitch_filename=None,
        grow_mask_by=0,
        model_loader_args={},
    )

    assert any(node.get("class_type") == "PiDConditioning" for node in graph.values())
    assert not any(node.get("class_type") == "UltimateSDUpscale" for node in graph.values())
    loader = next(node for node in graph.values() if node.get("class_type") == "UNETLoader")
    assert loader["inputs"]["unet_name"] == "pid_flux1_1024_to_4096_4step_mxfp8.safetensors"


def test_fast_2x_upscale_method_builds_basic_workflow():
    graph, _template = _build_comfy_prompt_graph(
        job=SimpleNamespace(upscale_method="fast_2x"),
        mode="upscale",
        model={"name": "ignored.safetensors", "category": "checkpoints"},
        model_family="",
        settings={
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "width": 2048,
            "height": 2048,
            "comfy_loras": [],
        },
        prompt="",
        negative="",
        seed=123,
        edit_strength=1.0,
        cn_upscale="OmniSR_X2_DIV2K.safetensors",
        input_filename="source.png",
        mask_filename=None,
        reference_stitch_filename=None,
        grow_mask_by=0,
        model_loader_args={},
    )

    assert any(node.get("class_type") == "ImageUpscaleWithModel" for node in graph.values())
    loader = next(node for node in graph.values() if node.get("class_type") == "UpscaleModelLoader")
    assert loader["inputs"]["model_name"] == "OmniSR_X2_DIV2K.safetensors"


def test_default_upscale_method_builds_ultimate_sd_workflow():
    graph, _template = _build_comfy_prompt_graph(
        job=SimpleNamespace(),
        mode="upscale",
        model={"name": "ignored.safetensors", "category": "checkpoints"},
        model_family="",
        settings={
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "width": 4096,
            "height": 4096,
            "comfy_loras": [],
        },
        prompt="restore the photo with crisp natural details",
        negative="",
        seed=123,
        edit_strength=1.0,
        cn_upscale="4x-UltraSharp.pth",
        input_filename="source.png",
        mask_filename=None,
        reference_stitch_filename=None,
        grow_mask_by=0,
        model_loader_args={},
    )

    assert any(node.get("class_type") == "UltimateSDUpscale" for node in graph.values())
    assert any(node.get("class_type") == "UpscaleModelLoader" for node in graph.values())
    assert not any(node.get("class_type") == "ImageUpscaleWithModel" for node in graph.values())


def test_pid_target_size_uses_4k_long_side_on_16gb():
    width, height, scale, max_long_side = _pid_upscale_target_size(
        2062,
        2586,
        requested_long_side=4096,
        vram_tier="16gb",
    )

    assert max_long_side == 4096
    assert scale > 1.5
    assert (width, height) == (3264, 4096)


def test_pid_target_size_marks_near_noop_on_5gb():
    width, height, scale, max_long_side = _pid_upscale_target_size(
        2062,
        2586,
        requested_long_side=4096,
        vram_tier="5gb",
    )

    assert max_long_side == 2048
    assert scale == 1.0
    assert (width, height) == (2064, 2592)


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


def test_dry_run_edit_plan_clears_stale_upscale_image(monkeypatch):
    import dreamforge_cli_direct as cli

    selected = {
        "name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "stem": "flux1-dev-kontext_fp8_scaled",
        "relative_path": "flux1-dev-kontext_fp8_scaled.safetensors",
        "path": "/models/flux1-dev-kontext_fp8_scaled.safetensors",
        "size_mb": 11000,
        "category": "diffusion_models",
        "engine_name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "family": "flux_kontext",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="flux1-dev-kontext_fp8_scaled.safetensors",
            prompt="replace the jacket color",
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
            input_image="/tmp/edit-source.png",
            inpaint_mask_path=None,
            upscale_image="/tmp/stale-upscale.png",
            upscale_method="fast_2x",
            edit_type="kontext",
            edit_strength=0.8,
            inpaint_grow=None,
            inpaint_feather=None,
            inpaint_mask_grow_by=None,
            preserve_character=False,
            preserve_style=False,
            preserve_text=False,
            face_preservation=False,
            vram_profile="16gb",
            style="image_edit",
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

    assert plan["mode"] == "edit"
    assert plan["proposed_patch"]["input_image"] == "/tmp/edit-source.png"
    assert plan["proposed_patch"]["upscale_image"] is None
    assert plan["proposed_patch"]["upscale_method"] is None


def test_dry_run_generate_reference_stays_generate_mode(monkeypatch):
    import dreamforge_cli_direct as cli

    selected = {
        "name": "z_image_turbo_bf16.safetensors",
        "stem": "z_image_turbo_bf16",
        "relative_path": "z_image_turbo_bf16.safetensors",
        "path": "/models/z_image_turbo_bf16.safetensors",
        "size_mb": 8000,
        "category": "diffusion_models",
        "engine_name": "z_image_turbo_bf16.safetensors",
        "family": "z_image",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="z_image_turbo_bf16.safetensors",
            prompt="same person in a forest",
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
            reference_image="/tmp/reference.png",
            inpaint_mask_path=None,
            upscale_image="/tmp/stale-upscale.png",
            upscale_method="fast_2x",
            edit_type="auto",
            edit_strength=0.35,
            inpaint_grow=None,
            inpaint_feather=None,
            inpaint_mask_grow_by=None,
            preserve_character=True,
            preserve_style=False,
            preserve_text=False,
            face_preservation=False,
            vram_profile="16gb",
            style="none",
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
            workflow_mode="generate",
            cn_selection="Custom...",
            cn_type="img2img",
        )
    )

    assert plan["mode"] == "generate"
    assert plan["proposed_patch"]["input_image"] == "/tmp/reference.png"
    assert plan["proposed_patch"]["workflow_mode"] == "generate"
    assert plan["proposed_patch"]["upscale_image"] is None
    assert plan["proposed_patch"]["upscale_method"] is None
    assert plan["proposed_patch"]["inpaint_mask_path"] is None


def test_dry_run_generate_reference_includes_reference_role(monkeypatch):
    import dreamforge_cli_direct as cli

    selected = {
        "name": "z_image_turbo_bf16.safetensors",
        "stem": "z_image_turbo_bf16",
        "relative_path": "z_image_turbo_bf16.safetensors",
        "path": "/models/z_image_turbo_bf16.safetensors",
        "size_mb": 8000,
        "category": "diffusion_models",
        "engine_name": "z_image_turbo_bf16.safetensors",
        "family": "z_image",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="z_image_turbo_bf16.safetensors",
            prompt="same person in a forest",
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
            reference_image="/tmp/reference.png",
            reference_role="restyle",
            inpaint_mask_path=None,
            upscale_image="/tmp/stale-upscale.png",
            upscale_method="fast_2x",
            edit_type="auto",
            edit_strength=0.35,
            inpaint_grow=None,
            inpaint_feather=None,
            inpaint_mask_grow_by=None,
            preserve_character=True,
            preserve_style=False,
            preserve_text=False,
            face_preservation=False,
            vram_profile="16gb",
            style="none",
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
            workflow_mode="generate",
            cn_selection="Custom...",
            cn_type="img2img",
        )
    )

    assert plan["mode"] == "generate"
    assert plan["proposed_patch"]["reference_role"] == "restyle"


def test_plan_mode_for_job_honors_generate_workflow_mode():
    from dreamforge_cli_direct import _plan_mode_for_job

    job = SimpleNamespace(
        workflow_mode="generate",
        input_image="/tmp/ref.png",
        upscale_image="/tmp/stale.png",
        edit_type="auto",
        inpaint_mask_path=None,
    )
    assert _plan_mode_for_job(job) == "generate"

    edit_job = SimpleNamespace(
        workflow_mode="",
        input_image="/tmp/edit.png",
        upscale_image=None,
        edit_type="kontext",
        inpaint_mask_path=None,
    )
    assert _plan_mode_for_job(edit_job) == "edit"


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
            style="image_edit",
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
            style="none",
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
    assert plan["mode"] == "generate"
    assert plan["mode_contract"]["model_policy"] == "preserve_user_model"
    assert plan["mode_contract"]["selected_model"] == "juggernautXL_v8Rundiffusion.safetensors"


def test_edit_dry_run_reports_routed_mode_contract(monkeypatch):
    import dreamforge_cli_direct as cli

    selected = {
        "name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "stem": "flux1-dev-kontext_fp8_scaled",
        "relative_path": "flux1-dev-kontext_fp8_scaled.safetensors",
        "path": "/models/flux1-dev-kontext_fp8_scaled.safetensors",
        "size_mb": 11000,
        "category": "diffusion_models",
        "engine_name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "family": "flux_kontext",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="flux1-dev-kontext_fp8_scaled.safetensors",
            prompt="change shirt color",
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
            input_image="/tmp/source.png",
            upscale_image=None,
            upscale_method="RealESRGAN_x2",
            edit_type="kontext",
            edit_strength=0.8,
            vram_profile="16gb",
            style="image_edit",
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

    assert plan["mode"] == "edit"
    assert plan["mode_contract"]["model_policy"] == "preserve_user_model"
    assert "edit_type" in plan["mode_contract"]["preserved_fields"]


def test_inpaint_dry_run_reports_missing_image_and_mask(monkeypatch):
    import dreamforge_cli_direct as cli

    selected = {
        "name": "flux-fill-dev.safetensors",
        "stem": "flux-fill-dev",
        "relative_path": "flux-fill-dev.safetensors",
        "path": "/models/flux-fill-dev.safetensors",
        "size_mb": 11000,
        "category": "diffusion_models",
        "engine_name": "flux-fill-dev.safetensors",
        "family": "flux_fill",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="flux-fill-dev.safetensors",
            prompt="replace this area",
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
            input_image=None,
            inpaint_mask_path=None,
            upscale_image=None,
            upscale_method="RealESRGAN_x2",
            edit_type="inpaint",
            edit_strength=0.8,
            vram_profile="16gb",
            style="image_edit",
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

    assert plan["mode"] == "inpaint"
    assert plan["ready"] is False
    assert "inpaint_repair" in plan["workflow_blueprint"]["template_ids"]
    assert plan["workflow_blueprint"]["readiness"]["missing_inputs"] == ["input_image", "mask"]


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
    monkeypatch.setattr(
        inv,
        "check_model_dependencies",
        lambda model, **_kwargs: missing if model["family"] == "qwen_image_edit" else [],
    )
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
            style="image_edit",
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
    assert actions[0]["requires_approval"] is True
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
            edit_type="kontext",
            edit_strength=None,
            vram_profile="auto",
            style="image_edit",
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
        performance="Custom...",
        steps=2,
        cfg_scale=2.5,
        sampler="euler",
        scheduler="normal",
        edit_type="kontext",
        input_image="/tmp/reference.png",
        upscale_image=None,
        model=None,
    )

    out = _apply_job_performance(
        {
            "performance_selection": "Custom...",
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


def test_o1_dev_quality_preset_ignores_stale_ui_sampling(monkeypatch):
    monkeypatch.chdir(_BACKEND)
    from dreamforge_generation import _apply_job_performance

    job = SimpleNamespace(
        performance="Quality",
        steps=50,
        cfg_scale=5.0,
        sampler="euler",
        scheduler="normal",
        model="hidream_o1_image_dev_mxfp8.safetensors",
    )
    out = _apply_job_performance(
        {
            "performance_selection": "Quality",
            "steps": 50,
            "cfg": 5.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "clip_skip": 1,
            "width": 1344,
            "height": 1344,
        },
        job,
        model_family="hidream_o1",
    )
    assert out["steps"] == 28
    assert out["cfg"] == 1.0
    assert out["sampler_name"] == "lcm"
    assert out["width"] == 2048
    assert out["height"] == 2048
    assert out["performance_selection"] == "Quality"


def test_flux_kontext_uses_krita_edit_recipe(monkeypatch):
    monkeypatch.chdir(_BACKEND)
    monkeypatch.setenv("DREAMFORGE_DESKTOP_VRAM_MODE", "16gb")
    from dreamforge_generation import _tune_edit_job_settings

    job = SimpleNamespace(
        performance="Speed",
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
            "performance_selection": "Speed",
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
        performance="Speed",
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
            "performance_selection": "Speed",
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


def test_flux_inpaint_custom_performance_uses_high_cfg(monkeypatch):
    monkeypatch.chdir(_BACKEND)
    from dreamforge_generation import _tune_edit_job_settings

    job = SimpleNamespace(
        performance="Custom...",
        steps=None,
        cfg_scale=None,
        sampler=None,
        scheduler=None,
        edit_type="inpaint",
        input_image="/tmp/reference.png",
        upscale_image=None,
    )

    out = _tune_edit_job_settings(
        {
            "performance_selection": "Custom...",
            "steps": 20,
            "cfg": 3.5,
            "sampler_name": "euler",
            "scheduler": "simple",
            "clip_skip": 1,
        },
        job,
        "flux_fill",
        is_live=False,
    )

    assert out["cfg"] == 30.0
    assert out["steps"] == 20


def test_flux_inpaint_restores_guidance_when_cfg_scale_capped(monkeypatch):
    monkeypatch.chdir(_BACKEND)
    from dreamforge_generation import _tune_edit_job_settings

    job = SimpleNamespace(
        performance="Custom...",
        steps=12,
        cfg_scale=5.0,
        sampler=None,
        scheduler=None,
        edit_type="inpaint",
        input_image="/tmp/reference.png",
        upscale_image=None,
    )

    out = _tune_edit_job_settings(
        {
            "performance_selection": "Custom...",
            "steps": 12,
            "cfg": 5.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "clip_skip": 1,
        },
        job,
        "flux_fill",
        is_live=False,
    )

    assert out["cfg"] == 30.0


def test_flux_inpaint_live_preview_uses_krita_live_steps(monkeypatch):
    monkeypatch.chdir(_BACKEND)
    from dreamforge_generation import _tune_edit_job_settings

    job = SimpleNamespace(
        performance="Speed",
        steps=None,
        cfg_scale=None,
        sampler=None,
        scheduler=None,
        edit_type="inpaint",
        input_image="/tmp/reference.png",
        upscale_image=None,
    )

    out = _tune_edit_job_settings(
        {
            "performance_selection": "Speed",
            "steps": 20,
            "cfg": 30.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "clip_skip": 1,
        },
        job,
        "flux_inpaint",
        is_live=True,
    )

    assert out["steps"] == 8
    assert out["cfg"] == 30.0


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


def test_mode_contract_preservation_hints():
    from dreamforge_mode_contract import build_mode_contract, build_preservation_hints

    hints = build_preservation_hints(
        {"face_preservation": True, "preserve_text": True, "preserve_style": False}
    )
    assert "Preserve face identity" in hints
    assert "Preserve text, logos, and typography" in hints
    assert "Preserve overall style" not in " ".join(hints)

    contract = build_mode_contract(
        "edit",
        {"preserve_character": True},
        {"face_preservation": True, "model": "flux1-dev-kontext_fp8_scaled.safetensors"},
    )
    assert contract["preservation_hints"]
    assert "Preserve character identity and outfit" in contract["preservation_hints"]


def test_edit_mode_contract_includes_preservation_from_job():
    from dreamforge_mode_contract import build_mode_contract

    job = {
        "model": "flux1-dev-kontext_fp8_scaled.safetensors",
        "input_image": "D:/refs/hero.png",
        "upscale_image": "D:/refs/stale_upscale.png",
        "edit_type": "kontext",
        "preserve_character": True,
        "preserve_text": True,
        "face_preservation": True,
    }
    proposed = {
        "model": job["model"],
        "edit_type": job["edit_type"],
        "input_image": job["input_image"],
    }
    contract = build_mode_contract("edit", proposed, job)
    hints = contract["preservation_hints"]
    assert "Preserve character identity and outfit" in hints
    assert "Preserve text, logos, and typography" in hints
    assert contract["model_policy"] in {"route_curated_model", "preserve_user_model"}


def test_edit_strength_is_clamped_for_kontext():
    from dreamforge_generation import _clamp_float

    assert _clamp_float(1.5, 1.0, 0.0, 1.0) == 1.0
    assert _clamp_float("bad", 1.0, 0.0, 1.0) == 1.0


def test_edit_dry_run_carries_edit_strength_and_preservation(monkeypatch):
    import dreamforge_cli_direct as cli

    selected = {
        "name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "stem": "flux1-dev-kontext_fp8_scaled",
        "relative_path": "flux1-dev-kontext_fp8_scaled.safetensors",
        "path": "/models/flux1-dev-kontext_fp8_scaled.safetensors",
        "size_mb": 11000,
        "category": "diffusion_models",
        "engine_name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "family": "flux_kontext",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="flux1-dev-kontext_fp8_scaled.safetensors",
            prompt="same pose, new background",
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
            input_image="/tmp/source.png",
            inpaint_mask_path=None,
            upscale_image=None,
            upscale_method="RealESRGAN_x2",
            edit_type="kontext",
            edit_strength=0.72,
            inpaint_grow=None,
            inpaint_feather=None,
            inpaint_mask_grow_by=None,
            preserve_character=True,
            preserve_style=False,
            preserve_text=True,
            face_preservation=True,
            vram_profile="16gb",
            style="image_edit",
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

    assert plan["mode"] == "edit"
    assert plan["settings"]["edit_strength"] == 0.72
    hints = plan["mode_contract"]["preservation_hints"]
    assert "Preserve character identity and outfit" in hints
    assert "Preserve text, logos, and typography" in hints
    assert "edit_strength" in plan["mode_contract"]["preserved_fields"]


def test_inpaint_dry_run_carries_mask_controls(monkeypatch):
    import dreamforge_cli_direct as cli

    selected = {
        "name": "flux-fill-dev.safetensors",
        "stem": "flux-fill-dev",
        "relative_path": "flux-fill-dev.safetensors",
        "path": "/models/flux-fill-dev.safetensors",
        "size_mb": 11000,
        "category": "diffusion_models",
        "engine_name": "flux-fill-dev.safetensors",
        "family": "flux_fill",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="flux-fill-dev.safetensors",
            prompt="fill the masked region",
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
            input_image="/tmp/source.png",
            inpaint_mask_path="/tmp/mask.png",
            upscale_image=None,
            upscale_method="RealESRGAN_x2",
            edit_type="inpaint",
            edit_strength=0.85,
            inpaint_grow=12,
            inpaint_feather=4,
            inpaint_mask_grow_by=8,
            preserve_character=False,
            preserve_style=False,
            preserve_text=False,
            face_preservation=False,
            vram_profile="16gb",
            style="image_edit",
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

    assert plan["mode"] == "inpaint"
    assert plan["settings"]["edit_strength"] == 1.0
    contract = plan["mode_contract"]
    assert "inpaint_mask_path" in contract["preserved_fields"]


def test_inpaint_dry_run_blocks_empty_mask(tmp_path, monkeypatch):
    import dreamforge_cli_direct as cli
    from PIL import Image

    image_path = tmp_path / "source.png"
    mask_path = tmp_path / "mask.png"
    Image.new("RGB", (512, 512), color=(10, 20, 30)).save(image_path)
    Image.new("L", (512, 512), color=0).save(mask_path)

    selected = {
        "name": "flux-fill-dev.safetensors",
        "stem": "flux-fill-dev",
        "relative_path": "flux-fill-dev.safetensors",
        "path": "/models/flux-fill-dev.safetensors",
        "size_mb": 11000,
        "category": "diffusion_models",
        "engine_name": "flux-fill-dev.safetensors",
        "family": "flux_fill",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="flux-fill-dev.safetensors",
            prompt="replace this area",
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
            input_image=str(image_path),
            inpaint_mask_path=str(mask_path),
            upscale_image=None,
            upscale_method="RealESRGAN_x2",
            edit_type="inpaint",
            edit_strength=0.8,
            vram_profile="16gb",
            style="image_edit",
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

    assert plan["ready"] is False
    assert "mask" in plan["workflow_blueprint"]["readiness"]["missing_inputs"]
    assert plan["inpaint_context"]["mask_empty"] is True
    assert any("empty" in warning.lower() for warning in plan["setup_warnings"])


def test_inpaint_dry_run_exposes_model_instruction_and_task_defaults(tmp_path, monkeypatch):
    import dreamforge_cli_direct as cli
    from PIL import Image

    image_path = tmp_path / "source.png"
    mask_path = tmp_path / "mask.png"
    image = Image.new("RGB", (512, 512), color=(10, 20, 30))
    image.save(image_path)
    mask = Image.new("L", image.size, color=0)
    mask.putpixel((200, 200), 255)
    mask.save(mask_path)

    selected = {
        "name": "flux-fill-dev.safetensors",
        "stem": "flux-fill-dev",
        "relative_path": "flux-fill-dev.safetensors",
        "path": "/models/flux-fill-dev.safetensors",
        "size_mb": 11000,
        "category": "diffusion_models",
        "engine_name": "flux-fill-dev.safetensors",
        "family": "flux_fill",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)

    def fake_prepare(_job, _model, prompt, negative, _settings):
        return {"prompt": f"prepared::{prompt}", "negative": f"neg::{negative}"}

    monkeypatch.setattr("dreamforge_prompt.prepare_generation_prompts", fake_prepare)

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="flux-fill-dev.safetensors",
            prompt="replace the sky",
            negative_prompt="blur",
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
            input_image=str(image_path),
            inpaint_mask_path=str(mask_path),
            edit_task="repair",
            upscale_image=None,
            upscale_method="RealESRGAN_x2",
            edit_type="inpaint",
            edit_strength=0.8,
            vram_profile="16gb",
            style="image_edit",
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

    final = plan["final_edit_request"]
    assert final["user_instruction"] == "replace the sky"
    assert final["model_instruction"] == "prepared::replace the sky"
    assert final["task"] == "repair"
    assert plan["edit_task_defaults"]["edit_task"] == "repair"
    assert plan["inpaint_context"]["mask_empty"] is False


def test_extend_dry_run_does_not_require_mask(tmp_path, monkeypatch):
    import dreamforge_cli_direct as cli
    from PIL import Image

    image_path = tmp_path / "source.png"
    Image.new("RGB", (512, 512), color=(10, 20, 30)).save(image_path)

    selected = {
        "name": "flux-fill-dev.safetensors",
        "stem": "flux-fill-dev",
        "relative_path": "flux-fill-dev.safetensors",
        "path": "/models/flux-fill-dev.safetensors",
        "size_mb": 11000,
        "category": "diffusion_models",
        "engine_name": "flux-fill-dev.safetensors",
        "family": "flux_fill",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="flux-fill-dev.safetensors",
            prompt="extend the scene to the right",
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
            input_image=str(image_path),
            inpaint_mask_path=None,
            edit_task="extend",
            upscale_image=None,
            upscale_method="RealESRGAN_x2",
            edit_type="outpaint",
            cn_type="outpaint",
            cn_selection="Custom...",
            outpaint_direction="right",
            outpaint_amount=256,
            outpaint_feathering=40,
            edit_strength=0.85,
            vram_profile="16gb",
            style="image_edit",
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

    assert plan["mode"] == "inpaint"
    assert plan["ready"] is True
    assert "mask" not in plan["workflow_blueprint"]["readiness"]["missing_inputs"]
    assert plan["inpaint_context"]["status"] == "outpaint"
    assert plan["inpaint_context"]["requires_mask"] is False
    assert plan["edit_task_defaults"]["edit_task"] == "extend"


def test_global_edit_dry_run_ignores_stale_outpaint_route(tmp_path, monkeypatch):
    import dreamforge_cli_direct as cli
    from PIL import Image

    image_path = tmp_path / "source.png"
    Image.new("RGB", (512, 512), color=(10, 20, 30)).save(image_path)

    selected = {
        "name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "stem": "flux1-dev-kontext_fp8_scaled",
        "relative_path": "flux1-dev-kontext_fp8_scaled.safetensors",
        "path": "/models/flux1-dev-kontext_fp8_scaled.safetensors",
        "size_mb": 11000,
        "category": "diffusion_models",
        "engine_name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "family": "flux_kontext",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="flux1-dev-kontext_fp8_scaled.safetensors",
            prompt="make the scene warmer",
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
            input_image=str(image_path),
            inpaint_mask_path=None,
            edit_task="global_edit",
            upscale_image=None,
            upscale_method="RealESRGAN_x2",
            edit_type="outpaint",
            cn_type="outpaint",
            cn_selection="Custom...",
            edit_strength=None,
            vram_profile="16gb",
            style="image_edit",
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

    assert plan["mode"] == "edit"
    assert plan["edit_task_defaults"]["edit_task"] == "global_edit"
    assert plan["edit_task_defaults"]["edit_type"] == "kontext"
    assert plan["final_edit_request"]["task"] == "global_edit"


def test_photo_restore_dry_run_exposes_task_defaults_and_instruction(tmp_path, monkeypatch):
    import dreamforge_cli_direct as cli
    from PIL import Image

    image_path = tmp_path / "old_photo.png"
    Image.new("RGB", (512, 512), color=(30, 25, 20)).save(image_path)

    selected = {
        "name": "epicrealismXL.safetensors",
        "stem": "epicrealismXL",
        "relative_path": "epicrealismXL.safetensors",
        "path": "/models/epicrealismXL.safetensors",
        "size_mb": 7000,
        "category": "checkpoints",
        "engine_name": "epicrealismXL.safetensors",
        "family": "sdxl",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="epicrealismXL.safetensors",
            prompt="restore this old photo",
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
            input_image=str(image_path),
            inpaint_mask_path=None,
            edit_task="photo_restore",
            upscale_image=None,
            upscale_method="RealESRGAN_x2",
            edit_type="auto",
            edit_strength=None,
            vram_profile="16gb",
            style="image_edit",
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

    assert plan["mode"] == "edit"
    assert plan["ready"] is True
    assert plan["edit_task_defaults"]["edit_task"] == "photo_restore"
    assert plan["edit_task_defaults"]["steps"] == 6
    assert plan["edit_task_defaults"]["depth_strength"] == 0.15
    assert plan["edit_task_defaults"]["lineart_strength"] == 0.35
    assert plan["final_edit_request"]["task"] == "photo_restore"
    assert plan["final_edit_request"]["task_hint"]
    assert plan["proposed_patch"]["sampler"] == "dpmpp_2s_ancestral_cfg_pp"


def _outfit_transfer_args(source_path: Path, *, reference_images=None):
    return SimpleNamespace(
        dry_run=True,
        json=True,
        model="Qwen_Image_Edit-Q3_K_M.gguf",
        prompt="put the person in the outfit from the reference photo",
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
        input_image=str(source_path),
        reference_image=None,
        reference_images=reference_images or [],
        references=None,
        control_images=[],
        inpaint_mask_path=None,
        edit_task="outfit_transfer",
        upscale_image=None,
        upscale_method="RealESRGAN_x2",
        edit_type="auto",
        edit_strength=None,
        vram_profile="16gb",
        style="image_edit",
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


def test_outfit_transfer_dry_run_requires_reference_image(tmp_path, monkeypatch):
    import dreamforge_cli_direct as cli
    import dreamforge_cli_inventory as inventory
    from PIL import Image

    source_path = tmp_path / "person.png"
    Image.new("RGB", (512, 512), color=(30, 25, 20)).save(source_path)

    selected = {
        "name": "Qwen_Image_Edit-Q3_K_M.gguf",
        "stem": "Qwen_Image_Edit-Q3_K_M",
        "relative_path": "Qwen_Image_Edit-Q3_K_M.gguf",
        "path": "/models/Qwen_Image_Edit-Q3_K_M.gguf",
        "size_mb": 9000,
        "category": "diffusion_models",
        "engine_name": "../diffusion_models/Qwen_Image_Edit-Q3_K_M.gguf",
        "family": "qwen_image_edit",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)
    monkeypatch.setattr(inventory, "check_model_dependencies", lambda *_args, **_kwargs: [])

    plan = cli.build_plan(_outfit_transfer_args(source_path))

    assert plan["mode"] == "edit"
    assert plan["ready"] is False
    assert plan["edit_task_defaults"]["edit_task"] == "outfit_transfer"
    assert plan["proposed_patch"]["edit_type"] == "qwen_edit"
    assert "reference_images" in plan["workflow_blueprint"]["readiness"]["missing_inputs"]
    assert any("Outfit Transfer needs" in warning for warning in plan["setup_warnings"])


def test_outfit_transfer_dry_run_ready_with_reference_image(tmp_path, monkeypatch):
    import dreamforge_cli_direct as cli
    import dreamforge_cli_inventory as inventory
    from PIL import Image

    source_path = tmp_path / "person.png"
    outfit_path = tmp_path / "outfit.png"
    Image.new("RGB", (512, 512), color=(30, 25, 20)).save(source_path)
    Image.new("RGB", (512, 512), color=(80, 10, 40)).save(outfit_path)

    selected = {
        "name": "Qwen_Image_Edit-Q3_K_M.gguf",
        "stem": "Qwen_Image_Edit-Q3_K_M",
        "relative_path": "Qwen_Image_Edit-Q3_K_M.gguf",
        "path": "/models/Qwen_Image_Edit-Q3_K_M.gguf",
        "size_mb": 9000,
        "category": "diffusion_models",
        "engine_name": "../diffusion_models/Qwen_Image_Edit-Q3_K_M.gguf",
        "family": "qwen_image_edit",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)
    monkeypatch.setattr(inventory, "check_model_dependencies", lambda *_args, **_kwargs: [])

    plan = cli.build_plan(
        _outfit_transfer_args(source_path, reference_images=[str(outfit_path)])
    )

    assert plan["mode"] == "edit"
    assert plan["ready"] is True
    assert "reference_images" not in plan["workflow_blueprint"]["readiness"]["missing_inputs"]
    assert plan["final_edit_request"]["task"] == "outfit_transfer"
    assert plan["final_edit_request"]["task_hint"]


def test_outfit_transfer_runtime_rejects_source_image_as_only_reference(tmp_path, monkeypatch):
    import dreamforge_cli_direct as cli
    import dreamforge_cli_inventory as inventory
    import dreamforge_generation as generation
    import dreamforge_prompt
    import dreamforge_workflow_executor as workflow_executor
    from PIL import Image

    source_path = tmp_path / "person.png"
    Image.new("RGB", (512, 512), color=(30, 25, 20)).save(source_path)
    job = _outfit_transfer_args(source_path)
    job.dry_run = False
    job.reference_role = None
    model = {
        "name": "Qwen_Image_Edit-Q3_K_M.gguf",
        "stem": "Qwen_Image_Edit-Q3_K_M",
        "relative_path": "Qwen_Image_Edit-Q3_K_M.gguf",
        "path": "/models/Qwen_Image_Edit-Q3_K_M.gguf",
        "size_mb": 9000,
        "category": "diffusion_models",
        "engine_name": "../diffusion_models/Qwen_Image_Edit-Q3_K_M.gguf",
        "family": "qwen_image_edit",
    }

    monkeypatch.setattr(
        cli,
        "_compile_job",
        lambda *_args, **_kwargs: (
            job,
            model,
            job.prompt,
            job.negative_prompt,
            512,
            512,
            None,
        ),
    )
    monkeypatch.setattr(inventory, "check_model_dependencies", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        generation,
        "run_preflight",
        lambda *_args, **_kwargs: SimpleNamespace(warnings=[], errors=[], has_errors=False),
    )
    monkeypatch.setattr(workflow_executor, "should_execute_workflow_plan", lambda *_args: False)
    monkeypatch.setattr(
        dreamforge_prompt,
        "prepare_generation_prompts",
        lambda _job, _model, prompt, negative, _settings: {
            "prompt": prompt,
            "negative": negative,
        },
    )

    events = []
    result = generation.run_generation(
        SimpleNamespace(),
        {},
        stream_sink=events.append,
        job_id="job-outfit-missing-ref",
    )

    assert result["status"] == "error"
    assert result["code"] == "invalid_request"
    assert "Outfit Transfer requires" in result["message"]
    assert any(event.get("code") == "invalid_request" for event in events)


def test_upscale_fast_4x_dry_run_applies_preset_fields(tmp_path, monkeypatch):
    import dreamforge_cli_direct as cli
    from PIL import Image

    image_path = tmp_path / "source.png"
    Image.new("RGB", (512, 512), color=(30, 25, 20)).save(image_path)

    selected = {
        "name": "sdxl.safetensors",
        "stem": "sdxl",
        "relative_path": "sdxl.safetensors",
        "path": "/models/sdxl.safetensors",
        "size_mb": 7000,
        "category": "checkpoints",
        "engine_name": "sdxl.safetensors",
        "family": "sdxl",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="sdxl.safetensors",
            prompt="",
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
            input_image=None,
            inpaint_mask_path=None,
            edit_task=None,
            upscale_image=str(image_path),
            upscale_method="ultimate_sd_upscale",
            upscale_preset="fast_4x",
            edit_type="auto",
            edit_strength=None,
            vram_profile="16gb",
            style="image_edit",
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

    assert plan["mode"] == "upscale"
    assert plan["settings"]["steps"] == 4
    assert plan["settings"]["cfg"] == 8.0
    assert plan["settings"]["sampler"] == "euler"
    assert plan["proposed_patch"]["upscale_preset"] == "fast_4x"
    assert plan["proposed_patch"]["upscale_by"] == 4.0
    assert plan["proposed_patch"]["upscale_tile_width"] == 1024


def test_preserve_text_auto_enables_qwen_preserve_resolution(monkeypatch):
    monkeypatch.chdir(_BACKEND)
    from dreamforge_generation import _apply_qwen_family_settings

    job = SimpleNamespace(
        performance="Lightning",
        edit_type="qwen_edit",
        input_image="/tmp/source.png",
        preserve_text=True,
        qwen_edit_mode="auto",
    )
    out = _apply_qwen_family_settings(
        {"steps": 8, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple"},
        job,
        "qwen_image_edit",
    )
    assert out.get("qwen_preserve_resolution") is True


def test_job_namespace_merges_references_from_payload():
    from types import SimpleNamespace

    from dreamforge_cli_direct import _job_namespace

    base = SimpleNamespace(reference_role="image_prompt", workflow_mode="ipadapter")
    data = {
        "references": [
            {"path": "/a.png", "role": "image_prompt", "weight": 0.8},
            {"path": "/b.png", "role": "image_prompt", "weight": 0.6},
        ]
    }
    job = _job_namespace(base, data)
    assert len(job.references) == 2
    assert job.references[0]["path"] == "/a.png"


def test_qwen_lightning_4step_routing_and_overrides(monkeypatch):
    import dreamforge_comfy_workflows
    monkeypatch.setattr(
        dreamforge_comfy_workflows,
        "_resolve_qwen_lightning_lora_name",
        lambda _args: "dummy_lora.safetensors",
    )

    from dreamforge_generation import _build_comfy_prompt_graph

    graph, _template = _build_comfy_prompt_graph(
        job=SimpleNamespace(qwen_edit_mode="lightning_4step"),
        mode="qwen_edit",
        model={"name": "qwen-image-edit-2511-Q4_K_M.gguf", "category": "diffusion_models"},
        model_family="qwen_image_edit",
        settings={
            "steps": 20,
            "cfg": 2.5,
            "sampler_name": "euler",
            "scheduler": "beta",
            "width": 1024,
            "height": 1024,
            "comfy_loras": [],
        },
        prompt="change outfit",
        negative="",
        seed=123,
        edit_strength=1.0,
        cn_upscale="",
        input_filename="main.png",
        mask_filename=None,
        reference_stitch_filename=None,
        grow_mask_by=0,
        model_loader_args={
            "ckpt_name": "qwen-image-edit-2511-Q4_K_M.gguf",
            "relative_path": "qwen-image-edit-2511-Q4_K_M.gguf",
            "category": "diffusion_models",
            "family": "qwen_image_edit",
        },
        qwen_reference_filenames=["ref1.png"],
    )

    sampler = next(n for n in graph.values() if n.get("class_type") == "KSampler")
    assert sampler["inputs"]["steps"] == 4
    assert sampler["inputs"]["cfg"] == 1.0
    assert sampler["inputs"]["sampler_name"] == "euler"
    assert sampler["inputs"]["scheduler"] == "simple"

    lora_node = next((n for n in graph.values() if n.get("class_type") == "LoraLoaderModelOnly"), None)
    assert lora_node is not None
    assert lora_node["inputs"]["strength_model"] == 1.0


def test_qwen_lightning_4step_respects_preserve_resolution():
    from dreamforge_generation import _build_comfy_prompt_graph

    graph, _template = _build_comfy_prompt_graph(
        job=SimpleNamespace(qwen_edit_mode="lightning_4step"),
        mode="qwen_edit",
        model={"name": "qwen-image-edit-2511-Q4_K_M.gguf", "category": "diffusion_models"},
        model_family="qwen_image_edit",
        settings={
            "steps": 20,
            "cfg": 2.5,
            "sampler_name": "euler",
            "scheduler": "beta",
            "width": 1024,
            "height": 1024,
            "comfy_loras": [],
            "qwen_preserve_resolution": True,
        },
        prompt="change outfit",
        negative="",
        seed=123,
        edit_strength=1.0,
        cn_upscale="",
        input_filename="main.png",
        mask_filename=None,
        reference_stitch_filename=None,
        grow_mask_by=0,
        model_loader_args={
            "ckpt_name": "qwen-image-edit-2511-Q4_K_M.gguf",
            "relative_path": "qwen-image-edit-2511-Q4_K_M.gguf",
            "category": "diffusion_models",
            "family": "qwen_image_edit",
        },
        qwen_reference_filenames=["ref1.png", "ref2.png"],
    )

    # When qwen_preserve_resolution is on, it must route to raw_plus (using ReferenceLatents)
    plus_nodes = [node for node in graph.values() if node.get("class_type") == "TextEncodeQwenImageEditPlus"]
    assert len(plus_nodes) == 2
    assert not any("image1" in node["inputs"] for node in plus_nodes)
    assert sum(1 for node in graph.values() if node.get("class_type") == "ReferenceLatent") == 6
