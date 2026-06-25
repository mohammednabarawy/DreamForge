"""Tests for Krita-derived studio resource catalog."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_krita_recipes import edit_recipe
from dreamforge_krita_resources import resolve_upscaler


def test_resolve_upscaler_fast_2x():
    info = resolve_upscaler("fast_2x")
    assert info["filename"] == "OmniSR_X2_DIV2K.safetensors"
    assert info["workflow"] == "basic"
    assert info["scale"] == 2


def test_resolve_upscaler_legacy_2x_alias():
    info = resolve_upscaler("2x")
    assert info["filename"] == "OmniSR_X2_DIV2K.safetensors"
    assert info["workflow"] == "basic"


def test_resolve_upscaler_default_quality():
    info = resolve_upscaler("default")
    assert info["filename"] == "4x-UltraSharp.pth"
    assert info["workflow"] == "ultimate_sd"


def test_resolve_upscaler_pid_flux1_4k():
    info = resolve_upscaler("pid_flux1_4k")
    assert info["workflow"] == "pid_flux"
    assert info["filename"] == "pid_flux1_1024_to_4096_4step_mxfp8.safetensors"


def test_resolve_upscaler_default_is_pid_flux1_4k():
    info = resolve_upscaler(None)
    assert info["method"] == "ultimate_sd_upscale"
    assert info["workflow"] == "ultimate_sd"


def test_inpaint_recipe_uses_high_cfg():
    recipe = edit_recipe("flux", "inpaint")
    assert recipe is not None
    assert recipe["cfg"] == 30.0
    assert recipe.get("inpaint_grow", 0) > 0


def test_edit_recipe_kontext_only_for_flux_kontext_family():
    assert edit_recipe("flux", "kontext") is None
    rk = edit_recipe("flux_kontext", "auto")
    assert rk is not None and rk["sampler_name"] == "euler"


def test_check_studio_edit_requires_kontext_download_when_missing(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_krita_resources.studio_edit_flux_unet_present",
        lambda models_root=None: False,
    )
    monkeypatch.setattr(
        "dreamforge_krita_resources.companion_file_present",
        lambda *args, **kwargs: False,
    )
    from dreamforge_krita_resources import check_studio_resources

    miss = check_studio_resources("edit")
    assert any(m.get("id") == "diffusion_flux_kontext_fp8_scaled" for m in miss)


def test_check_studio_inpaint_requires_flux_fill_when_missing(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_krita_resources.studio_inpaint_flux_fill_present",
        lambda models_root=None: False,
    )
    monkeypatch.setattr(
        "dreamforge_krita_resources.companion_file_present",
        lambda *args, **kwargs: False,
    )
    from dreamforge_krita_resources import check_studio_resources

    miss = check_studio_resources("inpaint")
    assert any(m.get("id") == "diffusion_flux_fill_dev" for m in miss)


def test_inpaint_mask_recipe_values_defaults():
    from dreamforge_krita_resources import inpaint_mask_recipe_values

    values = inpaint_mask_recipe_values("inpaint")
    assert values["inpaint_grow"] >= 0
    assert values["inpaint_feather"] >= 0
    assert values["inpaint_mask_grow_by"] > 0


def test_stitch_and_composite_helpers():
    pytest = __import__("pytest")
    Image = pytest.importorskip("PIL.Image")
    from dreamforge_krita_resources import (
        composite_inpaint_result,
        stitch_kontext_reference_images,
    )

    a = Image.new("RGB", (8, 8), color=(255, 0, 0))
    b = Image.new("RGB", (8, 8), color=(0, 255, 0))
    stitched = stitch_kontext_reference_images([a, b])
    assert stitched.size[0] == 16

    original = Image.new("RGB", (4, 4), color=(0, 0, 255))
    generated = Image.new("RGB", (4, 4), color=(255, 0, 0))
    mask = Image.new("L", (4, 4), color=0)
    mask.putpixel((0, 0), 255)
    merged = composite_inpaint_result(original, generated, mask)
    assert merged.getpixel((3, 3)) == (0, 0, 255)


def test_check_studio_upscale_requires_only_selected_upscaler(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_krita_resources.companion_file_present",
        lambda *args, **kwargs: False,
    )
    from dreamforge_krita_resources import check_studio_resources

    fast_2x = check_studio_resources("upscale", upscale_method="fast_2x")
    fast_ids = {m.get("id") for m in fast_2x}
    assert "upscaler_omnisr_2x" in fast_ids
    assert "upscaler_ultrasharp_legacy" not in fast_ids
    assert "upscaler_nmkd_4x" not in fast_ids

    default = check_studio_resources("upscale", upscale_method="default")
    default_ids = {m.get("id") for m in default}
    assert "upscaler_ultrasharp_legacy" in default_ids
    assert "upscaler_nmkd_4x" not in default_ids
    assert "upscaler_omnisr_2x" not in default_ids

    pid = check_studio_resources("upscale", upscale_method="pid_flux1_4k")
    pid_ids = {m.get("id") for m in pid}
    assert "pid_flux1_4k_model" in pid_ids
    assert "pid_gemma2_text_encoder" in pid_ids
    assert "upscaler_ultrasharp_legacy" not in pid_ids

    pid_bf16 = check_studio_resources("upscale", upscale_method="pid_flux1_4k_bf16")
    pid_bf16_ids = {m.get("id") for m in pid_bf16}
    assert "pid_flux1_4k_model_bf16" in pid_bf16_ids
    assert "upscaler_ultrasharp_legacy" not in pid_bf16_ids


def test_check_studio_edit_skips_kontext_download_when_present(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_krita_resources.studio_edit_flux_unet_present",
        lambda models_root=None: True,
    )
    monkeypatch.setattr(
        "dreamforge_krita_resources.companion_file_present",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "dreamforge_cli_inventory.companion_file_present",
        lambda *args, **kwargs: True,
    )
    from dreamforge_krita_resources import check_studio_resources

    assert check_studio_resources("edit") == []


def test_base_flux_dev_does_not_satisfy_kontext_readiness(tmp_path, monkeypatch):
    models = tmp_path / "models"
    dm = models / "diffusion_models"
    dm.mkdir(parents=True)
    weight = dm / "flux1-dev-fp8.safetensors"
    weight.write_bytes(b"0")
    real_stat = Path.stat

    def fake_stat(path, *args, **kwargs):
        stat = real_stat(path, *args, **kwargs)
        if Path(path) == weight:
            return type("Stat", (), {**{name: getattr(stat, name) for name in dir(stat) if name.startswith("st_")}, "st_size": 901 * 1024 * 1024})()
        return stat

    monkeypatch.setattr(Path, "stat", fake_stat)
    from dreamforge_krita_resources import studio_edit_flux_unet_present

    assert studio_edit_flux_unet_present(models) is False


def test_plan_inpaint_crop_stitch_for_large_image_with_small_mask():
    pytest = __import__("pytest")
    Image = pytest.importorskip("PIL.Image")
    from dreamforge_krita_resources import (
        plan_inpaint_crop_stitch,
        prepare_inpaint_mask_image,
        stitch_inpaint_crop,
    )

    image = Image.new("RGB", (2400, 1800), color=(10, 20, 30))
    mask = Image.new("L", (2400, 1800), color=0)
    for x in range(900, 1100):
        for y in range(700, 900):
            mask.putpixel((x, y), 255)
    plan = plan_inpaint_crop_stitch(image, mask, grow=8, feather=4)
    assert plan is not None
    box = plan["box"]
    assert box[2] - box[0] < 2400
    assert box[3] - box[1] < 1800
    stitched = stitch_inpaint_crop(
        image,
        Image.new("RGB", plan["crop_image"].size, color=(200, 100, 50)),
        box,
    )
    assert stitched.size == image.size
    assert stitched.getpixel((0, 0)) == (10, 20, 30)
    assert stitched.getpixel((1000, 800)) == (200, 100, 50)

    soft_bytes, soft = prepare_inpaint_mask_image(mask.crop(box), grow=4, feather=8, hard=False)
    hard_bytes, hard = prepare_inpaint_mask_image(mask.crop(box), grow=4, feather=8, hard=True)
    plain_bytes, plain = prepare_inpaint_mask_image(mask.crop(box), grow=4, feather=0, hard=False)
    assert len(soft_bytes) > 0 and len(hard_bytes) > 0
    assert list(hard.getdata()) == list(plain.getdata())
    assert list(soft.getdata()) != list(hard.getdata())


def test_plan_inpaint_crop_stitch_skips_small_images():
    pytest = __import__("pytest")
    Image = pytest.importorskip("PIL.Image")
    from dreamforge_krita_resources import plan_inpaint_crop_stitch

    image = Image.new("RGB", (1024, 1024), color=(0, 0, 0))
    mask = Image.new("L", (1024, 1024), color=0)
    mask.putpixel((512, 512), 255)
    assert plan_inpaint_crop_stitch(image, mask) is None
