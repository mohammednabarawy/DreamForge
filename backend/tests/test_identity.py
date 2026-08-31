"""Tests for modern identity preservation routing."""

from types import SimpleNamespace

import pytest

from dreamforge_identity import (
    apply_identity_to_job,
    build_identity_retry_params,
    faceid_assets_available,
    identity_intent_from_prompt,
    is_identity_preservation_job,
    normalize_identity_mode,
    resolve_identity_route,
    verify_identity_outputs,
)


def test_normalize_identity_mode_maps_legacy_faceid():
    assert normalize_identity_mode("faceid") == "preserve_face"
    assert normalize_identity_mode("preserve_face") == "preserve_face"
    assert normalize_identity_mode("ipadapter_faceid") == "ipadapter_faceid"
    assert normalize_identity_mode("bogus") is None


def test_is_identity_preservation_job():
    assert is_identity_preservation_job(SimpleNamespace(preserve_character=True)) is True
    assert is_identity_preservation_job(SimpleNamespace(face_preservation=True)) is True
    assert is_identity_preservation_job(SimpleNamespace(identity_mode="faceid")) is True
    assert is_identity_preservation_job(SimpleNamespace(prompt="same person in a forest")) is True
    assert is_identity_preservation_job(SimpleNamespace()) is False


def test_identity_intent_from_prompt():
    assert identity_intent_from_prompt("Use the reference face in a game card") is True
    assert identity_intent_from_prompt("A dramatic city skyline") is False


def test_resolve_identity_requires_reference():
    job = SimpleNamespace(preserve_character=True)
    plan = resolve_identity_route(job)
    assert plan["route"] == "invalid"


def test_resolve_identity_kontext_when_available(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_identity._pick_kontext_checkpoint",
        lambda: "flux1-dev-kontext_fp8_scaled.safetensors",
    )
    job = SimpleNamespace(
        preserve_character=True,
        input_image="/tmp/face.png",
        identity_mode="preserve_face",
    )
    plan = resolve_identity_route(job)
    assert plan["route"] == "kontext"
    assert plan["model"] == "flux1-dev-kontext_fp8_scaled.safetensors"


def test_faceid_assets_gated(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_workflow_planner.custom_node_pack_present",
        lambda _pack: False,
    )
    monkeypatch.setattr(
        "dreamforge_identity._pick_faceid_model",
        lambda: None,
    )
    assets = faceid_assets_available()
    assert assets["ok"] is False
    assert "ipadapter_faceid_model" in assets["missing"]


def test_faceid_requested_falls_back_without_assets(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_identity.faceid_assets_available",
        lambda: {"ok": False, "missing": ["ipadapter_faceid_model"]},
    )
    monkeypatch.setattr(
        "dreamforge_identity._pick_kontext_checkpoint",
        lambda: "flux1-dev-kontext_fp8_scaled.safetensors",
    )
    job = SimpleNamespace(
        preserve_character=True,
        reference_image="/tmp/face.png",
        identity_mode="ipadapter_faceid",
    )
    plan = resolve_identity_route(job)
    assert plan["route"] == "kontext"
    assert "notice" in plan


def test_apply_identity_kontext_patch(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_identity.resolve_identity_route",
        lambda job, **kwargs: {
            "route": "kontext",
            "reference_image": "/tmp/face.png",
            "model": "flux1-dev-kontext_fp8_scaled.safetensors",
        },
    )
    job = SimpleNamespace(preserve_character=True, input_image="/tmp/face.png")
    apply_identity_to_job(job)
    assert job.reference_role == "image_prompt"
    assert job.edit_type == "kontext"
    assert job.identity_mode == "preserve_face"
    assert job.face_preservation is True
    assert job.model == "flux1-dev-kontext_fp8_scaled.safetensors"


def test_apply_identity_preserves_custom_edit_workflow(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_identity.resolve_identity_route",
        lambda job, **kwargs: {
            "route": "kontext",
            "reference_image": "/tmp/face.png",
            "model": "flux1-dev-kontext_fp8_scaled.safetensors",
        },
    )
    job = SimpleNamespace(
        studio_mode="edit",
        custom_tool_id="legacy_identity_workflow",
        preserve_character=True,
        input_image="/tmp/face.png",
    )
    apply_identity_to_job(job)
    assert job.reference_role == "source_edit"
    assert job.edit_type == "kontext"
    assert getattr(job, "workflow_mode", None) in (None, "")


def test_apply_identity_skips_when_vary_active():
    job = SimpleNamespace(
        preserve_character=True,
        input_image="/tmp/face.png",
        vary_amount="subtle",
    )
    patch = apply_identity_to_job(job)
    assert patch == {}
    assert not hasattr(job, "edit_type") or job.edit_type is None


