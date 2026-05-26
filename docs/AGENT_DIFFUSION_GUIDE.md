# Agent diffusion routing guide

This document is the reference for DreamForge agents (desktop planner, MCP, CLI) when choosing **models**, **edit modes**, and **generation settings**. Prefer `plan_agent_instruction` / studio modes over guessing raw checkpoint names.

## Model families (what they are for)

| Family | Examples | Best for | Avoid when |
|--------|----------|----------|------------|
| **SDXL** | Juggernaut XL, RealVis XL | Photoreal portraits, product shots, general T2I | Exact text in-image, heavy identity locks |
| **Flux Schnell** | flux1-schnell | Fast drafts, layouts, 4–8 steps | Final print quality without upscaling |
| **Flux Dev** | flux1-dev | Higher-quality T2I, infographics | Low VRAM without quant variant |
| **Flux Kontext** | flux1-dev-kontext_* | Instruction edits, identity continuity, relighting, object swap | Mask-only local edits (use inpaint) |
| **Flux Fill / inpaint** | flux fill, inpaint checkpoints | Masked region edits, cleanup, outpaint | Whole-image restyle without mask |
| **Qwen Image Edit** | qwen_image_edit_* | Typography, logos, Arabic/bilingual text, semantic edits | Simple global color tweaks (Kontext is faster) |
| **Upscale** | RealESRGAN, SUPIR | Enlargement / restoration only | Creative changes (use edit) |

## Studio modes → required fields

| Mode | `edit_type` | `cn_selection` / `cn_type` | Required inputs |
|------|-------------|---------------------------|-----------------|
| **generate** | `auto` | `None` / `None` | prompt, model |
| **edit** | `kontext` (default) or `qwen_edit` (text) | Kontext: `None`/`None`; Qwen: `Custom...`/`qwen_edit` | `input_image`, prompt |
| **inpaint** | `inpaint` | `Custom...` / `inpaint` | `input_image`, `inpaint_mask_path`, prompt |
| **upscale** | `auto` | `Custom...` / `upscale` | `upscale_image`, `upscale_method` (`2x`), prompt |

## Kontext prompting (instruction edits)

1. **One change per pass** — multi-step edits as chained jobs.
2. **Name what must stay** — e.g. “change shirt to red, keep face, hair, and pose unchanged”.
3. **Use direct verbs** — change, replace, remove, add (not “make it better”).
4. **High-res source** — 1024px+ input reduces quality loss.
5. **English prompts** — Kontext is trained for English instructions.

For **masked** Kontext edits, use inpaint mode with `inpaint_mask_path` so unmasked pixels are preserved.

## When to use Qwen vs Kontext

- **Qwen Image Edit**: Arabic/RTL text, brand typography, “replace text X with Y”, object add/remove with language in the prompt.
- **Kontext**: same person/character, relighting, background swap, style transfer, iterative edits.

Arabic posters with **exact glyphs**: prefer `generate_arabic_poster` or hybrid text render — do not rely on diffusion alone for readable Arabic.

## VRAM profiles

| Profile | Typical hardware | Guidance |
|---------|------------------|----------|
| `16gb` | RTX 4070/4080/5060 Ti class | Full Flux Dev, Kontext FP8, most SDXL |
| `8gb` | Mid-range GPU | Schnell, SDXL Lightning, quantized Kontext |
| `5gb` | Low VRAM | Small/quant models only; expect CPU offload |
| `mps` | Apple Silicon | Unified memory; use `8gb` tier habits |

Always run **`dry_run`** before heavy jobs when dependencies are uncertain.

## Upscale

- Set `upscale_image` (not only `input_image`).
- `upscale_method`: `2x` for fast RealESRGAN-style path; use SUPIR only when installed and quality matters.
- Upscale does not change composition — use **edit** for content changes.

## Live preview

Desktop jobs stream **`preview`** events to the canvas the same way as generate. If previews stop while logs continue, check the job log under `outputs/dreamforge/logs/{job_id}.log`.

## Related docs

- [dreamforge_mcp_instructions.md](./dreamforge_mcp_instructions.md) — MCP tool usage
- [EDITING_ORCHESTRATION_PLAN.md](./EDITING_ORCHESTRATION_PLAN.md) — roadmap for edit router
- [OPTIMIZATION.md](./OPTIMIZATION.md) — VRAM / CPU tuning
