"""Download companion CLIP/VAE/text-encoder files for modern model families."""
from __future__ import annotations

import os
import shutil
import urllib.request
from pathlib import Path
from typing import Any, Callable

from dreamforge_cli_inventory import MODELS_ROOT, companion_file_present

try:
    from dreamforge_krita_resources import STUDIO_RESOURCE_SOURCES
except ImportError:
    STUDIO_RESOURCE_SOURCES = {}

# Comfy-Org/flux1-dev no longer hosts CLIP/T5/VAE; use upstream mirrors.
HF_BASE_FLUX_TEXT = (
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main"
)
HF_BASE_FLUX_VAE = (
    "https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main"
)
HF_BASE_QWEN = "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files"
HF_BASE_QWEN_CLIP = (
    "https://huggingface.co/unsloth/Qwen2.5-VL-7B-Instruct-GGUF/resolve/main"
)
HF_BASE_QWEN_LIGHTNING = (
    "https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/main"
)
HF_BASE_IDEOGRAM4 = "https://huggingface.co/Comfy-Org/Ideogram-4/resolve/main/split_files"
HF_BASE_FLUX2_VAE = "https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae"

# Shared catalog keyed by dependency id (referenced from MODEL_DEPENDENCIES).
COMPANION_SOURCES: dict[str, dict[str, Any]] = {
    "vae_flux_ae": {
        "url": f"{HF_BASE_FLUX_VAE}/ae.safetensors",
        "min_bytes": 300 * 1024 * 1024,
        # Gated on Hugging Face — set HF_TOKEN after accepting the model license.
        "requires_hf_token": True,
    },
    "clip_l_flux": {
        "url": f"{HF_BASE_FLUX_TEXT}/clip_l.safetensors",
        "min_bytes": 200 * 1024 * 1024,
    },
    "clip_t5_flux_fp8": {
        "url": f"{HF_BASE_FLUX_TEXT}/t5xxl_fp8_e4m3fn_scaled.safetensors",
        "min_bytes": 4 * 1024 * 1024 * 1024,
    },
    "clip_qwen25_vl_7b": {
        "url": f"{HF_BASE_QWEN}/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors",
        "min_bytes": 6 * 1024 * 1024 * 1024,
    },
    "clip_z_image_qwen3_4b_fp4": {
        "url": "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b_fp4_mixed.safetensors",
        "min_bytes": 3200 * 1024 * 1024,
    },
    "lora_krea2_identity_edit_v1_2": {
        "url": "https://huggingface.co/conradlocke/krea2-identity-edit/resolve/55bdbc7985fe5a9bc8e0f179a5101bbe32c98086/krea2_identity_edit_v1_2.safetensors",
        "min_bytes": 1600 * 1024 * 1024,
    },
    "clip_krea2_qwen3vl_4b": {
        "url": "https://huggingface.co/Comfy-Org/Qwen3-VL/resolve/main/text_encoders/qwen3vl_4b_fp8_scaled.safetensors",
        "min_bytes": 5 * 1024 * 1024 * 1024,
    },
    "clip_z_image_qwen3_4b_fp8": {
        "url": "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b_fp8_mixed.safetensors",
        "min_bytes": 5200 * 1024 * 1024,
    },
    "clip_qwen25_gguf_compatible": {
        "url": f"{HF_BASE_QWEN_CLIP}/Qwen2.5-VL-7B-Instruct-Q4_K_S.gguf",
        "min_bytes": 4 * 1024 * 1024 * 1024,
    },
    "vae_qwen_image": {
        "url": f"{HF_BASE_QWEN}/vae/qwen_image_vae.safetensors",
        "min_bytes": 200 * 1024 * 1024,
    },
    "lora_qwen_edit_lightning_4step": {
        "url": f"{HF_BASE_QWEN_LIGHTNING}/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
        "min_bytes": 800 * 1024 * 1024,
    },
    "lora_qwen_edit_lightning_8step": {
        "url": f"{HF_BASE_QWEN_LIGHTNING}/Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors",
        "min_bytes": 800 * 1024 * 1024,
    },
    "unet_ideogram4_unconditional": {
        "url": f"{HF_BASE_IDEOGRAM4}/diffusion_models/ideogram4_unconditional_fp8_scaled.safetensors",
        "min_bytes": 12 * 1024 * 1024 * 1024,
        "requires_hf_token": True,
    },
    "clip_qwen3vl_ideogram4": {
        "url": f"{HF_BASE_IDEOGRAM4}/text_encoders/qwen3vl_8b_fp8_scaled.safetensors",
        "min_bytes": 6 * 1024 * 1024 * 1024,
        "requires_hf_token": True,
    },
    "vae_flux2": {
        "url": f"{HF_BASE_FLUX2_VAE}/flux2-vae.safetensors",
        "min_bytes": 300 * 1024 * 1024,
    },
    "segformer_b2_clothes": {
        "url": "https://huggingface.co/mattmdjaga/segformer_b2_clothes/resolve/main/model.safetensors",
        "min_bytes": 100 * 1024 * 1024,
        "catalog_id": "segformer_b2_clothes",
    },
}

