import os
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from modules.model_ui_defaults import (  # noqa: E402
    apply_hidream_sampling_at_submit,
    engine_name_for_category,
    family_performance_settings,
    gallery_caption,
    infer_model_family,
    list_gallery_models,
    parse_gallery_caption,
    performance_preset_name,
    resolve_ui_profile,
    scan_model_category,
    should_apply_family_defaults,
)


def test_infer_model_family():
    assert infer_model_family("hidream_o1_image_dev_mxfp8.safetensors") == "hidream_o1"
    assert infer_model_family("flux1-dev-fp8.safetensors") == "flux"
    assert infer_model_family("FLUX.1-Fill-dev_fp8.safetensors") == "flux_fill"
    assert infer_model_family("ideogram4_fp8_scaled.safetensors") == "ideogram4"
    assert infer_model_family("dreamshaper_8.safetensors") == "sd15"
    assert infer_model_family("sd_xl_base.safetensors") == "sdxl"


def test_gallery_caption_roundtrip():
    cap = gallery_caption("diffusion_models", "flux/flux1-dev.safetensors")
    assert parse_gallery_caption(cap) == ("diffusion_models", "flux/flux1-dev.safetensors")
    assert parse_gallery_caption("foo.safetensors") == ("checkpoints", "foo.safetensors")


def test_engine_name_for_diffusion():
    from pathlib import Path

    assert engine_name_for_category(
        "diffusion_models", "flux/flux1-dev.safetensors"
    ) == str(Path("..") / "diffusion_models" / "flux/flux1-dev.safetensors")


def test_hidream_performance_preset():
    assert performance_preset_name("hidream_o1_image_dev_mxfp8.safetensors", "hidream_o1") == "Speed"
    assert performance_preset_name("hidream_o1_image_full.safetensors", "hidream_o1") == "Quality"


def test_resolve_ui_profile_applies_for_misaligned_lightning():
    profile = resolve_ui_profile(
        "hidream_o1_image_dev_mxfp8.safetensors",
        current_performance="Lightning",
        lock_enabled=True,
        preset_active=False,
    )
    assert profile["family"] == "hidream_o1"
    assert profile["apply_performance"] is True
    assert profile["performance_selection"] == "Speed"
    assert profile["custom_sampling"]["custom_steps"] == 22
    assert profile["custom_sampling"]["cfg"] == 1.0
    assert profile["custom_sampling"]["sampler_name"] == "lcm"
    assert profile["settings_patch"]["width"] == 1536
    assert profile["settings_patch"]["height"] == 1536
    assert profile["clear_styles"] is True
    assert profile["clear_negative"] is True


def test_resolve_ui_profile_respects_lock_off():
    profile = resolve_ui_profile(
        "flux1-dev-fp8.safetensors",
        current_performance="Speed",
        lock_enabled=False,
        preset_active=False,
    )
    assert profile["apply_performance"] is False
    assert profile["performance_selection"] == "Lightning"
    assert profile["custom_sampling"] is None


def test_should_not_apply_when_preset_active():
    assert should_apply_family_defaults(
        "hidream_o1", "Speed", True, True, "hidream_o1_dev.safetensors"
    ) is False


def test_unified_family_performance_settings_are_family_specific():
    flux = family_performance_settings("flux", "flux1-dev-fp8.safetensors", "Speed")
    hidream = family_performance_settings(
        "hidream_o1", "hidream_o1_image_dev_mxfp8.safetensors", "Speed"
    )
    ideogram = family_performance_settings("ideogram4", "ideogram4_fp8_scaled.safetensors", "Quality")

    assert flux["sampler_name"] == "euler"
    assert flux["scheduler"] == "beta"
    assert hidream["custom_steps"] == 22
    assert hidream["cfg"] == 1.0
    assert hidream["sampler_name"] == "lcm"
    assert ideogram["custom_steps"] == 48


def test_hidream_fast_variant_steps():
    fast = family_performance_settings("hidream", "HiDream-I1-Fast.safetensors", "Lightning")
    assert fast["custom_steps"] == 16
    assert fast["cfg"] == 1.0


def test_hidream_submit_clamps_sdxl_cfg():
    out = apply_hidream_sampling_at_submit(
        {"cfg": 7.0, "steps": 28, "performance_selection": "Custom..."},
        "hidream_o1_image_dev_mxfp8.safetensors",
        "hidream_o1",
    )
    assert out["cfg"] == 1.0
    assert out["negative"] == ""


def test_list_gallery_models_scans_without_model_handler():
    rows = list_gallery_models("", shared_models=None)
    assert isinstance(rows, list)
    assert scan_model_category("diffusion_models") is not None
