"""Tests for Phase 3 bridge handlers — discovery, provider, credential, download."""

import json

from dreamforge_desktop_bridge import HANDLERS, handle_request


def _call(cmd, params=None):
    req = {"cmd": cmd, "params": params or {}}
    return handle_request(json.dumps(req))


class TestPhase3BridgeHandlers:
    def test_provider_list(self):
        result = _call("provider_list")
        assert result["ok"] is True
        ids = {p["id"] for p in result["providers"]}
        assert "civitai" in ids
        assert "huggingface" in ids

    def test_credential_status(self):
        result = _call("credential_status")
        assert result["ok"] is True
        assert "civitai" in result["status"]

    def test_discovery_search(self, monkeypatch):
        def fake_search(self, *args, **kwargs):
            return {"ok": True, "assets": [], "count": 0, "providers": []}

        monkeypatch.setattr(
            "dreamforge_discovery_service.DiscoveryService.search", fake_search
        )
        result = _call("discovery_search", {"query": "flux", "kind": "checkpoint"})
        assert result["ok"] is True
        assert result["assets"] == []

    def test_discovery_cache_invalidate(self):
        result = _call("discovery_cache_invalidate")
        assert result["ok"] is True
        assert "removed" in result

    def test_credential_set_missing_provider(self):
        result = _call("credential_set", {"secret": "abc"})
        assert result["ok"] is False
        assert result.get("error") == "missing_provider"

    def test_download_enqueue_missing_url(self):
        result = _call("download_enqueue", {})
        assert result["ok"] is False
        assert result.get("error") == "missing_url"

    def test_download_queue_status(self):
        result = _call("download_queue_status")
        assert result["ok"] is True
        assert "items" in result

    def test_download_pause_missing_id(self):
        result = _call("download_pause", {})
        assert result["ok"] is False
        assert result.get("error") == "missing_item_id"

    def test_download_resume_missing_id(self):
        result = _call("download_resume", {})
        assert result["ok"] is False
        assert result.get("error") == "missing_item_id"

    def test_download_cancel_missing_id(self):
        result = _call("download_cancel", {})
        assert result["ok"] is False
        assert result.get("error") == "missing_item_id"

    def test_download_clear_completed(self):
        result = _call("download_clear_completed")
        assert result["ok"] is True
        assert "removed" in result

    def test_all_phase3_handlers_registered(self):
        for cmd in [
            "provider_list",
            "discovery_search",
            "discovery_cache_invalidate",
            "credential_status",
            "credential_set",
            "download_enqueue",
            "download_queue_status",
            "download_pause",
            "download_resume",
            "download_cancel",
            "download_clear_completed",
        ]:
            assert cmd in HANDLERS, f"missing handler: {cmd}"

    def test_custom_style_handlers_registered(self):
        assert "import_fooocus_styles" in HANDLERS
        assert "delete_custom_style" in HANDLERS

    def test_workflow_template_handler_registered(self):
        assert "list_workflow_templates" in HANDLERS

    def test_workflow_compatibility_handler_registered(self):
        assert "analyze_workflow_compatibility" in HANDLERS
        assert "compile_workflow_recipe" in HANDLERS
        assert "save_workflow_file" in HANDLERS

    def test_recipe_discovery_handler_registered(self):
        assert "recipe_discovery_search" in HANDLERS
