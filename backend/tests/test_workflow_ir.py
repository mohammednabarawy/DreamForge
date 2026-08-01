from dreamforge_workflow_ir import compile_workflow_ir


def test_native_ir_is_deterministic_and_executable():
    graph = {
        "2": {"class_type": "SaveImage", "inputs": {"images": ["6", 0]}},
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
        "4": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["3", 0], "negative": ["7", 0], "latent_image": ["5", 0], "steps": 10, "cfg": 5, "sampler_name": "euler", "scheduler": "normal", "seed": 3}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "a fox", "clip": ["1", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "blur", "clip": ["1", 1]}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["1", 2]}},
    }
    result = compile_workflow_ir(graph, source="local.json")
    assert result["can_execute"] is True
    assert result["version"] == "1.0"
    assert result["nodes"] == sorted(result["nodes"])
    assert result["recipe"]["source_url"] == "local.json"


def test_unknown_ir_is_fail_closed():
    result = compile_workflow_ir({"1": {"class_type": "CustomMagic", "inputs": {}}})
    assert result["can_execute"] is False
    assert result["report"]["state"] == "COMFY_ONLY"
