"""Tests for deterministic dynamic presets and custom-node verification."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_desktop_bridge import handle_request
from dreamforge_dynamic_presets import apply_dynamic_preset, infer_style_from_intent
from dreamforge_workflow_planner import assess_custom_node_pack, custom_node_pack_present


def test_infer_style_from_intent_product_ad():
    assert infer_style_from_intent("Create a premium product ad for sneakers") == "product_ad"


def test_apply_dynamic_preset_merges_recipe_without_overriding_explicit_model():
    settings, meta = apply_dynamic_preset(
        "cinematic movie still with dramatic lighting",
        {"model": "my-custom-model.safetensors", "style": "none"},
    )
    assert settings["model"] == "my-custom-model.safetensors"
    assert meta["applied"].get("style") == "cinematic_scene"
    assert settings.get("performance") == "HiDream"


def test_apply_dynamic_preset_is_deterministic():
    first, _ = apply_dynamic_preset("fast draft concept sketch", {})
    second, _ = apply_dynamic_preset("fast draft concept sketch", {})
    assert first == second


def test_apply_dynamic_preset_handles_existing_list_values():
    settings, meta = apply_dynamic_preset(
        "Professional product advertisement",
        {"styles": ["Style: existing"], "lora": []},
    )
    assert settings["styles"] == ["Style: existing"]
    assert meta["applied"].get("style") == "product_ad"


def test_custom_node_pack_requires_registered_nodes_when_object_info_provided(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_workflow_planner._custom_node_directory_present",
        lambda _pack: True,
    )
    object_info = {"IPAdapterModelLoader": {}, "CheckpointLoaderSimple": {}}
    status = assess_custom_node_pack("ComfyUI_IPAdapter_plus", object_info=object_info)
    assert status["directory_present"] is True
    assert status["ready"] is False
    assert "IPAdapter" in status["missing_nodes"]

    full_info = {
        "IPAdapterModelLoader": {},
        "IPAdapter": {},
    }
    assert custom_node_pack_present("ComfyUI_IPAdapter_plus", object_info=full_info) is True


def test_suggest_dynamic_preset_bridge():
    payload = handle_request(
        '{"cmd":"suggest_dynamic_preset","params":{"intent":"product advertisement photo","settings":{}}}'
    )
    assert payload.get("ok") is True
    assert payload["dynamic_preset"]["applied"].get("style") == "product_ad"
