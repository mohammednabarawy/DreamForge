"""Architecture and role classifier for DreamForge models.

Reads the safetensors header (no tensor data, no GPU) and decides:

  * **role**   – what kind of model file this is
                 (checkpoint / diffusion_model / vae / text_encoder / lora /
                 controlnet / clip_vision / upscale_model / embedding / unknown)
  * **family** – which architecture family
                 (sdxl / sd15 / sd3 / flux / flux_kontext / flux2 / hidream /
                  hidream_o1 / qwen_image / qwen_image_edit / wan / z_image /
                  hunyuan / unknown)
  * **target_dir** – the canonical ComfyUI subfolder

Detection priority is:

  1. Tensor-key signatures from the safetensors header (high confidence).
  2. File-size + filename heuristics (medium confidence).
  3. Filename only (low confidence – ckpt/pt/pth/bin/gguf fall through here).

The classifier never loads tensors and only reads ~64 KB from disk per file.

Used by ``backend/modules/model_organizer.py`` and exposed via the
``dreamforge_cli_inventory`` CLI.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

SAFETENSORS_HEADER_LIMIT = 64 * 1024 * 1024  # 64 MiB – upstream Comfy / HF cap
GGUF_MAGIC = b"GGUF"

# Folder names follow ComfyUI canonical layout (folder_paths.py).
ROLE_TO_FOLDER = {
    "checkpoint": "checkpoints",
    "diffusion_model": "diffusion_models",
    "vae": "vae",
    "text_encoder": "text_encoders",
    "clip_vision": "clip_vision",
    "lora": "loras",
    "controlnet": "controlnet",
    "upscale_model": "upscale_models",
    "embedding": "embeddings",
    "inpaint": "inpaint",
    "ipadapter": "ipadapter",
    "unknown": "",
}

# DreamForge keeps two legacy aliases that ComfyUI still scans.
LEGACY_ALIAS = {
    "unet": "diffusion_models",
    "clip": "text_encoders",
}

# Non-standard but well-known ComfyUI extension folders. Files inside these
# folders are LEFT ALONE by the auto-organizer (they belong to specialised
# loaders that ComfyUI nodes look for by exact folder name).
PRESERVED_EXTENSION_FOLDERS = frozenset({
    "ipadapter",
    "gligen",
    "photomaker",
    "style_models",
    "hypernetworks",
    "faceswap",
    "face_restore",
    "insightface",
    "sams",
    "sam",
    "ultralytics",
    "onnx",
    "model_patches",
    "latent_upscale_models",
    "rmbg",
    "RMBG",
    "segformer_b2_clothes",
    "CatVTON",
    "catvton",
    "LLM",
    "llm",
    "prompt_expansion",
    "safety_checker",
    "vitmatte",
    "luts",
    "diffusers",
    "diffusers_cache",
    "vae_approx",
    "configs",
    "inbox",
})

ALL_TARGET_FOLDERS = (
    frozenset(ROLE_TO_FOLDER.values())
    | frozenset(LEGACY_ALIAS.keys())
    | PRESERVED_EXTENSION_FOLDERS
)


def _filename_tokens(name: str) -> set[str]:
    lowered = (name or "").lower()
    return set(re.findall(r"[a-z0-9]+", lowered))


@dataclass
class ModelClassification:
    """Result of classifying a single model file."""

    path: Path
    role: str = "unknown"
    family: str = "unknown"
    target_dir: str = ""
    confidence: str = "low"  # low | medium | high
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    size_mb: float = 0.0
    needs_review: bool = False
    role_from_header: bool = False
    family_from_header: bool = False

    @property
    def role_matches_location(self) -> bool:
        """True when the file already lives in its canonical folder."""
        if not self.target_dir:
            return True
        try:
            relative = self.path.relative_to(self.path.parents[1])  # ".../<folder>/..."
        except (IndexError, ValueError):
            return False
        parts = relative.parts
        if not parts:
            return False
        first = parts[0]
        if first == self.target_dir:
            return True
        if first in LEGACY_ALIAS and LEGACY_ALIAS[first] == self.target_dir:
            return True
        return False

    def as_dict(self) -> dict:
        return {
            "path": str(self.path),
            "name": self.path.name,
            "role": self.role,
            "family": self.family,
            "target_dir": self.target_dir,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "size_mb": round(self.size_mb, 2),
            "needs_review": self.needs_review,
            "in_canonical_location": self.role_matches_location,
            "role_from_header": self.role_from_header,
            "family_from_header": self.family_from_header,
        }


# --------------------------------------------------------------------------- #
# Header reader (safetensors)
# --------------------------------------------------------------------------- #

def read_safetensors_header(path: Path) -> dict | None:
    """Return the metadata dict from a safetensors header, or None if invalid.

    The header layout is: 8 little-endian bytes (header length), then a UTF-8
    JSON blob whose top-level keys are tensor names plus an optional
    ``__metadata__`` block.  We only read the bytes we need.
    """
    try:
        with path.open("rb") as handle:
            raw_len = handle.read(8)
            if len(raw_len) != 8:
                return None
            header_len = int.from_bytes(raw_len, "little", signed=False)
            if header_len <= 0 or header_len > SAFETENSORS_HEADER_LIMIT:
                return None
            blob = handle.read(header_len)
            if len(blob) != header_len:
                return None
        return json.loads(blob.decode("utf-8", errors="replace"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def _tensor_keys(header: dict | None) -> list[str]:
    if not header:
        return []
    return [key for key in header.keys() if key != "__metadata__"]


def _has_key_prefix(keys: Sequence[str], *prefixes: str) -> bool:
    return any(any(key.startswith(prefix) for prefix in prefixes) for key in keys)


def _has_key_contains(keys: Sequence[str], *needles: str) -> bool:
    return any(any(needle in key for needle in needles) for key in keys)


# --------------------------------------------------------------------------- #
# Family detectors
# --------------------------------------------------------------------------- #

def _family_from_keys(keys: Sequence[str], filename_tokens: set[str]) -> tuple[str, list[str]]:
    """Return (family, reasons) inferred from tensor keys.

    The order of checks is significant – stricter signatures win.
    """
    reasons: list[str] = []

    if _has_key_contains(keys, "double_stream_modulation_img.lin.weight"):
        reasons.append("tensor 'double_stream_modulation_img.lin.weight' is Flux 2")
        return "flux2", reasons

    if _has_key_contains(
        keys,
        "model.diffusion_model.double_blocks.",
        "model.diffusion_model.single_blocks.",
        "diffusion_model.double_blocks.",
        "diffusion_model.single_blocks.",
        "lora_unet_double_blocks_",
        "lora_unet_single_blocks_",
    ):
        family = "flux"
        if "kontext" in filename_tokens:
            family = "flux_kontext"
            reasons.append("Flux double/single blocks + 'kontext' in filename")
        else:
            reasons.append("Flux double/single blocks tensor keys")
        return family, reasons

    if _has_key_contains(
        keys,
        "joint_blocks.",
        "model.diffusion_model.joint_blocks.",
    ):
        reasons.append("SD3 joint_blocks tensor keys")
        return "sd3", reasons

    if _has_key_contains(
        keys,
        "conditioner.embedders.1.",
        "lora_te2_",
        "text_encoder_2",
    ):
        reasons.append("SDXL dual-text-encoder signature")
        return "sdxl", reasons

    if _has_key_contains(
        keys,
        "model.diffusion_model.label_emb.",
        "cond_stage_model.model.transformer.resblocks",
    ):
        reasons.append("SDXL label_emb / OpenCLIP-G signature")
        return "sdxl", reasons

    if _has_key_contains(keys, "transformer_blocks.") and (
        _has_key_contains(keys, "ff_net.", "img_in.", "img_mlp.", "img_in.", "txt_in.", "txt_norm.")
        or "qwen" in filename_tokens
    ):
        family = "qwen_image_edit" if "edit" in filename_tokens else "qwen_image"
        reasons.append("MMDiT transformer_blocks (+ Qwen hints) detected")
        return family, reasons

    # Diffusers-format Flux DiT (used by svdq fp4 / community quantisations)
    if _has_key_prefix(keys, "single_transformer_blocks.", "transformer_blocks.") and _has_key_prefix(
        keys, "x_embedder.", "context_embedder.", "time_text_embed."
    ):
        if "kontext" in filename_tokens:
            return "flux_kontext", ["diffusers DiT (single+double blocks) + 'kontext' in filename"]
        return "flux", ["diffusers DiT (single+double blocks)"]

    # Z-Image (top-level layers/cap_embedder/noise_refiner)
    if _has_key_prefix(keys, "cap_embedder.", "noise_refiner."):
        return "z_image", ["Z-Image top-level MMDiT (cap_embedder / noise_refiner)"]

    if _has_key_prefix(keys, "diffusion_model.") and not _has_key_prefix(keys, "model.diffusion_model."):
        if "wan" in filename_tokens:
            reasons.append("'diffusion_model.' prefix + 'wan' in filename")
            return "wan", reasons
        if "z" in filename_tokens or "zimage" in filename_tokens:
            reasons.append("'diffusion_model.' prefix + 'z-image' in filename")
            return "z_image", reasons
        reasons.append("'diffusion_model.' prefix (Wan / video-DiT)")
        return "wan", reasons

    if _has_key_contains(
        keys,
        "model.diffusion_model.input_blocks.",
        "cond_stage_model.transformer.text_model",
        "cond_stage_model.transformer.embeddings",
    ):
        reasons.append("SD 1.x input_blocks / cond_stage_model signature")
        return "sd15", reasons

    return "unknown", reasons


def _family_from_filename(name: str) -> tuple[str, list[str]]:
    """Lowest-confidence fallback (used for GGUF / ckpt / pt files)."""
    lowered = (name or "").lower()
    reasons: list[str] = []
    if "qwen" in lowered:
        family = "qwen_image_edit" if "edit" in lowered else "qwen_image"
        reasons.append(f"filename hints '{family}'")
        return family, reasons
    if "hidream" in lowered:
        family = "hidream_o1" if ("o1" in lowered or "hidream_o1" in lowered) else "hidream"
        reasons.append(f"filename hints '{family}'")
        return family, reasons
    if "flux" in lowered:
        if "klein" in lowered or "flux-2" in lowered or "flux2" in lowered:
            reasons.append("filename hints 'flux2'")
            return "flux2", reasons
        if "kontext" in lowered:
            reasons.append("filename hints 'flux_kontext'")
            return "flux_kontext", reasons
        reasons.append("filename hints 'flux'")
        return "flux", reasons
    if "sd3" in lowered or "stable-diffusion-3" in lowered:
        reasons.append("filename hints 'sd3'")
        return "sd3", reasons
    if "z-image" in lowered or "z_image" in lowered:
        return "z_image", ["filename hints 'z_image'"]
    if "hunyuan" in lowered:
        return "hunyuan", ["filename hints 'hunyuan'"]
    if "wan" in lowered:
        return "wan", ["filename hints 'wan'"]
    sd15_hints = (
        "sd1.5", "sd15", "v1-5", "v1_5", "v15",
        "dreamshaper_8", "dreamshaper-8", "majicmix", "deliberate",
        "realisticvision", "512-inpainting",
    )
    if any(token in lowered for token in sd15_hints):
        return "sd15", ["filename hints 'sd 1.5'"]
    if "sdxl" in lowered or "xl_base" in lowered or "pony" in lowered:
        return "sdxl", ["filename hints 'sdxl'"]
    return "unknown", reasons


# --------------------------------------------------------------------------- #
# Role detectors
# --------------------------------------------------------------------------- #

_VAE_KEY_PREFIXES = ("first_stage_model.", "vae.")
_VAE_KEY_NEEDLES = ("decoder.up.", "encoder.down.", "decoder.mid.", "encoder.mid.")
_UNET_KEY_PREFIXES = ("model.diffusion_model.", "diffusion_model.")
_CLIP_KEY_PREFIXES = (
    "cond_stage_model.",
    "conditioner.embedders.",
    "text_model.",
    "text_encoder.",
    "text_encoder_2.",
    "transformer.encoder.",
    "embeddings.",
)
_CLIP_VISION_NEEDLES = (
    "vision_model.embeddings.patch_embedding",
    "vision_model.encoder.layers",
    # OpenCLIP-G/H ViT (top-level format used by laion CLIP encoders):
    "visual.transformer.resblocks",
    "visual.positional_embedding",
    "visual.conv1.weight",
    "visual.class_embedding",
)
_LORA_PREFIXES = ("lora_unet_", "lora_te", "lora_te1_", "lora_te2_")
_LORA_NEEDLES = (".lora_A.", ".lora_B.", ".lora_down.", ".lora_up.", ".alpha")
_CONTROLNET_PREFIXES = (
    "control_model.",
    "controlnet_cond_embedding.",
    "controlnet_blocks.",
    "controlnet_x_embedder.",
    "controlnet_down_blocks.",
    "controlnet_mid_block.",
    "input_hint_block.",
)
_CONTROLNET_KEYS = ("lora_controlnet",)  # exact tensor names that mean ControlNet
_IPADAPTER_PREFIXES = ("image_proj.", "ip_adapter.")
_UPSCALER_PREFIXES = ("model.0.weight",)  # Real-ESRGAN / ESRGAN minimal signature
_UPSCALER_NEEDLES = ("model.body.", "RRDB_trunk.", "conv_body.", "conv_first.")
_EMBEDDING_NEEDLES = ("string_to_param", "emb_params", "string_to_token")


def _looks_like_lora(keys: Sequence[str]) -> bool:
    if _has_key_prefix(keys, *_LORA_PREFIXES):
        return True
    if _has_key_contains(keys, *_LORA_NEEDLES):
        return True
    return False


def _looks_like_vae(keys: Sequence[str]) -> bool:
    if _has_key_prefix(keys, *_VAE_KEY_PREFIXES):
        return True
    # bare VAE files: decoder/encoder at top level
    if _has_key_contains(keys, *_VAE_KEY_NEEDLES) and not _has_key_prefix(keys, *_UNET_KEY_PREFIXES):
        return True
    return False


def _looks_like_unet(keys: Sequence[str]) -> bool:
    if _has_key_prefix(keys, *_UNET_KEY_PREFIXES):
        return True
    if _has_key_contains(keys, "double_blocks.", "single_blocks.", "joint_blocks."):
        return True
    # Diffusers-format DiT models (Flux, Qwen-Image, SD3) export tensors at the
    # top level (no ``model.diffusion_model.`` prefix). Recognise their stable
    # building blocks so quantised distributions (svdq-fp4, ggufs, fp8) still
    # classify as diffusion_model.
    diffusers_dit_blocks = (
        "transformer_blocks.",
        "single_transformer_blocks.",
        "x_embedder.",
        "time_text_embed.",
    )
    if _has_key_prefix(keys, *diffusers_dit_blocks):
        return True
    # Z-Image: ``layers.*`` MMDiT + cap_embedder / noise_refiner.
    if _has_key_prefix(keys, "cap_embedder.", "noise_refiner.", "context_refiner."):
        return True
    return False


def _looks_like_text_encoder(keys: Sequence[str]) -> bool:
    if _has_key_prefix(keys, *_CLIP_KEY_PREFIXES) and not _looks_like_unet(keys):
        return True
    return False


def _looks_like_clip_vision(keys: Sequence[str]) -> bool:
    return _has_key_contains(keys, *_CLIP_VISION_NEEDLES)


def _looks_like_controlnet(keys: Sequence[str]) -> bool:
    if _has_key_prefix(keys, *_CONTROLNET_PREFIXES):
        return True
    # Legacy ControlNet (and ControlLoRA) ship `lora_controlnet` + bare
    # `input_blocks.*` tensors – no `model.diffusion_model.` prefix.
    if any(key in _CONTROLNET_KEYS for key in keys):
        return True
    has_bare_input = any(
        key.startswith("input_blocks.") or key.startswith("output_blocks.")
        for key in keys
    )
    has_unet_prefix = _has_key_prefix(keys, *_UNET_KEY_PREFIXES)
    if has_bare_input and not has_unet_prefix:
        return True
    return False


def _looks_like_ipadapter(keys: Sequence[str]) -> bool:
    return _has_key_prefix(keys, *_IPADAPTER_PREFIXES)


def _looks_like_upscaler(keys: Sequence[str]) -> bool:
    if _has_key_prefix(keys, *_UPSCALER_PREFIXES):
        return True
    return _has_key_contains(keys, *_UPSCALER_NEEDLES)


def _looks_like_embedding(keys: Sequence[str]) -> bool:
    return _has_key_contains(keys, *_EMBEDDING_NEEDLES)


def _role_from_keys(keys: Sequence[str]) -> tuple[str, list[str]]:
    reasons: list[str] = []

    # IP-Adapter / ControlNet must win over lora/diffusion detection because
    # they share some tensor namespaces (legacy ControlNet exposes
    # ``input_blocks.*`` and "ControlLoRA" files include ``lora_controlnet``).
    if _looks_like_ipadapter(keys):
        reasons.append("image_proj.* / ip_adapter.* tensor namespace")
        return "ipadapter", reasons
    if _looks_like_controlnet(keys):
        reasons.append("ControlNet signature (control_model.* / lora_controlnet / bare input_blocks)")
        return "controlnet", reasons
    if _looks_like_lora(keys):
        reasons.append("lora_unet_* / .lora_A / .lora_B markers")
        return "lora", reasons
    if _looks_like_clip_vision(keys):
        reasons.append("CLIP-Vision (vision_model / visual.transformer) signature")
        return "clip_vision", reasons
    if _looks_like_upscaler(keys):
        reasons.append("ESRGAN-family tensor shape")
        return "upscale_model", reasons
    if _looks_like_embedding(keys):
        reasons.append("Textual-inversion key markers")
        return "embedding", reasons

    has_unet = _looks_like_unet(keys)
    has_vae = _looks_like_vae(keys)
    has_te = _looks_like_text_encoder(keys)

    if has_unet and (has_vae or has_te):
        reasons.append("UNet + (VAE/text-encoder) tensors → full checkpoint")
        return "checkpoint", reasons
    if has_unet:
        reasons.append("UNet-only tensors → diffusion_model")
        return "diffusion_model", reasons
    if has_vae and not has_te:
        reasons.append("VAE-only tensor namespace")
        return "vae", reasons
    if has_te and not has_unet:
        reasons.append("Text-encoder-only tensor namespace")
        return "text_encoder", reasons

    return "unknown", reasons


# --------------------------------------------------------------------------- #
# Filename / size heuristics (medium / low confidence)
# --------------------------------------------------------------------------- #

_TEXT_ENCODER_NAME_HINTS = (
    "t5xxl",
    "t5-v1_1",
    "t5_v1_1",
    "t5-xxl",
    "umt5",
    "byt5",
    "clip_l",
    "clip-l",
    "clip_g",
    "clip-g",
    "clip_vit-l",
    "openclip",
    "mistral_3_small",
    "mistral-3-small",
    "qwen2.5-vl",
    "qwen2_5_vl",
    "qwen_2.5_vl",
    "qwen_2_5_vl",
    "qwen3-",
    "qwen3_",
    "qwen_3-",
    "qwen_3_",
    "gemma",
    "llama_q",
    "long_clip",
    "long-clip",
)


def _role_from_filename(name: str, size_mb: float) -> tuple[str, list[str]]:
    lowered = (name or "").lower()
    reasons: list[str] = []

    # Order matters – ControlNet / IP-Adapter / CLIP-Vision / text-encoder
    # filename hints must beat the broader role-by-size fallback.
    if "ip-adapter" in lowered or "ipadapter" in lowered or "ip_adapter" in lowered:
        reasons.append("filename hints 'ipadapter'")
        return "ipadapter", reasons
    if (
        "controlnet" in lowered
        or "control_lora" in lowered
        or "control-lora" in lowered
        or lowered.startswith("control_v1")
        or lowered.startswith("control_v11")
        or lowered.startswith("control_sd")
    ):
        reasons.append("filename hints 'controlnet'")
        return "controlnet", reasons
    if "clip_vision" in lowered or "clipvision" in lowered or "image_encoder" in lowered:
        reasons.append("filename hints 'clip_vision'")
        return "clip_vision", reasons
    if any(hint in lowered for hint in _TEXT_ENCODER_NAME_HINTS):
        reasons.append("filename hints 'text_encoder'")
        return "text_encoder", reasons
    if any(token in lowered for token in ("lora", "lycoris", "lokr", "loha")):
        reasons.append("filename hints 'lora'")
        return "lora", reasons
    if any(token in lowered for token in (
        "esrgan", "swinir", "realesrgan", "ldsr", "remacri", "anime6b",
        "upscaler", "upscale_model", "x4-upscaler", "ultrasharp", "_x4_",
        "4x_", "8x_", "nmkd", "omnisr", "hat_sr", "real_hat",
    )):
        reasons.append("filename hints 'upscale_model'")
        return "upscale_model", reasons
    if any(token in lowered for token in ("vae", "_ae.", "/ae.", "kl-f8")):
        reasons.append("filename hints 'vae'")
        return "vae", reasons
    if any(token in lowered for token in (
        "t5xxl", "clip_l.", "clip_g.", "umt5", "byt5", "mistral_3_small",
        "qwen2.5-vl", "qwen_2.5_vl", "gemma", "llama_q",
    )):
        reasons.append("filename hints 'text_encoder'")
        return "text_encoder", reasons
    if "embedding" in lowered or "textual_inversion" in lowered:
        reasons.append("filename hints 'embedding'")
        return "embedding", reasons
    if "inpaint" in lowered and size_mb < 500:
        reasons.append("filename hints 'inpaint' (helper-sized)")
        return "controlnet", reasons

    # Size-based fallback for full vs UNet-only diffusion files.
    if size_mb >= 4_000:
        reasons.append(f"large file ({int(size_mb)} MB) suggests checkpoint/UNet")
        return "checkpoint", reasons
    if size_mb >= 200:
        reasons.append(f"medium file ({int(size_mb)} MB)")
        return "diffusion_model", reasons

    return "unknown", reasons


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def classify_model_file(path: Path) -> ModelClassification:
    """Classify a single weight file.

    Never raises – any error is reported via ``reasons`` / ``needs_review``.
    """
    path = Path(path)
    result = ModelClassification(path=path)

    try:
        result.size_mb = round(path.stat().st_size / (1024 * 1024), 2)
    except OSError as exc:
        result.reasons.append(f"stat() failed: {exc}")
        result.needs_review = True
        return result

    suffix = path.suffix.lower()
    filename_tokens = _filename_tokens(path.name)

    keys: list[str] = []
    if suffix == ".safetensors":
        header = read_safetensors_header(path)
        if header is None:
            result.reasons.append("safetensors header could not be parsed")
            result.needs_review = True
        else:
            keys = _tensor_keys(header)
            result.reasons.append(f"safetensors header parsed ({len(keys)} tensors)")

    elif suffix == ".gguf":
        # We do not parse GGUF yet – only sanity-check the magic number.
        try:
            with path.open("rb") as handle:
                magic = handle.read(4)
            if magic != GGUF_MAGIC:
                result.reasons.append("missing GGUF magic header")
                result.needs_review = True
            else:
                result.reasons.append("GGUF file (header not parsed)")
        except OSError as exc:
            result.reasons.append(f"could not read GGUF file: {exc}")
            result.needs_review = True

    elif suffix in {".ckpt", ".pt", ".pth", ".bin"}:
        result.reasons.append(f"{suffix} format – filename-only heuristics")
        result.needs_review = True

    else:
        result.reasons.append(f"unrecognised extension '{suffix}'")
        result.needs_review = True

    # Role detection: prefer header keys, otherwise filename + size.
    role = "unknown"
    role_from_header = False
    if keys:
        role, role_reasons = _role_from_keys(keys)
        if role != "unknown":
            role_from_header = True
        result.reasons.extend(role_reasons)
    if role == "unknown":
        role, role_reasons = _role_from_filename(path.name, result.size_mb)
        result.reasons.extend(role_reasons)

    # Family detection.
    family = "unknown"
    family_from_header = False
    family_reasons: list[str] = []
    if keys:
        family, family_reasons = _family_from_keys(keys, filename_tokens)
        if family != "unknown":
            family_from_header = True
    if family == "unknown":
        fname_family, fname_reasons = _family_from_filename(path.name)
        if fname_family != "unknown":
            family = fname_family
            family_reasons.extend(fname_reasons)
    result.reasons.extend(family_reasons)

    # Confidence resolution. A verdict is only "high" when BOTH role AND family
    # come from tensor-key signatures – otherwise filename heuristics can flip
    # specialised UNets into "checkpoints" by size alone.
    if role_from_header and family_from_header:
        result.confidence = "high"
    elif role_from_header or family_from_header:
        result.confidence = "medium"
    elif role != "unknown" and family != "unknown":
        result.confidence = "medium"
    else:
        result.confidence = "low"

    result.role_from_header = role_from_header
    result.family_from_header = family_from_header

    # GGUF distributions of Flux / Qwen / HiDream / Wan are UNet-only (the
    # tokenizer + VAE come from companion files). Without a parseable header
    # the size heuristic mistakes them for full checkpoints, so route them to
    # diffusion_models/ whenever we know they're a diffusion family.
    if (
        suffix == ".gguf"
        and role in ("checkpoint", "unknown")
        and family in {
            "flux", "flux_kontext", "flux2",
            "qwen_image", "qwen_image_edit",
            "hidream", "wan", "z_image", "hunyuan", "sd3",
        }
    ):
        role = "diffusion_model"
        result.reasons.append(
            f"GGUF + family={family}: routing to diffusion_models/ (UNet-only quantisation)"
        )

    # HiDream-O1 must live under checkpoints/ regardless of header heuristics
    # because the engine bootstraps an embedded tokenizer.
    if family == "hidream_o1":
        if role in ("diffusion_model", "unknown"):
            role = "checkpoint"
            result.warnings.append(
                "HiDream-O1 needs its bundled tokenizer; placing under checkpoints/."
            )

    # Flux Kontext is structurally identical to Flux – role stays diffusion_model.
    if family == "flux_kontext" and role == "checkpoint":
        # The current Flux Kontext release is UNet-only; if we accidentally
        # classified it as a checkpoint via filename, prefer diffusion_model.
        if not keys or not _looks_like_text_encoder(keys):
            role = "diffusion_model"
            result.reasons.append("Flux Kontext is UNet-only; demoting to diffusion_model")

    result.role = role
    result.family = family
    result.target_dir = ROLE_TO_FOLDER.get(role, "")

    if role == "unknown":
        result.warnings.append("Could not determine role with confidence – please review manually.")
        result.needs_review = True

    return result


def classify_directory(root: Path, extensions: Iterable[str] | None = None) -> list[ModelClassification]:
    """Classify every model file under ``root`` (recursive)."""
    root = Path(root)
    if not root.is_dir():
        return []
    if extensions is None:
        extensions = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf"}
    extensions = {ext.lower() for ext in extensions}
    results: list[ModelClassification] = []
    for entry in sorted(root.rglob("*")):
        if not entry.is_file() or entry.suffix.lower() not in extensions:
            continue
        results.append(classify_model_file(entry))
    return results
