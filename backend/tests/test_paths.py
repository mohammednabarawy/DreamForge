from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import pytest

from _paths import OUTPUTS_ROOT, PROJECT_ROOT
from dreamforge_paths import resolve_image_path, resolve_image_path_or_raise


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    image = tmp_path / "ref.png"
    image.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return image


def test_resolve_image_path_absolute(sample_image: Path):
    assert resolve_image_path(str(sample_image)) == sample_image.resolve()


def test_resolve_image_path_relative_to_project_root(tmp_path: Path):
    rel_dir = PROJECT_ROOT / "outputs" / "_path_test"
    rel_dir.mkdir(parents=True, exist_ok=True)
    target = rel_dir / "ref.png"
    target.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    try:
        rel = Path("outputs") / "_path_test" / "ref.png"
        assert resolve_image_path(str(rel)) == target.resolve()
    finally:
        target.unlink(missing_ok=True)
        rel_dir.rmdir()


def test_resolve_image_path_outputs_segment(sample_image: Path):
    session_dir = OUTPUTS_ROOT / "test-session"
    session_dir.mkdir(parents=True, exist_ok=True)
    target = session_dir / "photo.png"
    target.write_bytes(sample_image.read_bytes())
    try:
        rel = Path("outputs") / "test-session" / "photo.png"
        assert resolve_image_path(str(rel)) == target.resolve()
    finally:
        target.unlink(missing_ok=True)
        session_dir.rmdir()


def test_resolve_image_path_missing():
    assert resolve_image_path("outputs/does-not-exist/ref.png") is None


def test_resolve_image_path_or_raise(sample_image: Path):
    assert resolve_image_path_or_raise(str(sample_image)) == sample_image.resolve()


def test_resolve_image_path_or_raise_raises():
    with pytest.raises(FileNotFoundError):
        resolve_image_path_or_raise("missing/ref.png")
