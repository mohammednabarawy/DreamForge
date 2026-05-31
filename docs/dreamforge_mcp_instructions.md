# DreamForge MCP Server Agent Instructions

Welcome to the DreamForge MCP server. This server provides **local** AI image generation using SDXL, Flux, HiDream, Qwen, Z-Image, and related families via a managed ComfyUI backend on the user's machine.

**Local-only image execution:** GPU sampling, model weights, and output files stay on the host. Optional cloud LLM APIs are separate and used only if the user configures an agent provider for planning—not for rendering pixels.

## Start here

1. Call **`get_agent_catalog`** — full map of style recipes, LoRAs, model families, workflow modes, and tool index.
2. Call **`get_mcp_capabilities`** — enabled permissions (`read`, `plan`, `execute`) and approval rules.
3. Call **`dry_run`** before any GPU job — inspect `ready`, `missing_dependencies`, resolved model, and style defaults.

## Core principles

1. **Always `dry_run` first** — Before `generate_image`, `edit_image`, or heavy models, call `dry_run` to resolve dependencies and parameters without allocating GPU memory.
2. **Prefer style recipes** — Use `style` (`product_ad`, `cinematic`, `fast_draft`, …) plus brief fields (`subject`, `composition`, `lighting`) instead of raw prompt soup. Each recipe can set default models, aspect ratio, performance tier, and embedded SDXL style fragments.
3. **Discover before guessing** — `list_styles`, `list_loras`, `list_models`, `get_inventory`, and `recommend_for_style` reflect what is installed on this machine.
4. **Exact text = Arabic poster tool** — Do not rely on SDXL/Flux for precise Arabic or long English labels. Use `generate_arabic_poster` or `edit_image` with `edit_type="qwen_edit"` when dependencies are ready.
5. **Execution approval** — When the server enforces approval, pass `approved=true` on execution tools after the user confirms the plan.
6. **VRAM profiles** — `16gb` (default workstation), `8gb` (mid-range), `5gb` (tight VRAM). Match the user's hardware.

## Style recipes vs SDXL fragments

| Parameter | Meaning |
|-----------|---------|
| `style` | Single **style recipe id** (`product_ad`, `sai_enhance`, `cinematic`, …). Primary creative preset. |
| `styles` | Advanced override: raw SDXL prompt style fragments. Usually leave unset so the recipe supplies them. |
| `--sdxl-styles` (CLI) | Same as MCP `styles`; only when overriding the recipe. |

Legacy `use_case` naming is retired — always pass recipe ids to `style`.

## LoRAs

- MCP: `lora=["detail_tweaker_xl.safetensors:0.6"]` on `generate_image` / `dry_run`.
- CLI: `--lora detail_tweaker_xl.safetensors:0.6` (repeatable).
- Discover installed files with **`list_loras`** or **`get_agent_catalog`**.

## Capabilities and security

- Restrict tools with `DREAMFORGE_MCP_CAPABILITIES=read,plan` (omit `execute` to block GPU jobs).
- MCP does **not** expose arbitrary shell, filesystem write, or remote code execution.
- Workflow **`create_workflow`** returns a first-party **blueprint** (operations + readiness), not an imported third-party Comfy graph.

## Tool guidance

| Tool | When to use |
|------|-------------|
| `get_agent_catalog` | First call: capabilities, recipes, LoRAs, families, workflows |
| `dry_run` | Preflight any job; inspect `ready`, `missing_dependencies`, repair actions |
| `plan_workflow` | Intent → operations, templates, readiness without GPU |
| `list_models` / `resolve_model` / `recommend_model` / `recommend_for_style` | Model discovery and routing |
| `list_styles` / `get_inventory` | Style recipe catalog and grouped inventory |
| `list_loras` | Installed LoRA files and `filename:weight` syntax |
| `generate_image` | Text-to-image (approved); set `style`, optional `lora` |
| `edit_image` / `inpaint_image` / `remove_object` | Reference and mask edits |
| `upscale_image` | Post-process upscale |
| `generate_arabic_poster` | Exact RTL/LTR poster typography |
| `check_dependencies` | Companion files for a named model |
| `list_outputs` / `search_outputs` / `get_generation_bundle` | History and manifests |
| `get_last_generation` | Active session context |
| `validate_image` | Quality checks on disk |
| `analyze_project` | High-level project/session summary |
| `create_workflow` | Blueprint for multi-step local plans |

### MCP resources

| URI | Content |
|-----|---------|
| `capabilities://guide` | Same as `get_agent_catalog` |
| `styles://catalog` | Style recipe list |
| `loras://list` | Installed LoRAs |
| `models://list` | Model categories |
| `projects://summary` | Project analysis |

### Editing

Use `edit_image` with `edit_type`:

- **`kontext`** — Flux Kontext global edits (default for “change style / swap object”)
- **`inpaint`** — masked region edits (`inpaint_mask_path`)
- **`qwen_edit`** — typography-sensitive edits when Qwen Edit deps are installed
- **`img2img`** — low-denoise vary/refine
- **`auto`** — router picks from input + intent

See [AGENT_DIFFUSION_GUIDE.md](./AGENT_DIFFUSION_GUIDE.md).

### Validation

Manifests record prompt, model, seed, routing, validation warnings, and **lineage** (plan hash, sources, mask, outputs) for edit jobs.

If `validate_image` reports `very_low_contrast` or `image_appears_blank`, treat the run as failed and inspect dependencies/VAE compatibility.

## Model routing quick reference

- **SDXL** — Photorealism, product, portraits; supports DreamForge style recipes (`product_ad`, …).
- **Flux Schnell / Z-Image** — Fast drafts and infographics; minimal legacy SDXL fragments.
- **HiDream O1** — Cinematic scenes; slower (28+ steps); server applies family presets.
- **Flux Kontext** — Requires `input_image`; Krita-derived sampling recipes.
- **Qwen Edit** — Experimental; always `dry_run` first.

## CLI mirror (headless agents)

```powershell
.\dreamforge-cli.ps1 --json --list-styles
.\dreamforge-cli.ps1 --json --list-inventory
.\dreamforge-cli.ps1 --json --style product_ad --subject "luxury watch" --prompt "hero product on marble" --dry-run
.\dreamforge-cli.ps1 --json --style cinematic --lora "detail_tweaker_xl.safetensors:0.5" --prompt "..." --approved
```

See [README_CLI.md](./README_CLI.md) for the full flag reference.

## Troubleshooting

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for managed Comfy, model paths, missing custom nodes, low VRAM, and platform notes.

Pre-release verification: [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md).
