from pathlib import Path
from types import SimpleNamespace

import dreamforge_identity_registry as identities
from dreamforge_brain import heuristic_brain_decision
from dreamforge_desktop_bridge import handle_request


def _isolated_registry(tmp_path, monkeypatch) -> Path:
    db_path = tmp_path / "identity_registry.sqlite3"
    monkeypatch.setattr(identities, "REGISTRY_PATH", db_path)
    return db_path


def test_identity_registry_crud_search_is_local_sqlite(tmp_path, monkeypatch):
    db_path = _isolated_registry(tmp_path, monkeypatch)
    source = tmp_path / "hero.png"
    source.write_bytes(b"fake image")

    created = identities.upsert_identity(
        {
            "name": "Hero Character",
            "type": "character",
            "image_paths": [str(source), str(source), ""],
            "reference_pack_ids": ["hero-pack"],
            "tags": ["noir", "coat"],
            "notes": "Main protagonist.",
            "metadata": {"palette": ["black", "silver"]},
        }
    )

    assert db_path.is_file()
    assert created["id"] == "hero-character"
    assert created["type"] == "character"
    assert created["image_paths"] == [str(source)]
    assert identities.search_identities("noir")[0]["id"] == "hero-character"

    updated = identities.upsert_identity({"id": "hero-character", "name": "Hero Character", "type": "person"})
    assert updated["created_at"] == created["created_at"]
    assert updated["type"] == "person"

    assert identities.delete_identity("hero-character") is True
    assert source.exists(), "deleting an identity must not delete source images"
    assert identities.list_identities() == []


def test_apply_identity_adds_references_and_dependency_actions(tmp_path, monkeypatch):
    _isolated_registry(tmp_path, monkeypatch)
    identities.upsert_identity(
        {
            "name": "Portrait Lead",
            "type": "person",
            "image_paths": ["D:/refs/face.png", "D:/refs/pose.png"],
            "tags": ["lead"],
        }
    )

    settings = identities.apply_identity_to_settings(
        {
            "identity_id": "portrait-lead",
            "reference_images": ["D:/refs/mood.png"],
            "prompt": "keep the same face and preserve identity",
        }
    )

    assert settings["identity_reference"]["name"] == "Portrait Lead"
    assert settings["reference_images"] == ["D:/refs/mood.png", "D:/refs/face.png", "D:/refs/pose.png"]
    assert settings["identity_dependency_actions"][0]["local_only"] is True


def test_identity_bridge_roundtrip(tmp_path, monkeypatch):
    _isolated_registry(tmp_path, monkeypatch)

    saved = handle_request(
        '{"cmd":"save_identity","params":{"name":"Brand Place","type":"location","image_paths":["D:/place.png"]}}'
    )
    assert saved["ok"] is True
    assert saved["identity"]["id"] == "brand-place"

    listed = handle_request('{"cmd":"list_identities","params":{"query":"place"}}')
    assert listed["ok"] is True
    assert [item["name"] for item in listed["identities"]] == ["Brand Place"]

    deleted = handle_request('{"cmd":"delete_identity","params":{"id":"brand-place"}}')
    assert deleted["ok"] is True
    assert deleted["deleted"] is True


def test_brain_plan_names_attached_identity(tmp_path, monkeypatch):
    _isolated_registry(tmp_path, monkeypatch)
    identities.upsert_identity(
        {
            "name": "Same Founder",
            "type": "person",
            "image_paths": ["D:/refs/founder.png"],
            "tags": ["portrait"],
        }
    )

    decision = heuristic_brain_decision(
        "make the same person smile in the product ad",
        current_settings={"prompt": "portrait ad", "identity_id": "same-founder"},
    )

    assert decision["identity_reference"]["name"] == "Same Founder"
    assert decision["patch"]["identity_id"] == "same-founder"
    assert decision["patch"]["reference_images"] == ["D:/refs/founder.png"]
    assert "Same Founder" in decision["message"]


