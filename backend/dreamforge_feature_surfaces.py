"""Registry of UI-exposed feature surfaces and backend handlers (audit + tests)."""

from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]

# Values exposed in desktop UI (tauri-api + panels).
UI_REFERENCE_ROLES = frozenset(
    {"image_prompt", "restyle", "source_edit", "inpaint", "upscale", "structure"}
)
UI_INPAINT_INTENTS = frozenset({"default", "improve_detail", "modify_content"})
UI_VARY_AMOUNTS = frozenset({"subtle", "strong"})
UI_UPSCALE_PRESETS = frozenset({"1.5x", "2x", "fast_2x"})
UI_IDENTITY_MODES = frozenset(
    {"preserve_face", "kontext", "qwen_edit", "ipadapter_faceid", "auto"}
)
UI_ENHANCE_TARGETS = frozenset({"face", "hands", "eyes", "auto"})

# comfy_workflow_mode + _build_comfy_prompt_graph modes.
BACKEND_COMFY_MODES = frozenset(
    {
        "txt2img",
        "img2img",
        "kontext",
        "inpaint",
        "upscale",
        "ipadapter",
        "ipadapter_faceid",
        "ipadapter_controlnet",
        "controlnet",
        "face_detail",
        "outpaint",
        "hires",
        "area_composition",
        "qwen_edit",
    }
)

# Modes intentionally advanced/agent-only (not required from main studio tabs).
ADVANCED_ONLY_COMFY_MODES = frozenset({"hires", "area_composition", "outpaint"})

# UI path -> comfy modes each surface should resolve to.
UI_SURFACE_TO_COMFY_MODES: dict[str, frozenset[str]] = {
    "reference_role:image_prompt": frozenset({"ipadapter", "ipadapter_faceid"}),
    "reference_role:restyle": frozenset({"img2img", "kontext", "qwen_edit"}),
    "reference_role:structure": frozenset({"controlnet", "ipadapter_controlnet"}),
    "reference_role:source_edit": frozenset({"kontext", "qwen_edit", "img2img"}),
    "reference_role:inpaint": frozenset({"inpaint"}),
    "reference_role:upscale": frozenset({"upscale"}),
    "studio_mode:generate": frozenset({"txt2img", "img2img", "ipadapter", "ipadapter_controlnet", "ipadapter_faceid"}),
    "studio_mode:edit": frozenset({"kontext", "qwen_edit", "img2img"}),
    "studio_mode:inpaint": frozenset({"inpaint"}),
    "studio_mode:upscale": frozenset({"upscale"}),
    "inpaint_intent:default": frozenset({"inpaint"}),
    "inpaint_intent:improve_detail": frozenset({"inpaint"}),
    "inpaint_intent:modify_content": frozenset({"inpaint"}),
    "vary_amount:subtle": frozenset({"img2img"}),
    "vary_amount:strong": frozenset({"img2img"}),
    "upscale_preset:1.5x": frozenset({"upscale"}),
    "upscale_preset:2x": frozenset({"upscale"}),
    "upscale_preset:fast_2x": frozenset({"upscale"}),
    "enhance_target:face": frozenset({"face_detail"}),
    "enhance_target:hands": frozenset({"face_detail"}),
    "enhance_target:eyes": frozenset({"inpaint"}),
    "identity_mode:preserve_face": frozenset({"kontext", "qwen_edit", "img2img"}),
    "identity_mode:ipadapter_faceid": frozenset({"ipadapter_faceid", "kontext", "qwen_edit"}),
}

COMFY_MODE_GRAPH_BUILDERS: dict[str, str] = {
    "hires": "comfy_hires_two_pass",
    "area_composition": "comfy_area_composition",
    "ipadapter": "comfy_ipadapter_reference",
    "ipadapter_faceid": "comfy_ipadapter_faceid_reference",
    "ipadapter_controlnet": "comfy_ipadapter_controlnet_hybrid",
    "face_detail": "comfy_face_detail_basic",
    "controlnet": "comfy_controlnet_basic",
    "outpaint": "comfy_outpaint_basic",
    "upscale": "comfy_ultimate_sd_upscale",
    "inpaint": "comfy_inpaint_basic",
    "kontext": "comfy_flux_kontext_edit",
    "img2img": "comfy_img2img_basic",
    "txt2img": "comfy_txt2img_basic",
    "qwen_edit": "comfy_qwen_image_edit",
}

