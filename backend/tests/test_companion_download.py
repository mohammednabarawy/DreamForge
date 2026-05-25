from dreamforge_cli_inventory import companion_file_present
from dreamforge_companion_download import enrich_missing_dependency


def test_enrich_flux_vae():
    entry = {
        "id": "vae_flux_ae",
        "relative": "vae/ae.safetensors",
        "expected_path": "/models/vae/ae.safetensors",
    }
    out = enrich_missing_dependency(entry)
    assert out["url"]
    assert "black-forest-labs/FLUX.1-schnell" in out["url"]
    assert out.get("requires_hf_token") is True
    assert out["category"] == "vae"
    assert out["filename"] == "ae.safetensors"


def test_enrich_flux_t5_fp8_url():
    entry = {
        "id": "clip_t5_flux_fp8",
        "relative": "text_encoders/t5xxl_fp8_e4m3fn.safetensors",
    }
    out = enrich_missing_dependency(entry)
    assert "comfyanonymous/flux_text_encoders" in out["url"]
    assert out["url"].endswith("t5xxl_fp8_e4m3fn.safetensors")
    assert out["category"] == "text_encoders"
    assert "Comfy-Org/flux1-dev" not in out["url"]


def test_enrich_flux_clip_l_url():
    entry = {"id": "clip_l_flux", "relative": "clip/clip_l.safetensors"}
    out = enrich_missing_dependency(entry)
    assert "comfyanonymous/flux_text_encoders" in out["url"]
    assert out["url"].endswith("clip_l.safetensors")


def test_companion_present_clip_folder_t5(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "dreamforge_cli_inventory.MODELS_ROOT",
        tmp_path,
    )
    clip_dir = tmp_path / "clip"
    clip_dir.mkdir(parents=True)
    t5 = clip_dir / "t5xxl_fp8_e4m3fn.safetensors"
    t5.write_bytes(b"x" * (5 * 1024 * 1024))
    req = {
        "id": "clip_t5_flux_fp8",
        "relative": "text_encoders/t5xxl_fp8_e4m3fn.safetensors",
    }
    assert companion_file_present(req, min_bytes=1024 * 1024)


def test_enrich_unknown_id_has_no_url():
    entry = {"id": "unknown", "relative": "vae/foo.safetensors"}
    out = enrich_missing_dependency(entry)
    assert not out.get("url")
