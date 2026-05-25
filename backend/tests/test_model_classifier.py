"""Tests for the model classifier + organizer (no real weights required).

We synthesise the safetensors header layout (8-byte little-endian length +
JSON blob) so the classifier sees realistic tensor keys without us shipping
real model weights inside the repository.
"""
from __future__ import annotations

import json
import os
import struct
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from modules.model_classifier import (  # noqa: E402
    ROLE_TO_FOLDER,
    classify_directory,
    classify_model_file,
    read_safetensors_header,
)
from modules.model_organizer import build_plan, organize_models  # noqa: E402


def _write_safetensors(path: Path, tensor_keys: list[str], *, payload_size_bytes: int = 0) -> None:
    """Write a minimal but well-formed safetensors file with ``tensor_keys``."""
    metadata = {
        key: {"dtype": "F16", "shape": [1], "data_offsets": [i * 2, i * 2 + 2]}
        for i, key in enumerate(tensor_keys)
    }
    metadata["__metadata__"] = {"format": "pt"}
    header = json.dumps(metadata).encode("utf-8")
    body_size = max(len(tensor_keys) * 2, payload_size_bytes)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(struct.pack("<Q", len(header)))
        handle.write(header)
        handle.write(b"\0" * body_size)


# --------------------------------------------------------------------------- #
# Classifier
# --------------------------------------------------------------------------- #


def test_read_safetensors_header_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "tiny.safetensors"
    _write_safetensors(target, ["model.diffusion_model.input_blocks.0.0.weight"])
    header = read_safetensors_header(target)
    assert header is not None
    assert "model.diffusion_model.input_blocks.0.0.weight" in header


def test_classifier_detects_sdxl_checkpoint(tmp_path: Path) -> None:
    target = tmp_path / "sdxl_base.safetensors"
    _write_safetensors(
        target,
        [
            "model.diffusion_model.input_blocks.0.0.weight",
            "model.diffusion_model.label_emb.0.0.weight",
            "conditioner.embedders.0.transformer.text_model.embeddings.token_embedding.weight",
            "conditioner.embedders.1.model.transformer.resblocks.0.attn.in_proj_weight",
            "first_stage_model.encoder.down.0.block.0.norm1.weight",
        ],
    )
    verdict = classify_model_file(target)
    assert verdict.role == "checkpoint"
    assert verdict.family == "sdxl"
    assert verdict.target_dir == "checkpoints"
    assert verdict.confidence == "high"


def test_classifier_detects_flux_unet_only(tmp_path: Path) -> None:
    target = tmp_path / "flux1-dev.safetensors"
    _write_safetensors(
        target,
        [
            "model.diffusion_model.double_blocks.0.img_attn.norm.query_norm.scale",
            "model.diffusion_model.single_blocks.0.linear1.weight",
        ],
    )
    verdict = classify_model_file(target)
    assert verdict.role == "diffusion_model"
    assert verdict.family == "flux"
    assert verdict.target_dir == "diffusion_models"


def test_classifier_detects_flux_kontext_from_filename(tmp_path: Path) -> None:
    target = tmp_path / "flux1-kontext-dev.safetensors"
    _write_safetensors(
        target,
        [
            "model.diffusion_model.double_blocks.0.img_attn.norm.query_norm.scale",
        ],
    )
    verdict = classify_model_file(target)
    assert verdict.family == "flux_kontext"


def test_classifier_detects_diffusers_format_flux_dit(tmp_path: Path) -> None:
    target = tmp_path / "svdq-fp4_r32-flux.1-dev.safetensors"
    _write_safetensors(
        target,
        [
            "x_embedder.proj.weight",
            "context_embedder.weight",
            "time_text_embed.timestep_embedder.linear_1.weight",
            "single_transformer_blocks.0.attn.to_q.weight",
            "transformer_blocks.0.attn.to_q.weight",
        ],
    )
    verdict = classify_model_file(target)
    assert verdict.role == "diffusion_model"
    assert verdict.family == "flux"


def test_classifier_detects_flux_controlnet(tmp_path: Path) -> None:
    target = tmp_path / "FLUX.1-dev-Controlnet-Inpainting.safetensors"
    _write_safetensors(
        target,
        [
            "transformer_blocks.0.attn.to_q.weight",
            "controlnet_blocks.0.weight",
            "controlnet_x_embedder.proj.weight",
        ],
    )
    verdict = classify_model_file(target)
    assert verdict.role == "controlnet"
    assert verdict.target_dir == "controlnet"


