"""Read generation metadata embedded in PNG/WebP outputs."""

from __future__ import annotations

import json
import re
from typing import Any

_A1111_RE = re.compile(
    r"^(.+?)(?:\nNegative prompt:\s*(.*?))?\nSteps:\s*(\d+),\s*Sampler:\s*([^,]+?)(?:\s+(\S+))?,\s*"
    r"CFG scale:\s*([\d.]+),\s*Seed:\s*(-?\d+),\s*Size:\s*(\d+)x(\d+)",
    re.DOTALL | re.IGNORECASE,
)


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_image_info(path: str) -> dict[str, Any]:
    from PIL import Image

    with Image.open(path) as img:
        info: dict[str, Any] = {}
        for key, value in (img.info or {}).items():
            if isinstance(value, bytes):
                try:
                    value = value.decode("utf-8")
                except UnicodeDecodeError:
                    value = value.decode("utf-8", errors="replace")
            info[str(key)] = value
        return info


def _parse_parameters_blob(blob: str) -> dict[str, Any] | None:
    text = (blob or "").strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    match = _A1111_RE.match(text)
    if not match:
        return None
    prompt, negative, steps, sampler, scheduler, cfg, seed, width, height = match.groups()
    out: dict[str, Any] = {
        "Prompt": prompt.strip(),
        "Negative": (negative or "").strip(),
        "steps": int(steps),
        "sampler_name": sampler.strip(),
        "cfg": float(cfg),
        "seed": int(seed),
        "width": int(width),
        "height": int(height),
    }
    if scheduler and scheduler.strip():
        out["scheduler"] = scheduler.strip()
    return out


def extract_image_metadata(path: str) -> dict[str, Any]:
    """Return raw + parsed metadata for an image file."""
    info = _read_image_info(path)
    blob = str(info.get("parameters") or info.get("prompt") or "").strip()
    parsed = _parse_parameters_blob(blob) if blob else None
    return {
        "ok": bool(parsed),
        "file_path": path,
        "raw": info,
        "parameters": parsed,
    }


def settings_patch_from_metadata(params: dict[str, Any]) -> dict[str, Any]:
    """Map embedded parameters JSON to GenerationSettings patch keys."""
    if not isinstance(params, dict):
        return {}

    patch: dict[str, Any] = {}
    prompt = str(params.get("Prompt") or params.get("prompt") or "").strip()
    negative = str(params.get("Negative") or params.get("negative_prompt") or "").strip()
    if prompt:
        patch["prompt"] = prompt
    if negative:
        patch["negative_prompt"] = negative

    model = str(params.get("base_model_name") or params.get("model") or "").strip()
    if model:
        patch["model"] = model

    for src, dst in (
        ("steps", "steps"),
        ("cfg", "cfg_scale"),
        ("seed", "seed"),
        ("sampler_name", "sampler"),
        ("scheduler", "scheduler"),
        ("width", "width"),
        ("height", "height"),
        ("denoise", "edit_strength"),
        ("clip_skip", "clip_skip"),
    ):
        if src in params and params[src] is not None:
            if dst in {"steps", "seed", "width", "height"}:
                val = _coerce_int(params[src])
            elif dst in {"cfg_scale", "edit_strength", "clip_skip"}:
                val = _coerce_float(params[src])
            else:
                val = str(params[src]).strip() or None
            if val is not None:
                patch[dst] = val

    width = _coerce_int(params.get("width"))
    height = _coerce_int(params.get("height"))
    if width and height:
        patch["aspect_ratio"] = f"{width}x{height}"

    loras = params.get("loras")
    if isinstance(loras, list) and loras:
        names: list[str] = []
        for item in loras:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                label = str(item[1])
                name = label.split(" - ")[-1].strip() if " - " in label else label.strip()
                if name:
                    names.append(name)
            elif isinstance(item, str) and item.strip():
                names.append(item.strip())
        if names:
            patch["lora"] = names

    return patch


def import_image_metadata(path: str) -> dict[str, Any]:
    """End-to-end metadata import for studio bridge."""
    meta = extract_image_metadata(path)
    params = meta.get("parameters")
    if not isinstance(params, dict):
        return {
            "ok": False,
            "error": "no_generation_metadata",
            "file_path": path,
        }
    patch = settings_patch_from_metadata(params)
    if not patch:
        return {
            "ok": False,
            "error": "metadata_empty",
            "file_path": path,
        }
    return {
        "ok": True,
        "file_path": path,
        "patch": patch,
        "parameters": params,
    }
