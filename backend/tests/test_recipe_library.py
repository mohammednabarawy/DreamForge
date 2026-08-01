import json

import dreamforge_recipe_library as library


def test_save_recipe_writes_managed_library_file(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "RECIPE_LIBRARY_ROOT", tmp_path / "recipes")

    result = library.save_recipe(
        {"schema_version": "2.0", "model": "model.safetensors", "positive_prompt": "fox"},
        "civitai:42",
    )

    assert result["ok"] is True
    payload = json.loads((tmp_path / "recipes" / result["filename"]).read_text(encoding="utf-8"))
    assert payload["library_id"] == "civitai:42"
    assert payload["positive_prompt"] == "fox"
