"""Execute multi-step workflow_plan chains by calling run_generation per step."""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any


def _prior_image_paths(result: dict) -> list[str]:
    paths: list[str] = []
    for item in result.get("images") or []:
        if isinstance(item, dict) and item.get("path"):
            paths.append(str(item["path"]))
        elif isinstance(item, str):
            paths.append(item)
    for path in result.get("output_paths") or []:
        if path and path not in paths:
            paths.append(str(path))
    return paths


def _step_operation(step: Any) -> str:
    if isinstance(step, dict):
        return str(step.get("operation") or "").strip()
    return str(getattr(step, "operation", "") or "").strip()


def _step_params(step: Any) -> dict:
    if isinstance(step, dict):
        params = step.get("params")
        return dict(params) if isinstance(params, dict) else {}
    params = getattr(step, "params", None)
    return dict(params) if isinstance(params, dict) else {}


def patch_for_step(step: Any, *, prior_paths: list[str]) -> dict[str, Any]:
    """Map a workflow step to generation data overrides."""
    op = _step_operation(step)
    patch = _step_params(step)
    patch["execute_workflow_plan"] = False
    patch["_executing_plan_step"] = True

    if prior_paths:
        patch.setdefault("input_image", prior_paths[0])

    if op == "generate_image":
        patch.pop("input_image", None)
        patch.pop("upscale_image", None)
        patch.pop("workflow_mode", None)
    elif op == "face_detail":
        patch["workflow_mode"] = "face_detail"
    elif op == "text_integrate":
        patch["workflow_mode"] = "arabic_text_composite"
        patch.setdefault("use_case", "arabic_poster")
    elif op == "reference_guidance":
        patch["workflow_mode"] = "ipadapter"
    elif op == "controlnet_structure":
        patch["workflow_mode"] = "controlnet"
    elif op == "hires_fix":
        patch["workflow_mode"] = "hires"
    elif op == "upscale":
        if prior_paths:
            patch["upscale_image"] = prior_paths[0]
        patch.pop("input_image", None)
        patch.setdefault("cn_selection", "Custom...")
        patch.setdefault("cn_type", "upscale")
    elif op in {"edit_image", "face_edit", "style_transfer", "restyle"}:
        patch.setdefault("cn_selection", "Custom...")
        patch.setdefault("cn_type", "img2img")

    return patch


def should_execute_workflow_plan(job: Any, data: dict | None) -> bool:
    if bool(getattr(job, "_executing_plan_step", False)):
        return False
    if bool((data or {}).get("_executing_plan_step")):
        return False
    if os.environ.get("DREAMFORGE_IN_ARABIC_PIPELINE"):
        return False
    plan = getattr(job, "workflow_plan", None) or (data or {}).get("workflow_plan")
    if not isinstance(plan, list) or len(plan) <= 1:
        return False
    execute = getattr(job, "execute_workflow_plan", None)
    if execute is None:
        execute = (data or {}).get("execute_workflow_plan")
    return bool(execute)


def execute_workflow_plan(
    *,
    base_args,
    data: dict | None,
    job,
    stream_sink=None,
    job_id: str | None = None,
) -> dict:
    from dreamforge_generation import emit_event, run_generation

    plan = getattr(job, "workflow_plan", None) or (data or {}).get("workflow_plan") or []
    if not isinstance(plan, list) or len(plan) <= 1:
        return {
            "status": "error",
            "type": "error",
            "code": "invalid_workflow_plan",
            "message": "workflow_plan must contain at least two steps",
            "job_id": job_id,
        }

    prior_paths: list[str] = []
    step_results: list[dict] = []
    merged_data = deepcopy(dict(data or {}))
    merged_data["execute_workflow_plan"] = False
    result: dict = {}

    for index, step in enumerate(plan, start=1):
        op = _step_operation(step)
        step_data = deepcopy(merged_data)
        step_data.update(patch_for_step(step, prior_paths=prior_paths))
        if stream_sink is not None:
            emit_event(
                stream_sink,
                {
                    "type": "progress",
                    "job_id": job_id,
                    "phase": "sampling",
                    "progress": int((index - 1) / len(plan) * 100),
                    "message": f"Workflow step {index}/{len(plan)}: {op or 'step'}…",
                },
            )
        result = run_generation(
            base_args,
            step_data,
            stream_sink=stream_sink,
            job_id=job_id,
        )
        step_results.append({"operation": op, "status": result.get("status"), "index": index})
        if result.get("status") != "success":
            result["workflow_plan_failed_at"] = index
            result["workflow_plan_steps"] = step_results
            return result
        prior_paths = _prior_image_paths(result)
        if not prior_paths:
            err = {
                "status": "error",
                "type": "error",
                "code": "workflow_plan_no_output",
                "message": f"Step {index} ({op}) produced no output image for the next step",
                "job_id": job_id,
                "workflow_plan_failed_at": index,
                "workflow_plan_steps": step_results,
            }
            emit_event(stream_sink, err)
            return err

    return {
        **result,
        "workflow_plan_steps": step_results,
        "output_paths": prior_paths,
    }
