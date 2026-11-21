import json
import os
import re
from pathlib import Path
from datetime import datetime
import glob

from _paths import BACKEND_ROOT, PROJECT_ROOT, OUTPUTS_ROOT

_ISO_COMPACT_TZ_RE = re.compile(r"([+-]\d{2})(\d{2})$")
_MANIFEST_SUMMARY_CACHE: dict[str, tuple[int, int, dict, str, list[str]]] = {}


def invalidate_output_index_cache(path: str | Path | None = None) -> None:
    """Drop cached manifest summaries (all or for one path)."""
    if path is None:
        _MANIFEST_SUMMARY_CACHE.clear()
        return
    key = str(path)
    _MANIFEST_SUMMARY_CACHE.pop(key, None)
    try:
        _MANIFEST_SUMMARY_CACHE.pop(str(Path(path).resolve()), None)
    except OSError:
        pass


def _normalize_iso_timestamp(value: object) -> str | None:
    """Normalize ISO timestamps so +0300 offsets become +03:00 (WebKit/Safari safe)."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)
    text = _ISO_COMPACT_TZ_RE.sub(r"\1:\2", text)
    return text

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
    path = _resolve_manifest_path(str(manifest_path))
    if path is None:
        return {"status": "error", "message": "Saved generation not found in the image library."}
        
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
    return list(dict.fromkeys(paths))


def _split_cross_platform_parts(raw_path: str) -> list[str]:
    return [part for part in re.split(r"[\\/]+", raw_path) if part]


def _normalize_output_path(path: str) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    image_path = Path(raw)
    if image_path.exists():
        return str(image_path)
    parts = _split_cross_platform_parts(raw)
    lowered = [p.lower() for p in parts]
    if "outputs" in lowered:
        idx = lowered.index("outputs")
        rel_parts = parts[idx + 1 :]
        if rel_parts:
            candidate = OUTPUTS_ROOT.joinpath(*rel_parts)
            if candidate.exists():
                return str(candidate)
    if parts:
        candidate_root = OUTPUTS_ROOT / parts[-1]
        if candidate_root.exists():
            return str(candidate_root)
    if not image_path.is_absolute():
        candidate = PROJECT_ROOT / image_path
        if candidate.exists():
            return str(candidate)
    return raw


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


def _extract_dimensions(data: dict, settings: dict) -> tuple[int | None, int | None]:
    width = settings.get("width")
    height = settings.get("height")
    if not (isinstance(width, (int, float)) and isinstance(height, (int, float))):
        validation = data.get("validation")
        if isinstance(validation, list) and validation and isinstance(validation[0], dict):
            width = validation[0].get("width")
            height = validation[0].get("height")
    w = int(width) if isinstance(width, (int, float)) and width > 0 else None
    h = int(height) if isinstance(height, (int, float)) and height > 0 else None
    return w, h


def _summary_from_manifest_entry(item, data, *, max_prompt_chars=8000):
    model_info = data.get("model") or {}
    settings = data.get("settings") or {}
    if isinstance(model_info, str):
        model_info = {"name": model_info}
    elif not isinstance(model_info, dict):
        model_info = {}
    if not isinstance(settings, dict):
        settings = {}
    prompt = data.get("prompt", "") or ""
    if max_prompt_chars > 0 and len(prompt) > max_prompt_chars:
        prompt = prompt[:max_prompt_chars] + "…"
    width, height = _extract_dimensions(data, settings)
    timestamp = datetime.fromtimestamp(item["mtime"]).astimezone().isoformat()
    created_at = _normalize_iso_timestamp(data.get("created_at")) or timestamp
    return {
        "manifest_path": item["path"],
        "timestamp": timestamp,
        "created_at": created_at,
        "session": _session_from_manifest_path(item["path"]),
        "title": _title_from_manifest(data, item["path"]),
        "prompt": prompt,
        "model_family": model_info.get("family", "unknown"),
        "model_name": model_info.get("name", "unknown"),
        "model_stem": model_info.get("stem")
        or Path(model_info.get("name", "unknown")).stem,
        "images": [p for p in _image_paths_from_manifest(data) if Path(p).is_file()],
        "styles": settings.get("styles") or [],
        "seed": data.get("seed"),
        "width": width,
        "height": height,
    }


def _cached_manifest_record(item: dict) -> tuple[dict, str] | None:
    """Return cached (summary, search_haystack) for a manifest, validating mtime & image existence."""
    path = item["path"]
    try:
        st = os.stat(path)
    except OSError:
        _MANIFEST_SUMMARY_CACHE.pop(path, None)
        return None
    cached = _MANIFEST_SUMMARY_CACHE.get(path)
    if cached and cached[0] == st.st_mtime_ns and cached[1] == st.st_size:
        _, _, summary_template, haystack, candidate_images = cached
        live_images = [p for p in candidate_images if os.path.isfile(p)]
        if not live_images:
            return None
        summary = (
            summary_template
            if len(live_images) == len(summary_template["images"])
            else {**summary_template, "images": live_images}
        )
        return summary, haystack

    data = _load_manifest(path)
    if not isinstance(data, dict):
        return None
    candidate_images = _image_paths_from_manifest(data)
    summary = _summary_from_manifest_entry(item, data)
    haystack = " ".join(
        [
            str(data.get("prompt") or ""),
            str(data.get("negative_prompt") or ""),
            str(summary["title"]),
            str(summary["model_name"]),
            str(summary["model_stem"]),
            str(summary["session"]),
            " ".join(str(s) for s in (summary.get("styles") or [])),
        ]
    ).lower()
    _MANIFEST_SUMMARY_CACHE[path] = (
        st.st_mtime_ns,
        st.st_size,
        summary,
        haystack,
        candidate_images,
    )
    if not summary["images"]:
        return None
    return summary, haystack


def _manifest_filter_key(path_str: str) -> str:
    raw = str(path_str or "").strip()
    if not raw:
        return ""
    try:
        resolved = str(Path(raw).resolve())
    except OSError:
        resolved = raw
    return resolved.replace("\\", "/").lower()


def _collect_library_metadata(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    """Aggregate all sessions and models across all valid manifests (unfiltered by pagination)."""
    session_map: dict[str, dict] = {}
    model_map: dict[str, dict] = {}
    for item in entries:
        record = _cached_manifest_record(item)
        if record is None:
            continue
        summary, _ = record
        sid = summary["session"]
        ts = summary["created_at"] or summary["timestamp"]
        s_entry = session_map.get(sid)
        if s_entry is None:
            session_map[sid] = {"id": sid, "count": 1, "latest": ts}
        else:
            s_entry["count"] += 1
            if ts > s_entry["latest"]:
                s_entry["latest"] = ts
        m_name = str(summary.get("model_name") or "").strip()
        m_stem = str(summary.get("model_stem") or "").strip()
        if m_name and m_name.lower() != "unknown":
            m_key = m_name.lower()
            m_entry = model_map.get(m_key)
            if m_entry is None:
                model_map[m_key] = {"name": m_name, "stem": m_stem or Path(m_name).stem, "count": 1}
            else:
                m_entry["count"] += 1
    sessions = sorted(session_map.values(), key=lambda x: x["latest"], reverse=True)
    models = sorted(model_map.values(), key=lambda x: (-x["count"], x["stem"].lower()))
    return sessions, models


def list_outputs_with_meta(
    since=None,
    model=None,
    style=None,
    limit=20,
    offset=0,
    session=None,
    query=None,
    manifest_paths=None,
    sort="newest",
):
    """List recent outputs with pagination + full session/model facet metadata."""
    del style  # reserved for future filters
    offset = max(0, int(offset or 0))
    limit = max(1, int(limit or 20))
    sort_dir = str(sort or "newest").strip().lower()
    all_entries = _collect_manifest_entries(since=since, session=None)
    sessions_meta, models_meta = _collect_library_metadata(all_entries)

    if sort_dir == "oldest":
        ordered_entries = list(reversed(all_entries))
    else:
        ordered_entries = all_entries

    allowed = (
        None
        if manifest_paths is None
        else {_manifest_filter_key(p) for p in manifest_paths if str(p or "").strip()}
    )
    query_tokens = [tok for tok in str(query or "").strip().lower().split() if tok]
    model_filter = str(model or "").strip().lower()
    session_filter = str(session or "").strip()
    if session_filter == "all":
        session_filter = ""

    matched = 0
    results = []
    for item in ordered_entries:
        if session_filter and _session_from_manifest_path(item["path"]) != session_filter:
            continue
        if allowed is not None and _manifest_filter_key(item["path"]) not in allowed:
            continue
        record = _cached_manifest_record(item)
        if record is None:
            continue
        summary, haystack = record
        if model_filter and summary["model_name"].lower() != model_filter and summary["model_stem"].lower() != model_filter:
            continue
        if query_tokens and not all(tok in haystack for tok in query_tokens):
            continue
        if matched >= offset and len(results) < limit:
            results.append(summary)
        matched += 1
    return results, matched, sessions_meta, models_meta


def list_outputs(
    since=None,
    model=None,
    style=None,
    limit=20,
    offset=0,
    session=None,
    query=None,
    manifest_paths=None,
    sort="newest",
):
    """List recent outputs with pagination. Returns (items, total_matching)."""
    results, matched, _, _ = list_outputs_with_meta(
        since=since,
        model=model,
        style=style,
        limit=limit,
        offset=offset,
        session=session,
        query=query,
        manifest_paths=manifest_paths,
        sort=sort,
    )
    return results, matched


def search_outputs(
    query,
    limit=20,
    offset=0,
    session=None,
    manifest_paths=None,
    model=None,
    sort="newest",
):
    """Search manifests by prompt, negative, title, styles, session, or model name."""
    if not str(query or "").strip():
        return [], 0
    return list_outputs(
        query=query,
        limit=limit,
        offset=offset,
        session=session,
        manifest_paths=manifest_paths,
        model=model,
        sort=sort,
    )


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


def _paths_from_image_entry(item) -> list[str]:
    if isinstance(item, str):
        return [item]
    if isinstance(item, dict):
        paths: list[str] = []
        for key in ("path", "raw_path"):
            raw = item.get(key)
            if raw:
                paths.append(str(raw))
        return paths
    return []


def _find_image_index(data: dict, removed: Path) -> int | None:
    target_key = _output_path_key(str(removed))
    if not target_key:
        return None
    for index, item in enumerate(data.get("images") or []):
        if _manifest_image_entry_key(item) == target_key:
            return index
    return None


def _per_image_manifest_path(image: Path) -> Path:
    return image.with_suffix(".generation_manifest.json")


def _sidecar_files_for_image(image: Path, *, exclude_manifest: Path | None = None) -> list[Path]:
    sidecars: list[Path] = []
    composite = image.with_name(f"{image.stem}_composite.png")
    try:
        if composite.is_file() and composite.resolve() != image.resolve():
            sidecars.append(composite.resolve())
    except OSError:
        pass
    per_image_manifest = _per_image_manifest_path(image)
    try:
        if per_image_manifest.is_file():
            resolved = per_image_manifest.resolve()
            if exclude_manifest is None or resolved != exclude_manifest.resolve():
                sidecars.append(resolved)
    except OSError:
        pass
    return sidecars


def _paths_for_manifest_index(data: dict, index: int) -> list[str]:
    paths: list[str] = []
    images = data.get("images") or []
    if 0 <= index < len(images):
        paths.extend(_paths_from_image_entry(images[index]))
    raw_images = data.get("raw_images") or []
    if 0 <= index < len(raw_images):
        raw_item = raw_images[index]
        if isinstance(raw_item, str):
            paths.append(raw_item)
        elif isinstance(raw_item, dict) and raw_item.get("path"):
            paths.append(str(raw_item["path"]))
    deduped: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        key = _output_path_key(raw)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(raw)
    return deduped


def _all_referenced_paths(data: dict) -> list[str]:
    paths: list[str] = []
    for item in data.get("images") or []:
        paths.extend(_paths_from_image_entry(item))
    for item in data.get("raw_images") or []:
        if isinstance(item, str):
            paths.append(item)
        elif isinstance(item, dict) and item.get("path"):
            paths.append(str(item["path"]))
    deduped: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        key = _output_path_key(raw)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(raw)
    return deduped


def _delete_output_files(paths: list[str]) -> list[str]:
    deleted: list[str] = []
    for raw in paths:
        if _safe_unlink_output_file(raw):
            deleted.append(raw)
    return deleted


def _prune_lineage_outputs(data: dict, removed: Path) -> None:
    lineage = data.get("lineage")
    if not isinstance(lineage, dict):
        return
    target_key = _output_path_key(str(removed))
    if not target_key:
        return
    outputs = lineage.get("output_images")
    if isinstance(outputs, list):
        lineage["output_images"] = [
            item
            for item in outputs
            if _output_path_key(str(item)) != target_key
        ]


def _remove_image_from_manifest_data(data: dict, removed: Path) -> bool:
    index = _find_image_index(data, removed)
    if index is None:
        return False

    images = list(data.get("images") or [])
    images.pop(index)
    data["images"] = images

    for parallel_key in ("raw_images", "validation"):
        parallel = data.get(parallel_key)
        if isinstance(parallel, list) and index < len(parallel):
            updated = list(parallel)
            updated.pop(index)
            data[parallel_key] = updated

    _prune_lineage_outputs(data, removed)
    return True


def _collect_delete_paths_for_image(
    data: dict,
    image: Path,
    *,
    exclude_manifest: Path | None = None,
) -> list[str]:
    paths: list[str] = [str(image)]
    index = _find_image_index(data, image)
    if index is not None:
        paths.extend(_paths_for_manifest_index(data, index))
    paths.extend(str(path) for path in _sidecar_files_for_image(image, exclude_manifest=exclude_manifest))

    deduped: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        key = _output_path_key(raw)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(raw)
    return deduped


def delete_generation(manifest_path: str) -> dict:
    """Delete a manifest and all image files referenced by it."""
    from dreamforge_output_cleanup import purge_generation_artifacts

    manifest = _resolve_manifest_path(manifest_path)
    if not manifest:
        return {"ok": False, "error": "invalid_manifest_path"}

    data = _load_manifest(str(manifest)) or {}
    delete_paths = list(_all_referenced_paths(data))
    seen_sidecars: set[str] = set()
    for item in data.get("images") or []:
        for raw in _paths_from_image_entry(item):
            image = _resolve_under_outputs(_normalize_output_path(raw), must_be_file=False)
            if not image or not image.is_file():
                continue
            for sidecar in _sidecar_files_for_image(image, exclude_manifest=manifest):
                key = str(sidecar).lower()
                if key in seen_sidecars:
                    continue
                seen_sidecars.add(key)
                delete_paths.append(str(sidecar))

    deleted_images = _delete_output_files(delete_paths)
    deleted_external = purge_generation_artifacts(
        image_paths=delete_paths,
        manifest_data=data,
        exclude_manifest=manifest,
    )

    try:
        manifest.unlink()
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    invalidate_output_index_cache(manifest)

    return {
        "ok": True,
        "manifest_path": str(manifest),
        "deleted_images": deleted_images,
        "deleted_external": deleted_external,
    }


def delete_output_image(manifest_path: str, image_path: str) -> dict:
    """Delete one image file and update or remove its manifest."""
    from dreamforge_output_cleanup import purge_generation_artifacts

    manifest = _resolve_manifest_path(manifest_path)
    if not manifest:
        return {"ok": False, "error": "invalid_manifest_path"}

    image = _resolve_under_outputs(_normalize_output_path(image_path), must_be_file=True)
    if not image:
        return {"ok": False, "error": "invalid_image_path"}

    data = _load_manifest(str(manifest))
    if not data:
        delete_paths = _collect_delete_paths_for_image({}, image, exclude_manifest=manifest)
        deleted_files = _delete_output_files(delete_paths)
        deleted_external = purge_generation_artifacts(
            image_paths=delete_paths,
        )
        try:
            manifest.unlink(missing_ok=True)
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "deleted_image": str(image),
            "deleted_files": deleted_files,
            "deleted_external": deleted_external,
            "manifest_removed": True,
        }

    if _find_image_index(data, image) is None:
        return {"ok": False, "error": "image_not_in_manifest"}

    delete_paths = _collect_delete_paths_for_image(data, image, exclude_manifest=manifest)
    if not _remove_image_from_manifest_data(data, image):
        return {"ok": False, "error": "image_not_in_manifest"}

    remaining = _image_paths_from_manifest(data)
    deleted_files = _delete_output_files(delete_paths)
    deleted_external = purge_generation_artifacts(
        image_paths=delete_paths,
        manifest_data=data,
        exclude_manifest=manifest,
    )

    if not remaining:
        try:
            manifest.unlink()
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        invalidate_output_index_cache(manifest)
        return {
            "ok": True,
            "deleted_image": str(image),
            "deleted_files": deleted_files,
            "deleted_external": deleted_external,
            "manifest_removed": True,
        }

    try:
        with manifest.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    invalidate_output_index_cache(manifest)

    return {
        "ok": True,
        "deleted_image": str(image),
        "deleted_files": deleted_files,
        "deleted_external": deleted_external,
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

    deleted = 0
    for manifest in sorted(session_dir.rglob("*manifest*.json")):
        if not manifest.is_file():
            continue
        result = delete_generation(str(manifest))
        if result.get("ok"):
            deleted += 1

    # A project can also contain runtime logs or imported files. Delete only
    # manifest-owned generations, never recursively erase unrelated contents.
    try:
        session_dir.rmdir()
    except OSError:
        pass

    return {
        "ok": True,
        "session": session,
        "deleted_generations": deleted,
        "deleted_directory": str(session_dir) if not session_dir.exists() else None,
        "preserved_directory": str(session_dir) if session_dir.exists() else None,
    }
