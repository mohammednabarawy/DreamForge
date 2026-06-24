"""Daemon-owned DreamForge app config and agent provider checks."""

from __future__ import annotations

import copy
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
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
        "id": "llamacpp",
        "label": "llama.cpp server",
        "mode": "local",
        "base_url": "http://localhost:8080/v1",
        "default_model": "local-model",
        "requires_api_key": False,
        "test_kind": "openai_compatible",
    },
]

LOCAL_AGENT_PROVIDER_IDS = {preset["id"] for preset in PROVIDER_PRESETS}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

DEFAULT_APP_CONFIG: dict[str, Any] = {
    "agent": {
        "provider": "ollama",
        "base_url": "http://localhost:11434",
        "model": "gemma3:4b",
        "custom_instructions": "",
        "approval_required": True,
        "auto_configure_workflows": True,
    },
    "ui": {
        "studio_mode": "generate",
        "experience": "simple",
        "advanced_mode": False,
        "auto_enhance_on_generate": False,
        "enhance_strength": "balanced",
        "use_flufferizer": True,
        "civitai_api_key": "",
    },
}

_ALLOWED_ROOTS = {"agent", "privacy", "ui"}
_AGENT_KEYS = {
    "provider",
    "base_url",
    "model",
    "custom_instructions",
    "approval_required",
    "auto_configure_workflows",
}
_PRIVACY_KEYS: set[str] = set()
_UI_KEYS = {
    "studio_mode",
    "experience",
    "advanced_mode",
    "auto_enhance_on_generate",
    "enhance_strength",
    "use_flufferizer",
    "civitai_api_key",
}
_EXPERIENCE_VALUES = {"simple", "pro"}

