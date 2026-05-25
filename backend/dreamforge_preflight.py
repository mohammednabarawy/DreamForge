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

import os
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

from _paths import BACKEND_ROOT, PROJECT_ROOT
from dreamforge_errors import (
    disk_full,
    error,
    model_file_unreadable,
    model_not_found,
    virtual_memory_low,
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


def _model_basename(model: Mapping[str, Any]) -> str:
    return str(
        model.get("name")
        or model.get("engine_name")
        or model.get("relative_path")
        or ""
    )


def _is_unet_only_family(name: str, family: str) -> bool:
    """True when DreamForge routes through the lighter diffusion-model loader."""
    low = name.lower()
    fam = family.lower()
    if "hidream_o1" in low or "hidream-o1" in low or fam == "hidream_o1":
        return False
    if fam.startswith("flux") or "flux" in low:
        return True
    if fam.startswith("qwen") or "qwen_image" in low:
        return True
    if fam.startswith("hidream") or "hidream" in low:
        return True
    if fam == "wan" or "wan" in low:
        return True
    if ".gguf" in low:
        return True
    return False


def _estimate_required_vram_gb(model: Mapping[str, Any]) -> float | None:
    """Rough peak VRAM for a 1024x1024 run with --lowvram / --cpu-vae.

    Uses published ComfyUI / Flux community measurements (fp8 ~12-16 GB on
    16 GB cards) rather than ``file_size * multiplier``, which falsely claims
    a 16 GB fp8 file needs ~20 GB VRAM.
    """

    size_mb = model.get("size_mb") or model.get("size")
    if not size_mb:
        return None
    try:
        size_gb = float(size_mb) / 1024.0
    except (TypeError, ValueError):
        return None

    name = _model_basename(model)
    low = name.lower()
    family = str(model.get("family") or "").lower()

    if ".gguf" in low or any(tag in low for tag in ("q2_", "q3_", "q4_", "q5_", "q6_", "q8_")):
        # GGUF file size tracks VRAM closely (Apatero / city96 guides).
        return round(size_gb * 1.1 + 1.5, 2)

    if "fp8" in low or "e4m3" in low or "e5m2" in low or "nf4" in low:
        if family.startswith("flux") or "flux" in low:
            # 12-16 GB real-world; schnell + lowvram sits at the low end.
            return round(min(size_gb * 0.72 + 2.5, 14.5), 2)
        return round(size_gb * 0.75 + 2.0, 2)

    if family.startswith("flux") or "flux" in low:
        return 24.0 if size_gb > 18 else round(size_gb * 0.9 + 4.0, 2)

    multiplier = 1.6
    if family.startswith("hidream"):
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


def _estimate_peak_system_ram_gb(model: Mapping[str, Any], file_size_gb: float) -> float:
    """Peak *committed* system memory during model load (not peak VRAM).

    UNet-only Flux uses ``load_diffusion_model`` (streaming) plus T5/CLIP on
    CPU with --lowvram.  Peak is dominated by the text encoder (~5-10 GB), not
    the full checkpoint file size.
    """
    name = _model_basename(model)
    family = str(model.get("family") or "").lower()
    low = name.lower()

    if _is_unet_only_family(name, family):
        # T5: assume fp8 encoder when the UNet is fp8 (typical DreamForge layout).
        t5_gb = 5.0 if ("fp8" in low or "e4m3" in low) else 9.5
        if ".gguf" in low:
            unet_load_gb = file_size_gb * 0.35 + 1.0
        elif "fp8" in low:
            unet_load_gb = min(file_size_gb * 0.35, 6.0) + 1.5
        else:
            unet_load_gb = min(file_size_gb * 0.45, 8.0) + 2.0
        return round(t5_gb + unet_load_gb + 1.0, 2)  # +1 clip/vae/buffers

    # Legacy all-in-one checkpoint path (full file into RAM first).
    return round(file_size_gb * 1.55, 2)


def _memory_status() -> dict[str, float | None]:
    """Physical RAM and Windows commit budget (RAM + page file)."""
    out: dict[str, float | None] = {
        "total_phys_gb": None,
        "avail_phys_gb": None,
        "commit_limit_gb": None,
        "avail_commit_gb": None,
    }
    try:
        import psutil  # type: ignore

        vm = psutil.virtual_memory()
        out["total_phys_gb"] = vm.total / (1024 ** 3)
        out["avail_phys_gb"] = vm.available / (1024 ** 3)
        # psutil has no commit limit on all platforms; fill on Windows below.
    except Exception:
        pass

    if sys.platform == "win32":
        try:
            import ctypes

            class _MS(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            info = _MS()
            info.dwLength = ctypes.sizeof(_MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(info))  # type: ignore[attr-defined]
            out["total_phys_gb"] = info.ullTotalPhys / (1024 ** 3)
            out["avail_phys_gb"] = info.ullAvailPhys / (1024 ** 3)
            out["commit_limit_gb"] = info.ullTotalPageFile / (1024 ** 3)
            out["avail_commit_gb"] = info.ullAvailPageFile / (1024 ** 3)
        except Exception:
            pass

    return out


def _model_size_gb_from_path(path: Path) -> float | None:
    try:
        return path.stat().st_size / (1024 ** 3)
    except OSError:
        return None


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

    # 4) System memory / commit budget (RAM + page file on Windows).
    mem = _memory_status()
    total_ram = mem.get("total_phys_gb")
    avail_ram = mem.get("avail_phys_gb")
    avail_commit = mem.get("avail_commit_gb")
    commit_limit = mem.get("commit_limit_gb")
    if total_ram is not None:
        result.info["system_ram_gb"] = round(total_ram, 2)
    if avail_ram is not None:
        result.info["available_ram_gb"] = round(avail_ram, 2)
    if commit_limit is not None:
        result.info["commit_limit_gb"] = round(commit_limit, 2)
    if avail_commit is not None:
        result.info["available_commit_gb"] = round(avail_commit, 2)

    file_size_gb = _model_size_gb_from_path(path)
    if file_size_gb is not None:
        result.info["model_file_gb"] = round(file_size_gb, 2)

    if file_size_gb is not None:
        needed_ram = _estimate_peak_system_ram_gb(model, file_size_gb)
        result.info["estimated_peak_ram_gb"] = needed_ram
        # Prefer Windows commit budget (RAM + page file).  A machine with
        # 9 GB free physical RAM but 40+ GB commit available is fine.
        budget_gb = avail_commit if avail_commit is not None else avail_ram
        budget_label = "virtual memory (RAM + page file)" if avail_commit is not None else "system RAM"
        if budget_gb is not None and budget_gb + 0.75 < needed_ram:
            suggestions = [
                f"Close other apps until at least {needed_ram:.1f} GB of {budget_label} is available.",
                "Switch to a smaller / quantized variant (fp8, GGUF Q4/Q5) or to SDXL for this run.",
                "Set VRAM profile to 8 GB or 5 GB to enable --cpu-vae and reduce peak load.",
            ]
            if (
                sys.platform == "win32"
                and commit_limit is not None
                and total_ram is not None
                and commit_limit < (total_ram + needed_ram)
            ):
                suggestions.append(
                    "Increase the Windows paging file: Settings → System → About → "
                    "Advanced system settings → Performance Settings → Advanced → "
                    "Virtual memory → Change. Recommended max: at least "
                    f"{int((total_ram + needed_ram) * 1.5)} MB on a drive with free space, then reboot."
                )
            result.warnings.append(
                error(
                    "low_system_ram",
                    (
                        f"About {budget_gb:.1f} GB of {budget_label} is available, but loading "
                        f"{name} may need up to ~{needed_ram:.1f} GB during startup "
                        "(mostly the T5 text encoder on CPU). "
                        "If load fails, you may see WinError 1455."
                    ),
                    suggestions=suggestions,
                    details={
                        "model": name,
                        "model_file_gb": round(file_size_gb, 2),
                        "available_ram_gb": round(avail_ram, 2) if avail_ram is not None else None,
                        "available_commit_gb": round(avail_commit, 2) if avail_commit is not None else None,
                        "needed_ram_gb": needed_ram,
                        "loader": "unet_only" if _is_unet_only_family(_model_basename(model), str(model.get("family") or "")) else "checkpoint",
                    },
                    recoverable=True,
                    job_id=job_id,
                )
            )

    # 5) VRAM hint (generation phase, not load phase).
    estimated = _estimate_required_vram_gb(model)
    free_vram = _free_vram_gb()
    if estimated is not None:
        result.info["estimated_vram_gb"] = estimated
    if free_vram is not None:
        result.info["free_vram_gb"] = round(free_vram, 2)
    # Only warn when we are genuinely short — 16 GB cards with ~15 GB free
    # and a ~12 GB fp8 Flux estimate should proceed without noise.
    if estimated is not None and free_vram is not None and estimated > free_vram + 1.0:
        result.warnings.append(
            error(
                "vram_headroom_low",
                (
                    f"At 1024×1024 this model may need ~{estimated:.1f} GB VRAM "
                    f"(with low-VRAM offload), but only {free_vram:.1f} GB is free. "
                    "Generation might still work at a lower resolution."
                ),
                suggestions=[
                    "Switch the VRAM profile to 'low' or 'no' in Settings.",
                    "Lower the resolution (try 768×768).",
                    "Use a GGUF Q5/Q4 variant if you have one installed.",
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
