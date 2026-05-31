"""Daemon-owned DreamForge app config and agent provider checks."""

from __future__ import annotations

import copy
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from _paths import OUTPUTS_ROOT
from dreamforge_agent_tools import STYLE_RECIPES


CONFIG_ENV = "DREAMFORGE_APP_CONFIG_PATH"

PROVIDER_PRESETS: list[dict[str, Any]] = [
    {
        "id": "embedded",
        "label": "Embedded Llama.cpp (Local GGUF)",
        "mode": "local",
        "base_url": "",
        "default_model": "Qwen2.5-7B-Instruct-abliterated-v2.Q4_K_M.gguf",
        "requires_api_key": False,
        "test_kind": "embedded",
    },
    {
        "id": "ollama",
        "label": "Ollama",
        "mode": "local",
        "base_url": "http://localhost:11434",
        "default_model": "gemma3:4b",
        "requires_api_key": False,
        "test_kind": "ollama",
    },
    {
        "id": "lmstudio",
        "label": "LM Studio",
        "mode": "local",
        "base_url": "http://localhost:1234/v1",
        "default_model": "local-model",
        "requires_api_key": False,
        "test_kind": "openai_compatible",
    },
    {
        "id": "openai",
        "label": "OpenAI",
        "mode": "cloud",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "requires_api_key": True,
        "test_kind": "openai_compatible",
    },
    {
        "id": "openrouter",
        "label": "OpenRouter",
        "mode": "cloud",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o-mini",
        "requires_api_key": True,
        "test_kind": "openai_compatible",
    },
    {
        "id": "anthropic",
        "label": "Anthropic",
        "mode": "cloud",
        "base_url": "https://api.anthropic.com",
        "default_model": "claude-3-5-haiku-latest",
        "requires_api_key": True,
        "test_kind": "unsupported",
    },
    {
        "id": "google",
        "label": "Google Gemini",
        "mode": "cloud",
        "base_url": "https://generativelanguage.googleapis.com",
        "default_model": "gemini-2.0-flash",
        "requires_api_key": True,
        "test_kind": "unsupported",
    },
    {
        "id": "custom",
        "label": "Custom OpenAI-compatible",
        "mode": "custom",
        "base_url": "",
        "default_model": "",
        "requires_api_key": False,
        "test_kind": "openai_compatible",
    },
]

DEFAULT_APP_CONFIG: dict[str, Any] = {
    "agent": {
        "provider": "ollama",
        "base_url": "http://localhost:11434",
        "model": "gemma3:4b",
        "api_key": "",
        "custom_instructions": "",
        "approval_required": True,
        "auto_configure_workflows": True,
    },
    "privacy": {
        "cloud_confirmation_required": True,
        "allow_cloud_image_context": False,
    },
    "ui": {
        "studio_mode": "generate",
        "advanced_mode": False,
    },
}

_ALLOWED_ROOTS = {"agent", "privacy", "ui"}
_AGENT_KEYS = {
    "provider",
    "base_url",
    "model",
    "api_key",
    "custom_instructions",
    "approval_required",
    "auto_configure_workflows",
}
_PRIVACY_KEYS = {"cloud_confirmation_required", "allow_cloud_image_context"}
_UI_KEYS = {"studio_mode", "advanced_mode"}

