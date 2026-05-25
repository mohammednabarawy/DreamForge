"""JSON-RPC bridge for DreamForge (Tauri desktop).

Reads one JSON object per line on stdin; writes one JSON object per line on stdout.
Designed to be invoked from Rust without a separate HTTP server.

Commands:
  ping, get_paths, get_inventory, get_model_gallery, get_lora_gallery,
  resolve_model_profile, list_outputs, search_outputs,
  dry_run, build_cli_argv, list_use_cases, get_ui_defaults,
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
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except UnicodeEncodeError:
        sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
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


def _load_style_groups_from_csv() -> list[dict]:
    """Preserve DreamForge styles.csv section order (>>>>>> headers + Style: rows)."""
    import csv

    groups: list[dict] = []
    current_label = "General"
    current_id = "general"
    current_items: list[dict] = []

    def flush() -> None:
        if current_items:
            groups.append(
                {
                    "id": current_id,
                    "label": current_label,
                    "items": current_items,
                }
            )

    for style_table in (
        BACKEND_ROOT / "settings" / "styles.csv",
        BACKEND_ROOT / "settings" / "styles.default",
    ):
        if not style_table.exists():
            continue
        with style_table.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                name = (row.get("name") or "").strip()
                if not name:
                    continue
                if name.startswith(">>>>>>"):
                    flush()
                    current_items = []
                    current_label = name.replace(">", "").strip() or "Section"
                    current_id = current_label.lower().replace(" ", "-")
                    continue
                if not name.startswith("Style:"):
                    continue
                current_items.append(
                    {
                        "id": name,
                        "label": name.replace("Style: ", "", 1),
                    }
                )
        flush()
        if groups:
            break
    return groups


def _group_styles(styles: list) -> dict:
    """Build grouped style presets for the inspector (CSV order + extras)."""
    groups = _load_style_groups_from_csv()
    seen = {item["id"] for group in groups for item in group["items"]}

    extras: dict[str, list[dict]] = {}
    for raw in styles:
        name = (raw if isinstance(raw, str) else str(raw)).strip()
        if not name or name in seen or name.startswith(">>>>>>"):
            continue
        if name.startswith("Style:"):
            bucket = "Other styles"
        elif name.startswith("Artify:"):
            bucket = "Artify"
        else:
            bucket = "Presets"
        extras.setdefault(bucket, []).append(
            {"id": name, "label": name.replace("Style: ", "", 1)}
        )
        seen.add(name)

    for label, items in sorted(extras.items()):
        items.sort(key=lambda i: i["label"].lower())
        groups.append(
            {
                "id": label.lower().replace(" ", "-"),
                "label": label,
                "items": items,
            }
        )

    selectable = [item["id"] for group in groups for item in group["items"]]
    return {"groups": groups, "selectable": selectable}


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
    """Gradio model_gallery rows: Civit/cache thumbnails + captions."""
    from modules.model_ui_defaults import (
        GALLERY_CATEGORIES,
        engine_name_for_category,
        gallery_caption,
        infer_model_family,
        scan_model_category,
    )

    needle = (params.get("filter") or "").lower()
    items = []
    for category in GALLERY_CATEGORIES:
        for relative_name in scan_model_category(category):
            haystack = f"{category} {relative_name}".lower()
            if needle and needle not in haystack:
                continue
            filename = Path(relative_name).name
            if filename.endswith(".merge"):
                fallback = BACKEND_ROOT / "html" / "merge.jpeg"
            else:
                fallback = BACKEND_ROOT / "html" / "warning.jpeg"
            items.append(
                {
                    "category": category,
                    "relative_path": relative_name,
                    "caption": gallery_caption(category, relative_name),
                    "engine_name": engine_name_for_category(category, relative_name),
                    "family": infer_model_family(filename),
                    "thumbnail_path": _resolve_cached_thumbnail(
                        "checkpoints", filename, fallback
                    ),
                }
            )
    return {"ok": True, "items": items, "count": len(items)}


def cmd_get_lora_gallery(params: dict) -> dict:
    from dreamforge_cli_inventory import list_model_inventory

    needle = (params.get("filter") or "").lower()
    inv = list_model_inventory()
    loras = inv.get("categories", {}).get("loras", [])
    fallback = BACKEND_ROOT / "html" / "warning.png"  # loras use warning.png per util.py
    items = []
    seen = set()
    for entry in loras:
        name = entry.get("name") or ""
        relative_path = entry.get("relative_path") or name
        if not name:
            continue
        if relative_path in seen:
            continue
        seen.add(relative_path)
        haystack = name.lower()
        if needle and needle not in f"{name} {relative_path}".lower():
            continue
        items.append(
            {
                "name": name,
                "stem": entry.get("stem") or Path(name).stem,
                "relative_path": relative_path,
                "thumbnail_path": _resolve_cached_thumbnail("loras", name, fallback),
            }
        )
    return {"ok": True, "items": items, "count": len(items)}


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
    from dreamforge_cli_inventory import list_model_inventory, list_system_fonts

    inv = list_model_inventory()
    style_data = _group_styles(inv.get("styles", []))
    payload = {
        "ok": True,
        "models_root": inv.get("models_root"),
        "categories": inv.get("categories", {}),
        "presets": inv.get("presets", []),
        "styles": style_data["selectable"],
        "style_groups": style_data["groups"],
    }
    if params.get("include_fonts"):
        payload["fonts"] = list_system_fonts(font_filter=params.get("font_filter"))
    return payload


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


def cmd_list_use_cases(_params: dict) -> dict:
    from dreamforge_agent_tools import USE_CASE_RECIPES

    recipes = []
    for name, spec in sorted(USE_CASE_RECIPES.items()):
        recipes.append({"id": name, **spec})
    return {"ok": True, "use_cases": recipes}


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
    missing = check_model_dependencies(model)
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

    missing = check_model_dependencies(model)
    ids = params.get("ids")
    if ids:
        wanted = {str(item) for item in ids}
        missing = [item for item in missing if item.get("id") in wanted]
    if not missing:
        return {"ok": True, "status": "ready", "downloaded": 0, "results": [], "errors": []}

    payload = download_missing_companions(missing)
    payload["ok"] = not payload.get("errors")
    payload["model"] = model
    return payload


def _namespace_from_params(params: dict) -> SimpleNamespace:
    """Map generation request fields to CLI argparse namespace."""
    mapping = {
        "model": "model",
        "base_model": "model",
        "prompt": "prompt",
        "negative_prompt": "negative_prompt",
        "aspect_ratio": "aspect_ratio",
        "width": "width",
        "height": "height",
        "seed": "seed",
        "image_number": "image_number",
        "output": "output",
        "performance": "performance",
        "steps": "steps",
        "cfg_scale": "cfg_scale",
        "sampler": "sampler",
        "scheduler": "scheduler",
        "styles": "styles",
        "lora": "lora",
        "input_image": "input_image",
        "upscale_image": "upscale_image",
        "upscale_method": "upscale_method",
        "edit_type": "edit_type",
        "vram_profile": "vram_profile",
        "use_case": "use_case",
        "brand_kit": "brand_kit",
        "subject": "subject",
        "composition": "composition",
        "lighting": "lighting",
        "camera": "camera",
        "brand_colors": "brand_colors",
        "materials": "materials",
        "visual_style": "visual_style",
        "validate_output": "validate_output",
        "no_manifest": "no_manifest",
    }
    data = {"dry_run": True, "json": True}
    for key, attr in mapping.items():
        if key in params and params[key] is not None:
            data[attr] = params[key]
    return SimpleNamespace(**data)


def cmd_dry_run(params: dict) -> dict:
    from dreamforge_cli_direct import build_plan

    try:
        plan = build_plan(_namespace_from_params(params))
        return {"ok": True, "plan": plan}
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
    add("--upscale-image", params.get("upscale_image"))
    add("--upscale-method", params.get("upscale_method"))
    add("--edit-type", params.get("edit_type"))
    add("--vram-profile", params.get("vram_profile"))
    add("--use-case", params.get("use_case"))
    add("--brand-kit", params.get("brand_kit"))
    add("--subject", params.get("subject"))
    add("--composition", params.get("composition"))
    add("--lighting", params.get("lighting"))
    add("--camera", params.get("camera"))
    add("--brand-colors", params.get("brand_colors"))
    add("--materials", params.get("materials"))
    add("--visual-style", params.get("visual_style"))
    if params.get("validate_output"):
        argv.append("--validate-output")
    if params.get("no_manifest"):
        argv.append("--no-manifest")
    for style in params.get("styles") or []:
        argv.extend(["--style", style])
    for lora in params.get("lora") or []:
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
    "resolve_model_profile": cmd_resolve_model_profile,
    "list_outputs": cmd_list_outputs,
    "search_outputs": cmd_search_outputs,
    "delete_output": cmd_delete_output,
    "delete_output_image": cmd_delete_output_image,
    "delete_session": cmd_delete_session,
    "dry_run": cmd_dry_run,
    "build_cli_argv": cmd_build_cli_argv,
    "list_use_cases": cmd_list_use_cases,
    "get_ui_defaults": cmd_get_ui_defaults,
    "classify_models": cmd_classify_models,
    "organize_models": cmd_organize_models,
    "check_model_dependencies": cmd_check_model_dependencies,
    "download_model_companions": cmd_download_model_companions,
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
