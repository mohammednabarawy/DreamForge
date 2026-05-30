# Ultimate DreamForge AI Agent Tool — Instructions

This project (`D:\\DreamForge`) is an automation-friendly wrapper around **local** DreamForge inference for AI agents. It provides an MCP server, family-aware routing for modern models, managed ComfyUI execution, and an exact Arabic/text poster pipeline.

**Image generation never leaves the machine** unless the user separately configures a cloud LLM for planning chat—not for rendering.

## Core Capabilities

1. **MCP Server** (`dreamforge_mcp_server.py`) — Generation, editing, planning, inventory; capability-gated execution with optional approval.
2. **Headless CLI** (`dreamforge_cli_direct.py`) — `--json` for scripts; use-case recipes and manifests with edit lineage.
3. **Desktop bridge** (`dreamforge_desktop_bridge.py`) — Style memory, dynamic presets, custom-node checks, brain plans.
4. **Arabic/text poster pipeline** (`arabic_poster_pipeline.py`) — Multi-pass compositing for exact typography.
5. **Model inventory** — SDXL, Flux, Flux Kontext, Flux 2 Klein, HiDream O1, Qwen Image/Edit, Z-Image, Hunyuan.

---

## Agent Contract (Read First)

| Rule | Action |
| :--- | :--- |
| Discover models | Use MCP `list_models()` or `recommend_model(use_case)` |
| Plan before GPU | Use MCP `dry_run()` or `plan_workflow()` — check `ready` and `missing_dependencies` |
| User preferences | Local style memory + `dynamic_preset` in brain plans (opt-in on disk) |
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

- `README_CLI.md` — full argument reference, desktop bridge commands
- `TROUBLESHOOTING.md` — Comfy, models, nodes, VRAM, security
- `RELEASE_CHECKLIST.md` — pre-release test gate
- `dreamforge_mcp_instructions.md` — MCP tool details
- `EVALUATION_REPORT.md` — test results and improvement backlog
- `DREAMFORGE_AGENT_SKILL.md` — short skill for agents
