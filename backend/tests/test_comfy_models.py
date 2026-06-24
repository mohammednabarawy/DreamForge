"""Tests for Comfy model name resolution."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from dreamforge_comfy_models import (
    ComfyModelResolutionError,
    _basename_match,
    _object_info_options,
    _qwen_companion_basenames_on_disk,
    resolve_comfy_model_loader_args,
)


def test_basename_match_case_insensitive():
    assert _basename_match("CLIP_L.SAFETENSORS", ["clip_l.safetensors"]) == "clip_l.safetensors"


def test_object_info_options_extracts_choices():
    info = {
        "UNETLoader": {
            "input": {
                "required": {
                    "unet_name": [["a.safetensors", "b.safetensors"], {}],
                }
            }
        }
    }
    assert _object_info_options(info, "UNETLoader", "unet_name") == ["a.safetensors", "b.safetensors"]


def test_resolve_flux_split_loaders_from_object_info():
    client = SimpleNamespace(
        object_info=lambda: {
            "UNETLoader": {
                "input": {"required": {"unet_name": [["flux1-dev-kontext_fp8_scaled.safetensors"], {}]}}
            },
            "DualCLIPLoader": {
                "input": {
                    "required": {
                        "clip_name1": [["clip_l.safetensors"], {}],
                        "clip_name2": [["t5xxl_fp8_e4m3fn_scaled.safetensors"], {}],
                    }
                }
            },
            "VAELoader": {"input": {"required": {"vae_name": [["ae.safetensors", "pixel_space"], {}]}}},
        }
    )
    model = {
        "category": "diffusion_models",
        "relative_path": "flux1-dev-kontext_fp8_scaled.safetensors",
        "name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "family": "flux_kontext",
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "dreamforge_comfy_models.companion_file_present",
            lambda req: True,
        )
        mp.setattr(
            "dreamforge_comfy_models._flux_companion_basenames_on_disk",
            lambda family: {
                "clip_l": "clip_l.safetensors",
                "t5": "t5xxl_fp8_e4m3fn_scaled.safetensors",
                "vae": "ae.safetensors",
            },
        )
        mp.setattr("dreamforge_comfy_models.check_model_dependencies", lambda m: [])

        args = resolve_comfy_model_loader_args(
            client,
            model=model,
            model_family="flux_kontext",
        )

    assert args["unet_name"] == "flux1-dev-kontext_fp8_scaled.safetensors"
    assert args["clip_l"] == "clip_l.safetensors"
    assert args["t5"] == "t5xxl_fp8_e4m3fn_scaled.safetensors"
    assert args["vae"] == "ae.safetensors"


def test_write_extra_model_paths_uses_resolved_absolute_base(tmp_path, monkeypatch):
    import dreamforge_comfy_server as srv

    target = (tmp_path / "krita_models").resolve()
    target.mkdir()
    (target / "diffusion_models").mkdir()
    monkeypatch.setattr(srv, "resolved_models_root", lambda: target)
    yaml_path = srv.write_dreamforge_extra_model_paths_config(tmp_path / "comfy")
    text = yaml_path.read_text(encoding="utf-8")
    assert target.as_posix() in text


def test_resolve_qwen_split_loaders_from_object_info():
    client = SimpleNamespace(
        object_info=lambda: {
            "UNETLoader": {
                "input": {
                    "required": {
                        "unet_name": [["qwen_image_edit_2509_fp8_e4m3fn.safetensors"], {}],
                    }
                }
            },
            "CLIPLoader": {
                "input": {
                    "required": {
                        "clip_name": [["qwen_2.5_vl_7b_fp8_scaled.safetensors"], {}],
                    }
                }
            },
            "VAELoader": {
                "input": {
                    "required": {
                        "vae_name": [["qwen_image_vae.safetensors"], {}],
                    }
                }
            },
        }
    )
    model = {
        "category": "diffusion_models",
        "relative_path": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
        "name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
        "family": "qwen_image_edit",
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("dreamforge_comfy_models.companion_file_present", lambda req: True)
        mp.setattr(
            "dreamforge_comfy_models._qwen_companion_basenames_on_disk",
            lambda family: {
                "clip": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
                "vae": "qwen_image_vae.safetensors",
            },
        )
        mp.setattr("dreamforge_comfy_models.check_model_dependencies", lambda m: [])

        args = resolve_comfy_model_loader_args(
            client,
            model=model,
            model_family="qwen_image_edit",
        )

    assert args["unet_name"] == "qwen_image_edit_2509_fp8_e4m3fn.safetensors"
    assert args["clip"] == "qwen_2.5_vl_7b_fp8_scaled.safetensors"
    assert args["vae"] == "qwen_image_vae.safetensors"


def test_resolve_z_image_does_not_pick_qwen_image_companions():
    """Z-Image must load the Qwen3-4B encoder + Flux AE VAE, never the Qwen-Image
    encoder/VAE. The Qwen-Image VAE is a Wan-style video VAE that yields a 5D
    latent, crashing NextDiT with 'too many values to unpack (expected 4)'.
    Regression: both companion sets are present in ComfyUI's lists."""
    client = SimpleNamespace(
        object_info=lambda: {
            "UNETLoader": {
                "input": {"required": {"unet_name": [["z_image_turbo_fp8_e4m3fn.safetensors"], {}]}}
            },
            "CLIPLoader": {
                "input": {
                    "required": {
                        "clip_name": [
                            [
                                "qwen_2.5_vl_7b_fp8_scaled.safetensors",
                                "qwen_3_4b.safetensors",
                            ],
                            {},
                        ]
                    }
                }
            },
            "CLIPLoaderGGUF": {"input": {"required": {"clip_name": [[], {}]}}},
            "VAELoader": {
                "input": {
                    "required": {
                        "vae_name": [["ae.safetensors", "qwen_image_vae.safetensors"], {}]
                    }
                }
            },
        }
    )
    model = {
        "category": "diffusion_models",
        "relative_path": "z_image_turbo_fp8_e4m3fn.safetensors",
        "name": "z_image_turbo_fp8_e4m3fn.safetensors",
        "family": "z_image",
    }

    with pytest.MonkeyPatch.context() as mp:
        # Simulate an environment where the Qwen-Image companions are also on disk;
        # the z_image resolver must still ignore them.
        mp.setattr("dreamforge_comfy_models.companion_file_present", lambda req: True)
        mp.setattr("dreamforge_comfy_models.check_model_dependencies", lambda m: [])

        args = resolve_comfy_model_loader_args(client, model=model, model_family="z_image")

    assert args["clip"] == "qwen_3_4b.safetensors"
    assert args["vae"] == "ae.safetensors"


