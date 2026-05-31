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
| Discover capabilities | MCP `get_agent_catalog()` then `list_styles()` / `list_loras()` / `list_models()` |
| Plan before GPU | MCP `dry_run()` or `plan_workflow()` — check `ready` and `missing_dependencies` |
| Style presets | MCP/CLI `style=product_ad` (style **recipe id**; replaces legacy use_case) |
| User preferences | Local style memory + `dynamic_preset` in brain plans (opt-in on disk) |
| Image Editing | MCP `edit_image()` with `edit_type="kontext"` for Flux Kontext |
| LoRA stacks | MCP `lora=["file.safetensors:0.6"]` or CLI `--lora file:weight` |
| This machine (16 GB) | VRAM profile `16gb` |
| Final assets | Outputs tracked via manifest JSONs; use `list_outputs()` |
| Exact Arabic/text | `generate_arabic_poster()`, NOT raw SDXL prompts |

---

## Model routing by style recipe

| Style recipe | Typical model family | Notes |
| :--- | :--- | :--- |
| `product_ad` | sdxl | Commercial product shots; embedded SDXL style fragments |
| `cinematic` / `cinematic_scene` | hidream_o1 / sdxl | Scene lighting; HiDream for hero frames |
| `fast_draft` | z_image / flux | Iteration previews |
| `infographic` / `mockup_ui` | flux | Layouts; minimal legacy styles |
| `image_edit` | flux_kontext | Requires `--input-image` |
| `concept_art` | hidream_o1 | Environment illustration defaults |

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
