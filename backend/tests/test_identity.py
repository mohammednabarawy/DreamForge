"""Tests for modern identity preservation routing."""

from types import SimpleNamespace

import pytest

from dreamforge_identity import (
    apply_identity_to_job,
    faceid_assets_available,
    identity_intent_from_prompt,
    is_identity_preservation_job,
    normalize_identity_mode,
    resolve_identity_route,
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
        "dreamforge_identity.custom_node_pack_present",
        lambda _pack: False,
        raising=False,
    )
    from dreamforge_workflow_planner import custom_node_pack_present

    monkeypatch.setattr(
        "dreamforge_identity._inventory_model",
        lambda category, hints=(): None,
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
