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
    assert info["scale"] == 2


def test_resolve_upscaler_legacy_2x_alias():
    info = resolve_upscaler("2x")
    assert info["filename"] == "OmniSR_X2_DIV2K.safetensors"


def test_resolve_upscaler_default_quality():
    info = resolve_upscaler("default")
    assert "NMKD" in info["filename"]


def test_inpaint_recipe_uses_high_cfg():
    recipe = edit_recipe("flux", "inpaint")
    assert recipe is not None
    assert recipe["cfg"] == 30.0
    assert recipe.get("inpaint_grow", 0) > 0


def test_edit_recipe_kontext_only_for_flux_kontext_family():
    assert edit_recipe("flux", "kontext") is None
    rk = edit_recipe("flux_kontext", "auto")
    assert rk is not None and rk["sampler_name"] == "euler"


def test_check_studio_edit_requires_kontext_download_when_no_unet(monkeypatch):
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


def test_check_studio_edit_skips_diffusion_when_unet_present(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_krita_resources.studio_edit_flux_unet_present",
        lambda models_root=None: True,
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
