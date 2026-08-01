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


def test_list_and_delete_recipes(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "RECIPE_LIBRARY_ROOT", tmp_path / "recipes")
    saved = library.save_recipe({"model": "m.safetensors", "positive_prompt": "fox"}, "fox")
    listed = library.list_recipes()
    assert [item["filename"] for item in listed["items"]] == [saved["filename"]]
    assert library.delete_recipe(saved["filename"])["ok"] is True
    assert library.delete_recipe("../outside.json")["error"] == "invalid_recipe_filename"
