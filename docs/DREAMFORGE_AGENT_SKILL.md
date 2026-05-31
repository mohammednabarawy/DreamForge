# Skill: Local DreamForge Professional Image Generation

Use when an AI agent needs local image generation, editing, upscaling, Arabic/text-safe posters, or batch production on **D:\DreamForge** (RTX 5060 Ti 16 GB; also supports `--vram-profile 8gb` and `5gb`).

## First steps (MCP)

1. **`get_agent_catalog`** — style recipes, LoRAs, model families, workflow modes, tool index.
2. **`dry_run`** — resolve model/style/dependencies before GPU.
3. **`generate_image`** with `approved=true` after user confirms.

## Discovery tools

| Need | Tool |
|------|------|
| Full capability map | `get_agent_catalog` |
| Style recipe ids + defaults | `list_styles` |
| Installed LoRAs (`name:weight`) | `list_loras` |
| Checkpoints / ControlNet / VAE | `list_models` |
| Grouped desktop inventory | `get_inventory` |
| Model for a recipe | `recommend_for_style(style="product_ad")` |
| Pick checkpoint by substring | `resolve_model` |

## Creative generation

- Set **`style`** to a recipe id (`product_ad`, `cinematic`, `fast_draft`, `concept_art`, …), not legacy `use_case`.
- Add brief fields: `subject`, `composition`, `lighting`, `mood`, `camera`.
- Stack LoRAs: `lora=["file.safetensors:0.6"]`.
- Leave `styles` unset unless overriding embedded SDXL fragments.

## Execution tools

- Plan: `dry_run`, `plan_workflow`, `create_workflow`
- Generate: `generate_image`, `generate_arabic_poster`
- Edit: `edit_image`, `inpaint_image`, `remove_object`, `upscale_image`
- History: `list_outputs`, `get_last_generation`, `validate_image`

Brain / bridge planning merges **UserStyleProfile** and **dynamic presets** from intent (see `dynamic_preset` in plan JSON).

## Agent rules

- Image pixels render **locally only**; use MCP/CLI, not remote image APIs.
- Always `dry_run` before expensive modern models; check `ready` and `missing_dependencies`.
- Pass `approved=true` only after the user confirms execution.
- `--vram-profile 16gb` on 16 GB cards; `8gb` / `5gb` for smaller GPUs.
- Do not use SDXL for exact text; use Arabic pipeline or Qwen edit when deps are ready.

## Verified model families (2026-05)

- **SDXL** — JuggernautXL, RealVisXL; best with style recipes.
- **Flux** — Schnell (fast), Dev (quality).
- **Flux Kontext** — requires `input_image` for edits.
- **Flux 2 Klein** — fast 4B/9B drafts.
- **HiDream O1** — cinematic; 28+ steps.
- **Z-Image** — extremely fast drafts.
- **Qwen Image / Qwen Edit** — experimental; check dependencies.

## CLI quick example

```powershell
.\dreamforge-cli.ps1 --json --style product_ad --subject "wireless earbuds" --prompt "minimal studio hero" --lora "detail_tweaker_xl.safetensors:0.5" --vram-profile 16gb --dry-run
```

See `docs/dreamforge_mcp_instructions.md` and `docs/AI_INSTRUCTIONS.md`.
