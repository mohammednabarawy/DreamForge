import os
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from dreamforge_hidream_o1_profiles import (  # noqa: E402
    apply_hidream_o1_dev_at_submit,
    hidream_o1_dev_family_options,
    hidream_o1_dev_resolution,
    is_hidream_o1_dev_checkpoint,
)
from modules.model_ui_defaults import family_performance_settings  # noqa: E402

MODEL = "hidream_o1_image_dev_mxfp8.safetensors"


def test_is_hidream_o1_dev_checkpoint():
    assert is_hidream_o1_dev_checkpoint(MODEL)
    assert not is_hidream_o1_dev_checkpoint("hidream_o1_image_full.safetensors")
    assert not is_hidream_o1_dev_checkpoint("HiDream-I1-Fast.safetensors")


def test_o1_dev_profile_steps_and_sampler():
    speed = hidream_o1_dev_family_options("Speed")
    assert speed["custom_steps"] == 22
    assert speed["cfg"] == 1.0
    assert speed["sampler_name"] == "lcm"
    assert speed["hidream_noise_scale"] == 7.6

    quality = hidream_o1_dev_family_options("Quality")
    assert quality["custom_steps"] == 28
    assert quality["hidream_patch_seam_smoothing"] is True
    assert quality["hidream_prompt_refinement"] is True


def test_o1_dev_resolutions():
    assert hidream_o1_dev_resolution("Lightning") == (1024, 1024)
    assert hidream_o1_dev_resolution("Speed", aspect_ratio="768x1344") == (1344, 1792)
    assert hidream_o1_dev_resolution("Quality", aspect_ratio="1344x768") == (2304, 1728)


def test_family_performance_uses_o1_dev_table():
    speed = family_performance_settings("hidream_o1", MODEL, "Speed")
    assert speed["custom_steps"] == 22
    assert speed["sampler_name"] == "lcm"


def test_submit_clamps_cfg_and_applies_profile():
    out = apply_hidream_o1_dev_at_submit(
        {"cfg": 7.0, "steps": 30, "performance": "Speed", "aspect_ratio": "768x768"},
        MODEL,
        performance="Speed",
    )
    assert out["cfg"] == 1.0
    assert out["steps"] == 22
    assert out["sampler_name"] == "lcm"
    assert out["width"] == 1536
    assert out["height"] == 1536
    assert out["negative"] == ""
    assert out["prompt_enhancer"] == "none"


def test_quality_profile_enables_prompt_refinement():
    out = apply_hidream_o1_dev_at_submit(
        {"performance": "Quality", "aspect_ratio": "1024x1024"},
        MODEL,
        performance="Quality",
    )
    assert out["hidream_prompt_refinement"] is True
    assert out["prompt_enhancer"] == "hyperprompt"
    assert out["hidream_patch_seam_smoothing"] is True


def test_manifest_warnings_detect_profile_drift():
    from dreamforge_hidream_o1_profiles import hidream_o1_manifest_warnings

    warnings = hidream_o1_manifest_warnings(
        MODEL,
        {
            "performance_selection": "Quality",
            "cfg": 5.0,
            "steps": 50,
            "sampler_name": "euler",
            "width": 1344,
            "height": 1344,
        },
    )
    assert any("cfg" in w for w in warnings)
    assert any("steps" in w for w in warnings)
    assert any("sampler" in w for w in warnings)
