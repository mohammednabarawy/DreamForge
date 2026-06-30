"""Tests for named upscale presets."""

from types import SimpleNamespace

from dreamforge_upscale_presets import (
    apply_upscale_preset_to_job,
    normalize_upscale_preset,
)


def test_normalize_upscale_preset():
    assert normalize_upscale_preset("2x") == "2x"
    assert normalize_upscale_preset("FAST_2X") == "fast_2x"
    assert normalize_upscale_preset("FAITHFUL_2X") == "faithful_2x"
    assert normalize_upscale_preset("fast_4x") == "fast_4x"
    assert normalize_upscale_preset("detail_2x") == "detail_2x"
    assert normalize_upscale_preset("bogus") is None


def test_apply_upscale_preset_1_5x():
    job = SimpleNamespace(upscale_preset="1.5x")
    patch = apply_upscale_preset_to_job(job)
    assert patch["upscale_by"] == 1.5
    assert patch["upscale_preset"] == "1.5x"


def test_apply_upscale_preset_fast_2x():
    job = SimpleNamespace(upscale_preset="fast_2x")
    patch = apply_upscale_preset_to_job(job)
    assert patch["upscale_by"] == 2.0
    assert patch["steps"] == 12
    assert patch["upscale_tile_width"] == 768


def test_apply_upscale_preset_fast_4x():
    job = SimpleNamespace(upscale_preset="fast_4x")
    patch = apply_upscale_preset_to_job(job)
    assert patch["upscale_by"] == 4.0
    assert patch["steps"] == 4
    assert patch["cfg_scale"] == 8.0
    assert patch["sampler"] == "euler"


def test_apply_upscale_preset_faithful_and_detail_2x():
    faithful = apply_upscale_preset_to_job(SimpleNamespace(upscale_preset="faithful_2x"))
    detail = apply_upscale_preset_to_job(SimpleNamespace(upscale_preset="detail_2x"))
    assert faithful["upscale_denoise"] == 0.22
    assert faithful["upscale_tile_padding"] == 64
    assert detail["upscale_denoise"] == 0.33
    assert detail["upscale_tile_padding"] == 128


def test_apply_upscale_preset_respects_explicit_overrides():
    job = SimpleNamespace(upscale_preset="fast_2x", steps=30, upscale_by=3.0)
    patch = apply_upscale_preset_to_job(job)
    assert "steps" not in patch
    assert "upscale_by" not in patch
    assert patch["upscale_preset"] == "fast_2x"
