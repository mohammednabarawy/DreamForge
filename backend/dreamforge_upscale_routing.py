"""SDXL checkpoint routing for Ultimate SD Upscale jobs."""

from __future__ import annotations

from typing import Any

SDXL_UPSCALE_NEEDLES: tuple[str, ...] = (
    "epicrealism",
    "juggernaut",
    "realvis",
    "dreamshaper",
    "sd_xl",
    "sdxl",
)


def _gallery_hay(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key, ""))
        for key in ("family", "caption", "engine_name", "relative_path", "name")
    ).lower()


def is_sdxl_checkpoint(item: dict[str, Any]) -> bool:
    family = str(item.get("family") or "").lower()
    category = str(item.get("category") or "").lower()
    hay = _gallery_hay(item)
    if family == "sdxl" or "sdxl" in hay:
        return category in {"", "checkpoints"}
    return any(needle in hay for needle in SDXL_UPSCALE_NEEDLES)


def is_upscale_compatible_checkpoint(item: dict[str, Any]) -> bool:
    """Ultimate SD Upscale only supports SDXL-style checkpoints."""
    return is_sdxl_checkpoint(item)


def _score_upscale_checkpoint(item: dict[str, Any]) -> int:
    if not is_upscale_compatible_checkpoint(item):
        return -1
    hay = _gallery_hay(item)
    family = str(item.get("family") or "").lower()
    score = 0
    if family == "sdxl":
        score += 100
    if str(item.get("category") or "").lower() == "checkpoints":
        score += 80
    for needle in SDXL_UPSCALE_NEEDLES:
        if needle in hay:
            score += 25
    if "turbo" in hay or "lightning" in hay:
        score -= 10
    return score


def pick_best_sdxl_upscale_checkpoint(gallery: list[Any] | None) -> str:
    best_name = ""
    best_score = -1
    for raw in gallery or []:
        if not isinstance(raw, dict):
            continue
        score = _score_upscale_checkpoint(raw)
        if score <= best_score:
            continue
        name = str(raw.get("engine_name") or raw.get("name") or raw.get("relative_path") or "").strip()
        if not name:
            continue
        best_score = score
        best_name = name
    return best_name


def resolve_upscale_checkpoint_model(
    model: dict[str, Any],
    gallery: list[Any] | None,
) -> tuple[dict[str, Any], str | None]:
    """Return (model_dict, warning) — auto-picks SDXL when current checkpoint is incompatible."""
    current = dict(model or {})
    current_name = str(current.get("engine_name") or current.get("name") or "").strip()
    if current and is_upscale_compatible_checkpoint(current):
        return current, None

    picked_name = pick_best_sdxl_upscale_checkpoint(gallery)
    if picked_name:
        for raw in gallery or []:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("engine_name") or raw.get("name") or raw.get("relative_path") or "")
            if name == picked_name:
                routed = dict(raw)
                label = str(routed.get("caption") or routed.get("engine_name") or picked_name)
                if current_name and current_name != picked_name:
                    return (
                        routed,
                        f"Routed upscale to SDXL checkpoint {label} (Ultimate SD Upscale requires SDXL, not {current_name}).",
                    )
                return routed, None
        routed = dict(current)
        routed["engine_name"] = picked_name
        routed["name"] = picked_name
        routed.setdefault("family", "sdxl")
        routed.setdefault("category", "checkpoints")
        return routed, f"Routed upscale to SDXL checkpoint {picked_name}."

    if current_name:
        return current, None
    return current, "No SDXL checkpoint installed for Ultimate SD Upscale — install EpicRealism XL or Juggernaut XL."
