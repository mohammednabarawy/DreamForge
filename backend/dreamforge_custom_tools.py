"""Custom ComfyUI toolbox workflows (UI or API-format JSON)."""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

from dreamforge_comfy_workflow_import import (
    load_api_workflow_template,
    patch_node_field,
    workflow_class_types,
)


class CustomToolError(ValueError):
    """User-facing custom tool validation or binding failure."""


logger = logging.getLogger(__name__)


# Loader nodes -> list of (input field, preferred models subfolders).
WORKFLOW_LOADER_SPECS: dict[str, list[tuple[str, tuple[str, ...]]]] = {
    "CheckpointLoaderSimple": [("ckpt_name", ("checkpoints",))],
    "UNETLoader": [("unet_name", ("diffusion_models", "unet"))],
    "UnetLoaderGGUF": [("unet_name", ("diffusion_models", "unet"))],
    "CLIPLoader": [("clip_name", ("text_encoders", "clip"))],
    "CLIPLoaderGGUF": [("clip_name", ("text_encoders", "clip"))],
    "DualCLIPLoader": [
        ("clip_name1", ("text_encoders", "clip")),
        ("clip_name2", ("text_encoders", "clip")),
    ],
    "VAELoader": [("vae_name", ("vae",))],
    "ControlNetLoader": [("control_net_name", ("controlnet",))],
    "LoraLoader": [("lora_name", ("loras",))],
    "LoraLoaderModelOnly": [("lora_name", ("loras",))],
    "UpscaleModelLoader": [("model_name", ("upscale_models",))],
}

WORKFLOW_MODEL_DEFAULT = "__workflow_default__"

# Folders scanned for the custom-tool workflow model picker (includes encoders/VAE, not just checkpoints).
WORKFLOW_LOADER_GALLERY_CATEGORIES = (
    "checkpoints",
    "diffusion_models",
    "unet",
    "text_encoders",
    "clip",
    "vae",
    "loras",
    "controlnet",
    "upscale_models",
)

# Known workflow weight filenames -> companion catalog id (when downloadable).
_FILENAME_COMPANION_IDS: dict[str, str] = {
    "flux2-vae.safetensors": "vae_flux2",
    "ae.safetensors": "vae_flux_ae",
}

HF_FLUX2_KLEIN_9B = "https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main"
HF_BFL_KLEIN_9B = "https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8/resolve/main"

# Common graph weights with direct download mirrors for DreamForge companion fetch.
KNOWN_GRAPH_MODELS: dict[str, dict[str, Any]] = {
    "flux-2-klein-9b-fp8.safetensors": {
        "relative": "diffusion_models/flux-2-klein-9b-fp8.safetensors",
        "url": f"{HF_BFL_KLEIN_9B}/flux-2-klein-9b-fp8.safetensors",
        "min_bytes": 8 * 1024 * 1024 * 1024,
        "requires_hf_token": True,
        "note": "FLUX.2 Klein 9B FP8 diffusion model (accepts kv/base variants already on disk).",
        "accept_filenames": [
            "flux-2-klein-9b-fp8.safetensors",
            "flux-2-klein-9b-kv-fp8.safetensors",
            "flux-2-klein-base-9b-fp8.safetensors",
        ],
    },
    "qwen_3_8b_fp8mixed.safetensors": {
        "relative": "text_encoders/qwen_3_8b_fp8mixed.safetensors",
        "url": f"{HF_FLUX2_KLEIN_9B}/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors",
        "min_bytes": 4 * 1024 * 1024 * 1024,
        "note": "Qwen 3 8B text encoder for FLUX.2 Klein (CLIP type flux2).",
        "accept_filenames": [
            "qwen_3_8b_fp8mixed.safetensors",
            "qwen_3_8b_fp4mixed.safetensors",
            "qwen_3_8b.safetensors",
            "qwen3vl_8b_fp8_scaled.safetensors",
        ],
    },
    "flux2-vae.safetensors": {
        "companion_id": "vae_flux2",
        "relative": "vae/flux2-vae.safetensors",
        "min_bytes": 300 * 1024 * 1024,
        "note": "Flux 2 VAE used by Klein and Ideogram workflows.",
    },
    "gemma4_e4b_it_fp8_scaled.safetensors": {
        "relative": "text_encoders/gemma4_e4b_it_fp8_scaled.safetensors",
        "url": f"{HF_FLUX2_KLEIN_9B}/split_files/text_encoders/gemma4_e4b_it_fp8_scaled.safetensors",
        "min_bytes": 2 * 1024 * 1024 * 1024,
        "note": "Gemma text encoder for TextGenerate nodes in FLUX.2 workflows.",
    },
}


