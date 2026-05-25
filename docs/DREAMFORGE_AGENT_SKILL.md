# Skill: Local DreamForge Professional Image Generation

Use when an AI agent needs local image generation, editing, upscaling, Arabic/text-safe posters, or batch production on **D:\\DreamForge** (RTX 5060 Ti 16 GB; also supports `--vram-profile 8gb` and `5gb`).

## Preferred Entry Point: MCP Server
The `dreamforge_mcp_server.py` now provides **14 tools** for agents:
- `dry_run`: ALWAYS use before GPU tasks to check dependencies
- `list_models` / `resolve_model` / `recommend_model`: Find the best model for the task
- `generate_image` / `edit_image` / `upscale_image`: Core generation tools
- `generate_arabic_poster`: Use for precise Arabic/English text layout
- `get_last_generation` / `list_outputs` / `search_outputs`: Manage outputs and context
- `validate_image`: Quality validation

## Agent Rules
- Always use the MCP tools when available.
- Prefer `use_case` + creative-brief fields over a loose prompt.
- Always `dry_run` before expensive modern models; check `ready` and `missing_dependencies`.
- `--vram-profile 16gb` on this RTX 5060 Ti; `8gb` for 8 GB cards; `5gb` only for very low VRAM.
- Do not use SDXL for exact text; use Arabic pipeline or Qwen edit (when deps fixed).

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
