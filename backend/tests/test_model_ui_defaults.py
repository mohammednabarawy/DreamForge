import os
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from modules.model_ui_defaults import (  # noqa: E402
    engine_name_for_category,
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
    assert performance_preset_name("hidream_o1_image_dev_mxfp8.safetensors", "hidream_o1") == "HiDream"
    assert performance_preset_name("hidream_o1_image_full.safetensors", "hidream_o1") == "HiDream Full"


def test_resolve_ui_profile_applies_for_misaligned_speed():
    profile = resolve_ui_profile(
        "hidream_o1_image_dev_mxfp8.safetensors",
        current_performance="Speed",
        lock_enabled=True,
        preset_active=False,
    )
    assert profile["family"] == "hidream_o1"
    assert profile["apply_performance"] is True
    assert profile["performance_selection"] == "HiDream"
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
    assert profile["performance_selection"] == "Flux"


def test_should_not_apply_when_preset_active():
    assert should_apply_family_defaults(
        "hidream_o1", "Speed", True, True, "hidream_o1_dev.safetensors"
    ) is False


def test_list_gallery_models_scans_without_model_handler():
    rows = list_gallery_models("", shared_models=None)
    assert isinstance(rows, list)
    assert scan_model_category("diffusion_models") is not None
