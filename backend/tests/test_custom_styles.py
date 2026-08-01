import json

import dreamforge_custom_styles as custom_styles


def test_import_fooocus_mapping_is_normalized_and_persistent(tmp_path, monkeypatch):
    path = tmp_path / "custom_styles.json"
    monkeypatch.setattr(custom_styles, "CUSTOM_STYLES_PATH", path)

    result = custom_styles.import_fooocus_styles(
        {
            "Portrait": {
                "prompt": "{prompt}, soft studio light",
                "negative_prompt": "blurry",
                "base_model": "SDXL",
            }
        }
    )

    assert result["ok"] is True
    assert result["count"] == 1
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved[0]["original_name"] == "Portrait"
    assert saved[0]["architecture"] == "SDXL"
    assert saved[0]["offline"] is True
    assert custom_styles.list_custom_styles()[0]["id"].startswith("custom_portrait_")


def test_import_fooocus_rejects_empty_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(custom_styles, "CUSTOM_STYLES_PATH", tmp_path / "styles.json")
    try:
        custom_styles.import_fooocus_styles([])
    except ValueError as exc:
        assert "No style entries" in str(exc)
    else:
        raise AssertionError("empty style payload should fail")
