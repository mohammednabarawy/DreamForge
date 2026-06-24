"""Canonical aspect-ratio presets for DreamForge desktop + CLI UI."""

from __future__ import annotations

# Fooocus / SDXL extras not present in settings/resolutions.json.
_EXTRA_ASPECT_RATIOS: tuple[tuple[int, int], ...] = (
    (704, 896),
    (896, 704),
    (640, 960),
    (1056, 704),
    (1536, 640),
    (640, 1536),
)

# HiDream-O1 Dev profile targets + optional Quality alternates (up to 2048 native).
_HIDREAM_O1_ASPECT_RATIOS: tuple[tuple[int, int], ...] = (
    (1536, 1536),
    (1344, 1792),
    (1792, 1344),
    (2048, 2048),
    (1728, 2304),
    (2304, 1728),
    (1440, 2560),
    (2560, 1440),
)


def _aspect_label(width: int, height: int) -> str:
    return f"{int(width)}x{int(height)}"


def _parse_aspect_label(text: str) -> str | None:
    raw = (text or "").strip().replace("×", "x")
    if not raw:
        return None
    head = raw.split("(", 1)[0].strip()
    if "x" not in head.lower():
        return None
    w_s, h_s = head.lower().split("x", 1)
    try:
        w, h = int(w_s), int(h_s)
    except ValueError:
        return None
    if w <= 0 or h <= 0:
        return None
    return _aspect_label(w, h)


def list_aspect_ratio_presets() -> list[str]:
    """Merge resolutions.json, legacy Fooocus sizes, and HiDream-O1 targets."""
    seen: set[str] = set()
    ordered: list[str] = []

    def add(width: int, height: int) -> None:
        label = _aspect_label(width, height)
        if label in seen:
            return
        seen.add(label)
        ordered.append(label)

    try:
        from modules.resolutions import ResolutionSettings

        rs = ResolutionSettings()
        for _key, (width, height) in rs.aspect_ratios.items():
            add(width, height)
    except Exception:
        pass

    for width, height in _EXTRA_ASPECT_RATIOS + _HIDREAM_O1_ASPECT_RATIOS:
        add(width, height)

    ordered.sort(key=lambda item: (int(item.split("x")[0]) * int(item.split("x")[1]), item))
    return ordered


def list_aspect_ratio_presets_ui() -> list[str]:
    """Desktop dropdown labels (Unicode × for display parity with legacy UI)."""
    return [item.replace("x", "×") for item in list_aspect_ratio_presets()]


def normalize_aspect_preset(value: str | None) -> str | None:
    if not value:
        return None
    return _parse_aspect_label(value)
