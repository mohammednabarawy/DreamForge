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


def test_apply_identity_preserves_edit_studio_mode(monkeypatch):
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
