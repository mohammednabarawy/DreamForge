from dreamforge_cli_inventory import companion_file_present
from dreamforge_companion_download import (
    companion_download_tier,
    enrich_missing_dependency,
    ensure_creative_task_ready,
    split_companions_by_tier,
)


def test_enrich_flux_vae():
    entry = {
        "id": "vae_flux_ae",
        "relative": "vae/ae.safetensors",
        "expected_path": "/models/vae/ae.safetensors",
    }
    out = enrich_missing_dependency(entry)
    assert out["url"]
    assert "black-forest-labs/FLUX.1-schnell" in out["url"]
    assert out.get("requires_hf_token") is True
    assert out["category"] == "vae"
    assert out["filename"] == "ae.safetensors"


def test_enrich_flux_t5_fp8_url():
    entry = {
        "id": "clip_t5_flux_fp8",
        "relative": "text_encoders/t5xxl_fp8_e4m3fn_scaled.safetensors",
    }
    out = enrich_missing_dependency(entry)
    assert "comfyanonymous/flux_text_encoders" in out["url"]
    assert out["url"].endswith("t5xxl_fp8_e4m3fn_scaled.safetensors")
    assert out["category"] == "text_encoders"
    assert "Comfy-Org/flux1-dev" not in out["url"]


def test_enrich_flux_clip_l_url():
    entry = {"id": "clip_l_flux", "relative": "clip/clip_l.safetensors"}
    out = enrich_missing_dependency(entry)
    assert "comfyanonymous/flux_text_encoders" in out["url"]
    assert out["url"].endswith("clip_l.safetensors")


def test_enrich_qwen_companion_urls():
    clip = enrich_missing_dependency(
        {
            "id": "clip_qwen25_vl_7b",
            "relative": "text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors",
        }
    )
    vae = enrich_missing_dependency(
        {"id": "vae_qwen_image", "relative": "vae/qwen_image_vae.safetensors"}
    )
    assert "split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" in clip["url"]
    assert "split_files/vae/qwen_image_vae.safetensors" in vae["url"]


def test_enrich_qwen_2511_lightning_lora_url():
    lora = enrich_missing_dependency(
        {
            "id": "lora_qwen_edit_lightning_4step",
            "relative": "loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
        }
    )
    assert "lightx2v/Qwen-Image-Edit-2511-Lightning" in lora["url"]
    assert lora["filename"] == "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors"


def test_enrich_qwen_2511_lightning_8step_lora_url():
    lora = enrich_missing_dependency(
        {
            "id": "lora_qwen_edit_lightning_8step",
            "relative": "loras/Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors",
        }
    )
    assert "lightx2v/Qwen-Image-Edit-2511-Lightning" in lora["url"]
    assert lora["url"].endswith("Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors")
    assert lora["filename"] == "Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors"


def test_companion_present_clip_folder_t5(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "dreamforge_cli_inventory.MODELS_ROOT",
        tmp_path,
    )
    clip_dir = tmp_path / "clip"
    clip_dir.mkdir(parents=True)
    t5 = clip_dir / "t5xxl_fp8_e4m3fn_scaled.safetensors"
    t5.write_bytes(b"x" * (5 * 1024 * 1024))
    req = {
        "id": "clip_t5_flux_fp8",
        "relative": "text_encoders/t5xxl_fp8_e4m3fn_scaled.safetensors",
    }
    assert companion_file_present(req, min_bytes=1024 * 1024)


def test_enrich_unknown_id_has_no_url():
    entry = {"id": "unknown", "relative": "vae/foo.safetensors"}
    out = enrich_missing_dependency(entry)
    assert not out.get("url")


def test_enrich_upscaler_omnisr_2x():
    entry = {
        "id": "upscaler_omnisr_2x",
        "relative": "upscale_models/OmniSR_X2_DIV2K.safetensors",
    }
    out = enrich_missing_dependency(entry)
    assert out["url"]
    assert out["category"] == "upscale_models"
    assert out["filename"] == "OmniSR_X2_DIV2K.safetensors"


