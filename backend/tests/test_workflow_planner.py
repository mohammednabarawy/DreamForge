from dreamforge_workflow_planner import (
    LOCAL_IMAGE_BACKEND,
    build_live_workflow_blueprint,
    filter_operations_for_plan_mode,
    list_workflow_templates,
    resolve_operations_from_intent,
)


def test_live_blueprint_for_common_editing_needs():
    blueprint = build_live_workflow_blueprint(
        "make her smile, remove background people, make it cinematic, upscale to 4K",
        has_image=True,
        has_mask=False,
        has_references=False,
    )

    assert blueprint["image_backend"] == LOCAL_IMAGE_BACKEND
    assert blueprint["local_only"] is True
    assert "face_edit" in blueprint["operations"]
    assert "remove_object" in blueprint["operations"]
    assert "style_transfer" in blueprint["operations"]
    assert "upscale" in blueprint["operations"]
    assert "flux_kontext_edit" in blueprint["template_ids"]
    assert "upscale_basic" in blueprint["template_ids"]


def test_qwen_edit_readiness_recommends_8step_lightning_lora(monkeypatch):
    import dreamforge_workflow_planner as planner

    monkeypatch.setattr(
        planner,
        "_inventory_categories",
        lambda: {
            "diffusion_models": [
                {
                    "name": "qwen-image-edit-2511-Q4_K_M.gguf",
                    "family": "qwen_image_edit",
                }
            ]
        },
    )
    monkeypatch.setattr(planner, "custom_node_pack_present", lambda _pack: True)
    monkeypatch.setattr(
        "dreamforge_cli_inventory.qwen_specific_lightning_lora_present",
        lambda _req, **kwargs: False,
    )
    monkeypatch.setattr(
        "dreamforge_cli_inventory.companion_file_present",
        lambda _req, **kwargs: True,
    )

    blueprint = build_live_workflow_blueprint(
        "edit poster text",
        operations=["edit_image"],
        has_image=True,
        current_settings={
            "edit_type": "qwen_edit",
            "performance": "Lightning",
            "model": "qwen-image-edit-2511-Q4_K_M.gguf",
            "input_image": "poster.png",
        },
    )

    assert "qwen_image_edit" in blueprint["template_ids"]
    actions = blueprint["readiness"]["recommended_actions"]
    download = next((a for a in actions if a.get("action") == "download_model_companions"), None)
    assert download is not None
    assert any(
        item.get("id") == "lora_qwen_edit_lightning_8step"
        for item in download.get("missing", [])
    )


def test_qwen_edit_plan_uses_qwen_template():
    blueprint = build_live_workflow_blueprint(
        "edit Arabic poster text",
        operations=["edit_image"],
        has_image=True,
        current_settings={
            "edit_type": "qwen_edit",
            "model": "../diffusion_models/qwen-image-edit-2511-Q4_K_M.gguf",
        },
    )

    assert "qwen_image_edit" in blueprint["template_ids"]
    assert "flux_kontext_edit" not in blueprint["template_ids"]
    assert "qwen_text_encoder" in blueprint["required_models"]


def test_blueprint_routes_control_reference_and_compositing_patterns():
    operations = resolve_operations_from_intent(
        "use the same character reference, preserve pose with depth controlnet, composite as a product poster",
        has_image=True,
        has_references=True,
    )
    blueprint = build_live_workflow_blueprint(
        "use the same character reference, preserve pose with depth controlnet, composite as a product poster",
        operations=operations,
        has_image=True,
        has_references=True,
    )

    assert "reference_guidance" in operations
    assert "controlnet_structure" in operations
    assert "composite_layers" in operations
    assert "controlnet_structure" in blueprint["template_ids"]
    assert "area_composition" in blueprint["template_ids"]
    assert "readiness" in blueprint


def test_template_catalog_exposes_research_and_krita_patterns():
    templates = {item["id"]: item for item in list_workflow_templates()}

    assert "flux_kontext_edit" in templates
    assert "inpaint_repair" in templates
    assert "upscale_basic" in templates
    assert "reference_ipadapter" in templates
    assert templates["area_composition"]["builder"] == "comfy_area_composition"
    assert templates["flux_kontext_edit"]["krita_alignment"]
    assert "ComfyUI_IPAdapter_plus" in templates["reference_ipadapter"]["required_node_packs"]
    assert templates["face_detail_optional"]["builder"] == "comfy_face_detail_basic"
    assert "ComfyUI-Impact-Pack" in templates["face_detail_optional"]["required_node_packs"]


def test_controlnet_readiness_reports_missing_control_model(monkeypatch):
    import dreamforge_workflow_planner as planner

    monkeypatch.setattr(
        planner,
        "_inventory_categories",
        lambda: {
            "checkpoints": [{"name": "sdxl.safetensors"}],
            "controlnet": [],
            "upscale_models": [],
        },
    )
    blueprint = build_live_workflow_blueprint(
        "preserve pose with depth controlnet",
        has_image=True,
        current_settings={"prompt": "preserve pose with depth controlnet"},
    )

    assert "controlnet_structure" in blueprint["template_ids"]
    assert blueprint["readiness"]["ready"] is False
    assert "controlnet_model" in blueprint["readiness"]["missing_models"]