def test_dry_run_reports_attached_identity(tmp_path, monkeypatch):
    import dreamforge_cli_direct as cli

    _isolated_registry(tmp_path, monkeypatch)
    identities.upsert_identity(
        {
            "name": "Studio Product",
            "type": "product",
            "image_paths": ["D:/refs/front.png", "D:/refs/detail.png"],
            "tags": ["watch"],
        }
    )
    selected = {
        "name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "stem": "flux1-dev-kontext_fp8_scaled",
        "relative_path": "flux1-dev-kontext_fp8_scaled.safetensors",
        "path": "/models/flux1-dev-kontext_fp8_scaled.safetensors",
        "size_mb": 11000,
        "category": "diffusion_models",
        "engine_name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "family": "flux_kontext",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="flux1-dev-kontext_fp8_scaled.safetensors",
            prompt="use the same product identity",
            negative_prompt="",
            aspect_ratio=None,
            width=None,
            height=None,
            seed=1,
            image_number=1,
            output=None,
            performance="Speed",
            steps=None,
            cfg_scale=None,
            sampler=None,
            scheduler=None,
            styles=None,
            lora=[],
            input_image=None,
            reference_images=None,
            reference_pack_id=None,
            reference_pack_role=None,
            identity_id="studio-product",
            identity_role="product",
            inpaint_mask_path=None,
            upscale_image=None,
            upscale_method="fast_2x",
            edit_type="auto",
            edit_strength=None,
            vram_profile="16gb",
            style="image_edit",
            brand_kit=None,
            subject=None,
            composition=None,
            lighting=None,
            camera=None,
            brand_colors=None,
            materials=None,
            visual_style=None,
            validate_output=False,
            no_manifest=False,
        )
    )

    assert plan["identity_reference"]["name"] == "Studio Product"
    assert plan["reference_images"] == ["D:/refs/front.png", "D:/refs/detail.png"]
    assert plan["mode_contract"]["preserved_fields"]
    assert not [
        action for action in plan["recommended_actions"]
        if action.get("resource") == "face_identity_stack"
    ]


def test_dry_run_gates_requested_face_identity_dependencies(tmp_path, monkeypatch):
    import dreamforge_cli_direct as cli

    _isolated_registry(tmp_path, monkeypatch)
    identities.upsert_identity(
        {
            "name": "Same Founder",
            "type": "person",
            "image_paths": ["D:/refs/founder.png"],
            "tags": ["portrait"],
        }
    )
    selected = {
        "name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "stem": "flux1-dev-kontext_fp8_scaled",
        "relative_path": "flux1-dev-kontext_fp8_scaled.safetensors",
        "path": "/models/flux1-dev-kontext_fp8_scaled.safetensors",
        "size_mb": 11000,
        "category": "diffusion_models",
        "engine_name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "family": "flux_kontext",
    }
    monkeypatch.setattr(cli, "resolve_generation_model", lambda _name: selected)

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="flux1-dev-kontext_fp8_scaled.safetensors",
            prompt="make the same person smile",
            negative_prompt="",
            aspect_ratio=None,
            width=None,
            height=None,
            seed=1,
            image_number=1,
            output=None,
            performance="Speed",
            steps=None,
            cfg_scale=None,
            sampler=None,
            scheduler=None,
            styles=None,
            lora=[],
            input_image=None,
            reference_images=None,
            reference_pack_id=None,
            reference_pack_role=None,
            identity_id="same-founder",
            identity_role="person",
            identity_mode=None,
            face_preservation=False,
            inpaint_mask_path=None,
            upscale_image=None,
            upscale_method="fast_2x",
            edit_type="auto",
            edit_strength=None,
            vram_profile="16gb",
            style="image_edit",
            brand_kit=None,
            subject=None,
            composition=None,
            lighting=None,
            camera=None,
            brand_colors=None,
            materials=None,
            visual_style=None,
            validate_output=False,
            no_manifest=False,
        )
    )

    actions = [
        action for action in plan["recommended_actions"]
        if action.get("resource") == "face_identity_stack"
    ]
    assert plan["identity_reference"]["name"] == "Same Founder"
    assert actions
    assert actions[0]["local_only"] is True
    assert plan["ready"] is False
