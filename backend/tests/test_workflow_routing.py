from types import SimpleNamespace

from dreamforge_workflow_routing import (
    checkpoint_is_flux_fill,
    checkpoint_is_flux_kontext,
    plan_clear_fields_for_mode,
    plan_mode_for_job,
    resolve_comfy_workflow_mode,
    resolve_input_routing,
    route_label,
)


def test_resolve_input_routing_generate_restyle_ignores_stale_upscale():
    job = SimpleNamespace(
        reference_role="restyle",
        workflow_mode="generate",
        input_image="/tmp/ref.png",
        upscale_image="/tmp/stale.png",
        cn_selection="None",
        cn_type="None",
        edit_type="auto",
    )
    route = resolve_input_routing(
        job,
        model={"engine_name": "z_image_turbo.safetensors"},
        model_family="z_image",
        studio_mode="generate",
    )
    assert route.plan_mode == "generate"
    assert route.reference_role == "restyle"
    assert route.is_upscale_job is False
    assert route.cn_selection == "Custom..."
    assert route.cn_type == "img2img"


def test_resolve_input_routing_upscale_only_path():
    job = SimpleNamespace(
        reference_role="upscale",
        upscale_image="/tmp/up.png",
        input_image=None,
        cn_selection="None",
        cn_type="None",
        edit_type="auto",
    )
    route = resolve_input_routing(job, model_family="", studio_mode="upscale")
    assert route.is_upscale_job is True
    assert route.cn_type == "upscale"


def test_plan_mode_for_job_matches_reference_role():
    job = SimpleNamespace(
        reference_role="restyle",
        workflow_mode="generate",
        input_image="/tmp/ref.png",
    )
    assert plan_mode_for_job(job, studio_mode="generate") == "generate"


def test_plan_clear_fields_generate():
    assert "upscale_image" in plan_clear_fields_for_mode("generate")
    assert "inpaint_mask_path" in plan_clear_fields_for_mode("generate")


def test_route_label_kontext_family():
    assert "Kontext" in route_label("source_edit", "flux_kontext")


def test_resolve_input_routing_restyle_on_kontext_model_uses_img2img():
    job = SimpleNamespace(
        reference_role="restyle",
        workflow_mode="generate",
        input_image="/tmp/ref.png",
        reference_image="/tmp/ref.png",
        cn_selection="None",
        cn_type="None",
        edit_type="kontext",
    )
    route = resolve_input_routing(
        job,
        model={"engine_name": "flux1-dev-kontext_fp8_scaled.safetensors"},
        model_family="flux_kontext",
        studio_mode="generate",
    )
    assert route.plan_mode == "generate"
    assert route.reference_role == "restyle"
    assert route.cn_selection == "Custom..."
    assert route.cn_type == "img2img"
    assert route.edit_type == "auto"


def test_resolve_input_routing_image_prompt_uses_reference_path():
    job = SimpleNamespace(
        reference_role="image_prompt",
        reference_image="/tmp/ref.png",
        cn_selection="None",
        cn_type="None",
        edit_type="auto",
    )
    route = resolve_input_routing(
        job,
        model={"engine_name": "z_image.safetensors"},
        model_family="z_image",
        studio_mode="generate",
    )
    assert route.plan_mode == "generate"
    assert route.input_path == "/tmp/ref.png"
    assert route.workflow_mode == "ipadapter"


def test_should_coerce_image_prompt_without_explicit_reference_role():
    from dreamforge_workflow_routing import should_coerce_image_prompt_to_restyle

    job = SimpleNamespace(
        workflow_mode="ipadapter",
        reference_image="/tmp/ref.png",
    )
    route = resolve_input_routing(
        job,
        model={"engine_name": "z_image.safetensors"},
        model_family="z_image",
        studio_mode="generate",
    )
    assert route.reference_role == "image_prompt"
    assert should_coerce_image_prompt_to_restyle(
        route,
        job,
        studio_mode="generate",
    )


