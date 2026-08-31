"""Structured error codes for DreamForge.

A *single* source of truth for every failure mode that crosses the
worker -> Tauri -> UI boundary.  Each helper returns a JSON-serialisable
``dict`` with this shape::

    {
        "type": "error",
        "code": "out_of_memory",
        "message": "...",
        "suggestions": ["...", "..."],
        "details": {...},        # optional, code-specific
        "recoverable": true,     # optional, hint for UI retry CTAs
    }

The ``code`` is the stable identifier; ``message`` is the short
human-readable summary; ``suggestions`` lists actionable next steps the
UI can render as bullet points or as buttons.

Use :func:`error` for the generic builder, or one of the named helpers
(:func:`out_of_memory`, :func:`disk_full`, ...) for the well-known
failure modes.

Importing this module must stay cheap: no torch, no comfy, no model
loading.  The desktop bridge and worker both rely on it during boot.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable, Mapping


__all__ = [
    "error",
    "out_of_memory",
    "missing_input_image",
    "invalid_input_image",
    "missing_model_dependencies",
    "missing_custom_node_pack",
    "model_not_found",
    "model_file_unreadable",
    "unsupported_model_format",
    "disk_full",
    "virtual_memory_low",
    "worker_crashed",
    "worker_pipe_closed",
    "comfy_server_crashed",
    "generation_cancelled",
    "generation_in_progress",
    "invalid_request",
    "comfy_workflow_validation",
    "unsupported_workflow_class",
    "build_failure_report",
    "from_exception",
]


def error(
    code: str,
    message: str,
    *,
    suggestions: Iterable[str] | None = None,
    details: Mapping[str, Any] | None = None,
    recoverable: bool | None = None,
    job_id: str | None = None,
) -> dict:
    """Build a structured ``error`` event.

    Always includes ``type="error"`` and the supplied ``code`` /
    ``message``.  ``suggestions`` and ``details`` are omitted when
    empty so the JSON payload stays compact.
    """

    out: dict[str, Any] = {
        "type": "error",
        "error": code,        # legacy field, kept for backward compatibility
        "code": code,
        "message": message,
    }
    suggestion_list = [s for s in (suggestions or []) if s]
    if suggestion_list:
        out["suggestions"] = suggestion_list
    if details:
        out["details"] = dict(details)
    if recoverable is not None:
        out["recoverable"] = bool(recoverable)
    if job_id:
        out["job_id"] = job_id
    report = build_failure_report(code, message, details=out.get("details"), recoverable=recoverable)
    if report:
        out["failure_report"] = report
    return out


def build_failure_report(
    code: str,
    message: str = "",
    *,
    details: Mapping[str, Any] | None = None,
    recoverable: bool | None = None,
) -> dict[str, Any] | None:
    """Return machine-readable repair hints for UI, CLI, REST, and MCP.

    The actions here are intentionally conservative: anything that installs,
    downloads, retries GPU work, or changes the selected route requires explicit
    user approval before another layer may execute it.
    """

    detail_map = dict(details or {})
    actions: list[dict[str, Any]] = []

    def add(action: str, *, approval: bool = False, **payload: Any) -> None:
        item = {"action": action, "requires_approval": bool(approval)}
        item.update({k: v for k, v in payload.items() if v not in (None, "", [], {})})
        actions.append(item)

    if code == "out_of_memory":
        add("reduce_resolution", scale=0.75, hint="Retry at roughly 75% of the current pixel count.")
        add("reduce_batch", image_number=1, hint="Retry one image at a time.")
        add("switch_vram_profile", vram_profile="8gb", hint="Use a lower-memory Comfy launch profile.")
        add("switch_model_route", approval=True, hint="Pick a smaller quantized local model before retrying.")
        add("retry_with_safer_settings", approval=True, max_retries=1)
    elif code in {"comfy_server_crashed", "virtual_memory_low"}:
        add("restart_local_backend", approval=True, hint="Restart managed ComfyUI before retrying.")
        add("reduce_resolution", scale=0.75)
        add("switch_vram_profile", vram_profile="5gb" if code == "virtual_memory_low" else "8gb")
        add("retry_with_safer_settings", approval=True, max_retries=1)
    elif code == "missing_custom_node_pack":
        pack_id = detail_map.get("pack_id") or "unknown"
        nodes = detail_map.get("nodes") or []
        install_via = detail_map.get("install_via")
        add("replace_node_pattern", approval=True, nodes=nodes, hint="Rebuild this stage with a first-party fallback pattern when possible.")
        add(
            "install_custom_node_pack",
            approval=True,
            pack_id=pack_id,
            nodes=nodes,
            install_via=install_via,
            hint="Install custom nodes only after the user approves the exact pack.",
        )
        add("disable_optional_stage", approval=True, nodes=nodes)
    elif code == "missing_model_dependencies":
        missing = [item for item in (detail_map.get("missing") or []) if isinstance(item, Mapping)]
        recommended = list(detail_map.get("recommended_actions") or [])
        for item in recommended:
            if isinstance(item, Mapping):
                payload = dict(item)
                payload["requires_approval"] = True
                actions.append(payload)
        if missing:
            add(
                "download_model_companions",
                approval=True,
                missing=missing,
                hint="Download workflow annotators and companion files before retrying.",
            )
        add("switch_model_route", approval=True, hint="Use an already-installed compatible local model.")
    elif code in {"missing_input_image", "invalid_input_image"}:
        add("request_input", input="image", hint="Ask the user to attach or re-import a valid local image.")
        if code == "invalid_input_image":
            add("reimport_asset", path=detail_map.get("path"))
    elif code == "model_not_found":
        add("switch_model_route", approval=True, requested=detail_map.get("requested"))
        add("download_model_companions", approval=True, hint="Download only from known model catalog entries.")
    elif code == "invalid_request":
        add("rebuild_workflow_plan", hint="Rebuild the workflow from the current intent and canvas state.")
    elif code == "unsupported_workflow_class":
        add("replace_node_pattern", approval=True, workflow_class=detail_map.get("workflow_class"))
        add("rebuild_workflow_plan", approval=True)
    elif code == "comfy_workflow_validation":
        add("restart_local_backend", hint="Restart managed ComfyUI after updating DreamForge.")
        add("rebuild_workflow_plan", hint="Rebuild the workflow from the current settings.")
        add("inspect_logs", hint="Open Technical diagnostics for the ComfyUI node report.")
    elif code == "generation_failed":
        add("inspect_logs", hint="Open worker.log and comfy.server.log for the traceback.")
        add("rebuild_workflow_plan", approval=True)
    else:
        return None

    return {
        "kind": code,
        "summary": message,
        "recoverable": bool(recoverable),
        "auto_retry": False,
        "max_auto_retries": 0,
        "requires_user_approval": any(bool(item.get("requires_approval")) for item in actions),
        "repair_actions": actions,
    }


# --- Named helpers ----------------------------------------------------------


def out_of_memory(
    *,
    free_gb: float | None = None,
    needed_gb_est: float | None = None,
    vram_profile: str | None = None,
    job_id: str | None = None,
) -> dict:
    details: dict[str, Any] = {}
    if free_gb is not None:
        details["free_gb"] = round(float(free_gb), 2)
    if needed_gb_est is not None:
        details["needed_gb_est"] = round(float(needed_gb_est), 2)
    if vram_profile:
        details["vram_profile"] = str(vram_profile)

    suggestions = [
        "Lower the resolution (try 768x768 first, then raise it if stable).",
        "Reduce the batch / image count.",
        "Switch the VRAM profile to 'low' or 'no' in Settings.",
        "Use a quantized variant (look for fp8 / Q4_K / Q5_K).",
        "Close other GPU apps (browsers, games, video editors).",
    ]
    return error(
        "out_of_memory",
        "Ran out of GPU memory while generating.",
        suggestions=suggestions,
        details=details,
        recoverable=True,
        job_id=job_id,
    )


def missing_input_image(*, job_id: str | None = None) -> dict:
    return error(
        "missing_input_image",
        "This model or use case requires a reference image.",
        suggestions=[
            "Set Input image in Settings or drop one onto the canvas.",
            "If you wanted text-to-image, switch the use case to a non-edit option.",
        ],
        recoverable=True,
        job_id=job_id,
    )


def invalid_input_image(detail: str, *, path: str | None = None, job_id: str | None = None) -> dict:
    return error(
        "invalid_input_image",
        f"Input image could not be loaded: {detail}",
        suggestions=[
            "Verify the file exists and is a PNG, JPEG, or WebP.",
            "Try re-importing the image from disk.",
        ],
        details={"path": path} if path else None,
        recoverable=True,
        job_id=job_id,
    )


def missing_custom_node_pack(
    pack_id: str,
    *,
    job_id: str | None = None,
    nodes: Iterable[str] | None = None,
) -> dict:
    node_list = list(nodes or [])
    resolved_pack = str(pack_id or "").strip()
    if not resolved_pack or resolved_pack in {"unknown", "ComfyUI workflow"}:
        try:
            from dreamforge_workflow_planner import resolve_pack_id_for_nodes

            resolved_pack = resolve_pack_id_for_nodes(node_list) or resolved_pack or "unknown"
        except Exception:
            resolved_pack = resolved_pack or "unknown"
    install_via = None
    if resolved_pack and resolved_pack != "unknown":
        try:
            from dreamforge_comfy_manager import resolve_pack_install_strategy
            from dreamforge_workflow_planner import _recipe_entry_for_pack

            entry = _recipe_entry_for_pack(resolved_pack)
            install_via = resolve_pack_install_strategy(entry, resolved_pack)
        except Exception:
            install_via = None
    node_hint = ""
    if node_list:
        node_hint = f" (nodes: {', '.join(str(n) for n in node_list)})"
    details: dict[str, Any] = {"pack_id": resolved_pack, "nodes": node_list}
    if install_via:
        details["install_via"] = install_via
    return error(
        "missing_custom_node_pack",
        f"Required ComfyUI custom node pack is not installed: {resolved_pack}{node_hint}",
        suggestions=[
            "Install the pack into ComfyUI/custom_nodes using the Models panel or Krita recipe installer.",
            "Restart ComfyUI after installing custom nodes.",
            "Use Brain plan readiness to review required dependencies before running.",
        ],
        details=details,
        recoverable=True,
        job_id=job_id,
    )


def missing_model_dependencies(
    missing: list[Mapping[str, Any]],
    *,
    job_id: str | None = None,
    actions: Iterable[Mapping[str, Any]] | None = None,
) -> dict:
    names = ", ".join(
        str(m.get("name") or m.get("file") or m.get("kind") or "<unknown>") for m in missing
    ) or "required companion files"
    return error(
        "missing_model_dependencies",
        f"Missing companion files for the selected model: {names}",
        suggestions=[
            "Click Download next to Generate, or use Download missing assets in the error dialog.",
            "Workflow tools may need annotator weights under ComfyUI custom_nodes.",
            "Large workflow weights (over 500 MB) require approval before download.",
        ],
        details={"missing": list(missing), "recommended_actions": list(actions or [])},
        recoverable=True,
        job_id=job_id,
    )


def model_not_found(name: str, *, job_id: str | None = None) -> dict:
    return error(
        "model_not_found",
        f"Model '{name}' is not present on disk.",
        suggestions=[
            "Pick a different model from the gallery.",
            "Re-run model organization (Settings -> Models -> Organize).",
            "Use the download surface to fetch the model again.",
        ],
        details={"requested": name},
        recoverable=True,
        job_id=job_id,
    )


def model_file_unreadable(name: str, detail: str, *, job_id: str | None = None) -> dict:
    return error(
        "model_file_unreadable",
        f"Model file '{name}' could not be read: {detail}",
        suggestions=[
            "Re-download the model; the file is likely truncated or corrupted.",
            "Check disk health if other files also fail to read.",
        ],
        details={"requested": name, "detail": detail},
        recoverable=False,
        job_id=job_id,
    )


def unsupported_model_format(name: str, detail: str = "", *, job_id: str | None = None) -> dict:
    return error(
        "unsupported_model_format",
        f"Model '{name}' is not a supported image-generation model" + (f": {detail}" if detail else ""),
        suggestions=[
            "Run 'Organize models' so the file moves to its correct folder.",
            "If it really is a checkpoint, ensure the file extension is .safetensors / .gguf / .ckpt.",
        ],
        details={"requested": name, "detail": detail} if detail else {"requested": name},
        recoverable=False,
        job_id=job_id,
    )


def virtual_memory_low(detail: str = "", *, job_id: str | None = None) -> dict:
    return error(
        "virtual_memory_low",
        "Windows ran out of virtual memory while loading the model.",
        suggestions=[
            "Close browsers, games, and other heavy apps to free RAM.",
            "Increase the Windows paging file: Settings → System → About → Advanced system settings → Performance Settings → Advanced → Virtual memory → Change (use a drive with free space).",
            "In DreamForge, set VRAM profile to 8 GB or 5 GB in the inspector, then restart the GPU engine.",
            "Use a smaller or fp8-quantized checkpoint; avoid loading full fp16 Flux Dev on 8 GB systems.",
            "Reboot after changing the paging file so Windows applies the new limit.",
        ],
        details={"detail": detail} if detail else None,
        recoverable=True,
        job_id=job_id,
    )


def disk_full(detail: str = "", *, path: str | None = None, job_id: str | None = None) -> dict:
    return error(
        "disk_full",
        "Disk is full; could not write the output image.",
        suggestions=[
            "Free up space on the output drive.",
            "Move the outputs/ folder to a larger disk.",
        ],
        details={"path": path, "detail": detail} if path or detail else None,
        recoverable=True,
        job_id=job_id,
    )


def worker_crashed(detail: str = "", *, job_id: str | None = None) -> dict:
    return error(
        "worker_crashed",
        "GPU worker exited unexpectedly.",
        suggestions=[
            "Click 'Restart GPU engine'.",
            "Check worker.log for the underlying traceback.",
        ],
        details={"detail": detail} if detail else None,
        recoverable=True,
        job_id=job_id,
    )


def worker_pipe_closed(detail: str = "", *, job_id: str | None = None) -> dict:
    return error(
        "worker_pipe_closed",
        "GPU worker connection closed before the job could start.",
        suggestions=[
            "Click 'Restart GPU engine'.",
            "Wait until the engine is ready, then retry the generation.",
            "Check worker.log if the worker stops again.",
        ],
        details={"detail": detail} if detail else None,
        recoverable=True,
        job_id=job_id,
    )


_COMFY_CRASH_SUGGESTIONS_COMMON = (
    "Click 'Restart GPU engine' to relaunch ComfyUI and try again.",
    "Lower the resolution (try 768×768 first, then raise it if stable).",
    "Switch to a quantized model (fp8, Q4_K) to reduce VRAM usage.",
    "Close other GPU apps (browsers, games, video editors).",
    "If Task Manager shows Committed memory near its limit, increase the Windows page file (64GB+ on SSD).",
    "Check worker.log and comfy.server.log for the underlying traceback.",
)

_COMFY_CRASH_SUGGESTION_IDEOGRAM = (
    "Ideogram 4 loads two UNets plus Qwen3-VL — use Turbo mode on 16GB GPUs."
)

_COMFY_CRASH_SUGGESTION_EDIT = (
    "Photo edits use Flux Kontext or Qwen Edit — try a smaller source image or lower steps."
)


def _comfy_crash_suggestions(
    *,
    model_family: str = "",
    studio_mode: str = "",
) -> list[str]:
    suggestions = list(_COMFY_CRASH_SUGGESTIONS_COMMON)
    family = str(model_family or "").lower()
    mode = str(studio_mode or "").lower()
    if family == "ideogram4" or "ideogram" in family:
        suggestions.insert(2, _COMFY_CRASH_SUGGESTION_IDEOGRAM)
    elif mode == "edit":
        suggestions.insert(2, _COMFY_CRASH_SUGGESTION_EDIT)
    return suggestions


_COMFY_CRASH_SUGGESTIONS = _comfy_crash_suggestions()

_COMFY_CRASH_MESSAGE = (
    "ComfyUI server crashed or became unreachable during generation. "
    "This usually means it ran out of GPU or system memory (OOM) while loading or sampling."
)


def comfy_server_crashed(
    detail: str = "",
    *,
    job_id: str | None = None,
    model_family: str = "",
    studio_mode: str = "",
) -> dict:
    return error(
        "comfy_server_crashed",
        _COMFY_CRASH_MESSAGE,
        suggestions=_comfy_crash_suggestions(
            model_family=model_family,
            studio_mode=studio_mode,
        ),
        details={"detail": detail} if detail else None,
        recoverable=True,
        job_id=job_id,
    )


def generation_cancelled(*, job_id: str | None = None) -> dict:
    return error(
        "generation_cancelled",
        "Generation cancelled.",
        recoverable=True,
        job_id=job_id,
    )


def generation_in_progress(*, job_id: str | None = None) -> dict:
    return error(
        "generation_in_progress",
        "A generation is already running on the GPU worker.",
        suggestions=["Wait for the current job, or click Cancel to stop it."],
        recoverable=True,
        job_id=job_id,
    )


def comfy_workflow_validation(
    summary: str,
    *,
    suggestions: Iterable[str] | None = None,
    details: Mapping[str, Any] | None = None,
    job_id: str | None = None,
) -> dict:
    default_suggestions = [
        "Restart DreamForge to pick up the latest workflow fix, then generate again.",
        "Restart the GPU engine if the problem persists.",
        "Open Technical diagnostics below for the exact ComfyUI node and field.",
    ]
    return error(
        "comfy_workflow_validation",
        summary,
        suggestions=list(suggestions or default_suggestions),
        details=details,
        recoverable=True,
        job_id=job_id,
    )


def invalid_request(
    detail: str,
    *,
    job_id: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> dict:
    return error(
        "invalid_request",
        f"Invalid generation request: {detail}",
        details=details,
        recoverable=True,
        job_id=job_id,
    )


def unsupported_workflow_class(workflow_class: str, detail: str = "", *, job_id: str | None = None) -> dict:
    return error(
        "unsupported_workflow_class",
        f"Workflow class is not supported by DreamForge: {workflow_class}",
        suggestions=[
            "Rebuild the request using a first-party DreamForge workflow template.",
            "Avoid executing downloaded ComfyUI workflows directly.",
        ],
        details={"workflow_class": workflow_class, "detail": detail} if detail else {"workflow_class": workflow_class},
        recoverable=True,
        job_id=job_id,
    )


def _extract_missing_node_types(message: str, details: Mapping[str, Any] | None = None) -> list[str]:
    nodes: list[str] = []
    for pattern in (
        r"Cannot execute because node\s+([A-Za-z0-9_ .:-]+?)\s+does not exist",
        r"Node type\s+['\"]?([A-Za-z0-9_ .:-]+?)['\"]?\s+(?:does not exist|not found|is missing)",
        r"Unknown node type\s+['\"]?([A-Za-z0-9_ .:-]+?)['\"]?",
        r"Missing node(?: type)?\s+['\"]?([A-Za-z0-9_ .:-]+?)['\"]?",
    ):
        for match in re.finditer(pattern, message, flags=re.IGNORECASE):
            value = match.group(1).strip(" '\".:")
            if value and value not in nodes:
                nodes.append(value)
    detail_map = dict(details or {})
    status = detail_map.get("status")
    if isinstance(status, Mapping):
        for item in status.get("messages") or []:
            if not isinstance(item, (list, tuple)) or len(item) < 2 or not isinstance(item[1], Mapping):
                continue
            payload = item[1]
            exc_msg = str(
                payload.get("exception_message")
                or payload.get("exception_type")
                or payload.get("traceback")
                or ""
            ).lower()
            is_missing = any(
                phrase in exc_msg
                for phrase in (
                    "does not exist",
                    "not found",
                    "unknown node",
                    "is missing",
                    "cannot execute because node",
                )
            )
            if not is_missing:
                continue
            for key in ("node_type", "class_type"):
                value = str(payload.get(key) or "").strip()
                if value and value not in nodes:
                    nodes.append(value)
    return nodes


_COMFY_NODE_LABELS = {
    "VAEDecodeTiled": "VAE decode (tiled)",
    "VAEEncodeTiled": "VAE encode (tiled)",
    "KSampler": "sampler",
    "DualCLIPLoader": "text encoder loader",
}


def _friendly_comfy_node(class_type: str) -> str:
    return _COMFY_NODE_LABELS.get(class_type, class_type.replace("_", " "))


def _summarize_comfy_node_issue(class_type: str, err: Mapping[str, Any]) -> dict[str, str]:
    err_type = str(err.get("type") or "")
    extra = err.get("extra_info")
    extra_map = extra if isinstance(extra, Mapping) else {}
    details = str(
        err.get("details")
        or extra_map.get("input_name")
        or extra_map.get("input")
        or ""
    ).strip()
    if err_type == "required_input_missing" and details:
        issue = f"missing required input: {details}"
    elif err_type == "invalid_input_type" and details:
        issue = f"invalid input: {details}"
    else:
        issue = str(err.get("message") or err_type or "validation failed").strip()
    out = {
        "node": class_type,
        "node_label": _friendly_comfy_node(class_type),
        "issue": issue,
    }
    if details:
        out["input"] = details
    return out


def _looks_technical_error_message(msg: str) -> bool:
    text = msg.strip()
    if not text:
        return False
    if text.startswith("Comfy HTTP "):
        return True
    lowered = text.lower()
    if any(
        token in lowered
        for token in (
            "prompt_outputs_failed_validation",
            "node_errors",
            "required_input_missing",
            "traceback (most recent call last)",
        )
    ):
        return True
    if text.startswith("{") and '"error"' in text:
        return True
    return len(text) > 280 and ('"class_type"' in text or '"node_errors"' in text)


def _try_parse_comfy_http_validation(msg: str) -> dict[str, Any] | None:
    if "{" not in msg:
        return None
    json_start = msg.find("{")
    try:
        payload = json.loads(msg[json_start:])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, Mapping):
        return None

    node_errors = payload.get("node_errors")
    issues: list[dict[str, str]] = []
    if isinstance(node_errors, Mapping):
        for node_blob in node_errors.values():
            if not isinstance(node_blob, Mapping):
                continue
            class_type = str(node_blob.get("class_type") or "unknown")
            for item in node_blob.get("errors") or []:
                if isinstance(item, Mapping):
                    issues.append(_summarize_comfy_node_issue(class_type, item))

    err = payload.get("error")
    err_type = str(err.get("type") or "") if isinstance(err, Mapping) else ""
    if not issues and err_type != "prompt_outputs_failed_validation":
        return None

    if issues:
        first = issues[0]
        if first.get("node") == "VAEDecodeTiled" and first.get("input") in {
            "overlap",
            "temporal_size",
            "temporal_overlap",
        }:
            summary = (
                "DreamForge's tiled VAE decode step doesn't match your ComfyUI version — "
                f"a required setting ({first['input']}) is missing."
            )
        elif first.get("node") == "CLIPLoader" and "krea2" in str(first.get("input") or ""):
            summary = (
                "Krea 2 requires ComfyUI v0.26.0 or newer — the GPU engine is running an older "
                "ComfyUI that does not support CLIPLoader type 'krea2'."
            )
        else:
            summary = (
                "ComfyUI rejected the generation graph before sampling started: "
                f"{first['node_label']} — {first['issue']}."
            )
    else:
        summary = "ComfyUI rejected the generation graph before sampling could start."

    suggestions: list[str] | None = None
    if issues and issues[0].get("node") == "CLIPLoader" and "krea2" in str(
        issues[0].get("input") or ""
    ):
        suggestions = [
            "Restart the GPU engine so DreamForge can update ComfyUI to v0.26.0.",
            "If the problem persists, use Settings to reinstall or update the Comfy backend.",
            "Confirm qwen3vl_4b_fp8_scaled.safetensors is in text_encoders/ before generating.",
        ]

    return {
        "summary": summary,
        "suggestions": suggestions,
        "details": {
            "comfy_validation": dict(payload),
            "node_issues": issues,
            "raw_exception": msg,
        },
    }


_COMFY_DEPENDENCY_HINTS = (
    "locate the file on the hub",
    "local cache",
    "cannot find the requested files",
    "huggingface.co",
    "connection and try again",
    "no such file or directory",
    "filenotfounderror",
)


def _is_clip_checkpoint_mismatch(msg_lower: str) -> bool:
    """KSampler matmul / CLIP-loader tips mean wrong text encoder for the UNet."""
    if "mat1 and mat2 shapes cannot be multiplied" in msg_lower:
        return True
    if "shapes cannot be multiplied" in msg_lower and "ksampler" in msg_lower:
        return True
    if "make sure the correct file(s) and type is selected" in msg_lower:
        return True
    if "clip loader" in msg_lower and "ksampler" in msg_lower:
        return True
    return False


def _try_missing_annotator_weights(msg: str, *, job_id: str | None = None) -> dict | None:
    """Map missing preprocessor weights (HF hub / cache failures) to companion downloads."""
    msg_lower = msg.lower()
    if not any(hint in msg_lower for hint in _COMFY_DEPENDENCY_HINTS):
        return None

    missing_nodes: list[str] = []
    for match in re.finditer(r"([A-Za-z0-9]+Preprocessor)", msg):
        node = match.group(1).strip()
        if node and node not in missing_nodes:
            missing_nodes.append(node)
    if "depth_anything" in msg_lower or "depthanythingv2" in msg_lower:
        if "DepthAnythingV2Preprocessor" not in missing_nodes:
            missing_nodes.append("DepthAnythingV2Preprocessor")
    if "sk_model" in msg_lower or "lineartstandard" in msg_lower:
        if "LineartStandardPreprocessor" not in missing_nodes:
            missing_nodes.append("LineartStandardPreprocessor")
    if not missing_nodes:
        return None

    try:
        from dreamforge_comfy_manager import missing_workflow_model_entries

        missing = missing_workflow_model_entries(missing_nodes=missing_nodes)
    except Exception:
        missing = []
    if not missing:
        return None

    catalog_ids = [str(item.get("catalog_id") or item.get("id") or "") for item in missing]
    catalog_ids = [item for item in catalog_ids if item]
    actions = [
        {
            "action": "download_model_companions",
            "missing": missing,
            "catalog_ids": catalog_ids,
            "hint": "Download annotator weights into ComfyUI before retrying.",
        }
    ]
    return missing_model_dependencies(missing, job_id=job_id, actions=actions)


def from_exception(exc: BaseException, *, job_id: str | None = None) -> dict:
    """Map an arbitrary exception onto the closest structured code.

    This is the catch-all used by ``run_generation``'s outer ``except``.
    The exception's repr is preserved in ``details.exception`` so we
    keep the full diagnostic trail.
    """

    name = type(exc).__name__
    msg = str(exc).strip() or name
    exc_details = getattr(exc, "details", None)
    if not isinstance(exc_details, Mapping):
        exc_details = None

    # torch OutOfMemoryError comes through here on backends where the
    # specific OOM class isn't directly importable at module load time.
    msg_lower = msg.lower()
    winerror = getattr(exc, "winerror", None)
    if (
        winerror == 1455
        or "paging file is too small" in msg_lower
        or "os error 1455" in msg_lower
    ):
        return virtual_memory_low(f"{name}: {msg}", job_id=job_id)

    try:
        from dreamforge_comfy_client import is_comfy_oom_error

        oom_like = is_comfy_oom_error(msg)
    except Exception:
        oom_like = False
    if "OutOfMemoryError" in name or "cuda out of memory" in msg_lower or oom_like:
        details = {"exception": f"{name}: {msg}"}
        payload = out_of_memory(job_id=job_id)
        payload.setdefault("details", {}).update(details)
        payload["failure_report"] = build_failure_report(
            payload["code"],
            payload["message"],
            details=payload.get("details"),
            recoverable=payload.get("recoverable"),
        )
        return payload

    # ComfyUI server became unreachable (crashed, OOM-killed, driver reset).
    if "vae is invalid" in msg_lower and "none" in msg_lower:
        return error(
            "invalid_request",
            "ComfyUI received an empty VAE while encoding the input image.",
            suggestions=[
                "Restart the GPU engine so ComfyUI refreshes the visible VAE list.",
                "For Qwen edits, make sure qwen_image_vae.safetensors is visible under models/vae.",
                "Use a Qwen edit-capable local model or keep DreamForge's Qwen edit workflow selected.",
            ],
            details={"exception": f"{name}: {msg}"},
            recoverable=True,
            job_id=job_id,
        )
    if "int8_tensorwise" in msg_lower and ("keyerror" in msg_lower or name == "KeyError"):
        return error(
            "unsupported_model_format",
            "This ConvRot INT8 model needs newer ComfyUI quantization support.",
            suggestions=[
                "For Krea 2 editing, select the installed krea2TurboFP8_krea2TURBO.safetensors model.",
                "ConvRot INT8 requires a compatible ComfyUI and comfy-kitchen update; restarting the same engine is not enough.",
            ],
            details={"exception": f"{name}: {msg}"},
            recoverable=True,
            job_id=job_id,
        )
    if "float4_e2m1fn_x2" in msg_lower:
        return error(
            "unsupported_model_format",
            "This NVFP4 model needs a newer local Torch runtime with FP4 dtype support.",
            suggestions=[
                "Use the installed Qwen fp8 or GGUF edit model for this run.",
                "Update the embedded local Torch/Comfy runtime to a build that provides torch.float4_e2m1fn_x2.",
                "Restart the GPU engine after changing the runtime.",
            ],
            details={
                "exception": f"{name}: {msg}",
                "required_torch_attribute": "float4_e2m1fn_x2",
            },
            recoverable=True,
            job_id=job_id,
        )
    if "ultimatesdupscale" in msg_lower and "too many values to unpack" in msg_lower:
        return error(
            "unsupported_model_for_workflow",
            "Ultimate SD Upscale failed with this checkpoint — SDXL models work best.",
            suggestions=[
                "Switch to an SDXL checkpoint such as EpicRealism XL or Juggernaut XL.",
                "Leave the prompt empty for faithful upscale, or use light detail keywords only.",
                "Avoid Z-Image, Ideogram, or Flux split-loader checkpoints for Ultimate SD Upscale.",
            ],
            details={"exception": f"{name}: {msg}", "workflow": "ultimate_sd_upscale"},
            recoverable=True,
            job_id=job_id,
        )
    missing_nodes = _extract_missing_node_types(msg, exc_details)
    if missing_nodes:
        try:
            from dreamforge_workflow_planner import resolve_pack_id_for_nodes

            pack_id = resolve_pack_id_for_nodes(missing_nodes) or "unknown"
        except Exception:
            pack_id = "unknown"
        return missing_custom_node_pack(pack_id, nodes=missing_nodes, job_id=job_id)

    workflow_class_match = re.search(
        r"(?:unsupported|unknown|invalid)\s+workflow\s+(?:class|kind|mode)[:= ]+['\"]?([A-Za-z0-9_ .:-]+)",
        msg,
        flags=re.IGNORECASE,
    )
    if workflow_class_match:
        return unsupported_workflow_class(workflow_class_match.group(1).strip(" '\"."), msg, job_id=job_id)

    winerror = getattr(exc, "winerror", None)
    if (
        winerror == 1455
        or "paging file is too small" in msg_lower
        or "os error 1455" in msg_lower
    ):
        return virtual_memory_low(f"{name}: {msg}", job_id=job_id)

    annotator_payload = _try_missing_annotator_weights(msg, job_id=job_id)
    if annotator_payload is not None:
        return annotator_payload

    if "controlnet" in msg_lower and "needs a vae" in msg_lower:
        return comfy_workflow_validation(
            "ControlNet Union needs the checkpoint VAE connected on the ControlNet apply nodes.",
            suggestions=[
                "Restart the GPU engine so DreamForge loads the updated Portrait Master / Photo Restore graph.",
                "Use an SDXL checkpoint with a bundled VAE (EpicRealism XL, Juggernaut XL, etc.).",
                "Confirm the ControlNet Union model is installed under models/controlnet/.",
            ],
            details={
                "exception": f"{name}: {msg}",
                "node_issues": [
                    {
                        "node": "ControlNetApplyAdvanced",
                        "issue": "Missing required VAE input for ControlNet Union",
                    }
                ],
            },
            job_id=job_id,
        )

    if _is_clip_checkpoint_mismatch(msg_lower):
        return error(
            "unsupported_model_for_workflow",
            "The SDXL checkpoint and ControlNet model do not match for this workflow.",
            suggestions=[
                "Portrait Master and Photo Restore need SDXL ControlNet Union (not SD 1.5 ControlNet).",
                "Install xinsir-controlnet-union-sdxl-1.0-promax.safetensors under models/controlnet/.",
                "Keep EpicRealism XL or another SDXL checkpoint selected in the model picker.",
                "Remove SD 1.5 LoRAs; restart the GPU engine after changing ControlNet or checkpoint.",
            ],
            details={
                "exception": f"{name}: {msg}",
                "issue": "sdxl_controlnet_checkpoint_mismatch",
            },
            recoverable=True,
            job_id=job_id,
        )

    _comfy_crash_hints = (
        "connection could be made because the target machine actively refused",
        "comfyui server became unreachable",
        "no connection could be made",
        "[winerror 10061]",
        "connection refused",
        "[errno 111]",
    )
    if any(hint in msg_lower for hint in _comfy_crash_hints):
        return error(
            "comfy_server_crashed",
            _COMFY_CRASH_MESSAGE,
            suggestions=_comfy_crash_suggestions(),
            details={"exception": f"{name}: {msg}"},
            recoverable=True,
            job_id=job_id,
        )

    if isinstance(exc, OSError) and getattr(exc, "errno", None) in {28,}:
        # ENOSPC -> disk full
        return disk_full(msg, path=getattr(exc, "filename", None), job_id=job_id)

    if isinstance(exc, FileNotFoundError):
        return error(
            "model_not_found" if "model" in msg.lower() else "file_not_found",
            msg,
            details={"exception": f"{name}: {msg}", "filename": getattr(exc, "filename", None)},
            recoverable=False,
            job_id=job_id,
        )

    parsed_validation = _try_parse_comfy_http_validation(msg)
    if parsed_validation is not None:
        return comfy_workflow_validation(
            parsed_validation["summary"],
            suggestions=parsed_validation.get("suggestions"),
            details=parsed_validation["details"],
            job_id=job_id,
        )

    display_msg = msg
    if _looks_technical_error_message(msg):
        display_msg = "Something went wrong during generation."

    return error(
        "generation_failed",
        display_msg,
        suggestions=[
            "Click 'Restart GPU engine' and try again.",
            "Open Technical diagnostics or worker.log for the underlying traceback.",
        ],
        details={"exception": f"{name}: {msg}"},
        recoverable=True,
        job_id=job_id,
    )


def model_corrupt(
    model_name: str,
    path: str | Path | None = None,
    details: Mapping[str, Any] | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    return error(
        "model_corrupt",
        f"Model file '{model_name}' is corrupt or unreadable.",
        suggestions=[
            f"Run 'dreamforge models health' or 'dreamforge repair' to purge damaged files.",
            f"Re-download {model_name} using the Model Downloader.",
        ],
        details={"model_name": model_name, "path": str(path) if path else None, **dict(details or {})},
        recoverable=True,
        job_id=job_id,
    )


def download_failed(
    url: str,
    reason: str,
    job_id: str | None = None,
) -> dict[str, Any]:
    return error(
        "download_failed",
        f"Failed to download model from {url}: {reason}",
        suggestions=[
            "Verify your internet connection.",
            "If downloading from CivitAI, check if a CIVITAI_API_KEY is required for gated assets.",
            "Retry the download from the Model Downloader UI or CLI.",
        ],
        details={"url": url, "reason": reason},
        recoverable=True,
        job_id=job_id,
    )

