"""Tests for Comfy model name resolution."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from dreamforge_comfy_models import (
    ComfyModelResolutionError,
    _basename_match,
    _object_info_options,
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
