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
        weight = _number(item, "weight", "strength", integer=False) or 1.0
        result.append(LoRAComponent(filename=name, weight=float(weight)))
    return result


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
    if scheduler:
        settings["scheduler"] = str(scheduler)
    if width:
        settings["width"] = int(width)
    if height:
        settings["height"] = int(height)
    recipe = DreamForgeRecipe(
        model=str(_first(data, "model", "Model", "base_model_name", "baseModel", "modelName") or ""),
        positive_prompt=str(_first(data, "prompt", "Prompt", "positive_prompt", "positivePrompt") or ""),
        negative_prompt=str(_first(data, "negative_prompt", "negativePrompt", "Negative") or ""),
        seed=_number(data, "seed", "Seed", integer=True),
        sampler=str(_first(data, "sampler", "sampler_name", "Sampler") or ""),
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


def _civitai(query: str, page: int, limit: int, nsfw: bool) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "limit": max(1, min(limit, 100)),
            "page": max(1, page),
            "nsfw": "true" if nsfw else "false",
            "sort": "Most Reactions",
        }
    )
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
            meta = raw.get("meta") if isinstance(raw.get("meta"), Mapping) else {}
            prompt = str(_first(meta, "prompt", "Prompt") or "")
            if tokens and not all(token in prompt.lower() for token in tokens):
                continue
            item_id = raw.get("id")
            if item_id in (None, ""):
                continue
            source_url = f"https://civitai.com/images/{item_id}"
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
        }
    except Exception as exc:
        return _provider_error("civitai_images", exc)


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
) -> dict[str, Any]:
    selected = [provider] if provider in {"civitai_images", "lexica"} else ["civitai_images", "lexica"]
    calls = {
        "civitai_images": lambda: _civitai(query, page, limit, nsfw),
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
    }