_AGENT_FIELD_GUIDE = """
DreamForge routing field guide:
- generate: use for text-to-image when there is no source image to preserve. Let the user pick any library model in Generate mode.
- edit: use for source-image edits without a required mask. Default to Qwen Image Edit 2511 Lightning (edit_type=qwen_edit, performance=Lightning, steps=8, cfg_scale=1.0, sampler=euler, scheduler=simple, cn_selection=Custom..., cn_type=qwen_edit) for semantic edits, typography, posters, Arabic/bilingual text, object swaps, and appearance changes. Fall back to FLUX Kontext (edit_type=kontext) only when no Qwen Image Edit model is installed. See docs/AGENT_DIFFUSION_GUIDE.md for model families and configs.
- inpaint: use only when a local region/mask is required or the user says mask, erase, remove this area, fix spot, fill, outpaint, cleanup edge, or background/object replacement with strict local preservation. Prefer FLUX Fill/inpaint models and require input_image plus inpaint_mask_path before running.
- upscale: use only for enlargement/restoration/detail enhancement of an existing image. Prefer RealESRGAN_x2 for fast 2x, SUPIR when available for high-realism repair, and do not use text-to-image generation for pure upscale.
- agent: use only when a required decision is impossible from the instruction, such as missing source image for an edit or missing mask for inpaint.

Conditioning and quality rules:
- For exact Arabic or brand typography, do not ask diffusion to invent glyphs from scratch. Route to Qwen Image Edit and ask for deterministic rendered text/reference integration when possible. Preserve glyph geometry, layout, and surrounding pixels.
- Qwen Image Edit 2511 Lightning is the default edit route on 16 GB GPUs. Prefer performance=Lightning, steps=8, cfg_scale=1.0, sampler=euler, scheduler=simple unless the user explicitly requests Quality or the faster Speed/LCM route.
- Qwen Image Edit is strong for both semantic and appearance editing: it can change objects/text while preserving unchanged regions. Use explicit preservation wording in the prompt.
- For face/character preservation with Qwen, keep input_image from selected_image and name what must stay unchanged in the prompt. Use FLUX Kontext (edit_type=kontext) when the user explicitly asks for Kontext or only Kontext models are installed.
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
    return provider_preset("ollama")


def load_app_config(*, redacted: bool = True) -> dict[str, Any]:
    cfg = copy.deepcopy(DEFAULT_APP_CONFIG)
    path = config_path()
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            cfg = _merge_allowed(cfg, raw)
            raw_ui = raw.get("ui") if isinstance(raw.get("ui"), dict) else {}
            if "experience" not in raw_ui:
                cfg.setdefault("ui", {})["experience"] = "pro"
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    cfg = _normalize_ui_config(cfg)
    cfg = _normalize_agent_config(cfg)
    return redact_config(cfg) if redacted else cfg


def save_app_config(incoming: dict[str, Any]) -> dict[str, Any]:
    existing = load_app_config(redacted=False)
    next_cfg = _normalize_ui_config(
        _normalize_agent_config(_merge_allowed(existing, incoming))
    )
    ui_in = incoming.get("ui") if isinstance(incoming.get("ui"), dict) else {}
    if "civitai_api_key" in ui_in and not str(ui_in.get("civitai_api_key") or "").strip():
        preserved = str(existing.get("ui", {}).get("civitai_api_key") or "").strip()
        if preserved:
            next_cfg.setdefault("ui", {})["civitai_api_key"] = preserved

    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(next_cfg, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return redact_config(next_cfg)


def redact_config(cfg: dict[str, Any]) -> dict[str, Any]:
    redacted = copy.deepcopy(cfg)
    redacted.setdefault("agent", {})
    redacted["agent"]["api_key"] = ""
    redacted["agent"]["api_key_configured"] = False
    redacted["agent"]["api_key_tail"] = ""
    ui = redacted.setdefault("ui", {})
    civitai_key = str(ui.get("civitai_api_key") or "")
    if civitai_key:
        ui["civitai_api_key_configured"] = True
        ui["civitai_api_key_tail"] = civitai_key[-4:] if len(civitai_key) >= 4 else civitai_key
    else:
        ui["civitai_api_key_configured"] = False
        ui["civitai_api_key_tail"] = ""
    ui["civitai_api_key"] = ""
    return redacted


def test_agent_provider(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = _merge_runtime_config(load_app_config(redacted=False), config or {})
    agent = cfg.get("agent", {})
    provider = str(agent.get("provider") or DEFAULT_APP_CONFIG["agent"]["provider"])
    preset = provider_preset(provider)
    base_url = str(agent.get("base_url") or preset.get("base_url") or "").rstrip("/")
    model = str(agent.get("model") or preset.get("default_model") or "").strip()
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

    if not base_url:
        return _test_result(False, provider, model, start, "base_url_missing")
    if not _is_local_base_url(base_url):
        return _test_result(False, provider, model, start, "local_endpoint_required")
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
            _post_json(f"{base_url}/chat/completions", payload, None)
    except Exception as exc:  # noqa: BLE001 - bridge must return structured failures
        return _test_result(False, provider, model, start, _redact(str(exc), ""))

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


def _normalize_ui_config(cfg: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(cfg)
    ui = normalized.setdefault("ui", {})
    experience = str(ui.get("experience") or "simple").strip().lower()
    if experience not in _EXPERIENCE_VALUES:
        experience = "simple"
    ui["experience"] = experience
    strength = str(ui.get("enhance_strength") or "balanced").strip().lower()
    if strength not in {"minimal", "balanced", "rich"}:
        strength = "balanced"
    ui["enhance_strength"] = strength
    if ui.get("use_flufferizer") is None:
        ui["use_flufferizer"] = True
    else:
        ui["use_flufferizer"] = bool(ui.get("use_flufferizer"))
    if ui.get("auto_enhance_on_generate") is None:
        ui["auto_enhance_on_generate"] = False
    else:
        ui["auto_enhance_on_generate"] = bool(ui.get("auto_enhance_on_generate"))
    if experience == "simple" and str(ui.get("studio_mode") or "") == "agent":
        ui["studio_mode"] = "generate"
    return normalized


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
    return _normalize_agent_config(_merge_allowed(base, incoming), coerce_remote_base_url=False)


def _normalize_agent_config(cfg: dict[str, Any], *, coerce_remote_base_url: bool = True) -> dict[str, Any]:
    normalized = copy.deepcopy(cfg)
    agent = normalized.setdefault("agent", {})
    provider = str(agent.get("provider") or DEFAULT_APP_CONFIG["agent"]["provider"])
    reset_model = False
    if provider not in LOCAL_AGENT_PROVIDER_IDS:
        provider = DEFAULT_APP_CONFIG["agent"]["provider"]
        agent["provider"] = provider
        reset_model = True
    preset = provider_preset(provider)
    base_url = str(agent.get("base_url") or preset.get("base_url") or "").strip()
    if coerce_remote_base_url and provider != "embedded" and base_url and not _is_local_base_url(base_url):
        base_url = str(preset.get("base_url") or "")
    agent["base_url"] = base_url
    agent["model"] = str((None if reset_model else agent.get("model")) or preset.get("default_model") or "")
    agent.pop("api_key", None)
    agent.pop("clear_api_key", None)
    normalized["privacy"] = {}
    return normalized


def _is_local_base_url(base_url: str) -> bool:
    if not base_url:
        return False
    parsed = urllib.parse.urlparse(base_url)
    host = (parsed.hostname or "").lower()
    return host in LOCAL_HOSTS


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
    provider = str(agent.get("provider") or DEFAULT_APP_CONFIG["agent"]["provider"])
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
    if not base_url or not model:
        return None
    if not _is_local_base_url(base_url):
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
                raw = _post_json(f"{base_url}/chat/completions", payload, None)
            except Exception:
                payload.pop("response_format", None)
                raw = _post_json(f"{base_url}/chat/completions", payload, None)
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
                "upscale_method": "ultimate_sd_upscale",
                "cn_selection": "Custom...",
                "cn_type": "upscale",
            }
        )
        actions.append("Use Ultimate SD Upscale route.")
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
        if _gallery_has_qwen_edit(model_gallery):
            patch.update(_qwen_edit_lightning_patch())
            actions.append(
                "Use Qwen Image Edit 2511 Lightning for semantic and appearance editing."
            )
        else:
            patch.update(
                {
                    "style": "image_edit",
                    "edit_type": "kontext",
                    "cn_selection": "None",
                    "cn_type": "None",
                }
            )
            actions.append("Use FLUX Kontext for identity/reference continuity and global edits.")

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
        patch.setdefault("aspect_ratio", "704x1056")
        patch.setdefault("style", "arabic_poster" if "arabic" in text else "book_cover")
    if any(word in text for word in ("product", "ad", "advertising")):
        patch.setdefault("style", "product_ad")
        patch.setdefault("aspect_ratio", "896x704")
    if any(word in text for word in ("cinematic", "movie", "film")):
        patch.setdefault("style", "cinematic_scene")
        if mode == "generate":
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

        decision = heuristic_brain_decision(
            instruction,
            {**current, **{k: v for k, v in patch.items() if v is not None}},
            selected_image,
            model_gallery,
        )
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
    "enhance_auto_fix",
    "enhance_target",
    "enhance_detection_prompt",
    "enhance_post_upscale",
    "reference_image",
    "reference_images",
    "references",
    "reference_role",
    "reference_weight",
    "cn_strength",
    "cn_stop",
    "structure_type",
    "identity_mode",
    "face_preservation",
    "control_image",
    "qwen_scale_megapixels",
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
    if performance is not None and performance not in {"Speed", "Quality", "Extreme Speed", "Lightning", "Lcm", "Custom..."}:
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
    from dreamforge_mode_contract import build_mode_contract

    if not dynamic_preset:
        payload["mode_contract"] = build_mode_contract(
            str(payload.get("mode") or "generate"),
            payload.get("patch") if isinstance(payload.get("patch"), dict) else {},
            original,
            source=str(payload.get("source") or "local"),
        )
        return payload
    payload["dynamic_preset"] = dynamic_preset
    patch = payload.get("patch")
    if not isinstance(patch, dict):
        payload["mode_contract"] = build_mode_contract(
            str(payload.get("mode") or "generate"),
            {},
            original,
            source=str(payload.get("source") or "local"),
        )
        return payload
    applied = dynamic_preset.get("applied") if isinstance(dynamic_preset.get("applied"), dict) else {}
    for key in applied:
        if key in _GENERATION_PATCH_KEYS and key not in original:
            value = enriched.get(key)
            if value is not None:
                patch[key] = value
    _force_qwen_lightning_defaults(patch)
    payload["patch"] = _filter_generation_patch(patch)
    payload["mode_contract"] = build_mode_contract(
        str(payload.get("mode") or "generate"),
        payload["patch"],
        original,
        source=str(payload.get("source") or "local"),
    )
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


def _gallery_has_qwen_edit(gallery: list[Any]) -> bool:
    for item in gallery:
        if not isinstance(item, dict):
            continue
        if str(item.get("family") or "").lower() == "qwen_image_edit":
            return True
        hay = " ".join(
            str(item.get(key, "")) for key in ("family", "caption", "engine_name", "relative_path")
        ).lower()
        if "qwen" in hay and "edit" in hay:
            return True
    return False


def _qwen_edit_lightning_patch() -> dict[str, Any]:
    return {
        "style": "image_edit",
        "edit_type": "qwen_edit",
        "cn_selection": "Custom...",
        "cn_type": "qwen_edit",
        "performance": "Lightning",
        "steps": 8,
        "cfg_scale": 1.0,
        "sampler": "euler",
        "scheduler": "simple",
        "qwen_scale_megapixels": 1.25,
        "edit_strength": 1.0,
        "qwen_lightning_strength": 0.75,
    }


def _complete_patch_for_mode(
    mode: str,
    patch: dict[str, Any],
    selected_image: str,
    model_gallery: list[Any],
) -> dict[str, Any]:
    next_patch = dict(patch)
    if mode == "edit":
        next_patch.setdefault("style", "image_edit")
        edit_type = str(next_patch.get("edit_type") or "").lower()
        if not edit_type or edit_type == "auto":
            if _gallery_has_qwen_edit(model_gallery):
                next_patch.update(_qwen_edit_lightning_patch())
                edit_type = "qwen_edit"
            else:
                edit_type = "kontext"
                next_patch["edit_type"] = edit_type
        if edit_type == "qwen_edit":
            next_patch["edit_type"] = "qwen_edit"
            next_patch["cn_selection"] = "Custom..."
            next_patch["cn_type"] = "qwen_edit"
            _force_qwen_lightning_defaults(next_patch)
        elif edit_type == "kontext":
            next_patch["edit_type"] = "kontext"
            next_patch["cn_selection"] = "None"
            next_patch["cn_type"] = "None"
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
        next_patch.setdefault("upscale_method", "ultimate_sd_upscale")
        next_patch["cn_selection"] = "Custom..."
        next_patch["cn_type"] = "upscale"
        if selected_image:
            next_patch.setdefault("upscale_image", selected_image)
        preserve_model = bool(
            next_patch.get("user_picked_model") and next_patch.get("advanced_mode")
        )
        if not preserve_model:
            from dreamforge_upscale_routing import pick_best_sdxl_upscale_checkpoint

            sdxl_model = pick_best_sdxl_upscale_checkpoint(model_gallery)
            if sdxl_model:
                next_patch["model"] = sdxl_model

    if mode in {"generate", "edit", "inpaint", "upscale"} and not next_patch.get("model"):
        model = _pick_model_for_mode(
            mode,
            model_gallery,
            edit_type=str(next_patch.get("edit_type") or ""),
        )
        if model:
            next_patch["model"] = model
    return next_patch


def _force_qwen_lightning_defaults(patch: dict[str, Any]) -> None:
    """Apply Lightning defaults for Qwen edit when speed/Lightning is requested."""
    if patch.get("edit_type") != "qwen_edit":
        return
    perf = str(patch.get("performance") or "").strip().lower()
    if perf not in {"", "lightning", "speed", "lcm"}:
        return
    patch["performance"] = "Lightning"
    patch.setdefault("steps", 8)
    patch.setdefault("cfg_scale", 1.0)
    patch.setdefault("sampler", "euler")
    patch.setdefault("scheduler", "simple")
    patch.setdefault("qwen_scale_megapixels", 1.25)
    patch.setdefault("qwen_lightning_strength", 0.75)


def _pick_model_for_mode(mode: str, gallery: list[Any], *, edit_type: str = "") -> str:
    from dreamforge_cli_inventory import pick_best_qwen_edit_model

    if mode == "edit" and edit_type in ("qwen_edit", ""):
        picked = pick_best_qwen_edit_model(gallery)
        if picked:
            return picked
    if mode == "edit" and edit_type == "qwen_edit":
        needles = [
            "qwen-image-edit-2511-q4_k_m",
            "qwen image edit 2511",
            "qwen-image-edit-2511",
            "qwen image edit",
            "qwen_image_edit",
            "qwen-edit",
            "qwen edit",
            "qwen",
        ]
    elif mode == "edit" and edit_type == "kontext":
        needles = ["kontext", "flux kontext"]
    else:
        needles = {
            "inpaint": ["flux fill", "fill", "inpaint"],
            "edit": [
                "qwen-image-edit-2511-q4_k_m",
                "qwen image edit 2511",
                "qwen-image-edit-2511",
                "qwen image edit",
                "qwen_image_edit",
                "qwen edit",
                "kontext",
                "flux kontext",
            ],
            "upscale": [
                "epicrealism",
                "juggernaut",
                "realvis",
                "dreamshaper",
                "sd_xl",
                "sdxl",
            ],
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
