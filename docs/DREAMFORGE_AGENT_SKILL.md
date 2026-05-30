# Skill: Local DreamForge Professional Image Generation

Use when an AI agent needs local image generation, editing, upscaling, Arabic/text-safe posters, or batch production on **D:\\DreamForge** (RTX 5060 Ti 16 GB; also supports `--vram-profile 8gb` and `5gb`).

## Preferred Entry Point: MCP Server

The MCP server exposes generation, editing, planning, and inventory tools. Resources include models, outputs, sessions, and project summary.

**Always call `dry_run` before GPU work.** Execution tools require `approved=true` when approval is enforced.

Core tools:

- `dry_run`, `plan_workflow`, `create_workflow` — plan without GPU
- `list_models` / `resolve_model` / `recommend_model` / `check_dependencies`
- `generate_image` / `edit_image` / `inpaint_image` / `remove_object` / `upscale_image`
- `generate_arabic_poster` — exact Arabic/English poster layout
- `get_last_generation` / `list_outputs` / `search_outputs` / `get_generation_bundle`
- `validate_image`, `analyze_project`, `get_mcp_capabilities`

Brain / bridge planning merges **UserStyleProfile** and **dynamic presets** from intent (see `dynamic_preset` in plan JSON).

## Agent Rules

- Always use MCP tools when available; image pixels are rendered **locally only**.
- Prefer `use_case` + creative-brief fields over a loose prompt.
- Always `dry_run` before expensive modern models; check `ready` and `missing_dependencies`.
- Pass `approved=true` only after the user confirms execution.
- `--vram-profile 16gb` on 16 GB cards; `8gb` / `5gb` for smaller GPUs.
- Do not use SDXL for exact text; use Arabic pipeline or Qwen edit when deps are ready.

## Verified Modern Families (2026-05-22)
- **SDXL**: Proven (JuggernautXL, RealVisXL)
- **Flux**: Schnell (fast), Dev (quality). Fits in 16GB.
- **Flux Kontext**: Requires `--input-image`. Use for high-quality img2img edits.
- **Flux 2 Klein**: Fast 4B/9B draft models.
- **HiDream O1**: Cinematic. Very heavy (28-50 steps). Use `--lowvram` automatically via profile.
- **Z-Image**: Extremely fast drafts (20 steps).
- **Qwen Image / Qwen Edit**: Experimental. Check dependencies!

## 8 GB Card Quick Preset (CLI)
```powershell
.\dreamforge-cli.ps1 --json --model flux1-schnell-fp8 --width 768 --height 768 --steps 6 --vram-profile 8gb --prompt "professional product hero, no text" --output outputs\agent\hero.png --validate-output
```
