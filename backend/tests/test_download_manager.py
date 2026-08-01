"""Tests for dreamforge_download_manager — persistent queue, states, enqueue/pause/resume/cancel."""

import pytest

from dreamforge_download_manager import (
    QUEUE_PATH,
    DownloadItem,
    DownloadManager,
    DownloadState,
    get_download_manager,
)


@pytest.fixture(autouse=True)
def clean_queue():
    if QUEUE_PATH.exists():
        QUEUE_PATH.unlink()
    yield
    if QUEUE_PATH.exists():
        QUEUE_PATH.unlink()


def make_manager(**kwargs) -> DownloadManager:
    return DownloadManager(auto_start_worker=False, **kwargs)


class TestDownloadStates:
    def test_terminal_states(self):
        assert DownloadState.INSTALLED.is_terminal is True
        assert DownloadState.CANCELLED.is_terminal is True
        assert DownloadState.FAILED_AUTH.is_terminal is True
        assert DownloadState.FAILED_INTEGRITY.is_terminal is True
        assert DownloadState.QUEUED.is_terminal is False
        assert DownloadState.DOWNLOADING.is_terminal is False

    def test_failed_states(self):
        assert DownloadState.FAILED_NETWORK.is_failed is True
        assert DownloadState.FAILED_AUTH.is_failed is True
        assert DownloadState.FAILED_DISK.is_failed is True
        assert DownloadState.INSTALLED.is_failed is False


class TestDownloadItem:
    def test_roundtrip(self):
        item = DownloadItem(
            id="abc",
            url="https://example.com/model.safetensors",
            filename="model.safetensors",
            category="checkpoints",
        )
        restored = DownloadItem.from_dict(item.to_dict())
        assert restored.id == "abc"
        assert restored.url == "https://example.com/model.safetensors"
        assert restored.category == "checkpoints"

    def test_from_dict_ignores_unknown_keys(self):
        item = DownloadItem.from_dict({"id": "x", "url": "u", "unknown_field": 123})
        assert item.id == "x"
        assert item.url == "u"


class TestDownloadManagerQueue:
    def test_enqueue_creates_item(self):
        mgr = make_manager()
        result = mgr.enqueue(
            url="https://example.com/model.safetensors",
            category="checkpoints",
            filename="model.safetensors",
        )
        assert result["ok"] is True
        assert result["already_queued"] is False
        assert result["item"]["state"] == "queued"
        assert result["item"]["url"] == "https://example.com/model.safetensors"

    def test_enqueue_same_item_is_idempotent(self):
        mgr = make_manager()
        mgr.enqueue(url="https://example.com/model.safetensors")
        result = mgr.enqueue(url="https://example.com/model.safetensors")
        assert result["already_queued"] is True

    def test_queue_status(self):
        mgr = make_manager()
        mgr.enqueue(url="https://example.com/a.safetensors")
        mgr.enqueue(url="https://example.com/b.safetensors")
        status = mgr.queue_status()
        assert status["count"] == 2
        assert len(status["items"]) == 2

    def test_persistence_across_instances(self):
        mgr1 = make_manager()
        mgr1.enqueue(url="https://example.com/model.safetensors")
        mgr2 = make_manager()
        status = mgr2.queue_status()
        assert status["count"] == 1
        assert status["items"][0]["url"] == "https://example.com/model.safetensors"

    def test_restart_resets_downloading_to_queued(self):
        mgr1 = make_manager()
        mgr1.enqueue(url="https://example.com/model.safetensors")
        status = mgr1.queue_status()
        item_id = status["items"][0]["id"]
        with mgr1._lock:
            mgr1._items[item_id].state = DownloadState.DOWNLOADING.value
            mgr1._save_queue()
        mgr2 = make_manager()
        restored = [i for i in mgr2.queue_status()["items"] if i["id"] == item_id][0]
        assert restored["state"] == "queued"

    def test_pause_non_downloading_fails(self):
        mgr = make_manager()
        result = mgr.enqueue(url="https://example.com/model.safetensors")
        item_id = result["item"]["id"]
        pause = mgr.pause(item_id)
        assert pause["ok"] is False
        assert "cannot_pause" in pause["error"]

    def test_pause_unknown_id(self):
        mgr = make_manager()
        result = mgr.pause("missing")
        assert result["ok"] is False
        assert result["error"] == "not_found"

    def test_resume_paused(self):
        mgr = make_manager()
        result = mgr.enqueue(url="https://example.com/model.safetensors")
        item_id = result["item"]["id"]
        with mgr._lock:
            mgr._items[item_id].state = DownloadState.DOWNLOADING.value
        assert mgr.pause(item_id)["ok"] is True
        assert mgr.resume(item_id)["ok"] is True
        resumed = [i for i in mgr.queue_status()["items"] if i["id"] == item_id][0]
        assert resumed["state"] == "queued"

    def test_resume_unknown_id(self):
        mgr = make_manager()
        result = mgr.resume("missing")
        assert result["ok"] is False
        assert result["error"] == "not_found"

    def test_cancel(self):
        mgr = make_manager()
        result = mgr.enqueue(url="https://example.com/model.safetensors")
        item_id = result["item"]["id"]
        assert mgr.cancel(item_id)["ok"] is True
        cancelled = [i for i in mgr.queue_status()["items"] if i["id"] == item_id][0]
        assert cancelled["state"] == "cancelled"

    def test_cancel_terminal_fails(self):
        mgr = make_manager()
        result = mgr.enqueue(url="https://example.com/model.safetensors")
        item_id = result["item"]["id"]
        mgr.cancel(item_id)
        second = mgr.cancel(item_id)
        assert second["ok"] is False
        assert "already_terminal" in second["error"]

    def test_clear_completed(self):
        mgr = make_manager()
        r1 = mgr.enqueue(url="https://example.com/a.safetensors")
        r2 = mgr.enqueue(url="https://example.com/b.safetensors")
        with mgr._lock:
            mgr._items[r1["item"]["id"]].state = DownloadState.INSTALLED.value
        result = mgr.clear_completed()
        assert result["removed"] == 1
        remaining = mgr.queue_status()["items"]
        assert len(remaining) == 1
        assert remaining[0]["id"] == r2["item"]["id"]


