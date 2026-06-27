"""Task-first model/workflow routing (single policy source for creative tasks)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EDIT_ALLOWED_FAMILIES = frozenset({"flux_kontext", "qwen_image_edit"})
EDIT_FORBIDDEN_SIMPLE_FAMILIES = frozenset({"ideogram4"})


def _gallery_hay(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key, ""))
        for key in ("family", "caption", "engine_name", "relative_path", "name")
    ).lower()


def find_gallery_item(gallery: list[Any], engine_name: str) -> dict[str, Any] | None:
    target = str(engine_name or "").strip().lower()
    if not target:
        return None
    for raw in gallery or []:
        if not isinstance(raw, dict):
            continue
        for key in ("engine_name", "name", "relative_path", "caption"):
            val = str(raw.get(key) or "").strip().lower()
            if val and (val == target or val.endswith("/" + target) or target.endswith(val)):
                return dict(raw)
    return None


def gallery_family(gallery: list[Any], engine_name: str) -> str:
    item = find_gallery_item(gallery, engine_name)
    return str(item.get("family") or "").lower() if item else ""


def _is_qwen_edit_item(item: dict[str, Any]) -> bool:
    hay = _gallery_hay(item)
    return "qwen" in hay and "edit" in hay


def _is_kontext_item(item: dict[str, Any]) -> bool:
    family = str(item.get("family") or "").lower()
    if family == "flux_kontext":
        return True
    hay = _gallery_hay(item)
    return "kontext" in hay and "fill" not in hay


def pick_curated_edit_model(gallery: list[Any]) -> tuple[str, str]:
    """Return (engine_name, edit_type) — Kontext first, then Qwen Edit."""
    from dreamforge_app_config import _pick_model_for_mode

    kontext = _pick_model_for_mode("edit", gallery, edit_type="kontext")
    if kontext:
        return kontext, "kontext"
    qwen = _pick_model_for_mode("edit", gallery, edit_type="qwen_edit")
    if qwen:
        return qwen, "qwen_edit"
    return "", "kontext"


def edit_routing_patch(
    gallery: list[Any],
    engine_name: str,
    *,
    preferred_edit_type: str | None = None,
) -> dict[str, Any]:
    from dreamforge_edit_routing import edit_routing_for_model

    item = find_gallery_item(gallery, engine_name) or {}
    family = str(item.get("family") or "").lower()
    patch = edit_routing_for_model(item, family)
    pref = str(preferred_edit_type or "").lower()
    if pref == "qwen_edit":
        return {
            "edit_type": "qwen_edit",
            "edit_strength": 1.0,
            "cn_selection": "None",
            "cn_type": "None",
        }
    if pref == "kontext" and patch.get("edit_type") != "qwen_edit":
        return {
            "edit_type": "kontext",
            "edit_strength": 1.0,
            "cn_selection": "None",
            "cn_type": "None",
            "steps": 20,
        }
    return patch


@dataclass
class RouteDecision:
    patch: dict[str, Any]
    route_reason: str = ""
    workflow_kind: str = ""
    warnings: list[str] = field(default_factory=list)


def apply_task_routing(
    settings: dict[str, Any],
    studio_mode: str,
    gallery: list[Any] | None,
    *,
    advanced_mode: bool = False,
    user_picked_model: bool = False,
) -> RouteDecision:
    """Apply mode contracts; mutate and return a settings patch dict."""
    mode = (studio_mode or "generate").strip().lower()
    if mode == "agent":
        mode = "generate"
    gallery_list = gallery if isinstance(gallery, list) else []
    out = dict(settings)
    warnings: list[str] = []
    reason = "unchanged"

    if mode == "edit":
        from dreamforge_edit_routing import model_supports_edit

        current = str(out.get("model") or "").strip()
        family = gallery_family(gallery_list, current)
        current_item = find_gallery_item(gallery_list, current) if current else None
        manual = bool(
            user_picked_model
            and current
            and current_item
            and model_supports_edit(current_item, family)
        )

        if manual:
            if family in EDIT_FORBIDDEN_SIMPLE_FAMILIES:
                warnings.append(
                    "Ideogram 4 is optimized for generation — Flux Kontext or Qwen Edit usually give better photo edits."
                )
            out.update(
                edit_routing_patch(
                    gallery_list,
                    current,
                    preferred_edit_type=str(out.get("edit_type") or ""),
                )
            )
            reason = "user_edit_override"
        else:
            item = find_gallery_item(gallery_list, current) or {}
            valid = bool(
                current
                and model_supports_edit(item, family)
                and family not in EDIT_FORBIDDEN_SIMPLE_FAMILIES
            )
            if valid:
                out.update(
                    edit_routing_patch(
                        gallery_list,
                        current,
                        preferred_edit_type=str(out.get("edit_type") or ""),
                    )
                )
                reason = "compatible_edit_model"
            else:
                model, _edit_type = pick_curated_edit_model(gallery_list)
                if model:
                    out["model"] = model
                out.update(
                    edit_routing_patch(
                        gallery_list,
                        out.get("model") or model,
                        preferred_edit_type=str(out.get("edit_type") or _edit_type),
                    )
                )
                if family in EDIT_FORBIDDEN_SIMPLE_FAMILIES and model:
                    warnings.append(
                        f"Routed edit away from {current or family} to {model} (task-appropriate edit model)."
                    )
                reason = "easy_edit_default" if not advanced_mode else "pro_auto_edit_route"

        out["user_picked_model"] = bool(manual)
        out["advanced_mode"] = bool(advanced_mode)
        kind = str(out.get("edit_type") or "kontext")
        return RouteDecision(
            patch=out,
            route_reason=reason,
            workflow_kind=f"{kind}_edit",
            warnings=warnings,
        )

    if mode == "inpaint":
        from dreamforge_inpaint_routing import model_supports_inpaint, pick_best_inpaint_model
        from dreamforge_krita_resources import STUDIO_MODE_DEFAULTS

        current = str(out.get("model") or "").strip()
        current_item = find_gallery_item(gallery_list, current) if current else None
        manual = bool(
            user_picked_model
            and current
            and current_item
            and model_supports_inpaint(current_item, gallery_family(gallery_list, current))
        )
        fill = pick_best_inpaint_model(gallery_list)
        defaults = STUDIO_MODE_DEFAULTS.get("inpaint", {})

        if not manual:
            if fill:
                out["model"] = fill
            elif defaults.get("model_name"):
                out["model"] = defaults["model_name"]
            reason = "easy_inpaint_default"
        else:
            if not model_supports_inpaint(current_item, gallery_family(gallery_list, current)):
                warnings.append(
                    f"Selected model {current} may not support inpaint; Flux Fill or an "
                    "SDXL inpaint checkpoint is recommended."
                )
            reason = "user_inpaint_override"

        out["edit_type"] = "inpaint"
        out["cn_selection"] = "Custom..."
        out["cn_type"] = "inpaint"
        out["user_picked_model"] = bool(manual)
        out["advanced_mode"] = bool(advanced_mode)
        return RouteDecision(
            patch=out,
            route_reason=reason,
            workflow_kind="inpaint",
            warnings=warnings,
        )

    if mode == "upscale":
        from dreamforge_upscale_routing import pick_best_sdxl_upscale_checkpoint

        current = str(out.get("model") or "").strip()
        manual = bool(advanced_mode and user_picked_model and current)

        if manual:
            out["user_picked_model"] = True
            out["advanced_mode"] = True
            reason = "pro_upscale_user_model"
            warnings.append(
                "Using your selected checkpoint for Enhance — non-SDXL models (e.g. Flux) are allowed in Pro mode."
            )
        else:
            sdxl = pick_best_sdxl_upscale_checkpoint(gallery_list)
            if sdxl:
                out["model"] = sdxl
            out["user_picked_model"] = False
            out["advanced_mode"] = bool(advanced_mode)
            reason = "easy_upscale_sdxl_default"

        out.setdefault("upscale_method", "ultimate_sd_upscale")
        out.setdefault("cn_selection", "Custom...")
        out.setdefault("cn_type", "upscale")
        return RouteDecision(
            patch=out,
            route_reason=reason,
            workflow_kind="upscale",
            warnings=warnings,
        )

    out["advanced_mode"] = bool(advanced_mode)
    return RouteDecision(patch=out, route_reason=reason, workflow_kind=mode)
