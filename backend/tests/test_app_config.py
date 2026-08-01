from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import dreamforge_app_config as app_config


def test_app_config_rejects_cloud_agent_provider(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(app_config.CONFIG_ENV, str(tmp_path / "app-config.json"))

    saved = app_config.save_app_config(
        {
            "agent": {
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
            }
        }
    )
    assert saved["agent"]["provider"] == "ollama"
    assert saved["agent"]["base_url"] == "http://localhost:11434"
    assert saved["agent"]["model"] == "gemma3:4b"
    assert saved["agent"]["api_key"] == ""
    assert saved["agent"]["api_key_configured"] is False
    raw = app_config.load_app_config(redacted=False)
    assert "api_key" not in raw["agent"]


def test_provider_presets_include_local_ollama_without_key():
    providers = {p["id"]: p for p in app_config.list_agent_providers()}
    assert set(providers) == {"embedded", "ollama", "lmstudio", "llamacpp"}
    assert all(p["mode"] == "local" for p in providers.values())
    assert all(p["requires_api_key"] is False for p in providers.values())
    assert providers["ollama"]["requires_api_key"] is False
    assert providers["ollama"]["base_url"] == "http://localhost:11434"


def test_agent_provider_requires_local_endpoint(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(app_config.CONFIG_ENV, str(tmp_path / "app-config.json"))
    result = app_config.test_agent_provider(
        {
            "agent": {
                "provider": "lmstudio",
                "base_url": "https://api.openai.com/v1",
                "model": "local-model",
            }
        }
    )
    assert result["ok"] is False
    assert result["detail"] == "local_endpoint_required"


def test_heuristic_edit_defaults_to_qwen_lightning_when_qwen_installed():
    result = app_config._heuristic_agent_plan(
        "Change the jacket to navy blue, keep the face unchanged",
        {"prompt": ""},
        "D:/work/photo.png",
        [
            {
                "family": "qwen_image_edit",
                "caption": "Qwen Image Edit 2511",
                "engine_name": "qwen-image-edit-2511-Q4_K_M.gguf",
                "relative_path": "qwen-image-edit-2511-Q4_K_M.gguf",
            }
        ],
    )
    assert result["mode"] == "edit"
    assert result["patch"]["edit_type"] == "qwen_edit"
    assert result["patch"]["performance"] == "Lightning"
    assert result["patch"]["steps"] == 8
    assert result["patch"]["cfg_scale"] == 1.0


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
                "caption": "Qwen Image Edit 2511 Q4",
                "engine_name": "../diffusion_models/qwen-image-edit-2511-Q4_K_M.gguf",
                "relative_path": "qwen-image-edit-2511-Q4_K_M.gguf",
            },
        ],
    )

    assert result["patch"]["edit_type"] == "qwen_edit"
    assert result["patch"]["model"] == "../diffusion_models/qwen-image-edit-2511-Q4_K_M.gguf"


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
    assert result["mode_contract"]["model_policy"] == "route_curated_model"
    assert "edit_type" in result["mode_contract"]["changed_fields"]
    assert result["patch"]["performance"] == "Quality"
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
    assert result["patch"]["edit_type"] == "qwen_edit"
    assert result["patch"]["cn_selection"] == "None"
    assert result["patch"]["cn_type"] == "None"
    assert result["patch"]["performance"] == "Lightning"
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

    assert result["patch"]["cn_selection"] == "None"
    assert result["patch"]["cn_type"] == "None"
    assert result["patch"]["performance"] == "Quality"
    assert result["patch"]["steps"] == 8
    assert result["patch"]["cfg_scale"] == 1.0
    assert result["patch"]["sampler"] == "euler"
    assert result["patch"]["scheduler"] == "simple"


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


def test_redact_config_civitai_api_key():
    red = app_config.redact_config({"ui": {"civitai_api_key": "secret-key-abcd"}})
    assert red["ui"]["civitai_api_key"] == ""
    assert red["ui"]["civitai_api_key_configured"] is True
    assert red["ui"]["civitai_api_key_tail"] == "abcd"


