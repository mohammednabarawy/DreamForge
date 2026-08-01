"""Explicit, safe adapters for official ComfyUI workflow indexes."""

from __future__ import annotations

import json
import hashlib
import ipaddress
import re
import socket
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any, Mapping

from dreamforge_workflow_compatibility import MAX_WORKFLOW_BYTES, analyze_workflow

WORKFLOW_DOWNLOAD_ROOT = Path(__file__).resolve().parent.parent / "outputs" / "dreamforge" / "library" / "workflows"
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
OFFICIAL_WORKFLOW_INDEX_URL = "https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/index.json"
OFFICIAL_REPOSITORY_RAW_URL = "https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main"
OFFICIAL_TEMPLATE_BASE_URL = "https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates"
MAX_INDEX_ITEMS = 1000


def _https_url(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        return ""
    return url


def _public_https_url(value: Any) -> str:
    url = _https_url(value)
    if not url:
        return ""
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(urllib.parse.urlsplit(url).hostname, 443)}
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            return ""
    except (OSError, ValueError):
        return ""
    return url


def parse_workflow_index(payload: Any) -> list[dict[str, Any]]:
    rows = payload.get("workflows") if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list):
        return []
    if rows and isinstance(rows[0], Mapping) and isinstance(rows[0].get("templates"), list):
        return _parse_official_workflow_index(rows)
    items: list[dict[str, Any]] = []
    for index, row in enumerate(rows[:MAX_INDEX_ITEMS]):
        if not isinstance(row, Mapping):
            continue
        url = _https_url(row.get("url") or row.get("download_url") or row.get("workflow_url"))
        if not url:
            continue
        item_id = str(row.get("id") or row.get("slug") or f"workflow-{index + 1}").strip()
        def values(name: str) -> list[str]:
            raw_values = row.get(name, [])
            if not isinstance(raw_values, list):
                return []
            return [str(v) for v in raw_values if isinstance(v, (str, int))]

        items.append({
            "id": item_id,
            "label": str(row.get("label") or row.get("name") or item_id),
            "summary": str(row.get("summary") or row.get("description") or ""),
            "operation": str(row.get("operation") or row.get("category") or "workflow"),
            "mode": str(row.get("mode") or "generate"),
            "url": url,
            "thumbnail_url": _https_url(row.get("thumbnail_url") or row.get("thumbnail")) or None,
            "required_models": values("required_models"),
            "required_node_packs": values("required_node_packs"),
            "source": "workflow_index",
        })
    return items


def _parse_official_workflow_index(groups: list[Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for group in groups:
        if not isinstance(group, Mapping):
            continue
        category = str(group.get("title") or group.get("type") or "Other")
        mode = str(group.get("type") or "generate")
        templates = group.get("templates")
        if not isinstance(templates, list):
            continue
        for row in templates:
            if len(items) >= MAX_INDEX_ITEMS:
                return items
            if not isinstance(row, Mapping):
                continue
            item_id = str(row.get("name") or "").strip()
            if not item_id:
                continue
            tags = [str(value) for value in row.get("tags", []) if isinstance(value, (str, int))]
            models = [str(value) for value in row.get("models", []) if isinstance(value, (str, int))]
            thumbnails = row.get("thumbnail") if isinstance(row.get("thumbnail"), list) else []
            thumbnail = next((str(value) for value in thumbnails if isinstance(value, str) and not value.lower().endswith((".mp4", ".webm"))), "")
            items.append({
                "id": item_id,
                "label": str(row.get("title") or item_id),
                "summary": str(row.get("description") or ""),
                "operation": tags[0] if tags else mode,
                "mode": mode,
                "category": category,
                "tags": tags,
                "open_source": bool(row.get("openSource")),
                "url": f"{OFFICIAL_TEMPLATE_BASE_URL}/{urllib.parse.quote(item_id, safe='')}.json",
                "thumbnail_url": f"{OFFICIAL_REPOSITORY_RAW_URL}/{urllib.parse.quote(thumbnail, safe='/')}" if thumbnail else None,
                "required_models": models,
                "required_node_packs": [],
                "source": "comfy_official",
            })
    return items


def fetch_workflow_index(url: str) -> dict[str, Any]:
    safe_url = _public_https_url(url or OFFICIAL_WORKFLOW_INDEX_URL)
    if not safe_url:
        return {"ok": False, "error": "workflow_index_requires_https"}
    try:
        request = urllib.request.Request(safe_url, headers={"User-Agent": "DreamForge/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            final_url = getattr(response, "geturl", lambda: safe_url)()
            if not _public_https_url(final_url):
                return {"ok": False, "error": "workflow_index_redirect_rejected"}
            raw = response.read(MAX_WORKFLOW_BYTES + 1)
        if len(raw) > MAX_WORKFLOW_BYTES:
            return {"ok": False, "error": "workflow_index_too_large"}
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"workflow_index_fetch_failed: {exc}"}
    items = parse_workflow_index(payload)
    return {"ok": True, "items": items, "count": len(items)}


def download_workflow(url: str, *, filename: str = "workflow.json") -> dict[str, Any]:
    safe_url = _public_https_url(url)
    if not safe_url:
        return {"ok": False, "error": "workflow_download_requires_https"}
    stem = _SAFE_NAME.sub("_", Path(filename).stem).strip("._") or "workflow"
    try:
        request = urllib.request.Request(safe_url, headers={"User-Agent": "DreamForge/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            final_url = getattr(response, "geturl", lambda: safe_url)()
            if not _public_https_url(final_url):
                return {"ok": False, "error": "workflow_download_redirect_rejected"}
            raw = response.read(MAX_WORKFLOW_BYTES + 1)
        if len(raw) > MAX_WORKFLOW_BYTES:
            return {"ok": False, "error": "workflow_download_too_large"}
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or not payload:
            raise ValueError("workflow JSON must be a non-empty object")
        report = analyze_workflow(payload, source=safe_url)
        if report.get("state") == "INVALID":
            return {"ok": False, "error": f"workflow_rejected: {report.get('reason', 'invalid workflow')}", "report": report}
        name = f"{stem[:80]}-{hashlib.sha256(raw).hexdigest()[:12]}.json"
        destination = WORKFLOW_DOWNLOAD_ROOT / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_suffix(destination.suffix + ".part")
        partial.write_bytes(raw)
        partial.replace(destination)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return {"ok": False, "error": f"workflow_download_failed: {exc}"}
    return {"ok": True, "path": str(destination), "filename": name, "report": report, "execution": "disabled"}
