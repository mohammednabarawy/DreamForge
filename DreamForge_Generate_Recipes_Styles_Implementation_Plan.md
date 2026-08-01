# DreamForge Generate, Recipes, and Styles Implementation Plan

## Goal

Make Generate faster to operate, keep imported and downloaded recipes in a visible managed library, recreate only settings that are actually present in image metadata, open marketplace sources in the system browser, and preserve Fooocus-compatible style behavior while keeping ComfyUI as DreamForge's execution backend.

## Confirmed current state

- Generate already has mode-aware settings, performance presets, aspect presets, prompt helpers, ControlNet/Qwen controls, progress, references, and result actions.
- Recipes are normalized as DreamForge Recipe v2 JSON and saved under `outputs/dreamforge/library/recipes`, but imported image/JSON recipes are only applied to the current session and the Library has no Recipes tab.
- Civitai discovery returns generation metadata and source URLs, but locally saved recipes are not presented as a first-class library.
- Styles are applied through DreamForge's Fooocus-derived backend. The frontend correctly expands `{prompt}` templates, but custom-style negative text is not restored reliably when a style is cleared or switched.
- Marketplace link icons use webview anchors instead of an explicit system-browser command.

## Research decisions

- Keep Recipe v2 as the portable interchange format. Preserve unknown/missing fields and the original ComfyUI workflow metadata when available; never guess absent settings. ComfyUI embeds both the API prompt graph and workflow metadata in generated PNGs and supports workflow loading from generated media: [ComfyUI repository](https://github.com/comfyanonymous/ComfyUI), [ComfyUI metadata implementation](https://github.com/comfyanonymous/ComfyUI/blob/master/nodes.py).
- Parse common A1111/Civitai parameter text and ComfyUI prompt graphs into normalized settings. Civitai exposes image `meta` plus model-version URLs, hashes, and download links for exact dependency resolution: [Civitai REST API reference](https://github.com/civitai/civitai/wiki/REST-API-Reference).
- Follow Fooocus template semantics exactly: replace `{prompt}` in the positive template and split positive/negative templates into lines: [Fooocus style implementation](https://github.com/lllyasviel/Fooocus/blob/main/modules/sdxl_styles.py).
- Open source links in the operating-system browser through Tauri's supported opener path, with an HTTP/HTTPS allowlist.

## Implementation phases

### 1. Generate settings and command workspace

- Add a compact current-run summary and Basic/Advanced control density.
- Pair step and CFG sliders with precise number inputs.
- Add seed randomize, copy, paste, and reuse controls.
- Add custom width/height, aspect lock, and swap controls.
- Show parameter availability warnings from model-family metadata before falling back to label inference.
- Add reset actions and locally persisted user generation presets.
- Move hardware limits out of per-run controls and into App Settings.
- Persist the three-panel layout, add a distraction-free canvas focus mode, and allow prompt expansion.
- Permit reference-image reordering.
- Keep result actions available when only one image was generated.
- Make missing-dependency resolution a non-blocking drawer so the command area remains usable.

Acceptance:

- Common controls are visible without opening Advanced.
- Exact values can be typed and invalid values are bounded.
- Panel sizes and focus preference survive restart.
- A one-image run still exposes save/reuse/recreate actions.

### 2. Practical recipe lifecycle

- Preserve Recipe v2 timestamps so library deduplication is stable.
- Add backend list and delete operations for the managed recipe directory.
- Add `Library > Recipes` with preview, source, completeness, apply/recreate, reveal, and delete actions.
- Route JSON imports, image-metadata imports, and Civitai saves into the same managed library immediately.
- Export normalized Recipe v2 JSON from the selected/current generation settings.
- Parse A1111/Civitai parameter strings and ComfyUI API graphs for prompts, model, LoRAs, seed, size, sampler, scheduler, steps, CFG, denoise, and clip skip where present.
- Retain raw workflow/prompt metadata for lossless ComfyUI handoff; visibly mark partial recipes.
- Reuse the existing dependency resolver and download manager for exact Civitai model/LoRA versions.

Acceptance:

- Imported recipes appear immediately under `Library > Recipes`.
- The storage location is `D:\DreamForge\outputs\dreamforge\library\recipes` for this checkout.
- Recreate applies original values when present and does not fabricate absent values.
- Missing model/LoRA choices remain download, replace, or skip (LoRA only).

### 3. External sources and style correctness

- Route card source-link icons through a shared validated system-browser helper.
- Make source buttons keyboard accessible and expose descriptive labels.
- Restore both positive and negative base prompts when styles are cleared or switched.
- Verify custom Fooocus JSON import and backend style expansion with a focused regression test.

Acceptance:

- Card source links open externally and reject non-HTTP(S) URLs.
- `{prompt}` placement and negative fragments match Fooocus semantics.
- Switching or clearing a style never leaves stale negative text behind.

### 4. Verification

- Run focused recipe/style/parser tests and the full backend suite.
- Run the desktop TypeScript/build checks.
- Launch the desktop UI and inspect Generate and Library at normal and compact sizes, including keyboard focus and the recipe drawer.

## Deliberate boundaries

- ComfyUI remains the only generation backend.
- Recipe import is metadata-driven; pixels without embedded metadata cannot reproduce exact settings.
- No cloud recipe account, recipe editor framework, or new preset service is introduced. Local JSON plus the existing backend bridge covers the requested workflow.
