"""Tests for Phase 4 bridge handlers — compatibility surface + variant recommendation."""

import json

from dreamforge_desktop_bridge import HANDLERS, handle_request


def _call(cmd, params=None):
    req = {"cmd": cmd, "params": params or {}}
    return handle_request(json.dumps(req))


def _asset_dict():
    return {
        "id": "civitai:9",
        "name": "Flux Model",
        "kind": "checkpoint",
        "architecture": "flux",
        "versions": [
            {
                "id": "v1",
                "name": "v1",
                "files": [
                    {
                        "filename": "flux_fp16.safetensors",
                        "sha256": "f" * 64,
                        "size_bytes": 23 * 1024**3,
                        "variant": "fp16",
                        "format": "safetensors",
                    },
                    {
                        "filename": "flux_fp8.safetensors",
                        "sha256": "e" * 64,
                        "size_bytes": 12 * 1024**3,
                        "variant": "fp8",
                        "format": "safetensors",
                    },
                ],
            }
        ],
        "provenance": {"provider": "civitai", "provider_asset_id": "9"},
    }


class TestPhase4BridgeHandlers:
    def test_supported_architectures(self):
        result = _call("discover_supported_architectures")
        assert result["ok"] is True
        assert "architectures" in result
        assert result["count"] == len(result["architectures"])
        assert "flux" in result["architectures"]
        assert "sdxl" in result["architectures"]

    def test_recommend_file_variants(self, monkeypatch):
        from dreamforge_compute_profile import detect_compute_profile_static

        monkeypatch.setattr(
            "dreamforge_compute_profile.detect_compute_profile",
            lambda *a, **k: detect_compute_profile_static(
                vram_mb=24576, vram_profile="auto"
            ),
        )
        result = _call("discover_recommend_file_variants", {"asset": _asset_dict()})
        assert result["ok"] is True
        assert result["recommended"]["variant"] == "fp16"
        assert len(result["files"]) == 2
        assert "profile" in result

    def test_recommend_file_variants_missing_asset(self):
        result = _call("discover_recommend_file_variants", {})
        assert result["ok"] is False
        assert result.get("error") == "missing_asset"

    def test_all_phase4_handlers_registered(self):
        for cmd in [
            "discover_supported_architectures",
            "discover_recommend_file_variants",
        ]:
            assert cmd in HANDLERS, f"missing handler: {cmd}"
