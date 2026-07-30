"""Load ComfyUI workflows for DreamForge execution.

Supports Comfy Save (API Format) JSON and the default UI workflow export.
UI workflows are converted to API prompts at load time using ComfyUI's node
definitions (same approach as comfyui-workflow-to-api-converter-endpoint).
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from _paths import BACKEND_ROOT, COMFY_ROOT, PYTHON_EXE

logger = logging.getLogger(__name__)

_UI_SKIP_NODE_TYPES = frozenset(
    {
        "MarkdownNote",
        "Note",
        "Reroute",
        "PrimitiveNode",
    }
)


def is_ui_workflow_format(data: Any) -> bool:
    return isinstance(data, dict) and isinstance(data.get("nodes"), list)


def _workflow_root(data: dict[str, Any]) -> dict[str, Any]:
    prompt = data.get("prompt")
    if isinstance(prompt, dict):
        return prompt
    return data


def count_api_nodes(data: dict[str, Any]) -> tuple[int, int, int]:
    """Return (with_class_type, missing_class_type, total_node_like)."""
    root = _workflow_root(data)
    valid = missing = total = 0
    for value in root.values():
        if not isinstance(value, dict):
            continue
        inputs = value.get("inputs")
        if not isinstance(inputs, dict):
            continue
        total += 1
        if value.get("class_type"):
            valid += 1
        else:
            missing += 1
    return valid, missing, total


def _looks_like_api_prompt(data: Any) -> bool:
    if not isinstance(data, dict) or not data:
        return False
    if is_ui_workflow_format(data):
        return False
    root = _workflow_root(data)
    valid, missing, total = count_api_nodes(root)
    if valid == 0 or total == 0:
        return False
    if missing == 0:
        return True
    # Some custom nodes omit class_type in API export; still an API prompt graph.
    return valid >= missing


def guess_api_workflow_sibling(path: Path) -> Path | None:
    """Guess a Comfy API export stored next to a UI workflow save."""
    path = path.resolve()
    parent = path.parent
    stem = path.stem
    suffix = path.suffix
    candidates: list[Path] = []
    if " - " in stem:
        candidates.append(parent / f"{stem.replace(' - ', ' -API- ', 1)}{suffix}")
    candidates.append(parent / f"{stem}-API{suffix}")
    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.resolve() != path:
                return candidate
        except OSError:
            continue
    try:
        for sibling in parent.glob(f"*{suffix}"):
            if sibling.resolve() == path or "-API-" not in sibling.name:
                continue
            ui_match = guess_ui_workflow_sibling(sibling)
            if ui_match and ui_match.resolve() == path:
                return sibling
    except OSError:
        return None
    return None


def guess_ui_workflow_sibling(path: Path) -> Path | None:
    """Guess the Comfy UI workflow JSON next to an API export."""
    path = path.resolve()
    parent = path.parent
    name = path.name
    stem = path.stem
    candidates: list[Path] = []
    if "-API-" in name:
        candidates.append(parent / name.replace("-API-", " - ", 1))
        candidates.append(parent / name.replace("-API-", "-", 1))
    if re.search(r"(?i)[\s\-_]*api[\s\-_]*", stem):
        relaxed = re.sub(r"(?i)[\s\-_]*api[\s\-_]*", " - ", stem).strip(" -")
        if relaxed and relaxed != stem:
            candidates.append(parent / f"{relaxed}{path.suffix}")
    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.resolve() != path:
                return candidate
        except OSError:
            continue
    return None


def ui_node_type_map(ui_data: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in ui_data.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "").strip()
        class_type = str(node.get("type") or node.get("class_type") or "").strip()
        if node_id and class_type:
            out[node_id] = class_type
    return out


def repair_api_workflow_class_types(
    graph: dict[str, Any],
    ui_types: dict[str, str],
) -> list[str]:
    """Fill missing class_type fields from a UI workflow export."""
    repaired: list[str] = []
    for node_id, node in graph.items():
        if not isinstance(node, dict) or node.get("class_type"):
            continue
        class_type = ui_types.get(str(node_id))
        if not class_type:
            continue
        node["class_type"] = class_type
        repaired.append(str(node_id))
    return repaired


def _missing_class_type_node_ids(graph: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for node_id, node in graph.items():
        if not isinstance(node, dict):
            continue
        if isinstance(node.get("inputs"), dict) and not node.get("class_type"):
            missing.append(str(node_id))
    return missing


def is_workflow_link(value: Any) -> bool:
    """True when an API input value references another node output."""
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[1], int)
        and isinstance(value[0], (str, int))
    )


def ui_active_node_count(ui_data: dict[str, Any]) -> int:
    """Count UI nodes that participate in execution (not bypassed/notes)."""
    count = 0
    for node in ui_data.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type") or "").strip()
        if not node_type or node_type in _UI_SKIP_NODE_TYPES:
            continue
        if int(node.get("mode") or 0) == 4:
            continue
        count += 1
    return count


def pseudo_graph_from_ui_data(ui_data: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal API-like graph from a Comfy UI workflow for inspection."""
    graph: dict[str, Any] = {}
    for node in ui_data.get("nodes") or []:
        if not isinstance(node, dict) or node.get("id") is None:
            continue
        node_type = str(node.get("type") or "").strip()
        if not node_type or node_type in _UI_SKIP_NODE_TYPES:
            continue
        if int(node.get("mode") or 0) == 4:
            continue
        graph[str(node.get("id"))] = {
            "class_type": node_type,
            "inputs": {},
            "_meta": node,
        }
    return graph


