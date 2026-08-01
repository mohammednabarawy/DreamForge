import hashlib

import pytest

from dreamforge_asset_registry import (
    AssetRegistry,
    AssetResolver,
    AssetScanner,
    kind_for_ext,
    sha256_of_file,
)
from dreamforge_assets import (
    AssetFile,
    AssetKind,
    AssetVersion,
    DreamForgeAsset,
    Provenance,
)


@pytest.fixture()
def registry(tmp_path):
    reg = AssetRegistry(db_path=tmp_path / "test.db")
    yield reg
    reg.close()


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().lower()


def _provider_asset(asset_id, name, sha256, *, version="v1"):
    return DreamForgeAsset(
        id=asset_id,
        name=name,
        kind=AssetKind.CHECKPOINT,
        architecture="sdxl",
        versions=[
            AssetVersion(
                id=version,
                name=version,
                files=[AssetFile(filename=name, sha256=sha256)],
            )
        ],
        provenance=Provenance(provider="civitai", provider_asset_id=asset_id),
    )


def test_sha256_of_file_matches_expected():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "model.safetensors"
        path.write_bytes(b"hello world")
        assert sha256_of_file(path) == _digest(b"hello world")


def test_upsert_and_get_asset_round_trip(registry):
    asset = _provider_asset("civitai:123", "My Model", "a" * 64)
    asset_id = registry.upsert_asset(asset)
    assert asset_id == "civitai:123"
    restored = registry.get_asset("civitai:123")
    assert restored.name == "My Model"
    assert restored.kind is AssetKind.CHECKPOINT
    assert restored.architecture == "sdxl"


def test_upsert_requires_identity(registry):
    with pytest.raises(ValueError):
        registry.upsert_asset(DreamForgeAsset(name="No ID"))


def test_list_and_search_assets(registry):
    registry.upsert_asset(_provider_asset("civitai:1", "Juggernaut XL", "b" * 64))
    registry.upsert_asset(_provider_asset("civitai:2", "DreamShaper", "c" * 64))
    registry.upsert_asset(_provider_asset("hf:3", "Flux Dev", "d" * 64))
    assert registry.count_assets() == 3
    assert len(registry.list_assets()) == 3
    by_kind = registry.list_assets(kind="checkpoint")
    assert len(by_kind) == 3
    hits = registry.search_assets("dream")
    assert [a.name for a in hits] == ["DreamShaper"]


def test_same_sha256_across_providers_deduplicates_files(registry):
    shared = "e" * 64
    registry.upsert_asset(_provider_asset("civitai:1", "Model A", shared))
    registry.upsert_asset(_provider_asset("hf:1", "Model B", shared))
    record = registry.file_by_sha256(shared)
    assert record is not None
    assert record["filename"] in ("Model A", "Model B")
    # Both logical assets resolve to the same physical identity.
    assets = registry.assets_by_sha256(shared)
    assert {a.id for a in assets} == {"civitai:1", "hf:1"}


def test_register_local_file_computes_sha256(registry, tmp_path):
    path = tmp_path / "flux1-dev-fp8.safetensors"
    payload = b"\x00" * 4096
    path.write_bytes(payload)
    asset = registry.register_local_file(path, kind=AssetKind.CHECKPOINT)
    assert asset.architecture == "flux"
    assert asset.primary_file.sha256 == _digest(payload)
    record = registry.file_by_sha256(asset.primary_file.sha256)
    assert record["local_path"] == str(path.resolve())


def test_mark_file_local_associates_path(registry):
    asset = _provider_asset("civitai:9", "M", "f" * 64)
    registry.upsert_asset(asset)
    registry.mark_file_local("f" * 64, "C:\\models\\m.safetensors")
    record = registry.file_by_sha256("f" * 64)
    assert record["local_path"] == "C:\\models\\m.safetensors"


def test_delete_asset_removes_rows(registry):
    registry.upsert_asset(_provider_asset("civitai:1", "M", "g" * 64))
    registry.delete_asset("civitai:1")
    assert registry.get_asset("civitai:1") is None
    assert registry.count_assets() == 0
    assert registry.file_by_sha256("g" * 64) is None


def test_kind_for_ext_fallback():
    assert kind_for_ext(".safetensors") is AssetKind.CHECKPOINT
    assert kind_for_ext(".gguf") is AssetKind.CHECKPOINT
    assert kind_for_ext(".patch") is AssetKind.INPAINT
    assert kind_for_ext(".txt") is AssetKind.UNKNOWN


