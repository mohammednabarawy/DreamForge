from dreamforge_engine import DreamForgeEngine
from dreamforge_model_registry import ModelCapabilities, required_capabilities_for_request


def test_engine_namespace_preserves_workflow_specific_args():
    ns = DreamForgeEngine._to_namespace(
        {
            "prompt": "regional poster",
            "workflow_mode": "area_composition",
            "studio_mode": "generate",
            "region_prompts": ["0,0,512,512:left", "512,0,512,512:right"],
            "reference_mode": "ipadapter",
            "reference_images": ["D:/tmp/ref.png"],
            "hires": True,
            "cn_type": "depth",
            "outpaint_direction": "right",
            "edit_task": "photo_restore",
            "depth_strength": 0.15,
            "lineart_strength": 0.35,
            "face_preservation": True,
            "upscale_preset": "fast_4x",
            "upscale_by": 4,
            "upscale_denoise": 0.2,
            "upscale_tile_width": 1024,
            "upscale_tile_padding": 64,
        }
    )

    assert ns.workflow_mode == "area_composition"
    assert ns.studio_mode == "generate"
    assert ns.region_prompts == ["0,0,512,512:left", "512,0,512,512:right"]
    assert ns.reference_mode == "ipadapter"
    assert ns.reference_images == ["D:/tmp/ref.png"]
    assert ns.hires is True
    assert ns.cn_type == "depth"
    assert ns.outpaint_direction == "right"
    assert ns.edit_task == "photo_restore"
    assert ns.depth_strength == 0.15
    assert ns.lineart_strength == 0.35
    assert ns.face_preservation is True
    assert ns.upscale_preset == "fast_4x"
    assert ns.upscale_by == 4
    assert ns.upscale_denoise == 0.2
    assert ns.upscale_tile_width == 1024
    assert ns.upscale_tile_padding == 64


def test_model_registry_routes_edit_capability_before_default_generate():
    caps = required_capabilities_for_request(
        {
            "input_image": "D:/tmp/source.png",
            "edit_type": "qwen_edit",
            "upscale_method": "2x",
        }
    )

    assert ModelCapabilities.QWEN_SEMANTIC_EDIT in caps
    assert ModelCapabilities.TEXT_TO_IMAGE not in caps


def test_model_registry_routes_inpaint_to_flux_fill_capability():
    caps = required_capabilities_for_request(
        {
            "input_image": "D:/tmp/source.png",
            "inpaint_mask_path": "D:/tmp/mask.png",
            "edit_type": "inpaint",
        }
    )

    assert ModelCapabilities.INPAINT in caps
