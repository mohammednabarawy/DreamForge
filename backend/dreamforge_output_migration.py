"""Move legacy generation artifacts into outputs/dreamforge/ and fix manifest paths."""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from _paths import BACKEND_ROOT, OUTPUTS_ROOT, PROJECT_ROOT, resolve_comfy_root

DEFAULT_SESSION_ID = "dreamforge"
TARGET_DIR = OUTPUTS_ROOT / DEFAULT_SESSION_ID
LEGACY_NESTED_DIR = TARGET_DIR / "comfy"
BACKEND_LEGACY_OUTPUTS = BACKEND_ROOT / "outputs"
COMFY_OUTPUT_DIR = resolve_comfy_root() / "output"
COMFY_INPUT_DIR = resolve_comfy_root() / "input"
CONFIG_PATH = BACKEND_ROOT / "config.txt"

_PREVIEW_RE = re.compile(r"^preview(-[0-9a-f-]+)?\.(jpg|jpeg|webp)$", re.IGNORECASE)
_PRIMARY_COMFY_OUTPUT_RE = re.compile(r"^DreamForge_(\d+)_\.png$", re.IGNORECASE)
_TARGET_SEQ_RE = re.compile(r"^DreamForge_(\d+)__\d+\.png$", re.IGNORECASE)
_TIMESTAMPED_COMFY_RE = re.compile(r"^DreamForge_(\d+)__\d+\.png$", re.IGNORECASE)
_SKIP_COMFY_SUFFIXES = ("_kontext_refs", "_composite")


def _is_generation_artifact(name: str) -> bool:
    lower = name.lower()
    if lower.endswith(".png"):
        return not _PREVIEW_RE.match(lower.replace(".png", ".jpg"))  # never preview png
    if lower.endswith(".json") and "manifest" in lower:
        return True
    return False


