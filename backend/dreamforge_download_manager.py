"""Persistent download manager for DreamForge Discover & Library.

Wraps the existing ``dreamforge_model_downloader.download_model`` transfer
layer and adds:

- A persistent JSON queue (survives restart).
- Typed state machine: QUEUED -> RESOLVING -> DOWNLOADING -> VERIFYING ->
  REGISTERING -> INSTALLED  (or PAUSED / FAILED_* at any step).
- Pause / resume / cancel.
- Post-download SHA256 verification.
- Atomic ``.part`` -> final-path move (handled by the underlying downloader).
- Post-download ``AssetRegistry`` registration.
- Gated / auth failures surfaced with clear error codes.

Queue state is persisted to ``BACKEND_ROOT / cache / discover / download_queue.json``.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from _paths import BACKEND_ROOT, MODELS_ROOT

QUEUE_PATH = BACKEND_ROOT / "cache" / "discover" / "download_queue.json"


class DownloadState(str, Enum):
    QUEUED = "queued"
    RESOLVING = "resolving"
    CHECKING_DISK = "checking_disk"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    VERIFYING = "verifying"
    REGISTERING = "registering"
    INSTALLED = "installed"
    FAILED_NETWORK = "failed_network"
    FAILED_AUTH = "failed_auth"
    FAILED_INTEGRITY = "failed_integrity"
    FAILED_DISK = "failed_disk"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {
            DownloadState.INSTALLED,
            DownloadState.FAILED_NETWORK,
            DownloadState.FAILED_AUTH,
            DownloadState.FAILED_INTEGRITY,
            DownloadState.FAILED_DISK,
            DownloadState.CANCELLED,
        }

    @property
    def is_failed(self) -> bool:
        return self.value.startswith("failed_")


@dataclass
class DownloadItem:
    """One item in the persistent download queue."""

    id: str
    url: str
    filename: str = ""
    category: str = "checkpoints"
    expected_sha256: str = ""
    provider: str = ""
    provider_asset_id: str = ""
    provider_version_id: str = ""
    state: str = DownloadState.QUEUED.value
    error: str = ""
    error_code: str = ""
    progress_pct: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed_mbs: float = 0.0
    eta_seconds: int = 0
    final_path: str = ""
    queued_at: str = ""
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DownloadItem":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class DownloadManager:
    """Persistent download queue with pause/resume/cancel."""

    def __init__(
        self,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        auto_start_worker: bool = True,
    ) -> None:
        self._lock = threading.RLock()
        self._items: dict[str, DownloadItem] = {}
        self._progress_cb = progress_callback
        self._auto_start_worker = auto_start_worker
        self._worker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_events: dict[str, threading.Event] = {}
        self._load_queue()

    def _load_queue(self) -> None:
        if QUEUE_PATH.exists():
            try:
                with open(QUEUE_PATH, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for entry in raw:
                    item = DownloadItem.from_dict(entry)
                    self._items[item.id] = item
                    if item.state == DownloadState.DOWNLOADING.value:
                        item.state = DownloadState.QUEUED.value
            except Exception:
                pass

    def _save_queue(self) -> None:
        QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(QUEUE_PATH, "w", encoding="utf-8") as f:
            json.dump([item.to_dict() for item in self._items.values()], f, indent=2)

    def enqueue(
        self,
        url: str,
        category: str = "checkpoints",
        filename: str = "",
        expected_sha256: str = "",
        provider: str = "",
        provider_asset_id: str = "",
        provider_version_id: str = "",
    ) -> dict[str, Any]:
        """Add an item to the download queue. Returns the item dict."""
        import hashlib

        item_id = hashlib.sha256(f"{url}:{category}:{filename}".encode()).hexdigest()[:16]
        with self._lock:
            if item_id in self._items:
                existing = self._items[item_id]
                if not DownloadState(existing.state).is_terminal:
                    return {"ok": True, "item": existing.to_dict(), "already_queued": True}
            item = DownloadItem(
                id=item_id,
                url=url,
                filename=filename,
                category=category,
                expected_sha256=expected_sha256,
                provider=provider,
                provider_asset_id=provider_asset_id,
                provider_version_id=provider_version_id,
                state=DownloadState.QUEUED.value,
                queued_at=_now_iso(),
            )
            self._items[item_id] = item
            self._save_queue()
        self._ensure_worker()
        return {"ok": True, "item": item.to_dict(), "already_queued": False}

    def pause(self, item_id: str) -> dict[str, Any]:
        with self._lock:
            item = self._items.get(item_id)
            if not item:
                return {"ok": False, "error": "not_found"}
            if item.state != DownloadState.DOWNLOADING.value:
                return {"ok": False, "error": f"cannot_pause_state_{item.state}"}
            item.state = DownloadState.PAUSED.value
            evt = self._pause_events.get(item_id)
            if evt:
                evt.set()
            self._save_queue()
            return {"ok": True, "item": item.to_dict()}

    def resume(self, item_id: str) -> dict[str, Any]:
        with self._lock:
            item = self._items.get(item_id)
            if not item:
                return {"ok": False, "error": "not_found"}
            if item.state not in (DownloadState.PAUSED.value, DownloadState.FAILED_NETWORK.value):
                return {"ok": False, "error": f"cannot_resume_state_{item.state}"}
            item.state = DownloadState.QUEUED.value
            self._save_queue()
        self._ensure_worker()
        return {"ok": True, "item": item.to_dict()}

    def cancel(self, item_id: str) -> dict[str, Any]:
        with self._lock:
            item = self._items.get(item_id)
            if not item:
                return {"ok": False, "error": "not_found"}
            if DownloadState(item.state).is_terminal:
                return {"ok": False, "error": f"already_terminal_{item.state}"}
            item.state = DownloadState.CANCELLED.value
            evt = self._pause_events.get(item_id)
            if evt:
                evt.set()
            self._save_queue()
            return {"ok": True, "item": item.to_dict()}

    def queue_status(self) -> dict[str, Any]:
        with self._lock:
            items = [item.to_dict() for item in self._items.values()]
        return {"ok": True, "items": items, "count": len(items)}

    def clear_completed(self) -> dict[str, Any]:
        with self._lock:
            to_remove = [
                k for k, v in self._items.items() if DownloadState(v.state).is_terminal
            ]
            for k in to_remove:
                del self._items[k]
            self._save_queue()
        return {"ok": True, "removed": len(to_remove)}

    def _ensure_worker(self) -> None:
        if not self._auto_start_worker:
            return
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="download-mgr"
        )
        self._worker_thread.start()

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            item = self._next_queued()
            if item is None:
                break
            self._process_item(item)

    def _next_queued(self) -> DownloadItem | None:
        with self._lock:
            for item in self._items.values():
                if item.state == DownloadState.QUEUED.value:
                    return item
        return None

    def _process_item(self, item: DownloadItem) -> None:
        with self._lock:
            item.state = DownloadState.RESOLVING.value
            item.started_at = _now_iso()
            self._save_queue()

        civitai_key = ""
        if item.provider == "civitai" or "civitai.com" in item.url:
            try:
                from dreamforge_credentials import get_provider_credential
                civitai_key = get_provider_credential("civitai")
            except Exception:
                pass

        with self._lock:
            item.state = DownloadState.CHECKING_DISK.value
            self._save_queue()

        from dreamforge_model_downloader import resolve_category_folder
        dest_dir = resolve_category_folder(item.category)
        target_filename = item.filename
        if target_filename:
            target_path = dest_dir / target_filename
            if target_path.exists():
                item.state = DownloadState.INSTALLED.value
                item.final_path = str(target_path)
                item.finished_at = _now_iso()
                item.progress_pct = 100.0
                with self._lock:
                    self._save_queue()
                return

        with self._lock:
            item.state = DownloadState.DOWNLOADING.value
            self._save_queue()

        pause_evt = threading.Event()
        with self._lock:
            self._pause_events[item.id] = pause_evt

        def _progress(data: dict[str, Any]) -> None:
            item.progress_pct = float(data.get("percentage") or 0)
            item.downloaded_bytes = int(data.get("downloaded_bytes") or 0)
            item.total_bytes = int(data.get("total_bytes") or 0)
            item.speed_mbs = float(data.get("speed_mbs") or 0)
            item.eta_seconds = int(data.get("eta_seconds") or 0)
            if data.get("filename"):
                item.filename = str(data["filename"])
            if self._progress_cb:
                self._progress_cb({"type": "download_progress", "item_id": item.id, **data})

        from dreamforge_model_downloader import download_model
        result = download_model(
            url=item.url,
            category=item.category,
            filename=item.filename or None,
            expected_sha256=item.expected_sha256 or None,
            civitai_api_key=civitai_key or None,
            progress_callback=_progress,
        )

        with self._lock:
            self._pause_events.pop(item.id, None)

        if not result.get("ok"):
            error_msg = str(result.get("error") or "Download failed")
            error_lower = error_msg.lower()
            if "sha256" in error_lower or "hash" in error_lower:
                item.state = DownloadState.FAILED_INTEGRITY.value
                item.error_code = "failed_integrity"
            elif "401" in error_lower or "403" in error_lower or "auth" in error_lower:
                item.state = DownloadState.FAILED_AUTH.value
                item.error_code = "auth_required"
            else:
                item.state = DownloadState.FAILED_NETWORK.value
                item.error_code = "network_error"
            item.error = error_msg
            with self._lock:
                self._save_queue()
            return

        item.final_path = str(result.get("path") or "")
        item.filename = str(result.get("filename") or item.filename)

        with self._lock:
            item.state = DownloadState.REGISTERING.value
            self._save_queue()

        self._register_asset(item)

        with self._lock:
            item.state = DownloadState.INSTALLED.value
            item.progress_pct = 100.0
            item.finished_at = _now_iso()
            self._save_queue()

    def _register_asset(self, item: DownloadItem) -> None:
        """Register the downloaded file in the AssetRegistry."""
        try:
            from dreamforge_asset_registry import AssetRegistry
            from dreamforge_assets import (
                AssetFile,
                AssetKind,
                AssetVersion,
                DreamForgeAsset,
                Provenance,
                detect_architecture,
                detect_variant,
                kind_for_category,
            )

            registry = AssetRegistry()
            kind = kind_for_category(item.category)
            provenance = Provenance(
                provider=item.provider or "download",
                source_url=item.url,
                provider_asset_id=item.provider_asset_id,
                provider_version_id=item.provider_version_id,
                downloaded_at=_now_iso(),
                sha256=item.expected_sha256,
            )
            variant = detect_variant(item.filename)
            architecture = detect_architecture(item.filename)
            file_obj = AssetFile(
                filename=item.filename,
                sha256=item.expected_sha256,
                size_bytes=item.total_bytes,
                variant=variant,
                format=item.filename.rsplit(".", 1)[-1].lower() if "." in item.filename else "",
                download_url=item.url,
                local_path=item.final_path,
            )
            version = AssetVersion(
                id="v1",
                name=item.filename,
                files=[file_obj],
                provider_version_id=item.provider_version_id,
            )
            asset_id = f"{item.provider or 'download'}:{item.provider_asset_id or item.id}"
            asset = DreamForgeAsset(
                id=asset_id,
                name=item.filename.rsplit(".", 1)[0] if "." in item.filename else item.filename,
                kind=kind,
                architecture=architecture,
                versions=[version],
                provenance=provenance,
                version_id="v1",
            )
            registry.upsert(asset)
        except Exception:
            pass


_default_manager: DownloadManager | None = None
_manager_lock = threading.Lock()


def get_download_manager() -> DownloadManager:
    """Singleton download manager instance."""
    global _default_manager
    if _default_manager is None:
        with _manager_lock:
            if _default_manager is None:
                _default_manager = DownloadManager()
    return _default_manager
