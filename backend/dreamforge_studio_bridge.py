"""Studio-specific bridge commands for the Tauri desktop shell."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from _paths import BACKEND_ROOT, PROJECT_ROOT


def _error(message: str, **extra) -> dict:
    return {"ok": False, "error": message, **extra}


def _load_keywords(lora_name: str) -> str:
    from modules.util import load_keywords

    return (load_keywords(lora_name) or "").strip()


def _lora_default_weight(lora_name: str) -> float:
    from shared import path_manager

    cache_json = (
        Path(path_manager.model_paths["cache_path"]) / "loras" / Path(lora_name).name
    ).with_suffix(".json")
    if cache_json.is_file():
        try:
            data = json.loads(cache_json.read_text(encoding="utf-8"))
            for key in ("preferred weight", "preferred_weight", "weight"):
                if key in data and data[key] is not None:
                    return float(data[key])
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    return 1.0


def cmd_get_lora_info(params: dict) -> dict:
    name = (params.get("name") or params.get("relative_path") or "").strip()
    if not name:
        return _error("name required")
    keywords = _load_keywords(name)
    return {
        "ok": True,
        "name": name,
        "keywords": keywords,
        "default_weight": _lora_default_weight(name),
    }


def cmd_aggregate_lora_keywords(params: dict) -> dict:
    tokens = params.get("lora") or []
    parts: list[str] = []
    for token in tokens:
        if not isinstance(token, str):
            continue
        name = token.split(":", 1)[0].strip()
        if not name:
            continue
        kw = _load_keywords(name)
        if kw and kw not in parts:
            parts.append(kw)
    return {"ok": True, "keywords": ", ".join(parts)}


def cmd_apply_styles_to_prompt(params: dict) -> dict:
    from modules.sdxl_styles import apply_style

    styles = params.get("styles") or []
    prompt = params.get("prompt") or ""
    negative = params.get("negative_prompt") or ""
    lora_keywords = params.get("lora_keywords") or ""
    p, n = apply_style(styles, prompt, negative, lora_keywords)
    return {
        "ok": True,
        "prompt": p,
        "negative_prompt": n,
        "styles": [],
    }


def cmd_list_wildcards(_params: dict) -> dict:
    from modules.util import get_wildcard_files

    return {"ok": True, "wildcards": get_wildcard_files()}


def cmd_match_wildcards(params: dict) -> dict:
    from modules.util import get_wildcard_files

    files = get_wildcard_files()
    text = params.get("text") or ""
    marker = None
    if "__" in text:
        last = text.rfind("__")
        if last >= 0:
            fragment = text[last + 2 :]
            if fragment and not fragment.endswith("__"):
                marker = fragment.lower()
    if not marker:
        return {"ok": True, "matches": []}
    matches = [w for w in files if marker in w.lower()]
    return {"ok": True, "matches": matches[:40]}


def cmd_get_studio_settings(_params: dict) -> dict:
    from shared import path_manager, settings

    s = settings.default_settings
    return {
        "ok": True,
        "settings": {
            "path_checkpoints": "\n".join(path_manager.paths.get("path_checkpoints", [])),
            "path_loras": "\n".join(path_manager.paths.get("path_loras", [])),
            "path_outputs": path_manager.paths.get("path_outputs", ""),
            "path_inbox": path_manager.paths.get("path_inbox", ""),
            "archive_folders": "\n".join(s.get("archive_folders", [])),
            "images_per_page": int(s.get("images_per_page", 100)),
            "image_number_max": int(s.get("image_number_max", 50)),
            "auto_negative_prompt": bool(s.get("auto_negative_prompt", False)),
            "clip_skip": int(s.get("clip_skip", 1)),
            "seed_random": bool(s.get("seed_random", True)),
            "lora_min": float(s.get("lora_min", 0)),
            "lora_max": float(s.get("lora_max", 2)),
        },
    }


def cmd_save_studio_settings(params: dict) -> dict:
    from shared import path_manager, settings

    incoming = params.get("settings") or {}
    s = settings.default_settings

    for key in (
        "archive_folders",
        "path_checkpoints",
        "path_loras",
        "images_per_page",
        "image_number_max",
        "auto_negative_prompt",
        "clip_skip",
        "seed_random",
        "lora_min",
        "lora_max",
    ):
        if key in incoming:
            s[key] = incoming[key]

    for key in ("archive_folders", "path_checkpoints", "path_loras"):
        if key in s and isinstance(s[key], str):
            s[key] = [line.strip() for line in s[key].splitlines() if line.strip()]

    if "path_outputs" in incoming:
        path_manager.paths["path_outputs"] = incoming["path_outputs"]
    if "path_inbox" in incoming:
        path_manager.paths["path_inbox"] = incoming["path_inbox"]
    if "path_checkpoints" in s:
        path_manager.paths["path_checkpoints"] = s["path_checkpoints"]
    if "path_loras" in s:
        path_manager.paths["path_loras"] = s["path_loras"]

    settings.save_settings()
    path_manager.save_paths()
    return {"ok": True}


def cmd_get_app_config(_params: dict) -> dict:
    from dreamforge_app_config import load_app_config

    return {"ok": True, "config": load_app_config(redacted=True)}


def cmd_save_app_config(params: dict) -> dict:
    from dreamforge_app_config import save_app_config

    config = params.get("config") or {}
    return {"ok": True, "config": save_app_config(config)}


def cmd_list_agent_providers(_params: dict) -> dict:
    from dreamforge_app_config import list_agent_providers

    return {"ok": True, "providers": list_agent_providers()}


def cmd_test_agent_provider(params: dict) -> dict:
    from dreamforge_app_config import test_agent_provider

    config = params.get("config")
    return test_agent_provider(config if isinstance(config, dict) else None)


def cmd_agent_plan(params: dict) -> dict:
    from dreamforge_app_config import plan_agent_instruction

    return plan_agent_instruction(params)


def _image_browser():
    from modules.imagebrowser import ImageBrowser

    return ImageBrowser()


def cmd_browse_images(params: dict) -> dict:
    browser = _image_browser()
    page = int(params.get("page") or 1)
    search = (params.get("search") or "").strip()
    if search:
        browser.filter = search
    paths, range_text = browser.load_images(page)
    count, pages = browser.num_images_pages()
    return {
        "ok": True,
        "items": [str(p) for p in paths],
        "page": page,
        "pages": pages,
        "total": count,
        "range_text": range_text,
    }


def cmd_image_browser_metadata(params: dict) -> dict:
    path = (params.get("path") or "").strip()
    if not path:
        return _error("path required")
    from modules.imagebrowser import format_metadata_string, get_png_metadata

    meta = get_png_metadata(path)
    meta["file_path"] = path
    return {"ok": True, "metadata": meta, "text": format_metadata_string(meta)}


def cmd_image_browser_reindex(_params: dict) -> dict:
    browser = _image_browser()
    browser.update_images()
    paths, _ = browser.load_images(1)
    count, pages = browser.num_images_pages()
    return {
        "ok": True,
        "items": [str(p) for p in paths],
        "pages": pages,
        "message": f"Indexed {count} images",
    }


def cmd_random_onebutton_prompt(params: dict) -> dict:
    try:
        from random_prompt.build_dynamic_prompt import build_dynamic_prompt
    except ImportError as exc:
        return _error(f"onebutton_unavailable: {exc}")

    insanity = int(params.get("insanitylevel") or 5)
    prompt = build_dynamic_prompt(insanitylevel=insanity)
    return {"ok": True, "prompt": prompt}


def _evolve_tokenize(prompt: str, strength: float) -> str:
    from shared import tokenizer

    if tokenizer is None:
        return prompt
    all_tokens = list(tokenizer.get_vocab().keys())
    tokens = tokenizer.tokenize(prompt)
    res = []
    chance = float(strength) / 100.0
    for token in tokens:
        if random.random() < chance:
            res.append(all_tokens[random.randint(0, max(len(all_tokens) - 3, 0))])
        else:
            res.append(token)
    return tokenizer.convert_tokens_to_string(res).strip()


def _evolve_words(prompt: str, strength: float) -> str:
    import re

    words_path = BACKEND_ROOT / "wildcards_official" / "words.txt"
    if not words_path.is_file():
        return prompt
    word_list = words_path.read_text(encoding="utf-8").lower().splitlines()
    chance = float(strength) / 100.0
    parts = re.split(r"\b", prompt)
    out = []
    for word in parts:
        if (
            word
            and not word.isdigit()
            and word.lower() in word_list
            and random.random() < chance
        ):
            out.append(word_list[random.randint(0, len(word_list) - 1)])
        else:
            out.append(word)
    return "".join(out).strip()


def cmd_enhance_studio_prompt(params: dict) -> dict:
    from dreamforge_prompt.studio_enhance import enhance_studio_prompt

    return enhance_studio_prompt(params)


def cmd_validate_ideogram4_caption(params: dict) -> dict:
    from dreamforge_prompt.ideogram4 import validate_ideogram_caption

    text = str(params.get("prompt") or params.get("caption") or "").strip()
    if not text:
        return {"ok": False, "errors": ["caption required"], "normalized": None}
    return validate_ideogram_caption(text)


def cmd_build_ideogram4_caption_from_layout(params: dict) -> dict:
    from dreamforge_prompt.ideogram4 import validate_ideogram_caption
    from dreamforge_prompt.ideogram4_layout import caption_from_layout

    elements = params.get("elements")
    if not isinstance(elements, list):
        elements = []
    style = params.get("style_description")
    style_description = style if isinstance(style, dict) else None
    caption = caption_from_layout(
        aspect_ratio=str(params.get("aspect_ratio") or "1:1"),
        high_level_description=str(params.get("high_level_description") or "").strip(),
        background=str(params.get("background") or "").strip(),
        elements=elements,
        style_description=style_description,
    )
    return validate_ideogram_caption(caption)


def cmd_list_ideogram4_caption_templates(_params: dict) -> dict:
    from dreamforge_prompt.ideogram4_templates import list_ideogram4_caption_templates

    return {"templates": list_ideogram4_caption_templates()}


def cmd_render_ideogram4_caption_template(params: dict) -> dict:
    from dreamforge_prompt.ideogram4_templates import render_ideogram4_caption_template

    return render_ideogram4_caption_template(
        str(params.get("template_id") or params.get("id") or ""),
        aspect_ratio=str(params.get("aspect_ratio") or "").strip() or None,
    )


def cmd_evolve_prompts(params: dict) -> dict:
    prompt = (params.get("prompt") or "").strip()
    if not prompt:
        return _error("prompt required")
    mode = (params.get("mode") or "Tokens").strip()
    strength = float(params.get("strength") or 35)

    variants: list[str] = []
    for _ in range(4):
        if mode == "Words":
            variants.append(_evolve_words(prompt, strength))
        elif mode == "OBP Variant":
            from random_prompt.build_dynamic_prompt import createpromptvariant

            variants.append(
                createpromptvariant(
                    prompt, max(int(strength / 10), 3), advancedprompting=False
                )
            )
        else:
            variants.append(_evolve_tokenize(prompt, strength))
    return {"ok": True, "variants": variants}


def cmd_import_image_metadata(params: dict) -> dict:
    path = (params.get("path") or "").strip()
    if not path:
        return _error("path required")
    from dreamforge_image_metadata import import_image_metadata

    return import_image_metadata(path)


def cmd_interrogate_image(params: dict) -> dict:
    path = (params.get("path") or "").strip()
    if not path:
        return _error("path required")
    from dreamforge_paths import resolve_image_path_or_raise

    try:
        resolved = resolve_image_path_or_raise(path)
    except Exception as exc:
        return _error(f"invalid_image_path: {exc}")

    try:
        from dreamforge_generation import boot_headless
        from modules.interrogate import look
        from PIL import Image

        boot_headless()
    except ImportError as exc:
        return _error(f"interrogate_unavailable: {exc}")

    class _GradioStub:
        def update(self, **kwargs):
            return kwargs

        def Info(self, _message: str) -> None:
            return None

    gr = _GradioStub()
    interrogator = str(params.get("interrogator") or "").strip().lower()
    hint = interrogator if interrogator in {"brainblip", "clip", "florence"} else ""
    try:
        with Image.open(resolved) as image:
            result = look(image.copy(), hint, gr)
    except OSError as exc:
        return _error(f"invalid_image: {exc}")
    except Exception as exc:
        return _error(f"interrogate_failed: {exc}")

    if isinstance(result, dict):
        prompt_update = result.get("prompt")
        if hasattr(prompt_update, "get"):
            prompt_val = prompt_update.get("value")
        else:
            prompt_val = prompt_update
        gallery = result.get("gallery")
        gallery_val = gallery.get("value") if hasattr(gallery, "get") else None
        caption = str(prompt_val or "").strip()
        if not caption:
            return _error("empty_caption")
        return {
            "ok": True,
            "prompt": caption,
            "gallery": gallery_val,
        }

    caption = str(result or "").strip()
    if not caption:
        return _error("empty_caption")
    return {"ok": True, "prompt": caption}


def cmd_organize_models_preview(params: dict) -> dict:
    from dreamforge_cli_inventory import MODELS_ROOT
    from modules.model_classifier import classify_directory

    classifications = classify_directory(MODELS_ROOT)
    items = [c.as_dict() for c in classifications]
    apply = bool(params.get("apply", False))
    moved = 0
    if apply:
        from modules.model_organizer import organize_models

        payload = organize_models(MODELS_ROOT, apply=True, min_confidence=0.55)
        moved = len(payload.get("moves", []))
    return {"ok": True, "items": items, "moved": moved, "count": len(items)}


STUDIO_HANDLERS = {
    "get_lora_info": cmd_get_lora_info,
    "aggregate_lora_keywords": cmd_aggregate_lora_keywords,
    "apply_styles_to_prompt": cmd_apply_styles_to_prompt,
    "list_wildcards": cmd_list_wildcards,
    "match_wildcards": cmd_match_wildcards,
    "get_studio_settings": cmd_get_studio_settings,
    "save_studio_settings": cmd_save_studio_settings,
    "get_app_config": cmd_get_app_config,
    "save_app_config": cmd_save_app_config,
    "list_agent_providers": cmd_list_agent_providers,
    "test_agent_provider": cmd_test_agent_provider,
    "agent_plan": cmd_agent_plan,
    "browse_images": cmd_browse_images,
    "image_browser_metadata": cmd_image_browser_metadata,
    "image_browser_reindex": cmd_image_browser_reindex,
    "random_onebutton_prompt": cmd_random_onebutton_prompt,
    "enhance_studio_prompt": cmd_enhance_studio_prompt,
    "validate_ideogram4_caption": cmd_validate_ideogram4_caption,
    "build_ideogram4_caption_from_layout": cmd_build_ideogram4_caption_from_layout,
    "list_ideogram4_caption_templates": cmd_list_ideogram4_caption_templates,
    "render_ideogram4_caption_template": cmd_render_ideogram4_caption_template,
    "evolve_prompts": cmd_evolve_prompts,
    "import_image_metadata": cmd_import_image_metadata,
    "interrogate_image": cmd_interrogate_image,
    "organize_models_preview": cmd_organize_models_preview,
}
