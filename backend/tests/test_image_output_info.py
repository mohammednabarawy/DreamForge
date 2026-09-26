from PIL import Image

from dreamforge_studio_bridge import cmd_inspect_image_file


def test_inspect_image_file_reports_real_png_alpha(tmp_path):
    path = tmp_path / "result.png"
    Image.new("RGBA", (12, 8), (255, 0, 0, 0)).save(path)
    assert cmd_inspect_image_file({"path": str(path)}) == {
        "ok": True, "width": 12, "height": 8, "format": "PNG", "transparent": True,
    }
    Image.new("RGB", (12, 8), (255, 0, 0)).save(path)
    assert cmd_inspect_image_file({"path": str(path)})["transparent"] is False
    Image.new("RGBA", (12, 8), (255, 0, 0, 208)).save(path)
    assert cmd_inspect_image_file({"path": str(path)})["transparent"] is False
