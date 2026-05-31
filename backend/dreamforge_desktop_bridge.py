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
import sys
from pathlib import Path
from types import SimpleNamespace

from _paths import BACKEND_ROOT, PROJECT_ROOT, PYTHON_EXE, extend_sys_path

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
        line = json.dumps(payload, ensure_ascii=False, default=str)
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
    outputs = PROJECT_ROOT / "outputs"
    live_preview = outputs / "preview.jpg"
    engine_preview = BACKEND_ROOT / "outputs" / "preview.jpg"
    return {
        "ok": True,
        "project_root": str(PROJECT_ROOT),
        "backend_root": str(BACKEND_ROOT),
        "code_root": str(BACKEND_ROOT),
        "outputs_root": str(outputs),
        "live_preview_path": str(live_preview),
        "engine_preview_path": str(engine_preview),
        "python_exe": str(PYTHON_EXE),
        "cli_script": str(CLI_SCRIPT),
        "outputs_exists": outputs.is_dir(),
    }


def cmd_get_ui_defaults(_params: dict) -> dict:
    """DreamForge-style performance presets, aspect ratios, controlnet cheats."""
    perf_path = BACKEND_ROOT / "settings" / "performance.json"
    perf_default = BACKEND_ROOT / "settings" / "performance.default"
    performances = []
    if perf_default.exists():
        import json

        data = json.loads(perf_default.read_text(encoding="utf-8"))
        performances = list(data.keys())
    if perf_path.exists():
        import json

        data = json.loads(perf_path.read_text(encoding="utf-8"))
        for name in data:
            if name not in performances:
                performances.append(name)

    cn_path = BACKEND_ROOT / "settings" / "powerup.json"
    cn_default = BACKEND_ROOT / "settings" / "powerup.default"
    controlnet = []
    for path in (cn_path, cn_default):
        if path.exists():
            import json

            data = json.loads(path.read_text(encoding="utf-8"))
            controlnet.extend([k for k in data.keys() if k not in controlnet])

    aspect = [
        "1024×1024",
        "1152×896",
        "896×1152",
        "1344×768",
        "768×1344",
        "1536×640",
        "640×1536",
    ]
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
        current_performance=params.get("performance") or "Speed",
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


def cmd_list_reference_packs(_params: dict) -> dict:
    from dreamforge_reference_packs import list_reference_packs

    return {"ok": True, "packs": list_reference_packs()}


def cmd_save_reference_pack(params: dict) -> dict:
    from dreamforge_reference_packs import upsert_reference_pack

    pack = upsert_reference_pack(params)
    return {"ok": True, "pack": pack}


def cmd_delete_reference_pack(params: dict) -> dict:
    from dreamforge_reference_packs import delete_reference_pack

    pack_id = str(params.get("id") or params.get("pack_id") or "")
    deleted = delete_reference_pack(pack_id)
    return {"ok": True, "deleted": deleted}


def cmd_list_identities(params: dict) -> dict:
    from dreamforge_identity_registry import list_identities, search_identities

    identity_type = params.get("type")
    query = str(params.get("query") or "").strip()
    identities = search_identities(query, identity_type) if query else list_identities(identity_type)
    return {"ok": True, "identities": identities}


def cmd_save_identity(params: dict) -> dict:
    from dreamforge_identity_registry import upsert_identity

    identity = upsert_identity(params)
    return {"ok": True, "identity": identity}


def cmd_delete_identity(params: dict) -> dict:
    from dreamforge_identity_registry import delete_identity

    identity_id = str(params.get("id") or params.get("identity_id") or "")
    deleted = delete_identity(identity_id)
    return {"ok": True, "deleted": deleted}


def cmd_suggest_dynamic_preset(params: dict) -> dict:
    from dreamforge_dynamic_presets import suggest_dynamic_preset

    intent = str(params.get("intent") or params.get("instruction") or "")
    settings = params.get("settings") if isinstance(params.get("settings"), dict) else {}
    payload = suggest_dynamic_preset(intent, settings)
    payload["ok"] = True
    return payload


