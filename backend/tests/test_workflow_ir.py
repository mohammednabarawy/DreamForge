from dreamforge_workflow_ir import compile_workflow_ir


def test_native_ir_is_deterministic_and_executable():
    graph = {
        "2": {"class_type": "SaveImage", "inputs": {}},
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
        "4": {"class_type": "KSampler", "inputs": {"steps": 10, "cfg": 5, "sampler_name": "euler", "seed": 3}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "a fox"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512}},
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
