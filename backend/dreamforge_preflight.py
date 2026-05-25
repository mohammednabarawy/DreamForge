"""Preflight checks run *before* sampling starts.

The goal: fail fast (and with a structured error) when we already know the
generation will not succeed, and surface non-fatal warnings (VRAM headroom,
low disk space) so the UI can show a clear message instead of letting the
user wait several seconds only to hit a torch.cuda.OutOfMemoryError.

Each result is a list of dicts that conform to the
:func:`dreamforge_errors.error` shape, with ``type`` set to either
``"error"`` (hard stop) or ``"warning"`` (advisory).
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping

from _paths import BACKEND_ROOT, PROJECT_ROOT
from dreamforge_errors import (
    disk_full,
    error,
    model_file_unreadable,
    model_not_found,
)


__all__ = [
    "PreflightResult",
    "run_preflight",
]


MODELS_ROOT = BACKEND_ROOT / "models"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs"
# Hard floor below which we refuse to start; the manifest + output alone is
# usually a few MB but writing an 8K upscale can hit 100 MB.
_DISK_FREE_FLOOR_GB = 0.5
# Soft warning if free space dips below this; non-fatal.
_DISK_FREE_WARN_GB = 2.0


def _safetensors_can_open(path: Path) -> str | None:
    """Best-effort sanity check: return error string if header is unreadable."""

    try:
        with path.open("rb") as fh:
            head = fh.read(8)
    except OSError as exc:
        return f"open failed: {exc}"
    if len(head) < 8:
        return "file is shorter than 8 bytes (truncated)"
    length = int.from_bytes(head, "little")
    if length <= 0 or length > 64 * 1024 * 1024:
        # Header longer than 64 MB is almost certainly garbage.
        return f"safetensors header length looks corrupt ({length} bytes)"
    return None


def _model_path_candidates(model: Mapping[str, Any]) -> list[Path]:
    candidates: list[Path] = []
    name = model.get("name") or model.get("engine_name") or ""
    rel = model.get("relative_path") or name
    category = model.get("category")
    if category:
        candidates.append(MODELS_ROOT / category / rel)
    # The model dict from resolve_model_name often carries an absolute path.
    abs_path = model.get("path") or model.get("absolute_path")
    if isinstance(abs_path, str) and abs_path:
        candidates.append(Path(abs_path))
    # Fallback: just under models_root with the bare name.
    if name:
        candidates.append(MODELS_ROOT / name)
    # Dedup while preserving order.
    seen: set[str] = set()
    unique: list[Path] = []
    for p in candidates:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    return unique


def _resolve_model_path(model: Mapping[str, Any]) -> Path | None:
    for candidate in _model_path_candidates(model):
        if candidate.is_file():
            return candidate
    return None


def _estimate_required_gb(model: Mapping[str, Any]) -> float | None:
    """Rough VRAM estimate for the active model.

    These multipliers come from empirical Fooocus/Forge/ComfyUI measurements;
    they're intentionally conservative.  Returns ``None`` when we don't have
    enough info to estimate.
    """

    size_mb = model.get("size_mb") or model.get("size")
    if not size_mb:
        return None
    try:
        size_gb = float(size_mb) / 1024.0
    except (TypeError, ValueError):
        return None
    family = str(model.get("family") or "").lower()
    multiplier = 1.6  # baseline overhead (activations + samplers)
    if family.startswith("flux"):
        multiplier = 1.7
    elif family.startswith("hidream"):
        multiplier = 1.8
    elif family.startswith("qwen"):
        multiplier = 1.7
    elif family.startswith("sd3"):
        multiplier = 1.6
    elif family in {"sdxl", "sdxl_inpaint"}:
        multiplier = 1.5
    elif family == "sd15":
        multiplier = 1.3
    return round(size_gb * multiplier, 2)


def _free_vram_gb() -> float | None:
    try:
        import torch  # local import; not required when called from CLI
        if torch.cuda.is_available():
            free, _total = torch.cuda.mem_get_info()
            return free / (1024 ** 3)
    except Exception:
        return None
    return None


def _disk_free_gb(path: Path) -> float | None:
    try:
        return shutil.disk_usage(path).free / (1024 ** 3)
    except OSError:
        return None


class PreflightResult:
    """Container for preflight events.

    ``errors`` are hard stops; the caller should abort generation.
    ``warnings`` are advisory; the caller should emit them on the stream
    but proceed.
    """

    __slots__ = ("errors", "warnings", "info")

    def __init__(self) -> None:
        self.errors: list[dict] = []
        self.warnings: list[dict] = []
        self.info: dict[str, Any] = {}

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def all_events(self) -> Iterable[dict]:
        yield from self.warnings
        yield from self.errors

    def as_dict(self) -> dict:
        return {
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "info": dict(self.info),
        }


def run_preflight(
    model: Mapping[str, Any],
    *,
    output_dir: Path | str | None = None,
    job_id: str | None = None,
) -> PreflightResult:
    """Run cheap checks before sampling.

    * **Model exists & is readable** - hard error.
    * **Disk free space** - hard error if below the floor, warning under
      the soft threshold.
    * **VRAM headroom** - warning only; the GPU profile decides the final
      verdict.

    Companion-file checks are handled separately by
    ``check_model_dependencies`` because they need the full model dict +
    family-specific manifests.
    """

    result = PreflightResult()
    name = model.get("name") or model.get("engine_name") or "<unknown model>"

    # 1) Model exists.
    path = _resolve_model_path(model)
    if path is None:
        result.errors.append(model_not_found(name, job_id=job_id))
        return result  # nothing else makes sense without a model file.

    result.info["model_path"] = str(path)

    # 2) Model is readable (safetensors header sanity).
    if path.suffix.lower() == ".safetensors":
        issue = _safetensors_can_open(path)
        if issue:
            result.errors.append(model_file_unreadable(name, issue, job_id=job_id))
            return result

    # 3) Disk space on the output directory.
    out_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_ROOT
    out_root.parent.mkdir(parents=True, exist_ok=True) if not out_root.parent.exists() else None
    free_gb = _disk_free_gb(out_root if out_root.exists() else out_root.parent)
    if free_gb is not None:
        result.info["disk_free_gb"] = round(free_gb, 2)
        if free_gb < _DISK_FREE_FLOOR_GB:
            result.errors.append(
                disk_full(
                    f"Only {free_gb:.2f} GB free on {out_root}",
                    path=str(out_root),
                    job_id=job_id,
                )
            )
            return result
        if free_gb < _DISK_FREE_WARN_GB:
            result.warnings.append(
                error(
                    "low_disk_space",
                    f"Only {free_gb:.2f} GB free on {out_root}; "
                    "consider freeing space before generating large outputs.",
                    suggestions=[
                        "Move the outputs/ folder to a larger disk.",
                        "Delete old outputs you no longer need.",
                    ],
                    details={"free_gb": round(free_gb, 2), "path": str(out_root)},
                    recoverable=True,
                    job_id=job_id,
                )
            )

    # 4) VRAM hint.
    estimated = _estimate_required_gb(model)
    free_vram = _free_vram_gb()
    if estimated is not None:
        result.info["estimated_vram_gb"] = estimated
    if free_vram is not None:
        result.info["free_vram_gb"] = round(free_vram, 2)
    if estimated is not None and free_vram is not None and estimated > free_vram + 0.5:
        result.warnings.append(
            error(
                "vram_headroom_low",
                (
                    f"Model {name} typically needs ~{estimated:.1f} GB VRAM, "
                    f"but only {free_vram:.1f} GB is free. The run may OOM."
                ),
                suggestions=[
                    "Switch the VRAM profile to 'low' or 'no' in Settings.",
                    "Lower the resolution.",
                    "Use a quantized variant of the model (fp8 / Q4_K).",
                ],
                details={
                    "estimated_vram_gb": estimated,
                    "free_vram_gb": round(free_vram, 2),
                    "model": name,
                },
                recoverable=True,
                job_id=job_id,
            )
        )

    # Convert all warnings to type=="warning" (errors keep type=="error").
    for w in result.warnings:
        w["type"] = "warning"

    return result