def cmd_check_custom_node_packs(params: dict) -> dict:
    from dreamforge_workflow_planner import assess_custom_node_pack

    pack_ids = params.get("pack_ids") or params.get("packs") or []
    if isinstance(pack_ids, str):
        pack_ids = [pack_ids]
    object_info = None
    if params.get("use_object_info"):
        try:
            from dreamforge_comfy_server import ensure_comfy_running
            from dreamforge_comfy_client import ComfyClient

            server = ensure_comfy_running(timeout_s=20.0)
            object_info = ComfyClient(server.base_url).object_info(timeout_s=20.0)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "packs": []}

    packs = [assess_custom_node_pack(str(pack_id), object_info=object_info) for pack_id in pack_ids]
    return {
        "ok": True,
        "packs": packs,
        "ready": all(item.get("ready") for item in packs) if packs else True,
    }


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
    add("--reference-images", params.get("reference_images"))
    add("--reference-pack-id", params.get("reference_pack_id"))
    add("--reference-pack-role", params.get("reference_pack_role"))
    add("--identity-id", params.get("identity_id"))
    add("--identity-role", params.get("identity_role"))
    add("--identity-mode", params.get("identity_mode"))
    add("--face-preservation", params.get("face_preservation"))
    add("--control-images", params.get("control_images"))
    add("--comfy-workflow-api", params.get("comfy_workflow_api"))
    add("--use-comfy-server", params.get("use_comfy_server"))
    add("--upscale-image", params.get("upscale_image"))
    add("--upscale-method", params.get("upscale_method"))
    add("--edit-type", params.get("edit_type"))
    add("--edit-strength", params.get("edit_strength"))
    add("--qwen-edit-mode", params.get("qwen_edit_mode"))
    add("--qwen-image-shift", params.get("qwen_image_shift"))
    add("--qwen-scale-megapixels", params.get("qwen_scale_megapixels"))
    add("--inpaint-mask-path", params.get("inpaint_mask_path"))
    add("--inpaint-grow", params.get("inpaint_grow"))
    add("--inpaint-feather", params.get("inpaint_feather"))
    add("--inpaint-mask-grow-by", params.get("inpaint_mask_grow_by"))
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

    return {
        "ok": True,
        "argv": argv,
        "python": str(PYTHON_EXE),
        "cwd": str(PROJECT_ROOT),
    }


from dreamforge_studio_bridge import STUDIO_HANDLERS  # noqa: E402


HANDLERS = {
    "ping": cmd_ping,
    "get_health": cmd_get_health,
    "get_paths": cmd_get_paths,
    "get_inventory": cmd_get_inventory,
    "get_model_gallery": cmd_get_model_gallery,
    "get_lora_gallery": cmd_get_lora_gallery,
    "refresh_model_library_cache": cmd_refresh_model_library_cache,
    "resolve_model_profile": cmd_resolve_model_profile,
    "list_outputs": cmd_list_outputs,
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
    "check_model_dependencies": cmd_check_model_dependencies,
    "download_model_companions": cmd_download_model_companions,
    "check_studio_resources": cmd_check_studio_resources,
    "download_studio_resources": cmd_download_studio_resources,
    "get_user_style_profile": cmd_get_user_style_profile,
    "save_user_style_profile": cmd_save_user_style_profile,
    "clear_user_style_profile": cmd_clear_user_style_profile,
    "export_user_style_profile": cmd_export_user_style_profile,
    "list_reference_packs": cmd_list_reference_packs,
    "save_reference_pack": cmd_save_reference_pack,
    "delete_reference_pack": cmd_delete_reference_pack,
    "list_identities": cmd_list_identities,
    "save_identity": cmd_save_identity,
    "delete_identity": cmd_delete_identity,
    "suggest_dynamic_preset": cmd_suggest_dynamic_preset,
    "check_custom_node_packs": cmd_check_custom_node_packs,
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
