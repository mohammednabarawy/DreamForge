from dreamforge_model_registry import ModelCapabilities


def _model(name, size_mb, family):
    return {
        "name": name,
        "stem": name.rsplit(".", 1)[0],
        "relative_path": name,
        "path": f"D:/DreamForge/backend/models/checkpoints/{name}",
        "size_mb": size_mb,
        "family": family,
    }


def test_router_uses_detected_16gb_profile_for_auto(monkeypatch):
    import dreamforge_cli_inventory as inv

    monkeypatch.setattr(inv, "detect_vram_profile", lambda: "16gb")
    monkeypatch.setattr(
        inv,
        "list_model_inventory",
        lambda: {
            "categories": {
                "checkpoints": [
                    _model("dreamshaper_8.safetensors", 2033, "sd15"),
                    _model("flux1-schnell-fp8.safetensors", 16437, "flux"),
                ],
                "diffusion_models": [],
                "unet": [],
            }
        },
    )
    monkeypatch.setattr(inv, "check_model_dependencies", lambda _model: [])

    chosen = inv.route_best_model({ModelCapabilities.TEXT_TO_IMAGE}, "auto", "Quality")

    assert chosen["family"] == "flux"
    assert chosen["effective_vram_profile"] == "16gb"
    assert chosen["estimated_vram_gb"] <= 16.75


def test_router_prefers_small_local_model_for_5gb(monkeypatch):
    import dreamforge_cli_inventory as inv

    monkeypatch.setattr(
        inv,
        "list_model_inventory",
        lambda: {
            "categories": {
                "checkpoints": [
                    _model("dreamshaper_8.safetensors", 2033, "sd15"),
                    _model("flux1-schnell-fp8.safetensors", 16437, "flux"),
                ],
                "diffusion_models": [],
                "unet": [],
            }
        },
    )
    monkeypatch.setattr(inv, "check_model_dependencies", lambda _model: [])

    chosen = inv.route_best_model({ModelCapabilities.TEXT_TO_IMAGE}, "5gb", "Speed")

    assert chosen["family"] == "sd15"
    assert chosen["effective_vram_profile"] == "5gb"


def test_router_accepts_quantized_flux_for_8gb(monkeypatch):
    import dreamforge_cli_inventory as inv

    monkeypatch.setattr(
        inv,
        "list_model_inventory",
        lambda: {
            "categories": {
                "checkpoints": [
                    _model("dreamshaper_8.safetensors", 2033, "sd15"),
                ],
                "diffusion_models": [
                    _model("svdq-fp4_r32-flux.1-dev.safetensors", 6712, "flux"),
                    _model("flux1-schnell-fp8.safetensors", 16437, "flux"),
                ],
                "unet": [],
            }
        },
    )
    monkeypatch.setattr(inv, "check_model_dependencies", lambda _model: [])

    chosen = inv.route_best_model({ModelCapabilities.TEXT_TO_IMAGE}, "8gb", "Quality")

    assert chosen["name"] == "svdq-fp4_r32-flux.1-dev.safetensors"
    assert chosen["effective_vram_profile"] == "8gb"


def test_router_filters_large_models_for_no_gpu(monkeypatch):
    import dreamforge_cli_inventory as inv

    monkeypatch.setattr(
        inv,
        "list_model_inventory",
        lambda: {
            "categories": {
                "checkpoints": [
                    _model("tiny-diffusion_pytorch_model.safetensors", 319, "sdxl"),
                    _model("dreamshaper_8.safetensors", 2033, "sd15"),
                    _model("juggernautXL.safetensors", 6776, "sdxl"),
                ],
                "diffusion_models": [],
                "unet": [],
            }
        },
    )
    monkeypatch.setattr(inv, "check_model_dependencies", lambda _model: [])

    chosen = inv.route_best_model({ModelCapabilities.TEXT_TO_IMAGE}, "no_gpu", "Speed")

    assert chosen["name"] == "dreamshaper_8.safetensors"
    assert chosen["effective_vram_profile"] == "no_gpu"


