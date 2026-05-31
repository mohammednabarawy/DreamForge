"""Style recipe thumbnail paths (Fooocus/RuinedFooocus ``sdxl_styles/samples`` convention)."""

from __future__ import annotations

from pathlib import Path

from _paths import BACKEND_ROOT

STYLE_THUMBNAILS_DIR = BACKEND_ROOT / "assets" / "style_thumbnails"


def fooocus_sample_filename(display_name: str) -> str:
    """Match Fooocus sample naming: spaces and colons → underscores, ``.jpg`` suffix."""
    stem = display_name.strip().replace(" ", "_").replace(":", "_")
    while "__" in stem:
        stem = stem.replace("__", "_")
    return f"{stem}.jpg"


def resolve_style_thumbnail_path(style_id: str, spec: dict | None = None) -> str | None:
    """Return an on-disk thumbnail path for a style recipe, if one exists."""
    spec = spec or {}
    candidates: list[Path] = []

    rel = str(spec.get("thumbnail") or "").strip()
    if rel:
        rel_path = Path(rel.replace("/", "\\") if "\\" in rel else rel)
        if not rel_path.is_absolute():
            candidates.append(BACKEND_ROOT / rel_path)
        else:
            candidates.append(rel_path)

    original = str(spec.get("original_name") or "").strip()
    if original:
        candidates.append(STYLE_THUMBNAILS_DIR / fooocus_sample_filename(original))

    candidates.append(STYLE_THUMBNAILS_DIR / f"{style_id}.jpg")
    candidates.append(STYLE_THUMBNAILS_DIR / f"{style_id}.png")

    seen: set[str] = set()
    for path in candidates:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        if path.is_file():
            return str(path.resolve())

    if STYLE_THUMBNAILS_DIR.is_dir():
        wanted_stems = {
            Path(str(spec.get("thumbnail") or "")).stem.lower(),
            style_id.lower(),
        }
        original = str(spec.get("original_name") or "").strip()
        if original:
            wanted_stems.add(Path(fooocus_sample_filename(original)).stem.lower())
        for path in STYLE_THUMBNAILS_DIR.iterdir():
            if path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                continue
            stem = path.stem.lower()
            if stem in wanted_stems:
                return str(path.resolve())
    return None
