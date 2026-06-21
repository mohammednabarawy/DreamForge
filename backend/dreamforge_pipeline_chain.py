"""Optional post-generation upscale chain."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from dreamforge_upscale_defaults import upscale_field_defaults


def post_upscale_method_from_job(job: Any, data: dict | None) -> str | None:
    if bool(getattr(job, "_post_upscale_executing", False)):
        return None
    if bool((data or {}).get("_post_upscale_executing")):
        return None
    method = getattr(job, "post_upscale", None) or (data or {}).get("post_upscale")
    if method is True:
        return "ultimate_sd_upscale"
    if method:
        text = str(method).strip()
        return text or None
    return None


def should_run_post_upscale(
    job: Any,
    data: dict | None,
    *,
    primary_result: dict | None = None,
) -> bool:
    if primary_result and primary_result.get("status") != "success":
        return False
    method = post_upscale_method_from_job(job, data)
    if not method:
        return False
    cn_type = str(getattr(job, "cn_type", None) or (data or {}).get("cn_type") or "").lower()
    if cn_type == "upscale":
        return False
    return True


def first_image_path(result: dict) -> str | None:
    for item in result.get("images") or []:
        if isinstance(item, dict) and item.get("path"):
            return str(item["path"])
        if isinstance(item, str) and item.strip():
            return item.strip()
    for path in result.get("output_paths") or []:
        if path:
            return str(path)
    return None


def run_post_upscale_chain(
    primary_result: dict,
    *,
    base_args,
    data: dict | None,
    stream_sink=None,
    job_id: str | None = None,
) -> dict:
    """Run upscale stage after a successful primary generation."""
    from dreamforge_generation import emit_event, run_generation

    method = post_upscale_method_from_job(
        type("Job", (), dict(data or {}))(),
        data,
    )
    if not method:
        return primary_result

    source_path = first_image_path(primary_result)
    if not source_path:
        return primary_result

    if stream_sink is not None:
        emit_event(
            stream_sink,
            {
                "type": "progress",
                "job_id": job_id,
                "phase": "post_upscale",
                "progress": 95,
                "message": f"Running Ultimate SD Upscale ({method})...",
            },
        )

    chain_data = deepcopy(dict(data or {}))
    chain_data["_post_upscale_executing"] = True
    chain_data["post_upscale"] = None
    chain_data["post_upscale_enabled"] = False
    chain_data["input_image"] = None
    chain_data["inpaint_mask_path"] = None
    chain_data["upscale_image"] = source_path
    chain_data["upscale_method"] = method
    chain_data["cn_selection"] = "Custom..."
    chain_data["cn_type"] = "upscale"
    chain_data["edit_type"] = "auto"
    chain_data["image_number"] = 1
    for field, default in upscale_field_defaults(data or {}).items():
        if not field.startswith("upscale_"):
            continue
        if chain_data.get(field) is None:
            source = (data or {}).get(field)
            chain_data[field] = source if source is not None else default
    chain_data.pop("template_id", None)

    upscale_result = run_generation(
        base_args,
        chain_data,
        stream_sink=stream_sink,
        job_id=job_id,
    )
    if upscale_result.get("status") != "success":
        primary_result["post_upscale_error"] = upscale_result
        primary_result["chain_partial"] = True
        return primary_result

    final_path = first_image_path(upscale_result)
    merged = dict(primary_result)
    if final_path:
        merged["images"] = [{"path": final_path}]
        merged["output_paths"] = [final_path]
    merged["manifest"] = upscale_result.get("manifest") or primary_result.get("manifest")
    merged["post_upscale"] = method
    merged["chain_steps"] = [
        {
            "operation": "primary",
            "output": source_path,
            "manifest": primary_result.get("manifest"),
        },
        {
            "operation": "upscale",
            "output": final_path,
            "manifest": upscale_result.get("manifest"),
            "upscale_method": method,
        },
    ]
    return merged