def test_classifier_detects_legacy_control_lora(tmp_path: Path) -> None:
    target = tmp_path / "control_lora_rank128_v11p_sd15_depth_fp16.safetensors"
    _write_safetensors(
        target,
        [
            "lora_controlnet",
            "input_blocks.0.0.bias",
            "input_blocks.1.0.emb_layers.1.bias",
        ],
    )
    verdict = classify_model_file(target)
    assert verdict.role == "controlnet"


def test_classifier_detects_ip_adapter(tmp_path: Path) -> None:
    target = tmp_path / "ip-adapter-plus_sdxl.safetensors"
    _write_safetensors(
        target,
        [
            "image_proj.latents",
            "image_proj.layers.0.0.norm1.bias",
            "ip_adapter.1.to_k_ip.weight",
        ],
    )
    verdict = classify_model_file(target)
    assert verdict.role == "ipadapter"
    assert verdict.target_dir == "ipadapter"


def test_classifier_detects_lora_unet(tmp_path: Path) -> None:
    target = tmp_path / "some_style_v1.safetensors"
    _write_safetensors(
        target,
        [
            "lora_unet_down_blocks_0_attentions_0_proj_in.lora_down.weight",
            "lora_unet_down_blocks_0_attentions_0_proj_in.lora_up.weight",
            "lora_unet_down_blocks_0_attentions_0_proj_in.alpha",
        ],
    )
    verdict = classify_model_file(target)
    assert verdict.role == "lora"
    assert verdict.target_dir == "loras"


def test_classifier_detects_openclip_vision(tmp_path: Path) -> None:
    target = tmp_path / "CLIP-ViT-H-14-laion2B.safetensors"
    _write_safetensors(
        target,
        [
            "visual.conv1.weight",
            "visual.class_embedding",
            "visual.transformer.resblocks.0.attn.in_proj_weight",
            "transformer.resblocks.0.attn.in_proj_weight",
        ],
    )
    verdict = classify_model_file(target)
    assert verdict.role == "clip_vision"
    assert verdict.target_dir == "clip_vision"


def test_classifier_falls_back_to_filename_for_unknown_safetensors(tmp_path: Path) -> None:
    target = tmp_path / "t5xxl_fp16.safetensors"
    _write_safetensors(target, ["unknown.tensor.key"])
    verdict = classify_model_file(target)
    assert verdict.role == "text_encoder"
    assert verdict.target_dir == "text_encoders"


def test_classifier_routes_gguf_diffusion_to_diffusion_models(tmp_path: Path) -> None:
    target = tmp_path / "flux1-krea-dev-Q8_0.gguf"
    target.write_bytes(b"GGUF" + b"\0" * 16)
    verdict = classify_model_file(target)
    assert verdict.role == "diffusion_model"
    assert verdict.family == "flux"


def test_classifier_routes_qwen_text_encoder_gguf_to_text_encoders(tmp_path: Path) -> None:
    target = tmp_path / "qwen_2.5_vl_7b_edit-q2_k.gguf"
    target.write_bytes(b"GGUF" + b"\0" * 16)
    verdict = classify_model_file(target)
    assert verdict.role == "text_encoder"
    assert verdict.target_dir == "text_encoders"


# --------------------------------------------------------------------------- #
# Organizer
# --------------------------------------------------------------------------- #


