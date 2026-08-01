from dreamforge_assets import (
    AssetFile,
    AssetKind,
    AssetVersion,
    DreamForgeAsset,
    Provenance,
    asset_id_from_provenance,
    category_for_kind,
    detect_architecture,
    detect_variant,
    kind_for_category,
)


def test_asset_kind_from_string_normalizes_variants():
    assert AssetKind.from_string("checkpoint") is AssetKind.CHECKPOINT
    assert AssetKind.from_string("CHECKPOINTS") is AssetKind.CHECKPOINT
    assert AssetKind.from_string("lora") is AssetKind.LORA
    assert AssetKind.from_string("text-encoder") is AssetKind.TEXT_ENCODER
    assert AssetKind.from_string("upscale_models") is AssetKind.UPSCALER
    assert AssetKind.from_string("") is AssetKind.UNKNOWN
    assert AssetKind.from_string("nonsense") is AssetKind.UNKNOWN


def test_kind_category_round_trip():
    assert kind_for_category("checkpoints") is AssetKind.CHECKPOINT
    assert kind_for_category("LORAS") is AssetKind.LORA
    assert kind_for_category(None) is AssetKind.UNKNOWN
    assert category_for_kind(AssetKind.CHECKPOINT) == "checkpoints"
    assert category_for_kind(AssetKind.UPSCALER) == "upscale_models"
    assert category_for_kind(AssetKind.TEXT_ENCODER) == "text_encoders"


def test_detect_variant_prefers_specific_hints():
    assert detect_variant("model_fp8_scaled.safetensors") == "fp8_scaled"
    assert detect_variant("model_fp16.safetensors") == "fp16"
    assert detect_variant("model_q4_k_m.gguf") == "q4_k_m"
    assert detect_variant("model.safetensors") == ""


def test_detect_architecture_uses_family_metadata_first():
    assert detect_architecture("anything.safetensors", {"family": "FLUX"}) == "flux"
    assert detect_architecture("anything.safetensors", {"engine_name": "model.safetensors", "family": "sdxl"}) == "sdxl"


def test_detect_architecture_filename_heuristics():
    assert detect_architecture("flux1-dev-fp8.safetensors") == "flux"
    assert detect_architecture("flux-fill-dev.safetensors") == "flux_fill"
    assert detect_architecture("flux1-kontext.safetensors") == "flux_kontext"
    assert detect_architecture("qwen-image-edit.safetensors") == "qwen_image_edit"
    assert detect_architecture("sd_xl_base_1.0.safetensors") == "sdxl"
    assert detect_architecture("dreamshaper.safetensors") == "sd15"
    assert detect_architecture("unknown_model.bin") == ""


def test_provenance_license_label_never_infers_permission():
    unknown = Provenance(provider="civitai", source_url="https://example.com/m")
    assert unknown.license_label.startswith("Unknown")
    known = Provenance(provider="civitai", license="civitai-cc0")
    assert known.license_label == "civitai-cc0"
    assert Provenance.local().provider == "local"


def test_asset_identity_from_provenance():
    prov = Provenance(
        provider="civitai",
        provider_asset_id="123456",
        provider_version_id="654321",
    )
    assert asset_id_from_provenance(prov) == "civitai:123456"

    url_prov = Provenance(provider="huggingface", source_url="https://huggingface.co/org/repo")
    assert asset_id_from_provenance(url_prov).startswith("huggingface:")
    assert asset_id_from_provenance(Provenance(provider="")) == ""


def test_asset_active_version_and_primary_file_prefer_sha256():
    sha_file = AssetFile(filename="v2.safetensors", sha256="a" * 64)
    no_sha_file = AssetFile(filename="v1.safetensors")
    v1 = AssetVersion(id="v1", files=[no_sha_file])
    v2 = AssetVersion(id="v2", files=[sha_file])
    asset = DreamForgeAsset(
        id="civitai:1",
        versions=[v1, v2],
        version_id="v2",
        provenance=Provenance(provider="civitai", provider_asset_id="1"),
    )
    assert asset.active_version.id == "v2"
    assert asset.primary_file.sha256 == "a" * 64
    assert asset.all_sha256 == {"a" * 64}

    no_files = DreamForgeAsset(id="civitai:1", version_id="ghost", versions=[v1])
    assert no_files.active_version.id == "v1"


def test_asset_is_local_tracks_primary_file():
    remote = AssetFile(filename="m.safetensors", sha256="b" * 64, download_url="https://x/m")
    local = AssetFile(filename="m.safetensors", sha256="b" * 64, local_path="C:\\models\\m.safetensors")
    asset = DreamForgeAsset(
        id="civitai:1",
        versions=[AssetVersion(id="v1", files=[remote, local])],
        provenance=Provenance(provider="civitai", provider_asset_id="1"),
    )
    assert asset.is_local is True
    assert asset.to_dict()["is_local"] is True


def test_asset_round_trip_via_dict():
    asset = DreamForgeAsset(
        id="hf:org/repo",
        name="Test Model",
        kind=AssetKind.LORA,
        architecture="flux",
        versions=[
            AssetVersion(
                id="v1",
                name="v1",
                files=[AssetFile(filename="lora.safetensors", sha256="c" * 64, variant="fp16")],
                provider_version_id="abc",
                thumbnail_url="https://cdn.example.com/thumb.jpg",
            )
        ],
        provenance=Provenance(provider="huggingface", source_url="https://hf/org/repo", license="apache-2.0"),
        tags=["tag1"],
    )
    restored = DreamForgeAsset.from_dict(asset.to_dict())
    assert restored.id == asset.id
    assert restored.kind is AssetKind.LORA
    assert restored.architecture == "flux"
    assert restored.versions[0].files[0].sha256 == "c" * 64
    assert restored.versions[0].files[0].variant == "fp16"
    assert restored.versions[0].thumbnail_url == "https://cdn.example.com/thumb.jpg"
    assert restored.provenance.license == "apache-2.0"
    assert restored.tags == ["tag1"]