def test_download_companion_entries_bridge(tmp_path, monkeypatch):
    from dreamforge_desktop_bridge import cmd_download_companion_entries

    monkeypatch.setattr(
        "dreamforge_cli_inventory.MODELS_ROOT",
        tmp_path,
    )

    def fake_download(missing):
        dest = tmp_path / "upscale_models" / "OmniSR_X2_DIV2K.safetensors"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"x" * (3 * 1024 * 1024))
        return {
            "status": "ok",
            "results": [{"status": "downloaded", "id": "upscaler_omnisr_2x", "path": str(dest)}],
            "errors": [],
            "downloaded": 1,
        }

    monkeypatch.setattr(
        "dreamforge_companion_download.download_missing_companions",
        fake_download,
    )

    payload = cmd_download_companion_entries(
        {
            "items": [
                {
                    "id": "upscaler_omnisr_2x",
                    "relative": "upscale_models/OmniSR_X2_DIV2K.safetensors",
                }
            ]
        }
    )
    assert payload["ok"] is True
    assert payload["downloaded"] == 1


def test_verify_companion_entries_bridge_checks_exact_workflow_asset(tmp_path, monkeypatch):
    from dreamforge_desktop_bridge import cmd_verify_companion_entries

    monkeypatch.setattr(
        "dreamforge_cli_inventory.MODELS_ROOT",
        tmp_path,
    )
    target = tmp_path / "ipadapter" / "ip-adapter_sdxl_vit-h.safetensors"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"x" * (3 * 1024 * 1024))

    payload = cmd_verify_companion_entries(
        {
            "items": [
                {
                    "id": "ipadapter_sdxl_vith",
                    "relative": "ipadapter/ip-adapter_sdxl_vit-h.safetensors",
                    "min_bytes": 2 * 1024 * 1024,
                }
            ]
        }
    )
    assert payload["ok"] is True
    assert payload["ready"] is True
    assert payload["missing"] == []
    assert payload["present"][0]["id"] == "ipadapter_sdxl_vith"


def test_verify_companion_entries_finds_workflow_model_under_comfy_root(tmp_path, monkeypatch):
    from dreamforge_cli_inventory import companion_file_present
    from dreamforge_desktop_bridge import cmd_verify_companion_entries

    comfy_root = tmp_path / "engines" / "comfyui"
    target = (
        comfy_root
        / "custom_nodes/comfyui_controlnet_aux/ckpts/depth-anything/Depth-Anything-V2-Large/depth_anything_v2_vitl.pth"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"x" * (2 * 1024 * 1024))

    monkeypatch.setattr("dreamforge_comfy_manager._comfy_root", lambda: comfy_root)
    monkeypatch.setattr(
        "dreamforge_comfy_manager.workflow_model_ready",
        lambda catalog_id: catalog_id == "depth_anything_v2_vitl",
    )

    item = {
        "kind": "workflow_model",
        "catalog_id": "depth_anything_v2_vitl",
        "id": "depth_anything_v2_vitl",
        "relative": "../custom_nodes/comfyui_controlnet_aux/ckpts/depth-anything/Depth-Anything-V2-Large/depth_anything_v2_vitl.pth",
        "expected_path": str(target),
        "min_bytes": 1024 * 1024,
        "url": "https://example.com/depth_anything_v2_vitl.pth",
    }
    assert companion_file_present(item, min_bytes=1024 * 1024) is True

    payload = cmd_verify_companion_entries({"items": [item]})
    assert payload["ok"] is True
    assert payload["ready"] is True
    assert payload["missing"] == []


