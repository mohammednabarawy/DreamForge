"""Explicit, safe adapters for official ComfyUI workflow indexes."""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Any, Mapping

from dreamforge_workflow_compatibility import MAX_WORKFLOW_BYTES, analyze_workflow

WORKFLOW_DOWNLOAD_ROOT = Path(__file__).resolve().parent.parent / "outputs" / "dreamforge" / "library" / "workflows"
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _https_url(value: Any) -> str:
    url = str(value or "").strip()
    if not url.lower().startswith("https://"):
        return ""
    return url


def parse_workflow_index(payload: Any) -> list[dict[str, Any]]:
    rows = payload.get("workflows") if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list):
        return []
    items: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
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
            "source": "official_index",
        })
    return items


def fetch_workflow_index(url: str) -> dict[str, Any]:
    safe_url = _https_url(url)
    if not safe_url:
        return {"ok": False, "error": "workflow_index_requires_https"}
    try:
        request = urllib.request.Request(safe_url, headers={"User-Agent": "DreamForge/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(MAX_WORKFLOW_BYTES + 1)
        if len(raw) > MAX_WORKFLOW_BYTES:
            return {"ok": False, "error": "workflow_index_too_large"}
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"workflow_index_fetch_failed: {exc}"}
    items = parse_workflow_index(payload)
    return {"ok": True, "items": items, "count": len(items)}


def download_workflow(url: str, *, filename: str = "workflow.json") -> dict[str, Any]:
    safe_url = _https_url(url)
    if not safe_url:
        return {"ok": False, "error": "workflow_download_requires_https"}
    name = _SAFE_NAME.sub("_", Path(filename).name).strip("._") or "workflow.json"
    if not name.lower().endswith(".json"):
        name += ".json"
    try:
        request = urllib.request.Request(safe_url, headers={"User-Agent": "DreamForge/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(MAX_WORKFLOW_BYTES + 1)
        if len(raw) > MAX_WORKFLOW_BYTES:
            return {"ok": False, "error": "workflow_download_too_large"}
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or not payload:
            raise ValueError("workflow JSON must be a non-empty object")
        report = analyze_workflow(payload, source=safe_url)
        if report.get("state") == "INVALID":
            return {"ok": False, "error": f"workflow_rejected: {report.get('reason', 'invalid workflow')}", "report": report}
        destination = WORKFLOW_DOWNLOAD_ROOT / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_suffix(destination.suffix + ".part")
        partial.write_bytes(raw)
        partial.replace(destination)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return {"ok": False, "error": f"workflow_download_failed: {exc}"}
    return {"ok": True, "path": str(destination), "filename": name, "report": report, "execution": "disabled"}
