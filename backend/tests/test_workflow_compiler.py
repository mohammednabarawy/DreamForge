from dreamforge_workflow_compiler import compile_workflow_recipe


def test_native_graph_compiles_to_recipe():
    graph = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "a red fox"}},
        "3": {"class_type": "KSampler", "inputs": {"steps": 24, "cfg": 6, "sampler_name": "euler", "seed": 4}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024}},
        "5": {"class_type": "SaveImage", "inputs": {"images": ["3", 0]}},
    }
    result = compile_workflow_recipe(graph)
    assert result["can_recreate"] is True
    assert result["recipe"]["model"] == "model.safetensors"
    assert result["recipe"]["positive_prompt"] == "a red fox"
    assert result["recipe"]["aspect_ratio"] == "1024x1024"


def test_comfy_only_graph_cannot_compile():
    result = compile_workflow_recipe({"1": {"class_type": "CustomMagic", "inputs": {}}})
    assert result["can_recreate"] is False
    assert result["report"]["state"] == "COMFY_ONLY"


def test_native_graph_with_unbound_sampler_is_blocked():
    result = compile_workflow_recipe({
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "a fox"}},
        "3": {"class_type": "KSampler", "inputs": {}},
        "4": {"class_type": "SaveImage", "inputs": {}},
    })
    assert result["report"]["state"] == "NATIVE"
    assert result["can_recreate"] is False
    assert "sampler" in result["missing"]
