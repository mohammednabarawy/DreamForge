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
    "comfy_server_crashed",
    "generation_cancelled",
    "generation_in_progress",
    "invalid_request",
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
        add("replace_node_pattern", approval=True, nodes=nodes, hint="Rebuild this stage with a first-party fallback pattern when possible.")
        add(
            "install_custom_node_pack",
            approval=True,
            pack_id=pack_id,
            nodes=nodes,
            hint="Install custom nodes only after the user approves the exact pack.",
        )
        add("disable_optional_stage", approval=True, nodes=nodes)
    elif code == "missing_model_dependencies":
        recommended = list(detail_map.get("recommended_actions") or [])
        for item in recommended:
            if isinstance(item, Mapping):
                payload = dict(item)
                payload["requires_approval"] = True
                actions.append(payload)
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
        "Lower the resolution (try 1024x1024 or smaller).",
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
    node_hint = ""
    if nodes:
        node_hint = f" (nodes: {', '.join(str(n) for n in nodes)})"
    return error(
        "missing_custom_node_pack",
        f"Required ComfyUI custom node pack is not installed: {pack_id}{node_hint}",
        suggestions=[
            "Install the pack into ComfyUI/custom_nodes using the Models panel or Krita recipe installer.",
            "Restart ComfyUI after installing custom nodes.",
            "Use Brain plan readiness to review required dependencies before running.",
        ],
        details={"pack_id": pack_id, "nodes": list(nodes or [])},
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
            "Open the Models panel and click 'Download missing companions'.",
            "Or place the listed files into backend/models/{vae,text_encoders,clip_vision}.",
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


def comfy_server_crashed(detail: str = "", *, job_id: str | None = None) -> dict:
    return error(
        "comfy_server_crashed",
        "ComfyUI server crashed or became unreachable during generation. "
        "This usually means it ran out of GPU memory (OOM) after sampling finished.",
        suggestions=[
            "Click 'Restart GPU engine' to relaunch ComfyUI and try again.",
            "Lower the resolution (try 1024\u00d71024 or smaller).",
            "Switch to a quantized model (fp8, Q4_K) to reduce VRAM usage.",
            "Close other GPU apps (browsers, games, video editors).",
            "Check worker.log and comfy.server.log for the underlying traceback.",
        ],
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


def invalid_request(detail: str, *, job_id: str | None = None) -> dict:
    return error(
        "invalid_request",
        f"Invalid generation request: {detail}",
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
            for key in ("node_type", "class_type"):
                value = str(payload.get(key) or "").strip()
                if value and value not in nodes:
                    nodes.append(value)
    return nodes


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
    if "OutOfMemoryError" in name or "cuda out of memory" in msg.lower():
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
    msg_lower = msg.lower()
    missing_nodes = _extract_missing_node_types(msg, exc_details)
    if missing_nodes:
        return missing_custom_node_pack("unknown", nodes=missing_nodes, job_id=job_id)

    workflow_class_match = re.search(
        r"(?:unsupported|unknown|invalid)\s+workflow\s+(?:class|kind|mode)[:= ]+['\"]?([A-Za-z0-9_ .:-]+)",
        msg,
        flags=re.IGNORECASE,
    )
    if workflow_class_match:
        return unsupported_workflow_class(workflow_class_match.group(1).strip(" '\"."), msg, job_id=job_id)

    _comfy_crash_hints = (
        "connection could be made because the target machine actively refused",
        "comfyui server became unreachable",
        "no connection could be made",
        "[winerror 10061]",
        "connection refused",
        "[errno 111]",
    )
    if any(hint in msg_lower for hint in _comfy_crash_hints) or name == "ComfyExecutionError":
        return error(
            "comfy_server_crashed",
            "ComfyUI server crashed or became unreachable during generation. "
            "This usually means it ran out of GPU memory (OOM) after sampling finished.",
            suggestions=[
                "Click 'Restart GPU engine' to relaunch ComfyUI and try again.",
                "Lower the resolution (try 1024×1024 or smaller).",
                "Switch to a quantized model (fp8, Q4_K) to reduce VRAM usage.",
                "Close other GPU apps (browsers, games, video editors).",
                "Check worker.log and comfy.server.log for the underlying traceback.",
            ],
            details={"exception": f"{name}: {msg}"},
            recoverable=True,
            job_id=job_id,
        )

    winerror = getattr(exc, "winerror", None)
    if (
        winerror == 1455
        or "paging file is too small" in msg.lower()
        or "os error 1455" in msg.lower()
    ):
        return virtual_memory_low(f"{name}: {msg}", job_id=job_id)

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

    return error(
        "generation_failed",
        msg,
        suggestions=[
            "Click 'Restart GPU engine' and try again.",
            "Check worker.log for the underlying traceback.",
        ],
        details={"exception": f"{name}: {msg}"},
        recoverable=True,
        job_id=job_id,
    )
