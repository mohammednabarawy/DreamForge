"""ComfyUI readiness helpers for Ideogram 4 (core nodes ship in ComfyUI >= v0.24.0)."""

from __future__ import annotations

import os
from typing import Any

# ComfyUI tag that introduced Ideogram 4 core nodes.
IDEOGRAM4_COMFY_VERSION = "ba9ffa0a2b70250a2945e7cdca5d72febc53df51"  # v0.24.1

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
