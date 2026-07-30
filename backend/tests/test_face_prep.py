"""Tests for face prep module and identity verification report enrichment."""

from PIL import Image
from dreamforge_face_prep import preprocess_reference_face


def test_preprocess_reference_face(tmp_path):
    img_path = tmp_path / "person.png"
    img = Image.new("RGB", (600, 600), (120, 140, 160))
    img.save(img_path)

    res = preprocess_reference_face(img_path, output_path=tmp_path / "face_out.png")
    assert res["ok"] is True
    assert res["cropped_path"] is not None
    assert (tmp_path / "face_out.png").exists()