ASSET_GATED_FEATURES = frozenset(
    {
        "ipadapter",
        "ipadapter_faceid",
        "ipadapter_controlnet",
        "face_detail",
    }
)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _backend_has_handler(module: str, symbol: str) -> bool:
    try:
        mod = importlib.import_module(module)
    except ImportError:
        return False
    return callable(getattr(mod, symbol, None))


def audit_ui_enum_backend_coverage() -> list[str]:
    """Ensure each UI enum has a backend module reference."""
    issues: list[str] = []
    checks: list[tuple[frozenset[str], str, str]] = [
        (UI_INPAINT_INTENTS, "dreamforge_inpaint_intent.py", "VALID_INPAINT_INTENTS"),
        (UI_VARY_AMOUNTS, "dreamforge_vary_image.py", "VALID_VARY_AMOUNTS"),
        (UI_UPSCALE_PRESETS, "dreamforge_upscale_presets.py", "VALID_UPSCALE_PRESETS"),
        (UI_REFERENCE_ROLES, "dreamforge_reference_role.py", "VALID_REFERENCE_ROLES"),
        (UI_ENHANCE_TARGETS, "dreamforge_auto_enhance.py", "VALID_ENHANCE_TARGETS"),
    ]
    backend_dir = REPO_ROOT / "backend"
    for values, filename, token in checks:
        text = _read_text(backend_dir / filename)
        if not text:
            issues.append(f"missing backend file for {filename}")
            continue
        for value in values:
            if value not in text:
                issues.append(f"UI value {value!r} not referenced in {filename}")

    return issues


def audit_comfy_mode_graph_builders() -> list[str]:
    issues: list[str] = []
    for mode, builder in COMFY_MODE_GRAPH_BUILDERS.items():
        if not _backend_has_handler("dreamforge_comfy_workflows", builder):
            issues.append(f"comfy mode {mode!r} maps to missing builder {builder}")
    gen_text = _read_text(REPO_ROOT / "backend" / "dreamforge_generation.py")
    for mode in BACKEND_COMFY_MODES:
        if mode in {"txt2img", "qwen_edit"}:
            continue
        if (
            f'mode == "{mode}"' not in gen_text
            and f'mode in ("{mode}"' not in gen_text
            and f', "{mode}")' not in gen_text
        ):
            if mode not in {"img2img", "kontext"}:  # handled in family branches
                issues.append(f"comfy mode {mode!r} not referenced in dreamforge_generation.py")
    return issues


def audit_asset_gating_patterns() -> list[str]:
    """Features requiring companions should coerce or emit recoverable errors."""
    issues: list[str] = []
    gen_text = _read_text(REPO_ROOT / "backend" / "dreamforge_generation.py")
    required_snippets = [
        "should_coerce_image_prompt_to_restyle",
        "missing_custom_node_pack",
        "faceid_assets_available",
    ]
    for snippet in required_snippets:
        if snippet not in gen_text:
            issues.append(f"asset gating snippet missing from generation: {snippet}")
    return issues


def audit_orphan_comfy_modes() -> list[str]:
    """Backend comfy modes should be reachable from a documented UI surface."""
    covered: set[str] = set()
    for modes in UI_SURFACE_TO_COMFY_MODES.values():
        covered.update(modes)
    covered.update(ADVANCED_ONLY_COMFY_MODES)
    orphans = sorted(BACKEND_COMFY_MODES - covered)
    return [f"backend comfy mode {mode!r} has no UI surface mapping" for mode in orphans]


def run_feature_surface_audit() -> list[str]:
    issues: list[str] = []
    issues.extend(audit_ui_enum_backend_coverage())
    issues.extend(audit_comfy_mode_graph_builders())
    issues.extend(audit_asset_gating_patterns())
    issues.extend(audit_orphan_comfy_modes())
    return issues


def audit_frontend_surface_tokens() -> list[str]:
    """Cross-check desktop tauri-api exposes the same enum tokens."""
    issues: list[str] = []
    api_text = _read_text(REPO_ROOT / "apps" / "desktop" / "src" / "lib" / "tauri-api.ts")
    for value in UI_INPAINT_INTENTS:
        if value not in api_text:
            issues.append(f"inpaint_intent {value!r} missing from tauri-api.ts")
    for value in UI_VARY_AMOUNTS:
        if value not in api_text:
            issues.append(f"vary_amount {value!r} missing from tauri-api.ts")
    for value in UI_UPSCALE_PRESETS:
        if value not in api_text:
            issues.append(f"upscale_preset {value!r} missing from tauri-api.ts")
    return issues
