"""Integration tests for brain plan preview across REST, bridge, agent, and WebUI helpers."""

from __future__ import annotations

import json
import threading
import urllib.request
from socketserver import ThreadingTCPServer

from dreamforge_app_config import plan_agent_instruction
from dreamforge_brain import plan_user_intent
from dreamforge_desktop_bridge import cmd_brain_plan
from dreamforge_engine import DreamForgeEngine
from dreamforge_server import DreamForgeRESTHandler
from modules.ui.ui_agent_plan import _preset_hint, _request_plan


def test_engine_plan_includes_dynamic_preset():
    decision = DreamForgeEngine.plan(
        "Professional product advertisement for a luxury watch",
        current_settings={"prompt": "watch hero"},
    )
    preset = decision.get("dynamic_preset")
    assert isinstance(preset, dict)
    assert preset.get("applied", {}).get("style") == "product_ad"
    assert decision.get("mode_contract", {}).get("model_policy") in {
        "suggest_model",
        "manual_selection",
        "preserve_user_model",
        "route_curated_model",
    }


def test_engine_plan_contract_preserves_explicit_generate_model():
    decision = DreamForgeEngine.plan(
        "Professional product advertisement for a luxury watch",
        current_settings={
            "prompt": "watch hero",
            "model": "my-explicit-model.safetensors",
        },
    )
    contract = decision.get("mode_contract") or {}
    assert contract["model_policy"] == "preserve_user_model"
    assert contract["selected_model"] == "my-explicit-model.safetensors"


def test_plan_user_intent_includes_dynamic_preset():
    decision = plan_user_intent(
        "fast draft concept sketch of a dragon",
        current_settings={},
    )
    preset = decision.get("dynamic_preset")
    assert isinstance(preset, dict)
    assert preset.get("applied", {}).get("style") == "fast_draft"


def test_desktop_bridge_brain_plan_returns_decision():
    result = cmd_brain_plan({"instruction": "cinematic product hero shot"})
    assert result.get("ok") is True
    decision = result.get("decision") or {}
    assert decision.get("workflow_plan") or decision.get("patch")
    assert isinstance(decision.get("dynamic_preset"), dict)


def test_agent_plan_instruction_includes_dynamic_preset(tmp_path, monkeypatch):
    import dreamforge_app_config as app_config

    monkeypatch.setenv(app_config.CONFIG_ENV, str(tmp_path / "app-config.json"))
    result = plan_agent_instruction(
        {
            "instruction": "Instagram social post for a coffee shop",
            "settings": {"prompt": "latte art"},
            "model_gallery": [],
        }
    )
    assert result.get("ok") is True
    assert result.get("dynamic_preset", {}).get("applied", {}).get("style") == "social_post"
    assert isinstance(result.get("mode_contract"), dict)


def test_rest_brain_plan_endpoint():
    server = ThreadingTCPServer(("127.0.0.1", 0), DreamForgeRESTHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = json.dumps({"instruction": "product advertisement photo"}).encode("utf-8")
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/brain/plan",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        assert body.get("schema_version") or body.get("workflow_plan") or body.get("patch")
        preset = body.get("dynamic_preset")
        assert isinstance(preset, dict)
        assert preset.get("applied", {}).get("style") == "product_ad"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_ui_agent_plan_preset_hint():
    hint = _preset_hint(
        {
            "dynamic_preset": {
                "applied": {"style": "product_ad", "aspect_ratio": "1152x896"},
                "source": ["intent", "style_recipe"],
            }
        }
    )
    assert "product_ad" in hint
    assert "1152x896" in hint
    assert "intent" in hint


def test_ui_request_plan_returns_hint_for_product_intent():
    plan_json, hint = _request_plan("Professional product advertisement for headphones")
    plan = json.loads(plan_json)
    assert isinstance(plan, dict)
    assert plan.get("dynamic_preset", {}).get("applied", {}).get("style") == "product_ad"
    assert "product_ad" in hint
