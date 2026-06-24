"""ComfyUI readiness helpers for Ideogram 4 (core nodes ship in ComfyUI >= v0.24.0)."""

from __future__ import annotations

import os
from typing import Any

# Pinned ComfyUI release (Ideogram 4 nodes + Krea 2 CLIPLoader type).
DREAMFORGE_COMFY_VERSION = "f6c162ddcfbd7eefb39c06fe5b8d4c46e8d09f40"  # v0.26.0
IDEOGRAM4_COMFY_VERSION = DREAMFORGE_COMFY_VERSION
KREA2_MIN_COMFY_VERSION = DREAMFORGE_COMFY_VERSION

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
