"""AssetRegistry — SHA256-identity store for DreamForge Discover & Library.

Persistence (plan §19): SQLite at ``backend/cache/discover/asset_registry.db``.

Identity rules:
- Physical file identity == SHA256 (never filename alone, plan §31.14).
- Logical asset identity == provider + provider_asset_id (+ version id).
- Same SHA256 from two providers = one physical file, deduplicated.
- Local scans register files keyed by SHA256 + local path.

Responsibilities:
- ``AssetRegistry``  : upsert/query logical assets and physical files.
- ``AssetScanner``   : scan model folders and register local files (background hashing).
- ``AssetResolver``  : resolve a logical asset/version/file to a usable local path
  (or mark it as needing download).
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from _paths import BACKEND_ROOT
from dreamforge_assets import (
    AssetFile,
    AssetKind,
    AssetVersion,
    DreamForgeAsset,
    Provenance,
    asset_id_from_provenance,
    detect_architecture,
    detect_variant,
)

DEFAULT_DB_PATH = BACKEND_ROOT / "cache" / "discover" / "asset_registry.db"

# Extensions we register/hash by default (mirrors MODEL_EXTENSIONS usage).
MODEL_FILE_EXTENSIONS: frozenset[str] = frozenset(
    {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".patch", ".onnx"}
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'unknown',
    architecture TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    provenance TEXT NOT NULL DEFAULT '{}',
    payload TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS files (
    sha256 TEXT NOT NULL DEFAULT '',
    filename TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    variant TEXT NOT NULL DEFAULT '',
    format TEXT NOT NULL DEFAULT '',
    local_path TEXT NOT NULL DEFAULT '',
    asset_id TEXT NOT NULL DEFAULT '',
    version_id TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (sha256, asset_id, local_path)
);
CREATE INDEX IF NOT EXISTS idx_files_asset ON files(asset_id);
CREATE INDEX IF NOT EXISTS idx_assets_kind ON assets(kind);
CREATE INDEX IF NOT EXISTS idx_assets_arch ON assets(architecture);
"""


def _read_json(value: str) -> Any:
    try:
        return json.loads(value) if value else {}
    except json.JSONDecodeError:
        return {}


