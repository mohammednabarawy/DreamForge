from dreamforge_workflow_planner import (
    LOCAL_IMAGE_BACKEND,
    build_live_workflow_blueprint,
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
