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
            required = {"SaveImage"} & set(types)
            has_loader = bool(set(types) & {"CheckpointLoaderSimple", "UNETLoader", "UnetLoaderGGUF"})
            has_sampler = bool(set(types) & {"KSampler", "KSamplerAdvanced", "SamplerCustom"})
            if required and has_loader and has_sampler:
                state = "ADAPTABLE" if ui_format else "NATIVE"
                reason = "UI workflow requires conversion" if ui_format else "known native text/image graph semantics"
            else:
                state = "ADAPTABLE"
                reason = "known nodes need binding or graph normalization before execution"
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
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": True, "state": "INVALID", "format": "unknown", "source": str(file_path), "reason": f"workflow JSON is invalid: {exc}"}
    return analyze_workflow(payload, source=str(file_path))
