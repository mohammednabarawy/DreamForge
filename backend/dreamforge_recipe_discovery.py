"""Browse-only prompt/recipe discovery adapters.

External results are normalized to Recipe v2 metadata. They are never sent to
the generation engine; the desktop must explicitly recreate or save them.
"""

from __future__ import annotations

import concurrent.futures
import urllib.parse
from typing import Any, Mapping

from dreamforge_assets import Provenance
from dreamforge_provider_base import (
    ProviderError,
    classify_http_error,
    http_get_json,
)
from dreamforge_recipe import DreamForgeRecipe, LoRAComponent

CIVITAI_IMAGES_URL = "https://civitai.com/api/v1/images"
CIVITAI_MODEL_VERSION_URL = "https://civitai.com/api/v1/model-versions"
LEXICA_SEARCH_URL = "https://lexica.art/api/v1/search"


def _first(data: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _number(data: Mapping[str, Any], *keys: str, integer: bool = False) -> int | float | None:
    value = _first(data, *keys)
    if value in (None, ""):
        return None
    try:
        return int(value) if integer else float(value)
    except (TypeError, ValueError):
        return None


def _loras(data: Mapping[str, Any]) -> list[LoRAComponent]:
    raw = _first(data, "loras", "resources")
    if not isinstance(raw, list):
        return []
    result: list[LoRAComponent] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            result.append(LoRAComponent(filename=item.strip()))
            continue
        if not isinstance(item, Mapping):
            continue
        kind = str(item.get("type") or "").lower()
        if kind and "lora" not in kind:
            continue
        name = str(_first(item, "name", "model", "filename") or "").strip()
        if not name:
            continue
        parsed_weight = _number(item, "weight", "strength", integer=False)
        weight = 1.0 if parsed_weight is None else parsed_weight
        result.append(LoRAComponent(filename=name, weight=float(weight)))
    return result


def _resource_metadata(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = data.get("resources")
    if not isinstance(raw, list):
        return []
    resources: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        version_id = _first(item, "modelVersionId", "model_version_id", "versionId")
        resources.append({
            "name": str(_first(item, "name", "model", "filename") or ""),
            "type": str(item.get("type") or ""),
            "weight": _number(item, "weight", "strength"),
            "model_version_id": str(version_id or ""),
        })
    return resources


def recipe_from_metadata(
    metadata: Mapping[str, Any] | None,
    *,
    provider: str,
    source_url: str,
) -> DreamForgeRecipe:
    data = metadata or {}
    width = _number(data, "width", "Width", integer=True)
    height = _number(data, "height", "Height", integer=True)
    aspect = str(_first(data, "aspect_ratio", "aspectRatio") or "")
    if not aspect and width and height:
        aspect = f"{int(width)}x{int(height)}"
    settings: dict[str, Any] = {}
    scheduler = _first(data, "scheduler", "Scheduler")
    sampler = str(_first(data, "sampler", "sampler_name", "Sampler") or "")
    if not scheduler and "karras" in sampler.lower():
        scheduler = "karras"
    if scheduler:
        settings["scheduler"] = str(scheduler)
    if width:
        settings["width"] = int(width)
    if height:
        settings["height"] = int(height)
    version_ids = data.get("_civitai_model_version_ids")
    if isinstance(version_ids, list):
        settings["civitai_model_version_ids"] = [str(value) for value in version_ids if str(value).isdigit()]
    resources = _resource_metadata(data)
    if resources:
        settings["civitai_resources"] = resources
    model = str(_first(data, "model", "Model", "base_model_name", "baseModel", "modelName") or "")
    if not model:
        model = next((item["name"] for item in resources if "lora" not in item["type"].lower() and item["name"]), "")
    recipe = DreamForgeRecipe(
        model=model,
        positive_prompt=str(_first(data, "prompt", "Prompt", "positive_prompt", "positivePrompt") or ""),
        negative_prompt=str(_first(data, "negative_prompt", "negativePrompt", "Negative") or ""),
        seed=_number(data, "seed", "Seed", integer=True),
        sampler=sampler,
        cfg_scale=float(_number(data, "cfg_scale", "cfgScale", "cfg", "CFG scale") or 0),
        steps=int(_number(data, "steps", "Steps", integer=True) or 0),
        aspect_ratio=aspect,
        loras=_loras(data),
        settings=settings,
        source=provider,
        source_url=source_url,
        provenance=Provenance(provider=provider, source_url=source_url),
    )
    return recipe


def _item(
    *,
    provider: str,
    item_id: Any,
    title: str,
    image_url: str,
    source_url: str,
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    recipe = recipe_from_metadata(metadata, provider=provider, source_url=source_url)
    return {
        "id": f"{provider}:{item_id}",
        "provider": provider,
        "title": title or f"{provider} result {item_id}",
        "image_url": image_url,
        "source_url": source_url,
        "recipe": recipe.to_dict(),
        "completeness": recipe.completeness(),
    }


def _provider_error(provider: str, exc: Exception) -> dict[str, Any]:
    error = exc if isinstance(exc, ProviderError) else classify_http_error(exc)
    return {
        "provider": provider,
        "ok": False,
        "items": [],
        "error": error.message,
        "error_code": error.code,
    }


def _civitai(query: str, page: int, limit: int, nsfw: bool, cursor: str = "") -> dict[str, Any]:
    args = {
        # Civitai has no prompt query parameter. Fetch a wider metadata-rich
        # page and apply the prompt filter locally.
        "limit": max(1, min(100 if query.strip() else limit, 100)),
        "nsfw": "true" if nsfw else "false",
        "sort": "Most Reactions",
        "withMeta": "true",
    }
    if cursor:
        args["cursor"] = cursor
    elif page > 1:
        args["page"] = max(1, page)
    params = urllib.parse.urlencode(args)
    try:
        from dreamforge_credentials import get_provider_credential

        token = get_provider_credential("civitai")
        headers = {"Authorization": f"Bearer {token}"} if token else None
        payload = http_get_json(f"{CIVITAI_IMAGES_URL}?{params}", headers=headers, timeout=25)
        raw_items = payload.get("items") if isinstance(payload, Mapping) else []
        tokens = [part.lower() for part in query.split() if part.strip()]
        items: list[dict[str, Any]] = []
        for raw in raw_items if isinstance(raw_items, list) else []:
            if not isinstance(raw, Mapping):
                continue
            meta = dict(raw.get("meta")) if isinstance(raw.get("meta"), Mapping) else {}
            prompt = str(_first(meta, "prompt", "Prompt") or "")
            if not prompt:
                continue
            if tokens and not all(token in prompt.lower() for token in tokens):
                continue
            item_id = raw.get("id")
            if item_id in (None, ""):
                continue
            source_url = f"https://civitai.com/images/{item_id}"
            meta.setdefault("width", raw.get("width"))
            meta.setdefault("height", raw.get("height"))
            meta["_civitai_model_version_ids"] = raw.get("modelVersionIds") or []
            items.append(
                _item(
                    provider="civitai_images",
                    item_id=item_id,
                    title=f"Civitai image {item_id}",
                    image_url=str(raw.get("url") or ""),
                    source_url=source_url,
                    metadata=meta,
                )
            )
        metadata = payload.get("metadata") if isinstance(payload, Mapping) else {}
        return {
            "provider": "civitai_images",
            "ok": True,
            "items": items,
            "total": int((metadata or {}).get("totalItems") or len(items)),
            "next_cursor": str((metadata or {}).get("nextCursor") or ""),
        }
    except Exception as exc:
        return _provider_error("civitai_images", exc)


def resolve_civitai_recipe_resources(recipe: Mapping[str, Any] | None) -> dict[str, Any]:
    """Resolve Civitai version IDs retained by Recipe discovery to real files."""
    recipe = recipe or {}
    settings = recipe.get("settings") if isinstance(recipe.get("settings"), Mapping) else {}
    version_ids = settings.get("civitai_model_version_ids") if isinstance(settings, Mapping) else []
    resources = settings.get("civitai_resources") if isinstance(settings, Mapping) else []
    ids = {str(value) for value in version_ids if str(value).isdigit()} if isinstance(version_ids, list) else set()
    if isinstance(resources, list):
        ids.update(
            str(item.get("model_version_id"))
            for item in resources
            if isinstance(item, Mapping) and str(item.get("model_version_id") or "").isdigit()
        )
    if not ids:
        return {"ok": True, "resources": [], "errors": []}

    from dreamforge_credentials import get_provider_credential

    token = get_provider_credential("civitai")
    headers = {"Authorization": f"Bearer {token}"} if token else None
    from pathlib import Path

    from dreamforge_asset_registry import AssetRegistry, sha256_of_file
    from dreamforge_assets import AssetKind
    from dreamforge_cli_inventory import MODELS_ROOT
    from modules.model_ui_defaults import engine_name_for_category

    registry = AssetRegistry()
    resolved: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    try:
        for version_id in sorted(ids, key=int):
            try:
                payload = http_get_json(f"{CIVITAI_MODEL_VERSION_URL}/{version_id}", headers=headers, timeout=25)
            except Exception as exc:
                error = exc if isinstance(exc, ProviderError) else classify_http_error(exc)
                errors.append({"model_version_id": version_id, "error": error.message})
                continue
            model = payload.get("model") if isinstance(payload.get("model"), Mapping) else {}
            model_type = str(model.get("type") or "")
            type_key = model_type.lower()
            kind = "lora" if "lora" in type_key or "locon" in type_key else "model" if "checkpoint" in type_key else "other"
            files = payload.get("files") if isinstance(payload.get("files"), list) else []
            safe_files = [
                item for item in files
                if isinstance(item, Mapping) and str(item.get("name") or "").lower().endswith((".safetensors", ".gguf"))
            ]
            file_row = next((item for item in safe_files if item.get("primary")), safe_files[0] if safe_files else None)
            model_id = str(payload.get("modelId") or "")
            source_url = f"https://civitai.com/models/{model_id}?modelVersionId={version_id}" if model_id else f"https://civitai.com/model-versions/{version_id}"
            resource_meta = next((
                item for item in resources
                if isinstance(item, Mapping) and str(item.get("model_version_id") or "") == version_id
            ), {}) if isinstance(resources, list) else {}
            hashes = file_row.get("hashes") if isinstance(file_row, Mapping) and isinstance(file_row.get("hashes"), Mapping) else {}
            sha256 = str(hashes.get("SHA256") or "").lower()
            local_engine_name = ""
            local = registry.file_by_sha256(sha256) if sha256 else None
            if sha256 and not (local or {}).get("local_path") and isinstance(file_row, Mapping):
                target_name = Path(str(file_row.get("name") or "")).name.lower()
                # ponytail: hash same-name candidates only; use AssetScanner if renamed-file detection is needed.
                for candidate in Path(MODELS_ROOT).rglob("*"):
                    if not candidate.is_file() or candidate.name.lower() != target_name:
                        continue
                    try:
                        if sha256_of_file(candidate) != sha256:
                            continue
                        registry.register_local_file(
                            candidate,
                            sha256=sha256,
                            kind=AssetKind.LORA if kind == "lora" else AssetKind.CHECKPOINT,
                        )
                        local = {"local_path": str(candidate)}
                        break
                    except OSError:
                        continue
            local_path = Path(str((local or {}).get("local_path") or ""))
            if local_path.is_file():
                try:
                    relative = local_path.resolve().relative_to(Path(MODELS_ROOT).resolve())
                    if len(relative.parts) < 2:
                        raise ValueError("model is outside a category folder")
                    category, relative_name = relative.parts[0], str(Path(*relative.parts[1:]))
                    local_engine_name = relative_name if kind == "lora" else engine_name_for_category(category, relative_name)
                except (ValueError, IndexError):
                    local_engine_name = local_path.name
            download_url = str(file_row.get("downloadUrl") or payload.get("downloadUrl") or "") if isinstance(file_row, Mapping) else ""
            download_host = (urllib.parse.urlparse(download_url).hostname or "").lower()
            downloadable = bool(file_row and sha256 and download_host in {"civitai.com", "www.civitai.com"})
            file_error = ""
            if not file_row:
                file_error = "No SafeTensor or GGUF file is available for this version"
            elif not sha256:
                file_error = "Civitai did not provide a SHA256 hash for this file"
            elif not downloadable:
                file_error = "Civitai returned an untrusted download URL"
            resolved.append({
                "id": f"civitai:{version_id}",
                "kind": kind,
                "name": str(model.get("name") or payload.get("name") or resource_meta.get("name") or f"Civitai version {version_id}"),
                "version_name": str(payload.get("name") or ""),
                "model_id": model_id,
                "model_version_id": version_id,
                "source_url": source_url,
                "filename": str(file_row.get("name") or "") if isinstance(file_row, Mapping) else "",
                "download_url": download_url,
                "sha256": sha256,
                "local_engine_name": local_engine_name,
                "category": "loras" if kind == "lora" else "checkpoints" if kind == "model" else "",
                "weight": float(resource_meta.get("weight") if resource_meta.get("weight") is not None else 1.0),
                "downloadable": downloadable,
                "error": file_error,
            })
    finally:
        registry.close()
    return {"ok": not errors or bool(resolved), "resources": resolved, "errors": errors}


def _lexica(query: str, page: int, limit: int, _nsfw: bool) -> dict[str, Any]:
    if not query.strip():
        return {"provider": "lexica", "ok": True, "items": [], "total": 0}
    params = urllib.parse.urlencode({"q": query.strip()})
    try:
        payload = http_get_json(f"{LEXICA_SEARCH_URL}?{params}", timeout=20)
        raw_items = payload.get("images") if isinstance(payload, Mapping) else []
        start = max(0, page - 1) * limit
        selected = raw_items[start : start + max(1, min(limit, 50))] if isinstance(raw_items, list) else []
        items: list[dict[str, Any]] = []
        for index, raw in enumerate(selected):
            if not isinstance(raw, Mapping):
                continue
            item_id = raw.get("id") or f"{start + index}"
            source_url = f"https://lexica.art/prompt/{item_id}"
            metadata = {
                "prompt": raw.get("prompt"),
                "negativePrompt": raw.get("negativePrompt"),
                "model": raw.get("model") or raw.get("modelName"),
                "seed": raw.get("seed"),
                "width": raw.get("width"),
                "height": raw.get("height"),
                "guidance": raw.get("guidance"),
                "cfg": raw.get("guidance"),
            }
            items.append(
                _item(
                    provider="lexica",
                    item_id=item_id,
                    title="Lexica prompt",
                    image_url=str(raw.get("src") or raw.get("url") or ""),
                    source_url=source_url,
                    metadata=metadata,
                )
            )
        return {"provider": "lexica", "ok": True, "items": items, "total": len(raw_items) if isinstance(raw_items, list) else len(items)}
    except Exception as exc:
        return _provider_error("lexica", exc)


def search_recipe_discovery(
    query: str = "",
    *,
    provider: str = "all",
    page: int = 1,
    limit: int = 24,
    nsfw: bool = False,
    cursor: str = "",
) -> dict[str, Any]:
    selected = [provider] if provider in {"civitai_images", "lexica"} else ["civitai_images", "lexica"]
    calls = {
        "civitai_images": lambda: _civitai(query, page, limit, nsfw, cursor),
        "lexica": lambda: _lexica(query, page, limit, nsfw),
    }
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(selected)) as pool:
        results = list(pool.map(lambda name: calls[name](), selected))
    items = [item for result in results for item in result.get("items", [])]
    return {
        "ok": True,
        "query": query,
        "page": page,
        "limit": limit,
        "items": items,
        "providers": results,
        "provider_ok": sum(1 for result in results if result.get("ok")),
        "provider_errors": sum(1 for result in results if not result.get("ok")),
        "next_cursor": next((str(result.get("next_cursor") or "") for result in results if result.get("provider") == "civitai_images"), ""),
    }
