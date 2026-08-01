import dreamforge_recipe_discovery as discovery


def test_recipe_from_metadata_preserves_known_values_only():
    recipe = discovery.recipe_from_metadata(
        {
            "Prompt": "portrait",
            "negativePrompt": "blurry",
            "modelName": "model.safetensors",
            "sampler": "euler_a",
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
    assert recipe.seed == 123
    assert recipe.aspect_ratio == "768x1024"
    assert "missing" in recipe.completeness()


def test_recipe_discovery_normalizes_civitai_and_lexica(monkeypatch):
    def fake_get(url, headers=None, timeout=0):
        if "civitai.com" in url:
            return {
                "items": [
                    {
                        "id": 7,
                        "url": "https://images/7.png",
                        "meta": {"prompt": "a fox", "seed": 2, "steps": 12},
                    }
                ],
                "metadata": {"totalItems": 1},
            }
        return {"images": [{"id": "x", "src": "https://images/x.png", "prompt": "a fox", "seed": 3}]}

    monkeypatch.setattr(discovery, "http_get_json", fake_get)
    result = discovery.search_recipe_discovery("fox", limit=4)
    assert result["provider_ok"] == 2
    assert len(result["items"]) == 2
    assert {item["provider"] for item in result["items"]} == {"civitai_images", "lexica"}
    assert all(item["recipe"]["positive_prompt"] == "a fox" for item in result["items"])


def test_recipe_discovery_filters_civitai_prompt(monkeypatch):
    monkeypatch.setattr(
        discovery,
        "http_get_json",
        lambda *args, **kwargs: {"items": [{"id": 1, "url": "x", "meta": {"prompt": "cat"}}]},
    )
    result = discovery.search_recipe_discovery("fox", provider="civitai_images")
    assert result["items"] == []
