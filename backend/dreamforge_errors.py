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

from typing import Any, Iterable, Mapping


__all__ = [
    "error",
    "out_of_memory",
    "missing_input_image",
    "invalid_input_image",
    "missing_model_dependencies",
    "model_not_found",
    "model_file_unreadable",
    "unsupported_model_format",
    "disk_full",
    "worker_crashed",
    "generation_cancelled",
    "generation_in_progress",
    "invalid_request",
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
    return out


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


def missing_model_dependencies(
    missing: list[Mapping[str, Any]],
    *,
    job_id: str | None = None,
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
        details={"missing": list(missing)},
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


def from_exception(exc: BaseException, *, job_id: str | None = None) -> dict:
    """Map an arbitrary exception onto the closest structured code.

    This is the catch-all used by ``run_generation``'s outer ``except``.
    The exception's repr is preserved in ``details.exception`` so we
    keep the full diagnostic trail.
    """

    name = type(exc).__name__
    msg = str(exc).strip() or name

    # torch OutOfMemoryError comes through here on backends where the
    # specific OOM class isn't directly importable at module load time.
    if "OutOfMemoryError" in name or "cuda out of memory" in msg.lower():
        details = {"exception": f"{name}: {msg}"}
        payload = out_of_memory(job_id=job_id)
        payload.setdefault("details", {}).update(details)
        return payload

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