def test_ipadapter_readiness_blocks_when_custom_node_pack_missing(monkeypatch):
    import dreamforge_workflow_planner as planner

    monkeypatch.setattr(
        planner,
        "_inventory_categories",
        lambda: {
            "checkpoints": [{"name": "sdxl.safetensors"}],
            "ipadapter": [{"name": "ip-adapter-plus_sdxl.safetensors"}],
            "clip_vision": [{"name": "clip-vision_vit-h.safetensors"}],
        },
    )
    monkeypatch.setattr(planner, "custom_node_pack_present", lambda _pack: False)

    blueprint = build_live_workflow_blueprint(
        "use this style reference for a new image",
        has_image=False,
        has_references=True,
        current_settings={"prompt": "use this style reference for a new image", "reference_images": ["ref.png"]},
    )

    assert "reference_ipadapter" in blueprint["template_ids"]
    assert blueprint["readiness"]["ready"] is False
    assert "ComfyUI_IPAdapter_plus" in blueprint["readiness"]["missing_node_packs"]


def test_ipadapter_readiness_recommends_exact_downloadable_assets(monkeypatch):
    import dreamforge_workflow_planner as planner

    monkeypatch.setattr(
        planner,
        "_inventory_categories",
        lambda: {
            "checkpoints": [{"name": "sdxl.safetensors"}],
            "ipadapter": [],
            "clip_vision": [],
        },
    )
    monkeypatch.setattr(planner, "custom_node_pack_present", lambda _pack: True)

    blueprint = build_live_workflow_blueprint(
        "use this style reference for a new image",
        has_image=False,
        has_references=True,
        current_settings={"prompt": "use this style reference", "reference_images": ["ref.png"]},
    )

    actions = blueprint["readiness"]["recommended_actions"]
    downloads = [action for action in actions if action["action"] == "download_model_companions"]

    assert len(downloads) == 1
    assert {item["id"] for item in downloads[0]["missing"]} == {
        "ipadapter_sdxl_vith",
        "clip_vision_ipadapter_vith",
    }
    assert all(item.get("url") for item in downloads[0]["missing"])
    assert downloads[0]["requires_approval"] is True


def test_controlnet_readiness_recommends_depth_model_download(monkeypatch):
    import dreamforge_workflow_planner as planner

    monkeypatch.setattr(
        planner,
        "_inventory_categories",
        lambda: {
            "checkpoints": [{"name": "sdxl.safetensors"}],
            "controlnet": [],
        },
    )

    blueprint = build_live_workflow_blueprint(
        "preserve pose with depth controlnet",
        has_image=True,
        current_settings={
            "prompt": "preserve pose with depth controlnet",
            "control_image": "depth.png",
            "cn_type": "depth",
        },
    )

    downloads = [
        action for action in blueprint["readiness"]["recommended_actions"]
        if action["action"] == "download_model_companions"
    ]

    assert downloads
    assert downloads[0]["missing"][0]["id"] == "controlnet_depth_sd15"
    assert downloads[0]["missing"][0]["relative"].startswith("controlnet/")


def test_upscale_readiness_recommends_selected_upscaler_download(monkeypatch):
    import dreamforge_workflow_planner as planner

    monkeypatch.setattr(
        planner,
        "_inventory_categories",
        lambda: {
            "checkpoints": [{"name": "sdxl.safetensors"}],
            "upscale_models": [],
        },
    )

    blueprint = build_live_workflow_blueprint(
        "upscale this image 4x",
        has_image=True,
        current_settings={
            "prompt": "upscale this image",
            "input_image": "image.png",
            "upscale_method": "fast_4x",
        },
    )

    downloads = [
        action for action in blueprint["readiness"]["recommended_actions"]
        if action["action"] == "download_model_companions"
    ]

    assert downloads
    assert downloads[0]["missing"][0]["id"] == "upscaler_omnisr_4x"
    assert downloads[0]["missing"][0]["filename"] == "OmniSR_X4_DIV2K.safetensors"


def test_explicit_inpaint_blueprint_requires_image_and_mask(monkeypatch):
    import dreamforge_workflow_planner as planner

    monkeypatch.setattr(
        planner,
        "_inventory_categories",
        lambda: {"checkpoints": [{"name": "flux-fill-dev.safetensors", "family": "flux_fill"}]},
    )

    blueprint = build_live_workflow_blueprint(
        "replace this area",
        operations=["inpaint"],
        has_image=False,
        has_mask=False,
        current_settings={
            "prompt": "replace this area",
            "edit_type": "inpaint",
        },
    )

    assert "inpaint_repair" in blueprint["template_ids"]
    assert blueprint["readiness"]["ready"] is False
    assert blueprint["readiness"]["missing_inputs"] == ["input_image", "mask"]
    assert "A mask or region selection is required" in " ".join(blueprint["warnings"])


