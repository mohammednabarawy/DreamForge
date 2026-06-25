"""Tests for named inpaint intent presets."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_inpaint_intent import (
    merge_inpaint_additional_prompt,
    normalize_inpaint_intent,
    resolve_inpaint_intent_params,
)


def test_normalize_inpaint_intent_defaults_unknown():
    assert normalize_inpaint_intent(None) == "default"
    assert normalize_inpaint_intent("bogus") == "default"


def test_resolve_inpaint_intent_params_modify_content():
    job = SimpleNamespace(inpaint_intent="modify_content")
    params = resolve_inpaint_intent_params(job)
    assert params["inpaint_intent"] == "modify_content"
    assert params["edit_strength"] == 1.0
    assert params["inpaint_grow"] == 8
    assert params["inpaint_feather"] == 8
    assert params["inpaint_mask_grow_by"] == 16
    assert params["requires_fill_engine"] is True


def test_resolve_inpaint_intent_params_improve_detail():
    job = SimpleNamespace(inpaint_intent="improve_detail")
    params = resolve_inpaint_intent_params(job)
    assert params["edit_strength"] == 0.52
    assert params["requires_fill_engine"] is True


def test_resolve_inpaint_intent_params_job_override_wins():
    job = SimpleNamespace(
        inpaint_intent="default",
        edit_strength=0.61,
        inpaint_mask_grow_by=12,
    )
    params = resolve_inpaint_intent_params(job)
    assert params["edit_strength"] == 0.61
    assert params["inpaint_mask_grow_by"] == 12


def test_merge_inpaint_additional_prompt_only_for_detail_modes():
    job = SimpleNamespace(
        inpaint_intent="improve_detail",
        inpaint_additional_prompt="sharper eyes",
    )
    assert merge_inpaint_additional_prompt("fix face", job) == "fix face. sharper eyes"

    default_job = SimpleNamespace(inpaint_intent="default", inpaint_additional_prompt="ignored")
    assert merge_inpaint_additional_prompt("fix face", default_job) == "fix face"
