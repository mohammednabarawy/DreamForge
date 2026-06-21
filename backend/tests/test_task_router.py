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
        "family": "qwen_image_edit",
        "caption": "Qwen Edit Q4",
        "engine_name": "qwen-image-edit-2511-Q4_K_M.gguf",
        "relative_path": "qwen-image-edit-2511-Q4_K_M.gguf",
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


def test_easy_edit_routes_away_from_ideogram():
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
    assert "ideogram" not in routed.patch["model"].lower()
    assert routed.patch["edit_type"] == "kontext"
    assert routed.route_reason == "easy_edit_default"


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


def test_enforce_edit_simple_blocks_ideogram():
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
    assert "ideogram" not in out["model"].lower()
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


def test_resolve_edit_routes_kontext():
    result = resolve_creative_task(
        "edit",
        {"prompt": "make jacket blue"},
        GALLERY,
        selected_image="D:/photo.png",
        advanced_mode=False,
    )
    patch = result["patch"]
    assert patch["edit_type"] == "kontext"
    assert "kontext" in patch["model"].lower()
