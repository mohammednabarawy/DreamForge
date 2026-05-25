# DreamForge Agent Tool Evaluation

Date: 2026-05-22
Machine: NVIDIA GeForce RTX 5060 Ti, 16 GB VRAM (15.93 GB reported by Torch)

## Goal

Make this install the ultimate local image tool for AI agents.

## Executive Summary

| Capability | Status | Notes |
| :--- | :--- | :--- |
| MCP Server | **Production-ready** | 14 tools exposed including discovery, execution, and outputs |
| SDXL / Lightning | **Production-ready** | ~6–7 s per 768² image |
| Flux Schnell FP8 | **Production-ready** | ~11 s pipeline at 512², 4 steps |
| Flux 2 Klein | **Production-ready** | Fast 4B/9B draft generation |
| Flux Kontext | **Production-ready** | Img2Img editing supported via `--edit-type kontext` |
| Z-Image | **Production-ready** | ~6 s draft generation |
| HiDream O1 | **Production-ready @ 28 steps** | ~65 s at 1024², 28 steps, CFG 1.0 |
| Qwen-Image-Edit | **Blocked/Unstable** | Missing compatible CLIP (`qwen_2.5_vl_7b_edit-q2_k.gguf` architecture 'pig' rejected by gguf loader). FP8 crashes on load. |
| Arabic/text poster | **Production-ready** | Hybrid compositing; see `arabic_poster_pipeline.py` |

## Verification Plan

### Phase 1: MCP Server
✅ All 14 tools added and verified via dry runs. `dreamforge_output_index` correctly parses manifests. `instructions.md` provided to guide agent behavior.

### Phase 2: Model Routing
✅ Extended `MODEL_FAMILY_HINTS` with 10 families.
✅ `recommend_model_for_task` function implemented.
✅ VRAM profiles updated: `flux`, `flux2`, and `z_image` now fit in `--normalvram` on 16GB profile. Heavy models correctly forced to `--lowvram`.

### Phase 3: Recipes
✅ Added `image_edit`, `concept_art`, `fast_draft`, and `mockup_ui` use-case recipes.
✅ `validate_image` successfully parses outputs and fake text.

### Phase 4: Documentation
✅ Updated `AI_INSTRUCTIONS.md`, `DREAMFORGE_AGENT_SKILL.md`, `README_CLI.md`.

## Known Issues & Backlog

1. **Qwen Image Edit Stability**: The local execution pipeline crashes on FP8 variant (`exit code -1073741819`), and the GGUF variant rejects the official pathdb `pig` architecture CLIP. This remains an active area of research; use `flux_kontext` for edits until fixed.
2. **Video Generation**: Hunyuan and LTX-Video are installed in `diffusion_models` but not exposed via MCP yet.
3. **Database Indexing**: The `list_outputs` and `search_outputs` tools scan JSON files linearly. For production with thousands of images, a small SQLite layer could be beneficial.
