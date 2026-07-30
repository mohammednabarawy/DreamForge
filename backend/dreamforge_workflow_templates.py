"""Pre-packaged Workflow Templates Library for DreamForge.

Provides structured, ready-to-execute workflow presets for common creative goals:
- Portrait with Face Consistency
- Product Photography Studio
- Comic Character Series (multi-panel consistency)
- Style Transfer with Identity Preservation
"""

from typing import Any

WORKFLOW_TEMPLATES: dict[str, dict[str, Any]] = {
    "portrait_face_consistency": {
        "id": "portrait_face_consistency",
        "name": "Portrait with Face Consistency",
        "description": "High-fidelity studio portrait preserving exact subject likeness across generations.",
        "category": "portrait",
        "default_params": {
            "identity_mode": "preserve_face",
            "identity_verify": True,
            "identity_similarity_threshold": 0.55,
            "performance": "Quality",
            "style": "portrait_master",
            "aspect_ratio": "896x1152",
        },
        "recommended_models": ["sd_xl_base_1.0.safetensors", "flux1-dev-kontext_fp8_scaled.safetensors"],
    },
    "product_photography": {
        "id": "product_photography",
        "name": "Product Photography Studio",
        "description": "Commercial product shot with studio lighting, crisp reflections, and clean negative space.",
        "category": "commercial",
        "default_params": {
            "performance": "Quality",
            "style": "product_ad",
            "aspect_ratio": "1024x1024",
            "prompt_enhancer": "flufferizer",
        },
        "recommended_models": ["sd_xl_base_1.0.safetensors", "flux1-dev-fp8.safetensors"],
    },
    "comic_character_series": {
        "id": "comic_character_series",
        "name": "Comic Character Series",
        "description": "Consistent graphic novel panel rendering for a fixed character model across environments.",
        "category": "storytelling",
        "default_params": {
            "identity_mode": "preserve_face",
            "style": "comic_book",
            "aspect_ratio": "1152x896",
            "performance": "Speed",
        },
        "recommended_models": ["sd_xl_base_1.0.safetensors"],
    },
    "style_transfer_identity": {
        "id": "style_transfer_identity",
        "name": "Style Transfer with Identity Preservation",
        "description": "Apply artistic or painterly styles while maintaining face likeness from reference photos.",
        "category": "artistic",
        "default_params": {
            "identity_mode": "preserve_face",
            "identity_verify": True,
            "performance": "Quality",
            "aspect_ratio": "1024x1024",
        },
        "recommended_models": ["flux1-dev-kontext_fp8_scaled.safetensors", "sd_xl_base_1.0.safetensors"],
    },
}


def list_workflow_templates() -> list[dict[str, Any]]:
    return list(WORKFLOW_TEMPLATES.values())


def get_workflow_template(template_id: str) -> dict[str, Any] | None:
    return WORKFLOW_TEMPLATES.get(template_id.strip().lower())