def _graph_model_candidate_filenames(filename: str) -> list[str]:
    known = KNOWN_GRAPH_MODELS.get(filename, {})
    names = [str(name).strip() for name in (known.get("accept_filenames") or []) if str(name).strip()]
    if filename not in names:
        names.insert(0, filename)
    return names


def _model_file_matches_candidates(
    folder: Path,
    candidates: list[str],
    *,
    min_bytes: int,
) -> bool:
    if not folder.is_dir():
        return False
    for name in candidates:
        direct = folder / name
        if direct.is_file() and direct.stat().st_size >= min_bytes:
            return True
    lowered = {name.lower() for name in candidates}
    try:
        for path in folder.rglob("*.safetensors"):
            if not path.is_file() or path.stat().st_size < min_bytes:
                continue
            if path.name.lower() in lowered:
                return True
    except OSError:
        return False
    return False


def workflow_model_ref_key(node_id: str, field: str) -> str:
    return f"{node_id}:{field}"


def tool_model_overrides(tool: dict[str, Any] | None) -> dict[str, str]:
    """User-selected model filenames keyed by node_id:field (empty means workflow default)."""
    if not tool:
        return {}
    raw = tool.get("model_overrides")
    if not isinstance(raw, dict):
        return {}
    resolved: dict[str, str] = {}
    for key, value in raw.items():
        ref_key = str(key or "").strip()
        if not ref_key:
            continue
        selected = str(value or "").strip()
        if not selected or selected == WORKFLOW_MODEL_DEFAULT:
            continue
        resolved[ref_key] = selected
    return resolved


def effective_workflow_model_filename(
    ref: dict[str, str],
    overrides: dict[str, str],
) -> str:
    key = workflow_model_ref_key(str(ref.get("node_id") or ""), str(ref.get("field") or ""))
    override = overrides.get(key, "").strip()
    if override:
        return override
    return str(ref.get("filename") or "").strip()


def apply_custom_tool_model_overrides(
    graph: dict[str, Any],
    tool: dict[str, Any],
) -> dict[str, Any]:
    """Patch loader nodes with user-selected library models."""
    overrides = tool_model_overrides(tool)
    if not overrides:
        return graph
    out = copy.deepcopy(graph)
    for ref in extract_workflow_model_refs(out):
        key = workflow_model_ref_key(str(ref["node_id"]), str(ref["field"]))
        selected = overrides.get(key)
        if selected:
            patch_node_field(out, str(ref["node_id"]), str(ref["field"]), selected)
    return out


def build_workflow_loader_library() -> list[dict[str, Any]]:
    """List on-disk weights from loader-relevant models folders for override comboboxes."""
    from modules.model_ui_defaults import gallery_caption, scan_model_category

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for category in WORKFLOW_LOADER_GALLERY_CATEGORIES:
        for relative_name in scan_model_category(category):
            filename = Path(relative_name).name
            key = f"{category}:{relative_name}"
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "category": category,
                    "relative_path": relative_name,
                    "filename": filename,
                    "caption": gallery_caption(category, relative_name),
                }
            )
    return items


