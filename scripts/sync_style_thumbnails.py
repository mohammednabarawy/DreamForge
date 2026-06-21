#!/usr/bin/env python3
"""Sync Fooocus/RuinedFooocus style preview images into backend/assets/style_thumbnails."""

from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dreamforge_style_assets import STYLE_THUMBNAILS_DIR, fooocus_sample_filename  # noqa: E402
from dreamforge_style_recipes import STYLE_RECIPES  # noqa: E402

DEFAULT_STYLES = BACKEND / "settings" / "styles.default"
FOOOCUS_SAMPLES_API = (
    "https://api.github.com/repos/lllyasviel/Fooocus/contents/sdxl_styles/samples"
)
LOCAL_SOURCE_DIRS = [
    ROOT / ".research" / "RuinedFooocus" / "sdxl_styles" / "samples",
    ROOT / ".research" / "Fooocus" / "sdxl_styles" / "samples",
    Path(r"D:\Fooocus_win64_2-5-0\Fooocus\sdxl_styles\samples"),
    Path(r"D:\AgentFooocus\sdxl_styles\samples"),
]


def _copy_from_local_sources() -> int:
    STYLE_THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    for source in LOCAL_SOURCE_DIRS:
        if not source.is_dir():
            continue
        for path in source.glob("*.jpg"):
            target = STYLE_THUMBNAILS_DIR / path.name
            if target.exists():
                continue
            shutil.copy2(path, target)
            copied += 1
        for path in source.glob("*.jpeg"):
            target = STYLE_THUMBNAILS_DIR / path.with_suffix(".jpg").name
            if target.exists():
                continue
            shutil.copy2(path, target)
            copied += 1
    return copied


def _download_fooocus_samples(*, limit: int | None = None) -> int:
    STYLE_THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        FOOOCUS_SAMPLES_API,
        headers={"User-Agent": "DreamForge-style-sync"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    import json

    entries = json.loads(payload.decode("utf-8"))
    downloaded = 0
    for entry in entries:
        if entry.get("type") != "file":
            continue
        name = str(entry.get("name") or "")
        if not name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        target = STYLE_THUMBNAILS_DIR / (Path(name).stem + ".jpg")
        if target.exists():
            continue
        download_url = entry.get("download_url")
        if not download_url:
            continue
        with urllib.request.urlopen(download_url, timeout=120) as img_response:
            target.write_bytes(img_response.read())
        downloaded += 1
        if limit is not None and downloaded >= limit:
            break
    return downloaded


def _report_coverage() -> None:
    missing = []
    for style_id, spec in STYLE_RECIPES.items():
        original = str(spec.get("original_name") or "").strip()
        candidates = [
            STYLE_THUMBNAILS_DIR / f"{style_id}.jpg",
        ]
        if original:
            candidates.append(STYLE_THUMBNAILS_DIR / fooocus_sample_filename(original))
        if not any(path.is_file() for path in candidates):
            missing.append(style_id)
    total = len(STYLE_RECIPES)
    have = total - len(missing)
    print(f"Thumbnails: {have}/{total} styles covered in {STYLE_THUMBNAILS_DIR}")
    if missing[:10]:
        print("Missing examples:", ", ".join(missing[:10]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download Fooocus sample JPGs from GitHub (lllyasviel/Fooocus)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit remote downloads (for quick smoke sync)",
    )
    args = parser.parse_args()

    copied = _copy_from_local_sources()
    print(f"Copied {copied} thumbnail(s) from local Fooocus/RuinedFooocus installs.")

    if args.download:
        fetched = _download_fooocus_samples(limit=args.limit)
        print(f"Downloaded {fetched} thumbnail(s) from Fooocus GitHub.")

    _report_coverage()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
