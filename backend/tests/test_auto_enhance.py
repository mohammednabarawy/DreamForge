"""Tests for auto-enhance orchestration."""

from types import SimpleNamespace

from dreamforge_auto_enhance import (
    apply_auto_enhance_to_job,
    is_auto_enhance_job,
    parse_detection_targets,
    resolve_auto_enhance_plan,
)


def test_parse_detection_targets_from_prompt():
    assert parse_detection_targets("face, hands", None) == ["face", "hands"]
    assert parse_detection_targets("eyes and face", None) == ["eyes", "face"]


def test_resolve_face_detail_plan():
    job = SimpleNamespace(
        enhance_auto_fix=True,
        enhance_target="face",
        upscale_image="/tmp/portrait.png",
    )
    plan = resolve_auto_enhance_plan(job)
    assert plan["mode"] == "face_detail"
    assert plan["detail_target"] == "face"


def test_resolve_eyes_inpaint_plan():
    job = SimpleNamespace(
        enhance_target="eyes",
        input_image="/tmp/portrait.png",
    )
    plan = resolve_auto_enhance_plan(job)
    assert plan["mode"] == "inpaint_mask"
    assert plan["selection_kind"] == "eyes"


def test_apply_auto_enhance_face_sets_workflow_mode():
    job = SimpleNamespace(
        enhance_target="face",
        upscale_image="/tmp/portrait.png",
    )
    apply_auto_enhance_to_job(job)
    assert is_auto_enhance_job(job)
    assert job.workflow_mode == "face_detail"
    assert job.detail_target == "face"
    assert job.input_image == "/tmp/portrait.png"


def test_apply_auto_enhance_eyes_sets_inpaint_intent():
    job = SimpleNamespace(
        enhance_target="eyes",
        input_image="/tmp/portrait.png",
    )
    apply_auto_enhance_to_job(job)
    assert job.inpaint_intent == "improve_detail"
    assert job._auto_enhance_selection == "eyes"
