"""Regression check for Krea edit routing, grounded references, and dependency failures."""
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dreamforge_comfy_models import ComfyModelResolutionError, resolve_comfy_model_loader_args
from dreamforge_comfy_workflows import comfy_krea2_edit
from dreamforge_generation import _build_comfy_prompt_graph
from dreamforge_identity import apply_identity_to_job
from dreamforge_task_router import apply_task_routing
from dreamforge_workflow_routing import resolve_comfy_workflow_mode, resolve_input_routing

MODEL = {
    "name": "krea2_turbo.safetensors", "engine_name": "krea2_turbo.safetensors",
    "relative_path": "krea2_turbo.safetensors", "family": "krea2", "category": "diffusion_models",
}
SETTINGS = {"width": 768, "height": 1024, "steps": 8, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple"}
LORA = "krea2_identity_edit_v1_2.safetensors"


def test_krea2_edit_route_and_graph():
    for stale_type in ("auto", "kontext", "qwen_edit", "img2img"):
        settings = {"model": MODEL["name"], "input_image": "source.png", "edit_type": stale_type,
                    "steps": 13, "cfg_scale": 2.5, "width": 768, "height": 1024}
        result = apply_task_routing(settings, "edit", [MODEL], user_picked_model=True).patch
        assert result["model"] == MODEL["name"] and result["edit_type"] == "auto"
        assert (result["steps"], result["cfg_scale"], result["width"], result["height"]) == (13, 2.5, 768, 1024)
        job = SimpleNamespace(**result, workflow_mode="edit", studio_mode="edit", preserve_character=True)
        apply_identity_to_job(job, model_family="krea2")
        assert job.model == MODEL["name"] and job.reference_role == "source_edit"
        route = resolve_input_routing(job, model=MODEL, model_family="krea2", studio_mode="edit")
        mode = resolve_comfy_workflow_mode(route, model=MODEL, model_family="krea2", input_filename="source.png")
        assert mode == "krea2_edit"
        for refs in ([], ["subject.png"]):
            graph, _ = _build_comfy_prompt_graph(
                job=job, mode=mode, model=MODEL, model_family="krea2", settings=SETTINGS,
                prompt="Change the shirt to black", negative="unused", seed=2, edit_strength=0.3,
                cn_upscale="", input_filename="source.png", mask_filename=None,
                reference_stitch_filename="must-not-use-collage.png", grow_mask_by=0,
                krea2_reference_filenames=refs,
            )
            patch = next(n["inputs"] for n in graph.values() if n["class_type"] == "Krea2EditModelPatch")
            sampler = next(n["inputs"] for n in graph.values() if n["class_type"] == "KSampler")
            assert patch["target_latent"] == sampler["latent_image"]
            assert graph[sampler["latent_image"][0]]["class_type"] == "EmptySD3LatentImage"
            assert sampler["denoise"] == 1 and sampler["steps"] == SETTINGS["steps"]
            assert graph[sampler["negative"][0]]["inputs"]["prompt"] == ""
            positive = graph[sampler["positive"][0]]["inputs"]
            assert positive["image"] == patch["source_image"] and positive["grounding_px"] == 768
            assert ("image_b" in positive) == bool(refs)
            assert ("source_latent_b" in patch) == bool(refs)
            assert ("source_image_b" in patch) == bool(refs)
            if refs:
                assert positive["image_b"] == patch["source_image_b"] != patch["source_image"]
            assert [n["inputs"]["image"] for n in graph.values() if n["class_type"] == "LoadImage"] == ["source.png", *refs]
            for node in graph.values():
                for value in node["inputs"].values():
                    if isinstance(value, list):
                        assert value[0] in graph  # No implicit broadcast links or missing nodes.
    for workflow_mode, edit_type, expected in (("generate", "auto", "img2img"), (None, "img2img", "img2img")):
        job = SimpleNamespace(input_image="source.png", reference_role="restyle", workflow_mode=workflow_mode, edit_type=edit_type)
        route = resolve_input_routing(job, model=MODEL, model_family="krea2")
        assert resolve_comfy_workflow_mode(route, model=MODEL, model_family="krea2", input_filename="source.png") == expected


def test_krea2_edit_lora_and_input_validation():
    args = {**MODEL, "ckpt_name": MODEL["name"], "images": ["source.png"]}
    graph = comfy_krea2_edit({**args, "loras": [{"name": LORA, "weight": 0.9}]})
    edit_loras = [n for n in graph.values() if n["class_type"] == "LoraLoaderModelOnly"]
    assert len(edit_loras) == 1 and edit_loras[0]["inputs"]["strength_model"] == 0.9
    for extra in ({"images": []}, {"images": ["a", "b", "c"]}, {"loras": [{"name": "krea2_identity_edit_v1_1.safetensors"}]}):
        try:
            comfy_krea2_edit({**args, **extra})
        except ValueError:
            pass
        else:
            raise AssertionError(f"Invalid Krea edit accepted: {extra}")


def test_krea2_edit_requires_lora_only_for_edit(monkeypatch):
    import dreamforge_comfy_models as loaders
    monkeypatch.setattr(loaders, "check_model_dependencies", lambda model: [])
    monkeypatch.setattr(loaders, "_krea2_companion_basenames_on_disk", lambda family: {
        "clip": "qwen3vl_4b_fp8_scaled.safetensors", "vae": "qwen_image_vae.safetensors",
    })
    info = {
        "UNETLoader": {"input": {"required": {"unet_name": [[MODEL["name"]]]}}},
        "CLIPLoader": {"input": {"required": {"clip_name": [["qwen3vl_4b_fp8_scaled.safetensors"]], "type": [["krea2"]]}}},
        "VAELoader": {"input": {"required": {"vae_name": [["qwen_image_vae.safetensors"]]}}},
        "LoraLoaderModelOnly": {"input": {"required": {"lora_name": [[]]}}},
    }
    client = SimpleNamespace(object_info=lambda: info)
    assert "krea2_edit_lora" not in resolve_comfy_model_loader_args(client, model=MODEL, model_family="krea2")
    try:
        resolve_comfy_model_loader_args(client, model=MODEL, model_family="krea2", krea2_edit=True)
    except ComfyModelResolutionError as exc:
        assert LORA in str(exc)
    else:
        raise AssertionError("Missing edit LoRA must fail before sampling")
    info["LoraLoaderModelOnly"]["input"]["required"]["lora_name"] = [["edits/" + LORA]]
    assert resolve_comfy_model_loader_args(client, model=MODEL, model_family="krea2", krea2_edit=True)["krea2_edit_lora"] == "edits/" + LORA


def test_unsupported_int8_error_names_working_krea_alternative():
    from dreamforge_errors import from_exception
    for exc in (KeyError("int8_tensorwise"), RuntimeError("Comfy execution failed: KeyError: 'int8_tensorwise'")):
        payload = from_exception(exc)
        assert payload["code"] == "unsupported_model_format"
        assert "krea2TurboFP8" in " ".join(payload["suggestions"])
