---
name: dreamforge-image-studio
description: >-
  Operate DreamForge, a local AI image creation and editing studio (Tauri desktop,
  CLI, MCP). Use when creating or editing images, running ComfyUI workflows,
  configuring studio modes (generate/edit/inpaint/upscale/toolbox), importing
  custom tools, validating Apple Silicon/MPS or NVIDIA/CPU operation,
  troubleshooting GPU engine readiness, or automating generation. Not the
  playdreamforge.com game platform.
---

# DreamForge — Agent skill for image creation and editing

DreamForge is a **local, privacy-first** image studio. Inference runs on the user's GPU via an embedded **ComfyUI** worker. Optional cloud LLMs are only for **agent planning text**, not for rendering images.

**Repository:** [github.com/mohammednabarawy/DreamForge](https://github.com/mohammednabarawy/DreamForge)

## Disambiguation

| Name | What it is |
|------|------------|
| **This DreamForge** | Local desktop/CLI/MCP image studio (this repo) |
| **playdreamforge.com** | Unrelated game-creation product |
| **ComfyUI** | Node-graph engine under `backend/repositories/ComfyUI/` or a configured data-root `engines/comfyui/` |

---

## Surfaces (pick one)

| Surface | Launch | Best for |
|---------|--------|----------|
| **Desktop studio** | `dreamforge.bat` (Windows) / `./dreamforge.sh` (macOS/Linux) | Interactive create/edit, canvas, references, toolbox |
| **Native macOS development app** | `./script/build_and_run.sh --verify` | Build the ARM64/x64 Tauri app, launch it, and verify its process |
| **MCP server** | `dreamforge-mcp.bat` or `./venv/bin/python backend/dreamforge_mcp_server.py` | Agent tool automation |
| **CLI** | `dreamforge-cli.bat` or `./venv/bin/python backend/dreamforge_cli_direct.py` | Scripts, batch jobs, smoke tests |
| **Gradio WebUI** | `python backend/launch.py` | Power-user parity / debugging |

Prefer the **CLI** for deterministic smoke tests, **MCP** when its tools are
already connected, and the **desktop** when the request explicitly concerns UI behavior.

---

## Prerequisites checklist

Before generating:

1. **Setup done** — `setup.bat` or `./setup.sh`
2. **Models on disk** — canonical folders are under `backend/models/`; a configured external models root is also supported
3. **GPU engine ready** — desktop status shows ready (not booting/failed)
4. **VRAM profile** — match hardware: `16gb`, `8gb`, `5gb`, `mps_*`, or `auto`
5. **Dependencies** — run `dry_run` (MCP) or **Dry run** (desktop) before heavy jobs

Key paths:

```
DreamForge/
├── backend/models/            # User weights (checkpoints, loras, vae, …)
├── backend/repositories/ComfyUI/ # Managed/legacy ComfyUI checkout
├── venv/                      # Project Python; use this, not global Python
├── outputs/                   # Images + JSON manifests (gitignored)
├── outputs/dreamforge/logs/   # worker.log, per-job logs
└── backend/                   # Python engine + MCP
```

Do not assume a root `models/` or `engines/comfyui/` directory exists. Runtime
configuration may instead point to `models/` and `engines/comfyui/` below a
separate data root.

## Verified operating sequence

Use this sequence for any end-to-end request:

1. Run setup only when the project virtual environment or Comfy dependencies are missing:

   ```bash
   ./setup.sh
   ```

2. Discover models and check the selected model before loading the GPU:

   ```bash
   ./venv/bin/python backend/dreamforge_cli_direct.py --list-models --inventory-json
   ./venv/bin/python backend/dreamforge_cli_direct.py \
     --check-model-deps realisticVisionV60B1_v51HyperVAE.safetensors --inventory-json
   ```

3. Dry-run the exact request.
4. Execute one small deterministic image.
5. Verify the output file and its adjacent `*.generation_manifest.json`. Treat
   the manifest—not a UI label—as the authority for prompt, model, dimensions,
   steps, sampler, scheduler, device routing, and validation.
6. Inspect the image visually before reporting success.

On Apple Silicon, confirm native Python and MPS when diagnosing performance:

```bash
./venv/bin/python -c 'import platform, torch; print(platform.machine()); print(torch.backends.mps.is_built(), torch.backends.mps.is_available())'
```

Expected: `arm64`, then `True True`. The launchers prefer native Rust/Node/Python
and set `PYTORCH_ENABLE_MPS_FALLBACK=1` for unsupported MPS kernels.

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

### Desktop (agent-operated macOS UI)

Use the real packaged UI when asked to test UI generation:

1. Launch with `./script/build_and_run.sh --verify`. This is the canonical
   kill/build/launch entrypoint and is also wired to the Codex **Run** action in
   `.codex/environments/environment.toml`.
2. Require macOS Accessibility permission for the controlling terminal or
   agent host before using System Events. Never claim UI state from process
   existence alone.
3. Inspect the DreamForge window accessibility tree. Confirm the title-bar
   status contains **ENGINE READY** and **Apple MPS** (or the expected GPU).
4. Bring the app to the foreground before keyboard interaction.
5. In **Pro → Generation**, use **Custom...** for a smoke test. Choose a small
   aspect preset and a low step count. Use a real pointer/keyboard event for
   React/WebKit controls; direct accessibility property assignment can change
   the exposed value without updating React state.
6. Focus the prompt and submit with **Command+Enter**, the app's built-in
   generation shortcut. Clicking a button named Generate can be ambiguous
   because the mode tab and submit action share that label.
7. Follow `outputs/dreamforge/logs/worker.events` until a `finished` event with
   `success: true`, then open the result path and inspect its manifest.

For a fast UI smoke test, use one image, no enhancer, no reference, Custom
sampling, roughly 6–8 steps, and the smallest suitable visible size. Avoid a
30-step 768×768 MPS smoke unless quality testing is specifically requested.

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

### CLI (agent workflow)

Always pass explicit sampling for smoke tests. Any explicit `--steps`,
`--cfg-scale`, `--sampler`, or `--scheduler` value is treated as Custom so a
performance preset cannot silently replace it.

Dry run:

```bash
./venv/bin/python backend/dreamforge_cli_direct.py \
  --dry-run --json \
  --model realisticVisionV60B1_v51HyperVAE.safetensors \
  --prompt "a small brass robot tending glowing flowers" \
  --width 512 --height 512 --steps 8 --cfg-scale 4.5
```

Execute locally without remote model metadata lookups:

```bash
env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
  ./venv/bin/python backend/dreamforge_cli_direct.py \
  --model realisticVisionV60B1_v51HyperVAE.safetensors \
  --prompt "a small brass robot tending glowing flowers" \
  --negative-prompt "blurry, low quality, text, watermark" \
  --width 512 --height 512 --steps 8 --cfg-scale 4.5 \
  --seed 424242 --vram-profile auto --output outputs/agent-smoke.png
```

Do not use global `python`, a hard-coded Anaconda interpreter, or a Rosetta
x86_64 toolchain on Apple Silicon when the project `venv` and native toolchain
are available.

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
| `ModuleNotFoundError` from managed ComfyUI | Venv has Torch but incomplete Comfy requirements | Run `./setup.sh`; dependency markers are interpreter-specific |
| CLI ignores explicit steps | Stale build predating Custom normalization | Update; explicit CLI sampling must produce `performance_selection: Custom...` in the manifest |
| Desktop progress jumps immediately to 99% | Stale progress tracker counting repeated node messages | Update to the tracker that deduplicates Comfy node IDs |
| Cancel is delayed on MPS | Comfy's Python event loop is busy inside a Metal sampling call | Wait for the current kernel/step; do not repeatedly submit or kill unless the user accepts losing the job |
| Native macOS build traverses nested `.git` | Debug bundle copied the whole backend | Use `./script/build_and_run.sh`; it omits release resources for debug runs |
| Rust target reports `x86_64-apple-darwin` on Apple Silicon | Rosetta/Homebrew Rust precedes rustup | Prefer `$HOME/.cargo/bin`; confirm `rustc -vV` host is `aarch64-apple-darwin` |

Logs:

- `outputs/dreamforge/logs/worker.log` — engine boot
- `outputs/dreamforge/logs/worker.events` — structured progress, previews, result paths
- `outputs/dreamforge/logs/<job-id>.log` — per generation
- `backend/outputs/dreamforge/logs/comfy.server.log` — Comfy device, model load, sampler steps

Progress may remain below 100 until decode/save completes. Only treat a job as
successful after a `finished` event and validated output. For suspected hangs,
check whether the preview file modification time is still advancing before
interrupting the job.

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
| Runtime path resolution | `backend/dreamforge_runtime_paths.py`, `backend/_paths.py` |
| Python/Comfy bootstrap | `backend/dreamforge_embedded_python.py`, `backend/dreamforge_comfy_install.py` |
| Comfy progress stream | `backend/dreamforge_comfy_ws.py` |
| Native macOS shell | `apps/desktop/src-tauri/src/lib.rs`, `script/build_and_run.sh` |

## Validation after code changes

Run checks in proportion to the change. At minimum:

```bash
npm --prefix apps/desktop run build
env PYTHONPATH=backend python3 -m pytest backend/tests/test_comfy_ws.py -q
./script/build_and_run.sh --verify
```

For runtime/bootstrap changes, also run the relevant tests under
`backend/tests/test_runtime_paths.py`, `test_embedded_python_runtime.py`,
`test_bootstrap_markers.py`, `test_setup_environment.py`, and
`test_vram_profiles.py`. Do not report the app as working solely because the
frontend builds; prove at least one actual generation through the requested
surface.

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

Always: project venv, absolute image paths, dry-run first, local GPU only,
read manifests, visually inspect outputs, and preserve unrelated user files.
```
