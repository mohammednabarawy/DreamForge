import json

from dreamforge_brain import (
    LOCAL_IMAGE_BACKEND,
    coerce_brain_decision,
    heuristic_brain_decision,
    plan_user_intent,
)


def test_heuristic_brain_decision_keeps_image_execution_local():
    decision = heuristic_brain_decision(
        "Make her smile, remove background people, make it cinematic, upscale to 4K",
        current_settings={},
        selected_image="D:/tmp/photo.png",
        gallery=[],
    )

    assert decision["suggested_image_backend"] == LOCAL_IMAGE_BACKEND
    assert "face_edit" in decision["operations"]
    assert "remove_object" in decision["operations"]
    assert "style_transfer" in decision["operations"]
    assert "upscale" in decision["operations"]
    assert decision["workflow_blueprint"]["local_only"] is True
    assert "flux_kontext_edit" in decision["workflow_blueprint"]["template_ids"]
    assert decision["mode"] == "edit"
    assert decision["patch"]["upscale_method"] == "4x"


def test_heuristic_brain_maps_advanced_workflow_modes():
    decision = heuristic_brain_decision(
        "use the same character reference, preserve pose with depth controlnet, composite as a product poster",
        current_settings={
            "input_image": "D:/tmp/photo.png",
            "reference_images": ["D:/tmp/ref.png"],
            "control_images": ["D:/tmp/depth.png"],
        },
        selected_image="D:/tmp/photo.png",
        gallery=[],
    )

    patch = decision["patch"]
    assert "controlnet_structure" in decision["operations"]
    assert "reference_guidance" in decision["operations"]
    assert "composite_layers" in decision["operations"]
    assert patch["workflow_mode"] == "area_composition"
    assert patch["cn_type"] == "depth"
    assert patch["control_image"] == "D:/tmp/depth.png"
    assert patch["reference_image"] == "D:/tmp/ref.png"


def test_heuristic_brain_maps_face_detail_workflow_mode():
    decision = heuristic_brain_decision(
        "repair face details and sharpen the eyes",
        current_settings={"input_image": "D:/tmp/portrait.png"},
        selected_image="D:/tmp/portrait.png",
        gallery=[],
    )

    assert "face_detail" in decision["operations"]
    assert decision["patch"]["workflow_mode"] == "face_detail"
    assert decision["patch"]["input_image"] == "D:/tmp/portrait.png"
    assert "face_detail_optional" in decision["workflow_blueprint"]["template_ids"]


def test_heuristic_brain_maps_arabic_text_integrate():
    decision = heuristic_brain_decision(
        'Create a poster with exact Arabic text "مرحبا"',
        current_settings={},
        selected_image="",
        gallery=[],
    )

    assert "text_integrate" in decision["operations"]
    assert decision["patch"]["workflow_mode"] == "arabic_text_composite"
    assert decision["patch"]["use_case"] == "arabic_poster"
    assert decision["patch"]["arabic_text"] == "مرحبا"
    assert "arabic_text_composite" in decision["workflow_blueprint"]["template_ids"]


def test_plan_user_intent_falls_back_to_structured_local_schema():
    decision = plan_user_intent(
        "turn this into a cinematic rainy cyberpunk scene",
        selected_image="D:/tmp/source.png",
        provider_id="embedded",
        model="missing-model.gguf",
    )

    assert decision["schema_version"] == "1.0"
    assert decision["status"] == "planned"
    assert decision["suggested_image_backend"] == LOCAL_IMAGE_BACKEND
    assert decision["workflow_plan"]
    assert "style_transfer" in decision["operations"]
    assert decision["warnings"]


def test_coerce_brain_decision_normalizes_legacy_actions_schema():
    decision = coerce_brain_decision(
        {
            "actions": ["remove_object", "upscale"],
            "steps": ["remove_object", "upscale"],
            "mode": "edit",
            "patch": {"prompt": "remove people then upscale"},
            "confidence": "0.91",
            "suggested_image_backend": "cloud_flux",
        },
        user_intent="remove people then upscale",
        selected_image="D:/tmp/photo.png",
        provider_id="lmstudio",
    )

    assert decision["suggested_image_backend"] == LOCAL_IMAGE_BACKEND
    assert decision["suggested_brain_provider"] == "lmstudio"
    assert decision["confidence"] == 0.91
    assert [step["operation"] for step in decision["workflow_plan"]] == ["remove_object", "upscale"]
    json.dumps(decision)