# Studio upscalers / inpaint assets (Krita AI Diffusion manifest URLs).
for _resource_id, _src in STUDIO_RESOURCE_SOURCES.items():
    rel = _src.get("relative", "")
    if not rel or _resource_id in COMPANION_SOURCES:
        continue
    COMPANION_SOURCES[_resource_id] = {
        "url": _src["url"],
        "min_bytes": _src.get("min_bytes", 1024 * 1024),
        **({"requires_hf_token": True} if _src.get("requires_hf_token") else {}),
    }


def companion_category(relative: str) -> str:
    folder = relative.split("/", 1)[0] if "/" in relative else ""
    if folder in (
        "vae",
        "clip",
        "loras",
        "controlnet",
        "upscale_models",
        "checkpoints",
        "diffusion_models",
    ):
        return folder
    if folder == "text_encoders":
        return "text_encoders"
    return folder or "checkpoints"


def companion_filename(relative: str) -> str:
    return Path(relative).name


TIER_B_MIN_BYTES = 500 * 1024 * 1024


def companion_download_tier(entry: dict) -> str:
    """Classify companions: Tier A auto-downloads silently; Tier B needs approval."""
    if entry.get("requires_hf_token"):
        return "B"
    if not entry.get("url"):
        return "B"
    min_bytes = int(entry.get("min_bytes") or 1024 * 1024)
    if min_bytes >= TIER_B_MIN_BYTES:
        return "B"
    relative = str(entry.get("relative") or "").lower()
    if relative.startswith(("diffusion_models/", "checkpoints/", "unet/")):
        return "B"
    return "A"


def enrich_missing_dependency(entry: dict) -> dict:
    """Attach download url/category/filename for desktop companion fetch."""
    source = COMPANION_SOURCES.get(entry.get("id", ""), {})
    relative = entry.get("relative") or ""
    enriched = dict(entry)
    url = enriched.get("url") or source.get("url")
    if url:
        enriched["url"] = url
        enriched["category"] = companion_category(relative)
        enriched["filename"] = companion_filename(relative)
        enriched["min_bytes"] = enriched.get("min_bytes") or source.get("min_bytes", 1024 * 1024)
        if source.get("requires_hf_token"):
            enriched["requires_hf_token"] = True
    enriched["download_tier"] = companion_download_tier(enriched)
    return enriched


