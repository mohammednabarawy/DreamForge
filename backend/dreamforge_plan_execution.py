"""Convert brain / agent plans into DreamForgeEngine execution parameters."""

from __future__ import annotations

import json
import traceback
from copy import deepcopy
from typing import Any


def preset_hint_from_decision(decision: dict) -> str:
    """Format dynamic-preset metadata as markdown for plan preview UIs."""
    preset = decision.get("dynamic_preset") if isinstance(decision, dict) else None
    if not isinstance(preset, dict):
        return ""
    applied = preset.get("applied") if isinstance(preset.get("applied"), dict) else {}
    if not applied:
        return ""
    sources = preset.get("source") if isinstance(preset.get("source"), list) else []
    parts = [f"**{key}:** `{value}`" for key, value in applied.items()]
    hint = "Style preset hints: " + " · ".join(parts)
    if sources:
        hint += f" _(sources: {', '.join(str(s) for s in sources)})_"
    return hint


def request_agent_plan(instruction: str) -> tuple[str, str]:
    """Call DreamForgeEngine.plan and return JSON + preset hint (Gradio-free)."""
    if not instruction or not instruction.strip():
        empty = json.dumps({"status": "error", "message": "Please enter an instruction."}, indent=2)
        return empty, ""
    try:
        from dreamforge_engine import DreamForgeEngine

        decision = DreamForgeEngine.plan(instruction)
        return json.dumps(decision, indent=2, ensure_ascii=False), preset_hint_from_decision(decision)
    except Exception as exc:
        traceback.print_exc()
        return json.dumps({"status": "error", "message": str(exc)}, indent=2), ""


def normalize_brain_decision(decision: dict[str, Any]) -> dict[str, Any]:
    """Unwrap bridge envelopes and coerce to a brain decision dict."""
    if not isinstance(decision, dict):
        raise TypeError("decision must be a mapping")
    if isinstance(decision.get("decision"), dict):
        return dict(decision["decision"])
    return dict(decision)


def build_execution_params_from_brain_decision(
    decision: dict[str, Any],
    *,
    current_settings: dict[str, Any] | None = None,
    approved: bool = True,
) -> dict[str, Any]:
    """
    Merge a structured brain decision into engine-ready generation params.

    Returns a needs_approval payload when approval is required but not granted.
    """
    normalized = normalize_brain_decision(decision)
    if normalized.get("requires_approval") and not approved:
        return {
            "status": "needs_approval",
            "code": "plan_execution_requires_approval",
            "message": "Review the plan and approve execution before starting GPU work.",
            "operations": normalized.get("operations") or [],
            "local_only_image_backend": True,
        }

    base = deepcopy(current_settings or {})
    patch = normalized.get("patch") if isinstance(normalized.get("patch"), dict) else {}
    params = {**base, **patch}

    workflow_plan = normalized.get("workflow_plan")
    if isinstance(workflow_plan, list) and workflow_plan:
        params["workflow_plan"] = workflow_plan
        params["execute_workflow_plan"] = bool(
            normalized.get("execute_workflow_plan")
            or len(workflow_plan) > 1
        )

    params.setdefault("use_comfy_server", True)
    return params
