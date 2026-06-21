"""Preview-time prompt enhancement for the desktop prompt bar."""

from __future__ import annotations

from typing import Any

from dreamforge_prompt.pipeline import (
    _is_modern_family,
    prepare_generation_prompts,
)


def studio_enhancer_for_preview(studio_mode: str, family: str) -> str:
    """Pick RuinedFooocus-style enhancer for UI preview (may differ from runtime default)."""
    mode = (studio_mode or "generate").strip().lower()
    fam = (family or "").strip().lower()

    if mode in {"upscale", "agent"}:
        return "none"
    if mode in {"edit", "inpaint"}:
        if fam.startswith("qwen") or "kontext" in fam:
            return "none"
        if _is_modern_family(fam):
            return "none"
        return "flufferizer"
    if _is_modern_family(fam):
        return "none"
    return "flufferizer"


def _enhance_hint(studio_mode: str, family: str, enhancer: str | None) -> str:
    mode = (studio_mode or "generate").lower()
    fam = (family or "").lower()
    if mode == "upscale":
        return "Enhanced for upscale: detail restoration wording"
    if mode == "inpaint":
        return "Enhanced for inpaint: mask-local edit with seamless blend"
    if mode == "edit" and fam.startswith("qwen"):
        return "Enhanced for Qwen Image Edit: identity-safe localized edit"
    if mode == "edit" and "kontext" in fam:
        return "Enhanced for Flux Kontext: single-change edit with preservation"
    if enhancer == "flufferizer":
        return "Enhanced with Flufferizer expansion (Fooocus-style prompt boost)"
    if mode == "generate" and _is_modern_family(fam):
        return f"Enhanced for {fam or 'model'} generation quality"
    return "Prompt enhanced for the current model and studio mode"


def _apply_studio_mode(job, studio_mode: str) -> None:
    mode = (studio_mode or "generate").strip().lower()
    job.workflow_mode = mode
    if mode == "inpaint" and not getattr(job, "edit_type", None):
        job.edit_type = "inpaint"
    if mode == "edit" and str(getattr(job, "edit_type", "") or "").lower() in {"", "auto"}:
        family_hint = str(getattr(job, "model", "") or "").lower()
        if "qwen" in family_hint:
            job.edit_type = "qwen_edit"


def enhance_studio_prompt(params: dict[str, Any]) -> dict[str, Any]:
    """Enhance a studio prompt for preview in the prompt bar (no GPU generation)."""
    prompt_raw = str(params.get("prompt") or "").strip()
    if not prompt_raw:
        return {"ok": False, "error": "prompt required"}

    studio_mode = str(
        params.get("studio_mode") or params.get("workflow_mode") or "generate"
    ).lower()
    if studio_mode == "agent":
        studio_mode = "generate"

    from dreamforge_cli_direct import (
        _apply_edit_recipe_settings,
        _apply_generation_recipe_settings,
        _auto_settings,
        _compile_job,
    )
    from dreamforge_engine import DreamForgeEngine

    base_args = DreamForgeEngine._to_namespace(params)
    job, model, prompt, negative, width, height, _brand_kit = _compile_job(
        base_args, params
    )
    _apply_studio_mode(job, studio_mode)

    family = str(model.get("family") or "").lower()
    if family == "ideogram4" and studio_mode == "inpaint":
        from dreamforge_prompt.ideogram4 import ideogram_inpaint_prompt

        return {
            "ok": True,
            "prompt": ideogram_inpaint_prompt(prompt_raw, job),
            "negative_prompt": "",
            "hint": "Enhanced for inpaint: natural-language mask-local edit (no JSON caption)",
            "prompt_enhancer": "none",
            "prompt_format": "natural",
            "model_family": family,
            "studio_mode": studio_mode,
        }
    if family == "ideogram4" and studio_mode in ("generate", "edit"):
        from dreamforge_prompt.ideogram4 import run_ideogram4_magic_prompt

        magic = run_ideogram4_magic_prompt(
            prompt_raw,
            int(width or 1024),
            int(height or 1024),
            params=params,
        )
        if not magic.get("ok"):
            return {"ok": False, "error": magic.get("error") or "Ideogram magic prompt failed"}
        return {
            "ok": True,
            "prompt": magic.get("prompt") or prompt_raw,
            "negative_prompt": "",
            "hint": "Structured Ideogram 4 JSON caption (DreamForge brain)",
            "prompt_enhancer": "none",
            "prompt_format": "json",
            "model_family": family,
            "studio_mode": studio_mode,
            "magic_prompt_source": magic.get("magic_prompt_source"),
        }

    enhancer = studio_enhancer_for_preview(studio_mode, family)
    job.prompt_enhancer = enhancer

    settings = _apply_generation_recipe_settings(
        _apply_edit_recipe_settings(
            _auto_settings(model, job, width, height, negative),
            model,
            job,
        ),
        model,
        job,
    )
    settings["styles"] = list(
        getattr(job, "styles", None) or settings.get("styles") or []
    )

    prepared = prepare_generation_prompts(
        job,
        model,
        prompt,
        negative,
        settings,
        download_expansion=bool(params.get("download_expansion", True)),
    )

    out_prompt = str(prepared.get("prompt") or prompt_raw).strip()

    return {
        "ok": True,
        "prompt": out_prompt,
        "negative_prompt": prepared.get("negative") or negative or "",
        "hint": _enhance_hint(
            studio_mode, family, prepared.get("prompt_enhancer") or enhancer
        ),
        "prompt_enhancer": prepared.get("prompt_enhancer") or enhancer,
        "model_family": family,
        "studio_mode": studio_mode,
        "expansion_available": prepared.get("expansion_available"),
    }
