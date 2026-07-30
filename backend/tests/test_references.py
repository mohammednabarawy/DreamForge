"""Tests for multi-slot reference resolution."""

from types import SimpleNamespace

from dreamforge_references import (
    apply_reference_slots_to_job,
    coerce_reference_slots,
    character_binding_prompt,
    family_reference_mechanism,
    reconcile_slot_roles,
    resolve_reference_composition,
)


def test_coerce_reference_slots_from_legacy_image_prompt():
    job = SimpleNamespace(
        reference_image="/tmp/style.png",
        reference_role="image_prompt",
        reference_weight=0.6,
        cn_stop=0.5,
    )
    slots = coerce_reference_slots(job)
    assert len(slots) == 1
    assert slots[0]["role"] == "image_prompt"
    assert slots[0]["weight"] == 0.6
    assert slots[0]["stop_at"] == 0.5


def test_coerce_reference_slots_from_array():
    job = SimpleNamespace(
        references=[
            {"path": "/a.png", "role": "image_prompt", "weight": 0.6, "stop_at": 0.5},
            {"path": "/b.png", "role": "structure", "weight": 0.8, "stop_at": 0.9},
        ]
    )
    slots = coerce_reference_slots(job)
    assert len(slots) == 2
    assert slots[1]["role"] == "structure"


def test_resolve_hybrid_composition():
    slots = [
        {"path": "/style.png", "role": "image_prompt", "weight": 0.6, "stop_at": 0.5},
        {"path": "/edge.png", "role": "structure", "weight": 0.8, "stop_at": 0.9},
    ]
    comp = resolve_reference_composition(slots)
    assert comp["mode"] == "ipadapter_controlnet"
    assert len(comp["ipadapter_slots"]) == 1
    assert comp["structure_slot"]["path"] == "/edge.png"


def test_apply_reference_slots_sets_hybrid_workflow_mode():
    job = SimpleNamespace(
        references=[
            {"path": "/style.png", "role": "image_prompt", "weight": 0.6, "stop_at": 0.5},
            {"path": "/edge.png", "role": "structure", "weight": 0.8, "stop_at": 0.9},
        ]
    )
    apply_reference_slots_to_job(job)
    assert job.workflow_mode == "ipadapter_controlnet"
    assert job.cn_type == "canny"


def test_restyle_plus_image_prompt_is_valid_multi_reference():
    slots = [
        {"path": "/a.png", "role": "restyle"},
        {"path": "/b.png", "role": "image_prompt"},
    ]
    comp = resolve_reference_composition(slots)
    assert comp["mode"] == "restyle"
    assert comp["restyle_slot"]["path"] == "/a.png"
    assert [s["path"] for s in comp["ipadapter_slots"]] == ["/b.png"]


def test_source_edit_plus_image_prompt_keeps_edit_workflow():
    job = SimpleNamespace(
        references=[
            {"path": "/src.png", "role": "source_edit", "weight": 0.9},
            {"path": "/face.png", "role": "image_prompt", "weight": 0.7},
        ],
        input_image="/src.png",
        edit_type="kontext",
        workflow_mode="kontext",
    )
    apply_reference_slots_to_job(job)
    assert job.workflow_mode != "ipadapter"


def test_hidream_o1_family_uses_native_reference_mechanism():
    assert family_reference_mechanism("hidream_o1") == "hidream_o1_reference"


def test_reconcile_promotes_restyle_base_with_structure():
    slots = [
        {"path": "/face.png", "role": "restyle"},
        {"path": "/edge.png", "role": "structure"},
    ]
    reconciled = reconcile_slot_roles(slots)
    assert reconciled[0]["role"] == "image_prompt"
    comp = resolve_reference_composition(reconciled)
    assert comp["mode"] == "ipadapter_controlnet"


def test_apply_face_plus_structure_routes_hybrid():
    job = SimpleNamespace(
        references=[
            {"path": "/face.png", "role": "restyle", "weight": 0.8},
            {"path": "/edge.png", "role": "structure", "weight": 0.9},
        ]
    )
    apply_reference_slots_to_job(job)
    assert job.workflow_mode == "ipadapter_controlnet"


def test_invalid_restyle_structure_mix_without_reconcile():
    slots = [
        {"path": "/a.png", "role": "restyle"},
        {"path": "/b.png", "role": "structure"},
    ]
    comp = resolve_reference_composition(slots)
    assert comp["mode"] == "invalid"


def test_invalid_two_restyle_slots():
    slots = [
        {"path": "/a.png", "role": "restyle"},
        {"path": "/b.png", "role": "restyle"},
    ]
    comp = resolve_reference_composition(slots)
    assert comp["mode"] == "invalid"


def test_character_binding_preserves_metadata_and_prompt():
    job = SimpleNamespace(
        prompt="Two friends at a cafe",
        references=[
            {
                "path": "/a.png",
                "role": "image_prompt",
                "character_id": "character_a",
                "character_region": "left",
                "face_index": 1,
            },
            {
                "path": "/b.png",
                "role": "image_prompt",
                "character_id": "character_b",
                "character_region": "right",
            },
        ],
    )
    patch = apply_reference_slots_to_job(job)
    assert patch["references"][0]["face_index"] == 1
    assert "image 1 is Character A in the left region" in patch["character_binding_prompt"]
    assert "image 2 is Character B in the right region" in job.prompt
    assert job.preserve_character is True


def test_character_binding_prompt_ignores_unassigned_slots():
    assert character_binding_prompt([{"path": "/style.png", "role": "image_prompt"}]) == ""
