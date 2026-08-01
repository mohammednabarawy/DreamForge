"""High-confidence workflow-to-recipe compilation; never executes a graph."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

from dreamforge_assets import Provenance
from dreamforge_recipe import DreamForgeRecipe, LoRAComponent
from dreamforge_workflow_compatibility import analyze_workflow, analyze_workflow_file
from dreamforge_comfy_workflow_import import load_api_workflow_template


def _graph(payload: Mapping[str, Any]) -> dict[str, Any]:
    root = payload.get("prompt")
    return copy.deepcopy(root if isinstance(root, dict) else payload)


def _nodes(graph: Mapping[str, Any], class_type: str) -> list[dict[str, Any]]:
    return [
        node for node in graph.values()
        if isinstance(node, Mapping) and node.get("class_type") == class_type
    ]


def _first_input(nodes: list[dict[str, Any]], name: str) -> Any:
    for node in nodes:
        value = (node.get("inputs") or {}).get(name)
        if value not in (None, "") and not isinstance(value, list):
            return value
    return None


def _text_prompts(graph: Mapping[str, Any]) -> tuple[str, str]:
    positive = negative = ""
    for node in _nodes(graph, "CLIPTextEncode") + _nodes(graph, "TextEncodeQwenImageEdit"):
        inputs = node.get("inputs") or {}
        text = inputs.get("text") or inputs.get("prompt")
        if not isinstance(text, str) or not text.strip():
            continue
        meta = node.get("_meta") if isinstance(node.get("_meta"), Mapping) else {}
        label = str(meta.get("title") or meta.get("name") or "").lower()
        if "negative" in label and not negative:
            negative = text.strip()
        elif not positive:
            positive = text.strip()
        elif not negative:
            negative = text.strip()
    return positive, negative


def compile_workflow_recipe(payload: Mapping[str, Any], *, source: str = "") -> dict[str, Any]:
    report = analyze_workflow(payload, source=source)
    if report.get("state") != "NATIVE":
        return {"ok": True, "report": report, "can_recreate": False, "missing": ["native workflow semantics"]}
    graph = _graph(payload)
    positive, negative = _text_prompts(graph)
    loaders = _nodes(graph, "CheckpointLoaderSimple") + _nodes(graph, "UNETLoader") + _nodes(graph, "UnetLoaderGGUF")
    samplers = _nodes(graph, "KSampler") + _nodes(graph, "KSamplerAdvanced")
    latent = _nodes(graph, "EmptyLatentImage") + _nodes(graph, "EmptySD3LatentImage")
    sampler = samplers[0] if samplers else {}
    sampler_inputs = sampler.get("inputs") or {}
    model = _first_input(loaders, "ckpt_name") or _first_input(loaders, "unet_name") or ""
    width = _first_input(latent, "width")
    height = _first_input(latent, "height")
    missing: list[str] = []
    if not model:
        missing.append("model")
    if not positive:
        missing.append("positive_prompt")
    recipe = DreamForgeRecipe(
        model=str(model),
        positive_prompt=positive,
        negative_prompt=negative,
        seed=int(sampler_inputs["seed"]) if isinstance(sampler_inputs.get("seed"), (int, float)) else None,
        sampler=str(sampler_inputs.get("sampler_name") or ""),
        cfg_scale=float(sampler_inputs.get("cfg") or 0),
        steps=int(sampler_inputs.get("steps") or 0),
        aspect_ratio=f"{width}x{height}" if width and height else "",
        loras=[
            LoRAComponent(
                filename=str((node.get("inputs") or {}).get("lora_name") or ""),
                weight=float((node.get("inputs") or {}).get("strength_model") or 1),
            )
            for node in _nodes(graph, "LoraLoader") + _nodes(graph, "LoraLoaderModelOnly")
            if (node.get("inputs") or {}).get("lora_name")
        ],
        source="comfy_workflow",
        source_url=source,
        provenance=Provenance(provider="local", source_url=source),
    )
    return {
        "ok": True,
        "report": report,
        "can_recreate": not missing,
        "missing": missing,
        "recipe": recipe.to_dict(),
    }


def compile_workflow_file(path: str | Path) -> dict[str, Any]:
    file_path = Path(path).expanduser().resolve()
    report = analyze_workflow_file(file_path)
    if report.get("state") == "INVALID":
        return {"ok": True, "report": report, "can_recreate": False, "missing": [report.get("reason", "invalid workflow")]}
    try:
        payload = load_api_workflow_template(file_path)
    except (OSError, ValueError) as exc:
        return {"ok": True, "report": report, "can_recreate": False, "missing": [str(exc)]}
    return compile_workflow_recipe(payload, source=str(file_path))