def test_apply_identity_faceid_route(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_identity.resolve_identity_route",
        lambda job, **kwargs: {
            "route": "ipadapter_faceid",
            "reference_image": "/tmp/face.png",
            "ipadapter_faceid_model": "ip-adapter-faceid_sdxl.bin",
            "ok": True,
        },
    )
    job = SimpleNamespace(
        preserve_character=True,
        reference_image="/tmp/face.png",
        identity_mode="ipadapter_faceid",
    )
    apply_identity_to_job(job)
    assert job.workflow_mode == "ipadapter_faceid"
    assert job.identity_mode == "ipadapter_faceid"
    assert job.reference_role == "image_prompt"


def test_verify_identity_uses_selected_reference_face(monkeypatch):
    import numpy as np

    faces = {
        "/ref.png": [
            {"embedding": np.array([1.0, 0.0]), "area": 100.0},
            {"embedding": np.array([0.0, 1.0]), "area": 80.0},
        ],
        "/out.png": [{"embedding": np.array([0.0, 1.0]), "area": 100.0}],
    }
    monkeypatch.setattr("dreamforge_identity._face_embeddings", lambda path: faces[path])
    job = SimpleNamespace(
        identity_verify=True,
        _identity_reference_path="/ref.png",
        references=[{"path": "/ref.png", "face_index": 1}],
        identity_similarity_threshold=0.35,
    )
    result = verify_identity_outputs(job, ["/out.png"])
    assert result["status"] == "passed"
    assert result["score"] == 1.0


def test_identity_retry_is_single_and_uses_sdxl_faceid(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_identity.faceid_assets_available",
        lambda: {"ok": True, "missing": [], "ipadapter_faceid_model": "faceid.bin"},
    )
    monkeypatch.setattr("dreamforge_identity._pick_faceid_checkpoint", lambda: "sdxl.safetensors")
    job = SimpleNamespace(
        identity_retry=True,
        identity_mode="preserve_face",
        _identity_reference_path="/ref.png",
    )
    params, plan = build_identity_retry_params(
        job,
        {"prompt": "same person"},
        {"status": "failed", "score": 0.2},
    )
    assert plan["eligible"] is True
    assert params["model"] == "sdxl.safetensors"
    assert params["identity_retry_attempted"] is True
    assert params["_identity_retry_internal"] is True

    job.identity_retry_attempted = True
    params, plan = build_identity_retry_params(job, {}, {"status": "failed"})
    assert params is None
    assert plan["reason"] == "retry already attempted"


def test_pick_faceid_checkpoint_matches_sdxl_by_name(monkeypatch):
    """_pick_faceid_checkpoint must find an SDXL checkpoint from the real inventory
    shape (no 'family' or 'gallery' keys)."""
    from dreamforge_identity import _pick_faceid_checkpoint

    fake_inventory = {
        "models_root": "/models",
        "categories": {
            "checkpoints": [
                {
                    "name": "haveallsdxlInSFW_v40DMD2.safetensors",
                    "stem": "haveallsdxlInSFW_v40DMD2",
                    "relative_path": "haveallsdxlInSFW_v40DMD2.safetensors",
                    "path": "/models/checkpoints/haveallsdxlInSFW_v40DMD2.safetensors",
                    "size_mb": 6600.0,
                },
            ],
        },
    }
    import dreamforge_cli_inventory
    monkeypatch.setattr(
        "dreamforge_cli_inventory.list_model_inventory",
        lambda: fake_inventory,
    )
    result = _pick_faceid_checkpoint()
    assert result is not None
    assert "sdxl" in result.lower() or "haveall" in result.lower()


def test_pick_faceid_checkpoint_fallback_by_size(monkeypatch):
    """When no checkpoint has 'sdxl' in the name, the size-based fallback
    should pick a large-enough checkpoint."""
    from dreamforge_identity import _pick_faceid_checkpoint

    fake_inventory = {
        "models_root": "/models",
        "categories": {
            "checkpoints": [
                {
                    "name": "myCustomModel_v2.safetensors",
                    "stem": "myCustomModel_v2",
                    "relative_path": "myCustomModel_v2.safetensors",
                    "path": "/models/checkpoints/myCustomModel_v2.safetensors",
                    "size_mb": 6600.0,
                },
                {
                    "name": "tinyModel.safetensors",
                    "stem": "tinyModel",
                    "relative_path": "tinyModel.safetensors",
                    "path": "/models/checkpoints/tinyModel.safetensors",
                    "size_mb": 500.0,
                },
            ],
        },
    }
    monkeypatch.setattr(
        "dreamforge_cli_inventory.list_model_inventory",
        lambda: fake_inventory,
    )
    result = _pick_faceid_checkpoint()
    assert result == "myCustomModel_v2.safetensors"


