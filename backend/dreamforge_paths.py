"""Shared path resolution helpers for DreamForge backend."""
from __future__ import annotations

from pathlib import Path

from _paths import OUTPUTS_ROOT, PROJECT_ROOT


def resolve_image_path(path: str | None) -> Path | None:
    """Resolve an input/reference image path the same way the desktop preview does."""
    if not path or not str(path).strip():
        return None

    raw = str(path).strip()
    image_path = Path(raw)
    if image_path.is_file():
        return image_path.resolve()

    if not image_path.is_absolute():
        candidate = (PROJECT_ROOT / image_path).resolve()
        if candidate.is_file():
            return candidate

    parts = image_path.parts
    lowered = [part.lower() for part in parts]
    if "outputs" in lowered:
        idx = lowered.index("outputs")
        candidate = OUTPUTS_ROOT.joinpath(*parts[idx + 1 :]).resolve()
        if candidate.is_file():
            return candidate

    return None


def resolve_image_path_or_raise(path: str | None) -> Path:
    resolved = resolve_image_path(path)
    if resolved is None:
        raise FileNotFoundError(f"Input image not found: {path}")
    return resolved
