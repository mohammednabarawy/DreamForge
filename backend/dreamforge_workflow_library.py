"""Safe local workflow-library storage; imported workflows are never executed."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from _paths import PROJECT_ROOT
from dreamforge_workflow_compatibility import MAX_WORKFLOW_BYTES, analyze_workflow

WORKFLOW_LIBRARY_ROOT = PROJECT_ROOT / "outputs" / "dreamforge" / "library" / "workflows"


def _safe_stem(value: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("._")
    return (stem or "workflow")[:80]


def save_workflow_file(source: str | Path) -> dict[str, Any]:
    source_path = Path(source).expanduser().resolve()
    if not source_path.is_file():
        return {"ok": False, "error": "workflow_file_not_found"}
    try:
        size = source_path.stat().st_size
        if size > MAX_WORKFLOW_BYTES:
            return {"ok": False, "error": "workflow_file_too_large"}
        if source_path.suffix.lower() == ".png":
            from dreamforge_workflow_png import load_png_workflow

            payload = load_png_workflow(source_path)
            raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        else:
            raw = source_path.read_bytes()
            payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"workflow_json_invalid: {exc}"}
    if not isinstance(payload, dict) or not payload:
        return {"ok": False, "error": "workflow_json_invalid: expected a non-empty object"}

    report = analyze_workflow(payload, source=str(source_path))
    content_hash = hashlib.sha256(raw).hexdigest()[:12]
    WORKFLOW_LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    destination = WORKFLOW_LIBRARY_ROOT / f"{_safe_stem(source_path.stem)}-{content_hash}.json"
    temporary = destination.with_suffix(".json.part")
    try:
        temporary.write_bytes(raw)
        temporary.replace(destination)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return {"ok": False, "error": f"workflow_save_failed: {exc}"}
    return {
        "ok": True,
        "path": str(destination),
        "filename": destination.name,
        "report": report,
        "execution": "disabled",
    }
