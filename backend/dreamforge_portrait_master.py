"""Portrait Master toolbox: slider-driven portrait prompts + pose/depth ControlNet."""

from __future__ import annotations

from typing import Any

PORTRAIT_SHOTS: dict[str, str] = {
    "closeup": "extreme close-up portrait",
    "portrait": "head and shoulders portrait",
    "medium": "medium shot portrait",
    "full": "full body portrait",
}

PORTRAIT_EXPRESSIONS: dict[str, str] = {
    "neutral": "neutral expression",
    "happy": "warm smile, happy expression",
    "serious": "serious expression",
    "confident": "confident expression",
}

PORTRAIT_LIGHTING: dict[str, str] = {
    "soft": "soft diffused lighting",
    "studio": "studio portrait lighting",
    "natural": "natural window light",
    "dramatic": "dramatic cinematic lighting",
}

PORTRAIT_DEFAULT_NEGATIVE = (
    "low quality, blurry, distorted, deformed, bad anatomy, extra limbs, "
    "watermark, text, logo, oversaturated, underexposed"
)

PORTRAIT_SAMPLING_DEFAULTS: dict[str, Any] = {
    "steps": 20,
    "cfg": 5.5,
    "sampler_name": "dpmpp_2m",
    "scheduler": "karras",
    "edit_strength": 0.55,
    "portrait_pose_strength": 0.65,
    "portrait_depth_strength": 0.55,
    "portrait_megapixels": 2.0,
}


def _detail_phrase(value: float | None, *, low: str, mid: str, high: str) -> str | None:
    if value is None:
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if amount < 0.34:
        return low
    if amount < 0.67:
        return mid
    return high


def portrait_settings_from_job(job: Any) -> dict[str, Any]:
    return {
        "portrait_shot": getattr(job, "portrait_shot", None),
        "portrait_age": getattr(job, "portrait_age", None),
        "portrait_expression": getattr(job, "portrait_expression", None),
        "portrait_lighting": getattr(job, "portrait_lighting", None),
        "portrait_skin_detail": getattr(job, "portrait_skin_detail", None),
        "portrait_eye_detail": getattr(job, "portrait_eye_detail", None),
    }


def build_portrait_master_prompt(settings: dict[str, Any] | Any) -> str:
    """Build a portrait prompt from Portrait Master slider settings."""
    if not isinstance(settings, dict):
        settings = portrait_settings_from_job(settings)

    parts = ["professional portrait photograph", "photorealistic", "sharp focus"]

    shot = str(settings.get("portrait_shot") or "portrait").strip().lower()
    parts.append(PORTRAIT_SHOTS.get(shot, PORTRAIT_SHOTS["portrait"]))

    age = settings.get("portrait_age")
    try:
        age_value = int(age) if age is not None else 30
    except (TypeError, ValueError):
        age_value = 30
    age_value = max(1, min(100, age_value))
    parts.append(f"{age_value} years old")

    expression = str(settings.get("portrait_expression") or "neutral").strip().lower()
    parts.append(PORTRAIT_EXPRESSIONS.get(expression, PORTRAIT_EXPRESSIONS["neutral"]))

    lighting = str(settings.get("portrait_lighting") or "studio").strip().lower()
    parts.append(PORTRAIT_LIGHTING.get(lighting, PORTRAIT_LIGHTING["studio"]))

    skin = _detail_phrase(
        settings.get("portrait_skin_detail"),
        low="natural skin texture",
        mid="detailed skin texture",
        high="highly detailed skin pores and texture",
    )
    if skin:
        parts.append(skin)

    eyes = _detail_phrase(
        settings.get("portrait_eye_detail"),
        low="natural eyes",
        mid="detailed eyes",
        high="highly detailed eyes with catchlights",
    )
    if eyes:
        parts.append(eyes)

    return ", ".join(dict.fromkeys(part.strip() for part in parts if str(part).strip()))


def build_portrait_master_negative(settings: dict[str, Any] | Any) -> str:
    negative = PORTRAIT_DEFAULT_NEGATIVE
    shot_val = (
        settings.get("portrait_shot")
        if isinstance(settings, dict)
        else getattr(settings, "portrait_shot", None)
    )
    shot = str(shot_val or "portrait").strip().lower()
    if shot == "full":
        return negative
    return f"{negative}, full body, wide shot"


def merge_portrait_master_prompt(prompt: str, job: Any) -> str:
    from dreamforge_edit_tasks import normalize_edit_task

    if normalize_edit_task(getattr(job, "edit_task", None)) != "portrait_master":
        return prompt
    built = build_portrait_master_prompt(job)
    user = str(prompt or "").strip()
    if not user:
        return built
    if user.lower() in built.lower():
        return user
    return f"{user}, {built}"