def test_save_app_config_preserves_civitai_key_on_empty_patch(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(app_config.CONFIG_ENV, str(tmp_path / "app-config.json"))
    app_config.save_app_config({"ui": {"civitai_api_key": "my-secret-key"}})
    saved = app_config.save_app_config({"ui": {"civitai_api_key": ""}})
    assert saved["ui"]["civitai_api_key_configured"] is True
    raw = app_config.load_app_config(redacted=False)
    assert raw["ui"]["civitai_api_key"] == "my-secret-key"


def test_backend_can_explicitly_clear_provider_key(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(app_config.CONFIG_ENV, str(tmp_path / "config.json"))
    app_config.save_app_config({"ui": {"huggingface_api_key": "hf-secret"}})
    app_config.save_app_config(
        {"ui": {"huggingface_api_key": ""}}, preserve_redacted_secrets=False
    )
    assert app_config.load_app_config(redacted=False)["ui"]["huggingface_api_key"] == ""


def test_load_app_config_defaults_experience_pro_for_legacy_file(tmp_path: Path, monkeypatch):
    path = tmp_path / "app-config.json"
    monkeypatch.setenv(app_config.CONFIG_ENV, str(path))
    path.write_text(
        json.dumps({"ui": {"studio_mode": "generate", "advanced_mode": False}}),
        encoding="utf-8",
    )
    cfg = app_config.load_app_config(redacted=False)
    assert cfg["ui"]["experience"] == "pro"


def test_load_app_config_defaults_experience_simple_for_fresh_install(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(app_config.CONFIG_ENV, str(tmp_path / "missing-app-config.json"))
    cfg = app_config.load_app_config(redacted=False)
    assert cfg["ui"]["experience"] == "simple"


def test_save_app_config_simple_experience_clears_agent_mode(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(app_config.CONFIG_ENV, str(tmp_path / "app-config.json"))
    saved = app_config.save_app_config(
        {"ui": {"experience": "simple", "studio_mode": "agent"}},
    )
    assert saved["ui"]["experience"] == "simple"
    assert saved["ui"]["studio_mode"] == "generate"


def test_qwen_lightning_defaults_not_applied_for_quality():
    patch = {"edit_type": "qwen_edit", "performance": "Quality", "steps": 30, "cfg_scale": 5.0}
    app_config._force_qwen_lightning_defaults(patch)
    assert patch["performance"] == "Quality"
    assert patch["steps"] == 30
    assert patch["cfg_scale"] == 5.0


def test_qwen_lightning_defaults_apply_for_speed_modes():
    patch = {"edit_type": "qwen_edit", "performance": "Speed"}
    app_config._force_qwen_lightning_defaults(patch)
    assert patch["performance"] == "Lightning"
    assert patch["steps"] == 8
    assert patch["cfg_scale"] == 1.0


def test_save_app_config_persists_custom_tools(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(app_config.CONFIG_ENV, str(tmp_path / "app-config.json"))
    saved = app_config.save_app_config(
        {
            "custom_tools": [
                {
                    "id": "custom_1",
                    "name": "Pixel Art",
                    "description": "Test tool",
                    "workflow_path": "D:/workflows/pixel.json",
                    "bindings": {},
                }
            ]
        }
    )
    assert saved["custom_tools"][0]["name"] == "Pixel Art"
    reloaded = app_config.load_app_config(redacted=False)
    assert reloaded["custom_tools"][0]["workflow_path"] == "D:/workflows/pixel.json"


def test_agent_provider_change_resets_defaults(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(app_config.CONFIG_ENV, str(tmp_path / "app-config.json"))
    
    # 1. Start with Ollama configuration
    saved1 = app_config.save_app_config(
        {
            "agent": {
                "provider": "ollama",
                "base_url": "http://localhost:11434",
                "model": "gemma3:4b",
            }
        }
    )
    assert saved1["agent"]["provider"] == "ollama"
    assert saved1["agent"]["base_url"] == "http://localhost:11434"
    assert saved1["agent"]["model"] == "gemma3:4b"
    
    # 2. Change provider to lmstudio (without specifying base_url/model)
    saved2 = app_config.save_app_config(
        {
            "agent": {
                "provider": "lmstudio",
            }
        }
    )
    assert saved2["agent"]["provider"] == "lmstudio"
    # Should reset base_url and model to lmstudio preset defaults:
    assert saved2["agent"]["base_url"] == "http://localhost:1234/v1"
    assert saved2["agent"]["model"] == "local-model"