def test_scanner_registers_files_and_reuses_snapshot(registry, tmp_path):
    folder = tmp_path / "models"
    folder.mkdir()
    f1 = folder / "a.safetensors"
    f1.write_bytes(b"data-a" * 256)
    scanner = AssetScanner(registry, snapshot_path=tmp_path / "snap.json")

    first = scanner.scan_folder(folder, kind=AssetKind.CHECKPOINT)
    assert first.scanned == 1
    assert first.registered == 1
    assert first.unchanged == 0
    assert len(first.assets) == 1

    second = AssetScanner(registry, snapshot_path=tmp_path / "snap.json")
    rerun = second.scan_folder(folder, kind=AssetKind.CHECKPOINT)
    assert rerun.scanned == 1
    assert rerun.registered == 0
    assert rerun.unchanged == 1

    # File change triggers re-registration.
    f1.write_bytes(b"data-a-changed" * 256)
    third = AssetScanner(registry, snapshot_path=tmp_path / "snap.json")
    changed = third.scan_folder(folder, kind=AssetKind.CHECKPOINT)
    assert changed.registered == 1


def test_scanner_force_hash_rehashes(registry, tmp_path):
    folder = tmp_path / "models"
    folder.mkdir()
    (folder / "a.safetensors").write_bytes(b"x" * 512)
    scanner = AssetScanner(registry, snapshot_path=tmp_path / "snap.json")
    first = scanner.scan_folder(folder, kind=AssetKind.CHECKPOINT)
    assert first.registered == 1
    forced = scanner.scan_folder(folder, kind=AssetKind.CHECKPOINT, force_hash=True)
    assert forced.registered == 1
    assert forced.unchanged == 0


def test_scanner_ignores_non_model_extensions(registry, tmp_path):
    folder = tmp_path / "models"
    folder.mkdir()
    (folder / "notes.txt").write_text("hello")
    (folder / "thumb.png").write_bytes(b"png")
    scanner = AssetScanner(registry, snapshot_path=tmp_path / "snap.json")
    result = scanner.scan_folder(folder, kind=AssetKind.CHECKPOINT)
    assert result.scanned == 0
    assert result.errors == []


def test_scanner_missing_folder_reports_error(registry, tmp_path):
    scanner = AssetScanner(registry, snapshot_path=tmp_path / "snap.json")
    result = scanner.scan_folder(tmp_path / "nope", kind=AssetKind.CHECKPOINT)
    assert result.errors and "missing folder" in result.errors[0]


def _local_asset(asset_id, sha256, local_path):
    return DreamForgeAsset(
        id=asset_id,
        name="M",
        kind=AssetKind.CHECKPOINT,
        versions=[
            AssetVersion(
                id="v1",
                files=[AssetFile(filename="m.safetensors", sha256=sha256, local_path=local_path)],
            )
        ],
        provenance=Provenance(provider="civitai", provider_asset_id=asset_id),
    )


def test_resolver_local_path(registry, tmp_path):
    local_file = tmp_path / "m.safetensors"
    local_file.write_bytes(b"data" * 128)
    registry.upsert_asset(_local_asset("civitai:1", "h" * 64, str(local_file)))
    result = AssetResolver(registry).resolve(registry.get_asset("civitai:1"))
    assert result["status"] == "local"
    assert result["path"] == str(local_file)


def test_resolver_needs_download(registry):
    asset = DreamForgeAsset(
        id="civitai:2",
        name="M2",
        kind=AssetKind.CHECKPOINT,
        versions=[
            AssetVersion(
                id="v1",
                files=[AssetFile(filename="m.safetensors", sha256="i" * 64, download_url="https://x/m")],
            )
        ],
        provenance=Provenance(provider="civitai", provider_asset_id="2"),
    )
    registry.upsert_asset(asset)
    result = AssetResolver(registry).resolve(registry.get_asset("civitai:2"))
    assert result["status"] == "needs_download"
    assert result["download_url"] == "https://x/m"


def test_resolver_unknown_when_no_asset_or_no_file():
    assert AssetResolver(AssetRegistry.__new__(AssetRegistry)).resolve(None)["status"] == "unknown"


def test_resolver_prefers_variant(registry, tmp_path):
    local_file = tmp_path / "m_q4_k_m.gguf"
    local_file.write_bytes(b"gguf" * 128)
    asset = DreamForgeAsset(
        id="civitai:3",
        name="M3",
        kind=AssetKind.CHECKPOINT,
        versions=[
            AssetVersion(
                id="v1",
                files=[
                    AssetFile(filename="m_fp8.safetensors", sha256="j" * 64, variant="fp8"),
                    AssetFile(
                        filename="m_q4_k_m.gguf",
                        sha256="k" * 64,
                        variant="q4_k_m",
                        local_path=str(local_file),
                    ),
                ],
            )
        ],
        provenance=Provenance(provider="civitai", provider_asset_id="3"),
    )
    registry.upsert_asset(asset)
    result = AssetResolver(registry).resolve(
        registry.get_asset("civitai:3"), prefer_variant="q4_k_m"
    )
    assert result["status"] == "local"
    assert result["path"] == str(local_file)
    assert result["filename"] == "m_q4_k_m.gguf"
