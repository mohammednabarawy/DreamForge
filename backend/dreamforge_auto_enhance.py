"""Auto-enhance orchestration: detection prompt / target presets -> mask or FaceDetailer."""

from __future__ import annotations

import re
from typing import Any

VALID_ENHANCE_TARGETS = frozenset({"face", "hands", "eyes", "auto"})

DEFAULT_DETAIL_PROMPTS: dict[str, str] = {
    "face": "detailed face, sharp eyes, natural skin, high quality portrait",
    "hands": "detailed hands, natural fingers, anatomically correct",
    "eyes": "sharp detailed eyes, clear iris, natural eyelashes",
}

DETECTION_KEYWORDS: dict[str, str] = {
    "face": "face",
    "faces": "face",
    "hand": "hands",
    "hands": "hands",
    "finger": "hands",
    "fingers": "hands",
    "eye": "eyes",
    "eyes": "eyes",
}


def is_auto_enhance_job(job) -> bool:
    return bool(
        getattr(job, "enhance_auto_fix", False)
        or str(getattr(job, "enhance_target", "") or "").strip()
    )


def _normalize_target(value: Any) -> str | None:
    key = str(value or "").strip().lower()
    return key if key in VALID_ENHANCE_TARGETS else None


def parse_detection_targets(
    detection_prompt: str | None,
    enhance_target: str | None,
) -> list[str]:
    """Map free-text detection prompt + preset to selection kinds."""
    explicit = _normalize_target(enhance_target)
    if explicit and explicit != "auto":
        return [explicit]

    text = str(detection_prompt or "").strip().lower()
    if not text:
        return ["face"] if explicit == "auto" else []

    found: list[str] = []
    tokens = re.split(r"[,;/]+|\band\b", text)
    for token in tokens:
        word = token.strip()
        if not word:
            continue
        mapped = DETECTION_KEYWORDS.get(word)
        if mapped and mapped not in found:
            found.append(mapped)
    return found


def resolve_auto_enhance_plan(job) -> dict[str, Any]:
    """Decide FaceDetailer vs masked inpaint for the primary enhance target."""
    if not is_auto_enhance_job(job):
        return {"mode": "none"}

    targets = parse_detection_targets(
        getattr(job, "enhance_detection_prompt", None),
        getattr(job, "enhance_target", None),
    )
    if not targets:
        return {"mode": "invalid", "reason": "enhance_target or detection prompt required"}

    primary = targets[0]
    src = (
        getattr(job, "upscale_image", None)
        or getattr(job, "input_image", None)
        or getattr(job, "reference_image", None)
    )
    if not src:
        return {"mode": "invalid", "reason": "source image required for auto-enhance"}

    detail_prompt = (
        str(getattr(job, "detail_prompt", "") or "").strip()
        or str(getattr(job, "enhance_detection_prompt", "") or "").strip()
        or DEFAULT_DETAIL_PROMPTS.get(primary, DEFAULT_DETAIL_PROMPTS["face"])
    )

    plan: dict[str, Any] = {
        "mode": "face_detail" if primary in {"face", "hands"} else "inpaint_mask",
        "primary_target": primary,
        "source_image": str(src),
        "detail_prompt": detail_prompt,
        "selection_kind": primary if primary == "eyes" else None,
    }
    if primary == "hands":
        plan["detail_target"] = "hand"
    elif primary == "face":
        plan["detail_target"] = "face"
    return plan


def apply_auto_enhance_to_job(job) -> dict[str, Any]:
    """Project auto-enhance plan onto legacy routing fields."""
    plan = resolve_auto_enhance_plan(job)
    if plan.get("mode") == "none":
        return {}
    if plan.get("mode") == "invalid":
        return {"enhance_auto_fix": True, "auto_enhance_error": plan.get("reason")}

    src = plan["source_image"]
    out: dict[str, Any] = {
        "enhance_auto_fix": True,
        "input_image": src,
        "style": "image_edit",
        "detail_prompt": plan["detail_prompt"],
    }

    if plan["mode"] == "face_detail":
        out.update(
            {
                "workflow_mode": "face_detail",
                "detail_target": plan.get("detail_target", "face"),
                "cn_selection": "None",
                "cn_type": "None",
                "edit_type": "auto",
            }
        )
    else:
        out.update(
            {
                "workflow_mode": "generate",
                "reference_role": "inpaint",
                "edit_type": "inpaint",
                "cn_selection": "Custom...",
                "cn_type": "inpaint",
                "inpaint_intent": "improve_detail",
                "_auto_enhance_selection": plan.get("selection_kind") or "eyes",
            }
        )

    if bool(getattr(job, "enhance_post_upscale", False)):
        out["post_upscale_enabled"] = True
        out["post_upscale"] = str(getattr(job, "post_upscale", None) or "ultimate_sd_upscale")

    for key, value in out.items():
        if not key.startswith("_"):
            setattr(job, key, value)
        else:
            setattr(job, key, value)
    return out
