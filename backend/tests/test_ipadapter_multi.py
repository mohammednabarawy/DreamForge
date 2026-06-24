"""Graph tests for multi-slot IP-Adapter."""

from dreamforge_comfy_workflows import (
    _normalize_ipadapter_slots,
    comfy_ipadapter_controlnet_hybrid,
    comfy_ipadapter_reference,
)


def test_normalize_ipadapter_slots_from_reference_slots():
    args = {
        "reference_slots": [
            {"image": "style_a.png", "weight": 0.6, "stop_at": 0.5},
            {"image": "style_b.png", "weight": 0.4, "stop_at": 1.0},
        ]
    }
    slots = _normalize_ipadapter_slots(args)
    assert len(slots) == 2
    assert slots[0]["weight"] == 0.6


def test_multi_ipadapter_graph_chains_advanced_nodes():
    graph = comfy_ipadapter_reference(
        {
            "ckpt_name": "epicrealism-xl.safetensors",
            "prompt": "portrait",
            "negative": "",
            "reference_slots": [
                {"image": "a.png", "weight": 0.6, "stop_at": 0.5},
                {"image": "b.png", "weight": 0.4, "stop_at": 1.0},
            ],
            "ipadapter_model": "ip-adapter-plus_sdxl.safetensors",
            "clip_vision": "clip_vision_vit_h.safetensors",
            "width": 1024,
            "height": 1024,
        }
    )
    ipa_nodes = [node for node in graph.values() if node.get("class_type") == "IPAdapterAdvanced"]
    assert len(ipa_nodes) == 2
    assert ipa_nodes[0]["inputs"]["end_at"] == 0.5


def test_hybrid_ipadapter_controlnet_graph():
    graph = comfy_ipadapter_controlnet_hybrid(
        {
            "ckpt_name": "epicrealism-xl.safetensors",
            "prompt": "portrait",
            "negative": "",
            "reference_slots": [{"image": "style.png", "weight": 0.6, "stop_at": 0.5}],
            "structure_slot": {"image": "edges.png", "weight": 0.8, "stop_at": 0.9},
            "controlnet_model": "controlnet-canny-sdxl.safetensors",
            "ipadapter_model": "ip-adapter-plus_sdxl.safetensors",
            "clip_vision": "clip_vision_vit_h.safetensors",
            "width": 1024,
            "height": 1024,
        }
    )
    class_types = {node.get("class_type") for node in graph.values()}
    assert "IPAdapterAdvanced" in class_types
    assert "ControlNetApplyAdvanced" in class_types