def test_verify_companion_entries_custom_node_pack_directory(tmp_path, monkeypatch):
    from dreamforge_desktop_bridge import cmd_verify_companion_entries

    comfy_root = tmp_path / "engines" / "comfyui"
    pack_dir = comfy_root / "custom_nodes" / "rgthree-comfy"
    pack_dir.mkdir(parents=True)
    (pack_dir / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr("dreamforge_workflow_planner.COMFY_ROOT", str(comfy_root), raising=False)
    monkeypatch.setattr(
        "_paths.COMFY_ROOT",
        str(comfy_root),
        raising=False,
    )

    item = {
        "kind": "custom_node_pack",
        "pack_id": "rgthree-comfy",
        "id": "rgthree-comfy",
        "relative": "engines/comfyui/custom_nodes/rgthree-comfy",
    }
    payload = cmd_verify_companion_entries({"items": [item]})
    assert payload["ready"] is True
    assert payload["missing"] == []


def test_verify_companion_entries_graph_model_alias(tmp_path, monkeypatch):
    from dreamforge_desktop_bridge import cmd_verify_companion_entries

    models_root = tmp_path / "models"
    target = models_root / "diffusion_models" / "flux-2-klein-9b-kv-fp8.safetensors"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x" * 200)
    monkeypatch.setattr("dreamforge_cli_inventory.MODELS_ROOT", models_root)
    monkeypatch.setattr("_paths.MODELS_ROOT", models_root, raising=False)

    item = {
        "kind": "model_companion",
        "id": "graph_model:flux-2-klein-9b-fp8.safetensors",
        "filename": "flux-2-klein-9b-fp8.safetensors",
        "relative": "diffusion_models/flux-2-klein-9b-fp8.safetensors",
        "min_bytes": 100,
    }
    payload = cmd_verify_companion_entries({"items": [item]})
    assert payload["ready"] is True
    assert payload["missing"] == []


def test_check_workflow_task_dependencies_bridge(monkeypatch):
    from dreamforge_desktop_bridge import cmd_check_workflow_task_dependencies

    monkeypatch.setattr(
        "dreamforge_comfy_manager.missing_workflow_model_entries",
        lambda **kwargs: [
            {
                "kind": "workflow_model",
                "catalog_id": "depth_anything_v2_vitl",
                "id": "depth_anything_v2_vitl",
                "filename": "depth_anything_v2_vitl.pth",
                "url": "https://example.com/depth_anything_v2_vitl.pth",
                "min_bytes": 1024 * 1024,
            }
        ],
    )
    payload = cmd_check_workflow_task_dependencies({"edit_task": "portrait_master"})
    assert payload["ok"] is True
    assert payload["ready"] is False
    assert payload["missing"][0]["catalog_id"] == "depth_anything_v2_vitl"


def test_companion_download_tier_omnisr_is_a():
    out = enrich_missing_dependency(
        {
            "id": "upscaler_omnisr_2x",
            "relative": "upscale_models/OmniSR_X2_DIV2K.safetensors",
        }
    )
    assert out["download_tier"] == "A"


def test_companion_download_tier_hf_token_is_b():
    out = enrich_missing_dependency(
        {
            "id": "vae_flux_ae",
            "relative": "vae/ae.safetensors",
        }
    )
    assert out.get("requires_hf_token") is True
    assert out["download_tier"] == "B"


def test_companion_download_tier_large_min_bytes_is_b():
    assert (
        companion_download_tier(
            {"url": "https://example.com/large.safetensors", "min_bytes": 600 * 1024 * 1024}
        )
        == "B"
    )


def test_companion_download_tier_checkpoint_path_is_b():
    assert (
        companion_download_tier(
            {
                "url": "https://example.com/model.safetensors",
                "relative": "checkpoints/foo.safetensors",
                "min_bytes": 1024 * 1024,
            }
        )
        == "B"
    )


def test_split_companions_by_tier():
    tier_a = enrich_missing_dependency(
        {
            "id": "upscaler_omnisr_2x",
            "relative": "upscale_models/OmniSR_X2_DIV2K.safetensors",
        }
    )
    tier_b = enrich_missing_dependency(
        {"id": "vae_flux_ae", "relative": "vae/ae.safetensors"}
    )
    a_items, b_items = split_companions_by_tier([tier_a, tier_b])
    assert len(a_items) == 1
    assert a_items[0]["id"] == "upscaler_omnisr_2x"
    assert len(b_items) == 1
    assert b_items[0]["id"] == "vae_flux_ae"


def test_ensure_creative_task_ready_auto_downloads_tier_a(monkeypatch):
    monkeypatch.setattr("dreamforge_workflow_planner.missing_custom_node_pack_entries", lambda *a, **kw: [])
    tier_a = enrich_missing_dependency(
        {
            "id": "upscaler_omnisr_2x",
            "relative": "upscale_models/OmniSR_X2_DIV2K.safetensors",
        }
    )
    collect_passes = [[tier_a], []]

    def fake_collect(**kwargs):
        return None, collect_passes.pop(0)

    downloaded_batches: list[list[dict]] = []

    def fake_download(missing):
        downloaded_batches.append(list(missing))
        return {"downloaded": len(missing), "errors": [], "results": [], "status": "ok"}

    monkeypatch.setattr(
        "dreamforge_companion_download._collect_task_missing",
        fake_collect,
    )
    monkeypatch.setattr(
        "dreamforge_companion_download.download_missing_companions",
        fake_download,
    )

    result = ensure_creative_task_ready(studio_mode="upscale", upscale_method="omnisr_2x")
    assert result["ready"] is True
    assert result["downloaded_tier_a"] == 1
    assert len(downloaded_batches) == 1
    assert downloaded_batches[0][0]["id"] == "upscaler_omnisr_2x"


def test_ensure_creative_task_ready_auto_downloads_tier_b_when_requested(monkeypatch):
    monkeypatch.setattr("dreamforge_workflow_planner.missing_custom_node_pack_entries", lambda *a, **kw: [])
    tier_b = enrich_missing_dependency(
        {
            "id": "pid_flux1_4k_model",
            "relative": "diffusion_models/pid_flux1_1024_to_4096_4step_mxfp8.safetensors",
            "url": "https://example.com/pid.safetensors",
            "min_bytes": 1024 * 1024 * 1024,
        }
    )
    collect_passes = [[tier_b], []]

    def fake_collect(**kwargs):
        return None, collect_passes.pop(0)

    downloaded_batches: list[list[dict]] = []

    def fake_download(missing):
        downloaded_batches.append(list(missing))
        return {"downloaded": len(missing), "errors": [], "results": [], "status": "ok"}

    monkeypatch.setattr(
        "dreamforge_companion_download._collect_task_missing",
        fake_collect,
    )
    monkeypatch.setattr(
        "dreamforge_companion_download.download_missing_companions",
        fake_download,
    )

    result = ensure_creative_task_ready(
        studio_mode="upscale",
        upscale_method="pid_flux1_4k",
        auto_download_tier_b=True,
    )
    assert result["ready"] is True
    assert result["downloaded_tier_b"] == 1
    assert downloaded_batches[0][0]["id"] == "pid_flux1_4k_model"


def test_ensure_creative_task_ready_skips_node_setup_without_packs(monkeypatch):
    backend_calls: list[str] = []

    monkeypatch.setattr(
        "dreamforge_companion_download._collect_task_missing",
        lambda **kwargs: (None, []),
    )
    monkeypatch.setattr(
        "dreamforge_workflow_planner.required_custom_node_pack_ids",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "dreamforge_comfy_install.ensure_dreamforge_comfy_backend",
        lambda **kwargs: backend_calls.append("backend"),
    )
    monkeypatch.setattr(
        "dreamforge_comfy_server.fetch_comfy_object_info",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("object_info should not run")),
    )

    result = ensure_creative_task_ready(model_name="ideogram4_fp8_scaled.safetensors")
    assert result["ready"] is True
    assert backend_calls == []


