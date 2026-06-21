from dreamforge_upscale_routing import (
    is_upscale_compatible_checkpoint,
    pick_best_sdxl_upscale_checkpoint,
    resolve_upscale_checkpoint_model,
)


def test_pick_sdxl_over_flux_for_upscale():
    gallery = [
        {
            "engine_name": "flux1-dev-fp8.safetensors",
            "family": "flux",
            "category": "diffusion_models",
            "caption": "Flux Dev",
        },
        {
            "engine_name": "epicrealismXL_vxviiCrystalclear.safetensors",
            "family": "sdxl",
            "category": "checkpoints",
            "caption": "EpicRealism XL",
        },
    ]
    assert pick_best_sdxl_upscale_checkpoint(gallery) == "epicrealismXL_vxviiCrystalclear.safetensors"


def test_resolve_upscale_routes_incompatible_checkpoint():
    gallery = [
        {
            "engine_name": "z-image-turbo.safetensors",
            "family": "z-image",
            "category": "checkpoints",
            "caption": "Z-Image Turbo",
        },
        {
            "engine_name": "juggernautXL_v9.safetensors",
            "family": "sdxl",
            "category": "checkpoints",
            "caption": "Juggernaut XL",
        },
    ]
    model = {
        "engine_name": "z-image-turbo.safetensors",
        "family": "z-image",
        "category": "checkpoints",
        "name": "z-image-turbo.safetensors",
    }
    routed, msg = resolve_upscale_checkpoint_model(model, gallery)
    assert routed["engine_name"] == "juggernautXL_v9.safetensors"
    assert msg and "SDXL" in msg
    assert is_upscale_compatible_checkpoint(routed)


def test_z_image_is_not_upscale_compatible():
    item = {
        "engine_name": "z-image-turbo.safetensors",
        "family": "z-image",
        "category": "checkpoints",
    }
    assert not is_upscale_compatible_checkpoint(item)