_AGENT_FIELD_GUIDE = """
DreamForge routing field guide:
- generate: use for text-to-image when there is no source image to preserve. Let the user pick any library model in Generate mode.
- edit: use for source-image edits without a required mask. Default to FLUX Kontext (edit_type=kontext, cn_selection=None, cn_type=None) for identity continuity, relighting, style transfer, object swap, and most global edits. Use Qwen Image Edit (edit_type=qwen_edit) only when the user needs typography, logos, posters, Arabic/bilingual exact text, or semantic text-in-image changes. See docs/AGENT_DIFFUSION_GUIDE.md for model families and configs.
- inpaint: use only when a local region/mask is required or the user says mask, erase, remove this area, fix spot, fill, outpaint, cleanup edge, or background/object replacement with strict local preservation. Prefer FLUX Fill/inpaint models and require input_image plus inpaint_mask_path before running.
- upscale: use only for enlargement/restoration/detail enhancement of an existing image. Prefer RealESRGAN_x2 for fast 2x, SUPIR when available for high-realism repair, and do not use text-to-image generation for pure upscale.
- agent: use only when a required decision is impossible from the instruction, such as missing source image for an edit or missing mask for inpaint.

Conditioning and quality rules:
- For exact Arabic or brand typography, do not ask diffusion to invent glyphs from scratch. Route to Qwen Image Edit and ask for deterministic rendered text/reference integration when possible. Preserve glyph geometry, layout, and surrounding pixels.
- Qwen Image Edit public examples use text-aware image editing with about 50 inference steps and guidance around 4.0. For text/typography routes, prefer steps=50 and cfg_scale=4.0 unless the user requests speed.
- Qwen Image Edit is strong for both semantic and appearance editing: it can change objects/text while preserving unchanged regions. Use explicit preservation wording in the prompt.
- For face/character preservation, choose edit + kontext when the prompt emphasizes same identity, same character, consistency, or multi-turn continuity. Use input_image from selected_image when available.
- FLUX Kontext is the safer default for iterative edits and identity/reference continuity. Use direct prompts with one change per pass and explicitly name what must stay unchanged.
- For masked edits, preserve unmasked pixels, use mask-aware inpainting, and keep cn_type=inpaint.
- Use ControlNet/structural guidance only when the user asks to preserve pose, edges, depth, layout, or a sketch. Do not add it to normal Kontext edits.
- For structural preservation, keep the source image as input_image and prefer edit/inpaint over generate.
- Keep patch minimal. Do not invent files. Do not include secrets. Return JSON only.
""".strip()


def config_path() -> Path:
    override = os.environ.get(CONFIG_ENV)
    if override:
        return Path(override)
    return OUTPUTS_ROOT / "dreamforge" / "app-config.json"


def list_agent_providers() -> list[dict[str, Any]]:
    return copy.deepcopy(PROVIDER_PRESETS)


def provider_preset(provider_id: str) -> dict[str, Any]:
    for preset in PROVIDER_PRESETS:
        if preset["id"] == provider_id:
            return copy.deepcopy(preset)
    return provider_preset("custom")


def load_app_config(*, redacted: bool = True) -> dict[str, Any]:
    cfg = copy.deepcopy(DEFAULT_APP_CONFIG)
    path = config_path()
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            cfg = _merge_allowed(cfg, raw)
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return redact_config(cfg) if redacted else cfg


