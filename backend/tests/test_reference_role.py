from types import SimpleNamespace

from dreamforge_reference_role import (
    infer_reference_role,
    is_upscale_reference_role,
    plan_mode_from_reference_role,
)


def test_infer_reference_role_explicit():
    job = SimpleNamespace(reference_role="image_prompt", input_image="/tmp/a.png")
    assert infer_reference_role(job) == "image_prompt"


def test_infer_reference_role_generate_restyle():
    job = SimpleNamespace(
        workflow_mode="generate",
        input_image="/tmp/ref.png",
        reference_image="/tmp/ref.png",
        upscale_image="/tmp/stale.png",
    )
    assert infer_reference_role(job, studio_mode="generate") == "restyle"


def test_infer_reference_role_stale_upscale_ignored_with_input():
    job = SimpleNamespace(
        input_image="/tmp/edit.png",
        upscale_image="/tmp/stale.png",
        edit_type="kontext",
    )
    assert infer_reference_role(job, studio_mode="edit") == "source_edit"
    assert is_upscale_reference_role(job, studio_mode="edit") is False


def test_is_upscale_reference_role_only_upscale_path():
    job = SimpleNamespace(upscale_image="/tmp/up.png", input_image=None)
    assert is_upscale_reference_role(job, studio_mode="upscale") is True

    generate_job = SimpleNamespace(
        reference_role="restyle",
        workflow_mode="generate",
        input_image="/tmp/ref.png",
        upscale_image="/tmp/stale.png",
    )
    assert is_upscale_reference_role(generate_job, studio_mode="generate") is False


def test_plan_mode_from_reference_role():
    generate_job = SimpleNamespace(
        reference_role="restyle",
        workflow_mode="generate",
        input_image="/tmp/ref.png",
    )
    assert plan_mode_from_reference_role(generate_job) == "generate"

    edit_job = SimpleNamespace(reference_role="source_edit", input_image="/tmp/a.png")
    assert plan_mode_from_reference_role(edit_job) == "edit"

    upscale_job = SimpleNamespace(reference_role="upscale", upscale_image="/tmp/a.png")
    assert plan_mode_from_reference_role(upscale_job) == "upscale"
