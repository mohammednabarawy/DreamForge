"""Conservative, non-executing workflow compatibility and security analysis."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from dreamforge_comfy_workflow_import import (
    is_ui_workflow_format,
    ui_active_node_count,
    workflow_class_types,
)

COMPATIBILITY_STATES = ("NATIVE", "ADAPTABLE", "COMFY_ONLY", "INVALID")
MAX_WORKFLOW_BYTES = 20 * 1024 * 1024

KNOWN_NODE_TYPES = {
    "CheckpointLoaderSimple", "UNETLoader", "UnetLoaderGGUF", "CLIPLoader", "CLIPLoaderGGUF",
    "VAELoader", "LoadImage", "LoadImageMask", "EmptyLatentImage", "EmptySD3LatentImage",
    "CLIPTextEncode", "TextEncodeQwenImageEdit", "KSampler", "KSamplerAdvanced", "SamplerCustom",
    "ModelSamplingAuraFlow", "CFGNorm", "LoraLoader", "LoraLoaderModelOnly", "ControlNetLoader",
    "ControlNetApply", "VAEEncode", "VAEEncodeForInpaint", "VAEDecode", "SaveImage",
    "ImageScale", "ImageUpscaleWithModel", "UpscaleModelLoader", "ImageCompositeMasked",
    "ImagePadForOutpaint", "EmptyImage", "ConditioningCombine", "ConditioningAverage",
    "FluxGuidance", "ReferenceLatent", "ApplyControlNet", "PreviewImage",
}

# Only this deliberately small subset can be losslessly recreated by the
# current Recipe v2 compiler. Known advanced nodes remain ADAPTABLE.
NATIVE_RECIPE_NODE_TYPES = {
    "CheckpointLoaderSimple", "UNETLoader", "UnetLoaderGGUF", "CLIPLoader",
    "CLIPLoaderGGUF", "VAELoader", "EmptyLatentImage", "EmptySD3LatentImage",
    "CLIPTextEncode", "KSampler", "LoraLoader", "LoraLoaderModelOnly",
    "VAEDecode", "SaveImage", "PreviewImage",
}

DEPENDENCY_FIELDS = re.compile(
    r"(checkpoint|ckpt|unet|diffusion|lora|vae|clip|text.?encoder|control.?net|upscale.?model|embedding)",
    re.IGNORECASE,
)
BLOCKED_CLASS = re.compile(r"(python|execute|shell|subprocess|command|eval|javascript|remote)", re.IGNORECASE)
BLOCKED_VALUE = re.compile(r"(?:https?://|\.\.(?:[\\/]|$)|\$\([^)]+\)|`[^`]+`)", re.IGNORECASE)


def _graph(payload: Mapping[str, Any]) -> dict[str, Any]:
    prompt = payload.get("prompt")
    if isinstance(prompt, dict):
        return prompt
    return dict(payload)


def _node_types(payload: Mapping[str, Any]) -> list[str]:
    if is_ui_workflow_format(payload):
        return sorted({
            str(node.get("type") or node.get("class_type") or "").strip()
            for node in payload.get("nodes") or []
            if isinstance(node, dict) and str(node.get("type") or node.get("class_type") or "").strip()
        })
    return workflow_class_types(_graph(payload))


def _walk_values(value: Any):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key), item
            yield from _walk_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_values(item)


def _dependencies(payload: Mapping[str, Any]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for key, value in _walk_values(_graph(payload)):
        if not DEPENDENCY_FIELDS.search(key) or not isinstance(value, str):
            continue
        item = value.strip()
        if item and item not in seen:
            seen.add(item)
            found.append(item)
    return found


def _security(payload: Mapping[str, Any], types: list[str]) -> dict[str, Any]:
    blocked_nodes = [node_type for node_type in types if BLOCKED_CLASS.search(node_type)]
    blocked_values: list[str] = []
    for _key, value in _walk_values(payload):
        if isinstance(value, str) and BLOCKED_VALUE.search(value):
            blocked_values.append(value[:160])
    reasons: list[str] = []
    if blocked_nodes:
        reasons.append(f"blocked execution node type: {blocked_nodes[0]}")
    if blocked_values:
        reasons.append("external command, URL, or path traversal value detected")
    return {
        "safe": not reasons,
        "blocked": bool(reasons),
        "reasons": reasons,
        "blocked_nodes": blocked_nodes,
        "blocked_values": blocked_values[:10],
    }


def _link(value: Any) -> str | None:
    if isinstance(value, list) and len(value) >= 2 and isinstance(value[0], (str, int)):
        return str(value[0])
    return None


def _native_recipe_shape(graph: Mapping[str, Any]) -> tuple[bool, str]:
    """Return whether the API graph is exactly the lossless Recipe v2 subset."""
    nodes = {str(key): value for key, value in graph.items() if isinstance(value, Mapping)}
    types = {str(node.get("class_type") or "") for node in nodes.values()}
    if not types or not types <= NATIVE_RECIPE_NODE_TYPES:
        return False, "known advanced nodes require an adapter"

    samplers = [key for key, node in nodes.items() if node.get("class_type") == "KSampler"]
    outputs = [key for key, node in nodes.items() if node.get("class_type") in {"SaveImage", "PreviewImage"}]
    if len(samplers) != 1 or not outputs:
        return False, "native recreation requires one sampler and an image output"
    sampler_id = samplers[0]
    sampler_inputs = nodes[sampler_id].get("inputs") or {}
    if not all(_link(sampler_inputs.get(name)) for name in ("model", "positive", "negative", "latent_image")):
        return False, "sampler inputs are not fully connected"
    if not all(sampler_inputs.get(name) not in (None, "") for name in ("steps", "cfg", "sampler_name", "scheduler")):
        return False, "sampler settings are incomplete"

    def node_type(node_id: str | None) -> str:
        return str((nodes.get(node_id or "") or {}).get("class_type") or "")

    def reaches(start: str | None, targets: set[str], seen: set[str] | None = None) -> bool:
        if not start or start not in nodes:
            return False
        if start in targets:
            return True
        seen = seen or set()
        if start in seen:
            return False
        seen.add(start)
        return any(reaches(_link(value), targets, seen) for value in (nodes[start].get("inputs") or {}).values())

    model_id = _link(sampler_inputs.get("model"))
    if not reaches(model_id, {key for key, node in nodes.items() if node.get("class_type") in {"CheckpointLoaderSimple", "UNETLoader", "UnetLoaderGGUF"}}):
        return False, "sampler model is not connected to a supported loader"
    if node_type(_link(sampler_inputs.get("positive"))) != "CLIPTextEncode" or node_type(_link(sampler_inputs.get("negative"))) != "CLIPTextEncode":
        return False, "positive and negative prompts must be directly encoded"
    if node_type(_link(sampler_inputs.get("latent_image"))) not in {"EmptyLatentImage", "EmptySD3LatentImage"}:
        return False, "sampler latent is not a supported empty latent"
    if not any(reaches(output, {sampler_id}) for output in outputs):
        return False, "image output is not connected to the sampler"

    reachable: set[str] = set()
    def collect(node_id: str) -> None:
        if node_id in reachable or node_id not in nodes:
            return
        reachable.add(node_id)
        for value in (nodes[node_id].get("inputs") or {}).values():
            linked = _link(value)
            if linked:
                collect(linked)
    for output in outputs:
        collect(output)
    if reachable != set(nodes):
        return False, "workflow contains disconnected or unused nodes"
    return True, "lossless native text-to-image recipe"


def analyze_workflow(payload: Mapping[str, Any], *, source: str = "") -> dict[str, Any]:
    if not isinstance(payload, Mapping) or not payload:
        return {"ok": True, "state": "INVALID", "format": "unknown", "reason": "workflow must be a non-empty object"}
    ui_format = is_ui_workflow_format(payload)
    graph = _graph(payload)
    types = _node_types(payload)
    security = _security(payload, types)
    dependencies = _dependencies(payload)
    if security["blocked"]:
        state = "INVALID"
        reason = "; ".join(security["reasons"])
    elif not types:
        state = "INVALID"
        reason = "workflow contains no executable nodes"
    else:
        unknown = [node_type for node_type in types if node_type not in KNOWN_NODE_TYPES]
        if unknown:
            state = "COMFY_ONLY"
            reason = f"unknown node semantics: {unknown[0]}"
        else:
            native, native_reason = _native_recipe_shape(graph) if not ui_format else (False, "UI workflow requires conversion")
            if native:
                state = "NATIVE"
                reason = native_reason
            else:
                state = "ADAPTABLE"
                reason = native_reason
    node_count = ui_active_node_count(payload) if ui_format else len(graph)
    return {
        "ok": True,
        "state": state,
        "format": "ui" if ui_format else "api",
        "source": source,
        "node_count": node_count,
        "class_types": types,
        "dependencies": dependencies,
        "security": security,
        "reason": reason,
        "can_execute": state == "NATIVE",
    }


def analyze_workflow_file(path: str | Path) -> dict[str, Any]:
    file_path = Path(path).expanduser().resolve()
    if not file_path.is_file():
        return {"ok": True, "state": "INVALID", "format": "unknown", "source": str(file_path), "reason": "workflow file not found"}
    try:
        if file_path.stat().st_size > MAX_WORKFLOW_BYTES:
            return {"ok": True, "state": "INVALID", "format": "unknown", "source": str(file_path), "reason": "workflow file is too large"}
        if file_path.suffix.lower() == ".png":
            from dreamforge_workflow_png import load_png_workflow

            payload = load_png_workflow(file_path)
        else:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": True, "state": "INVALID", "format": "unknown", "source": str(file_path), "reason": f"workflow JSON is invalid: {exc}"}
    return analyze_workflow(payload, source=str(file_path))
