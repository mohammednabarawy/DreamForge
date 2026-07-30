"""Unified Model Download Manager for DreamForge.

Supports HuggingFace, CivitAI, and direct HTTPS model downloads with:
- Category auto-placement (checkpoints, loras, vae, ipadapter, upscale_models, etc.)
- Resumable downloads via HTTP Range headers
- SHA256 hash verification
- Real-time progress tracking (bytes, percentage, speed MB/s, ETA)
- Persistent download manifest tracking in MODELS_ROOT / download_manifest.json
"""

import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from _paths import BACKEND_ROOT, MODELS_ROOT

MANIFEST_PATH = MODELS_ROOT / "download_manifest.json"

CATEGORY_FOLDERS = {
    "checkpoints": "checkpoints",
    "diffusion_models": "diffusion_models",
    "unet": "unet",
    "loras": "loras",
    "vae": "vae",
    "controlnet": "controlnet",
    "upscale_models": "upscale_models",
    "clip": "clip",
    "text_encoders": "text_encoders",
    "clip_vision": "clip_vision",
    "embeddings": "embeddings",
    "inpaint": "inpaint",
    "ipadapter": "ipadapter",
    "insightface": "insightface/models",
}


def resolve_category_folder(category: str) -> Path:
    cat_key = category.strip().lower()
    folder_name = CATEGORY_FOLDERS.get(cat_key, cat_key)
    dest = MODELS_ROOT / folder_name
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def parse_filename_from_url(url: str, headers: dict[str, str] | None = None) -> str:
    if headers:
        cd = headers.get("content-disposition") or headers.get("Content-Disposition") or ""
        match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';]+)["\']?', cd, re.IGNORECASE)
        if match:
            return urllib.parse.unquote(match.group(1))

    parsed = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(parsed.path)
    name = Path(path).name
    if name and "." in name:
        return name
    return "downloaded_model.safetensors"


def _read_manifest() -> list[dict[str, Any]]:
    if MANIFEST_PATH.exists():
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _record_manifest(entry: dict[str, Any]) -> None:
    manifest = _read_manifest()
    manifest = [item for item in manifest if item.get("path") != entry.get("path")]
    manifest.append(entry)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def verify_sha256(file_path: Path, expected_sha256: str) -> bool:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    digest = hasher.hexdigest().lower()
    return digest == expected_sha256.strip().lower()


def download_model(
    url: str,
    category: str = "checkpoints",
    filename: str | None = None,
    expected_sha256: str | None = None,
    civitai_api_key: str | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Download a model file with progress tracking, resuming, and sha256 verification."""
    dest_dir = resolve_category_folder(category)

    civitai_key = civitai_api_key or os.environ.get("CIVITAI_API_KEY")
    req_url = url
    if civitai_key and "civitai.com" in url and "token=" not in url:
        sep = "&" if "?" in url else "?"
        req_url = f"{url}{sep}token={civitai_key}"

    headers = {
        "User-Agent": "DreamForge-Downloader/2.0",
    }

    req = urllib.request.Request(req_url, headers=headers)

    target_filename = filename
    total_bytes = 0

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            total_bytes = int(resp.headers.get("Content-Length", 0))
            if not target_filename:
                resp_headers = dict(resp.headers)
                target_filename = parse_filename_from_url(resp.url or url, resp_headers)
    except Exception:
        if not target_filename:
            target_filename = parse_filename_from_url(url)

    target_path = dest_dir / target_filename
    part_path = dest_dir / f"{target_filename}.part"

    downloaded_bytes = 0
    if part_path.exists():
        downloaded_bytes = part_path.stat().st_size

    if downloaded_bytes > 0:
        headers["Range"] = f"bytes={downloaded_bytes}-"

    req = urllib.request.Request(req_url, headers=headers)

    start_time = time.time()
    last_update = start_time
    written_session = 0

    mode = "ab" if downloaded_bytes > 0 else "wb"

    try:
        with urllib.request.urlopen(req, timeout=30) as resp, open(part_path, mode) as out_file:
            content_range = resp.headers.get("Content-Range", "")
            if content_range and "/" in content_range:
                total_bytes = int(content_range.split("/")[-1])
            elif total_bytes == 0:
                total_bytes = downloaded_bytes + int(resp.headers.get("Content-Length", 0))

            chunk_size = 512 * 1024
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                written_session += len(chunk)
                current_total = downloaded_bytes + written_session

                now = time.time()
                elapsed = now - start_time
                speed_mbs = (written_session / (1024 * 1024)) / elapsed if elapsed > 0 else 0.0
                remaining_bytes = max(0, total_bytes - current_total)
                eta_secs = int(remaining_bytes / (speed_mbs * 1024 * 1024)) if speed_mbs > 0 else 0

                progress_data = {
                    "filename": target_filename,
                    "downloaded_bytes": current_total,
                    "total_bytes": total_bytes,
                    "percentage": round((current_total / total_bytes) * 100, 1) if total_bytes > 0 else 0.0,
                    "speed_mbs": round(speed_mbs, 2),
                    "eta_seconds": eta_secs,
                    "status": "downloading",
                }

                if progress_callback and (now - last_update >= 0.5 or current_total == total_bytes):
                    progress_callback(progress_data)
                    last_update = now

    except Exception as exc:
        return {
            "ok": False,
            "error": f"Download failed: {exc}",
            "filename": target_filename,
            "path": str(target_path),
        }

    if part_path.exists():
        if target_path.exists():
            target_path.unlink()
        part_path.rename(target_path)

    sha_ok = True
    if expected_sha256:
        sha_ok = verify_sha256(target_path, expected_sha256)
        if not sha_ok:
            return {
                "ok": False,
                "error": f"SHA256 mismatch for {target_filename}",
                "filename": target_filename,
                "path": str(target_path),
            }

    entry = {
        "url": url,
        "category": category,
        "filename": target_filename,
        "path": str(target_path),
        "size_mb": round(target_path.stat().st_size / (1024 * 1024), 2),
        "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sha256_verified": sha_ok,
    }
    _record_manifest(entry)

    if progress_callback:
        progress_callback({
            "filename": target_filename,
            "downloaded_bytes": target_path.stat().st_size,
            "total_bytes": target_path.stat().st_size,
            "percentage": 100.0,
            "speed_mbs": 0.0,
            "eta_seconds": 0,
            "status": "completed",
        })

    return {
        "ok": True,
        "filename": target_filename,
        "path": str(target_path),
        "size_mb": entry["size_mb"],
        "category": category,
    }
