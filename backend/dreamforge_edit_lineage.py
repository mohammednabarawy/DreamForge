"""Edit lineage metadata for manifests (plan hash, sources, masks, outputs)."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def compute_plan_hash(data: dict[str, Any] | None, job: Any) -> str | None:
    """Stable short hash for workflow / agent plans attached to a job."""
    payload: dict[str, Any] = {}
    if isinstance(data, dict):
        for key in (
            "workflow_plan",
            "execute_workflow_plan",
            "brain_plan",
            "agent_plan",
            "operations",
            "plan_id",
        ):
            value = data.get(key)
            if value:
                payload[key] = value
    for attr in ("workflow_plan", "agent_instruction", "execute_workflow_plan"):
        value = getattr(job, attr, None)
        if value is not None and value != "" and value is not False:
            payload.setdefault(attr, value)
    if not payload:
        return None
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_edit_lineage(
    *,
    job: Any,
    data: dict[str, Any] | None = None,
    input_image: str | None = None,
    upscale_image: str | None = None,
    background_reference_image: str | None = None,
    inpaint_mask: str | None = None,
    edit_type: str | None = None,
    output_images: list[str] | None = None,
    chain_steps: list[dict[str, Any]] | None = None,
    template_id: str | None = None,
    post_upscale: str | None = None,
) -> dict[str, Any]:
    workflow_plan = getattr(job, "workflow_plan", None)
    if not workflow_plan and isinstance(data, dict):
        workflow_plan = data.get("workflow_plan")
    sources = [path for path in (input_image, upscale_image) if path]
    if background_reference_image and background_reference_image not in sources:
        sources.append(background_reference_image)
    lineage: dict[str, Any] = {
        "plan_hash": compute_plan_hash(data, job),
        "edit_type": edit_type,
        "source_images": sources,
        "inpaint_mask": inpaint_mask,
        "workflow_plan": workflow_plan,
        "output_images": list(output_images or []),
    }
    if background_reference_image:
        lineage["background_reference_image"] = background_reference_image
    if template_id:
        lineage["template_id"] = template_id
    if post_upscale:
        lineage["post_upscale"] = post_upscale
    if chain_steps:
        lineage["chain_steps"] = chain_steps
    automation_id = getattr(job, "automation_id", None) or (data or {}).get("automation_id")
    if automation_id:
        lineage["automation"] = {
            "automation_id": automation_id,
            "type": getattr(job, "automation_type", None) or (data or {}).get("automation_type"),
            "index": getattr(job, "automation_index", None) or (data or {}).get("automation_index"),
            "total": getattr(job, "automation_total", None) or (data or {}).get("automation_total"),
        }
    return lineage