def companion_item_present(item: dict, *, min_bytes: int = 1024 * 1024) -> bool:
    """True when a companion row is satisfied on disk (kind-aware)."""
    kind = str(item.get("kind") or "").strip()
    if kind == "custom_node_pack":
        pack_id = str(item.get("pack_id") or item.get("id") or "").strip()
        if not pack_id:
            return False
        from dreamforge_workflow_planner import _custom_node_directory_present

        return _custom_node_directory_present(pack_id)

    item_id = str(item.get("id") or "").strip()
    if kind == "model_companion" or item_id.startswith("graph_model:"):
        from dreamforge_custom_tools import KNOWN_GRAPH_MODELS, workflow_graph_model_file_present

        filename = str(item.get("filename") or "").strip()
        if not filename and item_id.startswith("graph_model:"):
            filename = item_id[len("graph_model:") :]
        if filename:
            known = KNOWN_GRAPH_MODELS.get(filename, {})
            min_b = int(item.get("min_bytes") or known.get("min_bytes") or min_bytes)
            relative = str(item.get("relative") or known.get("relative") or "")
            category = relative.split("/", 1)[0] if "/" in relative else ""
            folders = (category,) if category else None
            if workflow_graph_model_file_present(
                filename,
                folders=folders,
                min_bytes=min_b,
            ):
                return True

    return companion_file_present(item, min_bytes=min_bytes)


def filter_unsatisfied_companion_entries(items: list[dict]) -> list[dict]:
    """Drop companion rows that are already satisfied on disk (incl. filename aliases)."""
    kept: list[dict] = []
    for item in items:
        min_bytes = int(item.get("min_bytes") or 1024 * 1024)
        if companion_item_present(item, min_bytes=min_bytes):
            continue
        kept.append(item)
    return kept


