"""LLM-based prompt enhancement for Flux and modern natural-language families."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from dreamforge_prompt.pipeline import (
    _inpaint_boost,
    _is_modern_family,
    _kontext_edit_boost,
    _modern_generate_boost,
    _prompt_is_rich,
)

_PURPOSE_FILES = {
    "flux_generate": "flux_generate_enhance.txt",
    "flux_kontext_edit": "flux_kontext_edit_enhance.txt",
    "flux_inpaint": "flux_inpaint_enhance.txt",
    "qwen_edit": "qwen_edit_enhance.txt",
}

_MAX_TOKENS = {
    "flux_generate": 512,
    "flux_kontext_edit": 256,
    "flux_inpaint": 256,
    "qwen_edit": 320,
}

_VALID_STRENGTHS = frozenset({"minimal", "balanced", "rich"})

_STRENGTH_HINTS = {
    "minimal": (
        "\n\nSTRENGTH: Minimal — add only missing lighting and one clarifying detail; "
        "stay close to the original length."
    ),
    "rich": (
        "\n\nSTRENGTH: Rich — expand fully toward the upper end of the target length "
        "range with vivid atmosphere and concrete sensory detail."
    ),
}

_STRENGTH_TOKEN_SCALE = {
    "minimal": 0.65,
    "balanced": 1.0,
    "rich": 1.3,
}

_TEMPLATE_CACHE: dict[str, tuple[str, str]] = {}


def _template_path(purpose: str) -> Path:
    filename = _PURPOSE_FILES.get(purpose)
    if not filename:
        raise ValueError(f"Unknown enhance purpose: {purpose}")
    return Path(__file__).with_name(filename)


def _parse_template_sections(text: str) -> tuple[str, str]:
    if "[SYSTEM]" not in text:
        return text.strip(), ""
    after_system = text.split("[SYSTEM]", 1)[1]
    if "[USER]" in after_system:
        system_part, user_part = after_system.split("[USER]", 1)
        return system_part.strip(), user_part.strip()
    return after_system.strip(), ""


def load_enhance_template(purpose: str) -> tuple[str, str]:
    """Return (system_prompt, user_template) for a purpose."""
    cached = _TEMPLATE_CACHE.get(purpose)
    if cached is not None:
        return cached
    path = _template_path(purpose)
    if not path.is_file():
        raise FileNotFoundError(f"Flux enhance template missing: {path}")
    system, user = _parse_template_sections(path.read_text(encoding="utf-8"))
    _TEMPLATE_CACHE[purpose] = (system, user)
    return system, user


def normalize_enhance_strength(value: Any) -> str:
    text = str(value or "balanced").strip().lower()
    return text if text in _VALID_STRENGTHS else "balanced"


def resolve_enhance_prefs(params: dict[str, Any] | None) -> tuple[str, bool]:
    """Read enhance strength and Flufferizer toggle from params or app config."""
    from dreamforge_app_config import load_app_config

    merged = dict(params or {})
    ui = dict(load_app_config(redacted=False).get("ui") or {})
    strength = normalize_enhance_strength(
        merged.get("enhance_strength") or ui.get("enhance_strength")
    )
    use_fluff = merged.get("use_flufferizer")
    if use_fluff is None:
        use_fluff = ui.get("use_flufferizer", True)
    return strength, bool(use_fluff)


def _strength_max_tokens(base: int, strength: str) -> int:
    scale = _STRENGTH_TOKEN_SCALE.get(strength, 1.0)
    return min(1024, max(128, int(base * scale)))


def _apply_strength_to_system(system: str, strength: str) -> str:
    hint = _STRENGTH_HINTS.get(strength, "")
    if not hint:
        return system
    return f"{system.rstrip()}{hint}"


def build_enhance_messages(
    purpose: str,
    user_prompt: str,
    *,
    enhance_strength: str = "balanced",
) -> tuple[str, str]:
    system, user_tpl = load_enhance_template(purpose)
    system = _apply_strength_to_system(system, normalize_enhance_strength(enhance_strength))
    idea = str(user_prompt or "").strip()
    if user_tpl:
        user_msg = user_tpl.replace("{{USER_PROMPT}}", idea)
    else:
        user_msg = idea
    return system, user_msg


def resolve_flux_enhance_purpose(studio_mode: str, family: str) -> str | None:
    """Map studio mode + model family to an LLM enhance template purpose."""
    mode = (studio_mode or "generate").strip().lower()
    fam = (family or "").strip().lower()

    if fam == "ideogram4":
        return None

    if mode == "generate":
        if _is_modern_for_llm(fam):
            return "flux_generate"
        return None

    if mode == "edit":
        if fam.startswith("qwen"):
            return "qwen_edit"
        if "kontext" in fam or fam == "flux_kontext":
            return "flux_kontext_edit"
        return None

    if mode == "inpaint":
        if "flux" in fam or _is_modern_for_llm(fam):
            return "flux_inpaint"
        return None

    return None


def _is_modern_for_llm(family: str) -> bool:
    fam = (family or "").lower()
    if fam == "ideogram4":
        return False
    return _is_modern_family(fam)


def should_skip_llm_enhance(
    prompt: str,
    purpose: str,
    *,
    enhance_strength: str = "balanced",
) -> tuple[bool, str]:
    text = str(prompt or "").strip()
    if not text:
        return True, "empty prompt"

    strength = normalize_enhance_strength(enhance_strength)
    purpose_key = (purpose or "").strip().lower()
    if purpose_key == "flux_generate":
        if strength == "rich":
            return False, ""
        word_count = len(text.split())
        if strength == "minimal":
            if word_count >= 40 or (word_count >= 32 and _prompt_is_rich(text)):
                return True, "prompt already detailed"
            return False, ""
        if _prompt_is_rich(text):
            return True, "prompt already detailed"
        return False, ""

    if purpose_key == "flux_kontext_edit":
        lower = text.lower()
        if len(text) > 200 and "preserve" in lower and (
            "identity" in lower or "composition" in lower
        ):
            return True, "edit instruction already complete"
        return False, ""

    if purpose_key == "flux_inpaint":
        lower = text.lower()
        if "masked" in lower and "seamless" in lower and len(text.split()) >= 20:
            return True, "inpaint instruction already complete"
        return False, ""

    if purpose_key == "qwen_edit":
        lower = text.lower()
        if (
            "edit the reference photo" in lower
            and "preserve" in lower
            and len(text.split()) >= 18
        ):
            return True, "edit instruction already complete"
        return False, ""

    return False, ""


def _clean_llm_output(text: str) -> str:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:\w+)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    if (
        len(cleaned) >= 2
        and cleaned[0] == cleaned[-1]
        and cleaned[0] in {'"', "'"}
    ):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def rule_based_fallback_prompt(
    prompt: str,
    *,
    studio_mode: str,
    family: str,
    job: Any | None = None,
) -> str:
    """Apply lightweight rule boosts when LLM enhancement is unavailable."""
    mode = (studio_mode or "generate").lower()
    fam = (family or "").lower()
    text = str(prompt or "").strip()
    if mode == "inpaint" and job is not None:
        return _inpaint_boost(job, mode, text)
    if mode == "edit" and job is not None:
        return _kontext_edit_boost(job, fam, text)
    if mode == "generate":
        return _modern_generate_boost(fam, text)
    return text


def run_flux_llm_enhance(
    user_prompt: str,
    *,
    purpose: str,
    params: dict[str, Any] | None = None,
    enhance_strength: str | None = None,
) -> dict[str, Any]:
    """Expand or rewrite a prompt via configured DreamForge brain."""
    from dreamforge_brain import AiBrain
    from dreamforge_prompt.ideogram4 import _configure_brain_from_app_config

    purpose_key = str(purpose or "").strip().lower()
    if purpose_key not in _PURPOSE_FILES:
        return {"ok": False, "error": f"Unknown enhance purpose: {purpose}"}

    strength, _use_fluff = resolve_enhance_prefs(params)
    if enhance_strength is not None:
        strength = normalize_enhance_strength(enhance_strength)

    prompt_raw = str(user_prompt or "").strip()
    if not prompt_raw:
        return {"ok": False, "error": "prompt required"}

    skip, skip_reason = should_skip_llm_enhance(
        prompt_raw, purpose_key, enhance_strength=strength
    )
    if skip:
        return {
            "ok": True,
            "prompt": prompt_raw,
            "skipped": True,
            "skipped_reason": skip_reason,
            "enhance_source": "skip",
            "purpose": purpose_key,
            "enhance_strength": strength,
        }

    try:
        system, user_msg = build_enhance_messages(
            purpose_key, prompt_raw, enhance_strength=strength
        )
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc)}

    brain = AiBrain()
    _configure_brain_from_app_config(brain, params)
    max_tokens = _strength_max_tokens(_MAX_TOKENS.get(purpose_key, 384), strength)

    try:
        raw = brain.think(user_msg, system, max_tokens=max_tokens)
    except Exception as exc:
        return {
            "ok": False,
            "error": (
                f"Brain prompt enhancement failed: {exc}. "
                "Check App Settings → Agent: ensure your brain provider "
                "(embedded GGUF, Ollama, or LM Studio) is running."
            ),
            "purpose": purpose_key,
        }

    cleaned = _clean_llm_output(raw)
    if not cleaned:
        return {
            "ok": False,
            "error": (
                "Brain returned an empty response. Check App Settings → Agent: "
                "ensure your brain provider is running and loaded."
            ),
            "purpose": purpose_key,
            "enhance_raw": raw,
        }

    return {
        "ok": True,
        "prompt": cleaned,
        "skipped": False,
        "enhance_source": "brain",
        "purpose": purpose_key,
        "enhance_raw": raw,
        "enhance_strength": strength,
    }
