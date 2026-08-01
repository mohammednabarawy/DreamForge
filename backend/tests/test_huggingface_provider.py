"""Tests for dreamforge_huggingface_provider — normalization and gated detection."""

from dreamforge_assets import AssetKind
from dreamforge_huggingface_provider import (
    HuggingFaceProvider,
    normalize_hf_models,
)
from dreamforge_provider_base import ProviderSearchParams


SAMPLE_HF_ITEM = {
    "id": "black-forest-labs/FLUX.1-dev",
    "author": "black-forest-labs",
    "lastModified": "2025-01-15T00:00:00Z",
    "pipeline_tag": "text-to-image",
    "library_name": "diffusers",
    "tags": ["text-to-image", "flux"],
    "gated": False,
    "private": False,
    "siblings": [
        {"rfilename": "model.safetensors"},
        {"rfilename": "model_index.json"},
        {"rfilename": "README.md"},
        {"rfilename": "ae.safetensors"},
    ],
}


SAMPLE_GATED_ITEM = {
    "id": "meta-llama/Llama-3-70b",
    "author": "meta-llama",
    "pipeline_tag": "text-generation",
    "tags": ["text-generation"],
    "gated": "manual",
    "private": False,
    "siblings": [
        {"rfilename": "model-00001-of-00079.safetensors"},
        {"rfilename": "config.json"},
    ],
}


SAMPLE_PRIVATE_ITEM = {
    "id": "private/repo",
    "author": "private",
    "tags": [],
    "gated": False,
    "private": True,
    "siblings": [{"rfilename": "model.safetensors"}],
}


class TestNormalizeHfModels:
    def test_basic_item(self):
        assets = normalize_hf_models([SAMPLE_HF_ITEM])
        assert len(assets) == 1
        asset = assets[0]
        assert asset.id == "huggingface:black-forest-labs/FLUX.1-dev"
        assert asset.name == "FLUX.1-dev"
        assert asset.provenance.provider == "huggingface"
        assert asset.provenance.author == "black-forest-labs"

    def test_only_weight_files_kept(self):
        assets = normalize_hf_models([SAMPLE_HF_ITEM])
        version = assets[0].versions[0]
        filenames = [f.filename for f in version.files]
        assert "model.safetensors" in filenames
        assert "ae.safetensors" in filenames
        assert "model_index.json" not in filenames
        assert "README.md" not in filenames

    def test_download_url_format(self):
        assets = normalize_hf_models([SAMPLE_HF_ITEM])
        f = assets[0].versions[0].files[0]
        assert f.download_url.startswith("https://huggingface.co/")
        assert "/resolve/main/" in f.download_url

    def test_gated_repo_marked(self):
        assets = normalize_hf_models([SAMPLE_GATED_ITEM])
        assert len(assets) == 1
        assert "[gated]" in assets[0].description

    def test_private_repo_marked(self):
        assets = normalize_hf_models([SAMPLE_PRIVATE_ITEM])
        assert len(assets) == 1
        assert "[gated]" in assets[0].description

    def test_empty_items(self):
        assert normalize_hf_models([]) == []
        assert normalize_hf_models(None) == []

    def test_item_without_id(self):
        assets = normalize_hf_models([{"id": "", "siblings": []}])
        assert len(assets) == 0

    def test_item_without_weight_files(self):
        item = {"id": "x/y", "siblings": [{"rfilename": "config.json"}]}
        assets = normalize_hf_models([item])
        assert len(assets) == 0

    def test_kind_from_tags(self):
        item = {
            "id": "x/y",
            "tags": ["text-to-image", "controlnet"],
            "siblings": [{"rfilename": "model.safetensors"}],
        }
        assets = normalize_hf_models([item])
        assert assets[0].kind == AssetKind.CONTROLNET

    def test_architecture_detected(self):
        assets = normalize_hf_models([SAMPLE_HF_ITEM])
        assert assets[0].architecture == "flux"


class TestHuggingFaceProviderUrlBuild:
    def test_basic_search(self):
        provider = HuggingFaceProvider()
        params = ProviderSearchParams(query="flux", kind="checkpoint", limit=10, page=1)
        url = provider._build_url(params)
        assert "search=flux" in url
        assert "limit=10" in url
        assert "page=1" in url

    def test_no_kind(self):
        provider = HuggingFaceProvider()
        params = ProviderSearchParams(query="test", kind="")
        url = provider._build_url(params)
        assert "filter=" not in url

    def test_supports_kind(self):
        provider = HuggingFaceProvider()
        assert provider.supports_kind("checkpoint") is True
        assert provider.supports_kind("lora") is True
        assert provider.supports_kind("") is True
