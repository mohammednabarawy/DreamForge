"""Deterministic, execution-safe intermediate representation for native workflows."""

from __future__ import annotations

from typing import Any, Mapping

from dreamforge_workflow_compiler import compile_workflow_recipe
from dreamforge_workflow_compatibility import analyze_workflow

WORKFLOW_IR_VERSION = "1.0"


def compile_workflow_ir(payload: Mapping[str, Any], *, source: str = "") -> dict[str, Any]:
    report = analyze_workflow(payload, source=source)
    if report.get("state") != "NATIVE":
        return {
            "ok": True,
            "version": WORKFLOW_IR_VERSION,
            "can_execute": False,
            "report": report,
            "missing": ["native workflow semantics"],
        }
    compiled = compile_workflow_recipe(payload, source=source)
    if not compiled.get("can_recreate"):
        return {
            "ok": True,
            "version": WORKFLOW_IR_VERSION,
            "can_execute": False,
            "report": report,
            "missing": compiled.get("missing") or ["portable recipe fields"],
        }
    graph = payload.get("prompt") if isinstance(payload.get("prompt"), dict) else payload
    node_types = sorted(
        str(node.get("class_type") or "")
        for node in graph.values()
        if isinstance(node, Mapping) and node.get("class_type")
    )
    return {
        "ok": True,
        "version": WORKFLOW_IR_VERSION,
        "can_execute": True,
        "kind": "native_recipe",
        "source": source,
        "nodes": node_types,
        "dependencies": report.get("dependencies", []),
        "recipe": compiled["recipe"],
        "report": report,
    }


def compile_workflow_ir_file(path: str) -> dict[str, Any]:
    from dreamforge_workflow_compatibility import analyze_workflow_file
    from dreamforge_comfy_workflow_import import load_api_workflow_template

    report = analyze_workflow_file(path)
    if report.get("state") == "INVALID":
        return {"ok": True, "version": WORKFLOW_IR_VERSION, "can_execute": False, "report": report, "missing": [report.get("reason", "invalid workflow")]}
    try:
        if str(path).lower().endswith(".png"):
            from dreamforge_workflow_png import load_png_workflow

            payload = load_png_workflow(path)
        else:
            payload = load_api_workflow_template(path)
    except (OSError, ValueError) as exc:
        return {"ok": True, "version": WORKFLOW_IR_VERSION, "can_execute": False, "report": report, "missing": [str(exc)]}
    return compile_workflow_ir(payload, source=report.get("source", str(path)))
