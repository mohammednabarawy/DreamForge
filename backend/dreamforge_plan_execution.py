"""Convert brain / agent plans into DreamForgeEngine execution parameters."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


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
