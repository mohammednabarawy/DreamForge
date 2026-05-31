from pathlib import Path

import pytest

import dreamforge_reference_packs as packs
from dreamforge_brain import heuristic_brain_decision
from dreamforge_desktop_bridge import handle_request


@pytest.fixture()
def isolated_pack_store(tmp_path, monkeypatch):
    store = tmp_path / "reference_packs.json"
    monkeypatch.setattr(packs, "PACKS_PATH", store)
    return store


def test_reference_pack_crud_is_local_json(isolated_pack_store: Path):
    source = isolated_pack_store.parent / "source.png"
    source.write_bytes(b"fake image")

    created = packs.upsert_reference_pack(
        {
            "name": "Hero Watch",
            "type": "product",
            "image_paths": [str(source), str(source), ""],
            "tags": ["watch", "luxury"],
            "notes": "Use for product consistency.",
            "preferred_use_cases": ["product ads"],
        }
    )

    assert created["id"] == "hero-watch"
    assert created["type"] == "product"
    assert created["image_paths"] == [str(source)]
    assert isolated_pack_store.is_file()

    listed = packs.list_reference_packs()[0]
    assert listed["created_at"] == created["created_at"]
    assert listed["updated_at"] == created["updated_at"]

    listed = packs.list_reference_packs()
    assert [item["id"] for item in listed] == ["hero-watch"]

    assert packs.delete_reference_pack("hero-watch") is True
    assert source.exists(), "deleting a pack must not delete source images"
    assert packs.list_reference_packs() == []


def test_reference_pack_attach_adds_reference_images(isolated_pack_store: Path):
    packs.upsert_reference_pack(
        {
            "name": "Noir Character",
            "type": "character",
            "image_paths": ["D:/refs/face.png", "D:/refs/costume.png"],
            "tags": ["noir"],
        }
    )

    settings = packs.apply_reference_pack_to_settings(
        {"reference_pack_id": "noir-character", "reference_images": ["D:/refs/pose.png"]}
    )

    assert settings["reference_pack"]["name"] == "Noir Character"
    assert settings["reference_pack"]["type"] == "character"
    assert settings["reference_images"] == [
        "D:/refs/pose.png",
        "D:/refs/face.png",
        "D:/refs/costume.png",
    ]


def test_brain_plan_names_attached_reference_pack(isolated_pack_store: Path):
    packs.upsert_reference_pack(
        {
            "name": "Brand Kit A",
            "type": "brand",
            "image_paths": ["D:/refs/logo.png"],
            "tags": ["blue", "minimal"],
        }
    )

    decision = heuristic_brain_decision(
        "make a clean product ad using the brand reference",
        current_settings={"prompt": "product ad", "reference_pack_id": "brand-kit-a"},
    )

    assert decision["reference_pack"]["name"] == "Brand Kit A"
    assert "reference_guidance" in decision["operations"]
    assert decision["patch"]["reference_pack_id"] == "brand-kit-a"
    assert decision["patch"]["reference_images"] == ["D:/refs/logo.png"]
    assert "Brand Kit A" in decision["message"]


def test_reference_pack_bridge_roundtrip(isolated_pack_store: Path):
    saved = handle_request(
        '{"cmd":"save_reference_pack","params":{"name":"Style Study","type":"style","image_paths":["D:/a.png"]}}'
    )
    assert saved["ok"] is True
    assert saved["pack"]["id"] == "style-study"

    listed = handle_request('{"cmd":"list_reference_packs"}')
    assert listed["ok"] is True
    assert [item["name"] for item in listed["packs"]] == ["Style Study"]

    deleted = handle_request('{"cmd":"delete_reference_pack","params":{"id":"style-study"}}')
    assert deleted["ok"] is True
    assert deleted["deleted"] is True
    assert handle_request('{"cmd":"list_reference_packs"}')["packs"] == []


def test_dry_run_reports_attached_reference_pack(isolated_pack_store: Path, monkeypatch):
    import dreamforge_cli_direct as cli

    packs.upsert_reference_pack(
        {
            "name": "Product Angles",
            "type": "product",
            "image_paths": ["D:/refs/front.png", "D:/refs/side.png"],
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

    from types import SimpleNamespace

    plan = cli.build_plan(
        SimpleNamespace(
            dry_run=True,
            json=True,
            model="flux1-dev-kontext_fp8_scaled.safetensors",
            prompt="use the same product reference",
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
            reference_pack_id="product-angles",
            reference_pack_role="product",
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

    assert plan["reference_pack"]["name"] == "Product Angles"
    assert plan["reference_images"] == ["D:/refs/front.png", "D:/refs/side.png"]
    assert plan["mode_contract"]["preserved_fields"]
