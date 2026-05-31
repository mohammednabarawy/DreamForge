"""Local SQLite identity registry for DreamForge reference workflows."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _paths import PROJECT_ROOT

REGISTRY_PATH = PROJECT_ROOT / "outputs" / "dreamforge" / "memory" / "identity_registry.sqlite3"
IDENTITY_TYPES = {"person", "character", "product", "brand", "style", "location"}
MAX_IMAGES = 128


@dataclass
class IdentityRecord:
    id: str
    name: str
    type: str = "style"
    image_paths: list[str] = field(default_factory=list)
    reference_pack_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    embeddings: dict[str, Any] = field(default_factory=dict)
    embedding_status: str = "not_extracted"
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _registry_path() -> Path:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    return REGISTRY_PATH


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return text or "identity"


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


def _json_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return default
    return loaded


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_registry_path())
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS identities (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            image_paths TEXT NOT NULL,
            reference_pack_ids TEXT NOT NULL,
            tags TEXT NOT NULL,
            notes TEXT NOT NULL,
            metadata TEXT NOT NULL,
            embeddings TEXT NOT NULL,
            embedding_status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_identities_type ON identities(type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_identities_updated ON identities(updated_at)")
    return conn


def _row_to_identity(row: sqlite3.Row) -> IdentityRecord:
    return IdentityRecord(
        id=str(row["id"]),
        name=str(row["name"]),
        type=str(row["type"]),
        image_paths=_string_list(_json_loads(row["image_paths"], []), limit=MAX_IMAGES),
        reference_pack_ids=_string_list(_json_loads(row["reference_pack_ids"], [])),
        tags=_string_list(_json_loads(row["tags"], [])),
        notes=str(row["notes"] or ""),
        metadata=_json_dict(_json_loads(row["metadata"], {})),
        embeddings=_json_dict(_json_loads(row["embeddings"], {})),
        embedding_status=str(row["embedding_status"] or "not_extracted"),
        created_at=str(row["created_at"] or ""),
        updated_at=str(row["updated_at"] or ""),
    )


def _normalize_identity(payload: dict[str, Any], *, existing: IdentityRecord | None = None) -> IdentityRecord:
    name = str(payload.get("name") or (existing.name if existing else "")).strip()
    if not name:
        raise ValueError("identity_name_required")
    identity_id = _slug(str(payload.get("id") or (existing.id if existing else name)))
    identity_type = str(payload.get("type") or (existing.type if existing else "style")).strip().lower()
    if identity_type not in IDENTITY_TYPES:
        raise ValueError(f"identity_type_invalid: {identity_type}")
    created = existing.created_at if existing else _now()
    return IdentityRecord(
        id=identity_id,
        name=name,
        type=identity_type,
        image_paths=_string_list(payload.get("image_paths", existing.image_paths if existing else []), limit=MAX_IMAGES),
        reference_pack_ids=_string_list(
            payload.get("reference_pack_ids", existing.reference_pack_ids if existing else [])
        ),
        tags=_string_list(payload.get("tags", existing.tags if existing else [])),
        notes=str(payload.get("notes", existing.notes if existing else "") or "").strip(),
        metadata=_json_dict(payload.get("metadata", existing.metadata if existing else {})),
        embeddings=_json_dict(payload.get("embeddings", existing.embeddings if existing else {})),
        embedding_status=str(
            payload.get("embedding_status", existing.embedding_status if existing else "not_extracted")
            or "not_extracted"
        ).strip(),
        created_at=created,
        updated_at=_now(),
    )


def upsert_identity(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("identity_payload_required")
    identity_id = _slug(str(payload.get("id") or payload.get("name") or ""))
    with _connect() as conn:
        row = conn.execute("SELECT * FROM identities WHERE id = ?", (identity_id,)).fetchone()
        existing = _row_to_identity(row) if row else None
        identity = _normalize_identity(payload, existing=existing)
        conn.execute(
            """
            INSERT INTO identities (
                id, name, type, image_paths, reference_pack_ids, tags, notes,
                metadata, embeddings, embedding_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                type=excluded.type,
                image_paths=excluded.image_paths,
                reference_pack_ids=excluded.reference_pack_ids,
                tags=excluded.tags,
                notes=excluded.notes,
                metadata=excluded.metadata,
                embeddings=excluded.embeddings,
                embedding_status=excluded.embedding_status,
                updated_at=excluded.updated_at
            """,
            (
                identity.id,
                identity.name,
                identity.type,
                _json_dumps(identity.image_paths),
                _json_dumps(identity.reference_pack_ids),
                _json_dumps(identity.tags),
                identity.notes,
                _json_dumps(identity.metadata),
                _json_dumps(identity.embeddings),
                identity.embedding_status,
                identity.created_at,
                identity.updated_at,
            ),
        )
    return identity.to_dict()


def get_identity(identity_id: str) -> dict[str, Any] | None:
    wanted = _slug(identity_id)
    with _connect() as conn:
        row = conn.execute("SELECT * FROM identities WHERE id = ?", (wanted,)).fetchone()
    return _row_to_identity(row).to_dict() if row else None


def list_identities(identity_type: str | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM identities"
    params: tuple[Any, ...] = ()
    if identity_type:
        query += " WHERE type = ?"
        params = (str(identity_type).lower(),)
    query += " ORDER BY updated_at DESC, name ASC"
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_identity(row).to_dict() for row in rows]


def search_identities(query: str = "", identity_type: str | None = None) -> list[dict[str, Any]]:
    text = str(query or "").strip().lower()
    records = list_identities(identity_type)
    if not text:
        return records

    def matches(record: dict[str, Any]) -> bool:
        haystack = " ".join(
            [
                str(record.get("id") or ""),
                str(record.get("name") or ""),
                str(record.get("type") or ""),
                str(record.get("notes") or ""),
                " ".join(record.get("tags") or []),
            ]
        ).lower()
        return text in haystack

    return [record for record in records if matches(record)]


def delete_identity(identity_id: str) -> bool:
    wanted = _slug(identity_id)
    with _connect() as conn:
        cur = conn.execute("DELETE FROM identities WHERE id = ?", (wanted,))
        return cur.rowcount > 0


def dependency_actions_for_identity(identity: dict[str, Any], settings: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    current = settings or {}
    prompt_text = " ".join(
        str(current.get(key) or "")
        for key in ("prompt", "user_intent", "instruction", "identity_prompt")
    ).lower()
    wants_face = bool(
        current.get("face_preservation")
        or current.get("identity_face_preservation")
        or str(current.get("identity_mode") or "").lower() in {"face", "faceid", "face_id", "preserve_face"}
        or any(
            phrase in prompt_text
            for phrase in (
                "same person",
                "same face",
                "same character",
                "preserve identity",
                "keep the face",
                "face identity",
                "faceid",
            )
        )
    )
    if identity.get("type") not in {"person", "character"} or not wants_face:
        return []
    return [
        {
            "action": "install_local_identity_dependencies",
            "title": "Install local face identity dependencies",
            "detail": "InsightFace/IPAdapter FaceID or an equivalent local stack is required before face embeddings run.",
            "required": False,
            "local_only": True,
            "requires_approval": True,
            "resource": "face_identity_stack",
        }
    ]


def apply_identity_to_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(settings or {})
    identity_id = str(out.get("identity_id") or out.get("identity_reference_id") or "").strip()
    if not identity_id:
        return out
    identity = get_identity(identity_id)
    if not identity:
        out["identity_missing"] = identity_id
        return out
    images = _string_list(identity.get("image_paths"), limit=MAX_IMAGES)
    if images:
        existing = _string_list(out.get("reference_images"))
        out["reference_images"] = _string_list([*existing, *images], limit=MAX_IMAGES)
    out["identity_reference"] = {
        "id": identity["id"],
        "name": identity["name"],
        "type": identity["type"],
        "tags": identity.get("tags", []),
        "embedding_status": identity.get("embedding_status", "not_extracted"),
    }
    actions = dependency_actions_for_identity(identity, out)
    if actions:
        out["identity_dependency_actions"] = actions
    return out
