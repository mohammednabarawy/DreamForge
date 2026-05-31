from types import SimpleNamespace
from unittest.mock import patch

import pytest

from dreamforge_arabic_composite import (
    _pipeline_args,
    arabic_composite_requested,
    extract_arabic_text,
    resolve_arabic_text,
    run_arabic_text_composite_job,
)


def test_extract_arabic_text_from_quoted_string():
    text = 'Add headline "مرحبا بالعالم" to the poster'
    assert extract_arabic_text(text) == "مرحبا بالعالم"


def test_arabic_composite_requested_by_workflow_mode():
    job = SimpleNamespace(workflow_mode="arabic_text_composite", style="none")
    assert arabic_composite_requested(job) is True


def test_arabic_composite_requested_for_arabic_poster_style():
    job = SimpleNamespace(style="arabic_poster", arabic_text="اختبار")
    assert arabic_composite_requested(job) is True


def test_resolve_arabic_text_prefers_explicit_field():
    job = SimpleNamespace(arabic_text="نص", prompt="other")
    assert resolve_arabic_text(job) == "نص"


def test_pipeline_args_defaults_cfg_scale_when_unset():
    job = SimpleNamespace(cfg_scale=None, performance=None, steps=None)
    args = _pipeline_args(
        job=job,
        base_args=SimpleNamespace(performance="Speed", cfg_scale=None),
        model={"name": "test.safetensors"},
        prompt="lobby",
        negative="",
        width=1024,
        height=1024,
        seed=1,
    )
    assert args.cfg_scale == 7.0
    assert args.performance == "Speed"
    assert args.font_size is None
    assert args.padding == 60
    assert args.opacity == 1.0


def test_apply_preset_fills_text_pipeline_defaults():
    from arabic_poster_pipeline import apply_preset

    args = SimpleNamespace(
        arabic_text="مرحبا",
        font_style="default",
        harmonize=0.35,
        performance="Speed",
    )
    apply_preset(args)
    assert hasattr(args, "font_size")
    assert args.font_size is None
    assert args.padding == 60
    assert args.text_color == "255,255,255"


def test_run_arabic_text_composite_job_requires_text():
    job = SimpleNamespace(workflow_mode="arabic_text_composite", prompt="poster")
    result = run_arabic_text_composite_job(
        job=job,
        base_args=SimpleNamespace(),
        model={"name": "test.safetensors"},
        prompt="scene",
        negative="",
        width=512,
        height=512,
        seed=1,
    )
    assert result["status"] == "error"


@patch("arabic_poster_pipeline.run_full_pipeline", return_value=["/tmp/out.png"])
def test_run_arabic_text_composite_job_success(mock_pipeline):
    job = SimpleNamespace(
        workflow_mode="arabic_text_composite",
        arabic_text="مرحبا",
        prompt="luxury lobby",
    )
    result = run_arabic_text_composite_job(
        job=job,
        base_args=SimpleNamespace(performance="Speed"),
        model={"name": "test.safetensors"},
        prompt="luxury lobby",
        negative="",
        width=512,
        height=512,
        seed=42,
    )
    assert result["status"] == "success"
    assert result["output_paths"] == ["/tmp/out.png"]
    mock_pipeline.assert_called_once()
