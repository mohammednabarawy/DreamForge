from dreamforge_creative_templates import (
    default_template_id_for_mode,
    list_creative_templates,
    resolve_template_patch,
)


def test_default_template_by_mode():
    assert default_template_id_for_mode("generate") == "create.default"
    assert default_template_id_for_mode("edit") == "edit.kontext"
    assert default_template_id_for_mode("inpaint") == "inpaint.flux_fill"
    assert default_template_id_for_mode("upscale") == "enhance.ultimate_sd"


def test_default_template_post_upscale_variant():
    assert (
        default_template_id_for_mode("edit", post_upscale=True)
        == "edit.kontext.enhance2x"
    )
    assert (
        default_template_id_for_mode("inpaint", post_upscale=True)
        == "inpaint.flux_fill.enhance2x"
    )


def test_resolve_template_extends_chain():
    resolved = resolve_template_patch("edit.kontext.enhance2x", base={"prompt": "x"})
    assert resolved["template_id"] == "edit.kontext.enhance2x"
    assert resolved["patch"]["post_upscale"] == "ultimate_sd_upscale"
    assert resolved["patch"]["edit_type"] == "kontext"


def test_post_upscale_enabled_without_template_chain():
    resolved = resolve_template_patch(
        "edit.kontext",
        base={},
        post_upscale_enabled=True,
    )
    assert resolved["patch"]["post_upscale"] == "ultimate_sd_upscale"


def test_list_creative_templates_filters_mode():
    edit_only = list_creative_templates(studio_mode="edit")
    ids = {item["id"] for item in edit_only}
    assert "edit.kontext" in ids
    assert "create.default" not in ids


def test_z_image_template_uses_consumer_split_file_resources():
    resolved = resolve_template_patch("create.z_image", base={})
    assert resolved["template_id"] == "create.z_image"
    assert resolved["companions"] == [
        "z_image_turbo_nvfp4",
        "z_image_qwen3_4b_fp4",
        "z_image_ae_vae",
    ]
