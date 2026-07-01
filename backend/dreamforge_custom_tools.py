"""Custom ComfyUI toolbox workflows (API-format only)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from dreamforge_comfy_workflow_import import (
    load_api_workflow_template,
    patch_node_field,
    workflow_class_types,
)


class CustomToolError(ValueError):
    """User-facing custom tool validation or binding failure."""


def find_custom_tool(tool_id: str) -> dict[str, Any] | None:
    from dreamforge_app_config import load_app_config

    target = str(tool_id or "").strip()
    if not target:
        return None
    cfg = load_app_config(redacted=False)
    for tool in cfg.get("custom_tools") or []:
        if isinstance(tool, dict) and str(tool.get("id") or "").strip() == target:
            return dict(tool)
    return None


def _upload_local_image(client, path: str) -> str:
    from dreamforge_paths import resolve_image_path_or_raise

    resolved = resolve_image_path_or_raise(str(path))
    local_name = Path(resolved).name
    upload = client.upload_image(
        image_bytes=Path(resolved).read_bytes(),
        filename=local_name,
        folder_type="input",
        overwrite=True,
    )
    return str(upload.get("name") or local_name)


def _sorted_bindings(tool: dict[str, Any], binding_type: str) -> list[tuple[str, dict[str, Any]]]:
    bindings = tool.get("bindings") if isinstance(tool.get("bindings"), dict) else {}
    items = [
        (str(key), dict(value))
        for key, value in bindings.items()
        if isinstance(value, dict) and str(value.get("type") or "") == binding_type
    ]
    return sorted(items, key=lambda item: item[0])


def apply_custom_tool_bindings(
    graph: dict[str, Any],
    tool: dict[str, Any],
    *,
    prompt: str,
    negative: str,
    seed: int,
    settings: dict[str, Any],
    uploaded_images: dict[str, str],
) -> dict[str, Any]:
    """Patch explicit node bindings from a saved custom tool definition."""
    out = copy.deepcopy(graph)
    text_bindings = _sorted_bindings(tool, "text")
    for index, (_key, binding) in enumerate(text_bindings):
        value = prompt if index == 0 else negative
        if len(text_bindings) == 1:
            value = prompt
        patch_node_field(out, binding["node_id"], binding["field"], str(value or ""))

    for key, binding in _sorted_bindings(tool, "image"):
        uploaded = uploaded_images.get(key)
        if uploaded:
            patch_node_field(out, binding["node_id"], binding["field"], uploaded)

    for key, binding in _sorted_bindings(tool, "mask"):
        uploaded = uploaded_images.get(key)
        if uploaded:
            patch_node_field(out, binding["node_id"], binding["field"], uploaded)

    for _key, binding in _sorted_bindings(tool, "number"):
        field = str(binding.get("field") or "").lower()
        node_id = str(binding.get("node_id") or "")
        input_field = str(binding.get("field") or "")
        if "seed" in field:
            patch_node_field(out, node_id, input_field, int(seed))
        elif field == "steps" or field.endswith("_steps"):
            patch_node_field(out, node_id, input_field, int(settings.get("steps") or 20))
        elif field == "cfg" or "cfg" in field:
            patch_node_field(
                out,
                node_id,
                input_field,
                float(settings.get("cfg") or settings.get("cfg_scale") or 7.0),
            )
        elif "denoise" in field:
            patch_node_field(
                out,
                node_id,
                input_field,
                float(settings.get("edit_strength") or settings.get("denoise") or 1.0),
            )

    prefix = str(settings.get("filename_prefix") or "DreamForge")
    for node_id, node in out.items():
        if isinstance(node, dict) and node.get("class_type") == "SaveImage":
            patch_node_field(out, node_id, "filename_prefix", prefix)
            break

    return out


def build_custom_tool_prompt_graph(
    *,
    client,
    job: Any,
    settings: dict[str, Any],
    prompt: str,
    negative: str,
    seed: int,
    input_path: str | None,
    extra_reference_paths: list[str] | None,
    mask_path: str | None,
) -> tuple[dict[str, Any], str]:
    """Load, bind, and return an API-format Comfy prompt graph for a custom tool."""
    tool_id = str(getattr(job, "custom_tool_id", None) or "").strip()
    tool = find_custom_tool(tool_id)
    if not tool:
        raise CustomToolError(f"Custom tool {tool_id!r} was not found in app config.")

    workflow_path = str(tool.get("workflow_path") or "").strip()
    if not workflow_path:
        raise CustomToolError(f"Custom tool {tool.get('name') or tool_id} has no workflow_path.")
    if not Path(workflow_path).is_file():
        raise CustomToolError(
            f"Workflow file not found for {tool.get('name') or tool_id}: {workflow_path}"
        )

    try:
        graph = load_api_workflow_template(workflow_path)
    except ValueError as exc:
        raise CustomToolError(
            f"{tool.get('name') or tool_id} requires ComfyUI Save (API Format) JSON. {exc}"
        ) from exc

    local_images: list[str] = []
    if input_path:
        local_images.append(str(input_path))
    for ref in extra_reference_paths or []:
        path = str(ref or "").strip()
        if path and path not in local_images:
            local_images.append(path)

    uploaded_images: dict[str, str] = {}
    image_bindings = _sorted_bindings(tool, "image")
    if image_bindings and not local_images:
        raise CustomToolError(
            f"{tool.get('name') or tool_id} needs at least one image binding input."
        )
    for index, (key, _binding) in enumerate(image_bindings):
        source = local_images[min(index, len(local_images) - 1)] if local_images else None
        if source:
            uploaded_images[key] = _upload_local_image(client, source)

    if mask_path:
        for key, _binding in _sorted_bindings(tool, "mask"):
            uploaded_images[key] = _upload_local_image(client, str(mask_path))

    patched = apply_custom_tool_bindings(
        graph,
        tool,
        prompt=prompt,
        negative=negative,
        seed=seed,
        settings=settings,
        uploaded_images=uploaded_images,
    )
    return patched, workflow_path


def custom_tool_preflight(tool: dict[str, Any], object_info: dict[str, Any]) -> list[str]:
    workflow_path = str(tool.get("workflow_path") or "").strip()
    if not workflow_path or not Path(workflow_path).is_file():
        return ["workflow_file_missing"]
    try:
        graph = load_api_workflow_template(workflow_path)
    except ValueError:
        return ["workflow_not_api_format"]
    return sorted(
        node for node in workflow_class_types(graph) if node not in (object_info or {})
    )


def custom_tool_dependency_entries(
    tool: dict[str, Any],
    object_info: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return installable companion rows for a custom tool's missing Comfy nodes."""
    missing_nodes = custom_tool_preflight(tool, object_info or {})
    if not missing_nodes:
        return []
    entries: list[dict[str, Any]] = []
    try:
        from dreamforge_workflow_planner import missing_custom_node_pack_entries, resolve_pack_id_for_nodes

        pack_id = resolve_pack_id_for_nodes(missing_nodes)
        if pack_id:
            entries.extend(
                missing_custom_node_pack_entries([pack_id], object_info=object_info)
            )
            return entries
    except Exception:
        pass
    entries.append(
        {
            "kind": "custom_node_pack",
            "pack_id": missing_nodes[0],
            "id": missing_nodes[0],
            "filename": missing_nodes[0],
            "relative": "engines/comfyui/custom_nodes",
            "category": "custom_nodes",
            "install_via": "manager",
            "missing_nodes": missing_nodes,
            "note": (
                "Search ComfyUI-Manager for a pack providing: "
                + ", ".join(missing_nodes)
            ),
        }
    )
    return entries
