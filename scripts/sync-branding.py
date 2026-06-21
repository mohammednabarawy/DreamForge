"""Copy DreamForge branding assets into desktop public/ and backend html/."""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP_BRAND = ROOT / "apps" / "desktop" / "public" / "branding"
HTML = ROOT / "backend" / "html"
ICONS = ROOT / "apps" / "desktop" / "src-tauri" / "icons"

SOURCES = [DESKTOP_BRAND]

FILES = {
    "logo-icon.png": ["logo-icon.png", "d__DreamForge_logo-icon.png"],
    "logo-wordmark.png": ["logo-wordmark.png", "d__DreamForge_logo-wordmark.png"],
    "background.png": ["background.png", "d__DreamForge_background.png"],
    "32x32.png": ["32x32.png", "d__DreamForge_32x32.png"],
    "128x128@2x.png": ["128x128@2x.png", "d__DreamForge_128x128_2x.png"],
}


def resolve_src(name: str, aliases: list[str]) -> Path | None:
    for folder in SOURCES:
        if not folder.is_dir():
            continue
        for alias in aliases:
            path = folder / alias
            if path.is_file():
                return path
    return None


def main() -> None:
    DESKTOP_BRAND.mkdir(parents=True, exist_ok=True)
    HTML.mkdir(parents=True, exist_ok=True)
    ICONS.mkdir(parents=True, exist_ok=True)

    for canonical, aliases in FILES.items():
        src = resolve_src(canonical, aliases)
        if not src:
            print(f"skip missing {canonical}")
            continue
        dest = DESKTOP_BRAND / canonical
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        if canonical == "logo-icon.png":
            shutil.copy2(src, HTML / "logo.png")
        elif canonical == "logo-wordmark.png":
            shutil.copy2(src, HTML / "logo-wordmark.png")
        elif canonical == "background.png":
            shutil.copy2(src, HTML / "background.png")
        if canonical in ("32x32.png", "128x128@2x.png"):
            shutil.copy2(src, ICONS / canonical)
        print(f"copied {src.name} -> {canonical}")

    # Regenerate ico / 128 / icns from logo-icon
    import subprocess

    regen = ROOT / "apps" / "desktop" / "scripts" / "regenerate-icons.py"
    py = ROOT / "python_embeded" / "python.exe"
    if py.is_file() and regen.is_file():
        subprocess.run([str(py), str(regen)], check=True)


if __name__ == "__main__":
    main()
