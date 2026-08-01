import dreamforge_recipe_discovery as discovery


def test_recipe_from_metadata_preserves_known_values_only():
    recipe = discovery.recipe_from_metadata(
        {
            "Prompt": "portrait",
            "negativePrompt": "blurry",
            "modelName": "model.safetensors",
            "sampler": "Euler a Karras",
            "cfgScale": 5,
            "steps": 18,
            "seed": 123,
            "width": 768,
            "height": 1024,
        },
        provider="lexica",
        source_url="https://lexica.art/prompt/1",
    )
    assert recipe.positive_prompt == "portrait"
    assert recipe.negative_prompt == "blurry"
    assert recipe.model == "model.safetensors"
    assert recipe.sampler == "euler_ancestral"
    assert recipe.settings["scheduler"] == "karras"
    assert recipe.seed == 123
    assert recipe.aspect_ratio == "768x1024"
    assert "missing" in recipe.completeness()


def test_recipe_discovery_normalizes_civitai_and_lexica(monkeypatch):
    requested = []

    def fake_get(url, headers=None, timeout=0):
        requested.append(url)
        if "civitai.com" in url:
            return {
                "items": [
                    {
                        "id": 7,
                        "url": "https://images/7.png",
                        "modelVersionIds": [101, 202],
                        "meta": {"prompt": "a fox", "seed": 2, "steps": 12},
                    }
                ],
                "metadata": {"totalItems": 1, "nextCursor": "next-7"},
            }
        return {"images": [{"id": "x", "src": "https://images/x.png", "prompt": "a fox", "seed": 3}]}

    monkeypatch.setattr(discovery, "http_get_json", fake_get)
    result = discovery.search_recipe_discovery("fox", limit=4)
    assert result["provider_ok"] == 2
    assert len(result["items"]) == 2
    assert {item["provider"] for item in result["items"]} == {"civitai_images", "lexica"}
    assert all(item["recipe"]["positive_prompt"] == "a fox" for item in result["items"])
    assert any("withMeta=true" in url for url in requested)
    assert result["next_cursor"] == "next-7"
    assert result["items"][0]["recipe"]["settings"]["civitai_model_version_ids"] == ["101", "202"]


def test_recipe_discovery_filters_civitai_prompt(monkeypatch):
    monkeypatch.setattr(
        discovery,
        "http_get_json",
        lambda *args, **kwargs: {"items": [{"id": 1, "url": "x", "meta": {"prompt": "cat"}}]},
    )
    result = discovery.search_recipe_discovery("fox", provider="civitai_images")
    assert result["items"] == []


def test_recipe_discovery_uses_cursor_and_requires_prompt(monkeypatch):
    requested = []
    monkeypatch.setattr(
        discovery,
        "http_get_json",
        lambda url, **kwargs: requested.append(url) or {
            "items": [{"id": 1, "url": "x", "width": 640, "height": 480, "meta": {}}],
            "metadata": {},
        },
    )
    result = discovery.search_recipe_discovery(provider="civitai_images", cursor="abc|2")
    assert result["items"] == []
    assert "cursor=abc%7C2" in requested[0]


def test_resolve_civitai_recipe_resources_returns_real_safe_downloads(monkeypatch, tmp_path):
    local_file = tmp_path / "portrait.safetensors"
    local_file.write_bytes(b"installed")

    class FakeRegistry:
        def file_by_sha256(self, sha256):
            return {"local_path": str(local_file)} if sha256 == "ab" * 32 else None

        def close(self):
            pass

    monkeypatch.setattr("dreamforge_asset_registry.AssetRegistry", FakeRegistry)
    monkeypatch.setattr(
        discovery,
        "http_get_json",
        lambda url, **kwargs: {
            "id": 22,
            "modelId": 11,
            "name": "v1",
            "model": {"name": "Portrait Helper", "type": "LORA"},
            "files": [{
                "name": "portrait.safetensors",
                "primary": True,
                "downloadUrl": "https://civitai.com/api/download/models/22",
                "hashes": {"SHA256": "AB" * 32},
            }],
        },
    )
    monkeypatch.setattr("dreamforge_credentials.get_provider_credential", lambda *_args: "token")
    result = discovery.resolve_civitai_recipe_resources({
        "settings": {
            "civitai_model_version_ids": ["22"],
            "civitai_resources": [{"model_version_id": "22", "weight": 0.7}],
        }
    })
    item = result["resources"][0]
    assert item["kind"] == "lora"
    assert item["filename"] == "portrait.safetensors"
    assert item["sha256"] == "ab" * 32
    assert item["source_url"] == "https://civitai.com/models/11?modelVersionId=22"
    assert item["weight"] == 0.7
    assert item["local_engine_name"] == "portrait.safetensors"
    assert item["downloadable"] is True
