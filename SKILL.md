---
name: dreamforge-image-studio
description: >-
  Operate DreamForge, a local AI image creation and editing studio (Tauri desktop,
  CLI, MCP). Use when creating or editing images, running ComfyUI workflows,
  configuring studio modes (generate/edit/inpaint/upscale/toolbox), importing
  custom tools, troubleshooting GPU engine readiness, or automating generation
  via dreamforge-mcp. Not the playdreamforge.com game platform.
---

# DreamForge — Agent skill for image creation and editing

DreamForge is a **local, privacy-first** image studio. Inference runs on the user's GPU via an embedded **ComfyUI** worker. Optional cloud LLMs are only for **agent planning text**, not for rendering images.

**Repository:** [github.com/mohammednabarawy/DreamForge](https://github.com/mohammednabarawy/DreamForge)

## Disambiguation

| Name | What it is |
|------|------------|
| **This DreamForge** | Local desktop/CLI/MCP image studio (this repo) |
| **playdreamforge.com** | Unrelated game-creation product |
| **ComfyUI** | Node-graph engine DreamForge embeds under `engines/comfyui/` |

---

## Surfaces (pick one)

| Surface | Launch | Best for |
|---------|--------|----------|
| **Desktop studio** | `dreamforge.bat` (Win) / `./dreamforge.sh` (macOS/Linux) | Interactive create/edit, canvas, references, toolbox |
| **MCP server** | `dreamforge-mcp.bat` | AI agents automating generation |
| **CLI** | `dreamforge-cli.bat` | Scripts, batch jobs, CI smoke |
| **Gradio WebUI** | `python backend/launch.py` | Power-user parity / debugging |

Agents should prefer **MCP** for automation and **desktop** guidance when helping a human use the UI.

---

## Prerequisites checklist

Before generating:

1. **Setup done** — `setup.bat` or `./setup.sh` (clones ComfyUI into `engines/comfyui/`)
2. **Models on disk** — checkpoints/UNet/VAE/CLIP under `models/` (not bundled)
3. **GPU engine ready** — desktop status shows ready (not booting/failed)
4. **VRAM profile** — match hardware: `16gb`, `8gb`, `5gb`, `mps_*`, or `auto`
5. **Dependencies** — run `dry_run` (MCP) or **Dry run** (desktop) before heavy jobs

Key paths:

```
DreamForge/
├── models/                    # User weights (checkpoints, loras, vae, …)
├── engines/comfyui/           # Managed ComfyUI
├── outputs/                   # Images + JSON manifests (gitignored)
├── outputs/dreamforge/logs/   # worker.log, per-job logs
└── backend/                   # Python engine + MCP
```

---

## Studio modes (desktop)

Set in app config `ui.studio_mode`:

| Mode | Purpose | Requires |
|------|---------|----------|
| `generate` | Text-to-image (and img2img with references) | Prompt, model |
| `edit` | Semantic edit on a source image | `input_image`, prompt |
| `inpaint` | Masked local edit | `input_image`, `inpaint_mask_path`, Flux Fill model |
| `upscale` | Enlarge / restore detail | Source image |
| `toolbox` | Preset tools + **custom ComfyUI workflows** | Tool-specific inputs |
| `agent` | Natural-language planning (optional cloud brain) | Agent provider config |

**Generate is disabled** until the GPU worker reports ready. If boot fails, check `outputs/dreamforge/logs/worker.log` and use **Restart GPU engine**.

---

## Creating images

### Desktop (human workflow)

1. Wait for engine **ready** in the title bar.
2. Set mode to **Generate** (or **Edit** with a reference).
3. Enter a **prompt** in the prompt bar.
4. Pick a **model** from the gallery (Inspector).
5. Optional: style recipe, LoRA stack, aspect ratio, performance tier.
6. Optional: attach **reference images** (face, structure, restyle) — routing adapts per model family.
7. Click **Generate** (or **Dry run** first).

Outputs land in `outputs/` with a JSON **manifest** (prompt, model, routing, lineage).

### MCP (agent workflow)

Always plan before executing:

```
1. list_models / resolve_model / recommend_model
2. check_dependencies(model_name)   # companion VAE, CLIP, etc.
3. dry_run(prompt=..., model=..., style=..., vram_profile=...)
4. generate_image(..., approved=True)   # approved required for GPU execution
```

**`generate_image` essentials:**

- `prompt` — positive prompt (required)
- `model` — filename or stem; omit only if style recipe supplies default
- `style` — recipe id (`none`, `product_ad`, `cinematic`, …); use `list_styles`
- `vram_profile` — `16gb`, `8gb`, `5gb`, `auto`, …
- `aspect_ratio` or `width`/`height`
- `reference_images` — list of **absolute paths** for multi-reference
- `lora` — e.g. `["detail_tweaker_xl.safetensors:0.6"]`
- `approved=True` — **required** or MCP blocks execution

**CLI example:**

```bat
dreamforge-cli.bat --prompt "a beautiful landscape at golden hour" --output landscape.png
```

Add `--dry-run` to validate without loading GPU.

---

## Editing images

### Edit types (routing)

| Goal | Desktop mode | MCP / params |
|------|--------------|--------------|
| Global semantic change | **Edit** | `edit_image`, `edit_type=auto` or `qwen_edit` / `kontext` |
| Change masked region | **Inpaint** | `edit_image`, `edit_type=inpaint`, mask path |
| Preserve identity (Flux) | **Edit** + Kontext model | `edit_type=kontext` |
| Qwen semantic edit | **Edit** | `edit_type=qwen_edit` |
| Upscale | **Upscale** | `upscale_image` |

**`edit_image` essentials:**

- `input_image` — **absolute path** to source
- `prompt` — what to change
- `edit_type` — `auto` | `kontext` | `inpaint` | `img2img` | `qwen_edit`
- `inpaint_mask_path` — required for inpaint
- `approved=True`

### Inpaint (desktop)

1. Switch to **Inpaint** mode.
2. Attach source image to canvas or reference panel.
3. Paint mask on canvas (or load mask).
4. Wait for mask sync (Generate disabled while saving mask).
5. Use **Flux Fill** checkpoint — app prompts download if missing.
6. Choose intent: Default / Improve detail / Modify content.

### Toolbox native tools

In **Creative Toolbox** (`toolbox` mode), built-in tasks include:

- **Photo restore** — damaged/old photos
- **Outfit transfer** — person + outfit reference (+ optional mask)
- **Cutout compose** — subject + background reference
- **Portrait Master** — slider-driven portrait with ControlNet

Each task has specific image/mask requirements; Generate stays blocked until inputs are satisfied.

---

## Custom ComfyUI tools (toolbox)

Users can import ComfyUI workflow JSON as **custom tools**:

1. **Creative Toolbox → Import Tool**
2. Select workflow JSON — **UI format or API format** both work
3. Bind only what the workflow needs (usually **LoadImage** for reference)
4. Click **Use Tool** to select (selection persists in app config)
5. Attach required images, then **Generate**

### Critical rules for custom workflows

- **Do not bind text** on `CLIPTextEncode` nodes whose `text` input is **linked** to another node (e.g. `CR Prompt List`). Binding breaks multi-prompt/carousel loops.
- **Carousel / batch workflows** — bind **image only**; let the workflow drive prompts internally.
- If Generate shows *"Select your custom tool again"* — click **Use Tool** (stale tool id after re-import).
- If dependency modal shows `workflow_not_api_format` — update DreamForge; UI workflows are supported. Real missing items are Comfy **node packs** and **model weights**.
- Keep UI + API workflow siblings in the same folder when possible; DreamForge prefers the API sibling at runtime for accuracy.

Workflow files are stored in app config `custom_tools[]` with `workflow_path`, `bindings`, and optional `model_overrides`.

---

## Model families (routing hints)

DreamForge routes by installed model family:

| Family | Typical use |
|--------|-------------|
| SDXL / SD1.5 | General txt2img, ControlNet |
| Flux / Flux Kontext | Quality generation, identity-preserving edit |
| Qwen Image Edit | Semantic edit, typography, bilingual text |
| HiDream | Multi-reference, quality tier |
| Ideogram | Structured / layout-heavy generation |
| Krea / Z-Image | Reference-driven generation |

Use `resolve_model(query)` or desktop model gallery. Low VRAM: prefer **Lightning** / **Speed** performance presets.

---

## Multi-reference images

Attach multiple references with roles (desktop reference panel):

- **image_prompt / face** — identity or appearance
- **structure** — pose, depth, layout
- **restyle** — style transfer source
- **source_edit** — edit target

MCP: pass `reference_images=["C:/abs/path1.png", "C:/abs/path2.png"]`.

Routing chains latents (Kontext), stitches inputs (Krea/Z/Ideogram), or uses IP-Adapter hybrids depending on model.

---

## Agent planning (optional)

`plan_workflow(instruction, selected_image=...)` returns a structured plan without GPU work. Desktop **Agent** mode can use local (Ollama, embedded GGUF) or configured cloud providers for **decision text only**.

Image execution always stays **local** via ComfyUI.

---

## Troubleshooting (agents)

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Generate disabled, engine booting | ComfyUI still starting | Wait or Restart GPU engine |
| Missing companion files | VAE/CLIP not downloaded | `check_dependencies`, approve download modal |
| Custom tool "removed" | Stale `custom_tool_id` | Click **Use Tool** again or re-import |
| One image instead of batch | Text binding broke prompt list | Remove CLIP text bindings |
| Comfy works in browser, DreamForge fails | Worker lifecycle / port conflict | Restart engine; check `worker.log` |
| Inpaint blocked | No Flux Fill or no mask | Install Fill model; paint mask |
| Ideogram model in custom tool deps | Wrong gallery model checked | Custom tools skip base model deps when selected |

Logs:

- `outputs/dreamforge/logs/worker.log` — engine boot
- `outputs/dreamforge/logs/<job-id>.log` — per generation

---

## MCP tool quick reference

| Tool | Purpose |
|------|---------|
| `dry_run` | Plan + dependency check, no GPU |
| `generate_image` | Text-to-image / img2img with controls |
| `edit_image` | Edit / inpaint existing image |
| `upscale_image` | Upscale |
| `plan_workflow` | Agent instruction → plan JSON |
| `list_models` | Inventory by category |
| `resolve_model` | Lookup model metadata + family |
| `check_dependencies` | Missing companion files |
| `list_styles` / `list_loras` | Discovery for recipes and LoRA |
| `get_agent_catalog` | Combined discovery payload |

**Execution gate:** pass `approved=True` on all GPU tools unless testing denial paths.

---

## Related project skills

Install curated agency skills for deeper work:

```powershell
.\.cursor\skills\install.ps1
```

| Skill | Use when |
|-------|----------|
| `agency-ai-engineer` | Model/workflow integration, Comfy routing |
| `agency-prompt-engineer` | Prompt templates, Ideogram/Flux copy |
| `agency-frontend-developer` | Desktop UI, Tauri, React studio |
| `agency-backend-architect` | Python pipeline, `dreamforge_generation.py` |
| `agency-minimal-change-engineer` | Focused fixes, parity |
| `agency-reality-checker` | Pre-ship smoke verification |

---

## Code map (for implementers)

| Area | Location |
|------|----------|
| Desktop UI | `apps/desktop/src/` |
| Generation readiness | `apps/desktop/src/lib/generationReadiness.ts` |
| Custom tools | `apps/desktop/src/lib/customTools.ts`, `backend/dreamforge_custom_tools.py` |
| Comfy workflows | `backend/dreamforge_comfy_workflows.py`, `backend/dreamforge_generation.py` |
| Workflow import (UI/API) | `backend/dreamforge_comfy_workflow_import.py` |
| MCP tools | `backend/dreamforge_mcp_server.py` |
| CLI | `backend/dreamforge_cli_direct.py` |
| App config (custom tools) | `outputs/dreamforge/app-config.json` via `dreamforge_app_config.py` |

---

## Agent workflow summary

```
User wants an image
  ├─ Interactive? → Guide desktop: engine ready → mode → prompt → model → Generate
  └─ Automated?   → MCP: dry_run → check_dependencies → generate_image(approved=True)

User wants to edit
  ├─ Full image edit     → Edit mode / edit_image
  ├─ Masked change       → Inpaint + Flux Fill / edit_type=inpaint
  └─ Comfy workflow      → Toolbox custom tool + image bindings only

Always: absolute paths for images, local GPU only, read manifests in outputs/
```