def _seed_models_tree(root: Path) -> None:
    """Create a small canonical layout with a couple of misplaced files."""
    # SDXL LoRA dropped into checkpoints/ – should be moved to loras/.
    _write_safetensors(
        root / "checkpoints" / "my_style_lora.safetensors",
        [
            "lora_unet_down_blocks_0_attentions_0_proj_in.lora_down.weight",
            "lora_unet_down_blocks_0_attentions_0_proj_in.lora_up.weight",
            # Family marker so the organizer treats this as a strong-signal move.
            "lora_te2_text_model_encoder_layers_0_mlp_fc1.lora_down.weight",
        ],
    )
    # Legacy clip/ folder: should migrate to text_encoders/.
    _write_safetensors(
        root / "clip" / "clip_l.safetensors",
        ["text_model.embeddings.token_embedding.weight"],
    )
    # Properly placed checkpoint – should be left alone.
    _write_safetensors(
        root / "checkpoints" / "sdxl_base.safetensors",
        [
            "model.diffusion_model.input_blocks.0.0.weight",
            "model.diffusion_model.label_emb.0.0.weight",
            "first_stage_model.encoder.down.0.block.0.norm1.weight",
        ],
    )
    # IP-Adapter mistakenly stored in controlnet/. Filename carries the SDXL
    # family hint so the organizer treats this as a confident move.
    _write_safetensors(
        root / "controlnet" / "ip-adapter-plus_sdxl.safetensors",
        [
            "image_proj.latents",
            "ip_adapter.1.to_k_ip.weight",
            # Add an SDXL marker so the family is inferred from header.
            "conditioner.embedders.1.model.transformer.resblocks.0.attn.in_proj_weight",
        ],
    )
    # Diffusers cache snapshot – classifier should leave it alone.
    _write_safetensors(
        root / "CatVTON" / "sd-vae-ft-mse" / "diffusion_pytorch_model.safetensors",
        ["unknown.key"],
    )
    # Already-canonical IP-Adapter in ipadapter/ – preserved extension folder.
    _write_safetensors(
        root / "ipadapter" / "ip-adapter_face_sdxl.safetensors",
        ["image_proj.latents", "ip_adapter.1.to_k_ip.weight"],
    )


def test_organizer_dry_run_plans_expected_moves(tmp_path: Path) -> None:
    _seed_models_tree(tmp_path)
    plan = build_plan(tmp_path)
    sources_to_move = {
        Path(action.source).name for action in plan.actions if action.will_move
    }
    skipped = {
        Path(action.source).name for action in plan.actions if not action.will_move
    }

    assert "my_style_lora.safetensors" in sources_to_move
    assert "clip_l.safetensors" in sources_to_move
    assert "ip-adapter-plus_sdxl.safetensors" in sources_to_move

    assert "sdxl_base.safetensors" in skipped
    assert "ip-adapter_face_sdxl.safetensors" in skipped  # preserved extension folder
    assert "diffusion_pytorch_model.safetensors" in skipped  # diffusers snapshot


def test_organizer_does_not_move_in_dry_run(tmp_path: Path) -> None:
    _seed_models_tree(tmp_path)
    organize_models(tmp_path, apply=False)
    assert (tmp_path / "checkpoints" / "my_style_lora.safetensors").exists()
    assert (tmp_path / "clip" / "clip_l.safetensors").exists()


def test_organizer_apply_moves_files(tmp_path: Path) -> None:
    _seed_models_tree(tmp_path)
    payload = organize_models(tmp_path, apply=True)
    assert payload["applied"] is True

    # LoRA moved out of checkpoints/ into loras/.
    assert not (tmp_path / "checkpoints" / "my_style_lora.safetensors").exists()
    assert (tmp_path / "loras" / "my_style_lora.safetensors").exists()

    # clip/ migrated to text_encoders/ (legacy alias migration).
    assert not (tmp_path / "clip" / "clip_l.safetensors").exists()
    assert (tmp_path / "text_encoders" / "clip_l.safetensors").exists()

    # IP-Adapter moved from controlnet/ to ipadapter/.
    assert not (tmp_path / "controlnet" / "ip-adapter-plus_sdxl.safetensors").exists()
    assert (tmp_path / "ipadapter" / "ip-adapter-plus_sdxl.safetensors").exists()

    # Properly placed checkpoint untouched.
    assert (tmp_path / "checkpoints" / "sdxl_base.safetensors").exists()
    # Diffusers snapshot untouched.
    assert (tmp_path / "CatVTON" / "sd-vae-ft-mse" / "diffusion_pytorch_model.safetensors").exists()


def test_organizer_handles_missing_root(tmp_path: Path) -> None:
    bogus = tmp_path / "does_not_exist"
    plan = build_plan(bogus)
    assert plan.actions == []
    assert plan.errors


def test_role_to_folder_is_complete() -> None:
    assert "checkpoint" in ROLE_TO_FOLDER
    assert "diffusion_model" in ROLE_TO_FOLDER
    assert "ipadapter" in ROLE_TO_FOLDER
    assert "unknown" in ROLE_TO_FOLDER
    assert ROLE_TO_FOLDER["ipadapter"] == "ipadapter"
