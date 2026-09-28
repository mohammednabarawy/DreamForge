from dreamforge_creative_tasks import enforce_creative_task_settings, resolve_creative_task
from dreamforge_task_router import apply_task_routing

GALLERY = [
    {
        "family": "flux_kontext",
        "caption": "Flux Kontext FP8",
        "engine_name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "relative_path": "flux1-dev-kontext_fp8_scaled.safetensors",
    },
    {
        "family": "flux_fill",
        "caption": "Flux Fill FP8",
        "engine_name": "flux1-fill-dev-fp8.safetensors",
        "relative_path": "flux1-fill-dev-fp8.safetensors",
    },
    {
        "family": "qwen_image_2.1",
        "caption": "Qwen Image 2.1",
        "engine_name": "qwen_image_2.1_int8_convrot.safetensors",
        "relative_path": "qwen_image_2.1_int8_convrot.safetensors",
    },
    {
        "family": "ideogram4",
        "caption": "Ideogram 4 FP8",
        "engine_name": "ideogram4_fp8_scaled.safetensors",
        "relative_path": "ideogram4_fp8_scaled.safetensors",
    },
    {
        "family": "flux",
        "caption": "Flux Dev FP8",
        "engine_name": "flux1-dev-fp8.safetensors",
        "relative_path": "flux1-dev-fp8.safetensors",
        "category": "checkpoints",
    },
    {
        "family": "sdxl",
        "caption": "Juggernaut XL",
        "engine_name": "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors",
        "relative_path": "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors",
        "category": "checkpoints",
    },
]


def test_edit_keeps_compatible_ideogram():
    routed = apply_task_routing(
        {
            "model": "ideogram4_fp8_scaled.safetensors",
            "prompt": "make the sky blue",
            "input_image": "D:/photo.png",
        },
        "edit",
        GALLERY,
        advanced_mode=False,
        user_picked_model=False,
    )
    assert routed.patch["model"] == "ideogram4_fp8_scaled.safetensors"
    assert routed.patch["edit_type"] == "kontext"
    assert routed.route_reason == "compatible_edit_model"


def test_pro_upscale_preserves_flux_user_pick():
    routed = apply_task_routing(
        {
            "model": "flux1-dev-fp8.safetensors",
            "upscale_image": "D:/photo.png",
            "upscale_method": "ultimate_sd_upscale",
        },
        "upscale",
        GALLERY,
        advanced_mode=True,
        user_picked_model=True,
    )
    assert routed.patch["model"] == "flux1-dev-fp8.safetensors"
    assert routed.patch.get("user_picked_model") is True
    assert routed.route_reason == "pro_upscale_user_model"


def test_easy_upscale_forces_sdxl_default():
    routed = apply_task_routing(
        {
            "model": "flux1-dev-fp8.safetensors",
            "upscale_image": "D:/photo.png",
        },
        "upscale",
        GALLERY,
        advanced_mode=False,
        user_picked_model=False,
    )
    assert "juggernaut" in routed.patch["model"].lower() or "sdxl" in routed.patch["model"].lower()
    assert not routed.patch.get("user_picked_model")


def test_enforce_edit_keeps_compatible_ideogram():
    out = enforce_creative_task_settings(
        {
            "model": "ideogram4_fp8_scaled.safetensors",
            "prompt": "make jacket blue",
            "input_image": "D:/photo.png",
        },
        studio_mode="edit",
        model_gallery=GALLERY,
        advanced_mode=False,
        user_picked_model=False,
    )
    assert out["model"] == "ideogram4_fp8_scaled.safetensors"
    assert out["edit_type"] == "kontext"


def test_enforce_upscale_pro_keeps_flux():
    out = enforce_creative_task_settings(
        {
            "model": "flux1-dev-fp8.safetensors",
            "upscale_image": "D:/photo.png",
            "upscale_method": "ultimate_sd_upscale",
        },
        studio_mode="upscale",
        model_gallery=GALLERY,
        advanced_mode=True,
        user_picked_model=True,
    )
    assert out["model"] == "flux1-dev-fp8.safetensors"
    assert out.get("user_picked_model") is True


def test_resolve_edit_uses_qwen_image_21():
    result = resolve_creative_task(
        "edit",
        {"prompt": "make jacket blue"},
        GALLERY,
        selected_image="D:/photo.png",
        advanced_mode=False,
    )
    patch = result["patch"]
    assert patch["edit_type"] == "qwen_edit"
    assert "qwen_image_2.1" in patch["model"].lower()