def _write_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def sha256_of_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute the SHA256 of a file in streaming chunks."""
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


class AssetRegistry:
    """SQLite-backed registry of logical assets and physical files."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._lock = threading.RLock()
        self._connect()

    def _connect(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- logical assets --------------------------------------------------------

    def upsert_asset(self, asset: DreamForgeAsset) -> str:
        """Insert or update a logical asset by its deterministic id."""
        if not asset.id:
            asset.id = asset_id_from_provenance(asset.provenance)
        if not asset.id:
            raise ValueError("asset.id is required (provide provenance or id)")
        payload = asset.to_dict()
        provenance = payload.pop("provenance", {})
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO assets (id, name, kind, architecture, description, tags,
                                    provenance, payload, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    kind=excluded.kind,
                    architecture=excluded.architecture,
                    description=excluded.description,
                    tags=excluded.tags,
                    provenance=excluded.provenance,
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (
                    asset.id,
                    asset.name,
                    asset.kind.value,
                    asset.architecture,
                    asset.description,
                    _write_json(asset.tags),
                    _write_json(provenance),
                    _write_json(payload),
                    asset.created_at,
                ),
            )
            self._register_asset_files(asset)
            self._conn.commit()
        return asset.id

    def _register_asset_files(self, asset: DreamForgeAsset) -> None:
        for version in asset.versions:
            for file_ in version.files:
                if not file_.sha256:
                    continue
                self._conn.execute(
                    """
                    INSERT INTO files (sha256, filename, size_bytes, variant, format,
                                       local_path, asset_id, version_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(sha256, asset_id, local_path) DO UPDATE SET
                        filename=excluded.filename,
                        size_bytes=excluded.size_bytes,
                        variant=excluded.variant,
                        format=excluded.format,
                        version_id=excluded.version_id
                    """,
                    (
                        file_.sha256,
                        file_.filename,
                        file_.size_bytes,
                        file_.variant,
                        file_.format,
                        file_.local_path,
                        asset.id,
                        version.id,
                    ),
                )

    def get_asset(self, asset_id: str) -> Optional[DreamForgeAsset]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM assets WHERE id = ?", (asset_id,)
            ).fetchone()
        if row is None:
            return None
        return self._asset_from_row(row)

    def _asset_from_row(self, row: sqlite3.Row) -> DreamForgeAsset:
        payload = _read_json(row["payload"])
        provenance = Provenance.from_dict(_read_json(row["provenance"]))
        versions = [AssetVersion.from_dict(v) for v in (payload.get("versions") or [])]
        asset = DreamForgeAsset(
            id=row["id"],
            name=row["name"],
            kind=AssetKind.from_string(row["kind"]),
            architecture=row["architecture"],
            description=row["description"],
            versions=versions,
            provenance=provenance,
            tags=[str(t) for t in _read_json(row["tags"])],
        )
        return asset

    def list_assets(
        self,
        *,
        kind: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[DreamForgeAsset]:
        query = "SELECT * FROM assets"
        params: list[Any] = []
        if kind:
            query += " WHERE kind = ?"
            params.append(kind)
        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [self._asset_from_row(row) for row in rows]

    def search_assets(
        self,
        query: str,
        *,
        kind: str | None = None,
        limit: int = 100,
    ) -> list[DreamForgeAsset]:
        """Naive LIKE search over name/architecture/description (bounded)."""
        term = f"%{query.strip()}%"
        sql = (
            "SELECT * FROM assets WHERE (name LIKE ? OR architecture LIKE ? "
            "OR description LIKE ?)"
        )
        params: list[Any] = [term, term, term]
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        sql += " LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._asset_from_row(row) for row in rows]

    def count_assets(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS c FROM assets").fetchone()
        return int(row["c"]) if row else 0

    # -- physical files / dedupe ----------------------------------------------

    def file_by_sha256(self, sha256: str) -> Optional[dict[str, Any]]:
        sha256 = sha256.strip().lower()
        if not sha256:
            return None
        with self._lock:
            row = self._conn.execute(
                """SELECT * FROM files WHERE sha256 = ?
                   ORDER BY CASE WHEN local_path <> '' THEN 0 ELSE 1 END, local_path
                   LIMIT 1""",
                (sha256,),
            ).fetchone()
        if row is None:
            return None
        return {
            "sha256": row["sha256"],
            "filename": row["filename"],
            "size_bytes": row["size_bytes"],
            "variant": row["variant"],
            "format": row["format"],
            "local_path": row["local_path"],
            "asset_id": row["asset_id"],
            "version_id": row["version_id"],
        }

    def assets_by_sha256(self, sha256: str) -> list[DreamForgeAsset]:
        sha256 = sha256.strip().lower()
        if not sha256:
            return []
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT a.* FROM assets a
                JOIN files f ON f.asset_id = a.id
                WHERE f.sha256 = ?
                ORDER BY a.updated_at DESC
                """,
                (sha256,),
            ).fetchall()
        return [self._asset_from_row(row) for row in rows]

    def mark_file_local(self, sha256: str, local_path: str) -> None:
        """Associate a local path with an existing physical file record."""
        with self._lock:
            self._conn.execute(
                "UPDATE files SET local_path = ? WHERE sha256 = ?",
                (local_path, sha256),
            )
            self._conn.commit()

    def register_local_file(
        self,
        path: str | Path,
        *,
        sha256: str | None = None,
        kind: AssetKind = AssetKind.UNKNOWN,
        architecture: str = "",
        name: str = "",
        provenance: Provenance | None = None,
    ) -> DreamForgeAsset:
        """Register a local file; compute SHA256 if not provided (background-hashed)."""
        path = Path(path).resolve()
        if not path.is_file():
            raise FileNotFoundError(str(path))
        size = path.stat().st_size
        digest = sha256 or sha256_of_file(path)
        filename = path.name
        variant = detect_variant(filename)
        arch = architecture or detect_architecture(filename)
        file_ = AssetFile(
            filename=filename,
            sha256=digest,
            size_bytes=size,
            variant=variant,
            format=path.suffix.lstrip("."),
            local_path=str(path),
        )
        version = AssetVersion(
            id=f"v:{digest[:12]}",
            name=filename,
            files=[file_],
        )
        provenance = provenance or Provenance.local()
        asset = DreamForgeAsset(
            id=asset_id_from_provenance(provenance) or f"local:{digest[:24]}",
            name=name or filename,
            kind=kind,
            architecture=arch,
            versions=[version],
            provenance=provenance,
        )
        if asset.kind == AssetKind.UNKNOWN:
            asset.kind = kind_for_ext(path.suffix)
        self.upsert_asset(asset)
        return asset

    # -- sqlite utilities ------------------------------------------------------

    def delete_asset(self, asset_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM files WHERE asset_id = ?", (asset_id,))
            self._conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
            self._conn.commit()


def kind_for_ext(suffix: str) -> AssetKind:
    """Best-effort kind from a file extension (fallback when folder kind is unknown)."""
    suffix = (suffix or "").lower()
    if suffix in {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf"}:
        return AssetKind.CHECKPOINT
    if suffix in {".patch"}:
        return AssetKind.INPAINT
    if suffix in {".onnx"}:
        return AssetKind.UNKNOWN
    return AssetKind.UNKNOWN


@dataclass
class ScanResult:
    scanned: int = 0
    registered: int = 0
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)
    assets: list[DreamForgeAsset] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "registered": self.registered,
            "unchanged": self.unchanged,
            "errors": list(self.errors),
            "asset_ids": [a.id for a in (self.assets or [])],
        }


class AssetScanner:
    """Scans model folders and registers local files without full rehash on every
    launch (plan §24): skips rehashing files whose size+mtime are unchanged since
    the last scan snapshot."""

    def __init__(
        self,
        registry: AssetRegistry,
        snapshot_path: str | Path | None = None,
    ) -> None:
        self._registry = registry
        self._snapshot_path = (
            Path(snapshot_path) if snapshot_path else BACKEND_ROOT / "cache" / "discover" / "scan_snapshot.json"
        )
        self._snapshot: dict[str, dict[str, Any]] = self._load_snapshot()

    def _load_snapshot(self) -> dict[str, dict[str, Any]]:
        if self._snapshot_path.is_file():
            try:
                data = json.loads(self._snapshot_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except (OSError, json.JSONDecodeError):
                pass
        return {}

    def _save_snapshot(self) -> None:
        self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._snapshot_path.with_suffix(self._snapshot_path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._snapshot, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._snapshot_path)

    def scan_folder(
        self,
        folder: str | Path,
        *,
        kind: AssetKind = AssetKind.UNKNOWN,
        force_hash: bool = False,
    ) -> ScanResult:
        folder = Path(folder)
        result = ScanResult()
        if not folder.is_dir():
            result.errors.append(f"missing folder: {folder}")
            return result
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in MODEL_FILE_EXTENSIONS:
                continue
            result.scanned += 1
            try:
                stat = path.stat()
                key = str(path)
                fingerprint = self._snapshot.get(key) or {}
                unchanged = (
                    not force_hash
                    and fingerprint.get("size") == stat.st_size
                    and fingerprint.get("mtime_ns") == stat.st_mtime_ns
                    and bool(self._registry.file_by_sha256(fingerprint.get("sha256", "")))
                )
                if unchanged:
                    result.unchanged += 1
                    continue
                digest = sha256_of_file(path)
                self._snapshot[key] = {
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                    "sha256": digest,
                }
                asset = self._registry.register_local_file(
                    path, sha256=digest, kind=kind
                )
                result.registered += 1
                if result.assets is None:
                    result.assets = []
                result.assets.append(asset)
            except OSError as exc:
                result.errors.append(f"{path}: {exc}")
        self._save_snapshot()
        return result


class AssetResolver:
    """Resolves a logical asset to a usable local file, or reports why not."""

    def __init__(self, registry: AssetRegistry) -> None:
        self._registry = registry

    def resolve(
        self,
        asset: DreamForgeAsset | None,
        *,
        prefer_variant: str = "",
        sha256: str = "",
    ) -> dict[str, Any]:
        """Resolve to a local file path when available.

        Returns ``status`` in {"local", "needs_download", "unknown"}.
        """
        if asset is None:
            return {"status": "unknown", "reason": "asset not found", "path": ""}
        file_ = asset.primary_file
        if file_ is None:
            return {"status": "unknown", "reason": "no file variant", "path": ""}
        if sha256:
            record = self._registry.file_by_sha256(sha256)
            if record and record.get("local_path") and Path(record["local_path"]).is_file():
                return {
                    "status": "local",
                    "path": record["local_path"],
                    "sha256": sha256,
                    "filename": file_.filename,
                }
        if prefer_variant and not file_.local_path:
            for version in asset.versions:
                for variant_file in version.files:
                    if variant_file.variant == prefer_variant and variant_file.local_path:
                        if Path(variant_file.local_path).is_file():
                            return {
                                "status": "local",
                                "path": variant_file.local_path,
                                "sha256": variant_file.sha256,
                                "filename": variant_file.filename,
                            }
        if file_.local_path and Path(file_.local_path).is_file():
            return {
                "status": "local",
                "path": file_.local_path,
                "sha256": file_.sha256,
                "filename": file_.filename,
            }
        return {
            "status": "needs_download" if file_.download_url else "unknown",
            "reason": "file not installed" if file_.download_url else "no download source",
            "download_url": file_.download_url,
            "sha256": file_.sha256,
            "filename": file_.filename,
        }
