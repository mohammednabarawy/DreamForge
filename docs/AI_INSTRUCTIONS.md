# Ultimate DreamForge AI Agent Tool — Instructions

This project (`D:\\DreamForge`) is an automation-friendly wrapper around local DreamForge for AI agents. It provides a rich MCP server, family-aware routing for 10+ modern models, and an exact Arabic/text poster pipeline.

## Core Capabilities

1. **MCP Server** (`dreamforge_mcp_server.py`) — 14 tools including `dry_run`, `recommend_model`, `edit_image`, and output search.
2. **Headless CLI** (`dreamforge_cli_direct.py`) — Direct PowerShell wrappers available (`dreamforge-cli.ps1`).
3. **Arabic/text poster pipeline** (`arabic_poster_pipeline.py`) — Multi-pass compositing for exact typography.
4. **Model Inventory** — Detects and routes SDXL, Flux, Flux Kontext, Flux 2 Klein, HiDream O1, Qwen Image, Qwen Edit, Z-Image, and Hunyuan.

---

## Agent Contract (Read First)

| Rule | Action |
| :--- | :--- |
| Discover models | Use MCP `list_models()` or `recommend_model(use_case)` |
| Plan before GPU | Use MCP `dry_run()` — check `ready` and `missing_dependencies` |
| Image Editing | Use MCP `edit_image()` with `edit_type="kontext"` for Flux Kontext |
| This machine (16 GB) | VRAM profile `16gb` |
| Final assets | Outputs tracked via manifest JSONs; use `list_outputs()` |
| Exact Arabic/text | Use `generate_arabic_poster()`, NOT raw SDXL prompts |

---

## Model Routing by Use Case

| Use case | Recommended model | Family |
| :--- | :--- | :--- |
| `product_ad` | `epicrealismXL_VXIAbeast4SLightning` / `RealVisXL` | sdxl |
| `cinematic_scene` | `hidream_o1_image_dev_mxfp8` | hidream_o1 |
| `infographic` | `flux1-schnell-fp8` | flux |
| `fast_draft` | `z_image_turbo_fp8_e4m3fn` | z_image |
| `image_edit` | `flux1-dev-kontext_fp8_scaled` | flux_kontext |
| `concept_art` | `hidream_o1_image_dev_mxfp8` | hidream_o1 |

**Important Notes:**
- **Modern families** (Flux, HiDream, Qwen, Z-Image) disable legacy DreamForge styles.
- **HiDream-O1** requires 28-50 steps, CFG 1.0-5.0 (handled automatically by CLI).
- **Flux Kontext** requires an `--input-image` and uses the inpainting pipeline internally.
- **Qwen-Image-Edit** remains experimental; check dependencies first.

---

## VRAM Profiles

| Profile | Hardware | Behavior |
| :--- | :--- | :--- |
| `16gb` | RTX 5060 Ti 16 GB | `--normalvram` for SDXL/Flux FP8, `--lowvram` for heavy HiDream |
| `8gb` | Mid-range | `--lowvram`, up to 1024², prefer Schnell/Lightning/Z-Image |
| `5gb` | Low VRAM | `--lowvram`, up to 896², Q3/Q4 GGUF, SVDQ/FP4 only |

---

## Qwen-Image-Edit Dependencies

For Qwen edit models, ensure `clip/Qwen2.5-VL-7B-Instruct-Q4_K_S.gguf` is installed. Dry-run will return `missing_dependencies` if absent. 

---

## Related Docs

- `README_CLI.md` — full argument reference
- `EVALUATION_REPORT.md` — test results and improvement backlog
- `DREAMFORGE_AGENT_SKILL.md` — short skill for agents