def test_masked_edit_keeps_qwen_inpaint_controls():
    routed = apply_task_routing(
        {"model": "ideogram4_fp8_scaled.safetensors", "input_image": "D:/photo.png",
         "inpaint_mask_path": "D:/mask.png", "prompt": "Change the shirt"},
        "edit", GALLERY,
    )
    assert "qwen_image_2.1" in routed.patch["model"].lower()
    assert routed.patch["edit_type"] == "inpaint"
    assert routed.patch["cn_type"] == "inpaint"


def test_generate_and_edit_keep_other_selected_models():
    for model in ("ideogram4_fp8_scaled.safetensors", "flux1-dev-kontext_fp8_scaled.safetensors"):
        settings = {"model": model, "input_image": "D:/photo.png", "prompt": "Create a portrait"}
        assert apply_task_routing(settings, "generate", GALLERY).patch["model"] == model
        edited = apply_task_routing(settings, "edit", GALLERY)
        assert edited.patch["model"] == model


def test_edit_works_with_selected_kontext_when_qwen_image_21_is_missing():
    gallery = [item for item in GALLERY if item["family"] != "qwen_image_2.1"]
    routed = apply_task_routing(
        {"model": "flux1-dev-kontext_fp8_scaled.safetensors", "input_image": "D:/photo.png"},
        "edit",
        gallery,
        advanced_mode=False,
        user_picked_model=False,
    )
    assert routed.patch["model"] == "flux1-dev-kontext_fp8_scaled.safetensors"
    assert routed.patch["edit_type"] == "kontext"
    assert not routed.warnings


def test_explicit_edit_selection_survives_resolution_sampling_and_mask_routing():
    for item in GALLERY:
        if item["family"] in {"flux_fill", "qwen_image_2.1"}:
            continue
        settings = {"model": item["engine_name"], "input_image": "D:/photo.png",
                    "edit_type": "qwen_edit", "prompt": "Change the shirt", "performance": "Custom...",
                    "steps": 13, "cfg_scale": 2.5, "sampler": "euler", "scheduler": "simple", "edit_strength": 0.6}
        result = resolve_creative_task("edit", settings, GALLERY, user_picked_model=True, vram_profile="16gb")
        patch = result["patch"]
        assert patch["model"] == settings["model"]
        assert patch["edit_type"] != "qwen_edit"
        assert patch["cfg_scale"] == 2.5
        assert patch["steps"] == 13
        assert patch["edit_strength"] == 0.6
        masked = apply_task_routing({**settings, "inpaint_mask_path": "D:/mask.png"}, "edit", GALLERY, user_picked_model=True)
        assert masked.patch["model"] == settings["model"]
        assert masked.patch["edit_type"] == "inpaint"

    unknown = {"model": "unknown.safetensors", "input_image": "D:/photo.png"}
    routed = apply_task_routing(unknown, "edit", GALLERY, user_picked_model=True)
    assert routed.patch["model"] == unknown["model"]
    assert routed.warnings


def test_toolbox_custom_tool_skips_native_task_routing():
    routed = apply_task_routing(
        {
            "custom_tool_id": "custom_pixel",
            "edit_task": "cutout_compose",
            "edit_strength": 1.0,
            "input_image": "D:/photo.png",
            "reference_images": ["D:/bg.png"],
        },
        "edit",
        GALLERY,
        toolbox_studio_mode="toolbox",
    )
    assert routed.patch["custom_tool_id"] == "custom_pixel"
    assert float(routed.patch.get("edit_strength") or 0) == 1.0
    assert routed.route_reason != "toolbox_cutout_compose"


def test_removed_toolbox_outfit_route_does_not_auto_mask():
    routed = apply_task_routing(
        {
            "edit_task": "outfit_transfer",
            "outfit_transfer_regions": ["upper_body"],
            "input_image": "D:/photo.png",
            "reference_images": ["D:/outfit.png"],
        },
        "edit",
        GALLERY,
        toolbox_studio_mode="toolbox",
    )
    assert routed.patch.get("outfit_auto_mask") is not True
    assert routed.patch["edit_type"] == "qwen_edit"
    assert routed.route_reason != "toolbox_outfit_segformer"
