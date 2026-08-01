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


def _link(value: Any) -> str | None:
    return str(value[0]) if isinstance(value, list) and len(value) >= 2 and isinstance(value[0], (str, int)) else None


def compile_workflow_recipe(payload: Mapping[str, Any], *, source: str = "") -> dict[str, Any]:
    report = analyze_workflow(payload, source=source)
    if report.get("state") != "NATIVE":
        return {"ok": True, "report": report, "can_recreate": False, "missing": ["native workflow semantics"]}
    graph = {str(key): value for key, value in _graph(payload).items() if isinstance(value, Mapping)}
    sampler = next(node for node in graph.values() if node.get("class_type") == "KSampler")
    sampler_inputs = sampler.get("inputs") or {}
    node = lambda value: graph.get(_link(value) or "", {})
    positive = str((node(sampler_inputs.get("positive")).get("inputs") or {}).get("text") or "").strip()
    negative = str((node(sampler_inputs.get("negative")).get("inputs") or {}).get("text") or "").strip()
    latent_inputs = node(sampler_inputs.get("latent_image")).get("inputs") or {}
    width, height = latent_inputs.get("width"), latent_inputs.get("height")

    loras: list[LoRAComponent] = []
    model_node = node(sampler_inputs.get("model"))
    while model_node.get("class_type") in {"LoraLoader", "LoraLoaderModelOnly"}:
        inputs = model_node.get("inputs") or {}
        weight = inputs.get("strength_model")
        loras.append(LoRAComponent(filename=str(inputs.get("lora_name") or ""), weight=float(1 if weight is None else weight)))
        model_node = node(inputs.get("model"))
    loader_inputs = model_node.get("inputs") or {}
    model = loader_inputs.get("ckpt_name") or loader_inputs.get("unet_name") or ""
    missing: list[str] = []
    if not model:
        missing.append("model")
    if not positive:
        missing.append("positive_prompt")
    if not sampler_inputs.get("sampler_name"):
        missing.append("sampler")
    if not sampler_inputs.get("scheduler"):
        missing.append("scheduler")
    if not isinstance(sampler_inputs.get("cfg"), (int, float)) or float(sampler_inputs.get("cfg") or 0) <= 0:
        missing.append("cfg_scale")
    if not isinstance(sampler_inputs.get("steps"), (int, float)) or int(sampler_inputs.get("steps") or 0) <= 0:
        missing.append("steps")
    if not isinstance(width, (int, float)) or not isinstance(height, (int, float)) or width <= 0 or height <= 0:
        missing.append("aspect_ratio")
    recipe = DreamForgeRecipe(
        model=str(model),
        positive_prompt=positive,
        negative_prompt=negative,
        seed=int(sampler_inputs["seed"]) if isinstance(sampler_inputs.get("seed"), (int, float)) else None,
        sampler=str(sampler_inputs.get("sampler_name") or ""),
        cfg_scale=float(sampler_inputs.get("cfg") or 0),
        steps=int(sampler_inputs.get("steps") or 0),
        aspect_ratio=f"{width}x{height}" if width and height else "",
        loras=[item for item in reversed(loras) if item.filename],
        source="comfy_workflow",
        source_url=source,
        provenance=Provenance(provider="local", source_url=source),
        settings={
            "width": int(width),
            "height": int(height),
            "scheduler": str(sampler_inputs.get("scheduler") or ""),
        } if isinstance(width, (int, float)) and isinstance(height, (int, float)) and width > 0 and height > 0 else {},
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
        if file_path.suffix.lower() == ".png":
            from dreamforge_workflow_png import load_png_workflow

            payload = load_png_workflow(file_path)
        else:
            payload = load_api_workflow_template(file_path)
    except (OSError, ValueError) as exc:
        return {"ok": True, "report": report, "can_recreate": False, "missing": [str(exc)]}
    return compile_workflow_recipe(payload, source=str(file_path))