def _unique_dest(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    n = 2
    while True:
        candidate = dest.with_name(f"{stem}_legacy_{n}{suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _image_entry_path(item: Any) -> str | None:
    if isinstance(item, str):
        return item.strip() or None
    if isinstance(item, dict):
        raw = item.get("path")
        return str(raw).strip() if raw else None
    return None


def _set_image_entry_path(item: Any, new_path: str) -> Any:
    if isinstance(item, str):
        return new_path
    if isinstance(item, dict):
        return {**item, "path": new_path}
    return item


def _resolve_existing_png(name: str) -> Path | None:
    if not name.lower().endswith(".png"):
        return None
    candidates = [
        TARGET_DIR / name,
        OUTPUTS_ROOT / name,
        LEGACY_NESTED_DIR / name,
        BACKEND_LEGACY_OUTPUTS / name,
        COMFY_OUTPUT_DIR / name,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def _rewrite_manifest_images(manifest: Path, *, dry_run: bool) -> bool:
    data = _load_json(manifest)
    if not data:
        return False
    images = data.get("images")
    if not isinstance(images, list):
        return False

    changed = False
    new_images: list[Any] = []
    for item in images:
        raw = _image_entry_path(item)
        if not raw:
            new_images.append(item)
            continue
        name = Path(raw.replace("\\", "/")).name
        resolved = _resolve_existing_png(name)
        if resolved is None:
            new_images.append(item)
            continue
        canonical = str((TARGET_DIR / name).resolve())
        if raw.replace("\\", "/") != canonical.replace("\\", "/"):
            changed = True
            new_images.append(_set_image_entry_path(item, canonical))
        else:
            new_images.append(item)

    if not changed:
        return False
    data["images"] = new_images
    if not dry_run:
        _save_json(manifest, data)
    return True


def _format_created_at(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().strftime(
        "%Y-%m-%dT%H:%M:%S%z"
    )


def _existing_target_by_seq() -> dict[int, Path]:
    existing: dict[int, Path] = {}
    if not TARGET_DIR.is_dir():
        return existing
    for entry in TARGET_DIR.glob("DreamForge_*__*.png"):
        match = _TARGET_SEQ_RE.match(entry.name)
        if match:
            existing[int(match.group(1))] = entry
    return existing


def _legacy_manifest_payload(
    *,
    dest: Path,
    raw_name: str,
    source_path: str,
    created_at: str,
) -> dict[str, Any]:
    canonical = str(dest.resolve())
    return {
        "schema_version": "1.2",
        "template_id": "legacy.import",
        "prompt": "",
        "negative_prompt": "",
        "seed": None,
        "model": {
            "name": "unknown",
            "stem": "unknown",
            "family": "unknown",
        },
        "settings": {},
        "routing": {},
        "lineage": {
            "imported_from": source_path,
            "raw_images": [raw_name],
        },
        "images": [canonical],
        "raw_images": [raw_name],
        "validation": [],
        "created_at": created_at,
        "migration": {
            "source": "engines/comfyui/output",
            "imported_at": datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z"),
        },
    }


def migrate_comfy_output_generations(*, dry_run: bool = False) -> dict[str, Any]:
    """Import primary DreamForge SaveImage outputs from ComfyUI into outputs/dreamforge/."""
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    if not COMFY_OUTPUT_DIR.is_dir():
        return {
            "ok": True,
            "imported": [],
            "imported_count": 0,
            "manifests_created": [],
            "manifest_count": 0,
            "skipped_existing": [],
            "skipped_count": 0,
            "skipped": [],
            "dry_run": dry_run,
        }

    existing_by_seq = _existing_target_by_seq()
    imported: list[dict[str, str]] = []
    manifests_created: list[str] = []
    skipped_existing: list[str] = []
    skipped: list[str] = []

    for src in sorted(COMFY_OUTPUT_DIR.glob("DreamForge_*.png")):
        match = _PRIMARY_COMFY_OUTPUT_RE.match(src.name)
        if not match:
            continue
        seq = int(match.group(1))
        existing = existing_by_seq.get(seq)
        if existing is not None:
            try:
                if existing.stat().st_size == src.stat().st_size:
                    skipped_existing.append(str(src))
                    if not dry_run and src.exists():
                        src.unlink(missing_ok=True)
                    continue
            except OSError:
                pass

        try:
            mtime_ms = int(src.stat().st_mtime * 1000)
            created_at = _format_created_at(src)
            raw_name = src.name
            source_path = str(src.resolve())
        except OSError as exc:
            skipped.append(f"{src}: {exc}")
            continue

        dest = TARGET_DIR / f"DreamForge_{seq:05d}__{mtime_ms}.png"
        if dest.exists():
            dest = _unique_dest(dest)

        try:
            if not dry_run:
                TARGET_DIR.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
            final_dest = dest
            imported.append({"from": str(src), "to": str(final_dest)})
            existing_by_seq[seq] = final_dest

            manifest_path = final_dest.with_suffix(".generation_manifest.json")
            if not manifest_path.exists():
                payload = _legacy_manifest_payload(
                    dest=final_dest,
                    raw_name=raw_name,
                    source_path=source_path,
                    created_at=created_at,
                )
                if not dry_run:
                    _save_json(manifest_path, payload)
                manifests_created.append(str(manifest_path))
        except OSError as exc:
            skipped.append(f"{src}: {exc}")

    return {
        "ok": True,
        "imported": imported,
        "imported_count": len(imported),
        "manifests_created": manifests_created,
        "manifest_count": len(manifests_created),
        "skipped_existing": skipped_existing,
        "skipped_count": len(skipped_existing),
        "skipped": skipped,
        "dry_run": dry_run,
    }


def _is_skipped_comfy_artifact(name: str) -> bool:
    lower = name.lower()
    return any(token in lower for token in _SKIP_COMFY_SUFFIXES)


def _copy_file(src: Path, dest: Path, *, dry_run: bool) -> Path:
    if dest.exists():
        try:
            if src.stat().st_size == dest.stat().st_size:
                return dest
        except OSError:
            pass
        dest = _unique_dest(dest)
    if not dry_run:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dest))
    return dest


def migrate_comfy_input_copies(*, dry_run: bool = False) -> dict[str, Any]:
    """Copy timestamped DreamForge PNGs from ComfyUI input into outputs/dreamforge/."""
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    if not COMFY_INPUT_DIR.is_dir():
        return {
            "ok": True,
            "imported": [],
            "imported_count": 0,
            "manifests_created": [],
            "manifest_count": 0,
            "skipped_existing": [],
            "skipped_count": 0,
            "skipped": [],
            "dry_run": dry_run,
        }

    existing_by_seq = _existing_target_by_seq()
    imported: list[dict[str, str]] = []
    manifests_created: list[str] = []
    skipped_existing: list[str] = []
    skipped: list[str] = []

    for src in sorted(COMFY_INPUT_DIR.glob("DreamForge_*__*.png")):
        if _is_skipped_comfy_artifact(src.name):
            continue
        match = _TIMESTAMPED_COMFY_RE.match(src.name)
        if not match:
            continue
        seq = int(match.group(1))
        if seq in existing_by_seq:
            skipped_existing.append(str(src))
            continue

        dest = TARGET_DIR / src.name
        try:
            created_at = _format_created_at(src)
            source_path = str(src.resolve())
        except OSError as exc:
            skipped.append(f"{src}: {exc}")
            continue

        try:
            final_dest = _copy_file(src, dest, dry_run=dry_run)
            imported.append({"from": str(src), "to": str(final_dest)})
            existing_by_seq[seq] = final_dest

            manifest_path = final_dest.with_suffix(".generation_manifest.json")
            if not manifest_path.exists():
                payload = _legacy_manifest_payload(
                    dest=final_dest,
                    raw_name=src.name,
                    source_path=source_path,
                    created_at=created_at,
                )
                payload["migration"]["source"] = "engines/comfyui/input"
                if not dry_run:
                    _save_json(manifest_path, payload)
                manifests_created.append(str(manifest_path))
        except OSError as exc:
            skipped.append(f"{src}: {exc}")

    return {
        "ok": True,
        "imported": imported,
        "imported_count": len(imported),
        "manifests_created": manifests_created,
        "manifest_count": len(manifests_created),
        "skipped_existing": skipped_existing,
        "skipped_count": len(skipped_existing),
        "skipped": skipped,
        "dry_run": dry_run,
    }


def _move_file(src: Path, dest: Path, *, dry_run: bool) -> Path:
    if dest.exists():
        try:
            if src.stat().st_size == dest.stat().st_size:
                if not dry_run:
                    src.unlink(missing_ok=True)
                return dest
        except OSError:
            pass
        dest = _unique_dest(dest)
    if not dry_run:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
    return dest


def _collect_source_files() -> list[Path]:
    sources: list[Path] = []
    if OUTPUTS_ROOT.is_dir():
        for entry in OUTPUTS_ROOT.iterdir():
            if entry.is_file() and _is_generation_artifact(entry.name):
                sources.append(entry)
    if LEGACY_NESTED_DIR.is_dir():
        for entry in LEGACY_NESTED_DIR.iterdir():
            if entry.is_file() and _is_generation_artifact(entry.name):
                sources.append(entry)
    if BACKEND_LEGACY_OUTPUTS.is_dir():
        for entry in BACKEND_LEGACY_OUTPUTS.iterdir():
            if entry.is_file() and _is_generation_artifact(entry.name):
                sources.append(entry)
        nested = BACKEND_LEGACY_OUTPUTS / DEFAULT_SESSION_ID
        if nested.is_dir():
            for entry in nested.iterdir():
                if entry.is_file() and _is_generation_artifact(entry.name):
                    sources.append(entry)
    return sources


def _update_config_outputs_path(*, dry_run: bool) -> bool:
    if not CONFIG_PATH.is_file():
        return False
    try:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    desired = str((PROJECT_ROOT / "outputs" / DEFAULT_SESSION_ID).resolve())
    current = str(payload.get("path_outputs") or "").strip()
    legacy_values = {
        str(BACKEND_LEGACY_OUTPUTS.resolve()),
        str(BACKEND_LEGACY_OUTPUTS),
        "../outputs/",
        "../outputs",
    }
    if current.replace("\\", "/") == desired.replace("\\", "/"):
        return False
    if current and current not in legacy_values and "backend" not in current.lower():
        return False
    payload["path_outputs"] = desired
    if not dry_run:
        CONFIG_PATH.write_text(json.dumps(payload, indent=4), encoding="utf-8")
    return True


def migrate_legacy_outputs(*, dry_run: bool = False) -> dict[str, Any]:
    """Move root / comfy / backend legacy PNG+manifest files into outputs/dreamforge/."""
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    moved: list[dict[str, str]] = []
    skipped: list[str] = []

    for src in _collect_source_files():
        dest = TARGET_DIR / src.name
        if src.resolve() == dest.resolve():
            continue
        try:
            final_dest = _move_file(src, dest, dry_run=dry_run)
            moved.append({"from": str(src), "to": str(final_dest)})
        except OSError as exc:
            skipped.append(f"{src}: {exc}")

    updated_manifests: list[str] = []
    for manifest in sorted(TARGET_DIR.glob("*manifest*.json")):
        if _rewrite_manifest_images(manifest, dry_run=dry_run):
            updated_manifests.append(str(manifest))

    if not dry_run and LEGACY_NESTED_DIR.is_dir():
        try:
            next(LEGACY_NESTED_DIR.iterdir())
        except StopIteration:
            LEGACY_NESTED_DIR.rmdir()

    config_updated = _update_config_outputs_path(dry_run=dry_run)
    comfy_import = migrate_comfy_output_generations(dry_run=dry_run)
    input_import = migrate_comfy_input_copies(dry_run=dry_run)

    return {
        "ok": True,
        "target": str(TARGET_DIR.resolve()),
        "moved": moved,
        "moved_count": len(moved),
        "updated_manifests": updated_manifests,
        "updated_count": len(updated_manifests),
        "skipped": skipped,
        "config_updated": config_updated,
        "comfy_import": comfy_import,
        "input_import": input_import,
        "dry_run": dry_run,
    }
