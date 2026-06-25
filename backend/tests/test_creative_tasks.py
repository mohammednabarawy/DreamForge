from dreamforge_creative_tasks import (
    apply_vram_quality_defaults,
    enforce_creative_task_settings,
    resolve_creative_task,
)


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
]


def test_resolve_inpaint_routes_flux_fill():
    result = resolve_creative_task(
        "inpaint",
        {"prompt": "fix the sky"},
        GALLERY,
        selected_image="D:/photo.png",
    )
    patch = result["patch"]
    assert patch["edit_type"] == "inpaint"
    assert patch["cn_type"] == "inpaint"
    assert "flux1-fill" in patch["model"]
    assert patch["input_image"] == "D:/photo.png"


def test_resolve_inpaint_clears_mask_when_selected_image_changes():
    result = resolve_creative_task(
        "inpaint",
        {
            "prompt": "fix the sky",
            "input_image": "D:/old.png",
            "inpaint_mask_path": "D:/old-mask.png",
        },
        GALLERY,
        selected_image="D:/new.png",
    )
    patch = result["patch"]
    assert patch["input_image"] == "D:/old.png"
    assert patch.get("inpaint_mask_path") == "D:/old-mask.png"


def test_resolve_inpaint_preserves_mask_when_history_selection_differs():
    result = resolve_creative_task(
        "inpaint",
        {
            "prompt": "fix the sky",
            "input_image": "D:/photo.png",
            "inpaint_mask_path": "D:/mask.png",
        },
        GALLERY,
        selected_image="D:/other-history.png",
    )
    patch = result["patch"]
    assert patch["input_image"] == "D:/photo.png"
    assert patch.get("inpaint_mask_path") == "D:/mask.png"


def test_resolve_edit_routes_kontext():
    result = resolve_creative_task(
        "edit",
        {"prompt": "make jacket blue"},
        GALLERY,
        selected_image="D:/photo.png",
    )
    patch = result["patch"]
    assert patch["edit_type"] == "kontext"
    assert patch["input_image"] == "D:/photo.png"
    assert "kontext" in patch["model"].lower()
    assert patch.get("upscale_image") in (None, "")


def test_resolve_edit_preserves_user_model_override():
    result = resolve_creative_task(
        "edit",
        {
            "prompt": "make jacket blue",
            "model": "qwen-image-edit-2511-Q4_K_M.gguf",
            "edit_type": "qwen_edit",
        },
        GALLERY,
        selected_image="D:/photo.png",
    )
    patch = result["patch"]
    assert patch["model"] == "qwen-image-edit-2511-Q4_K_M.gguf"
    assert patch["edit_type"] == "qwen_edit"


def test_resolve_upscale_sets_method():
    result = resolve_creative_task(
        "upscale",
        {},
        GALLERY,
        selected_image="D:/photo.png",
    )
    patch = result["patch"]
    assert patch["cn_type"] == "upscale"
    assert patch["upscale_image"] == "D:/photo.png"
    assert patch.get("upscale_method")


def test_resolve_edit_with_post_upscale_template():
    result = resolve_creative_task(
        "edit",
        {"prompt": "make jacket blue", "post_upscale_enabled": True},
        GALLERY,
        selected_image="D:/photo.png",
    )
    patch = result["patch"]
    assert patch.get("post_upscale") == "ultimate_sd_upscale"
    assert result.get("template_id") == "edit.kontext.enhance2x"
    assert patch.get("upscale_image") in (None, "")


def test_vram_quality_caps_inpaint_steps_without_cfg_clamp():
    patch = apply_vram_quality_defaults(
        {"steps": 28, "cfg_scale": 7},
        studio_mode="inpaint",
        vram_profile="5gb",
    )
    assert patch["steps"] <= 12
    assert patch["cfg_scale"] == 7


def test_vram_quality_caps_edit_cfg_on_5gb():
    patch = apply_vram_quality_defaults(
        {"steps": 28, "cfg_scale": 7},
        studio_mode="edit",
        vram_profile="5gb",
    )
    assert patch["steps"] <= 12
    assert patch["cfg_scale"] <= 5


def test_enforce_on_submit_inpaint_preserves_user_model_override():
    out = enforce_creative_task_settings(
        {
            "model": "wrong-model.safetensors",
            "edit_type": "auto",
            "cn_type": "img2img",
            "prompt": "fix",
        },
        studio_mode="inpaint",
        model_gallery=GALLERY,
        advanced_mode=True,
        user_picked_model=True,
    )
    assert out["edit_type"] == "inpaint"
    assert out["model"] == "wrong-model.safetensors"


def test_enforce_on_submit_inpaint_uses_default_when_model_empty():
    out = enforce_creative_task_settings(
        {
            "edit_type": "auto",
            "cn_type": "img2img",
            "prompt": "fix",
        },
        studio_mode="inpaint",
        model_gallery=GALLERY,
    )
    assert out["edit_type"] == "inpaint"
    assert "flux1-fill" in out["model"]
