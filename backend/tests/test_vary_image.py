"""Tests for Fooocus-style Vary presets."""

from types import SimpleNamespace

from dreamforge_vary_image import apply_vary_amount_to_job, normalize_vary_amount


def test_normalize_vary_amount():
    assert normalize_vary_amount("subtle") == "subtle"
    assert normalize_vary_amount("STRONG") == "strong"
    assert normalize_vary_amount("medium") is None


def test_apply_vary_subtle_sets_img2img_strength():
    job = SimpleNamespace(vary_amount="subtle")
    patch = apply_vary_amount_to_job(job)
    assert patch["vary_amount"] == "subtle"
    assert patch["reference_role"] == "restyle"
    assert patch["cn_type"] == "img2img"
    assert patch["edit_strength"] == 0.3


def test_apply_vary_strong_keeps_explicit_strength():
    job = SimpleNamespace(vary_amount="strong", edit_strength=0.45)
    patch = apply_vary_amount_to_job(job)
    assert patch["vary_amount"] == "strong"
    assert "edit_strength" not in patch