def test_resolve_krea2_split_loaders_from_object_info():
    """Krea 2 OSS loads via UNETLoader + CLIPLoader(type=krea2) + Qwen Image VAE."""
    client = SimpleNamespace(
        object_info=lambda: {
            "UNETLoader": {
                "input": {"required": {"unet_name": [["krea2_turbo_fp8_scaled.safetensors"], {}]}}
            },
            "CLIPLoader": {
                "input": {
                    "required": {
                        "clip_name": [["qwen3vl_4b_fp8_scaled.safetensors"], {}],
                        "type": [["stable_diffusion", "qwen_image", "krea2"], {}],
                    }
                }
            },
            "CLIPLoaderGGUF": {"input": {"required": {"clip_name": [[], {}]}}},
            "VAELoader": {
                "input": {"required": {"vae_name": [["qwen_image_vae.safetensors"], {}]}}
            },
        }
    )
    model = {
        "category": "diffusion_models",
        "relative_path": "krea2_turbo_fp8_scaled.safetensors",
        "name": "krea2_turbo_fp8_scaled.safetensors",
        "family": "krea2",
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("dreamforge_comfy_models.companion_file_present", lambda req: True)
        mp.setattr(
            "dreamforge_comfy_models._krea2_companion_basenames_on_disk",
            lambda family: {
                "clip": "qwen3vl_4b_fp8_scaled.safetensors",
                "vae": "qwen_image_vae.safetensors",
            },
        )
        mp.setattr("dreamforge_comfy_models.check_model_dependencies", lambda m: [])

        args = resolve_comfy_model_loader_args(client, model=model, model_family="krea2")

    assert args["unet_name"] == "krea2_turbo_fp8_scaled.safetensors"
    assert args["clip"] == "qwen3vl_4b_fp8_scaled.safetensors"
    assert args["vae"] == "qwen_image_vae.safetensors"


def test_resolve_krea2_fails_when_comfyui_too_old():
    client = SimpleNamespace(
        object_info=lambda: {
            "UNETLoader": {
                "input": {"required": {"unet_name": [["krea2_turbo_fp8_scaled.safetensors"], {}]}}
            },
            "CLIPLoader": {
                "input": {
                    "required": {
                        "clip_name": [["qwen3vl_4b_fp8_scaled.safetensors"], {}],
                        "type": [["stable_diffusion", "qwen_image"], {}],
                    }
                }
            },
            "VAELoader": {
                "input": {"required": {"vae_name": [["qwen_image_vae.safetensors"], {}]}}
            },
        }
    )
    model = {
        "category": "diffusion_models",
        "relative_path": "krea2_turbo_fp8_scaled.safetensors",
        "name": "krea2_turbo_fp8_scaled.safetensors",
        "family": "krea2",
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("dreamforge_comfy_models.companion_file_present", lambda req: True)
        mp.setattr(
            "dreamforge_comfy_models._krea2_companion_basenames_on_disk",
            lambda family: {
                "clip": "qwen3vl_4b_fp8_scaled.safetensors",
                "vae": "qwen_image_vae.safetensors",
            },
        )
        mp.setattr("dreamforge_comfy_models.check_model_dependencies", lambda m: [])

        with pytest.raises(ComfyModelResolutionError, match="too old for Krea 2"):
            resolve_comfy_model_loader_args(client, model=model, model_family="krea2")


def test_resolve_qwen_gguf_uses_gguf_unet_loader_choices():
    client = SimpleNamespace(
        object_info=lambda: {
            "UNETLoader": {
                "input": {
                    "required": {
                        "unet_name": [["qwen_image_edit_2509_fp8_e4m3fn.safetensors"], {}],
                    }
                }
            },
            "UnetLoaderGGUF": {
                "input": {
                    "required": {
                        "unet_name": [["Qwen_Image_Edit-Q5_1.gguf"], {}],
                    }
                }
            },
            "CLIPLoaderGGUF": {
                "input": {
                    "required": {
                        "clip_name": [["Qwen2.5-VL-7B-Instruct-Q4_K_S.gguf"], {}],
                    }
                }
            },
            "VAELoader": {
                "input": {
                    "required": {
                        "vae_name": [["qwen_image_vae.safetensors"], {}],
                    }
                }
            },
        }
    )
    model = {
        "category": "diffusion_models",
        "relative_path": "Qwen_Image_Edit-Q5_1.gguf",
        "name": "Qwen_Image_Edit-Q5_1.gguf",
        "family": "qwen_image_edit",
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("dreamforge_comfy_models.companion_file_present", lambda req: True)
        mp.setattr(
            "dreamforge_comfy_models._qwen_companion_basenames_on_disk",
            lambda family: {
                "clip": "Qwen2.5-VL-7B-Instruct-Q4_K_S.gguf",
                "vae": "qwen_image_vae.safetensors",
            },
        )
        mp.setattr("dreamforge_comfy_models.check_model_dependencies", lambda m: [])

        args = resolve_comfy_model_loader_args(
            client,
            model=model,
            model_family="qwen_image_edit",
        )

    assert args["unet_name"] == "Qwen_Image_Edit-Q5_1.gguf"
    assert args["clip"] == "Qwen2.5-VL-7B-Instruct-Q4_K_S.gguf"
    assert args["vae"] == "qwen_image_vae.safetensors"


def test_qwen_companion_basenames_do_not_treat_vae_as_clip():
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("dreamforge_comfy_models.companion_file_present", lambda req: True)
        result = _qwen_companion_basenames_on_disk("qwen_image_edit")
    assert result.get("vae") == "qwen_image_vae.safetensors"
    assert result.get("clip") == "qwen_2.5_vl_7b_fp8_scaled.safetensors"


def test_resolve_qwen_checkpoint_loads_explicit_companions():
    client = SimpleNamespace(
        object_info=lambda: {
            "CheckpointLoaderSimple": {
                "input": {
                    "required": {
                        "ckpt_name": [["qwenImage2512Nvfp4_v10.safetensors"], {}],
                    }
                }
            },
            "CLIPLoader": {
                "input": {
                    "required": {
                        "clip_name": [["qwen_2.5_vl_7b_fp8_scaled.safetensors"], {}],
                    }
                }
            },
            "VAELoader": {
                "input": {
                    "required": {
                        "vae_name": [["qwen_image_vae.safetensors"], {}],
                    }
                }
            },
        }
    )
    model = {
        "category": "checkpoints",
        "relative_path": "qwenImage2512Nvfp4_v10.safetensors",
        "name": "qwenImage2512Nvfp4_v10.safetensors",
        "family": "qwen_image",
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "dreamforge_comfy_models._qwen_companion_basenames_on_disk",
            lambda family: {
                "clip": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
                "vae": "qwen_image_vae.safetensors",
            },
        )
        mp.setattr("dreamforge_comfy_models.check_model_dependencies", lambda m: [])

        args = resolve_comfy_model_loader_args(
            client,
            model=model,
            model_family="qwen_image",
        )

    assert args["ckpt_name"] == "qwenImage2512Nvfp4_v10.safetensors"
    assert args["clip"] == "qwen_2.5_vl_7b_fp8_scaled.safetensors"
    assert args["vae"] == "qwen_image_vae.safetensors"


def test_resolve_qwen_edit_when_vae_on_disk_but_clip_missing_from_comfy():
    client = SimpleNamespace(
        object_info=lambda: {
            "UNETLoader": {
                "input": {
                    "required": {
                        "unet_name": [["qwen_image_edit_2509_fp8_e4m3fn.safetensors"], {}],
                    }
                }
            },
            "CLIPLoader": {"input": {"required": {"clip_name": [[], {}]}}},
            "VAELoader": {
                "input": {"required": {"vae_name": [["qwen_image_vae.safetensors"], {}]}}
            },
        }
    )
    model = {
        "category": "diffusion_models",
        "relative_path": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
        "name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
        "family": "qwen_image_edit",
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("dreamforge_comfy_models.companion_file_present", lambda req: True)
        mp.setattr(
            "dreamforge_comfy_models._qwen_companion_basenames_on_disk",
            lambda family: {
                "clip": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
                "vae": "qwen_image_vae.safetensors",
            },
        )
        mp.setattr("dreamforge_comfy_models.check_model_dependencies", lambda m: [])

        with pytest.raises(ComfyModelResolutionError, match="Qwen CLIP"):
            resolve_comfy_model_loader_args(
                client,
                model=model,
                model_family="qwen_image_edit",
            )


def test_resolve_raises_when_comfy_sees_no_unets():
    client = SimpleNamespace(
        object_info=lambda: {
            "UNETLoader": {"input": {"required": {"unet_name": [[], {}]}}},
            "DualCLIPLoader": {
                "input": {
                    "required": {
                        "clip_name1": [[], {}],
                        "clip_name2": [[], {}],
                    }
                }
            },
            "VAELoader": {"input": {"required": {"vae_name": [["pixel_space"], {}]}}},
        }
    )
    model = {
        "category": "diffusion_models",
        "relative_path": "flux1-dev-kontext_fp8_scaled.safetensors",
        "name": "flux1-dev-kontext_fp8_scaled.safetensors",
        "family": "flux",
    }

    with pytest.raises(ComfyModelResolutionError):
        resolve_comfy_model_loader_args(client, model=model, model_family="flux")
