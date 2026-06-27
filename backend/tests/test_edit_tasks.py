from types import SimpleNamespace

from dreamforge_edit_tasks import (
    apply_edit_task_defaults_to_job,
    EDIT_TASK_PRESETS,
    resolve_edit_task_defaults,
    normalize_edit_task,
)


def test_normalize_edit_task_aliases():
    assert normalize_edit_task("remove") == "remove"
    assert normalize_edit_task("improve_detail") == "repair"
    assert normalize_edit_task("modify_content") == "replace"
    assert normalize_edit_task("") is None


def test_resolve_edit_task_defaults_maps_inpaint_intent():
    repair = resolve_edit_task_defaults("repair", mode="inpaint")
    assert repair["edit_task"] == "repair"
    assert repair["inpaint_intent"] == "improve_detail"
    assert repair["requires_mask"] is True
    assert repair["hint"]

    inferred = resolve_edit_task_defaults(None, mode="inpaint", settings={"inpaint_intent": "improve_detail"})
    assert inferred["edit_task"] == "repair"


def test_resolve_edit_task_defaults_global_edit_for_edit_mode():
    defaults = resolve_edit_task_defaults(None, mode="edit")
    assert defaults["edit_task"] == "global_edit"
    assert defaults["scope"] == "source_image"
    assert defaults["requires_mask"] is False

    stale = resolve_edit_task_defaults(
        "global_edit",
        mode="edit",
        settings={"edit_type": "outpaint"},
    )
    assert stale["edit_type"] == "kontext"


def test_all_edit_task_presets_have_hints():
    for task, preset in EDIT_TASK_PRESETS.items():
        assert preset.get("hint"), f"missing hint for {task}"
        assert preset.get("scope")


def test_apply_edit_task_defaults_to_job_keeps_user_values():
    job = SimpleNamespace(edit_task="refine", inpaint_intent=None, edit_strength=None)
    defaults = apply_edit_task_defaults_to_job(job, mode="inpaint")
    assert defaults["edit_strength"] == 0.45
    assert job.inpaint_intent == "improve_detail"
    assert job.edit_strength == 0.45

    explicit = SimpleNamespace(edit_task="refine", inpaint_intent=None, edit_strength=0.9)
    apply_edit_task_defaults_to_job(explicit, mode="inpaint")
    assert explicit.edit_strength == 0.9


def test_apply_global_edit_task_clears_stale_local_route():
    job = SimpleNamespace(
        edit_task="global_edit",
        edit_type="outpaint",
        cn_type="outpaint",
        cn_selection="Custom...",
        edit_strength=None,
    )
    apply_edit_task_defaults_to_job(job, mode="edit")
    assert job.edit_type == "kontext"
    assert job.cn_type is None
    assert job.cn_selection is None
