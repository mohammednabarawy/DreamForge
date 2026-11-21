"""ComfyUI readiness helpers for Ideogram 4 (core nodes ship in ComfyUI >= v0.24.0)."""

from __future__ import annotations

import os
from typing import Any

# Pinned ComfyUI release (MiniMax H3 Image + Ideogram 4 + Krea 2 + Qwen 2.1).
try:
    from dreamforge_krita_recipes import COMFY_INSTALL_RECIPE as _COMFY_RECIPE

    DREAMFORGE_COMFY_VERSION = str(
        _COMFY_RECIPE.get("comfy_version") or "a277b5bf213e8a44fa34817b7770b54f86ef4cea"
    )
    DREAMFORGE_COMFY_VERSION_LABEL = str(_COMFY_RECIPE.get("comfy_version_label") or "v0.46.0")
except Exception:
    DREAMFORGE_COMFY_VERSION = "a277b5bf213e8a44fa34817b7770b54f86ef4cea"  # v0.46.0
    DREAMFORGE_COMFY_VERSION_LABEL = "v0.46.0"

IDEOGRAM4_COMFY_VERSION = DREAMFORGE_COMFY_VERSION
KREA2_MIN_COMFY_VERSION = DREAMFORGE_COMFY_VERSION
MINIMAX_H3_MIN_COMFY_VERSION = DREAMFORGE_COMFY_VERSION

IDEOGRAM4_CORE_NODES = frozenset(
    {
        "UNETLoader",
        "CFGOverride",
        "CLIPLoader",
        "CLIPTextEncode",
        "ConditioningZeroOut",
        "DualModelGuider",
        "Ideogram4Scheduler",
        "RandomNoise",
        "KSamplerSelect",
        "SamplerCustomAdvanced",
        "VAELoader",
        "VAEDecode",
        "SaveImage",
    }
)

IDEOGRAM4_TXT2IMG_NODES = frozenset({"EmptyFlux2LatentImage"})

IDEOGRAM4_EDIT_NODES = frozenset(
    {
        "LoadImage",
        "VAEEncode",
        "AddNoise",
        "SplitSigmasDenoise",
        "ImageToMask",
        "VAEEncodeForInpaint",
    }
)


def ideogram4_nodes_for_kind(kind: str) -> frozenset[str]:
    from dreamforge_prompt.ideogram4_workflows import (
        IDEOGRAM4_WORKFLOW_IMG2IMG,
        IDEOGRAM4_WORKFLOW_INPAINT,
    )

    required = set(IDEOGRAM4_CORE_NODES)
    if kind == IDEOGRAM4_WORKFLOW_IMG2IMG:
        required |= IDEOGRAM4_EDIT_NODES - {"VAEEncodeForInpaint", "ImageToMask"}
    elif kind == IDEOGRAM4_WORKFLOW_INPAINT:
        required |= IDEOGRAM4_EDIT_NODES - {"VAEEncode"}
    else:
        required |= IDEOGRAM4_TXT2IMG_NODES
    return frozenset(required)


def missing_ideogram4_nodes(object_info: dict[str, Any], kind: str) -> list[str]:
    available = set(object_info.keys())
    return sorted(node for node in ideogram4_nodes_for_kind(kind) if node not in available)


def ideogram4_comfy_ready(object_info: dict[str, Any], kind: str) -> bool:
    return not missing_ideogram4_nodes(object_info, kind)


def ideogram4_edit_disabled() -> bool:
    return os.environ.get("DREAMFORGE_DISABLE_IDEOGRAM4_EDIT", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
