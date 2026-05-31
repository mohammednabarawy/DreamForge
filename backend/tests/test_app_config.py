from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import dreamforge_app_config as app_config


def test_app_config_redacts_and_preserves_api_key(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(app_config.CONFIG_ENV, str(tmp_path / "app-config.json"))

    saved = app_config.save_app_config(
        {
            "agent": {
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
                "api_key": "sk-test-secret",
            }
        }
    )
    assert saved["agent"]["api_key"] == ""
    assert saved["agent"]["api_key_configured"] is True
    assert saved["agent"]["api_key_tail"] == "cret"

    saved_again = app_config.save_app_config({"agent": {"model": "gpt-4.1-mini"}})
    assert saved_again["agent"]["api_key_configured"] is True
    raw = app_config.load_app_config(redacted=False)
    assert raw["agent"]["api_key"] == "sk-test-secret"
    assert raw["agent"]["model"] == "gpt-4.1-mini"


def test_provider_presets_include_local_ollama_without_key():
    providers = {p["id"]: p for p in app_config.list_agent_providers()}
    assert providers["ollama"]["requires_api_key"] is False
    assert providers["ollama"]["base_url"] == "http://localhost:11434"


def test_agent_provider_missing_key_is_structured_failure(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(app_config.CONFIG_ENV, str(tmp_path / "app-config.json"))
    result = app_config.test_agent_provider(
        {
            "agent": {
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
            }
        }
    )
    assert result["ok"] is False
    assert result["detail"] == "api_key_missing"


def test_redacted_runtime_config_preserves_stored_key(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(app_config.CONFIG_ENV, str(tmp_path / "app-config.json"))
    monkeypatch.setattr(app_config, "_post_json", lambda *args, **kwargs: {})
    app_config.save_app_config(
        {
            "agent": {
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
                "api_key": "sk-live-secret",
            }
        }
    )
    result = app_config.test_agent_provider(
        {
            "agent": {
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
                "api_key": "",
                "api_key_configured": True,
            }
        }
    )
    assert result["detail"] != "api_key_missing"


def test_heuristic_edit_defaults_to_kontext_without_text_intent():
    result = app_config._heuristic_agent_plan(
        "Change the jacket to navy blue, keep the face unchanged",
        {"prompt": ""},
        "D:/work/photo.png",
        [
            {
                "family": "flux_kontext",
                "caption": "Flux Kontext",
                "engine_name": "flux1-dev-kontext_fp8_scaled.safetensors",
                "relative_path": "flux1-dev-kontext_fp8_scaled.safetensors",
            }
        ],
    )
    assert result["mode"] == "edit"
    assert result["patch"]["edit_type"] == "kontext"
    assert result["patch"]["cn_selection"] == "None"
    assert result["patch"]["cn_type"] == "None"
    assert result["patch"]["input_image"] == "D:/work/photo.png"


def test_heuristic_qwen_edit_picks_qwen_model_before_kontext():
    result = app_config._heuristic_agent_plan(
        "Edit this Arabic poster and preserve the exact text",
        {"prompt": ""},
        "D:/work/poster.png",
        [
            {
                "family": "flux_kontext",
                "caption": "Flux Kontext",
                "engine_name": "flux-kontext",
                "relative_path": "flux-kontext",
            },
            {
                "family": "qwen_image_edit",
                "caption": "Qwen Image Edit",
                "engine_name": "qwen-image-edit",
                "relative_path": "qwen-image-edit",
            },
        ],
    )

    assert result["patch"]["edit_type"] == "qwen_edit"
    assert result["patch"]["model"] == "qwen-image-edit"


def test_agent_plan_falls_back_to_local_edit_route(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(app_config.CONFIG_ENV, str(tmp_path / "app-config.json"))
    result = app_config.plan_agent_instruction(
        {
            "instruction": "Edit this Arabic poster and preserve the exact text",
            "selected_image": "D:/work/poster.png",
            "settings": {"prompt": "old"},
            "model_gallery": [
                {
                    "family": "qwen_image_edit",
                    "caption": "Qwen Image Edit",
                    "engine_name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
                    "relative_path": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
                }
            ],
        }
    )
    assert result["ok"] is True
    assert result["source"] == "local"
    assert result["mode"] == "edit"
    assert result["patch"]["input_image"] == "D:/work/poster.png"
    assert result["patch"]["edit_type"] == "qwen_edit"
    assert result["patch"]["steps"] == 50
    assert result["patch"]["cfg_scale"] == 4.0
    assert "fake Arabic" in result["patch"]["negative_prompt"]


def test_agent_plan_includes_dynamic_preset_for_product_intent(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(app_config.CONFIG_ENV, str(tmp_path / "app-config.json"))
    result = app_config.plan_agent_instruction(
        {
            "instruction": "Professional product advertisement photo for a luxury watch",
            "settings": {"prompt": "watch hero"},
            "model_gallery": [],
        }
    )
    assert result["ok"] is True
    preset = result.get("dynamic_preset")
    assert isinstance(preset, dict)
    assert preset.get("applied", {}).get("style") == "product_ad"
    assert result["patch"].get("style") == "product_ad"


def test_provider_plan_uses_schema_then_text_fallback(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(app_config.CONFIG_ENV, str(tmp_path / "app-config.json"))
    app_config.save_app_config(
        {
            "agent": {
                "provider": "lmstudio",
                "base_url": "http://127.0.0.1:1234/v1",
                "model": "local-model",
            }
        }
    )
    calls = []

    def fake_post(_url, payload, _api_key):
        calls.append(copy.deepcopy(payload))
        if "response_format" in payload:
            raise RuntimeError("schema unsupported")
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"message":"ok","mode":"image_edit","patch":{"prompt":"x","aspect_ratio":"auto"},"actions":[],"downloads":[]}'
                    }
                }
            ]
        }

    monkeypatch.setattr(app_config, "_post_json", fake_post)
    result = app_config.plan_agent_instruction(
        {
            "instruction": "edit this",
            "selected_image": "D:/image.png",
            "settings": {},
            "model_gallery": [
                {
                    "family": "qwen_image_edit",
                    "caption": "Qwen Image Edit",
                    "engine_name": "qwen-image-edit.safetensors",
                    "relative_path": "qwen-image-edit.safetensors",
                }
            ],
        }
    )
    assert len(calls) == 2
    assert calls[0]["response_format"]["type"] == "json_schema"
    assert "response_format" not in calls[1]
    assert "DreamForge routing field guide" in calls[0]["messages"][0]["content"]
    user_payload = json.loads(calls[0]["messages"][1]["content"])
    assert user_payload["available_model_summary"][0]["family"] == "qwen_image_edit"
    assert result["source"] == "provider"
    assert result["mode"] == "edit"
    assert result["patch"]["input_image"] == "D:/image.png"
    assert result["patch"]["edit_type"] == "kontext"
    assert result["patch"]["cn_selection"] == "None"
    assert result["patch"]["cn_type"] == "None"
    assert "aspect_ratio" not in result["patch"]


def test_generation_patch_drops_invalid_provider_values():
    patch = app_config._filter_generation_patch(
        {
            "prompt": "hello",
            "aspect_ratio": "auto",
            "edit_type": "image_edit",
            "performance": "high",
            "style": "made_up",
            "input_image": "D:/x.png",
            "unknown": True,
        }
    )
    assert patch == {
        "prompt": "hello",
        "performance": "Quality",
        "style": "image_edit",
        "input_image": "D:/x.png",
    }


def test_provider_route_sanitizes_invalid_control_values(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(app_config.CONFIG_ENV, str(tmp_path / "app-config.json"))
    app_config.save_app_config(
        {
            "agent": {
                "provider": "lmstudio",
                "base_url": "http://127.0.0.1:1234/v1",
                "model": "local-model",
            }
        }
    )

    def fake_post(_url, payload, _api_key):
        if "response_format" in payload:
            raise RuntimeError("schema unsupported")
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "message": "ok",
                                "mode": "edit",
                                "patch": {
                                    "prompt": "x",
                                    "edit_type": "qwen_edit",
                                    "cn_selection": "auto",
                                    "cn_type": "edit",
                                },
                                "actions": [],
                                "downloads": [],
                            }
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(app_config, "_post_json", fake_post)
    result = app_config.plan_agent_instruction(
        {
            "instruction": "edit Arabic text",
            "selected_image": "D:/image.png",
            "settings": {},
            "model_gallery": [],
        }
    )

    assert result["patch"]["cn_selection"] == "Custom..."
    assert result["patch"]["cn_type"] == "qwen_edit"
    assert result["patch"]["steps"] == 50
    assert result["patch"]["cfg_scale"] == 4.0


def test_provider_upscale_route_overrides_invalid_control_values(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(app_config.CONFIG_ENV, str(tmp_path / "app-config.json"))
    app_config.save_app_config(
        {
            "agent": {
                "provider": "lmstudio",
                "base_url": "http://127.0.0.1:1234/v1",
                "model": "local-model",
            }
        }
    )

    def fake_post(_url, payload, _api_key):
        if "response_format" in payload:
            raise RuntimeError("schema unsupported")
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "message": "ok",
                                "mode": "upscale",
                                "patch": {
                                    "prompt": "restore detail",
                                    "cn_selection": "None",
                                    "cn_type": "img2img",
                                },
                                "actions": [],
                                "downloads": [],
                            }
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(app_config, "_post_json", fake_post)
    result = app_config.plan_agent_instruction(
        {
            "instruction": "upscale this image",
            "selected_image": "D:/image.png",
            "settings": {},
            "model_gallery": [],
        }
    )

    assert result["mode"] == "upscale"
    assert result["patch"]["upscale_image"] == "D:/image.png"
    assert result["patch"]["cn_selection"] == "Custom..."
    assert result["patch"]["cn_type"] == "upscale"
