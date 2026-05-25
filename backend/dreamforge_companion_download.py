"""Download companion CLIP/VAE/text-encoder files for modern model families."""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path
from typing import Any

from dreamforge_cli_inventory import MODELS_ROOT, companion_file_present

# Comfy-Org/flux1-dev no longer hosts CLIP/T5/VAE; use upstream mirrors.
HF_BASE_FLUX_TEXT = (
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main"
)
HF_BASE_FLUX_VAE = (
    "https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main"
)
HF_BASE_QWEN = "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main"
HF_BASE_QWEN_CLIP = (
    "https://huggingface.co/unsloth/Qwen2.5-VL-7B-Instruct-GGUF/resolve/main"
)

# Shared catalog keyed by dependency id (referenced from MODEL_DEPENDENCIES).
COMPANION_SOURCES: dict[str, dict[str, Any]] = {
    "vae_flux_ae": {
        "url": f"{HF_BASE_FLUX_VAE}/ae.safetensors",
        "min_bytes": 300 * 1024 * 1024,
        # Gated on Hugging Face — set HF_TOKEN after accepting the model license.
        "requires_hf_token": True,
    },
    "clip_l_flux": {
        "url": f"{HF_BASE_FLUX_TEXT}/clip_l.safetensors",
        "min_bytes": 200 * 1024 * 1024,
    },
    "clip_t5_flux_fp8": {
        "url": f"{HF_BASE_FLUX_TEXT}/t5xxl_fp8_e4m3fn.safetensors",
        "min_bytes": 4 * 1024 * 1024 * 1024,
    },
    "clip_qwen25_vl_7b": {
        "url": f"{HF_BASE_QWEN}/qwen_2.5_vl_7b_fp8_scaled.safetensors",
        "min_bytes": 6 * 1024 * 1024 * 1024,
    },
    "clip_qwen25_gguf_compatible": {
        "url": f"{HF_BASE_QWEN_CLIP}/Qwen2.5-VL-7B-Instruct-Q4_K_S.gguf",
        "min_bytes": 4 * 1024 * 1024 * 1024,
    },
    "vae_qwen_image": {
        "url": f"{HF_BASE_QWEN}/qwen_image_vae.safetensors",
        "min_bytes": 200 * 1024 * 1024,
    },
}


def companion_category(relative: str) -> str:
    folder = relative.split("/", 1)[0] if "/" in relative else ""
    if folder in ("vae", "clip", "loras", "controlnet", "upscale_models", "checkpoints"):
        return folder
    if folder == "text_encoders":
        return "text_encoders"
    return folder or "checkpoints"


def companion_filename(relative: str) -> str:
    return Path(relative).name


def enrich_missing_dependency(entry: dict) -> dict:
    """Attach download url/category/filename for desktop companion fetch."""
    source = COMPANION_SOURCES.get(entry.get("id", ""), {})
    relative = entry.get("relative") or ""
    enriched = dict(entry)
    if source.get("url"):
        enriched["url"] = source["url"]
        enriched["category"] = companion_category(relative)
        enriched["filename"] = companion_filename(relative)
        enriched["min_bytes"] = source.get("min_bytes", 1024 * 1024)
        if source.get("requires_hf_token"):
            enriched["requires_hf_token"] = True
    return enriched


def _download_file(url: str, dest: Path, *, min_bytes: int = 1024 * 1024) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size >= min_bytes:
        return dest

    partial = dest.with_suffix(dest.suffix + ".partial")
    headers = {"User-Agent": "DreamForge-companion-download/1.0"}
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    if len(data) < min_bytes:
        raise OSError(
            f"Downloaded file too small ({len(data)} bytes); expected at least {min_bytes}."
        )
    partial.write_bytes(data)
    partial.replace(dest)
    return dest


def download_companion(entry: dict) -> dict:
    """Download one companion entry (must include url + expected_path or relative)."""
    enriched = enrich_missing_dependency(entry)
    url = enriched.get("url")
    if not url:
        return {
            "status": "skipped",
            "id": enriched.get("id"),
            "reason": "no_download_url",
        }

    relative = enriched.get("relative") or ""
    dest = Path(enriched.get("expected_path") or (MODELS_ROOT / relative))
    dest.parent.mkdir(parents=True, exist_ok=True)

    min_bytes = int(enriched.get("min_bytes") or 1024 * 1024)
    if companion_file_present(enriched, min_bytes=min_bytes):
        return {
            "status": "exists",
            "path": str(dest),
            "id": enriched.get("id"),
        }

    path = _download_file(
        url,
        dest,
        min_bytes=int(enriched.get("min_bytes") or 1024 * 1024),
    )
    return {"status": "downloaded", "path": str(path), "id": enriched.get("id")}


def download_missing_companions(missing: list[dict]) -> dict:
    results = []
    errors = []
    for entry in missing:
        try:
            results.append(download_companion(entry))
        except Exception as exc:
            errors.append(
                {
                    "id": entry.get("id"),
                    "relative": entry.get("relative"),
                    "error": str(exc),
                }
            )
    return {
        "status": "error" if errors and not results else "ok",
        "results": results,
        "errors": errors,
        "downloaded": sum(1 for r in results if r.get("status") == "downloaded"),
        "skipped": sum(1 for r in results if r.get("status") in ("exists", "skipped")),
    }