def test_ensure_creative_task_ready_can_install_nodes(monkeypatch):
    install_calls: list[str] = []

    monkeypatch.setattr(
        "dreamforge_companion_download._collect_task_missing",
        lambda **kwargs: (None, []),
    )
    monkeypatch.setattr(
        "dreamforge_workflow_planner.required_custom_node_pack_ids",
        lambda **kwargs: ["ComfyUI_UltimateSDUpscale"],
    )

    def fake_missing_entries(pack_ids, *, object_info=None):
        if object_info is None:
            return [{"pack_id": "ComfyUI_UltimateSDUpscale"}]
        return []

    monkeypatch.setattr(
        "dreamforge_workflow_planner.missing_custom_node_pack_entries",
        fake_missing_entries,
    )
    monkeypatch.setattr(
        "dreamforge_comfy_install.ensure_comfyui_checkout",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "dreamforge_comfy_install.ensure_comfyui_python_deps",
        lambda **kwargs: None,
    )

    def fake_install(entry, *, progress=None):
        install_calls.append(str(entry["id"]))
        if progress:
            progress(f"installed {entry['id']}")

    monkeypatch.setattr(
        "dreamforge_workflow_planner._recipe_entry_for_pack",
        lambda pack_id: {
            "id": pack_id,
            "url": "https://example.com/repo",
            "version": "abc123",
        },
    )
    monkeypatch.setattr(
        "dreamforge_comfy_install.ensure_custom_node_pack",
        fake_install,
    )
    monkeypatch.setattr(
        "dreamforge_comfy_server.fetch_comfy_object_info",
        lambda **kwargs: {"UltimateSDUpscale": {}},
    )

    result = ensure_creative_task_ready(studio_mode="upscale", auto_install_nodes=True)
    assert result["ready"] is True
    assert install_calls == ["ComfyUI_UltimateSDUpscale"]
    assert result.get("needs_comfy_restart") is True
    assert any("installed ComfyUI_UltimateSDUpscale" in msg for msg in result["node_setup"])