def test_should_not_coerce_explicit_restyle_on_generate():
    from dreamforge_workflow_routing import should_coerce_image_prompt_to_restyle

    job = SimpleNamespace(
        workflow_mode="generate",
        input_image="/tmp/ref.png",
        reference_image="/tmp/ref.png",
        reference_role="restyle",
    )
    route = resolve_input_routing(
        job,
        model={"engine_name": "z_image.safetensors"},
        model_family="z_image",
        studio_mode="generate",
    )
    assert route.reference_role == "restyle"
    assert not should_coerce_image_prompt_to_restyle(
        route,
        job,
        studio_mode="generate",
    )


def test_coerce_image_prompt_to_restyle_route():
    from dreamforge_workflow_routing import coerce_image_prompt_to_restyle_route

    job = SimpleNamespace(
        reference_role="image_prompt",
        reference_image="/tmp/ref.png",
        workflow_mode="ipadapter",
    )
    route = resolve_input_routing(
        job,
        model={"engine_name": "z_image.safetensors"},
        model_family="z_image",
        studio_mode="generate",
    )
    assert route.cn_type == "None"

    fallback = coerce_image_prompt_to_restyle_route(route, job)
    assert fallback.reference_role == "restyle"
    assert fallback.cn_selection == "Custom..."
    assert fallback.cn_type == "img2img"
    assert fallback.workflow_mode == "generate"
    assert fallback.input_path == "/tmp/ref.png"
    assert any("IP-Adapter" in item for item in fallback.warnings)


def test_generate_upscale_role_only_in_upscale_mode():
    job = SimpleNamespace(
        reference_role="restyle",
        workflow_mode="generate",
        input_image="/tmp/ref.png",
        upscale_image="/tmp/stale.png",
        cn_selection="None",
        cn_type="None",
        edit_type="auto",
    )
    route = resolve_input_routing(
        job,
        model_family="sdxl",
        studio_mode="generate",
    )
    assert route.is_upscale_job is False
    assert route.cn_type == "img2img"

    upscale_job = SimpleNamespace(
        reference_role="upscale",
        upscale_image="/tmp/up.png",
        cn_selection="None",
        cn_type="None",
        edit_type="auto",
    )
    upscale_route = resolve_input_routing(
        upscale_job,
        model_family="sdxl",
        studio_mode="upscale",
    )
    assert upscale_route.is_upscale_job is True
    assert upscale_route.cn_type == "upscale"


def test_resolve_input_routing_structure_role():
    job = SimpleNamespace(
        reference_role="structure",
        reference_image="/tmp/structure.png",
        cn_selection="None",
        cn_type="None",
        edit_type="auto",
    )
    route = resolve_input_routing(
        job,
        model={"engine_name": "sdxl.safetensors"},
        model_family="sdxl",
        studio_mode="generate",
    )
    assert route.plan_mode == "generate"
    assert route.reference_role == "structure"
    assert route.cn_selection == "Custom..."
    assert route.cn_type == "canny"
    assert route.workflow_mode == "controlnet"
    assert route.input_path == "/tmp/structure.png"


def test_resolve_comfy_workflow_mode_img2img():
    job = SimpleNamespace(
        workflow_mode="generate",
        input_image="/tmp/a.png",
        cn_selection="Custom...",
        cn_type="img2img",
        edit_type="auto",
    )
    route = resolve_input_routing(
        job,
        model={"engine_name": "z_image.safetensors"},
        model_family="z_image",
    )
    mode = resolve_comfy_workflow_mode(
        route,
        model={"engine_name": "z_image.safetensors"},
        model_family="z_image",
        input_filename="a.png",
    )
    assert mode == "img2img"


def test_checkpoint_is_flux_kontext():
    assert checkpoint_is_flux_kontext(
        {"engine_name": "flux1-dev-kontext_fp8_scaled.safetensors"},
        "flux_kontext",
    )
    assert not checkpoint_is_flux_fill(
        {"engine_name": "flux1-dev-kontext_fp8_scaled.safetensors"},
        "flux_kontext",
    )