def test_explicit_inpaint_blueprint_requires_flux_fill_checkpoint(monkeypatch):
    import dreamforge_workflow_planner as planner

    monkeypatch.setattr(
        planner,
        "_inventory_categories",
        lambda: {"checkpoints": [{"name": "haveallsdxlInpaint_v10.safetensors", "family": "sdxl"}]},
    )

    blueprint = build_live_workflow_blueprint(
        "replace this area",
        operations=["inpaint"],
        has_image=True,
        has_mask=True,
        current_settings={
            "prompt": "replace this area",
            "edit_type": "inpaint",
            "inpaint_mask_path": "D:/tmp/mask.png",
            "input_image": "D:/tmp/source.png",
        },
    )

    assert "inpaint_repair" in blueprint["template_ids"]
    assert blueprint["readiness"]["ready"] is False
    assert "flux_fill_checkpoint" in blueprint["readiness"]["missing_models"]


def test_highly_detailed_style_prompt_does_not_route_to_face_detail():
    ops = resolve_operations_from_intent(
        "cinematic film still, highly detailed, volumetric lighting",
        has_image=False,
    )
    assert "face_detail" not in ops
    blueprint = build_live_workflow_blueprint(
        "cinematic film still, highly detailed, volumetric lighting",
        operations=ops,
        has_image=False,
        current_settings={"prompt": "cinematic film still, highly detailed"},
    )
    assert "face_detail_optional" not in blueprint["template_ids"]


def test_face_detail_blueprint_requires_impact_packs_and_bbox_models(monkeypatch, tmp_path):
    import dreamforge_workflow_planner as planner

    models = tmp_path / "models"
    (models / "checkpoints").mkdir(parents=True)
    (models / "checkpoints" / "sdxl.safetensors").write_bytes(b"x")
    (models / "ultralytics" / "bbox").mkdir(parents=True)
    (models / "ultralytics" / "bbox" / "face_yolov8m.pt").write_bytes(b"x")

    monkeypatch.setattr(planner, "_models_root_hint", lambda: models)
    monkeypatch.setattr(
        planner,
        "_inventory_categories",
        lambda: {"checkpoints": [{"name": "sdxl.safetensors"}]},
    )
    monkeypatch.setattr(planner, "custom_node_pack_present", lambda _pack: True)

    blueprint = build_live_workflow_blueprint(
        "repair face details and sharpen eyes",
        has_image=True,
        current_settings={"prompt": "repair face details", "input_image": "portrait.png"},
    )

    assert "face_detail" in blueprint["operations"]
    assert "face_detail_optional" in blueprint["template_ids"]
    assert blueprint["readiness"]["ready"] is True


def test_inpaint_plan_mode_drops_optional_text_and_style_ops(monkeypatch):
    import dreamforge_workflow_planner as planner

    monkeypatch.setattr(
        planner,
        "_inventory_categories",
        lambda: {"checkpoints": [{"name": "flux-fill-dev.safetensors", "family": "flux_fill"}]},
    )

    ops = resolve_operations_from_intent(
        "add logo headline cinematic lighting inpaint this area",
        has_image=True,
        has_mask=True,
    )
    assert "inpaint" in ops
    assert "text_integrate" in ops
    assert "style_transfer" in ops

    filtered = filter_operations_for_plan_mode(
        ops,
        mode="inpaint",
        has_image=True,
        workflow_mode="",
    )
    assert filtered == ["inpaint"]

    blueprint = build_live_workflow_blueprint(
        "add logo headline cinematic lighting inpaint this area",
        operations=filtered,
        has_image=True,
        has_mask=True,
        current_settings={
            "prompt": "inpaint this area",
            "input_image": "photo.png",
            "inpaint_mask_path": "mask.png",
            "edit_type": "inpaint",
        },
    )
    assert "arabic_text_composite" not in blueprint["template_ids"]
    assert "text" not in blueprint["readiness"]["missing_inputs"]
    assert blueprint["readiness"]["ready"] is True


def test_upscale_large_tiles_low_vram_warning():
    blueprint = build_live_workflow_blueprint(
        "upscale image",
        operations=["upscale"],
        has_image=True,
        current_settings={
            "upscale_by": 4.0,
            "upscale_tile_width": 1024,
            "upscale_tile_height": 1024,
            "vram_profile": "8gb",
        },
    )
    warnings = blueprint.get("warnings") or []
    assert any("low VRAM" in w for w in warnings)


def test_upscale_normal_no_warning():
    blueprint = build_live_workflow_blueprint(
        "upscale image",
        operations=["upscale"],
        has_image=True,
        current_settings={
            "upscale_by": 2.0,
            "upscale_tile_width": 512,
            "upscale_tile_height": 512,
            "vram_profile": "16gb",
        },
    )
    warnings = blueprint.get("warnings") or []
    assert not any("low VRAM" in w for w in warnings)

