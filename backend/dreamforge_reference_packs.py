"""Local lightweight reference packs for DreamForge identity/reference workflows."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _paths import PROJECT_ROOT

PACKS_PATH = PROJECT_ROOT / "outputs" / "dreamforge" / "memory" / "reference_packs.json"
PACK_TYPES = {"person", "character", "product", "brand", "style"}
MAX_IMAGES = 64


@dataclass
class ReferencePack:
    id: str
    name: str
    type: str = "style"
    image_paths: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    preferred_use_cases: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _packs_path() -> Path:
    PACKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    return PACKS_PATH


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return text or "reference-pack"


def _string_list(value: Any, *, limit: int | None = None) -> list[str]:
    if value is None:
        items: list[Any] = []
    elif isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        items = []
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if limit and len(out) >= limit:
            break
    return out


def _read_store() -> dict[str, Any]:
    path = _packs_path()
    if not path.is_file():
        return {"schema_version": "1.0", "packs": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": "1.0", "packs": []}
    if not isinstance(raw, dict):
        return {"schema_version": "1.0", "packs": []}
    packs = raw.get("packs")
    return {"schema_version": str(raw.get("schema_version") or "1.0"), "packs": packs if isinstance(packs, list) else []}


def _write_store(packs: list[ReferencePack]) -> None:
    path = _packs_path()
    payload = {
        "schema_version": "1.0",
        "packs": [pack.to_dict() for pack in sorted(packs, key=lambda item: item.updated_at, reverse=True)],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _deserialize_pack(payload: dict[str, Any]) -> ReferencePack:
    """Load a pack from disk without mutating timestamps."""
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("reference_pack_name_required")
    pack_id = str(payload.get("id") or _slug(name)).strip()
    pack_type = str(payload.get("type") or "style").strip().lower()
    if pack_type not in PACK_TYPES:
        raise ValueError(f"reference_pack_type_invalid: {pack_type}")
    return ReferencePack(
        id=_slug(pack_id),
        name=name,
        type=pack_type,
        image_paths=_string_list(payload.get("image_paths"), limit=MAX_IMAGES),
        tags=_string_list(payload.get("tags")),
        notes=str(payload.get("notes") or "").strip(),
        preferred_use_cases=_string_list(payload.get("preferred_use_cases")),
        created_at=str(payload.get("created_at") or ""),
        updated_at=str(payload.get("updated_at") or ""),
    )


def _normalize_pack(payload: dict[str, Any], *, existing: ReferencePack | None = None) -> ReferencePack:
    name = str(payload.get("name") or (existing.name if existing else "")).strip()
    if not name:
        raise ValueError("reference_pack_name_required")
    pack_id = str(payload.get("id") or (existing.id if existing else _slug(name))).strip()
    pack_type = str(payload.get("type") or (existing.type if existing else "style")).strip().lower()
    if pack_type not in PACK_TYPES:
        raise ValueError(f"reference_pack_type_invalid: {pack_type}")
    created = existing.created_at if existing else _now()
    return ReferencePack(
        id=_slug(pack_id),
        name=name,
        type=pack_type,
        image_paths=_string_list(payload.get("image_paths", existing.image_paths if existing else []), limit=MAX_IMAGES),
        tags=_string_list(payload.get("tags", existing.tags if existing else [])),
        notes=str(payload.get("notes", existing.notes if existing else "") or "").strip(),
        preferred_use_cases=_string_list(
            payload.get("preferred_use_cases", existing.preferred_use_cases if existing else [])
        ),
        created_at=created,
        updated_at=_now(),
    )


def list_reference_packs() -> list[dict[str, Any]]:
    packs = [_deserialize_pack(item) for item in _read_store()["packs"] if isinstance(item, dict)]
    return [pack.to_dict() for pack in packs]


def get_reference_pack(pack_id: str) -> dict[str, Any] | None:
    wanted = _slug(pack_id)
    for item in _read_store()["packs"]:
        if not isinstance(item, dict):
            continue
        try:
            pack = _deserialize_pack(item)
        except ValueError:
            continue
        if pack.id == wanted:
            return pack.to_dict()
    return None


def upsert_reference_pack(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("reference_pack_payload_required")
    current = [_deserialize_pack(item) for item in _read_store()["packs"] if isinstance(item, dict)]
    pack_id = _slug(str(payload.get("id") or payload.get("name") or ""))
    existing = next((pack for pack in current if pack.id == pack_id), None)
    updated = _normalize_pack(payload, existing=existing)
    next_packs = [pack for pack in current if pack.id != updated.id]
    next_packs.append(updated)
    _write_store(next_packs)
    return updated.to_dict()


def delete_reference_pack(pack_id: str) -> bool:
    wanted = _slug(pack_id)
    current = [_deserialize_pack(item) for item in _read_store()["packs"] if isinstance(item, dict)]
    next_packs = [pack for pack in current if pack.id != wanted]
    if len(next_packs) == len(current):
        return False
    _write_store(next_packs)
    return True


def apply_reference_pack_to_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(settings or {})
    pack_id = str(out.get("reference_pack_id") or "").strip()
    if not pack_id:
        return out
    pack = get_reference_pack(pack_id)
    if not pack:
        out["reference_pack_missing"] = pack_id
        return out
    images = _string_list(pack.get("image_paths"), limit=MAX_IMAGES)
    if images:
        existing = _string_list(out.get("reference_images"))
        out["reference_images"] = _string_list([*existing, *images], limit=MAX_IMAGES)
    out["reference_pack"] = {
        "id": pack["id"],
        "name": pack["name"],
        "type": pack["type"],
        "tags": pack.get("tags", []),
        "preferred_use_cases": pack.get("preferred_use_cases", []),
    }
    return out
