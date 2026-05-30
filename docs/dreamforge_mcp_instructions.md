# DreamForge MCP Server Agent Instructions

Welcome to the DreamForge MCP Server. This server provides **local** AI image generation using SDXL, Flux, HiDream, Qwen, Z-Image, and related families via a managed ComfyUI backend on the user's machine.

**Local-only image execution:** GPU sampling, model weights, and output files stay on the host. Optional cloud LLM APIs are separate and used only if the user configures an agent provider for planning—not for rendering pixels.

## Core Principles

1. **Always `dry_run` first** — Before `generate_image`, `edit_image`, or heavy models, call `dry_run` to resolve dependencies and parameters without allocating GPU memory.
2. **Prefer use cases** — Use `use_case` (`product_ad`, `cinematic_scene`, `fast_draft`, …) plus brief fields (`subject`, `composition`, `lighting`) instead of raw prompt soup. Brain planning also returns a **`dynamic_preset`** block merging intent with local style memory.
3. **Exact text = Arabic poster tool** — Do not rely on SDXL/Flux for precise Arabic or long English labels. Use `generate_arabic_poster` or `edit_image` with `edit_type="qwen_edit"` when dependencies are ready.
4. **Execution approval** — When the server enforces approval, pass `approved=true` on execution tools after the user confirms the plan.
5. **VRAM profiles** — `16gb` (default workstation), `8gb` (mid-range), `5gb` (tight VRAM). Match the user's hardware.

## Capabilities and security

- Call **`get_mcp_capabilities`** to see enabled tool groups (`read`, `plan`, `execute`).
- Restrict tools with `DREAMFORGE_MCP_CAPABILITIES=read,plan` (omit `execute` to block GPU jobs).
- MCP does **not** expose arbitrary shell, filesystem write, or remote code execution.
- Workflow **`create_workflow`** returns a first-party **blueprint** (operations + readiness), not an imported third-party Comfy graph.
- Companion downloads and custom-node installs require **user approval** in the desktop UI when triggered from failure reports.

## Tool Guidance

| Tool | When to use |
|------|-------------|
| `dry_run` | Preflight any job; inspect `ready`, `missing_dependencies`, repair actions |
| `plan_workflow` | Intent → operations, templates, readiness without GPU |
| `recommend_model` / `list_models` / `resolve_model` | Model discovery |
| `generate_image` | Text-to-image (approved) |
| `edit_image` / `inpaint_image` / `remove_object` | Reference and mask edits |
| `upscale_image` | Post-process upscale |
| `generate_arabic_poster` | Exact RTL/LTR poster typography |
| `check_dependencies` | Companion files for a named model |
| `list_outputs` / `search_outputs` / `get_generation_bundle` | History and manifests |
| `get_last_generation` | Active session context |
| `validate_image` | Quality checks on disk |
| `analyze_project` | High-level project/session summary |
| `create_workflow` | Blueprint for multi-step local plans |
| `list_use_cases` / `list_styles` | Recipe and style catalogs |

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

- **SDXL** — Photorealism, product, portraits; supports DreamForge style presets.
- **Flux Schnell / Z-Image** — Fast drafts and infographics; minimal legacy styles.
- **HiDream O1** — Cinematic scenes; slower (28+ steps); server applies family presets.
- **Flux Kontext** — Requires `input_image`; Krita-derived sampling recipes.
- **Qwen Edit** — Experimental; always `dry_run` first.

## Troubleshooting

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for managed Comfy, model paths, missing custom nodes, low VRAM, and platform notes.

Pre-release verification: [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md).
