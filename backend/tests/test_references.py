"""Tests for multi-slot reference resolution."""

from types import SimpleNamespace

from dreamforge_references import (
    apply_reference_slots_to_job,
    coerce_reference_slots,
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


def test_invalid_restyle_mix():
    slots = [
        {"path": "/a.png", "role": "restyle"},
        {"path": "/b.png", "role": "image_prompt"},
    ]
    comp = resolve_reference_composition(slots)
    assert comp["mode"] == "invalid"