def test_ensure_creative_task_ready_photo_restore_reports_missing_node_packs(monkeypatch):
    monkeypatch.setattr(
        "dreamforge_companion_download._collect_task_missing",
        lambda **kwargs: (None, []),
    )
    monkeypatch.setattr(
        "dreamforge_workflow_planner._custom_node_directory_present",
        lambda _pack: False,
    )
    monkeypatch.setattr(
        "dreamforge_comfy_server.fetch_comfy_object_info",
        lambda **kwargs: {},
    )

    result = ensure_creative_task_ready(
        studio_mode="edit",
        edit_task="photo_restore",
    )

    assert result["ready"] is False
    packs = {item["pack_id"] for item in result["missing_node_packs"]}
    assert packs == {
        "comfyui_controlnet_aux",
        "ComfyUI-Impact-Pack",
        "ComfyUI-Impact-Subpack",
    }
    aux = next(item for item in result["missing_node_packs"] if item["pack_id"] == "comfyui_controlnet_aux")
    assert "DepthAnythingV2Preprocessor" in aux["required_nodes"]
    assert "LineartStandardPreprocessor" in aux["required_nodes"]


def test_cmd_ensure_creative_task_ready_bridge(monkeypatch):
    from dreamforge_desktop_bridge import cmd_ensure_creative_task_ready

    def fake_ensure(**kwargs):
        assert kwargs["auto_download_tier_b"] is True
        assert kwargs["auto_install_nodes"] is True
        assert kwargs["edit_task"] == "photo_restore"
        return {
            "ready": True,
            "missing": [],
            "missing_tier_a": [],
            "missing_tier_b": [],
            "downloaded_tier_a": 1,
            "errors": [],
        }

    monkeypatch.setattr(
        "dreamforge_companion_download.ensure_creative_task_ready",
        fake_ensure,
    )

    payload = cmd_ensure_creative_task_ready(
        {
            "studio_mode": "edit",
            "edit_task": "photo_restore",
            "auto_download_tier_b": True,
            "auto_install_nodes": True,
        }
    )
    assert payload["ok"] is True
    assert payload["ready"] is True
    assert payload["downloaded_tier_a"] == 1


def test_cmd_build_cli_argv_includes_upscale_preset_fields():
    from dreamforge_desktop_bridge import cmd_build_cli_argv

    payload = cmd_build_cli_argv(
        {
            "upscale_image": "D:/tmp/source.png",
            "upscale_method": "ultimate_sd_upscale",
            "upscale_preset": "fast_4x",
            "upscale_by": 4,
            "upscale_denoise": 0.2,
            "upscale_tile_width": 1024,
            "upscale_tile_padding": 64,
            "upscale_force_uniform_tiles": True,
        }
    )
    argv = payload["argv"]
    assert "--upscale-preset" in argv
    assert argv[argv.index("--upscale-preset") + 1] == "fast_4x"
    assert "--upscale-by" in argv
    assert argv[argv.index("--upscale-by") + 1] == "4"
    assert "--upscale-force-uniform-tiles" in argv

