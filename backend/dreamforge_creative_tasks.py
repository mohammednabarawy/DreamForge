"""Unified creative task routing (Create / Edit / Fix region / Enhance)."""



from __future__ import annotations



from typing import Any



from dreamforge_creative_templates import (

    default_template_id_for_mode,

    resolve_template_patch,

)

from dreamforge_krita_resources import STUDIO_MODE_DEFAULTS

from dreamforge_vram_profiles import normalize_vram_profile, profile_tier





def apply_vram_quality_defaults(

    patch: dict[str, Any],

    *,

    studio_mode: str,

    vram_profile: str | None = None,

) -> dict[str, Any]:

    """Tighten steps/performance on low-VRAM tiers."""

    out = dict(patch)

    tier = profile_tier(normalize_vram_profile(vram_profile))

    mode = (studio_mode or "generate").strip().lower()

    steps = int(out.get("steps") or 20)



    if tier == "5gb":

        if mode == "edit" and str(out.get("edit_type") or "") == "qwen_edit":

            out["performance"] = "Lightning"

            out["steps"] = min(steps, 8)

            out.setdefault("cfg_scale", 1.0)

        elif mode == "edit":

            out["steps"] = min(steps, 12)

            out["cfg_scale"] = min(float(out.get("cfg_scale") or 7.0), 5.0)

        elif mode == "inpaint":

            out["steps"] = min(steps, 12)

        elif mode == "generate":

            out["steps"] = min(steps, 20)

    elif tier == "8gb" and mode in {"edit", "inpaint"}:

        out["steps"] = min(steps, 20)



    return out





def _resolve_template_id(

    mode: str,

    base: dict[str, Any],

    *,

    template_id: str | None = None,

) -> str | None:

    explicit = (template_id or base.get("template_id") or "").strip()

    if explicit:

        return explicit

    post_upscale = bool(base.get("post_upscale_enabled") or base.get("post_upscale"))

    return default_template_id_for_mode(mode, post_upscale=post_upscale)





def resolve_creative_task(

    studio_mode: str,

    settings: dict[str, Any] | None = None,

    model_gallery: list[Any] | None = None,

    *,

    vram_profile: str | None = None,

    advanced_mode: bool = False,

    selected_image: str = "",

    template_id: str | None = None,

    user_picked_model: bool = False,

) -> dict[str, Any]:

    """Return a settings patch for the given studio task."""

    from dreamforge_app_config import _complete_patch_for_mode

    from dreamforge_task_router import apply_task_routing



    mode = (studio_mode or "generate").strip().lower()

    if mode == "agent":

        mode = "generate"

    base = dict(settings) if isinstance(settings, dict) else {}

    gallery = model_gallery if isinstance(model_gallery, list) else []

    base_model = str(base.get("model") or "").strip()



    resolved_template_id = _resolve_template_id(mode, base, template_id=template_id)

    post_upscale_enabled = bool(

        base.get("post_upscale_enabled") or base.get("post_upscale")

    )

    template_meta = resolve_template_patch(

        resolved_template_id,

        base=base,

        vram_profile=vram_profile or base.get("vram_profile"),

        post_upscale_enabled=post_upscale_enabled,

    )

    patch: dict[str, Any] = {}

    templated = dict(template_meta.get("patch") or {})

    for key, value in templated.items():

        if key not in {"template_id", "post_upscale_enabled"}:

            patch[key] = value



    defaults = STUDIO_MODE_DEFAULTS.get(mode, {})

    if defaults.get("model_name") and not base.get("model") and not patch.get("model"):

        patch.setdefault("model", defaults["model_name"])

    if defaults.get("performance"):

        patch.setdefault("performance", defaults["performance"])



    if mode == "edit":

        src = (selected_image or base.get("input_image") or patch.get("input_image") or "").strip()

        if src:

            patch["input_image"] = src

        if not patch.get("post_upscale"):

            patch["upscale_image"] = None

            patch["upscale_method"] = None

        patch["inpaint_mask_path"] = None

    elif mode == "inpaint":

        previous_src = (base.get("input_image") or "").strip()

        # Keep the attached inpaint source authoritative; history selection is only a fallback.
        src = (previous_src or selected_image or patch.get("input_image") or "").strip()

        if src:

            patch["input_image"] = src

        if previous_src and src and src != previous_src:

            patch["inpaint_mask_path"] = None

        if not patch.get("post_upscale"):

            patch["upscale_image"] = None

            patch["upscale_method"] = None

    elif mode == "upscale":

        src = (

            selected_image

            or base.get("upscale_image")

            or base.get("input_image")

            or patch.get("upscale_image")

            or ""

        ).strip()

        if src:

            patch["upscale_image"] = src

        patch["input_image"] = None

        patch["inpaint_mask_path"] = None

        patch.pop("post_upscale", None)

    merged = _complete_patch_for_mode(mode, {**base, **patch}, selected_image, gallery)

    if (
        mode == "upscale"
        and advanced_mode
        and user_picked_model
        and base_model
    ):
        merged["model"] = base_model

    route_reason = ""
    route_warnings: list[str] = []
    workflow_kind = mode
    if mode in {"edit", "inpaint", "upscale"}:
        routed = apply_task_routing(
            merged,
            mode,
            gallery,
            advanced_mode=advanced_mode,
            user_picked_model=user_picked_model,
        )
        merged = routed.patch
        route_reason = routed.route_reason
        route_warnings = list(routed.warnings)
        workflow_kind = routed.workflow_kind or mode



    if resolved_template_id:

        merged["template_id"] = resolved_template_id

    if merged.get("post_upscale") and mode in {"edit", "inpaint"}:

        merged["upscale_image"] = None

        merged["upscale_method"] = None



    merged = apply_vram_quality_defaults(

        merged,

        studio_mode=mode,

        vram_profile=vram_profile or base.get("vram_profile"),

    )



    changed = {

        key: merged[key]

        for key in merged

        if key in patch or merged.get(key) != base.get(key)

    }

    return {

        "ok": True,

        "studio_mode": mode,

        "template_id": resolved_template_id,

        "patch": merged,

        "changed": changed,

        "model": merged.get("model") or "",

        "post_upscale": merged.get("post_upscale"),

        "template_companions": template_meta.get("companions") or [],

        "vram_tier": profile_tier(normalize_vram_profile(vram_profile or base.get("vram_profile"))),

        "route_reason": route_reason,

        "route_warnings": route_warnings,

        "workflow_kind": workflow_kind,

    }





def enforce_creative_task_settings(

    settings: dict[str, Any] | None,

    *,

    studio_mode: str,

    model_gallery: list[Any] | None = None,

    vram_profile: str | None = None,

    advanced_mode: bool = False,

    template_id: str | None = None,

    selected_image: str = "",

    user_picked_model: bool = False,

) -> dict[str, Any]:

    """Apply routing guards immediately before job submit."""

    base = dict(settings) if isinstance(settings, dict) else {}

    mode = (studio_mode or "generate").strip().lower()

    gallery = model_gallery if isinstance(model_gallery, list) else []

    resolved = resolve_creative_task(

        mode,

        base,

        gallery,

        vram_profile=vram_profile or base.get("vram_profile"),

        advanced_mode=advanced_mode,

        template_id=template_id or base.get("template_id"),

        selected_image=selected_image,

        user_picked_model=user_picked_model,

    )

    patch = resolved.get("patch") if isinstance(resolved.get("patch"), dict) else {}

    if mode not in {"edit", "inpaint", "upscale"}:

        return apply_vram_quality_defaults(

            base,

            studio_mode=mode,

            vram_profile=vram_profile or base.get("vram_profile"),

        )

    return patch