class TestDownloadManagerProcessing:
    def test_worker_processes_queued_item(self, monkeypatch, tmp_path):
        mgr = make_manager()
        called = {}

        def fake_download(**kwargs):
            called["url"] = kwargs["url"]
            path = tmp_path / "model.safetensors"
            path.write_bytes(b"model")
            return {"ok": True, "path": str(path), "filename": "model.safetensors"}

        monkeypatch.setattr(
            "dreamforge_model_downloader.download_model", fake_download
        )
        result = mgr.enqueue(url="https://example.com/model.safetensors", category="checkpoints")
        item_id = result["item"]["id"]
        mgr._process_item(mgr._items[item_id])
        assert called["url"] == "https://example.com/model.safetensors"
        item = [i for i in mgr.queue_status()["items"] if i["id"] == item_id][0]
        assert item["state"] == "installed"

    def test_worker_failure_marks_failed(self, monkeypatch, tmp_path):
        mgr = make_manager()

        def fake_fail(**kwargs):
            return {"ok": False, "error": "Download failed: 403 Forbidden"}

        monkeypatch.setattr("dreamforge_model_downloader.download_model", fake_fail)
        result = mgr.enqueue(url="https://example.com/gated.safetensors")
        item_id = result["item"]["id"]
        mgr._process_item(mgr._items[item_id])
        item = [i for i in mgr.queue_status()["items"] if i["id"] == item_id][0]
        assert item["state"] == "failed_auth"
        assert item["error_code"] == "auth_required"

    def test_worker_integrity_failure(self, monkeypatch, tmp_path):
        mgr = make_manager()

        def fake_bad_hash(**kwargs):
            return {"ok": False, "error": "SHA256 mismatch for model.safetensors"}

        monkeypatch.setattr("dreamforge_model_downloader.download_model", fake_bad_hash)
        result = mgr.enqueue(url="https://example.com/model.safetensors", expected_sha256="a" * 64)
        item_id = result["item"]["id"]
        mgr._process_item(mgr._items[item_id])
        item = [i for i in mgr.queue_status()["items"] if i["id"] == item_id][0]
        assert item["state"] == "failed_integrity"
        assert item["error_code"] == "failed_integrity"

    def test_already_installed_skips_download(self, monkeypatch, tmp_path):
        mgr = make_manager()
        model_dir = tmp_path / "checkpoints"
        model_dir.mkdir(parents=True)
        existing = model_dir / "existing.safetensors"
        existing.write_bytes(b"data")

        def fake_resolve_category(category):
            return model_dir

        def fake_download(**kwargs):
            raise AssertionError("should not download when file exists")

        monkeypatch.setattr(
            "dreamforge_model_downloader.resolve_category_folder", fake_resolve_category
        )
        monkeypatch.setattr("dreamforge_model_downloader.download_model", fake_download)
        result = mgr.enqueue(
            url="https://example.com/model.safetensors",
            category="checkpoints",
            filename="existing.safetensors",
        )
        item_id = result["item"]["id"]
        mgr._process_item(mgr._items[item_id])
        item = [i for i in mgr.queue_status()["items"] if i["id"] == item_id][0]
        assert item["state"] == "installed"
        assert item["final_path"] == str(existing)

    def test_existing_file_with_wrong_hash_is_replaced_only_by_verified_download(self, monkeypatch, tmp_path):
        import hashlib
        model_dir = tmp_path / "checkpoints"
        model_dir.mkdir()
        existing = model_dir / "existing.safetensors"
        existing.write_bytes(b"wrong")
        expected = hashlib.sha256(b"correct").hexdigest()
        monkeypatch.setattr("dreamforge_model_downloader.resolve_category_folder", lambda _category: model_dir)
        def fake_download(**_kwargs):
            existing.write_bytes(b"correct")
            return {"ok": True, "path": str(existing), "filename": existing.name}
        monkeypatch.setattr("dreamforge_model_downloader.download_model", fake_download)
        mgr = make_manager()
        result = mgr.enqueue(url="https://example.com/model", filename="existing.safetensors", expected_sha256=expected)
        mgr._process_item(mgr._items[result["item"]["id"]])
        assert mgr.queue_status()["items"][0]["state"] == "installed"
        assert existing.read_bytes() == b"correct"

    def test_pause_interrupt_keeps_partial_item_paused(self, monkeypatch):
        mgr = make_manager()
        result = mgr.enqueue(url="https://example.com/model")
        item = mgr._items[result["item"]["id"]]
        def fake_download(**kwargs):
            assert mgr.pause(item.id)["ok"] is True
            assert kwargs["should_stop"]() is True
            return {"ok": False, "interrupted": True}
        monkeypatch.setattr("dreamforge_model_downloader.download_model", fake_download)
        mgr._process_item(item)
        assert item.state == "paused"


class TestGetDownloadManager:
    def test_singleton(self):
        mgr1 = get_download_manager()
        mgr2 = get_download_manager()
        assert mgr1 is mgr2
