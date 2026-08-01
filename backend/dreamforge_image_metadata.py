"""Read generation metadata embedded in PNG/WebP outputs."""

from __future__ import annotations

import json
import re
from typing import Any

_LORA_RE = re.compile(r"<lora:([^:>]+)(?::(-?\d+(?:\.\d+)?))?>", re.IGNORECASE)


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
    from PIL import ExifTags, Image

    with Image.open(path) as img:
        info: dict[str, Any] = {}
        for key, value in (img.info or {}).items():
            if isinstance(value, bytes):
                try:
                    value = value.decode("utf-8")
                except UnicodeDecodeError:
                    value = value.decode("utf-8", errors="replace")
            info[str(key)] = value
        for key, value in img.getexif().items():
            name = str(ExifTags.TAGS.get(key, key))
            if isinstance(value, bytes):
                payload = value[8:] if value.startswith(b"UNICODE\x00") else value
                try:
                    value = payload.decode("utf-16-le") if payload.startswith((b"\xff\xfe", b"\x00")) else payload.decode("utf-8")
                except UnicodeDecodeError:
                    value = payload.decode("utf-8", errors="replace")
            info[name] = value
        return info


def _parse_parameters_blob(blob: str) -> dict[str, Any] | None:
    text = (blob or "").strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                return None
            comfy = _parse_comfy_prompt(parsed)
            return comfy or parsed
        except json.JSONDecodeError:
            return None
    lines = text.splitlines()
    parameter_index = next((index for index in range(len(lines) - 1, -1, -1) if re.match(r"\s*Steps\s*:", lines[index], re.IGNORECASE)), -1)
    if parameter_index < 0:
        return None
    prompt_lines = lines[:parameter_index]
    negative_index = next((index for index, line in enumerate(prompt_lines) if line.lower().startswith("negative prompt:")), -1)
    if negative_index >= 0:
        prompt = "\n".join(prompt_lines[:negative_index]).strip()
        negative = "\n".join([prompt_lines[negative_index].split(":", 1)[1], *prompt_lines[negative_index + 1:]]).strip()
    else:
        prompt, negative = "\n".join(prompt_lines).strip(), ""
    values: dict[str, str] = {}
    for part in re.split(r",\s*(?=[A-Za-z][A-Za-z /_-]*:)", " ".join(lines[parameter_index:])):
        if ":" in part:
            key, value = part.split(":", 1)
            values[key.strip().lower()] = value.strip()
    out: dict[str, Any] = {"Prompt": prompt, "Negative": negative}
    mapping = {
        "steps": "steps", "sampler": "sampler_name", "cfg scale": "cfg", "seed": "seed",
        "model": "model", "clip skip": "clip_skip", "denoising strength": "denoise",
        "scheduler": "scheduler", "hires upscaler": "hires_upscaler", "hires upscale": "hires_upscale",
    }
    for source, destination in mapping.items():
        if source in values:
            out[destination] = values[source]
    sampler = str(out.get("sampler_name") or "")
    scheduler_match = re.search(r"\s+(Karras|Exponential|SGM Uniform|Normal|Simple|Beta)$", sampler, re.IGNORECASE)
    if scheduler_match:
        out["sampler_name"] = sampler[:scheduler_match.start()].strip()
        out["scheduler"] = scheduler_match.group(1).lower().replace(" ", "_")
    size = re.match(r"(\d+)\s*[x×]\s*(\d+)", values.get("size", ""))
    if size:
        out["width"], out["height"] = int(size.group(1)), int(size.group(2))
    loras = [{"filename": name, "weight": float(weight or 1)} for name, weight in _LORA_RE.findall(prompt)]
    if loras:
        out["loras"] = loras
    return out


def _node_id(value: Any) -> str:
    return str(value[0]) if isinstance(value, list) and value else ""