def _download_file(
    url: str,
    dest: Path,
    *,
    min_bytes: int = 1024 * 1024,
    progress: Callable[[str], None] | None = None,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size >= min_bytes:
        return dest

    partial = dest.with_suffix(dest.suffix + ".partial")
    headers = {"User-Agent": "DreamForge-companion-download/1.0"}
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    timeout_s = max(600, int(min_bytes / (512 * 1024)) + 120)
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        total = int(response.headers.get("Content-Length") or 0)
        downloaded = 0
        last_report_pct = -1
        with partial.open("wb") as fh:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
                downloaded += len(chunk)
                if progress and total > 0:
                    pct = min(100, int((downloaded * 100) / total))
                    if pct >= last_report_pct + 5 or pct == 100:
                        last_report_pct = pct
                        progress(f"Downloading {dest.name}… {pct}%")
                elif progress and downloaded > 0 and downloaded % (50 * 1024 * 1024) < len(chunk):
                    progress(f"Downloading {dest.name}… {downloaded // (1024 * 1024)} MB")
    size = partial.stat().st_size if partial.is_file() else 0
    if size < min_bytes:
        try:
            partial.unlink()
        except OSError:
            pass
        raise OSError(
            f"Downloaded file too small ({size} bytes); expected at least {min_bytes}."
        )
    partial.replace(dest)
    return dest


def download_companion(entry: dict) -> dict:
    """Download one companion entry (must include url + expected_path or relative)."""
    enriched = enrich_missing_dependency(entry)
    url = enriched.get("url")
    if not url:
        return {
            "status": "skipped",
            "id": enriched.get("id"),
            "reason": "no_download_url",
        }

    from dreamforge_cli_inventory import companion_asset_path

    dest = companion_asset_path(enriched)
    if dest is None:
        return {
            "status": "skipped",
            "id": enriched.get("id"),
            "reason": "no_destination_path",
        }
    dest.parent.mkdir(parents=True, exist_ok=True)

    min_bytes = int(enriched.get("min_bytes") or 1024 * 1024)
    if companion_item_present(enriched, min_bytes=min_bytes):
        return {
            "status": "exists",
            "path": str(dest),
            "id": enriched.get("id"),
        }

    path = _download_file(
        url,
        dest,
        min_bytes=int(enriched.get("min_bytes") or 1024 * 1024),
    )
    return {"status": "downloaded", "path": str(path), "id": enriched.get("id")}


def download_missing_companions(
    missing: list[dict],
    progress: Callable[[str], None] | None = None,
) -> dict:
    results = []
    errors = []
    for entry in missing:
        if progress is not None:
            label = entry.get("filename") or entry.get("relative") or "asset"
            progress(f"Downloading {label}...")
        try:
            results.append(download_companion(entry))
        except Exception as exc:
            errors.append(
                {
                    "id": entry.get("id"),
                    "relative": entry.get("relative"),
                    "error": str(exc),
                }
            )
    return {
        "status": "error" if errors and not results else "ok",
        "results": results,
        "errors": errors,
        "downloaded": sum(1 for r in results if r.get("status") == "downloaded"),
        "skipped": sum(1 for r in results if r.get("status") in ("exists", "skipped")),
    }


def tag_companion_tiers(missing: list[dict]) -> list[dict]:
    return [enrich_missing_dependency(dict(item)) for item in missing]


def split_companions_by_tier(missing: list[dict]) -> tuple[list[dict], list[dict]]:
    tagged = tag_companion_tiers(missing)
    tier_a = [item for item in tagged if item.get("download_tier") == "A"]
    tier_b = [item for item in tagged if item.get("download_tier") == "B"]
    return tier_a, tier_b


def _merge_missing_items(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    merged: list[dict] = []
    for item in items:
        key = str(item.get("id") or item.get("relative") or item.get("expected_path") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _collect_task_missing(
    *,
    model_name: str | None,
    studio_mode: str | None,
    upscale_method: str | None,
    performance: str | None,
    template_id: str | None = None,
    edit_task: str | None = None,
    custom_tool_id: str | None = None,
) -> tuple[Any | None, list[dict]]:
    from dreamforge_cli_inventory import (
        check_model_dependencies,
        check_studio_resources,
        resolve_generation_model,
    )
    from dreamforge_creative_templates import companion_entries_for_template

    missing: list[dict] = []
    resolved_model = None
    if model_name and not custom_tool_id:
        resolved_model = resolve_generation_model(model_name)
        if resolved_model:
            missing.extend(
                check_model_dependencies(
                    resolved_model,
                    performance=performance,
                )
            )
    if studio_mode:
        missing.extend(
            check_studio_resources(studio_mode, upscale_method=upscale_method, **({"model_name": model_name} if model_name and not custom_tool_id else {}))
        )
    if template_id:
        missing.extend(companion_entries_for_template(template_id))
    chain_method = None
    if template_id:
        from dreamforge_creative_templates import template_post_upscale_method

        chain_method = template_post_upscale_method(template_id)
    post_upscale = chain_method or upscale_method
    if post_upscale and studio_mode in {None, "edit", "inpaint", "generate"}:
        missing.extend(check_studio_resources("upscale", upscale_method=post_upscale))
    if edit_task:
        from dreamforge_comfy_manager import missing_workflow_model_entries

        missing.extend(missing_workflow_model_entries(edit_task=edit_task))
    if custom_tool_id:
        from dreamforge_custom_tools import custom_tool_dependencies_for_id

        missing.extend(custom_tool_dependencies_for_id(custom_tool_id))
    return resolved_model, tag_companion_tiers(
        filter_unsatisfied_companion_entries(_merge_missing_items(missing))
    )


def _studio_prepare_label(
    studio_mode: str | None,
    upscale_method: str | None = None,
) -> str:
    mode = str(studio_mode or "").lower()
    if mode == "upscale":
        method = str(upscale_method or "ultimate_sd_upscale").lower()
        if "ultimate" in method:
            return "Checking Ultimate SD Upscale model and nodes…"
        return f"Checking {method.replace('_', ' ')} upscale assets…"
    if mode == "inpaint":
        return "Checking inpaint models and mask tools…"
    if mode == "edit":
        return "Checking edit models and reference tools…"
    return "Scanning required model and studio assets…"


def _node_pack_label(studio_mode: str | None, upscale_method: str | None = None) -> str:
    mode = str(studio_mode or "").lower()
    if mode == "upscale":
        method = str(upscale_method or "ultimate_sd_upscale").lower()
        if "ultimate" in method:
            return "Ultimate SD Upscale"
    return "required ComfyUI"


def ensure_creative_task_ready(
    *,
    model_name: str | None = None,
    studio_mode: str | None = None,
    upscale_method: str | None = None,
    performance: str | None = None,
    edit_task: str | None = None,
    custom_tool_id: str | None = None,
    auto_download_tier_a: bool = True,
    auto_download_tier_b: bool = False,
    auto_install_nodes: bool = False,
    template_id: str | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict:
    """Check model + studio deps; silently fetch Tier A assets when allowed."""
    setup_messages: list[str] = []
    
    def _handle_progress(msg: str):
        setup_messages.append(msg)
        if progress is not None:
            progress(msg)

    _handle_progress(_studio_prepare_label(studio_mode, upscale_method))
    node_label = _node_pack_label(studio_mode, upscale_method)

    from dreamforge_workflow_planner import (
        missing_custom_node_pack_entries,
        required_custom_node_pack_ids,
    )

    pack_ids = required_custom_node_pack_ids(
        studio_mode=studio_mode,
        upscale_method=upscale_method,
        edit_task=edit_task,
    )
    if studio_mode == "edit" and model_name and not custom_tool_id:
        from dreamforge_cli_inventory import resolve_generation_model
        selected = resolve_generation_model(model_name)
        if selected and selected.get("family") == "krea2" and "comfyui-krea2edit" not in pack_ids:
            pack_ids.append("comfyui-krea2edit")
    if custom_tool_id:
        from dreamforge_custom_tools import (
            custom_tool_dependencies_for_id,
            find_custom_tool,
        )

        tool = find_custom_tool(custom_tool_id)
        if tool:
            node_label = str(tool.get("name") or custom_tool_id)
        for item in custom_tool_dependencies_for_id(custom_tool_id):
            if str(item.get("kind") or "") != "custom_node_pack":
                continue
            pack_id = str(item.get("pack_id") or item.get("id") or "").strip()
            if pack_id and pack_id not in pack_ids:
                pack_ids.append(pack_id)
    object_info_cache: dict | None = None

    if auto_install_nodes and pack_ids:
        missing_dirs = missing_custom_node_pack_entries(pack_ids, object_info=None)
        installed_any = False

        if not missing_dirs:
            _handle_progress(f"{node_label} custom nodes are already installed.")
        else:
            _handle_progress(
                f"Installing {len(missing_dirs)} missing ComfyUI node pack(s) for {node_label}…"
            )
            from dreamforge_comfy_install import (
                ensure_comfyui_checkout,
                ensure_comfyui_python_deps,
                ensure_custom_node_pack,
            )
            from dreamforge_workflow_planner import _recipe_entry_for_pack

            ensure_comfyui_checkout(progress=_handle_progress)
            ensure_comfyui_python_deps(progress=_handle_progress)
            for item in missing_dirs:
                pack_id = str(item.get("pack_id") or "")
                entry = _recipe_entry_for_pack(pack_id)
                if entry:
                    ensure_custom_node_pack(entry, progress=_handle_progress)
                    installed_any = True

        needs_restart = installed_any
        if not needs_restart:
            try:
                from dreamforge_comfy_server import fetch_comfy_object_info

                object_info_cache = fetch_comfy_object_info(timeout_s=12.0)
                still_missing = missing_custom_node_pack_entries(
                    pack_ids,
                    object_info=object_info_cache,
                )
                needs_restart = bool(still_missing)
                if still_missing:
                    _handle_progress(
                        f"{node_label} nodes are installed but not registered yet — ComfyUI restart required…"
                    )
            except Exception:
                needs_restart = True

        if needs_restart:
            if not installed_any:
                _handle_progress("ComfyUI restart required so custom nodes are registered…")
            setup_messages.append("needs_comfy_restart")

    _handle_progress("Scanning required model and studio assets…")
    resolved_model, missing = _collect_task_missing(
        model_name=model_name,
        studio_mode=studio_mode,
        upscale_method=upscale_method,
        performance=performance,
        template_id=template_id,
        edit_task=edit_task,
        custom_tool_id=custom_tool_id,
    )
    tier_a = [item for item in missing if item.get("download_tier") == "A"]
    tier_b = [item for item in missing if item.get("download_tier") == "B"]

    downloaded_a = 0
    downloaded_b = 0
    errors: list[dict] = []
    def _download_batch(items: list[dict]) -> dict:
        try:
            return download_missing_companions(items, progress=_handle_progress)
        except TypeError as exc:
            if "progress" not in str(exc):
                raise
            return download_missing_companions(items)

    if auto_download_tier_a and tier_a:
        _handle_progress(f"Downloading {len(tier_a)} helper asset(s)…")
        payload = _download_batch(tier_a)
        downloaded_a = int(payload.get("downloaded") or 0)
        errors = list(payload.get("errors") or [])
        if downloaded_a > 0:
            try:
                from dreamforge_model_library_cache import invalidate_model_library_cache

                invalidate_model_library_cache()
            except ImportError:
                pass
    if auto_download_tier_b and tier_b:
        _handle_progress(f"Downloading {len(tier_b)} large asset(s)…")
        payload = _download_batch(tier_b)
        downloaded_b = int(payload.get("downloaded") or 0)
        errors.extend(list(payload.get("errors") or []))
        if downloaded_b > 0:
            try:
                from dreamforge_model_library_cache import invalidate_model_library_cache

                invalidate_model_library_cache()
            except ImportError:
                pass

    _handle_progress("Rechecking required assets…")
    _, missing_after = _collect_task_missing(
        model_name=model_name,
        studio_mode=studio_mode,
        upscale_method=upscale_method,
        performance=performance,
        template_id=template_id,
        edit_task=edit_task,
        custom_tool_id=custom_tool_id,
    )
    still_a = [item for item in missing_after if item.get("download_tier") == "A"]
    still_b = [item for item in missing_after if item.get("download_tier") == "B"]
    missing_node_packs: list[dict] = []
    try:
        if pack_ids:
            _handle_progress(f"Verifying {node_label} ComfyUI nodes…")
            if object_info_cache is None:
                try:
                    from dreamforge_comfy_server import fetch_comfy_object_info

                    object_info_cache = fetch_comfy_object_info(timeout_s=12.0)
                except Exception:
                    object_info_cache = None
            missing_node_packs = missing_custom_node_pack_entries(
                pack_ids,
                object_info=object_info_cache,
            )
    except Exception:
        missing_node_packs = []
    ready = len(missing_after) == 0 and len(missing_node_packs) == 0
    if ready:
        _handle_progress("Required assets are ready.")
    elif missing_node_packs:
        _handle_progress(
            f"Missing {len(missing_node_packs)} custom node pack(s) — approval required."
        )
    elif still_b:
        _handle_progress(f"Missing {len(still_b)} large asset(s) — approval required.")
    elif still_a:
        _handle_progress(f"Still missing {len(still_a)} helper asset(s).")

    return {
        "ok": ready,
        "ready": ready,
        "missing": missing_after,
        "missing_tier_a": still_a,
        "missing_tier_b": still_b,
        "missing_node_packs": missing_node_packs,
        "downloaded_tier_a": downloaded_a,
        "downloaded_tier_b": downloaded_b,
        "downloaded": downloaded_a + downloaded_b,
        "errors": errors,
        "model": model_name,
        "studio_mode": studio_mode,
        "template_id": template_id,
        "node_setup": setup_messages,
        "needs_comfy_restart": "needs_comfy_restart" in setup_messages,
    }
