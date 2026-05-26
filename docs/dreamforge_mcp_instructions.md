# DreamForge MCP Server Agent Instructions

Welcome to the DreamForge MCP Server! This server provides powerful, local AI image generation capabilities using state-of-the-art models like SDXL, Flux, HiDream, and Qwen.

## Core Principles

1. **Always `dry_run` first**: Before invoking `generate_image` or `edit_image` with heavy models (Flux Dev, HiDream O1), use the `dry_run` tool to ensure dependencies are met and parameters are correctly resolved without waiting for GPU allocation.
2. **Prefer Use Cases**: Instead of writing raw, complex prompts, use the `use_case` parameter (e.g., `product_ad`, `cinematic_scene`, `infographic`) combined with creative brief fields (`subject`, `composition`, `lighting`). The server will auto-compile professional prompts.
3. **Exact Text = Arabic Poster Tool**: Standard diffusion models (like SDXL) struggle with precise text rendering, especially Arabic. ALWAYS use `generate_arabic_poster` when exact, legible text is required. DO NOT try to generate exact text using raw SDXL/Flux prompts unless it's very short English.
4. **VRAM Profiles Matter**:
   - `16gb`: Use for RTX 4070/4080/5060 class cards. Supports all models.
   - `8gb`: Use for mid-range cards. Stick to `flux1-schnell` or SDXL Lightning for speed.
   - `5gb`: For low-end cards. Use heavily quantized models only.

## Tool Guidance

*   **Model Selection**: Use `recommend_model` if you aren't sure which model fits the user's request. Pass the `use_case` and it will return ranked options.
*   **Active Context**: The server tracks the `last_generation`. Use `get_last_generation` to fetch the metadata and output paths of the most recent job. Other tools may default to these values if you omit them.
*   **Image Editing**: Use `edit_image` with `edit_type` (`kontext`, `qwen_edit`, `inpaint`, `img2img`, `auto`) and optional `inpaint_mask_path` for masked edits. Default global edits to **kontext**; use **qwen_edit** only for typography / exact text. See [AGENT_DIFFUSION_GUIDE.md](./AGENT_DIFFUSION_GUIDE.md).
*   **Validation**: Generated images include automatic validation. If `validate_image` reports `very_low_contrast` or `image_appears_blank`, the generation likely failed (e.g., due to an incompatible VAE).
*   **Finding Outputs**: Use `list_outputs` to find previous generations.

## Model Routing Quick Reference

*   **SDXL (e.g., JuggernautXL, RealVisXL)**: Best for photorealism, portraits, and general purpose. Use with SDXL style presets.
*   **Flux (e.g., flux1-schnell, flux1-dev)**: Best for speed (schnell), infographics, and modern aesthetics. **Note:** Does NOT use legacy DreamForge styles.
*   **HiDream O1**: Best for cinematic scenes and concept art. **Note:** Very slow (28-50 steps). Requires specific CFG settings automatically applied by the server.
*   **Flux Kontext**: Best for image editing, style transfer, and object swapping. Requires an `input_image`.
*   **Z-Image**: Extremely fast draft generation.
