"""Tests for dreamforge_model_downloader."""

from pathlib import Path
from dreamforge_model_downloader import (
    parse_filename_from_url,
    resolve_category_folder,
    verify_sha256,
)


def test_parse_filename_from_url():
    assert parse_filename_from_url("https://huggingface.co/repo/resolve/main/model.safetensors") == "model.safetensors"
    assert parse_filename_from_url("https://civitai.com/api/download/models/123456") == "downloaded_model.safetensors"
    
    headers = {"content-disposition": 'attachment; filename="custom_name.safetensors"'}
    assert parse_filename_from_url("https://example.com/file", headers) == "custom_name.safetensors"


def test_resolve_category_folder():
    folder = resolve_category_folder("checkpoints")
    assert folder.name == "checkpoints"
    assert folder.exists()


def test_verify_sha256(tmp_path):
    dummy_file = tmp_path / "test.bin"
    dummy_file.write_bytes(b"hello dreamforge")
    
    import hashlib
    expected = hashlib.sha256(b"hello dreamforge").hexdigest()
    assert verify_sha256(dummy_file, expected) is True
    assert verify_sha256(dummy_file, "badhash") is False