def save_app_config(incoming: dict[str, Any]) -> dict[str, Any]:
    existing = load_app_config(redacted=False)
    next_cfg = _merge_allowed(existing, incoming)

    agent_in = incoming.get("agent") if isinstance(incoming.get("agent"), dict) else {}
    if agent_in.get("clear_api_key"):
        next_cfg["agent"]["api_key"] = ""
    elif "api_key" in agent_in:
        api_key = str(agent_in.get("api_key") or "")
        if api_key:
            next_cfg["agent"]["api_key"] = api_key
        else:
            next_cfg["agent"]["api_key"] = existing.get("agent", {}).get("api_key", "")

    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(next_cfg, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return redact_config(next_cfg)


def redact_config(cfg: dict[str, Any]) -> dict[str, Any]:
    redacted = copy.deepcopy(cfg)
    api_key = str(redacted.get("agent", {}).get("api_key") or "")
    redacted.setdefault("agent", {})
    redacted["agent"]["api_key"] = ""
    redacted["agent"]["api_key_configured"] = bool(api_key)
    redacted["agent"]["api_key_tail"] = api_key[-4:] if api_key else ""
    return redacted


def test_agent_provider(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = _merge_runtime_config(load_app_config(redacted=False), config or {})
    agent = cfg.get("agent", {})
    provider = str(agent.get("provider") or "custom")
    preset = provider_preset(provider)
    base_url = str(agent.get("base_url") or preset.get("base_url") or "").rstrip("/")
    model = str(agent.get("model") or preset.get("default_model") or "").strip()
    api_key = str(agent.get("api_key") or "").strip()
    start = time.perf_counter()

    if provider == "embedded":
        from dreamforge_brain import XLC_AVAILABLE, EmbeddedLlamaCppProvider
        if not XLC_AVAILABLE:
            return _test_result(False, provider, model, start, "xllamacpp_not_installed")
        try:
            prov = EmbeddedLlamaCppProvider()
            path = prov._get_model_path()
            if not path.is_file():
                return _test_result(False, provider, model, start, f"gguf_model_missing: {path}")
            return _test_result(True, provider, model, start, "ok")
        except Exception as e:
            return _test_result(False, provider, model, start, str(e))

    if preset.get("requires_api_key") and not api_key:
        return _test_result(False, provider, model, start, "api_key_missing")
    if not base_url:
        return _test_result(False, provider, model, start, "base_url_missing")
    if not model:
        return _test_result(False, provider, model, start, "model_missing")
    if preset.get("test_kind") == "unsupported":
        return _test_result(
            False,
            provider,
            model,
            start,
            "connection_test_not_implemented_for_provider",
        )

    try:
        if preset.get("test_kind") == "ollama" and "/v1" not in base_url:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "Reply with only: ok"}],
                "stream": False,
            }
            _post_json(f"{base_url}/api/chat", payload, None)
        else:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "Reply with only: ok"}],
                "temperature": 0,
                "max_tokens": 8,
            }
            _post_json(f"{base_url}/chat/completions", payload, api_key or None)
    except Exception as exc:  # noqa: BLE001 - bridge must return structured failures
        return _test_result(False, provider, model, start, _redact(str(exc), api_key))

    return _test_result(True, provider, model, start, "ok")


def plan_agent_instruction(params: dict[str, Any]) -> dict[str, Any]:
    cfg = load_app_config(redacted=False)
    instruction = str(params.get("instruction") or "").strip()
    current = params.get("settings") if isinstance(params.get("settings"), dict) else {}
    selected_image = str(params.get("selected_image") or "").strip()
    model_gallery = params.get("model_gallery")
    if not isinstance(model_gallery, list):
        model_gallery = []

    if not instruction:
        return {
            "ok": False,
            "error": "instruction_required",
            "message": "Tell the agent what you want to create or edit.",
        }

    from dreamforge_dynamic_presets import apply_dynamic_preset

    enriched, dynamic_preset = apply_dynamic_preset(instruction, current)
    original = dict(current)

    provider_plan = _provider_agent_plan(
        cfg,
        instruction,
        enriched,
        selected_image,
        model_gallery,
        dynamic_preset=dynamic_preset,
        original_settings=original,
    )
    if provider_plan:
        return provider_plan

    result = _heuristic_agent_plan(
        instruction,
        enriched,
        selected_image,
        model_gallery,
        dynamic_preset=dynamic_preset,
        original_settings=original,
    )
    return result