def library_options_for_workflow_ref(
    ref: dict[str, str],
    library: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Filter workflow loader library rows to folders accepted by a loader node."""
    rows = library if library is not None else build_workflow_loader_library()
    folders = {
        item.strip()
        for item in str(ref.get("search_folders") or ref.get("folders") or "").split(",")
        if item.strip()
    }
    if not folders:
        return list(rows)
    return [item for item in rows if str(item.get("category") or "") in folders]


def list_custom_tool_workflow_models(tool: dict[str, Any]) -> list[dict[str, Any]]:
    """Describe each workflow loader slot and the user's override selection."""
    graph = _load_custom_tool_graph(tool)
    if graph is None:
        return []
    raw_overrides = tool.get("model_overrides")
    raw_overrides = raw_overrides if isinstance(raw_overrides, dict) else {}
    overrides = tool_model_overrides(tool)
    library = build_workflow_loader_library()
    slots: list[dict[str, Any]] = []
    for ref in extract_workflow_model_refs(graph):
        key = workflow_model_ref_key(str(ref["node_id"]), str(ref["field"]))
        selection = str(raw_overrides.get(key) or WORKFLOW_MODEL_DEFAULT).strip()
        if not selection:
            selection = WORKFLOW_MODEL_DEFAULT
        effective = effective_workflow_model_filename(ref, overrides)
        slots.append(
            {
                **ref,
                "ref_key": key,
                "workflow_filename": ref["filename"],
                "selection": selection,
                "effective_filename": effective,
                "uses_workflow_default": selection == WORKFLOW_MODEL_DEFAULT,
                "library_options": library_options_for_workflow_ref(ref, library),
            }
        )
    return slots


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
            f"{tool.get('name') or tool_id} workflow could not be loaded. {exc}"
        ) from exc

    graph = apply_custom_tool_model_overrides(graph, tool)

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


def custom_tool_preflight(
    tool: dict[str, Any],
    object_info: dict[str, Any] | None,
) -> list[str]:
    workflow_path = str(tool.get("workflow_path") or "").strip()
    if not workflow_path or not Path(workflow_path).is_file():
        return ["workflow_file_missing"]
    graph = _load_custom_tool_graph(tool)
    if graph is None:
        return []
    if object_info is None:
        return []
    return sorted(
        node for node in workflow_class_types(graph) if node not in object_info
    )


def extract_workflow_model_refs(graph: dict[str, Any]) -> list[dict[str, str]]:
    """Collect weight filenames referenced by loader nodes in an API workflow graph."""
    refs: list[dict[str, str]] = []
    seen: set[str] = set()
    for node_id, node in graph.items():
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type") or "").strip()
        specs = WORKFLOW_LOADER_SPECS.get(class_type)
        if not specs:
            continue
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        for field, folders in specs:
            value = inputs.get(field)
            if not isinstance(value, str):
                continue
            filename = value.strip()
            if not filename or filename.startswith("["):
                continue
            key = f"{node_id}:{field}:{filename}"
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                {
                    "filename": filename,
                    "class_type": class_type,
                    "node_id": str(node_id),
                    "field": field,
                    "folders": folders[0],
                    "search_folders": ",".join(folders),
                }
            )
    return refs


def workflow_graph_model_file_present(
    filename: str,
    *,
    folders: tuple[str, ...] | None = None,
    min_bytes: int = 1024 * 1024,
) -> bool:
    """True when a workflow-referenced weight exists under MODELS_ROOT."""
    from dreamforge_cli_inventory import companion_file_present

    companion_id = (
        _FILENAME_COMPANION_IDS.get(filename)
        or str(KNOWN_GRAPH_MODELS.get(filename, {}).get("companion_id") or "").strip()
        or None
    )
    if companion_id:
        relative = str(
            KNOWN_GRAPH_MODELS.get(filename, {}).get("relative")
            or f"vae/{filename}"
        )
        if companion_file_present(
            {"id": companion_id, "relative": relative},
            min_bytes=min_bytes,
        ):
            return True

    try:
        from _paths import MODELS_ROOT
    except ImportError:
        return False

    search = folders or tuple(
        folder
        for specs in WORKFLOW_LOADER_SPECS.values()
        for _field, spec_folders in specs
        for folder in spec_folders
    )
    candidates = _graph_model_candidate_filenames(filename)
    for folder in search:
        root = MODELS_ROOT / folder
        if _model_file_matches_candidates(root, candidates, min_bytes=min_bytes):
            return True
    # Klein UNet is often stored under diffusion_models even when the workflow filename differs.
    if "klein" in filename.lower() and "9b" in filename.lower():
        klein_root = MODELS_ROOT / "diffusion_models"
        if _model_file_matches_candidates(
            klein_root,
            [
                "flux-2-klein-9b-fp8.safetensors",
                "flux-2-klein-9b-kv-fp8.safetensors",
                "flux-2-klein-base-9b-fp8.safetensors",
            ],
            min_bytes=min_bytes,
        ):
            return True
    if "qwen" in filename.lower() and "8b" in filename.lower():
        for folder in ("text_encoders", "clip"):
            root = MODELS_ROOT / folder
            if not root.is_dir():
                continue
            try:
                for path in root.rglob("*.safetensors"):
                    if not path.is_file() or path.stat().st_size < min_bytes:
                        continue
                    name = path.name.lower()
                    if "qwen" in name and "8b" in name:
                        return True
            except OSError:
                continue
    return False


