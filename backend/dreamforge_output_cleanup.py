"""Hard-delete generation artifacts from every DreamForge storage location."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from _paths import (
    BACKEND_ROOT,
    COMFY_STAGING_DIR,
    OUTPUTS_ROOT,
    PREVIEWS_DIR,
    PROJECT_ROOT,
    resolve_comfy_root,
)

BACKEND_LEGACY_OUTPUTS = BACKEND_ROOT / "outputs"
BACKEND_LEGACY_PREVIEWS = BACKEND_ROOT / "temp" / "previews"
COMFY_OUTPUT_DIR = resolve_comfy_root() / "output"
COMFY_INPUT_DIR = resolve_comfy_root() / "input"
_STALE_DELETED_INDEX = OUTPUTS_ROOT / ".deleted_generations.json"

_DREAMFORGE_SEQ_RE = re.compile(r"^DreamForge_(\d+)", re.IGNORECASE)

_ALLOWED_DELETE_ROOTS: list[Path] = []


def _allowed_delete_roots() -> list[Path]:
    global _ALLOWED_DELETE_ROOTS
    if _ALLOWED_DELETE_ROOTS:
        return _ALLOWED_DELETE_ROOTS
    roots = [
        OUTPUTS_ROOT,
        PREVIEWS_DIR,
        COMFY_STAGING_DIR,
        COMFY_OUTPUT_DIR,
        COMFY_INPUT_DIR,
        BACKEND_LEGACY_OUTPUTS,
        BACKEND_LEGACY_PREVIEWS,
        PROJECT_ROOT / "backend" / "outputs",
    ]
    resolved: list[Path] = []
    for root in roots:
        try:
            resolved.append(root.resolve())
        except OSError:
            continue
    _ALLOWED_DELETE_ROOTS = resolved
    return _ALLOWED_DELETE_ROOTS


def seq_from_filename(name: str) -> int | None:
    match = _DREAMFORGE_SEQ_RE.match(Path(name).name)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _path_allowed_for_delete(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for root in _allowed_delete_roots():
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def safe_hard_delete(path: Path) -> bool:
    if not path.is_file() or not _path_allowed_for_delete(path):
        return False
    try:
        path.unlink()
        return True
    except OSError:
        return False


def _unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    ordered: list[Path] = []
    for path in paths:
        try:
            key = str(path.resolve()).lower()
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)
    return ordered


def _manifest_raw_names(data: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in data.get("raw_images") or []:
        if isinstance(item, str):
            raw = item.strip()
        elif isinstance(item, dict) and item.get("path"):
            raw = str(item["path"]).strip()
        else:
            continue
        if raw:
            names.append(Path(raw).name)
    return names


def _manifest_image_names(data: dict[str, Any], image_paths: list[str]) -> list[str]:
    names: list[str] = []
    for raw in image_paths:
        name = Path(str(raw)).name
        if name:
            names.append(name)
    for item in data.get("images") or []:
        if isinstance(item, str):
            raw = item.strip()
        elif isinstance(item, dict) and item.get("path"):
            raw = str(item["path"]).strip()
        else:
            continue
        if raw:
            names.append(Path(raw).name)
    return names


def _related_filenames(name: str) -> set[str]:
    stem = Path(name).stem
    related = {
        name,
        f"{stem}_composite.png",
        f"{stem}_raw.png",
        f"{stem}.generation_manifest.json",
    }
    seq = seq_from_filename(name)
    if seq is not None:
        related.add(f"DreamForge_{seq:05d}_.png")
    return related


def _files_named_in_roots(filename: str, roots: list[Path]) -> list[Path]:
    matches: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for candidate in root.rglob(filename):
            if candidate.is_file():
                matches.append(candidate)
    return matches


def _comfy_files_for_seq(seq: int) -> list[Path]:
    matches: list[Path] = []
    prefixes = (f"DreamForge_{seq:05d}", f"DreamForge_{seq}")
    for base in (COMFY_OUTPUT_DIR, COMFY_INPUT_DIR):
        if not base.is_dir():
            continue
        for entry in base.iterdir():
            if not entry.is_file():
                continue
            lower = entry.name.lower()
            if not lower.endswith(".png"):
                continue
            if any(entry.name.startswith(prefix) for prefix in prefixes):
                matches.append(entry)
    return matches


def _staging_files_for_names(names: set[str]) -> list[Path]:
    matches: list[Path] = []
    if not COMFY_STAGING_DIR.is_dir():
        return matches
    for entry in COMFY_STAGING_DIR.iterdir():
        if not entry.is_file():
            continue
        entry_name = entry.name
        for name in names:
            stem = Path(name).stem
            if entry_name == name or entry_name.startswith(stem):
                matches.append(entry)
                break
    return matches


def _preview_paths_for_job(job_id: str) -> list[Path]:
    paths: list[Path] = []
    if not job_id:
        return paths
    try:
        from dreamforge_comfy_ws import _sanitize_job_id

        preview_name = f"preview-{_sanitize_job_id(job_id)}.jpg"
    except Exception:
        preview_name = f"preview-{job_id}.jpg"
    for root in (PREVIEWS_DIR, BACKEND_LEGACY_PREVIEWS, BACKEND_LEGACY_OUTPUTS):
        candidate = root / preview_name
        if candidate.is_file():
            paths.append(candidate)
    return paths


def _job_id_from_manifest(data: dict[str, Any]) -> str:
    job_id = str(data.get("job_id") or "").strip()
    if job_id:
        return job_id
    settings = data.get("settings")
    if isinstance(settings, dict):
        return str(settings.get("job_id") or "").strip()
    return ""


def collect_generation_artifact_paths(
    *,
    image_paths: list[str],
    manifest_data: dict[str, Any] | None = None,
    exclude_manifest: Path | None = None,
) -> list[Path]:
    data = manifest_data if isinstance(manifest_data, dict) else {}
    collected: list[Path] = []
    names = set(_manifest_image_names(data, image_paths))
    names.update(_manifest_raw_names(data))

    related_names: set[str] = set()
    sequences: set[int] = set()
    for name in names:
        related_names.update(_related_filenames(name))
        seq = seq_from_filename(name)
        if seq is not None:
            sequences.add(seq)

    search_roots = [OUTPUTS_ROOT, BACKEND_LEGACY_OUTPUTS]
    for filename in related_names:
        collected.extend(_files_named_in_roots(filename, search_roots))

    for seq in sequences:
        collected.extend(_comfy_files_for_seq(seq))

    collected.extend(_staging_files_for_names(related_names))
    collected.extend(_preview_paths_for_job(_job_id_from_manifest(data)))

    if exclude_manifest is not None:
        try:
            excluded = exclude_manifest.resolve()
            collected = [
                path
                for path in collected
                if path.resolve() != excluded
            ]
        except OSError:
            pass

    return _unique_paths(collected)


def purge_generation_artifacts(
    *,
    image_paths: list[str],
    manifest_data: dict[str, Any] | None = None,
    exclude_manifest: Path | None = None,
) -> list[str]:
    if _STALE_DELETED_INDEX.is_file():
        safe_hard_delete(_STALE_DELETED_INDEX)

    deleted: list[str] = []
    for path in collect_generation_artifact_paths(
        image_paths=image_paths,
        manifest_data=manifest_data,
        exclude_manifest=exclude_manifest,
    ):
        if safe_hard_delete(path):
            deleted.append(str(path))
    return deleted