def _merge_allowed(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    if not isinstance(incoming, dict):
        return merged
    for root in _ALLOWED_ROOTS:
        if not isinstance(incoming.get(root), dict):
            continue
        merged.setdefault(root, {})
        allowed = _keys_for_root(root)
        for key, value in incoming[root].items():
            if key in allowed:
                merged[root][key] = value
    return merged


def _merge_runtime_config(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = _merge_allowed(base, incoming)
    agent_in = incoming.get("agent") if isinstance(incoming.get("agent"), dict) else {}
    if agent_in.get("api_key") == "" and agent_in.get("api_key_configured"):
        merged.setdefault("agent", {})
        merged["agent"]["api_key"] = base.get("agent", {}).get("api_key", "")
    return merged


def _provider_agent_plan(
    cfg: dict[str, Any],
    instruction: str,
    current: dict[str, Any],
    selected_image: str,
    model_gallery: list[Any],
    *,
    dynamic_preset: dict[str, Any] | None = None,
    original_settings: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    agent = cfg.get("agent", {})
    provider = str(agent.get("provider") or "custom")
    preset = provider_preset(provider)

    # Embedded llama.cpp provider uses AiBrain directly
    if provider == "embedded":
        from dreamforge_brain import AiBrain, XLC_AVAILABLE
        if not XLC_AVAILABLE:
            return None
        try:
            brain = AiBrain()
            brain.configure("embedded")
            plan = brain.plan_decision(
                user_intent=instruction,
                current_settings=_safe_settings(current),
                selected_image=selected_image,
                gallery=_model_gallery_summary(model_gallery),
            )
        except Exception as exc:
            print(f"[DreamForge Brain Plan Error] {exc}", file=sys.stderr)
            return None
        if not isinstance(plan, dict):
            return None
        patch = plan.get("patch") if isinstance(plan.get("patch"), dict) else {}
        mode = _normalize_mode(str(plan.get("mode") or _mode_for_patch(patch, selected_image)))
        patch = _complete_patch_for_mode(mode, patch, selected_image, model_gallery)
        blueprint = plan.get("workflow_blueprint") if isinstance(plan.get("workflow_blueprint"), dict) else {}
        return _attach_dynamic_preset(
            {
                "ok": True,
                "source": "provider",
                "provider": provider,
                "provider_model": "Embedded Qwen",
                "message": str(plan.get("message") or "Agent planned a DreamForge workflow."),
                "mode": mode,
                "patch": _filter_generation_patch(patch),
                "actions": _string_list(plan.get("actions")),
                "downloads": _string_list(plan.get("downloads")),
                "workflow_plan": plan.get("workflow_plan"),
                "workflow_blueprint": blueprint,
                "readiness": blueprint.get("readiness") if isinstance(blueprint, dict) else None,
                "operations": plan.get("operations"),
            },
            dynamic_preset,
            current,
            original_settings or {},
        )

    # For non-embedded providers, use _post_json directly (testable HTTP path)
    if preset.get("test_kind") not in {"ollama", "openai_compatible"}:
        return None

    base_url = str(agent.get("base_url") or preset.get("base_url") or "").rstrip("/")
    model = str(agent.get("model") or preset.get("default_model") or "").strip()
    api_key = str(agent.get("api_key") or "").strip()
    if not base_url or not model:
        return None
    if preset.get("requires_api_key") and not api_key:
        return None

    system = (
        "You are DreamForge's local creative workflow planner and image-editing router. "
        "Return only JSON with keys: message, mode, patch, actions, downloads. "
        "patch must use DreamForge GenerationSettings keys only. "
        "Choose the workflow, model family, edit_type, control route, and required tools from the user intent. "
        f"{_AGENT_FIELD_GUIDE}"
    )
    if agent.get("custom_instructions"):
        system += "\nUser instructions: " + str(agent.get("custom_instructions"))
    user = {
        "instruction": instruction,
        "current_settings": _safe_settings(current),
        "selected_image": selected_image,
        "available_model_summary": _model_gallery_summary(model_gallery),
        "allowed_modes": ["generate", "edit", "inpaint", "upscale", "agent"],
        "allowed_edit_types": ["auto", "kontext", "inpaint", "img2img", "qwen_edit"],
        "important_patch_keys": [
            "model",
            "prompt",
            "negative_prompt",
            "style",
            "edit_type",
            "edit_strength",
            "input_image",
            "inpaint_mask_path",
            "upscale_image",
            "upscale_method",
            "cn_selection",
            "cn_type",
            "performance",
            "aspect_ratio",
        ],
    }
    try:
        if preset.get("test_kind") == "ollama" and "/v1" not in base_url:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(user)},
                ],
                "stream": False,
                "format": "json",
            }
            raw = _post_json(f"{base_url}/api/chat", payload, None)
            content = ((raw.get("message") or {}).get("content") or "").strip()
        else:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(user)},
                ],
                "temperature": 0.2,
                "max_tokens": 900,
                "response_format": _agent_response_schema(),
            }
            try:
                raw = _post_json(f"{base_url}/chat/completions", payload, api_key or None)
            except Exception:
                payload.pop("response_format", None)
                raw = _post_json(f"{base_url}/chat/completions", payload, api_key or None)
            choices = raw.get("choices") or []
            content = ((choices[0].get("message") or {}).get("content") or "").strip()
        plan = _parse_json_object(content)
    except Exception:
        return None

    if not isinstance(plan, dict):
        return None
    patch = plan.get("patch") if isinstance(plan.get("patch"), dict) else {}
    mode = _normalize_mode(str(plan.get("mode") or _mode_for_patch(patch, selected_image)))
    patch = _complete_patch_for_mode(mode, patch, selected_image, model_gallery)
    blueprint = plan.get("workflow_blueprint") if isinstance(plan.get("workflow_blueprint"), dict) else {}
    return _attach_dynamic_preset(
        {
            "ok": True,
            "source": "provider",
            "provider": provider,
            "provider_model": model,
            "message": str(plan.get("message") or "Agent planned a DreamForge workflow."),
            "mode": mode,
            "patch": _filter_generation_patch(patch),
            "actions": _string_list(plan.get("actions")),
            "downloads": _string_list(plan.get("downloads")),
            "workflow_plan": plan.get("workflow_plan"),
            "workflow_blueprint": blueprint,
            "readiness": blueprint.get("readiness") if isinstance(blueprint, dict) else None,
            "operations": plan.get("operations"),
        },
        dynamic_preset,
        current,
        original_settings or {},
    )


