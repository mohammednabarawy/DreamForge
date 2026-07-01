"""JSON-RPC bridge for DreamForge (Tauri desktop).

Reads one JSON object per line on stdin; writes one JSON object per line on stdout.
Designed to be invoked from Rust without a separate HTTP server.

Commands:
  ping, get_paths, get_inventory, get_model_gallery, get_lora_gallery,
  resolve_model_profile, list_outputs, search_outputs,
  dry_run, build_cli_argv, list_styles, get_ui_defaults,
  classify_models, organize_models
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("DREAMFORGE_HEADLESS", "1")

from _paths import BACKEND_ROOT, bootstrap_paths, extend_sys_path

bootstrap_paths()
extend_sys_path()
CACHE_ROOT = BACKEND_ROOT / "cache"
CLI_SCRIPT = BACKEND_ROOT / "dreamforge_cli_direct.py"


def _force_utf8_io() -> None:
    """Ensure stdout/stderr use UTF-8 with replacement.

    On Windows the default code page (cp1252, cp1256, ...) crashes the
    bridge when payloads contain non-ASCII characters such as "->" arrows
    or model names with accents.  Tauri reads our stdout as UTF-8 anyway,
    so force the encoding here and keep error handling permissive.
    """

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_force_utf8_io()


def _emit(payload: dict) -> None:
    try:
        line = json.dumps(payload, ensure_ascii=True, default=str)
    except (TypeError, ValueError) as exc:
        line = json.dumps(
            {
                "ok": False,
                "error": f"response_encode_failed: {exc}",
            },
            ensure_ascii=True,
        )
    try:
        sys.stdout.write(line + "\n")
    except UnicodeEncodeError:
        sys.stdout.write(json.dumps(payload, ensure_ascii=True, default=str) + "\n")
    sys.stdout.flush()


def _error(message: str, **extra) -> dict:
    return {"ok": False, "error": message, **extra}


@contextmanager
def _isolate_stdout():
    """Keep bridge protocol JSON-only on stdout while handlers run."""
    real_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = real_stdout


def cmd_ping(_params: dict) -> dict:
    return {"ok": True, "service": "dreamforge_desktop_bridge", "version": "0.1.0"}


def _worker_events_path() -> Path:
    return PROJECT_ROOT / "outputs" / "dreamforge" / "logs" / "worker.events"


def _scan_worker_events() -> dict:
    """Last-known worker state from worker.events (no subprocess)."""
    path = _worker_events_path()
    out: dict = {
        "events_exists": path.is_file(),
        "worker_ready": False,
        "boot_phase": "unknown",
        "boot_message": "",
        "last_error": None,
        "gpu_name": None,
        "vram_gb": None,
        "cuda_available": None,
        "mps_available": None,
    }
    if not path.is_file():
        return out
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    last_boot: dict | None = None
    last_ready: dict | None = None
    last_err: dict | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = evt.get("type")
        if t == "boot_progress":
            last_boot = evt
        elif t == "ready":
            last_ready = evt
        elif t == "error" and not evt.get("job_id"):
            last_err = evt
    if last_ready:
        out["worker_ready"] = True
        out["boot_phase"] = "ready"
        out["boot_message"] = ""
        out["gpu_name"] = last_ready.get("gpu_name")
        out["vram_gb"] = last_ready.get("vram_gb")
        out["cuda_available"] = last_ready.get("cuda_available")
        out["mps_available"] = last_ready.get("mps_available")
    elif last_boot:
        out["boot_phase"] = last_boot.get("phase") or "loading_pipeline"
        out["boot_message"] = last_boot.get("message") or ""
    if last_err:
        out["last_error"] = last_err.get("error") or last_err.get("message")
    return out


def cmd_get_health(_params: dict) -> dict:
    """LTX-style health snapshot for the desktop shell (read-only)."""
    worker = _scan_worker_events()
    if worker["worker_ready"]:
        health = "alive"
    elif worker.get("last_error"):
        health = "dead"
    elif worker.get("boot_message") or worker.get("boot_phase") not in ("unknown", "ready"):
        health = "booting"
    else:
        health = "unknown"
    return {
        "ok": True,
        "health": health,
        "bridge": "ok",
        "service": "dreamforge_desktop_bridge",
        **worker,
    }


def cmd_get_paths(_params: dict) -> dict:
    import _paths
    from dreamforge_runtime_paths import runtime_status

    status = runtime_status()
    paths = status.get("paths") or {}
    outputs = Path(paths.get("outputs_root") or (_paths.PROJECT_ROOT / "outputs"))
    previews = Path(paths.get("previews_dir") or (_paths.PROJECT_ROOT / "temp" / "previews"))
    live_preview = previews / "preview.jpg"
    engine_preview = _paths.BACKEND_ROOT / "temp" / "previews" / "preview.jpg"
    python_exe = paths.get("embedded_python") or str(_paths.PYTHON_EXE)
    return {
        "ok": True,
        "project_root": paths.get("data_root") or str(_paths.PROJECT_ROOT),
        "data_root": paths.get("data_root") or str(_paths.PROJECT_ROOT),
        "backend_root": paths.get("backend_root") or str(_paths.BACKEND_ROOT),
        "code_root": str(_paths.BACKEND_ROOT),
        "outputs_root": str(outputs),
        "temp_root": paths.get("temp_root") or str(_paths.PROJECT_ROOT / "temp"),
        "previews_dir": str(previews),
        "comfy_staging_dir": paths.get("comfy_staging_dir")
        or str(_paths.PROJECT_ROOT / "temp" / "comfy-staging"),
        "models_root": paths.get("models_root") or str(_paths.PROJECT_ROOT / "models"),
        "comfy_root": paths.get("comfy_root") or "",
        "install_root": paths.get("install_root") or "",
        "embedded_python_dir": paths.get("embedded_python_dir") or "",
        "embedded_python": python_exe,
        "live_preview_path": str(live_preview),
        "engine_preview_path": str(engine_preview),
        "python_exe": python_exe,
        "cli_script": str(CLI_SCRIPT),
        "outputs_exists": outputs.is_dir(),
        "setup_complete": not status.get("needs_setup_wizard", False),
        "runtime_config": status.get("config") or {},
    }


def cmd_get_runtime_status(_params: dict) -> dict:
    from dreamforge_runtime_paths import runtime_status

    return runtime_status()


def cmd_apply_runtime_preferences(params: dict) -> dict:
    from dreamforge_bootstrap import apply_runtime_preferences

    return apply_runtime_preferences(
        data_root=params.get("data_root"),
        models_root=params.get("models_root"),
        models_source=params.get("models_source"),
        setup_complete=params.get("setup_complete"),
    )


def cmd_validate_models_folder(params: dict) -> dict:
    from dreamforge_runtime_paths import validate_models_folder

    path = str(params.get("path") or "").strip()
    if not path:
        return _error("path is required")
    return validate_models_folder(
        Path(path),
        create=bool(params.get("create")),
    )


def cmd_get_bootstrap_system_info(_params: dict) -> dict:
    from dreamforge_bootstrap import bootstrap_system_info

    return bootstrap_system_info()


def cmd_get_setup_progress(_params: dict) -> dict:
    from dreamforge_bootstrap import get_setup_progress

    return get_setup_progress()


def cmd_run_bootstrap_step(params: dict) -> dict:
    from dreamforge_bootstrap import run_bootstrap_step

    step = str(params.get("step") or "").strip()
    if not step:
        return _error("step is required")
    return run_bootstrap_step(step)


def cmd_reset_setup_state(params: dict) -> dict:
    from dreamforge_bootstrap import reset_setup_state

    return reset_setup_state(clear_markers=bool(params.get("clear_markers")))


def cmd_repair_installation(params: dict) -> dict:
    from dreamforge_bootstrap import repair_installation

    return repair_installation(clear_markers=bool(params.get("clear_markers")))


def cmd_run_full_bootstrap(_params: dict) -> dict:
    from dreamforge_bootstrap import run_full_bootstrap

    return run_full_bootstrap()


def cmd_finalize_setup(params: dict) -> dict:
    from dreamforge_bootstrap import finalize_setup
    from dreamforge_runtime_paths import RuntimeConfig

    raw = params.get("config")
    config = RuntimeConfig.from_dict(raw) if isinstance(raw, dict) else None
    return finalize_setup(config)


def cmd_get_ui_defaults(_params: dict) -> dict:
    """Unified desktop performance presets, aspect ratios, controlnet cheats."""
    from modules.model_ui_defaults import ui_performance_choices

    performances = ui_performance_choices()

    cn_path = BACKEND_ROOT / "settings" / "powerup.json"
    cn_default = BACKEND_ROOT / "settings" / "powerup.default"
    controlnet = []
    for path in (cn_path, cn_default):
        if path.exists():
            import json

            data = json.loads(path.read_text(encoding="utf-8"))
            controlnet.extend([k for k in data.keys() if k not in controlnet])

    from dreamforge_aspect_presets import list_aspect_ratio_presets_ui

    aspect = list_aspect_ratio_presets_ui()
    return {
        "ok": True,
        "performances": performances,
        "controlnet_presets": controlnet,
        "aspect_ratios": aspect,
        "samplers": [
            "dpmpp_2m_sde_gpu",
            "euler",
            "euler_ancestral",
            "dpmpp_2m",
            "dpmpp_sde",
        ],
        "schedulers": ["karras", "normal", "exponential", "sgm_uniform"],
    }





def _resolve_cached_thumbnail(cache_subdir: str, model_filename: str, fallback: Path) -> str:
    """Match DreamForge web UI cache layout (see modules/util.py)."""
    cache_base = CACHE_ROOT / cache_subdir / Path(model_filename).name
    for suffix in (".jpeg", ".jpg", ".png", ".gif"):
        candidate = cache_base.with_suffix(suffix)
        if candidate.is_file():
            return str(candidate.resolve())
    if fallback.is_file():
        return str(fallback.resolve())
    return str(fallback)


def cmd_get_model_gallery(params: dict) -> dict:
    from dreamforge_model_library_cache import get_cached_model_gallery

    needle = (params.get("filter") or "").lower()
    force_refresh = bool(params.get("force_refresh"))
    items, from_cache = get_cached_model_gallery(force_refresh=force_refresh)
    if needle:
        items = [
            item
            for item in items
            if needle
            in f"{item.get('category', '')} {item.get('caption', '')} {item.get('engine_name', '')}".lower()
        ]
    return {"ok": True, "items": items, "count": len(items), "from_cache": from_cache}


def cmd_get_lora_gallery(params: dict) -> dict:
    from dreamforge_model_library_cache import get_cached_lora_gallery

    needle = (params.get("filter") or "").lower()
    force_refresh = bool(params.get("force_refresh"))
    items, from_cache = get_cached_lora_gallery(force_refresh=force_refresh)
    if needle:
        items = [
            item
            for item in items
            if needle in f"{item.get('name', '')} {item.get('relative_path', '')}".lower()
        ]
    return {"ok": True, "items": items, "count": len(items), "from_cache": from_cache}


def cmd_resolve_model_profile(params: dict) -> dict:
    from modules.model_ui_defaults import gallery_model_type_label, resolve_ui_profile

    caption = params.get("caption") or params.get("relative_path") or ""
    category = params.get("category") or "checkpoints"
    if caption.startswith("[") and "] " in caption:
        category, relative_name = caption.split("] ", 1)
        category = category.strip("[]")
        relative_name = relative_name.strip()
    else:
        relative_name = params.get("relative_path") or caption

    profile = resolve_ui_profile(
        relative_name,
        category=category,
        current_performance=params.get("performance") or "Lightning",
        lock_enabled=bool(params.get("lock_family_defaults", True)),
        preset_active=bool(params.get("preset_active", False)),
    )
    civit = params.get("civit_base")
    if not civit:
        civit = gallery_model_type_label(category, relative_name, shared_models=None)

    return {
        "ok": True,
        "profile": profile,
        "caption": caption or relative_name,
        "civit_base": civit,
        "relative_path": relative_name,
        "category": category,
    }


def cmd_get_inventory(params: dict) -> dict:
    from dreamforge_cli_inventory import list_system_fonts
    from dreamforge_model_library_cache import get_cached_inventory

    force_refresh = bool(params.get("force_refresh"))
    payload, from_cache = get_cached_inventory(force_refresh=force_refresh)
    if params.get("include_fonts"):
        payload = dict(payload)
        payload["fonts"] = list_system_fonts(font_filter=params.get("font_filter"))
    payload["from_cache"] = from_cache
    return payload


def cmd_refresh_model_library_cache(_params: dict) -> dict:
    from dreamforge_model_library_cache import rebuild_model_library_cache

    stats = rebuild_model_library_cache()
    return {"ok": True, **stats}


def cmd_list_outputs(params: dict) -> dict:
    from dreamforge_output_index import list_outputs

    since = params.get("since")
    if since is not None:
        since = float(since)
    limit = int(params.get("limit", 40))
    offset = int(params.get("offset", 0))
    model = params.get("model")
    session = params.get("session")
    items, total = list_outputs(
        since=since,
        model=model,
        limit=limit,
        offset=offset,
        session=session,
    )
    return {
        "ok": True,
        "items": items,
        "count": len(items),
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(items) < total,
    }


def cmd_get_generation_bundle(params: dict) -> dict:
    from dreamforge_output_index import get_generation_bundle

    manifest_path = params.get("manifest_path") or params.get("path")
    if not manifest_path:
        return _error("missing_manifest_path")
    payload = get_generation_bundle(str(manifest_path))
    payload["ok"] = payload.get("status") == "success"
    return payload


def cmd_search_outputs(params: dict) -> dict:
    from dreamforge_output_index import search_outputs

    query = params.get("query", "")
    limit = int(params.get("limit", 20))
    offset = int(params.get("offset", 0))
    items, total = search_outputs(query, limit=limit, offset=offset)
    return {
        "ok": True,
        "items": items,
        "count": len(items),
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(items) < total,
    }


def cmd_delete_output(params: dict) -> dict:
    from dreamforge_output_index import delete_generation

    manifest_path = params.get("manifest_path", "")
    result = delete_generation(manifest_path)
    if not result.get("ok"):
        return result
    return {**result, "ok": True}


def cmd_delete_output_image(params: dict) -> dict:
    from dreamforge_output_index import delete_output_image

    manifest_path = params.get("manifest_path", "")
    image_path = params.get("image_path", "")
    result = delete_output_image(manifest_path, image_path)
    if not result.get("ok"):
        return result
    return {**result, "ok": True}


def cmd_delete_session(params: dict) -> dict:
    from dreamforge_output_index import delete_session

    session = params.get("session", "")
    result = delete_session(session)
    if not result.get("ok"):
        return result
    return {**result, "ok": True}


def cmd_list_styles(_params: dict) -> dict:
    from dreamforge_agent_tools import list_style_recipes_for_agent

    recipes = list_style_recipes_for_agent(include_thumbnail=True)
    return {"ok": True, "styles": recipes}


def _style_recipe_label(style_id: str, spec: dict) -> str:
    original = str(spec.get("original_name") or "").strip()
    if original:
        return original
    return style_id.replace("_", " ").strip().title()


def _group_styles(_legacy_style_names: list[str] | None = None) -> dict:
    """Group ``STYLE_RECIPES`` for inventory cache (replaces SDXL CSV grouping)."""
    from dreamforge_style_recipes import STYLE_RECIPES

    buckets: dict[str, dict] = {
        "presets": {"id": "presets", "label": "Presets", "items": []},
        "classic": {"id": "classic", "label": "Classic SDXL", "items": []},
        "artify": {"id": "artify", "label": "Artify", "items": []},
        "other": {"id": "other", "label": "Other", "items": []},
    }
    selectable: list[str] = []
    for style_id in sorted(STYLE_RECIPES.keys()):
        spec = STYLE_RECIPES[style_id]
        selectable.append(style_id)
        item = {"id": style_id, "label": _style_recipe_label(style_id, spec)}
        original = str(spec.get("original_name") or "").lower()
        if spec.get("models"):
            buckets["presets"]["items"].append(item)
        elif original.startswith("artify"):
            buckets["artify"]["items"].append(item)
        elif original.startswith("style:") or original:
            buckets["classic"]["items"].append(item)
        else:
            buckets["other"]["items"].append(item)
    return {
        "selectable": selectable,
        "groups": [group for group in buckets.values() if group["items"]],
    }


def cmd_classify_models(_params: dict) -> dict:
    """Return per-file classifier verdicts for the entire models tree.

    Read-only.  Powers the desktop "Models -> Organize" preview pane so the
    user can see what DreamForge thinks every file is (role + family +
    confidence + reasons) before applying any moves.
    """
    from dreamforge_cli_inventory import MODELS_ROOT
    from modules.model_classifier import classify_directory

    classifications = classify_directory(MODELS_ROOT)
    items = [c.as_dict() for c in classifications]
    families: dict[str, int] = {}
    roles: dict[str, int] = {}
    for item in items:
        families[item["family"]] = families.get(item["family"], 0) + 1
        roles[item["role"]] = roles.get(item["role"], 0) + 1
    return {
        "ok": True,
        "models_root": str(MODELS_ROOT),
        "totals": {"files": len(items), "families": families, "roles": roles},
        "files": items,
    }


def cmd_relocate_downloaded_model(params: dict) -> dict:
    """Classify a freshly downloaded model and move it to its canonical folder.

    Civitai / Discover downloads always land under the user-picked category
    (usually ``checkpoints/``), but diffusion-only weights (Krea 2, Flux/Qwen
    UNet-only files, ...) must live under ``diffusion_models/`` or ComfyUI's
    ``CheckpointLoaderSimple`` rejects them with "Could not detect model type".
    This reads the safetensors header (high-confidence role+family) and relocates
    the single file when its canonical folder differs from where it landed.

    Params:
        path (str): absolute path to the downloaded file (preferred), or
        category + filename: resolved against MODELS_ROOT.
    """
    from pathlib import Path

    from dreamforge_cli_inventory import MODELS_ROOT
    from modules.model_classifier import classify_model_file
    from modules.model_organizer import _move_one, _unique_destination

    raw_path = str(params.get("path") or "").strip()
    if raw_path:
        source = Path(raw_path)
    else:
        category = str(params.get("category") or "checkpoints").strip() or "checkpoints"
        filename = str(params.get("filename") or "").strip()
        if not filename:
            return {"ok": False, "error": "relocate_downloaded_model requires path or filename"}
        source = Path(MODELS_ROOT) / category / filename

    if not source.is_file():
        return {"ok": False, "error": f"file not found: {source}"}

    classification = classify_model_file(source)
    target_dir = classification.target_dir
    if not target_dir:
        return {
            "ok": True,
            "moved": False,
            "reason": "no_canonical_target",
            "family": classification.family,
            "role": classification.role,
            "path": str(source),
        }

    try:
        current_folder = source.parent.name
    except (AttributeError, IndexError):
        current_folder = ""

    # Already in the right place (canonical folder or its legacy alias).
    from modules.model_classifier import LEGACY_ALIAS

    if current_folder == target_dir or LEGACY_ALIAS.get(current_folder) == target_dir:
        return {
            "ok": True,
            "moved": False,
            "reason": "already_in_canonical_folder",
            "family": classification.family,
            "role": classification.role,
            "path": str(source),
        }

    # Only relocate when the verdict is trustworthy (tensor-header derived).
    if not classification.role_from_header and classification.confidence != "high":
        return {
            "ok": True,
            "moved": False,
            "reason": f"low_confidence:{classification.confidence}",
            "family": classification.family,
            "role": classification.role,
            "path": str(source),
        }

    destination = _unique_destination(Path(MODELS_ROOT) / target_dir / source.name)
    success, error = _move_one(source, destination)
    if not success:
        return {"ok": False, "error": error, "path": str(source)}

    # Move sidecar metadata (.json / preview) alongside the weight file.
    moved_sidecars = []
    for ext in (".json", ".png", ".jpg", ".jpeg", ".webp", ".txt", ".civitai.info"):
        sidecar = source.with_suffix(ext)
        if sidecar.is_file():
            sidecar_dst = _unique_destination(destination.parent / sidecar.name)
            ok, _ = _move_one(sidecar, sidecar_dst)
            if ok:
                moved_sidecars.append(str(sidecar_dst))

    from dreamforge_model_library_cache import invalidate_model_library_cache

    invalidate_model_library_cache()

    return {
        "ok": True,
        "moved": True,
        "family": classification.family,
        "role": classification.role,
        "category": target_dir,
        "source": str(source),
        "destination": str(destination),
        "sidecars": moved_sidecars,
    }


def cmd_organize_models(params: dict) -> dict:
    """Plan (and optionally apply) automatic model organization.

    Params:
        apply (bool): when true, perform the moves; default is dry-run.
        include_low_confidence (bool): include low-confidence filename-only
            verdicts in the plan; default false (those land in ``ambiguous``).
    """
    from dreamforge_cli_inventory import MODELS_ROOT
    from modules.model_organizer import organize_models

    apply = bool(params.get("apply"))
    include_low = bool(params.get("include_low_confidence"))
    payload = organize_models(
        MODELS_ROOT,
        apply=apply,
        include_low_confidence=include_low,
    )
    if apply:
        from dreamforge_model_library_cache import invalidate_model_library_cache

        invalidate_model_library_cache()
    payload["ok"] = True
    return payload


def cmd_check_model_dependencies(params: dict) -> dict:
    from dreamforge_cli_inventory import check_model_dependencies, resolve_generation_model

    model_name = params.get("model") or params.get("engine_name")
    if not model_name:
        return _error("missing_model")
    model = resolve_generation_model(model_name)
    if not model:
        return _error(f"model_not_found: {model_name}")
    missing = check_model_dependencies(
        model,
        performance=params.get("performance"),
    )
    return {
        "ok": True,
        "model": model,
        "missing": missing,
        "ready": len(missing) == 0,
    }


def cmd_download_model_companions(params: dict) -> dict:
    from dreamforge_cli_inventory import check_model_dependencies, resolve_generation_model
    from dreamforge_companion_download import download_missing_companions

    model_name = params.get("model") or params.get("engine_name")
    if not model_name:
        return _error("missing_model")
    model = resolve_generation_model(model_name)
    if not model:
        return _error(f"model_not_found: {model_name}")

    missing = check_model_dependencies(
        model,
        performance=params.get("performance"),
    )
    ids = params.get("ids")
    if ids:
        wanted = {str(item) for item in ids}
        missing = [item for item in missing if item.get("id") in wanted]
    if not missing:
        return {"ok": True, "status": "ready", "downloaded": 0, "results": [], "errors": []}

    payload = download_missing_companions(missing)
    payload["ok"] = not payload.get("errors")
    payload["model"] = model
    if int(payload.get("downloaded") or 0) > 0:
        from dreamforge_model_library_cache import invalidate_model_library_cache

        invalidate_model_library_cache()
    return payload


def cmd_check_studio_resources(params: dict) -> dict:
    from dreamforge_cli_inventory import check_studio_resources

    studio_mode = params.get("studio_mode") or params.get("mode")
    if not studio_mode:
        return _error("missing_studio_mode")
    missing = check_studio_resources(
        str(studio_mode),
        upscale_method=params.get("upscale_method"),
    )
    return {
        "ok": True,
        "studio_mode": studio_mode,
        "missing": missing,
        "ready": len(missing) == 0,
    }


def cmd_check_image_prompt_resources(_params: dict) -> dict:
    from dreamforge_krita_resources import check_image_prompt_resources
    from dreamforge_companion_download import enrich_missing_dependency

    missing = [
        enrich_missing_dependency(item) for item in check_image_prompt_resources()
    ]
    return {"ok": True, "missing": missing, "ready": len(missing) == 0}


def cmd_download_companion_entries(params: dict) -> dict:
    """Download an explicit list of companion/studio assets to canonical model paths."""
    from dreamforge_companion_download import download_missing_companions, enrich_missing_dependency

    raw = params.get("items") or []
    if not isinstance(raw, list):
        return _error("invalid_items")
    enriched = [
        enrich_missing_dependency(dict(item))
        for item in raw
        if isinstance(item, dict)
    ]
    downloadable = [item for item in enriched if item.get("url")]
    if not downloadable:
        return {
            "ok": False,
            "status": "missing",
            "downloaded": 0,
            "results": [],
            "errors": [],
            "missing": enriched,
        }
    payload = download_missing_companions(downloadable)
    errors = list(payload.get("errors") or [])
    payload["ok"] = not errors
    if errors:
        first = errors[0]
        payload["error"] = first.get("error") or f"Failed to download {first.get('id', 'asset')}"
    if int(payload.get("downloaded") or 0) > 0:
        from dreamforge_model_library_cache import invalidate_model_library_cache

        invalidate_model_library_cache()
    return payload


def cmd_verify_companion_entries(params: dict) -> dict:
    """Verify an explicit list of companion/studio assets by canonical path."""
    from dreamforge_cli_inventory import companion_file_present
    from dreamforge_companion_download import enrich_missing_dependency

    raw = params.get("items") or []
    if not isinstance(raw, list):
        return _error("invalid_items")
    enriched = [
        enrich_missing_dependency(dict(item))
        for item in raw
        if isinstance(item, dict)
    ]
    missing = []
    present = []
    for item in enriched:
        min_bytes = int(item.get("min_bytes") or 1024 * 1024)
        if companion_file_present(item, min_bytes=min_bytes):
            present.append(item)
        else:
            missing.append(item)
    return {
        "ok": True,
        "ready": len(missing) == 0,
        "present": present,
        "missing": missing,
    }


def cmd_download_studio_resources(params: dict) -> dict:
    from dreamforge_cli_inventory import download_studio_resources

    studio_mode = params.get("studio_mode") or params.get("mode")
    if not studio_mode:
        return _error("missing_studio_mode")
    payload = download_studio_resources(
        str(studio_mode),
        upscale_method=params.get("upscale_method"),
    )
    payload["ok"] = payload.get("status") != "error" or bool(payload.get("results"))
    return payload


def cmd_ensure_creative_task_ready(params: dict) -> dict:
    from dreamforge_companion_download import ensure_creative_task_ready

    def _write_boot_progress(message: str) -> None:
        try:
            from dreamforge_worker_ipc import emit, events_file_path
            events_path = events_file_path(PROJECT_ROOT)
            emit({
                "type": "boot_progress",
                "phase": "preparing_tools",
                "message": message
            }, events_path)
        except Exception:
            pass

    model_name = params.get("model") or params.get("engine_name")
    studio_mode = params.get("studio_mode") or params.get("mode")
    if not model_name and not studio_mode:
        return _error("missing_model_or_studio_mode")
    payload = ensure_creative_task_ready(
        model_name=str(model_name) if model_name else None,
        studio_mode=str(studio_mode) if studio_mode else None,
        upscale_method=params.get("upscale_method"),
        performance=params.get("performance"),
        edit_task=params.get("edit_task"),
        auto_download_tier_a=bool(params.get("auto_download_tier_a", True)),
        auto_download_tier_b=bool(params.get("auto_download_tier_b", False)),
        auto_install_nodes=bool(params.get("auto_install_nodes", False)),
        template_id=params.get("template_id"),
        progress=_write_boot_progress,
    )
    payload["ok"] = bool(payload.get("ready"))
    return payload


def cmd_resolve_creative_task(params: dict) -> dict:
    from dreamforge_creative_tasks import enforce_creative_task_settings, resolve_creative_task

    studio_mode = params.get("studio_mode") or params.get("mode")
    if not studio_mode:
        return _error("missing_studio_mode")
    settings = params.get("settings") if isinstance(params.get("settings"), dict) else {}
    gallery = params.get("model_gallery") if isinstance(params.get("model_gallery"), list) else []
    if params.get("enforce"):
        patch = enforce_creative_task_settings(
            settings,
            studio_mode=str(studio_mode),
            model_gallery=gallery,
            vram_profile=params.get("vram_profile"),
            advanced_mode=bool(params.get("advanced_mode")),
            template_id=params.get("template_id"),
            selected_image=str(params.get("selected_image") or ""),
            user_picked_model=bool(params.get("user_picked_model")),
        )
        return {"ok": True, "patch": patch, "studio_mode": studio_mode}
    payload = resolve_creative_task(
        str(studio_mode),
        settings,
        gallery,
        vram_profile=params.get("vram_profile"),
        advanced_mode=bool(params.get("advanced_mode")),
        selected_image=str(params.get("selected_image") or ""),
        template_id=params.get("template_id"),
        user_picked_model=bool(params.get("user_picked_model")),
    )
    payload["ok"] = bool(payload.get("ok", True))
    return payload


def cmd_list_creative_templates(params: dict) -> dict:
    from dreamforge_creative_templates import list_creative_templates

    studio_mode = params.get("studio_mode") or params.get("mode")
    templates = list_creative_templates(
        studio_mode=str(studio_mode) if studio_mode else None,
    )
    return {"ok": True, "templates": templates}


def cmd_resolve_creative_template(params: dict) -> dict:
    from dreamforge_creative_templates import resolve_template_patch

    template_id = params.get("template_id")
    if not template_id:
        return _error("missing_template_id")
    settings = params.get("settings") if isinstance(params.get("settings"), dict) else {}
    payload = resolve_template_patch(
        str(template_id),
        base=settings,
        vram_profile=params.get("vram_profile"),
        post_upscale_enabled=bool(params.get("post_upscale_enabled")),
    )
    payload["ok"] = True
    return payload


def cmd_preview_automation(params: dict) -> dict:
    from dreamforge_automation import preview_automation

    spec = params.get("spec") if isinstance(params.get("spec"), dict) else params
    payload = preview_automation(spec)
    payload["ok"] = bool(payload.get("job_count", 0) >= 0)
    return payload





def cmd_get_user_style_profile(_params: dict) -> dict:
    from dreamforge_user_style_profile import export_profile

    payload = export_profile()
    payload["ok"] = True
    return payload


def cmd_save_user_style_profile(params: dict) -> dict:
    from dreamforge_user_style_profile import UserStyleProfile, load_profile, save_profile

    raw = params.get("profile")
    if not isinstance(raw, dict):
        current = load_profile()
        if "enabled" in params:
            current.enabled = bool(params["enabled"])
            profile = save_profile(current)
            return {"ok": True, "status": "success", "profile": profile.to_dict()}
        return _error("missing_profile")

    profile = UserStyleProfile(
        enabled=bool(raw.get("enabled", True)),
        favorite_models=[str(item) for item in raw.get("favorite_models") or []],
        favorite_styles=[str(item) for item in raw.get("favorite_styles") or []],
        aspect_ratios=[str(item) for item in raw.get("aspect_ratios") or []],
        workflow_modes=[str(item) for item in raw.get("workflow_modes") or []],
        generation_count=int(raw.get("generation_count") or 0),
    )
    profile = save_profile(profile)
    return {"ok": True, "status": "success", "profile": profile.to_dict()}


def cmd_clear_user_style_profile(_params: dict) -> dict:
    from dreamforge_user_style_profile import clear_profile

    profile = clear_profile()
    return {"ok": True, "status": "success", "profile": profile.to_dict()}


def cmd_export_user_style_profile(_params: dict) -> dict:
    from dreamforge_user_style_profile import export_profile

    payload = export_profile()
    payload["ok"] = True
    return payload


def cmd_generate_inpaint_selection_mask(params: dict) -> dict:
    from dreamforge_inpaint_selection import generate_inpaint_selection_mask

    image_path = str(params.get("image_path") or params.get("imagePath") or "").strip()
    selection = str(params.get("selection") or params.get("kind") or "").strip()
    if not image_path:
        return {"ok": False, "error": "image_path_required"}
    tap_x = params.get("tap_x", params.get("tapX"))
    tap_y = params.get("tap_y", params.get("tapY"))
    output_path = params.get("output_path") or params.get("outputPath")
    result = generate_inpaint_selection_mask(
        image_path,
        selection,
        tap_x=float(tap_x) if tap_x is not None else None,
        tap_y=float(tap_y) if tap_y is not None else None,
        output_path=str(output_path).strip() if output_path else None,
    )
    return result


def cmd_write_studio_mask_png(params: dict) -> dict:
    """Persist a UI-painted inpaint mask PNG under backend temp/studio_masks."""
    import base64
    import binascii
    import re
    import time

    from _paths import TEMP_ROOT, bootstrap_paths

    bootstrap_paths()
    raw = str(
        params.get("data_base64")
        or params.get("dataBase64")
        or params.get("data_url")
        or ""
    ).strip()
    if not raw:
        return {"ok": False, "error": "data_base64_required"}
    payload = raw
    match = re.match(r"^data:image/(?:png|jpeg|webp);base64,(.+)$", raw, flags=re.I)
    if match:
        payload = match.group(1)
    try:
        data = base64.b64decode(payload, validate=False)
    except (ValueError, binascii.Error) as exc:
        return {"ok": False, "error": f"invalid_base64: {exc}"}
    if not data:
        return {"ok": False, "error": "empty_image_payload"}
    folder = TEMP_ROOT / "studio_masks"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"mask_{int(time.time() * 1000)}.png"
    path.write_bytes(data)
    return {"ok": True, "path": str(path.resolve())}


def cmd_suggest_dynamic_preset(params: dict) -> dict:
    from dreamforge_dynamic_presets import suggest_dynamic_preset

    intent = str(params.get("intent") or params.get("instruction") or "")
    settings = params.get("settings") if isinstance(params.get("settings"), dict) else {}
    payload = suggest_dynamic_preset(intent, settings)
    payload["ok"] = True
    return payload


def cmd_install_custom_node_packs(params: dict) -> dict:
    from dreamforge_comfy_install import ensure_custom_node_pack
    from dreamforge_comfy_manager import (
        fix_packs_via_manager,
        install_packs_via_manager,
        resolve_pack_install_strategy,
    )
    from dreamforge_workflow_planner import _recipe_entry_for_pack, assess_custom_node_pack

    pack_ids = params.get("pack_ids") or params.get("packs") or []
    if isinstance(pack_ids, str):
        pack_ids = [pack_ids]
    strategy = str(params.get("strategy") or "auto").strip().lower()
    pack_strategies = params.get("pack_strategies") if isinstance(params.get("pack_strategies"), dict) else {}
    messages: list[str] = []
    from dreamforge_comfy_manager import make_progress_sink

    _progress = make_progress_sink(messages, progress_file=params.get("progress_file"))

    installed: list[str] = []
    errors: list[dict[str, str]] = []
    manager_ids: list[str] = []
    pinned_ids: list[str] = []
    for raw_id in pack_ids:
        pack_id = str(raw_id).strip()
        if not pack_id:
            continue
        entry = _recipe_entry_for_pack(pack_id)
        pack_strategy = str(pack_strategies.get(pack_id) or strategy or "auto").strip().lower()
        if pack_strategy == "auto":
            pack_strategy = resolve_pack_install_strategy(entry, pack_id)
        if pack_strategy == "manager":
            manager_ids.append(pack_id)
        else:
            if not entry:
                errors.append({"pack_id": pack_id, "error": "unknown custom node pack"})
                continue
            pinned_ids.append(pack_id)

    if manager_ids:
        manager_result = install_packs_via_manager(
            manager_ids,
            progress=_progress,
            exit_on_fail=bool(params.get("exit_on_fail")),
        )
        messages.extend(manager_result.messages)
        installed.extend(manager_result.installed)
        errors.extend(manager_result.errors)
        if manager_result.installed and params.get("fix_manager_deps", True):
            fix_result = fix_packs_via_manager(manager_result.installed, progress=_progress)
            messages.extend(fix_result.messages)
            errors.extend(fix_result.errors)

    for pack_id in pinned_ids:
        entry = _recipe_entry_for_pack(pack_id)
        if not entry:
            errors.append({"pack_id": pack_id, "error": "unknown custom node pack"})
            continue
        try:
            ensure_custom_node_pack(entry, progress=_progress)
            installed.append(pack_id)
        except Exception as exc:
            errors.append({"pack_id": pack_id, "error": str(exc)})

    needs_restart = bool(installed)
    if installed and params.get("restart_comfy", True):
        try:
            from dreamforge_comfy_server import restart_managed_comfy_server

            _progress("Restarting ComfyUI to register new custom nodes…")
            restart_managed_comfy_server(timeout_s=90.0, reason="custom_node_install")
        except Exception as exc:
            messages.append(f"ComfyUI restart failed: {exc}")

    object_info = None
    if installed and not params.get("skip_object_info"):
        try:
            from dreamforge_comfy_server import fetch_comfy_object_info

            object_info = fetch_comfy_object_info(timeout_s=30.0)
        except Exception:
            object_info = None

    packs = [assess_custom_node_pack(pack_id, object_info=object_info) for pack_id in installed]
    ready = bool(installed) and not errors and all(item.get("ready") for item in packs)
    return {
        "ok": ready,
        "ready": ready,
        "installed": installed,
        "packs": packs,
        "errors": errors,
        "messages": messages,
        "needs_comfy_restart": needs_restart,
    }


def cmd_install_workflow_models(params: dict) -> dict:
    from dreamforge_comfy_manager import install_workflow_models, make_progress_sink, workflow_model_ready

    catalog_ids = params.get("catalog_ids") or params.get("models") or []
    if isinstance(catalog_ids, str):
        catalog_ids = [catalog_ids]
    messages: list[str] = []
    _progress = make_progress_sink(messages, progress_file=params.get("progress_file"))

    result = install_workflow_models(
        [str(item).strip() for item in catalog_ids if str(item).strip()],
        progress=_progress,
        prefer_manager=bool(params.get("prefer_manager", True)),
    )
    ready = bool(result.installed) and not result.errors
    if catalog_ids:
        ready = all(workflow_model_ready(str(item)) for item in catalog_ids) and not result.errors
    return {
        "ok": ready,
        "ready": ready,
        "installed": result.installed,
        "errors": result.errors,
        "messages": messages,
    }


def cmd_get_manager_queue_status(_params: dict) -> dict:
    from dreamforge_comfy_manager import get_manager_queue_status

    return get_manager_queue_status()


def cmd_custom_tool_dependencies(params: dict) -> dict:
    from dreamforge_custom_tools import custom_tool_dependency_entries, find_custom_tool

    tool_id = str(params.get("tool_id") or params.get("custom_tool_id") or "").strip()
    tool = find_custom_tool(tool_id)
    if not tool:
        return {"ok": False, "error": f"custom tool not found: {tool_id}", "missing": []}
    object_info = None
    if params.get("use_object_info"):
        try:
            from dreamforge_comfy_server import fetch_comfy_object_info

            object_info = fetch_comfy_object_info(timeout_s=20.0)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "missing": []}
    missing = custom_tool_dependency_entries(tool, object_info=object_info)
    return {
        "ok": True,
        "ready": not missing,
        "missing": missing,
        "tool_id": tool_id,
        "tool_name": tool.get("name") or tool_id,
    }


def cmd_check_custom_node_packs(params: dict) -> dict:
    from dreamforge_workflow_planner import assess_custom_node_pack

    pack_ids = params.get("pack_ids") or params.get("packs") or []
    if isinstance(pack_ids, str):
        pack_ids = [pack_ids]
    object_info = None
    if params.get("use_object_info"):
        try:
            from dreamforge_comfy_server import fetch_comfy_object_info

            object_info = fetch_comfy_object_info(timeout_s=20.0)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "packs": []}

    packs = [assess_custom_node_pack(str(pack_id), object_info=object_info) for pack_id in pack_ids]
    return {
        "ok": True,
        "packs": packs,
        "ready": all(item.get("ready") for item in packs) if packs else True,
    }


def cmd_check_comfy_backend(_params: dict) -> dict:
    from dreamforge_comfy_ideogram4 import IDEOGRAM4_COMFY_VERSION
    import _paths

    comfy_dir = Path(_paths.COMFY_ROOT)
    pin_file = BACKEND_ROOT / ".dreamforge_comfy_pin"
    target = IDEOGRAM4_COMFY_VERSION
    current = pin_file.read_text(encoding="utf-8").strip() if pin_file.is_file() else ""
    
    installed = comfy_dir.is_dir() and any(comfy_dir.iterdir())
    needs_update = not installed or current != target
    
    return {
        "ok": True,
        "installed": installed,
        "needs_update": needs_update,
        "current": current,
        "target": target,
    }


def cmd_install_comfy_backend(params: dict) -> dict:
    from dreamforge_comfy_install import ensure_dreamforge_comfy_backend
    
    try:
        ensure_dreamforge_comfy_backend(
            progress=lambda msg: print(f"[Comfy Install] {msg}", file=sys.stderr),
            optional_nodes=params.get("optional_nodes", False)
        )
        return {"ok": True}
    except Exception as exc:
        import traceback
        traceback.print_exc(file=sys.stderr)
        return {"ok": False, "error": str(exc)}


def cmd_dry_run(params: dict) -> dict:
    from dreamforge_engine import DreamForgeEngine

    try:
        plan = DreamForgeEngine.dry_run(params)
        return {"ok": True, "plan": plan}
    except Exception as exc:
        return _error(str(exc), detail=type(exc).__name__)



def cmd_brain_plan(params: dict) -> dict:
    from dreamforge_engine import DreamForgeEngine

    try:
        instruction = str(params.get("instruction") or params.get("prompt") or "")
        decision = DreamForgeEngine.plan(
            instruction,
            current_settings=params.get("current_settings") if isinstance(params.get("current_settings"), dict) else params,
            selected_image=str(params.get("selected_image") or params.get("input_image") or params.get("upscale_image") or ""),
            gallery=params.get("gallery") if isinstance(params.get("gallery"), list) else [],
            brain_provider=str(params.get("brain_provider") or "auto"),
            brain_base_url=str(params.get("brain_base_url") or ""),
            brain_model=str(params.get("brain_model") or ""),
            brain_api_key=str(params.get("brain_api_key") or ""),
        )
        return {"ok": True, "decision": decision}
    except Exception as exc:
        return _error(str(exc), detail=type(exc).__name__)


def cmd_build_cli_argv(params: dict) -> dict:
    """Build argv for dreamforge_cli_direct.py from a generation request."""
    argv = [str(CLI_SCRIPT)]
    if params.get("json"):
        argv.append("--json")

    def add(flag: str, value) -> None:
        if value is None:
            return
        if isinstance(value, bool):
            if value:
                argv.append(flag)
            return
        if isinstance(value, list):
            for item in value:
                argv.extend([flag, str(item)])
            return
        argv.extend([flag, str(value)])

    add("--model", params.get("model") or params.get("base_model"))
    add("--prompt", params.get("prompt"))
    add("--negative-prompt", params.get("negative_prompt"))
    add("--aspect-ratio", params.get("aspect_ratio"))
    add("--width", params.get("width"))
    add("--height", params.get("height"))
    add("--seed", params.get("seed"))
    add("--image-number", params.get("image_number"))
    add("--output", params.get("output"))
    add("--performance", params.get("performance"))
    add("--steps", params.get("steps"))
    add("--cfg-scale", params.get("cfg_scale"))
    add("--sampler", params.get("sampler"))
    add("--scheduler", params.get("scheduler"))
    add("--input-image", params.get("input_image"))
    add("--reference-image", params.get("reference_image"))
    add("--reference-images", params.get("reference_images"))
    add("--identity-mode", params.get("identity_mode"))
    add("--face-preservation", params.get("face_preservation"))
    add("--control-images", params.get("control_images"))
    add("--comfy-workflow-api", params.get("comfy_workflow_api"))
    add("--use-comfy-server", params.get("use_comfy_server"))
    add("--upscale-image", params.get("upscale_image"))
    add("--upscale-method", params.get("upscale_method"))
    add("--upscale-preset", params.get("upscale_preset"))
    add("--upscale-by", params.get("upscale_by"))
    add("--upscale-denoise", params.get("upscale_denoise"))
    add("--upscale-tile-width", params.get("upscale_tile_width"))
    add("--upscale-tile-height", params.get("upscale_tile_height"))
    add("--upscale-tile-padding", params.get("upscale_tile_padding"))
    add("--upscale-mask-blur", params.get("upscale_mask_blur"))
    add("--upscale-seam-fix-mode", params.get("upscale_seam_fix_mode"))
    add("--upscale-force-uniform-tiles", params.get("upscale_force_uniform_tiles"))
    add("--upscale-tiled-decode", params.get("upscale_tiled_decode"))
    add("--edit-type", params.get("edit_type"))
    add("--edit-strength", params.get("edit_strength"))
    add("--qwen-edit-mode", params.get("qwen_edit_mode"))
    add("--qwen-image-shift", params.get("qwen_image_shift"))
    add("--qwen-scale-megapixels", params.get("qwen_scale_megapixels"))
    add("--qwen-preserve-resolution", params.get("qwen_preserve_resolution"))
    add("--qwen-preserve-megapixels", params.get("qwen_preserve_megapixels"))
    add("--inpaint-mask-path", params.get("inpaint_mask_path"))
    add("--inpaint-grow", params.get("inpaint_grow"))
    add("--inpaint-feather", params.get("inpaint_feather"))
    add("--inpaint-mask-grow-by", params.get("inpaint_mask_grow_by"))
    add("--inpaint-hard-mask", params.get("inpaint_hard_mask"))
    add("--preserve-character", params.get("preserve_character"))
    add("--preserve-style", params.get("preserve_style"))
    add("--preserve-text", params.get("preserve_text"))
    add("--vram-profile", params.get("vram_profile"))
    add("--style", params.get("style"))
    add("--sdxl-styles", params.get("styles"))
    add("--brand-kit", params.get("brand_kit"))
    add("--subject", params.get("subject"))
    add("--composition", params.get("composition"))
    add("--lighting", params.get("lighting"))
    add("--camera", params.get("camera"))
    add("--brand-colors", params.get("brand_colors"))
    add("--materials", params.get("materials"))
    add("--visual-style", params.get("visual_style"))
    add("--workflow-mode", params.get("workflow_mode"))
    add("--arabic-text", params.get("arabic_text"))
    if params.get("execute_workflow_plan"):
        argv.append("--execute-workflow-plan")
    workflow_plan = params.get("workflow_plan")
    if workflow_plan is not None:
        if isinstance(workflow_plan, (list, dict)):
            import json

            argv.extend(["--workflow-plan", json.dumps(workflow_plan, ensure_ascii=False)])
        else:
            add("--workflow-plan", workflow_plan)
    if params.get("validate_output"):
        argv.append("--validate-output")
    if params.get("no_manifest"):
        argv.append("--no-manifest")
    for lora in params.get("loras") or []:
        argv.extend(["--lora", lora])
    if params.get("dry_run"):
        argv.append("--dry-run")
    add("--stream-file", params.get("stream_file"))

    import _paths

    return {
        "ok": True,
        "argv": argv,
        "python": str(_paths.PYTHON_EXE),
        "cwd": str(_paths.PROJECT_ROOT),
    }


from dreamforge_studio_bridge import STUDIO_HANDLERS  # noqa: E402


HANDLERS = {
    "ping": cmd_ping,
    "get_health": cmd_get_health,
    "get_paths": cmd_get_paths,
    "get_runtime_status": cmd_get_runtime_status,
    "apply_runtime_preferences": cmd_apply_runtime_preferences,
    "validate_models_folder": cmd_validate_models_folder,
    "get_bootstrap_system_info": cmd_get_bootstrap_system_info,
    "get_setup_progress": cmd_get_setup_progress,
    "run_bootstrap_step": cmd_run_bootstrap_step,
    "reset_setup_state": cmd_reset_setup_state,
    "repair_installation": cmd_repair_installation,
    "run_full_bootstrap": cmd_run_full_bootstrap,
    "finalize_setup": cmd_finalize_setup,
    "get_inventory": cmd_get_inventory,
    "get_model_gallery": cmd_get_model_gallery,
    "get_lora_gallery": cmd_get_lora_gallery,
    "refresh_model_library_cache": cmd_refresh_model_library_cache,
    "resolve_model_profile": cmd_resolve_model_profile,
    "list_outputs": cmd_list_outputs,
    "get_generation_bundle": cmd_get_generation_bundle,
    "search_outputs": cmd_search_outputs,
    "delete_output": cmd_delete_output,
    "delete_output_image": cmd_delete_output_image,
    "delete_session": cmd_delete_session,
    "dry_run": cmd_dry_run,
    "brain_plan": cmd_brain_plan,
    "build_cli_argv": cmd_build_cli_argv,
    "list_styles": cmd_list_styles,
    "get_ui_defaults": cmd_get_ui_defaults,
    "classify_models": cmd_classify_models,
    "organize_models": cmd_organize_models,
    "relocate_downloaded_model": cmd_relocate_downloaded_model,
    "check_model_dependencies": cmd_check_model_dependencies,
    "download_model_companions": cmd_download_model_companions,
    "check_studio_resources": cmd_check_studio_resources,
    "check_image_prompt_resources": cmd_check_image_prompt_resources,
    "download_companion_entries": cmd_download_companion_entries,
    "verify_companion_entries": cmd_verify_companion_entries,
    "ensure_creative_task_ready": cmd_ensure_creative_task_ready,
    "resolve_creative_task": cmd_resolve_creative_task,
    "list_creative_templates": cmd_list_creative_templates,
    "resolve_creative_template": cmd_resolve_creative_template,
    "preview_automation": cmd_preview_automation,
    "download_studio_resources": cmd_download_studio_resources,
    "get_user_style_profile": cmd_get_user_style_profile,
    "save_user_style_profile": cmd_save_user_style_profile,
    "clear_user_style_profile": cmd_clear_user_style_profile,
    "export_user_style_profile": cmd_export_user_style_profile,
    "generate_inpaint_selection_mask": cmd_generate_inpaint_selection_mask,
    "write_studio_mask_png": cmd_write_studio_mask_png,
    "suggest_dynamic_preset": cmd_suggest_dynamic_preset,
    "check_custom_node_packs": cmd_check_custom_node_packs,
    "install_custom_node_packs": cmd_install_custom_node_packs,
    "install_workflow_models": cmd_install_workflow_models,
    "get_manager_queue_status": cmd_get_manager_queue_status,
    "custom_tool_dependencies": cmd_custom_tool_dependencies,
    "check_comfy_backend": cmd_check_comfy_backend,
    "install_comfy_backend": cmd_install_comfy_backend,
    **STUDIO_HANDLERS,
}


def handle_request(line: str) -> dict:
    try:
        req = json.loads(line)
    except json.JSONDecodeError as exc:
        return _error(f"invalid_json: {exc}")

    cmd = req.get("cmd")
    params = req.get("params") or {}
    if not cmd:
        return _error("missing_cmd")
    handler = HANDLERS.get(cmd)
    if not handler:
        return _error(f"unknown_cmd: {cmd}")
    try:
        from dreamforge_runtime_paths import init_runtime_paths

        init_runtime_paths()
    except Exception:
        pass
    try:
        with _isolate_stdout():
            result = handler(params)
        if "ok" not in result:
            result["ok"] = True
        return result
    except Exception as exc:
        import traceback

        return _error(str(exc), detail=type(exc).__name__, traceback=traceback.format_exc())


def run_stdio_loop() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        _emit(handle_request(line))


def main() -> None:
    parser = argparse.ArgumentParser(description="DreamForge desktop JSON bridge")
    parser.add_argument("--once", type=str, help='Run single command JSON, e.g. \'{"cmd":"ping"}\'')
    args = parser.parse_args()
    if args.once:
        _emit(handle_request(args.once))
        return
    run_stdio_loop()


if __name__ == "__main__":
    main()