def test_router_skips_missing_companion_candidates(monkeypatch):
    import dreamforge_cli_inventory as inv

    qwen = _model("Qwen_Image_Edit-Q3_K_M.gguf", 9231, "qwen_image_edit")
    kontext = _model("flux1-dev-kontext_fp8_scaled.safetensors", 11353, "flux_kontext")
    monkeypatch.setattr(
        inv,
        "list_model_inventory",
        lambda: {
            "categories": {
                "checkpoints": [],
                "diffusion_models": [qwen, kontext],
                "unet": [],
            }
        },
    )
    monkeypatch.setattr(
        inv,
        "check_model_dependencies",
        lambda model: [{"id": "missing"}] if model["family"] == "qwen_image_edit" else [],
    )

    chosen = inv.route_best_model({ModelCapabilities.IMAGE_TO_IMAGE}, "16gb", "Quality")

    assert chosen["family"] == "flux_kontext"


def test_model_fallback_actions_include_download_and_switch(monkeypatch):
    import dreamforge_cli_inventory as inv

    qwen = _model("Qwen_Image_Edit-Q3_K_M.gguf", 9231, "qwen_image_edit")
    kontext = _model("flux1-dev-kontext_fp8_scaled.safetensors", 6712, "flux_kontext")
    monkeypatch.setattr(
        inv,
        "resolve_generation_model",
        lambda name: qwen if "Qwen" in name else None,
    )
    monkeypatch.setattr(
        inv,
        "list_model_inventory",
        lambda: {
            "categories": {
                "checkpoints": [],
                "diffusion_models": [qwen, kontext],
                "unet": [],
            }
        },
    )

    def fake_missing(model):
        return [{"id": "clip_qwen25_edit_gguf", "name": "qwen_2.5_vl_7b_edit-q2_k.gguf"}] if model["family"] == "qwen_image_edit" else []

    monkeypatch.setattr(inv, "check_model_dependencies", fake_missing)

    actions = inv.model_fallback_actions(
        qwen,
        {ModelCapabilities.IMAGE_TO_IMAGE},
        "16gb",
        "Quality",
    )

    assert actions[0]["action"] == "download_model_companions"
    assert actions[0]["missing"][0]["id"] == "clip_qwen25_edit_gguf"
    assert actions[1]["action"] == "switch_model"
    assert actions[1]["family"] == "flux_kontext"


def test_router_prefers_fast_model_for_batches(monkeypatch):
    import dreamforge_cli_inventory as inv

    monkeypatch.setattr(
        inv,
        "list_model_inventory",
        lambda: {
            "categories": {
                "checkpoints": [
                    _model("flux1-dev-fp8.safetensors", 16447, "flux"),
                    _model("flux1-schnell-fp8.safetensors", 16437, "flux"),
                ],
                "diffusion_models": [],
                "unet": [],
            }
        },
    )
    monkeypatch.setattr(inv, "check_model_dependencies", lambda _model: [])

    chosen = inv.route_best_model({ModelCapabilities.TEXT_TO_IMAGE}, "16gb", "Speed")

    assert chosen["name"] == "flux1-schnell-fp8.safetensors"


def test_router_prefers_quality_model_for_final_render(monkeypatch):
    import dreamforge_cli_inventory as inv

    monkeypatch.setattr(
        inv,
        "list_model_inventory",
        lambda: {
            "categories": {
                "checkpoints": [
                    _model("flux1-dev-fp8.safetensors", 16447, "flux"),
                    _model("flux1-schnell-fp8.safetensors", 16437, "flux"),
                ],
                "diffusion_models": [],
                "unet": [],
            }
        },
    )
    monkeypatch.setattr(inv, "check_model_dependencies", lambda _model: [])

    chosen = inv.route_best_model({ModelCapabilities.TEXT_TO_IMAGE}, "16gb", "Quality")

    assert chosen["name"] == "flux1-dev-fp8.safetensors"