def _heuristic_agent_plan(
    instruction: str,
    current: dict[str, Any],
    selected_image: str,
    model_gallery: list[Any],
    *,
    dynamic_preset: dict[str, Any] | None = None,
    original_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    text = instruction.lower()
    has_text_intent = any(
        word in text
        for word in (
            "text",
            "typography",
            "arabic",
            "عربي",
            "logo",
            "poster",
            "sign",
            "caption",
            "words",
            "letters",
        )
    )
    has_identity_intent = any(
        word in text
        for word in (
            "same face",
            "same character",
            "identity",
            "consistent",
            "consistency",
            "preserve face",
            "keep face",
            "multi-turn",
            "reference",
        )
    )
    has_mask_intent = any(
        word in text
        for word in (
            "inpaint",
            "mask",
            "masked",
            "erase",
            "remove this",
            "fix spot",
            "fill",
            "outpaint",
            "cleanup edge",
        )
    )
    has_upscale_intent = any(
        word in text
        for word in ("upscale", "enlarge", "2x", "4x", "sharpen", "restore", "super resolution")
    )
    patch: dict[str, Any] = {"prompt": instruction}
    actions: list[str] = []
    downloads: list[str] = []

    mode = "generate"
    if has_mask_intent:
        mode = "inpaint"
        patch.update(
            {
                "style": "image_edit",
                "edit_type": "inpaint",
                "cn_selection": "Custom...",
                "cn_type": "inpaint",
            }
        )
        actions.append("Use mask-aware inpainting route with local preservation.")
    elif has_upscale_intent:
        mode = "upscale"
        patch.update(
            {
                "upscale_method": "2x",
                "cn_selection": "Custom...",
                "cn_type": "upscale",
            }
        )
        actions.append("Use upscale route (2x).")
    elif selected_image or any(
        word in text
        for word in (
            "edit",
            "replace",
            "change",
            "keep same",
            "same face",
            "preserve",
            "reference",
            "typography",
            "text",
        )
    ):
        mode = "edit"
        edit_type = "qwen_edit" if has_text_intent else "kontext"
        if edit_type == "kontext":
            patch.update(
                {
                    "style": "image_edit",
                    "edit_type": "kontext",
                    "cn_selection": "None",
                    "cn_type": "None",
                }
            )
            actions.append("Use FLUX Kontext for identity/reference continuity and global edits.")
        else:
            patch.update(
                {
                    "style": "image_edit",
                    "edit_type": "qwen_edit",
                    "cn_selection": "Custom...",
                    "cn_type": "qwen_edit",
                    "steps": 50,
                    "cfg_scale": 4.0,
                }
            )
            actions.append("Use Qwen Image Edit for text-aware semantic and appearance editing.")

    if selected_image and mode in {"edit", "inpaint", "upscale"}:
        if mode == "upscale":
            patch["upscale_image"] = selected_image
        else:
            patch["input_image"] = selected_image
    elif mode in {"edit", "inpaint", "upscale"}:
        actions.append("Attach or select an input image before running.")

    if "arabic" in text or "عربي" in instruction or "خط" in instruction:
        patch["style"] = "arabic_poster" if mode == "generate" else "image_edit"
        patch["negative_prompt"] = "fake Arabic, broken glyphs, unreadable text, random letters"
        actions.append("Use deterministic Arabic text/reference rendering before diffusion when text must be exact.")

    if "poster" in text:
        patch.setdefault("aspect_ratio", "896x1344")
        patch.setdefault("style", "arabic_poster" if "arabic" in text else "book_cover")
    if any(word in text for word in ("product", "ad", "advertising")):
        patch.setdefault("style", "product_ad")
        patch.setdefault("aspect_ratio", "1152x896")
    if any(word in text for word in ("cinematic", "movie", "film")):
        patch.setdefault("style", "cinematic_scene")
        patch.setdefault("performance", "Quality")

    model = _pick_model_for_mode(mode, model_gallery, edit_type=str(patch.get("edit_type") or ""))
    if model:
        patch["model"] = model
        downloads.append(f"Check companion files for {Path(model).name}.")

    workflow_plan = None
    workflow_blueprint = None
    readiness = None
    operations = None
    try:
        from dreamforge_brain import heuristic_brain_decision

        decision = heuristic_brain_decision(instruction, current, selected_image, [])
        if isinstance(decision, dict):
            workflow_plan = decision.get("workflow_plan")
            workflow_blueprint = decision.get("workflow_blueprint")
            operations = decision.get("operations")
            if isinstance(workflow_blueprint, dict):
                readiness = workflow_blueprint.get("readiness")
            brain_patch = _filter_generation_patch(
                decision.get("patch") if isinstance(decision.get("patch"), dict) else {}
            )
            for key, value in brain_patch.items():
                patch.setdefault(key, value)
    except Exception:
        pass

    return _attach_dynamic_preset(
        {
            "ok": True,
            "source": "local",
            "provider": "",
            "provider_model": "",
            "message": f"Prepared an {mode} workflow from the instruction." if mode in {"edit", "inpaint", "upscale"} else "Prepared a generate workflow from the instruction.",
            "mode": mode,
            "patch": _filter_generation_patch(patch),
            "actions": actions,
            "downloads": downloads,
            "workflow_plan": workflow_plan,
            "workflow_blueprint": workflow_blueprint,
            "readiness": readiness,
            "operations": operations,
        },
        dynamic_preset,
        current,
        original_settings or {},
    )


_GENERATION_PATCH_KEYS = {
    "model",
    "prompt",
    "negative_prompt",
    "aspect_ratio",
    "seed",
    "steps",
    "cfg_scale",
    "sampler",
    "scheduler",
    "styles",
    "lora",
    "vram_profile",
    "style",
    "performance",
    "image_number",
    "cn_selection",
    "cn_type",
    "upscale_image",
    "upscale_method",
    "edit_type",
    "edit_strength",
    "input_image",
    "inpaint_mask_path",
    "lora_keywords",
    "clip_skip",
    "auto_negative_prompt",
    "subject",
    "composition",
    "lighting",
    "camera",
    "brand_colors",
    "workflow_mode",
    "arabic_text",
    "execute_workflow_plan",
    "workflow_plan",
    "detail_target",
    "detail_prompt",
    "reference_image",
    "control_image",
}


def _filter_generation_patch(patch: dict[str, Any]) -> dict[str, Any]:
    filtered = {k: v for k, v in patch.items() if k in _GENERATION_PATCH_KEYS}
    aspect = filtered.get("aspect_ratio")
    if aspect is not None and not re.match(r"^\d{2,5}x\d{2,5}$", str(aspect)):
        filtered.pop("aspect_ratio", None)
    edit_type = filtered.get("edit_type")
    if edit_type is not None and edit_type not in {
        "auto",
        "kontext",
        "inpaint",
        "img2img",
        "qwen_edit",
    }:
        filtered.pop("edit_type", None)
    cn_selection = filtered.get("cn_selection")
    if cn_selection is not None and cn_selection not in {"None", "Custom..."}:
        filtered.pop("cn_selection", None)
    cn_type = filtered.get("cn_type")
    if cn_type is not None and cn_type not in {
        "None",
        "img2img",
        "inpaint",
        "upscale",
        "qwen_edit",
        "canny",
        "cpds",
        "depth",
        "pose",
    }:
        filtered.pop("cn_type", None)
    performance = filtered.get("performance")
    if performance is not None and performance not in {"Speed", "Quality", "Extreme Speed", "Custom..."}:
        value = str(performance).strip().lower()
        if value in {"high", "best", "hq", "slow"}:
            filtered["performance"] = "Quality"
        elif value in {"fast", "quick", "low"}:
            filtered["performance"] = "Speed"
        else:
            filtered.pop("performance", None)
    style = filtered.get("style")
    if style is not None and style not in {"none", *STYLE_RECIPES.keys()}:
        filtered["style"] = "image_edit" if filtered.get("input_image") else "none"
    return filtered


def _attach_dynamic_preset(
    payload: dict[str, Any],
    dynamic_preset: dict[str, Any] | None,
    enriched: dict[str, Any],
    original: dict[str, Any],
) -> dict[str, Any]:
    if not dynamic_preset:
        return payload
    payload["dynamic_preset"] = dynamic_preset
    patch = payload.get("patch")
    if not isinstance(patch, dict):
        return payload
    applied = dynamic_preset.get("applied") if isinstance(dynamic_preset.get("applied"), dict) else {}
    for key in applied:
        if key in _GENERATION_PATCH_KEYS and key not in original:
            value = enriched.get(key)
            if value is not None:
                patch[key] = value
    payload["patch"] = _filter_generation_patch(patch)
    return payload


def _safe_settings(settings: dict[str, Any]) -> dict[str, Any]:
    return _filter_generation_patch(settings)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None][:12]


