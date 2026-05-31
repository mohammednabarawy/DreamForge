import json
import os
import shutil
from pathlib import Path
from datetime import datetime
import glob

from _paths import BACKEND_ROOT, PROJECT_ROOT
OUTPUTS_ROOT = PROJECT_ROOT / "outputs"

def _load_manifest(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _get_manifest_mtime(path):
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0

def get_generation_bundle(manifest_path):
    """Return the full generation bundle given a manifest path."""
    path = Path(manifest_path)
    if not path.is_absolute():
        path = OUTPUTS_ROOT / path
    
    if not path.exists():
        return {"status": "error", "message": f"Manifest not found: {path}"}
        
    data = _load_manifest(path)
    if not data:
        return {"status": "error", "message": f"Failed to parse manifest: {path}"}
        
    return {
        "status": "success",
        "manifest_path": str(path),
        "bundle": data
    }

def _session_from_manifest_path(path: str) -> str:
    try:
        rel = Path(path).resolve().relative_to(OUTPUTS_ROOT.resolve())
        parts = rel.parts
        if len(parts) >= 2:
            return parts[0]
        if len(parts) == 1:
            return "root"
    except ValueError:
        pass
    return "unsorted"


def _title_from_manifest(data: dict, manifest_path: str) -> str:
    images = _image_paths_from_manifest(data)
    if images:
        return Path(images[0]).stem
    stem = Path(manifest_path).stem
    for token in (".generation_manifest", "_manifest"):
        stem = stem.replace(token, "")
    return stem or "untitled"


def _image_paths_from_manifest(data: dict) -> list[str]:
    paths = []
    for item in data.get("images") or []:
        if isinstance(item, str):
            paths.append(_normalize_output_path(item))
        elif isinstance(item, dict) and item.get("path"):
            paths.append(_normalize_output_path(str(item["path"])))
    return paths


def _normalize_output_path(path: str) -> str:
    image_path = Path(path)
    if image_path.exists():
        return str(image_path)
    parts = image_path.parts
    lowered = [p.lower() for p in parts]
    if "outputs" in lowered:
        idx = lowered.index("outputs")
        candidate = OUTPUTS_ROOT.joinpath(*parts[idx + 1 :])
        if candidate.exists():
            return str(candidate)
    if not image_path.is_absolute():
        candidate = PROJECT_ROOT / image_path
        if candidate.exists():
            return str(candidate)
    return path


def _collect_manifest_entries(since=None, session=None):
    """Sorted manifest paths (newest first), optionally filtered by time and session folder."""
    entries = []
    if not OUTPUTS_ROOT.exists():
        return entries

    for root, _, files in os.walk(OUTPUTS_ROOT):
        for file in files:
            if file.endswith(".json") and "manifest" in file:
                path = os.path.join(root, file)
                mtime = _get_manifest_mtime(path)
                if since is not None and (mtime * 1000) <= since:
                    continue
                if session and session != "all":
                    if _session_from_manifest_path(path) != session:
                        continue
                entries.append({"path": path, "mtime": mtime})

    entries.sort(key=lambda x: x["mtime"], reverse=True)
    return entries


def _summary_from_manifest_entry(item, data, *, max_prompt_chars=8000):
    model_info = data.get("model") or {}
    settings = data.get("settings") or {}
    prompt = data.get("prompt", "") or ""
    if max_prompt_chars > 0 and len(prompt) > max_prompt_chars:
        prompt = prompt[:max_prompt_chars] + "…"
    return {
        "manifest_path": item["path"],
        "timestamp": datetime.fromtimestamp(item["mtime"]).isoformat(),
        "created_at": data.get("created_at"),
        "session": _session_from_manifest_path(item["path"]),
        "title": _title_from_manifest(data, item["path"]),
        "prompt": prompt,
        "model_family": model_info.get("family", "unknown"),
        "model_name": model_info.get("name", "unknown"),
        "model_stem": model_info.get("stem")
        or Path(model_info.get("name", "unknown")).stem,
        "images": _image_paths_from_manifest(data),
        "styles": settings.get("styles") or [],
        "seed": data.get("seed"),
    }


def list_outputs(
    since=None,
    model=None,
    style=None,
    limit=20,
    offset=0,
    session=None,
):
    """List recent outputs with pagination. Returns (items, total_matching)."""
    del style  # reserved for future filters
    offset = max(0, int(offset or 0))
    limit = max(1, int(limit or 20))
    entries = _collect_manifest_entries(since=since, session=session)

    if model:
        results = []
        matched = 0
        for item in entries:
            data = _load_manifest(item["path"])
            if not data:
                continue
            if data.get("model", {}).get("name", "").lower() != model.lower():
                continue
            if matched >= offset and len(results) < limit:
                results.append(_summary_from_manifest_entry(item, data))
            matched += 1
        return results, matched

    total = len(entries)
    results = []
    for item in entries[offset : offset + limit]:
        data = _load_manifest(item["path"])
        if not data:
            continue
        results.append(_summary_from_manifest_entry(item, data))
    return results, total

def search_outputs(query, limit=20, offset=0):
    """Search manifests by prompt, negative, title, or model name."""
    if not query:
        return [], 0

    query_lower = query.lower().strip()
    offset = max(0, int(offset or 0))
    limit = max(1, int(limit or 20))
    entries = _collect_manifest_entries()

    results = []
    matched = 0
    for item in entries:
        data = _load_manifest(item["path"])
        if not data:
            continue
        prompt = data.get("prompt", "") or ""
        negative = data.get("negative_prompt", "") or ""
        title = _title_from_manifest(data, item["path"]) or ""
        model_name = (data.get("model") or {}).get("name", "") or ""
        model_stem = (data.get("model") or {}).get("stem") or Path(model_name).stem
        haystack = " ".join(
            [prompt, negative, title, model_name, model_stem]
        ).lower()
        if query_lower not in haystack:
            continue
        if matched >= offset and len(results) < limit:
            results.append(_summary_from_manifest_entry(item, data))
        matched += 1

    return results, matched


def _output_path_key(path_str: str) -> str:
    """Stable key for comparing manifest image paths to disk paths."""
    if not path_str:
        return ""
    norm = _normalize_output_path(path_str)
    candidates = [
        Path(norm),
        Path(path_str),
        OUTPUTS_ROOT / path_str,
        PROJECT_ROOT / path_str,
    ]
    if not Path(path_str).is_absolute():
        parts = Path(path_str.replace("\\", "/")).parts
        lowered = [p.lower() for p in parts]
        if "outputs" in lowered:
            idx = lowered.index("outputs")
            candidates.append(OUTPUTS_ROOT.joinpath(*parts[idx + 1 :]))
    for cand in candidates:
        try:
            resolved = cand.resolve()
            resolved.relative_to(OUTPUTS_ROOT.resolve())
            return str(resolved).lower()
        except (OSError, ValueError):
            continue
    parts = Path(path_str.replace("\\", "/")).parts
    lowered = [p.lower() for p in parts]
    if "outputs" in lowered:
        idx = lowered.index("outputs")
        return str(Path(*parts[idx:]).as_posix()).lower()
    return path_str.replace("\\", "/").lower()


def _resolve_under_outputs(path_str: str, *, must_be_file: bool = True) -> Path | None:
    """Resolve a path and ensure it lives under OUTPUTS_ROOT."""
    raw = Path(path_str)
    candidates = [raw]
    if not raw.is_absolute():
        candidates.extend(
            [
                OUTPUTS_ROOT / path_str,
                PROJECT_ROOT / path_str,
            ]
        )
    for cand in candidates:
        try:
            resolved = cand.resolve()
        except OSError:
            continue
        try:
            resolved.relative_to(OUTPUTS_ROOT.resolve())
        except ValueError:
            continue
        if must_be_file and not resolved.is_file():
            continue
        if not must_be_file and not resolved.exists():
            continue
        return resolved
    return None


def _resolve_manifest_path(manifest_path: str) -> Path | None:
    path = _resolve_under_outputs(manifest_path, must_be_file=True)
    if not path:
        return None
    if path.suffix.lower() != ".json" or "manifest" not in path.name.lower():
        return None
    return path


def _safe_unlink_output_file(path_str: str) -> bool:
    normalized = _normalize_output_path(path_str)
    path = _resolve_under_outputs(normalized, must_be_file=True)
    if not path:
        return False
    try:
        path.unlink()
        return True
    except OSError:
        return False


def _manifest_image_entry_key(item) -> str:
    if isinstance(item, str):
        return _output_path_key(item)
    if isinstance(item, dict) and item.get("path"):
        return _output_path_key(str(item["path"]))
    return ""


def _remove_image_from_manifest_data(data: dict, removed: Path) -> bool:
    target_key = _output_path_key(str(removed))
    if not target_key:
        return False
    changed = False
    new_images = []
    for item in data.get("images") or []:
        if _manifest_image_entry_key(item) == target_key:
            changed = True
            continue
        new_images.append(item)
    if changed:
        data["images"] = new_images
    return changed


def delete_generation(manifest_path: str) -> dict:
    """Delete a manifest and all image files referenced by it."""
    manifest = _resolve_manifest_path(manifest_path)
    if not manifest:
        return {"ok": False, "error": "invalid_manifest_path"}

    deleted_images = []
    data = _load_manifest(str(manifest))
    if data:
        for raw in _image_paths_from_manifest(data):
            if _safe_unlink_output_file(raw):
                deleted_images.append(raw)

    try:
        manifest.unlink()
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    return {
        "ok": True,
        "manifest_path": str(manifest),
        "deleted_images": deleted_images,
    }


def delete_output_image(manifest_path: str, image_path: str) -> dict:
    """Delete one image file and update or remove its manifest."""
    manifest = _resolve_manifest_path(manifest_path)
    if not manifest:
        return {"ok": False, "error": "invalid_manifest_path"}

    image = _resolve_under_outputs(_normalize_output_path(image_path), must_be_file=True)
    if not image:
        return {"ok": False, "error": "invalid_image_path"}

    data = _load_manifest(str(manifest))
    if not data:
        try:
            image.unlink()
            manifest.unlink(missing_ok=True)
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "deleted_image": str(image),
            "manifest_removed": True,
        }

    if not _remove_image_from_manifest_data(data, image):
        return {"ok": False, "error": "image_not_in_manifest"}

    remaining = _image_paths_from_manifest(data)

    try:
        image.unlink()
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    if not remaining:
        try:
            manifest.unlink()
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "deleted_image": str(image),
            "manifest_removed": True,
        }

    try:
        with manifest.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    return {
        "ok": True,
        "deleted_image": str(image),
        "manifest_path": str(manifest),
        "remaining_images": len(remaining),
    }


def delete_session(session_id: str) -> dict:
    """Delete all generations in a session folder, or root-level manifests."""
    session = (session_id or "").strip()
    if not session:
        return {"ok": False, "error": "empty_session"}

    if session == "root":
        deleted = 0
        for entry in list(OUTPUTS_ROOT.iterdir()):
            if not entry.is_file():
                continue
            if entry.suffix.lower() != ".json" or "manifest" not in entry.name.lower():
                continue
            result = delete_generation(str(entry))
            if result.get("ok"):
                deleted += 1
        return {"ok": True, "session": session, "deleted_generations": deleted}

    session_dir = (OUTPUTS_ROOT / session).resolve()
    try:
        session_dir.relative_to(OUTPUTS_ROOT.resolve())
    except ValueError:
        return {"ok": False, "error": "invalid_session"}

    if not session_dir.is_dir():
        return {"ok": False, "error": "session_not_found"}

    try:
        shutil.rmtree(session_dir)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    return {
        "ok": True,
        "session": session,
        "deleted_directory": str(session_dir),
    }
