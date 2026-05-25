"""Regenerate Tauri bundle icons from public/branding/logo-icon.png."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "public" / "branding" / "logo-icon.png"
OUT = ROOT / "src-tauri" / "icons"


def square_crop(img: Image.Image) -> Image.Image:
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


def main() -> None:
    if not SRC.is_file():
        raise SystemExit(f"Missing source: {SRC}")
    OUT.mkdir(parents=True, exist_ok=True)
    img = square_crop(Image.open(SRC).convert("RGBA"))
    for name, size in [("32x32.png", 32), ("128x128.png", 128), ("128x128@2x.png", 256)]:
        img.resize((size, size), Image.Resampling.LANCZOS).save(OUT / name)
    img.save(
        OUT / "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)],
    )
    try:
        img.resize((512, 512), Image.Resampling.LANCZOS).save(
            OUT / "icon.icns",
            format="ICNS",
        )
    except Exception as exc:
        print(f"icon.icns skipped ({exc}); macOS builds may regenerate with iconutil", file=sys.stderr)
    print(f"Wrote icons to {OUT}")


if __name__ == "__main__":
    main()
