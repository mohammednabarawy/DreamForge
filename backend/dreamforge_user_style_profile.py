"""Local, inspectable user style memory for planning hints."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from _paths import PROJECT_ROOT

PROFILE_PATH = PROJECT_ROOT / "outputs" / "dreamforge" / "memory" / "user_style_profile.json"
MAX_TRACKED = 12


@dataclass
class UserStyleProfile:
    enabled: bool = True
    favorite_models: list[str] = field(default_factory=list)
    favorite_styles: list[str] = field(default_factory=list)
    aspect_ratios: list[str] = field(default_factory=list)
    workflow_modes: list[str] = field(default_factory=list)
    generation_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _profile_path() -> Path:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return PROFILE_PATH


def load_profile() -> UserStyleProfile:
    path = _profile_path()
    if not path.is_file():
        return UserStyleProfile()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return UserStyleProfile()
    if not isinstance(raw, dict):
        return UserStyleProfile()
    return UserStyleProfile(
        enabled=bool(raw.get("enabled", True)),
        favorite_models=[str(item) for item in raw.get("favorite_models") or []][:MAX_TRACKED],
        favorite_styles=[str(item) for item in raw.get("favorite_styles") or []][:MAX_TRACKED],
        aspect_ratios=[str(item) for item in raw.get("aspect_ratios") or []][:MAX_TRACKED],
        workflow_modes=[str(item) for item in raw.get("workflow_modes") or []][:MAX_TRACKED],
        generation_count=int(raw.get("generation_count") or 0),
    )


def save_profile(profile: UserStyleProfile) -> UserStyleProfile:
    path = _profile_path()
    path.write_text(json.dumps(profile.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return profile


def clear_profile() -> UserStyleProfile:
    profile = UserStyleProfile(enabled=True)
    return save_profile(profile)


def export_profile() -> dict[str, Any]:
    profile = load_profile()
    return {"status": "success", "profile": profile.to_dict(), "path": str(_profile_path())}


def _top(counter: Counter[str], limit: int = MAX_TRACKED) -> list[str]:
    return [name for name, _count in counter.most_common(limit)]


def record_successful_job(params: dict[str, Any], result: dict[str, Any] | None = None) -> None:
    if result and result.get("status") != "success":
        return
    profile = load_profile()
    if not profile.enabled:
        return

    models = Counter(profile.favorite_models)
    styles = Counter(profile.favorite_styles)
    aspects = Counter(profile.aspect_ratios)
    modes = Counter(profile.workflow_modes)

    model = params.get("model")
    if model:
        models[str(model)] += 1
    for style in params.get("styles") or []:
        if style:
            styles[str(style)] += 1
    aspect = params.get("aspect_ratio")
    if aspect:
        aspects[str(aspect)] += 1
    elif params.get("width") and params.get("height"):
        aspects[f"{params['width']}x{params['height']}"] += 1
    mode = params.get("workflow_mode")
    if mode:
        modes[str(mode)] += 1

    profile.favorite_models = _top(models)
    profile.favorite_styles = _top(styles)
    profile.aspect_ratios = _top(aspects)
    profile.workflow_modes = _top(modes)
    profile.generation_count += 1
    save_profile(profile)


def apply_planning_hints(current_settings: dict[str, Any] | None) -> dict[str, Any]:
    settings = dict(current_settings or {})
    profile = load_profile()
    if not profile.enabled:
        return settings

    if not settings.get("model") and profile.favorite_models:
        settings.setdefault("model", profile.favorite_models[0])
    if not settings.get("styles") and profile.favorite_styles:
        settings.setdefault("styles", profile.favorite_styles[:3])
    if not settings.get("aspect_ratio") and profile.aspect_ratios:
        settings.setdefault("aspect_ratio", profile.aspect_ratios[0])
    if not settings.get("workflow_mode") and profile.workflow_modes:
        settings.setdefault("workflow_mode", profile.workflow_modes[0])
    return settings
