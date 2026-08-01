"""Tests for dreamforge_civitai_provider — normalization and provider search URL building."""

from dreamforge_assets import AssetKind
from dreamforge_civitai_provider import (
    CivitaiProvider,
    civitai_kind_to_asset_kind,
    normalize_civitai_models,
)
from dreamforge_provider_base import ProviderSearchParams, SearchFilters


SAMPLE_CIVITAI_ITEM = {
    "id": 12345,
    "name": "Test Flux Model",
    "type": "Checkpoint",
    "description": "<p>A great model</p>",
    "creator": {"username": "testuser"},
    "tags": ["flux", "realistic"],
    "modelVersions": [
        {
            "id": 67890,
            "name": "v1.0",
            "baseModel": "Flux.1 D",
            "publishedAt": "2025-01-15T00:00:00Z",
            "images": [
                {"url": "https://image.civitai.com/x/nsfw-false.jpg", "nsfw": False},
                {"url": "https://image.civitai.com/x/nsfw-true.jpg", "nsfw": True},
            ],
            "files": [
                {
                    "id": 111,
                    "name": "test_flux_fp16.safetensors",
                    "sizeKB": 6500000,
                    "type": "Model",
                    "metadata": {"fp": "fp16", "format": "SafeTensor"},
                    "downloadUrl": "https://civitai.com/api/download/models/67890",
                    "hashes": {"SHA256": "ABCDEF1234567890"},
                },
                {
                    "id": 112,
                    "name": "preview.png",
                    "sizeKB": 500,
                    "type": "Preview",
                    "metadata": {},
                    "downloadUrl": "https://civitai.com/preview/112",
                    "hashes": {},
                },
            ],
        }
    ],
}


class TestCivitaiKindMapping:
    def test_checkpoint(self):
        assert civitai_kind_to_asset_kind("Checkpoint") == "checkpoint"

    def test_lora(self):
        assert civitai_kind_to_asset_kind("LoRA") == "lora"

    def test_vae(self):
        assert civitai_kind_to_asset_kind("VAE") == "vae"

    def test_textual_inversion(self):
        assert civitai_kind_to_asset_kind("TextualInversion") == "embedding"

    def test_unknown(self):
        assert civitai_kind_to_asset_kind("SomethingNew") == "unknown"

    def test_none(self):
        assert civitai_kind_to_asset_kind(None) == "unknown"


class TestNormalizeCivitaiModels:
    def test_single_item(self):
        assets = normalize_civitai_models([SAMPLE_CIVITAI_ITEM])
        assert len(assets) == 1
        asset = assets[0]
        assert asset.id == "civitai:12345"
        assert asset.name == "Test Flux Model"
        assert asset.kind == AssetKind.CHECKPOINT
        assert asset.provenance.provider == "civitai"
        assert asset.provenance.provider_asset_id == "12345"
        assert asset.provenance.author == "testuser"
        assert "flux" in asset.tags

    def test_version_and_files(self):
        assets = normalize_civitai_models([SAMPLE_CIVITAI_ITEM])
        asset = assets[0]
        assert len(asset.versions) == 1
        version = asset.versions[0]
        assert version.name == "v1.0"
        assert version.base_model == "Flux.1 D"
        assert len(version.files) == 1  # Preview skipped
        f = version.files[0]
        assert f.filename == "test_flux_fp16.safetensors"
        assert f.sha256 == "abcdef1234567890"  # lowered
        assert f.variant == "fp16"
        assert f.format == "safetensors"
        assert "download" in f.download_url

    def test_thumbnail_prefers_non_nsfw_image(self):
        assets = normalize_civitai_models([SAMPLE_CIVITAI_ITEM])
        version = assets[0].versions[0]
        assert version.thumbnail_url == "https://image.civitai.com/x/nsfw-false.jpg"

    def test_empty_items(self):
        assert normalize_civitai_models([]) == []
        assert normalize_civitai_models(None) == []

    def test_item_without_versions(self):
        item = {"id": 1, "name": "NoVersions", "type": "Checkpoint", "modelVersions": []}
        assets = normalize_civitai_models([item])
        assert len(assets) == 0

    def test_item_without_name(self):
        item = {"id": 1, "name": "", "type": "Checkpoint"}
        assets = normalize_civitai_models([item])
        assert len(assets) == 0

    def test_html_stripped_from_description(self):
        assets = normalize_civitai_models([SAMPLE_CIVITAI_ITEM])
        assert "<p>" not in assets[0].description
        assert "A great model" in assets[0].description

    def test_architecture_detected(self):
        assets = normalize_civitai_models([SAMPLE_CIVITAI_ITEM])
        assert assets[0].architecture == "flux"


class TestCivitaiProviderUrlBuild:
    def test_basic_search(self):
        provider = CivitaiProvider()
        params = ProviderSearchParams(query="flux", kind="checkpoint", limit=10, page=1)
        url = provider._build_url(params)
        assert "query=flux" in url
        assert "types=Checkpoint" in url
        assert "limit=10" in url
        assert "page=1" in url

    def test_nsfw_false_default(self):
        provider = CivitaiProvider()
        params = ProviderSearchParams(query="test", filters=SearchFilters(nsfw=False))
        url = provider._build_url(params)
        assert "nsfw=false" in url

    def test_nsfw_true(self):
        provider = CivitaiProvider()
        params = ProviderSearchParams(query="test", filters=SearchFilters(nsfw=True))
        url = provider._build_url(params)
        assert "nsfw=false" not in url

    def test_lora_type(self):
        provider = CivitaiProvider()
        params = ProviderSearchParams(query="test", kind="lora")
        url = provider._build_url(params)
        assert "types=LoRA" in url

    def test_no_kind(self):
        provider = CivitaiProvider()
        params = ProviderSearchParams(query="test", kind="")
        url = provider._build_url(params)
        assert "types=" not in url

    def test_supports_kind(self):
        provider = CivitaiProvider()
        assert provider.supports_kind("checkpoint") is True
        assert provider.supports_kind("lora") is True
        assert provider.supports_kind("") is True
