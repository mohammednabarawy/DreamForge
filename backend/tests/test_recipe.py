from dreamforge_recipe import (
    DreamForgeRecipe,
    LoRAComponent,
    RECIPE_SCHEMA_VERSION,
    normalize_sampler,
)


def test_normalize_sampler_aliases():
    assert normalize_sampler("DPM++ 2M") == "dpmpp_2m"
    assert normalize_sampler("DPM++ 2M SDE") == "dpmpp_2m_sde"
    assert normalize_sampler("Euler a") == "euler_ancestral"
    assert normalize_sampler("euler") == "euler"
    assert normalize_sampler("UniPC") == "uni_pc"
    assert normalize_sampler("DDIM") == "ddim"
    assert normalize_sampler("dpmpp_sde") == "dpmpp_sde"
    assert normalize_sampler("") is None
    assert normalize_sampler(None) is None


def test_recipe_empty_not_runnable_and_zero_completeness():
    recipe = DreamForgeRecipe()
    assert recipe.is_runnable is False
    report = recipe.completeness()
    assert report["score"] == 0.0
    assert set(report["missing"]) == {
        "model",
        "positive_prompt",
        "sampler",
        "cfg_scale",
        "steps",
        "aspect_ratio",
    }
    assert "never invented" in report["note"]


def test_recipe_complete_recipe_full_score():
    recipe = DreamForgeRecipe(
        model="sd_xl_base.safetensors",
        positive_prompt="a cat",
        sampler="DPM++ 2M",
        cfg_scale=5.0,
        steps=28,
        aspect_ratio="896x704",
    )
    assert recipe.is_runnable is True
    report = recipe.completeness()
    assert report["score"] == 1.0
    assert report["missing"] == []


def test_recipe_missing_model_never_invented():
    recipe = DreamForgeRecipe(
        positive_prompt="a cat",
        sampler="euler",
        cfg_scale=5.0,
        steps=28,
        aspect_ratio="896x704",
    )
    report = recipe.completeness()
    assert recipe.model == ""
    assert "model" in report["missing"]
    assert report["score"] == round(5 / 6, 3)


def test_recipe_never_invents_seed_or_negative():
    recipe = DreamForgeRecipe(
        model="m.safetensors",
        positive_prompt="x",
        sampler="euler",
        cfg_scale=5.0,
        steps=28,
        aspect_ratio="1:1",
    )
    assert recipe.seed is None
    assert recipe.negative_prompt == ""
    report = recipe.completeness()
    assert "seed" not in report["present"]
    assert "negative_prompt" not in report["present"]


def test_recipe_round_trip_preserves_all_fields():
    recipe = DreamForgeRecipe(
        model="flux1-dev.safetensors",
        positive_prompt="  neon city  ",
        negative_prompt=" blurry",
        seed=42,
        sampler="DPM++ 2M SDE",
        cfg_scale=3.5,
        steps=20,
        aspect_ratio="832x1216",
        performance="speed",
        styles=["anime"],
        loras=[LoRAComponent(filename="style.safetensors", weight=0.8)],
        settings={"clip_skip": 1},
        source="civitai_image",
        source_url="https://civitai.com/images/1",
    )
    restored = DreamForgeRecipe.from_dict(recipe.to_dict())
    assert restored == recipe
    assert restored.sampler == "dpmpp_2m_sde"
    assert restored.positive_prompt == "neon city"
    assert restored.negative_prompt == "blurry"
    assert restored.seed == 42
    assert restored.loras[0].weight == 0.8
    assert restored.settings == {"clip_skip": 1}
    assert restored.schema_version == RECIPE_SCHEMA_VERSION


def test_recipe_from_dict_handles_seed_edge_cases():
    assert DreamForgeRecipe.from_dict({"seed": None}).seed is None
    assert DreamForgeRecipe.from_dict({"seed": ""}).seed is None
    assert DreamForgeRecipe.from_dict({"seed": "123"}).seed == 123
    assert DreamForgeRecipe.from_dict({"seed": "oops"}).seed is None


def test_recipe_from_style_recipe_keeps_known_values_only():
    recipe = DreamForgeRecipe.from_style_recipe(
        "concept_art",
        {
            "models": ["hidream_o1_image_dev_mxfp8.safetensors"],
            "prompt_prefix": "concept art of ",
            "performance": "quality",
            "aspect_ratio": "832x1216",
            "styles": ["concept_art"],
            "thumbnail": "ignored.png",
            "seed": 999,  # style recipes shouldn't carry seeds
        },
        prompt="a dragon",
    )
    assert recipe.model == "hidream_o1_image_dev_mxfp8.safetensors"
    assert recipe.positive_prompt == "concept art of a dragon"
    assert recipe.source == "style"
    assert recipe.seed is None
    assert "thumbnail" not in recipe.settings
    assert recipe.settings.get("seed") is None


def test_recipe_lora_dict_normalization():
    recipe = DreamForgeRecipe.from_dict(
        {
            "loras": [{"filename": "a.safetensors", "weight": "0.5"}],
            "styles": ["", "anime", None],
        }
    )
    assert isinstance(recipe.loras[0], LoRAComponent)
    assert recipe.loras[0].weight == 0.5
    assert recipe.styles == ["anime"]