def _mode_for_patch(patch: dict[str, Any], selected_image: str) -> str:
    if patch.get("upscale_image"):
        return "upscale"
    if patch.get("edit_type") == "inpaint" or patch.get("inpaint_mask_path"):
        return "inpaint"
    if patch.get("input_image") or selected_image:
        return "edit"
    return "generate"


def _normalize_mode(mode: str) -> str:
    value = mode.strip().lower().replace("-", "_")
    if value in {"image_edit", "img2img", "reference_edit", "text_edit"}:
        return "edit"
    if value in {"mask", "masked_edit"}:
        return "inpaint"
    if value in {"enlarge", "enhance"}:
        return "upscale"
    if value in {"generate", "edit", "inpaint", "upscale", "agent"}:
        return value
    return "generate"


def _complete_patch_for_mode(
    mode: str,
    patch: dict[str, Any],
    selected_image: str,
    model_gallery: list[Any],
) -> dict[str, Any]:
    next_patch = dict(patch)
    if mode == "edit":
        next_patch.setdefault("style", "image_edit")
        next_patch.setdefault("edit_type", "kontext")
        if next_patch.get("edit_type") == "kontext":
            next_patch["cn_selection"] = "None"
            next_patch["cn_type"] = "None"
        else:
            next_patch["cn_selection"] = "Custom..."
            next_patch["cn_type"] = (
                "qwen_edit" if next_patch.get("edit_type") == "qwen_edit" else "img2img"
            )
            if next_patch.get("edit_type") == "qwen_edit":
                next_patch.setdefault("steps", 50)
                next_patch.setdefault("cfg_scale", 4.0)
        if selected_image:
            next_patch.setdefault("input_image", selected_image)
    elif mode == "inpaint":
        next_patch.setdefault("style", "image_edit")
        next_patch["edit_type"] = "inpaint"
        next_patch["cn_selection"] = "Custom..."
        next_patch["cn_type"] = "inpaint"
        if selected_image:
            next_patch.setdefault("input_image", selected_image)
    elif mode == "upscale":
        next_patch.setdefault("upscale_method", "2x")
        next_patch["cn_selection"] = "Custom..."
        next_patch["cn_type"] = "upscale"
        if selected_image:
            next_patch.setdefault("upscale_image", selected_image)

    if mode in {"generate", "edit", "inpaint", "upscale"} and not next_patch.get("model"):
        model = _pick_model_for_mode(
            mode,
            model_gallery,
            edit_type=str(next_patch.get("edit_type") or ""),
        )
        if model:
            next_patch["model"] = model
    return next_patch


