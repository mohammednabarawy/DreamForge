"""Tests for model library disk cache."""

from __future__ import annotations

import json

import pytest

import dreamforge_model_library_cache as cache


def test_fingerprint_changes_when_model_file_added(tmp_path, monkeypatch):
    models = tmp_path / "models"
    (models / "checkpoints").mkdir(parents=True)
    (models / "loras").mkdir(parents=True)
    thumb = tmp_path / "cache"
    (thumb / "checkpoints").mkdir(parents=True)
    (thumb / "loras").mkdir(parents=True)

    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "library_cache")
    monkeypatch.setattr(cache, "MANIFEST_PATH", tmp_path / "library_cache" / "manifest.json")
    monkeypatch.setattr(cache, "INVENTORY_PATH", tmp_path / "library_cache" / "inventory.json")
    monkeypatch.setattr(cache, "MODEL_GALLERY_PATH", tmp_path / "library_cache" / "model_gallery.json")
    monkeypatch.setattr(cache, "LORA_GALLERY_PATH", tmp_path / "library_cache" / "lora_gallery.json")
    monkeypatch.setattr("dreamforge_cli_inventory.MODELS_ROOT", models)
    monkeypatch.setattr(cache, "BACKEND_ROOT", tmp_path)

    first = cache.compute_library_fingerprint()
    (models / "checkpoints" / "demo.safetensors").write_bytes(b"x" * 2048)
    second = cache.compute_library_fingerprint()
    assert first != second


def test_get_cached_model_gallery_reuses_disk_cache(tmp_path, monkeypatch):
    models = tmp_path / "models"
    (models / "checkpoints").mkdir(parents=True)
    (models / "loras").mkdir(parents=True)
    cache_dir = tmp_path / "library_cache"
    cache_dir.mkdir()

    monkeypatch.setattr(cache, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(cache, "MANIFEST_PATH", cache_dir / "manifest.json")
    monkeypatch.setattr(cache, "INVENTORY_PATH", cache_dir / "inventory.json")
    monkeypatch.setattr(cache, "MODEL_GALLERY_PATH", cache_dir / "model_gallery.json")
    monkeypatch.setattr(cache, "LORA_GALLERY_PATH", cache_dir / "lora_gallery.json")
    monkeypatch.setattr("dreamforge_cli_inventory.MODELS_ROOT", models)
    monkeypatch.setattr(cache, "BACKEND_ROOT", tmp_path)

    fingerprint = cache.compute_library_fingerprint()
    gallery = [{"category": "checkpoints", "relative_path": "demo.safetensors", "caption": "x"}]
    cache._write_json(cache.MODEL_GALLERY_PATH, gallery)
    cache._write_json(
        cache.MANIFEST_PATH,
        {"fingerprint": fingerprint, "built_at": 1, "counts": {"model_gallery": 1}},
    )

    calls = {"build": 0}

    def _fake_build():
        calls["build"] += 1
        return [{"category": "checkpoints", "relative_path": "other.safetensors"}]

    monkeypatch.setattr(cache, "build_model_gallery_items", _fake_build)

    items, from_cache = cache.get_cached_model_gallery(force_refresh=False)
    assert from_cache is True
    assert items == gallery
    assert calls["build"] == 0


def test_force_refresh_invalidates_gallery_cache(tmp_path, monkeypatch):
    models = tmp_path / "models"
    (models / "checkpoints").mkdir(parents=True)
    (models / "loras").mkdir(parents=True)
    cache_dir = tmp_path / "library_cache"
    cache_dir.mkdir()

    monkeypatch.setattr(cache, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(cache, "MANIFEST_PATH", cache_dir / "manifest.json")
    monkeypatch.setattr(cache, "INVENTORY_PATH", cache_dir / "inventory.json")
    monkeypatch.setattr(cache, "MODEL_GALLERY_PATH", cache_dir / "model_gallery.json")
    monkeypatch.setattr(cache, "LORA_GALLERY_PATH", cache_dir / "lora_gallery.json")
    monkeypatch.setattr("dreamforge_cli_inventory.MODELS_ROOT", models)
    monkeypatch.setattr(cache, "BACKEND_ROOT", tmp_path)

    fingerprint = cache.compute_library_fingerprint()
    cache._write_json(cache.MODEL_GALLERY_PATH, [{"stale": True}])
    cache._write_json(cache.MANIFEST_PATH, {"fingerprint": fingerprint})

    rebuilt = [{"category": "checkpoints", "relative_path": "fresh.safetensors"}]
    monkeypatch.setattr(cache, "build_model_gallery_items", lambda: rebuilt)
    monkeypatch.setattr(cache, "build_lora_gallery_items", lambda: [])
    monkeypatch.setattr(
        cache,
        "build_inventory_payload",
        lambda: {"ok": True, "categories": {}, "styles": [], "style_groups": []},
    )

    items, from_cache = cache.get_cached_model_gallery(force_refresh=True)
    assert from_cache is False
    assert items == rebuilt
    assert not cache.MANIFEST_PATH.exists() or json.loads(cache.MANIFEST_PATH.read_text())