def test_pick_faceid_checkpoint_excludes_refiner(monkeypatch):
    """Refiner checkpoints must be skipped even if named 'sdxl'."""
    from dreamforge_identity import _pick_faceid_checkpoint

    fake_inventory = {
        "models_root": "/models",
        "categories": {
            "checkpoints": [
                {
                    "name": "sdxl_refiner_1.0.safetensors",
                    "stem": "sdxl_refiner_1.0",
                    "relative_path": "sdxl_refiner_1.0.safetensors",
                    "path": "/models/checkpoints/sdxl_refiner_1.0.safetensors",
                    "size_mb": 6000.0,
                },
            ],
        },
    }
    monkeypatch.setattr(
        "dreamforge_cli_inventory.list_model_inventory",
        lambda: fake_inventory,
    )
    result = _pick_faceid_checkpoint()
    assert result is None


def test_pick_faceid_checkpoint_returns_none_when_empty(monkeypatch):
    """No checkpoints at all should return None."""
    from dreamforge_identity import _pick_faceid_checkpoint

    fake_inventory = {
        "models_root": "/models",
        "categories": {"checkpoints": []},
    }
    monkeypatch.setattr(
        "dreamforge_cli_inventory.list_model_inventory",
        lambda: fake_inventory,
    )
    assert _pick_faceid_checkpoint() is None


@pytest.mark.parametrize("studio_mode", ["generate", "edit"])
@pytest.mark.parametrize("family", ["krea2", "flux_kontext", "qwen_image_edit"])
def test_native_studio_compile_drops_legacy_identity_without_changing_model(monkeypatch, studio_mode, family):
    from dreamforge_cli_direct import _compile_job
    from dreamforge_references import apply_reference_slots_to_job

    model = {"name": family + ".safetensors", "engine_name": family + ".safetensors", "family": family}
    monkeypatch.setitem(_compile_job.__globals__, "_resolve_model", lambda *args: model)
    monkeypatch.setattr("dreamforge_identity._pick_kontext_checkpoint", lambda: pytest.fail("legacy model routing ran"))
    monkeypatch.setattr("dreamforge_identity._face_embeddings", lambda path: pytest.fail("face analysis ran"))
    payload = {
        "studio_mode": studio_mode, "model": model["name"], "prompt": "same person with a blue shirt",
        "input_image": "source.png", "reference_role": "source_edit", "steps": 13, "cfg_scale": 2.5,
        "width": 608, "height": 768, "seed": 42, "identity_mode": "ipadapter_faceid",
        "preserve_character": True, "face_preservation": True, "identity_verify": True,
        "identity_retry": True, "identity_face_index": 1, "identity_similarity_threshold": 0.6,
        "ipadapter_model": "ip-adapter-faceid.bin", "workflow_mode": "ipadapter_faceid",
        "lora": ["krea2_identity_edit_v1_2.safetensors:0.75"],
        "references": [{"path": "source.png", "role": "source_edit", "character_id": "character_a", "face_index": 1},
                       {"path": "subject.png", "role": "image_prompt", "character_region": "left"}],
    }
    job, selected, prompt, _, width, height, _ = _compile_job(SimpleNamespace(), payload)
    ref_patch = apply_reference_slots_to_job(job)
    assert not ref_patch.get("character_binding_prompt")
    assert apply_identity_to_job(job, model_family=family) == {}
    assert selected == model and job.model == model["name"]
    assert prompt == payload["prompt"] and (width, height, job.steps, job.cfg_scale, job.seed) == (608, 768, 13, 2.5, 42)
    assert job.lora == payload["lora"]
    assert not any((job.preserve_character, job.face_preservation, job.identity_mode, job.identity_verify, job.identity_retry))
    assert job.ipadapter_model is None and job.identity_face_index is None
    assert [slot["path"] for slot in job.references] == ["source.png", "subject.png"]
    assert verify_identity_outputs(job, ["result.png"]) == {"status": "disabled"}
    assert build_identity_retry_params(job, payload, {"status": "failed"})[0] is None
    # Even direct callers passing stale flags or natural-language likeness requests cannot reactivate it.
    assert resolve_identity_route(SimpleNamespace(**payload), model_family=family) == {"route": "none"}
    assert verify_identity_outputs(SimpleNamespace(**payload), ["result.png"]) == {"status": "disabled"}
    assert payload["references"][0]["character_id"] == "character_a"


def test_identity_cleanup_keeps_toolbox_custom_workflows_and_photo_restore():
    from dreamforge_identity import clear_legacy_identity_settings

    saved = {"identity_mode": "ipadapter_faceid", "identity_verify": True, "face_preservation": True,
             "references": [{"path": "source.png", "character_id": "character_a", "face_index": 1}]}
    for context in ({"studio_mode": "toolbox"}, {"studio_mode": "inpaint"},
                    {"studio_mode": "edit", "custom_tool_id": "legacy_workflow"}, {}):
        params = {**saved, **context}
        assert clear_legacy_identity_settings(params) == params
    restore = clear_legacy_identity_settings({**saved, "studio_mode": "edit", "edit_task": "photo_restore"})
    assert restore["face_preservation"] and not restore["identity_verify"]