def _pick_model_for_mode(mode: str, gallery: list[Any], *, edit_type: str = "") -> str:
    if mode == "edit" and edit_type == "qwen_edit":
        needles = ["qwen image edit", "qwen_image_edit", "qwen-edit", "qwen edit", "qwen"]
    elif mode == "edit" and edit_type == "kontext":
        needles = ["kontext", "flux kontext"]
    else:
        needles = {
            "inpaint": ["flux fill", "fill", "inpaint"],
            "edit": ["kontext", "flux kontext", "qwen image edit", "qwen_image_edit", "qwen edit"],
            "upscale": ["upscale", "supir", "esrgan", "real-esrgan"],
            "generate": ["juggernaut", "realvis", "flux1-schnell", "sdxl"],
        }.get(mode, [])
    for needle in needles:
        for item in gallery:
            if not isinstance(item, dict):
                continue
            hay = " ".join(str(item.get(k, "")) for k in ("family", "caption", "engine_name", "relative_path")).lower()
            if needle in hay:
                return str(item.get("engine_name") or item.get("relative_path") or "")
    return ""


def _model_gallery_summary(gallery: list[Any]) -> list[dict[str, str]]:
    """Compact installed-model context for small local LLMs."""
    priorities = [
        "qwen",
        "kontext",
        "fill",
        "inpaint",
        "flux",
        "upscale",
        "supir",
        "esrgan",
        "real-esrgan",
        "sdxl",
    ]
    summary: list[dict[str, str]] = []
    seen: set[str] = set()
    for needle in priorities:
        for item in gallery:
            if not isinstance(item, dict):
                continue
            hay = " ".join(
                str(item.get(k, ""))
                for k in ("family", "caption", "engine_name", "relative_path", "category")
            ).lower()
            if needle not in hay:
                continue
            engine = str(item.get("engine_name") or item.get("relative_path") or "").strip()
            if not engine or engine in seen:
                continue
            seen.add(engine)
            summary.append(
                {
                    "engine_name": engine,
                    "family": str(item.get("family") or ""),
                    "caption": str(item.get("caption") or "")[:120],
                }
            )
            if len(summary) >= 24:
                return summary
    return summary


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("agent response was not a JSON object")
    return parsed


def _agent_response_schema() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "dreamforge_agent_plan",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "message": {"type": "string"},
                    "mode": {
                        "type": "string",
                        "enum": ["generate", "edit", "inpaint", "upscale", "agent", "image_edit"],
                    },
                    "patch": {"type": "object"},
                    "actions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "downloads": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["message", "mode", "patch", "actions", "downloads"],
            },
        },
    }


def _keys_for_root(root: str) -> set[str]:
    if root == "agent":
        return _AGENT_KEYS
    if root == "privacy":
        return _PRIVACY_KEYS
    if root == "ui":
        return _UI_KEYS
    return set()


def _post_json(url: str, payload: dict[str, Any], api_key: str | None) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    return json.loads(text) if text else {}


def _test_result(
    ok: bool,
    provider: str,
    model: str,
    start: float,
    detail: str,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "provider": provider,
        "model": model,
        "latency_ms": int((time.perf_counter() - start) * 1000),
        "detail": detail,
    }


def _redact(text: str, secret: str) -> str:
    if not secret:
        return text[:500]
    return text.replace(secret, "[redacted]")[:500]
