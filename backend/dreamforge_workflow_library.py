"""Safe local workflow-library storage; imported workflows are never executed."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
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
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"workflow_json_invalid: {exc}"}
    if not isinstance(payload, dict) or not payload:
        return {"ok": False, "error": "workflow_json_invalid: expected a non-empty object"}

    report = analyze_workflow(payload, source=str(source_path))
    content_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()[:12]
    WORKFLOW_LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    destination = WORKFLOW_LIBRARY_ROOT / f"{_safe_stem(source_path.stem)}-{content_hash}.json"
    temporary = destination.with_suffix(".json.part")
    try:
        with source_path.open("rb") as src, temporary.open("wb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
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
