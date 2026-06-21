from dreamforge_engine import DreamForgeEngine
from dreamforge_model_registry import ModelCapabilities, required_capabilities_for_request


def test_engine_namespace_preserves_workflow_specific_args():
    ns = DreamForgeEngine._to_namespace(
        {
            "prompt": "regional poster",
            "workflow_mode": "area_composition",
            "region_prompts": ["0,0,512,512:left", "512,0,512,512:right"],
            "reference_mode": "ipadapter",
            "reference_images": ["D:/tmp/ref.png"],
            "hires": True,
            "cn_type": "depth",
            "outpaint_direction": "right",
        }
    )

    assert ns.workflow_mode == "area_composition"
    assert ns.region_prompts == ["0,0,512,512:left", "512,0,512,512:right"]
    assert ns.reference_mode == "ipadapter"
    assert ns.reference_images == ["D:/tmp/ref.png"]
    assert ns.hires is True
    assert ns.cn_type == "depth"
    assert ns.outpaint_direction == "right"


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

    assert ModelCapabilities.FLUX_FILL_INPAINT in caps
    assert ModelCapabilities.INPAINT not in caps
