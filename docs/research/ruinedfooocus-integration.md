# RuinedFooocus integration (Comfy path)

Reference clone: `.research/RuinedFooocus` (gitignored). Upstream: [runew0lf/RuinedFooocus](https://github.com/runew0lf/RuinedFooocus).

DreamForge does **not** run RuinedFooocus as a runtime. Reliable prompting and LoRA behavior from that stack are ported into the managed ComfyUI generation path.

## Architecture

```
Job (CLI / desktop)
  → dreamforge_prompt.prepare_generation_prompts()
       process_prompt (legacy modules.prompt_processing)
       parse_loras (<lora:name:weight> tags)
       shift_attention (multi-image batches)
       merge_generation_loras (job.lora + parsed tags)
  → dreamforge_generation._build_comfy_prompt_graph()
       bindings["loras"] → dreamforge_comfy_workflows._apply_user_lora_stack()
  → ComfyUI prompt graph
```

## Package layout

| Module | Role |
|--------|------|
| `backend/dreamforge_prompt/pipeline.py` | Canonical `prepare_generation_prompts()` |
| `backend/dreamforge_prompt/legacy.py` | Wraps `modules.prompt_processing` under backend cwd |
| `backend/dreamforge_prompt/expansion.py` | Flufferizer model path + download |
| `backend/dreamforge_prompt/loras.py` | Merge job LoRAs with prompt tags; resolve on disk |
| `backend/dreamforge_prompt/shift_attention.py` | Batch attention span interpolation |
| `backend/dreamforge_prompt_pipeline.py` | Backward-compat re-exports only |

Legacy Fooocus modules remain under `backend/modules/` (styles, wildcards, Hyperprompt, Erniehancer, etc.) and are invoked through `legacy.py`.

## Prompt enhancers

CLI: `--prompt-enhancer {none,flufferizer,hyperprompt,erniehancer}`

Defaults:

- **SDXL / classic checkpoints**: Flufferizer (when weights exist under `backend/prompt_expansion/`)
- **Flux / Qwen / HiDream / SD3**: none (SDXL style presets are filtered out; enhancer styles still allowed)

## LoRAs

Sources (merged in RuinedFooocus order):

1. Explicit `job.lora` entries (gallery or `name:weight` CLI strings)
2. `<lora:filename:weight>` tags left in the prompt after `parse_loras`

Comfy graphs stack LoRAs after the base loader:

- **CheckpointLoaderSimple**: `LoraLoader` (model + clip)
- **Split loaders (Flux / Qwen / HiDream)**: `LoraLoaderModelOnly`

## Refreshing the reference clone

```powershell
git clone --depth 1 https://github.com/runew0lf/RuinedFooocus.git .research/RuinedFooocus
```

Use the clone only for diffing upstream behavior; production code lives under `backend/dreamforge_prompt/` and `backend/modules/`.

## Style thumbnails

Preview images follow Fooocus `sdxl_styles/samples/` naming and live in `backend/assets/style_thumbnails/`. Sync with:

```powershell
python scripts/sync_style_thumbnails.py --download
```