def _convert_cli_script() -> Path:
    return BACKEND_ROOT / "tools" / "convert_comfy_ui_workflow_cli.py"


def convert_ui_workflow_to_api(
    ui_data: dict[str, Any],
    *,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    """Convert a Comfy UI workflow dict to an executable API prompt graph."""
    if not is_ui_workflow_format(ui_data):
        raise ValueError("Expected Comfy UI workflow JSON with a top-level nodes array.")
    if not COMFY_ROOT.is_dir():
        raise ValueError(
            "ComfyUI is not installed yet, so DreamForge cannot convert UI workflows. "
            "Install the GPU engine first, or export Save (API Format) from ComfyUI."
        )
    cli = _convert_cli_script()
    if not cli.is_file():
        raise ValueError(f"UI workflow converter is missing: {cli}")

    python_exe = PYTHON_EXE if PYTHON_EXE and Path(PYTHON_EXE).is_file() else Path(sys.executable)
    env = os.environ.copy()
    env["COMFY_ROOT"] = str(COMFY_ROOT)
    proc = subprocess.run(
        [str(python_exe), str(cli)],
        input=json.dumps(ui_data),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(COMFY_ROOT),
        env=env,
        timeout=180,
        check=False,
    )
    stdout = (proc.stdout or "").strip()
    if proc.returncode != 0:
        detail = (proc.stderr or stdout).strip()
        label = Path(source_path).name if source_path else "UI workflow"
        raise ValueError(
            f"Could not convert {label} from Comfy UI format to API format. {detail}".strip()
        )
    json_start = stdout.find("{")
    json_end = stdout.rfind("}")
    if json_start < 0 or json_end <= json_start:
        raise ValueError("UI workflow conversion returned invalid JSON.")
    try:
        converted = json.loads(stdout[json_start : json_end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("UI workflow conversion returned invalid JSON.") from exc
    if not isinstance(converted, dict) or not _looks_like_api_prompt(converted):
        raise ValueError("UI workflow conversion did not produce a valid API prompt graph.")
    return converted


def convert_ui_workflow_file(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    ui_data = json.loads(file_path.read_text(encoding="utf-8"))
    return convert_ui_workflow_to_api(ui_data, source_path=file_path)


def _api_graph_from_file_data(data: dict[str, Any]) -> dict[str, Any]:
    if isinstance(data.get("prompt"), dict):
        return copy.deepcopy(data["prompt"])
    return copy.deepcopy(data)


def _should_prefer_ui_conversion(
    api_graph: dict[str, Any],
    ui_data: dict[str, Any],
) -> bool:
    """Prefer UI conversion when the API export dropped executable nodes."""
    api_nodes = count_api_nodes(api_graph)[2]
    ui_nodes = ui_active_node_count(ui_data)
    if ui_nodes <= api_nodes:
        return False
    ui_types = {
        str(node.get("type") or "").strip()
        for node in ui_data.get("nodes") or []
        if isinstance(node, dict)
        and int(node.get("mode") or 0) != 4
        and str(node.get("type") or "").strip() not in _UI_SKIP_NODE_TYPES
    }
    api_types = set(workflow_class_types(api_graph))
    return bool(ui_types - api_types)


def load_api_workflow_template(
    path: str | Path,
    *,
    ui_path: str | Path | None = None,
    prefer_ui: bool = True,
) -> dict[str, Any]:
    """Read a Comfy workflow JSON file as an executable API prompt graph."""
    file_path = Path(path)
    raw = file_path.read_text(encoding="utf-8")
    data = json.loads(raw)

    if is_ui_workflow_format(data):
        api_sibling = guess_api_workflow_sibling(file_path)
        if api_sibling and api_sibling.is_file():
            logger.info(
                "Using API sibling %s for execution (UI workflow %s).",
                api_sibling.name,
                file_path.name,
            )
            return load_api_workflow_template(api_sibling, prefer_ui=False)
        graph = convert_ui_workflow_to_api(data, source_path=file_path)
        missing = _missing_class_type_node_ids(graph)
        if missing:
            repair_api_workflow_class_types(graph, ui_node_type_map(data))
        return graph

    graph = _api_graph_from_file_data(data)
    missing = _missing_class_type_node_ids(graph)
    ui_file = Path(ui_path) if ui_path else guess_ui_workflow_sibling(file_path)
    ui_data: dict[str, Any] | None = None
    if ui_file and ui_file.is_file():
        try:
            ui_candidate = json.loads(ui_file.read_text(encoding="utf-8"))
            if is_ui_workflow_format(ui_candidate):
                ui_data = ui_candidate
        except (OSError, json.JSONDecodeError):
            ui_data = None

    if missing and ui_data:
        repair_api_workflow_class_types(graph, ui_node_type_map(ui_data))
        missing = _missing_class_type_node_ids(graph)

    if prefer_ui and ui_data and _should_prefer_ui_conversion(graph, ui_data):
        logger.info(
            "Using UI workflow %s because API export %s is missing executable nodes.",
            ui_file.name if ui_file else ui_data,
            file_path.name,
        )
        graph = convert_ui_workflow_to_api(ui_data, source_path=ui_file)
        missing = _missing_class_type_node_ids(graph)
        if missing:
            repair_api_workflow_class_types(graph, ui_node_type_map(ui_data))

    if not _looks_like_api_prompt(graph):
        if missing:
            raise ValueError(
                f"{path} is missing class_type on nodes {', '.join(missing)}. "
                "Re-export with Save (API Format), keep the UI workflow JSON in the "
                "same folder, or point workflow_path at the UI workflow file."
            )
        raise ValueError(
            f"{path} is not a Comfy UI or Save (API Format) workflow JSON."
        )
    return graph


def inspect_comfy_workflow_file(path: str | Path) -> dict[str, Any]:
    """Parse a workflow file for custom-tool import (UI or API)."""
    file_path = Path(path)
    raw = file_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    ui_format = is_ui_workflow_format(data)
    ui_sibling = guess_ui_workflow_sibling(file_path)
    warning = ""
    error = ""
    graph: dict[str, Any] = {}
    repaired_nodes: list[str] = []
    api_format = False
    converts_at_runtime = False
    try:
        if ui_format:
            converts_at_runtime = True
            api_sibling = guess_api_workflow_sibling(file_path)
            if api_sibling and api_sibling.is_file():
                graph = load_api_workflow_template(file_path)
                api_format = True
                warning = (
                    f"UI workflow detected — DreamForge will execute the paired API export "
                    f"{api_sibling.name} when this tool runs."
                )
            else:
                graph = convert_ui_workflow_to_api(data, source_path=file_path)
                api_format = True
                warning = (
                    "UI workflow detected — DreamForge will convert it with ComfyUI node "
                    "definitions when this tool runs."
                )
        else:
            scratch = copy.deepcopy(_workflow_root(data)) if isinstance(data, dict) else {}
            missing_before = _missing_class_type_node_ids(scratch)
            graph = load_api_workflow_template(file_path)
            api_format = True
            if missing_before:
                repaired_nodes = [
                    node_id
                    for node_id in missing_before
                    if isinstance(graph.get(node_id), dict) and graph[node_id].get("class_type")
                ]
                if repaired_nodes and ui_sibling:
                    warning = (
                        f"Repaired {len(repaired_nodes)} custom node(s) using UI workflow "
                        f"{ui_sibling.name}."
                    )
                elif repaired_nodes:
                    warning = f"Repaired {len(repaired_nodes)} node(s) missing class_type in API export."
            if ui_sibling and ui_sibling.is_file():
                try:
                    ui_data = json.loads(ui_sibling.read_text(encoding="utf-8"))
                    if is_ui_workflow_format(ui_data) and _should_prefer_ui_conversion(graph, ui_data):
                        warning = (
                            f"API export is missing nodes present in {ui_sibling.name}. "
                            "Consider pointing this tool at the UI workflow file instead."
                        )
                except (OSError, json.JSONDecodeError):
                    pass
    except ValueError as exc:
        error = str(exc)
        if ui_format:
            graph = pseudo_graph_from_ui_data(data) if not graph else graph
        else:
            root = _workflow_root(data) if isinstance(data, dict) else {}
            if isinstance(root, dict):
                graph = {str(k): v for k, v in root.items() if isinstance(v, dict)}
        valid, missing, total = count_api_nodes(data if isinstance(data, dict) else {})
        api_format = bool(valid and not ui_format and valid >= missing)

    if ui_format and graph:
        api_format = True
        converts_at_runtime = True
        if error and not warning:
            warning = (
                "UI workflow will be converted when the GPU engine runs. "
                f"{error}"
            )
            error = ""

    return {
        "api_format": api_format,
        "ui_format": ui_format,
        "converts_at_runtime": converts_at_runtime,
        "nodes": graph,
        "class_types": workflow_class_types(graph) if graph else [],
        "repaired_nodes": repaired_nodes,
        "ui_sibling": str(ui_sibling) if ui_sibling else None,
        "warning": warning,
        "error": error,
    }


def resolve_comfy_workflow_template(
    *,
    mode: str,
    explicit_path: str | None = None,
) -> Path | None:
    """Resolve optional API workflow template path from job or env."""
    candidates: list[str] = []
    if explicit_path:
        candidates.append(str(explicit_path).strip())
    mode_key = (mode or "auto").strip().lower()
    env_by_mode = {
        "txt2img": "DREAMFORGE_COMFY_WORKFLOW_TXT2IMG",
        "img2img": "DREAMFORGE_COMFY_WORKFLOW_IMG2IMG",
        "kontext": "DREAMFORGE_COMFY_WORKFLOW_KONTEXT",
        "inpaint": "DREAMFORGE_COMFY_WORKFLOW_INPAINT",
        "upscale": "DREAMFORGE_COMFY_WORKFLOW_UPSCALE",
    }
    mode_env = env_by_mode.get(mode_key)
    if mode_env:
        candidates.append(os.environ.get(mode_env, "").strip())
    candidates.append(os.environ.get("DREAMFORGE_COMFY_WORKFLOW_API", "").strip())
    for item in candidates:
        if not item:
            continue
        path = Path(item)
        if path.is_file():
            return path
    return None


def _set_first_matching_input(
    graph: dict[str, Any],
    *,
    class_types: tuple[str, ...],
    input_names: tuple[str, ...],
    value: Any,
) -> bool:
    for node in graph.values():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") not in class_types:
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for name in input_names:
            if name in inputs:
                inputs[name] = value
                return True
    return False


def patch_api_workflow(graph: dict[str, Any], bindings: dict[str, Any]) -> dict[str, Any]:
    """Patch a cloned API workflow with DreamForge generation bindings."""
    out = copy.deepcopy(graph)

    ckpt = bindings.get("ckpt_name")
    if ckpt:
        _set_first_matching_input(
            out,
            class_types=("CheckpointLoaderSimple",),
            input_names=("ckpt_name",),
            value=str(ckpt),
        )
    category = str(bindings.get("category") or "").lower()
    relative = bindings.get("relative_path")
    unet_name = str(relative or ckpt or "")
    for prefix in ("../diffusion_models/", "..\\diffusion_models\\", "../unet/", "..\\unet\\"):
        if unet_name.lower().startswith(prefix):
            unet_name = unet_name[len(prefix) :]
    if category in ("diffusion_models", "unet") and unet_name:
        _set_first_matching_input(
            out,
            class_types=("UNETLoader", "UnetLoaderGGUF"),
            input_names=("unet_name",),
            value=unet_name,
        )
        _set_first_matching_input(
            out,
            class_types=("DualCLIPLoader", "DualCLIPLoaderGGUF"),
            input_names=("clip_name1",),
            value=str(bindings.get("clip_l") or "clip_l.safetensors"),
        )
        _set_first_matching_input(
            out,
            class_types=("DualCLIPLoader", "DualCLIPLoaderGGUF"),
            input_names=("clip_name2",),
            value=str(bindings.get("t5") or "t5xxl_fp8_e4m3fn_scaled.safetensors"),
        )
        _set_first_matching_input(
            out,
            class_types=("VAELoader",),
            input_names=("vae_name",),
            value=str(bindings.get("vae") or "ae.safetensors"),
        )

    prompt = bindings.get("prompt")
    if prompt is not None:
        _set_first_matching_input(
            out,
            class_types=("CLIPTextEncode",),
            input_names=("text",),
            value=str(prompt),
        )

    negative = bindings.get("negative")
    if negative is not None:
        patched = False
        for node in out.values():
            if not isinstance(node, dict) or node.get("class_type") != "CLIPTextEncode":
                continue
            inputs = node.get("inputs") or {}
            text = str(inputs.get("text", "")).lower()
            if any(token in text for token in ("negative", "bad", "worst", "low quality")):
                inputs["text"] = str(negative)
                patched = True
                break
        if not patched:
            # Fall back to second CLIPTextEncode node if present.
            clip_nodes = [
                n
                for n in out.values()
                if isinstance(n, dict) and n.get("class_type") == "CLIPTextEncode"
            ]
            if len(clip_nodes) > 1:
                clip_nodes[1].setdefault("inputs", {})["text"] = str(negative)

    image = bindings.get("image")
    if image:
        _set_first_matching_input(
            out,
            class_types=("LoadImage",),
            input_names=("image",),
            value=str(image),
        )

    reference_stitch = bindings.get("reference_stitch")
    if reference_stitch:
        load_nodes = [
            node
            for node in out.values()
            if isinstance(node, dict) and node.get("class_type") == "LoadImage"
        ]
        if len(load_nodes) > 1:
            load_nodes[1].setdefault("inputs", {})["image"] = str(reference_stitch)

    mask = bindings.get("mask")
    if mask:
        load_nodes = [
            (node_id, node)
            for node_id, node in out.items()
            if isinstance(node, dict) and node.get("class_type") == "LoadImage"
        ]
        if len(load_nodes) > 1:
            _node_id, node = load_nodes[1]
            node.setdefault("inputs", {})["image"] = str(mask)
        else:
            _set_first_matching_input(
                out,
                class_types=("LoadImage",),
                input_names=("image",),
                value=str(mask),
            )

    upscale_model = bindings.get("upscale_model")
    if upscale_model:
        _set_first_matching_input(
            out,
            class_types=("UpscaleModelLoader",),
            input_names=("model_name",),
            value=str(upscale_model),
        )

    seed = bindings.get("seed")
    if seed is not None:
        _set_first_matching_input(
            out,
            class_types=("KSampler",),
            input_names=("seed",),
            value=int(seed),
        )

    steps = bindings.get("steps")
    if steps is not None:
        _set_first_matching_input(
            out,
            class_types=("KSampler",),
            input_names=("steps",),
            value=int(steps),
        )

    cfg = bindings.get("cfg")
    if cfg is not None:
        _set_first_matching_input(
            out,
            class_types=("KSampler",),
            input_names=("cfg",),
            value=float(cfg),
        )
        _set_first_matching_input(
            out,
            class_types=("FluxGuidance",),
            input_names=("guidance",),
            value=float(cfg),
        )

    denoise = bindings.get("denoise")
    if denoise is not None:
        _set_first_matching_input(
            out,
            class_types=("KSampler",),
            input_names=("denoise",),
            value=float(denoise),
        )

    width = bindings.get("width")
    height = bindings.get("height")
    if width is not None and height is not None:
        _set_first_matching_input(
            out,
            class_types=("EmptyLatentImage", "EmptySD3LatentImage"),
            input_names=("width",),
            value=int(width),
        )
        _set_first_matching_input(
            out,
            class_types=("EmptyLatentImage", "EmptySD3LatentImage"),
            input_names=("height",),
            value=int(height),
        )

    sampler = bindings.get("sampler_name")
    if sampler:
        _set_first_matching_input(
            out,
            class_types=("KSampler",),
            input_names=("sampler_name",),
            value=str(sampler),
        )

    scheduler = bindings.get("scheduler")
    if scheduler:
        _set_first_matching_input(
            out,
            class_types=("KSampler",),
            input_names=("scheduler",),
            value=str(scheduler),
        )

    grow_mask_by = bindings.get("grow_mask_by")
    if grow_mask_by is not None:
        _set_first_matching_input(
            out,
            class_types=("VAEEncodeForInpaint",),
            input_names=("grow_mask_by",),
            value=int(grow_mask_by),
        )

    prefix = bindings.get("filename_prefix")
    if prefix:
        _set_first_matching_input(
            out,
            class_types=("SaveImage",),
            input_names=("filename_prefix",),
            value=str(prefix),
        )

    return out


def patch_node_field(
    graph: dict[str, Any],
    node_id: str,
    field: str,
    value: Any,
    *,
    preserve_links: bool = True,
) -> bool:
    """Set a single input on a specific API workflow node."""
    node = graph.get(str(node_id))
    if not isinstance(node, dict):
        return False
    inputs = node.setdefault("inputs", {})
    field_name = str(field)
    existing = inputs.get(field_name)
    if preserve_links and is_workflow_link(existing):
        return False
    inputs[field_name] = value
    return True


def workflow_class_types(graph: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(node.get("class_type"))
            for node in graph.values()
            if isinstance(node, dict) and node.get("class_type")
        }
    )


def build_prompt_from_template(path: str | Path, bindings: dict[str, Any]) -> dict[str, Any]:
    graph = load_api_workflow_template(path)
    return patch_api_workflow(graph, bindings)


def coerce_reference_image_paths(job) -> list[str]:
    """Extra Kontext/control reference images (Krita multi-reference conditioning).

    Merges two channels so every additional reference reaches the stitch/chain
    and Qwen Plus consumers:
    - ``reference_images`` / ``control_images`` (Krita-style extra refs), and
    - the non-primary slots of the multi-slot ``references`` array (Pro Create),
      excluding the primary, which is already projected onto ``input_image`` /
      ``reference_image``.
    """
    raw = getattr(job, "reference_images", None)
    if raw is None:
        raw = getattr(job, "control_images", None)
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            raw = None
        elif text.startswith("["):
            try:
                raw = json.loads(text)
            except json.JSONDecodeError:
                raw = [part.strip() for part in text.split(",") if part.strip()]
        else:
            raw = [part.strip() for part in text.split(",") if part.strip()]

    out: list[str] = []
    seen: set[str] = set()
    if isinstance(raw, (list, tuple)):
        for item in raw:
            path = str(item or "").strip()
            if not path:
                continue
            key = path.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(path)

    try:
        from dreamforge_references import coerce_reference_slots

        slots = coerce_reference_slots(job)
    except Exception:
        slots = []
    if len(slots) > 1:
        primary_paths = {
            str(getattr(job, "input_image", None) or "").strip().lower(),
            str(getattr(job, "reference_image", None) or "").strip().lower(),
        }
        primary_paths.discard("")
        for slot in slots:
            role = str(slot.get("role") or "").strip().lower()
            if role not in {"image_prompt", "restyle", "source_edit"}:
                continue
            path = str(slot.get("path") or "").strip()
            if not path:
                continue
            key = path.lower()
            if key in seen or key in primary_paths:
                continue
            seen.add(key)
            out.append(path)
    return out


def comfy_workflow_mode(
    *,
    input_filename: str | None,
    cn_type: str,
    model: dict,
    model_family: str,
    checkpoint_is_flux_kontext,
    workflow_mode: str | None = None,
    edit_type: str | None = None,
) -> str:
    mode_key = str(workflow_mode or "").strip().lower()
    edit = str(edit_type or "").lower()
    if mode_key == "hires":
        return "hires"
    if mode_key in ("area_composition", "composite"):
        return "area_composition"
    if (model_family or "").lower() == "hidream_o1" and mode_key in (
        "ipadapter",
        "reference_ipadapter",
    ):
        return "hidream_reference"
    if mode_key == "ipadapter":
        return "ipadapter"
    if mode_key == "ipadapter_style":
        return "ipadapter_style"
    if mode_key == "ipadapter_faceid":
        return "ipadapter_faceid"
    if mode_key == "ipadapter_controlnet":
        return "ipadapter_controlnet"
    if mode_key == "face_detail" or edit == "face_detail":
        return "face_detail"
    cn = str(cn_type or "None").lower()
    controlnet_types = {
        "depth",
        "canny",
        "pose",
        "openpose",
        "lineart",
        "scribble",
        "sketch",
        "recolour",
        "controlnet",
        "controlnet_structure",
    }
    if cn == "outpaint" or edit == "outpaint" or mode_key == "outpaint":
        return "outpaint"
    if cn in controlnet_types or mode_key == "controlnet":
        return "controlnet"
    if cn == "ipadapter" or mode_key in ("ipadapter", "reference_ipadapter"):
        return "ipadapter"
    if cn == "reference" and not input_filename:
        return "ipadapter"
    if cn == "area_composition":
        return "area_composition"
    if input_filename:
        if cn == "upscale":
            return "upscale"
        if cn == "inpaint":
            return "inpaint"
        family = (model_family or "").lower()
        if family == "qwen_image_edit" or edit == "qwen_edit":
            return "qwen_edit"
        if checkpoint_is_flux_kontext(model, model_family):
            return "kontext"
        return "img2img"
    if (model_family or "").startswith("flux"):
        return "txt2img"
    return "txt2img"