def _parse_comfy_prompt(graph: dict[str, Any]) -> dict[str, Any] | None:
    nodes = {str(key): value for key, value in graph.items() if isinstance(value, dict) and value.get("class_type")}
    if not nodes:
        return None
    sampler = next((node for node in nodes.values() if str(node.get("class_type", "")).lower() in {"ksampler", "ksampleradvanced"}), None)
    if not sampler:
        return None
    inputs = sampler.get("inputs") if isinstance(sampler.get("inputs"), dict) else {}
    out: dict[str, Any] = {}
    for source, destination in (("seed", "seed"), ("noise_seed", "seed"), ("steps", "steps"), ("cfg", "cfg"), ("sampler_name", "sampler_name"), ("scheduler", "scheduler"), ("denoise", "denoise")):
        value = inputs.get(source)
        if value is not None and not isinstance(value, list):
            out[destination] = value
    def text_from(ref: Any) -> str:
        node = nodes.get(_node_id(ref), {})
        node_inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
        return "\n".join(str(node_inputs[key]).strip() for key in ("text", "text_g", "text_l", "clip_l", "t5xxl") if isinstance(node_inputs.get(key), str) and node_inputs[key].strip())
    positive, negative = text_from(inputs.get("positive")), text_from(inputs.get("negative"))
    if positive:
        out["Prompt"] = positive
    if negative:
        out["Negative"] = negative
    for node in nodes.values():
        class_type = str(node.get("class_type", "")).lower()
        node_inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
        if "checkpointloader" in class_type and isinstance(node_inputs.get("ckpt_name"), str):
            out["model"] = node_inputs["ckpt_name"]
        if "emptylatentimage" in class_type or "emptysd3latentimage" in class_type:
            if not isinstance(node_inputs.get("width"), list):
                out["width"] = node_inputs.get("width")
            if not isinstance(node_inputs.get("height"), list):
                out["height"] = node_inputs.get("height")
    loras = []
    for node in nodes.values():
        class_type = str(node.get("class_type", "")).lower()
        node_inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
        if "loraloader" in class_type and isinstance(node_inputs.get("lora_name"), str):
            loras.append({"filename": node_inputs["lora_name"], "weight": _coerce_float(node_inputs.get("strength_model")) or 1.0})
    if loras:
        out["loras"] = loras
    return out or None


def extract_image_metadata(path: str) -> dict[str, Any]:
    """Return raw + parsed metadata for an image file."""
    info = _read_image_info(path)
    blob = info.get("parameters") or info.get("prompt") or info.get("UserComment") or ""
    if isinstance(blob, dict):
        parsed = _parse_comfy_prompt(blob)
    else:
        parsed = _parse_parameters_blob(str(blob).strip()) if blob else None
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
        ("scheduler", "scheduler"),
        ("width", "width"),
        ("height", "height"),
        ("denoise", "denoise"),
        ("clip_skip", "clip_skip"),
    ):
        if src in params and params[src] is not None:
            if dst in {"steps", "seed", "width", "height"}:
                val = _coerce_int(params[src])
            elif dst in {"cfg_scale", "denoise", "clip_skip"}:
                val = _coerce_float(params[src])
            else:
                val = str(params[src]).strip() or None
            if val is not None:
                patch[dst] = val

    if params.get("sampler_name"):
        from dreamforge_recipe import normalize_sampler

        sampler = normalize_sampler(str(params["sampler_name"]))
        if sampler:
            patch["sampler"] = sampler

    width = _coerce_int(params.get("width"))
    height = _coerce_int(params.get("height"))
    if width and height:
        patch["aspect_ratio"] = f"{width}x{height}"

    loras = params.get("loras")
    if isinstance(loras, list) and loras:
        names: list[str] = []
        for item in loras:
            if isinstance(item, dict) and item.get("filename"):
                name = str(item["filename"]).strip()
                weight = _coerce_float(item.get("weight"))
                names.append(f"{name}:{weight:g}" if weight is not None else name)
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
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
    from dreamforge_recipe import DreamForgeRecipe, LoRAComponent

    recipe_loras: list[LoRAComponent] = []
    for value in patch.get("lora", []):
        match = re.match(r"^(.*):(-?\d+(?:\.\d+)?)$", str(value))
        recipe_loras.append(LoRAComponent(filename=match.group(1) if match else str(value), weight=float(match.group(2)) if match else 1.0))
    recipe_settings = {key: value for key, value in patch.items() if key not in {"model", "prompt", "negative_prompt", "seed", "sampler", "cfg_scale", "steps", "aspect_ratio", "lora"}}
    raw = meta.get("raw") if isinstance(meta.get("raw"), dict) else {}
    for source, destination in (("prompt", "comfy_prompt"), ("workflow", "comfy_workflow")):
        value = raw.get(source)
        if value:
            if isinstance(value, str) and value.strip().startswith("{"):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            recipe_settings[destination] = value
    recipe = DreamForgeRecipe(
        model=str(patch.get("model") or ""),
        positive_prompt=str(patch.get("prompt") or ""),
        negative_prompt=str(patch.get("negative_prompt") or ""),
        seed=patch.get("seed") if isinstance(patch.get("seed"), int) else None,
        sampler=str(patch.get("sampler") or ""),
        cfg_scale=float(patch.get("cfg_scale") or 0),
        steps=int(patch.get("steps") or 0),
        aspect_ratio=str(patch.get("aspect_ratio") or ""),
        loras=recipe_loras,
        settings=recipe_settings,
        source="image_metadata",
    )
    return {
        "ok": True,
        "file_path": path,
        "patch": patch,
        "parameters": params,
        "recipe": recipe.to_dict(),
    }
