from types import SimpleNamespace

from dreamforge_edit_tasks import (
    apply_edit_task_defaults_to_job,
    EDIT_TASK_PRESETS,
    merge_outfit_transfer_prompt,
    outfit_transfer_has_reference,
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


def test_resolve_edit_task_defaults_photo_restore():
    defaults = resolve_edit_task_defaults("photo_restore", mode="edit")
    assert defaults["edit_task"] == "photo_restore"
    assert defaults["steps"] == 6
    assert defaults["cfg"] == 1.5
    assert defaults["depth_strength"] == 0.15
    assert defaults["lineart_strength"] == 0.35
    assert defaults["face_preservation"] is True


def test_apply_photo_restore_task_clears_kontext_route():
    job = SimpleNamespace(
        edit_task="photo_restore",
        edit_type="kontext",
        cn_type="kontext",
        cn_selection="Custom...",
        edit_strength=None,
        steps=None,
        cfg_scale=None,
        depth_strength=None,
        lineart_strength=None,
        face_preservation=None,
    )
    apply_edit_task_defaults_to_job(job, mode="edit")
    assert job.edit_type == "auto"
    assert job.cn_type is None
    assert job.cn_selection is None
    assert job.steps == 6
    assert job.cfg_scale == 1.5
    assert job.sampler == "dpmpp_2s_ancestral_cfg_pp"
    assert job.depth_strength == 0.15
    assert job.lineart_strength == 0.35
    assert job.face_preservation is True


def test_apply_outfit_transfer_defaults_prefers_qwen_without_mask():
    job = SimpleNamespace(
        edit_task="outfit_transfer",
        edit_type="auto",
        cn_type="img2img",
        cn_selection="Custom...",
        edit_strength=None,
        inpaint_mask_path=None,
    )
    defaults = apply_edit_task_defaults_to_job(job, mode="edit")
    assert defaults["edit_task"] == "outfit_transfer"
    assert job.edit_type == "qwen_edit"
    assert job.cn_type is None
    assert job.cn_selection is None
    assert job.edit_strength == 1.0


def test_apply_outfit_transfer_defaults_uses_inpaint_with_mask():
    job = SimpleNamespace(
        edit_task="outfit_transfer",
        edit_type="qwen_edit",
        cn_type=None,
        cn_selection=None,
        edit_strength=None,
        inpaint_mask_path="/tmp/mask.png",
    )
    apply_edit_task_defaults_to_job(job, mode="edit")
    assert job.edit_type == "inpaint"
    assert job.cn_type == "inpaint"
    assert job.cn_selection == "Custom..."


def test_merge_outfit_transfer_prompt_adds_region_guidance():
    job = SimpleNamespace(
        edit_task="outfit_transfer",
        outfit_transfer_regions=["upper_body", "shoes_accessories"],
    )
    prompt = merge_outfit_transfer_prompt("swap outfit", job)
    assert "upper body clothing" in prompt
    assert "shoes and accessories" in prompt
    assert "only change clothing" in prompt


def test_outfit_transfer_has_reference():
    assert outfit_transfer_has_reference(SimpleNamespace(reference_images=["/tmp/outfit.png"]))
    assert outfit_transfer_has_reference(SimpleNamespace(reference_image="/tmp/outfit.png"))
    assert outfit_transfer_has_reference(
        SimpleNamespace(input_image="/tmp/person.png", references=[{"path": "/tmp/outfit.png"}])
    )
    assert not outfit_transfer_has_reference(SimpleNamespace(reference_images=[]))
    assert not outfit_transfer_has_reference(
        SimpleNamespace(input_image="/tmp/person.png", reference_image="/tmp/person.png")
    )
    assert not outfit_transfer_has_reference(
        SimpleNamespace(input_image="/tmp/person.png", references=[{"path": "/tmp/person.png"}])
    )