def missing_workflow_graph_model_entries(
    graph: dict[str, Any],
    *,
    tool: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return installable rows for model files referenced by a workflow graph."""
    from dreamforge_companion_download import enrich_missing_dependency

    overrides = tool_model_overrides(tool)
    missing: list[dict[str, Any]] = []
    for ref in extract_workflow_model_refs(graph):
        workflow_filename = str(ref["filename"])
        effective = effective_workflow_model_filename(ref, overrides)
        uses_default = effective == workflow_filename
        folders = tuple(
            item.strip()
            for item in str(ref.get("search_folders") or ref.get("folders") or "").split(",")
            if item.strip()
        )
        known = (
            KNOWN_GRAPH_MODELS.get(workflow_filename, {})
            if uses_default
            else KNOWN_GRAPH_MODELS.get(effective, {})
        )
        min_bytes = int(known.get("min_bytes") or 1024 * 1024)
        if workflow_graph_model_file_present(
            effective,
            folders=folders,
            min_bytes=min_bytes,
        ):
            continue
        companion_id = (
            _FILENAME_COMPANION_IDS.get(effective)
            or _FILENAME_COMPANION_IDS.get(workflow_filename)
            or str(known.get("companion_id") or "").strip()
            or None
        )
        relative = str(
            known.get("relative")
            or f"{ref.get('folders')}/{effective}"
        )
        row: dict[str, Any] = {
            "kind": "model_companion",
            "id": companion_id or f"graph_model:{effective}",
            "filename": effective,
            "relative": relative,
            "category": relative.split("/", 1)[0] if "/" in relative else "models",
            "install_via": "direct" if known.get("url") or companion_id else "manager",
            "note": str(
                known.get("note")
                or (
                    f"Workflow requires {workflow_filename}"
                    if uses_default
                    else f"Selected model {effective} for {ref.get('class_type')}"
                )
            ),
            "workflow_ref": True,
            "workflow_node_id": ref.get("node_id"),
            "workflow_class_type": ref.get("class_type"),
            "workflow_model_field": ref.get("field"),
            "workflow_default_filename": workflow_filename,
            "uses_workflow_default": uses_default,
        }
        if known.get("url") and uses_default:
            row["url"] = known["url"]
            row["min_bytes"] = min_bytes
        elif known.get("url") and effective in KNOWN_GRAPH_MODELS:
            row["url"] = known["url"]
            row["min_bytes"] = min_bytes
        if known.get("requires_hf_token"):
            row["requires_hf_token"] = True
        missing.append(enrich_missing_dependency(row))
    return missing


def _load_custom_tool_graph(tool: dict[str, Any]) -> dict[str, Any] | None:
    from dreamforge_comfy_workflow_import import (
        is_ui_workflow_format,
        pseudo_graph_from_ui_data,
        ui_active_node_count,
    )

    workflow_path = str(tool.get("workflow_path") or "").strip()
    if not workflow_path or not Path(workflow_path).is_file():
        return None

    try:
        data = json.loads(Path(workflow_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if is_ui_workflow_format(data):
        pseudo = pseudo_graph_from_ui_data(data)
        if not pseudo:
            return None
        try:
            return load_api_workflow_template(workflow_path)
        except ValueError:
            logger.info(
                "Using UI workflow inspection graph for %s (conversion deferred until generation).",
                Path(workflow_path).name,
            )
            return pseudo

    try:
        return load_api_workflow_template(workflow_path)
    except ValueError:
        return None


def custom_tool_dependency_entries(
    tool: dict[str, Any],
    object_info: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return installable companion rows for a custom tool's missing nodes and weights."""
    from dreamforge_companion_download import tag_companion_tiers

    graph = _load_custom_tool_graph(tool)
    if graph is None:
        workflow_path = str(tool.get("workflow_path") or "").strip()
        if not workflow_path or not Path(workflow_path).is_file():
            return [
                {
                    "kind": "custom_tool",
                    "id": "workflow_file_missing",
                    "filename": "workflow_file_missing",
                    "relative": workflow_path or "workflow",
                    "category": "custom_tool",
                    "note": "Custom tool workflow JSON was not found on disk.",
                }
            ]
        return []

    missing_nodes = custom_tool_preflight(tool, object_info)
    entries: list[dict[str, Any]] = []
    mapped_nodes: set[str] = set()
    try:
        from dreamforge_workflow_planner import (
            missing_custom_node_pack_entries,
            resolve_pack_ids_for_nodes,
        )

        pack_ids = resolve_pack_ids_for_nodes(
            missing_nodes if object_info is not None else workflow_class_types(graph)
        )
        if pack_ids:
            entries.extend(
                missing_custom_node_pack_entries(pack_ids, object_info=object_info)
            )
            from dreamforge_krita_recipes import COMFY_INSTALL_RECIPE

            for section in ("required_custom_nodes", "optional_custom_nodes"):
                for entry in COMFY_INSTALL_RECIPE.get(section) or []:
                    if str(entry.get("id") or "") not in pack_ids:
                        continue
                    mapped_nodes.update(
                        str(node).strip()
                        for node in (entry.get("nodes") or [])
                        if str(node).strip()
                    )
            from dreamforge_workflow_planner import EXTRA_NODE_TO_PACK

            for node in missing_nodes:
                if EXTRA_NODE_TO_PACK.get(node):
                    mapped_nodes.add(node)
    except Exception:
        pass

    leftover = [node for node in missing_nodes if node not in mapped_nodes]
    if leftover:
        entries.append(
            {
                "kind": "custom_node_pack",
                "pack_id": leftover[0],
                "id": leftover[0],
                "filename": leftover[0],
                "relative": "engines/comfyui/custom_nodes",
                "category": "custom_nodes",
                "install_via": "manager",
                "missing_nodes": leftover,
                "note": (
                    "Search ComfyUI-Manager for a pack providing: "
                    + ", ".join(leftover)
                ),
            }
        )

    entries.extend(missing_workflow_graph_model_entries(graph, tool=tool))
    from dreamforge_companion_download import filter_unsatisfied_companion_entries

    return tag_companion_tiers(
        filter_unsatisfied_companion_entries(_merge_custom_tool_dependency_rows(entries))
    )


def _merge_custom_tool_dependency_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for item in items:
        key = str(
            item.get("pack_id")
            or item.get("catalog_id")
            or item.get("id")
            or item.get("relative")
            or ""
        )
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def custom_tool_dependencies_for_id(
    tool_id: str,
    *,
    object_info: dict[str, Any] | None = None,
    use_object_info: bool = True,
) -> list[dict[str, Any]]:
    tool = find_custom_tool(tool_id)
    if not tool:
        return []
    resolved_info = object_info
    if use_object_info and resolved_info is None:
        try:
            from dreamforge_comfy_server import fetch_comfy_object_info

            resolved_info = fetch_comfy_object_info(timeout_s=12.0)
        except Exception:
            resolved_info = None
    return custom_tool_dependency_entries(tool, object_info=resolved_info)
