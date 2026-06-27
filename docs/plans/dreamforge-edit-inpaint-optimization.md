# DreamForge Edit and Inpaint Optimization Plan

Date: 2026-06-26

## 1. Executive Summary

DreamForge already has more than a superficial Edit/Inpaint implementation. Verified code paths show a Tauri/React desktop UI, a Python bridge, a single-flight GPU worker, ComfyUI graph builders, mask export, automatic quick selections, mask grow/feather preprocessing, crop-and-stitch inpainting for large images, Flux Fill routing, Qwen Image Edit routing, Kontext routing, live progress, cancellation, output manifests, and edit lineage.

The highest-impact gaps are not "add inpaint" but tightening the product contract around it:

- Make the local edit task explicit: Remove, Replace, Repair, Refine, Extend, or Global Edit.
- Expose context crop/padding and mask preview honestly, because the backend already does crop-and-stitch but the user cannot inspect it.
- Centralize model capability metadata beyond the current small family map and filename heuristics.
- Add deterministic mask/preservation regression tests for every inpaint path that claims unmasked pixels are preserved.
- Improve result handling in a deliberately small first pass: candidate thumbnails, compare, retry same settings, and "use as current source." True layer editing belongs later unless DreamForge already has a layer model.

No rewrite is recommended. The lazy path is to keep the existing React/Tauri/Python/Comfy architecture and add a small backend-owned task/default contract, a minimal model-capability contract, visible crop/mask/prompt feedback, and focused tests around the existing shared pipeline.

## 2. Repository Areas Inspected

Primary files inspected:

- Desktop shell and state: `apps/desktop/src/App.tsx`, `apps/desktop/src/hooks/useDreamForge.ts`
- Canvas and prompt UI: `apps/desktop/src/components/CanvasPanel.tsx`, `PromptBar.tsx`, `InspectorPanel.tsx`
- Mask UI: `CanvasMaskEditor.tsx`, `CanvasToolRail.tsx`, `InpaintMaskModal.tsx`
- Edit/inpaint controls: `EditFamilySettingsPanel.tsx`, `GenerationSettingsPanel.tsx`
- Frontend routing/settings types: `lib/tauri-api.ts`, `lib/inpaintIntent.ts`, `lib/inpaintModel.ts`, `lib/editModel.ts`, `lib/routeResolution.ts`, `lib/creativeTask.ts`
- Bridge/Tauri: `apps/desktop/src-tauri/src/lib.rs`, `backend/dreamforge_desktop_bridge.py`
- Backend execution/routing: `backend/dreamforge_engine.py`, `dreamforge_generation.py`, `dreamforge_workflow_routing.py`, `dreamforge_workflow_planner.py`, `dreamforge_model_registry.py`
- Comfy graph builders: `backend/dreamforge_comfy_workflows.py`
- Mask and Krita-style resources: `backend/dreamforge_krita_resources.py`, `dreamforge_inpaint_selection.py`, `dreamforge_inpaint_intent.py`
- Agent/MCP surfaces: `backend/dreamforge_agent_runtime.py`, `dreamforge_mcp_server.py`, `dreamforge_agent_tools.py`
- Tests: `backend/tests/test_generation_routing.py`, `test_krita_resources.py`, `test_inpaint_selection.py`, `test_inpaint_intent.py`, `test_workflow_routing.py`, `test_model_router.py`

## 3. Current Architecture Map

Verified flow:

1. `App.tsx` creates the three-pane desktop shell: history, canvas, inspector.
2. `useDreamForge.ts` owns studio mode, settings, selected output, preview URL, model gallery, dependency checks, generation lifecycle, cancellation, and modal state.
3. `PromptBar.tsx` switches modes, captures instructions, attaches images, exposes Generate/Cancel, and routes drag-and-drop images as reference/inpaint/upscale by mode.
4. `CanvasPanel.tsx` displays preview, before/after/split compare, zoom/pan, inline mask editing, auto-fix buttons, and Vary buttons.
5. `CanvasMaskEditor.tsx` and `InpaintMaskModal.tsx` produce black/white masks where white means selected edit region.
6. Frontend settings are sent through Tauri `invoke_generation`.
7. Tauri `src-tauri/src/lib.rs` starts and monitors a Python GPU worker, emits progress/preview/finished events, and forwards bridge commands.
8. `DreamForgeEngine.execute_job()` serializes GPU work through one worker queue.
9. `dreamforge_generation.run_generation()` resolves model, mode, image paths, masks, resources, and builds a Comfy API graph.
10. `dreamforge_comfy_workflows.py` emits first-party Comfy graphs for Qwen Edit, Flux Kontext, Flux Fill, VAE inpaint, img2img, outpaint, IP-Adapter, face detail, and upscaling.
11. Results are staged, optionally composited/stiched, copied to outputs, indexed in manifests, and surfaced back to the canvas/gallery.

## 4. Current Edit Workflow

Verified:

- History actions call `historyEditThis()`, which selects the image and attaches it for Edit.
- Edit mode defaults are planned in `planStudioModeSwitch()` and remote creative-task enforcement, then sanitized before generation.
- `EditFamilySettingsPanel.tsx` exposes edit strength when an input image or edit family type exists.
- Edit routes include `qwen_edit`, `kontext`, and `img2img` through `GenerationSettings.edit_type`.
- `dreamforge_generation._tune_edit_job_settings()` applies model-family defaults and caps steps by VRAM tier unless Custom settings are explicit.
- `comfy_qwen_image_edit()` uses `TextEncodeQwenImageEdit`, optional Qwen Lightning LoRA, AuraFlow sampling, source scaling, VAE encode, KSampler, and decode.
- `comfy_flux_kontext_edit()` uses `FluxKontextImageScale`, VAE source/reference latents, `ReferenceLatent`, `FluxGuidance`, KSampler, and decode.

Current edit weaknesses:

- The prompt field is shared between generation and editing; the UI does not clearly distinguish "global prompt" from "edit instruction."
- Preservation toggles are hints only; the final rewritten prompt/request is not visible to users.
- Qwen/Kontext/img2img routing is partly capability-based and partly filename/family heuristic.
- Multi-reference behavior exists, but users get little explanation of role, weight, or why references are stitched for Kontext.

## 5. Current Inpaint Workflow

Verified:

- Inpaint mode attaches a source image and opens inline mask editing.
- Inline mask tools support paint, erase, subject/background quick selection, brush size, clear, and full-screen expansion.
- Full-screen mask tools add tap object/background, quick selects for subject/background/clothes/face/eyes/hands/legs/feet, add/replace selection merge mode, grow/shrink, and live mask sync.
- `useMaskPublisher` writes studio mask PNGs through `write_studio_mask_png`; backend tests verify round-trip.
- `dreamforge_inpaint_selection.py` creates selection masks with rembg, YOLO when available, heuristics, and tap flood fill.
- `dreamforge_inpaint_intent.py` and frontend `inpaintIntent.ts` define Default, Improve detail, and Modify content presets.
- Backend preprocesses masks with grow and Gaussian feather in `dreamforge_krita_resources.preprocess_inpaint_mask()`.
- For large images with small masks, `plan_inpaint_crop_stitch()` crops the masked region with margin, snaps dimensions, uploads the crop, then stitches the result back.
- Flux Fill graph uses `InpaintModelConditioning`, `DifferentialDiffusion`, and `FluxGuidance`; generic inpaint uses `VAEEncodeForInpaint`.
- For non-Flux-Fill and crop-stitch paths, `composite_inpaint_result()` composites generated pixels over the original with the processed mask.

Current inpaint weaknesses:

- Context crop exists but is not previewed or user-adjustable.
- Mask grow/feather exist in two places: modal morph tools and settings preprocess controls. They are related but not clearly explained.
- Flux Fill output is not always post-composited because the graph is trusted to preserve unmasked pixels; this needs explicit leakage tests.
- There is no visible hard distinction between the model-generated region, image-processing crop/stitch, and final compositing.
- Outpaint graph exists, but the main UI does not expose a clear Extend flow with direction and previewed expansion.

## 6. Web Research Sources and Dates

Sources checked on 2026-06-26:

- ComfyUI official examples/docs: inpaint, img2img, Flux Fill, ControlNet, and workflow node patterns. Source: [ComfyUI examples](https://comfyanonymous.github.io/ComfyUI_examples/) and [ComfyUI docs](https://docs.comfy.org/)
- Krita AI Diffusion official repository and documentation: integrated canvas editing, selection/mask workflows, managed Comfy backend, live mode, and Flux/Qwen/Kontext recipes. Source: [Krita AI Diffusion](https://github.com/Acly/krita-ai-diffusion)
- InvokeAI official docs: unified canvas, image layers, mask/selection editing, bounding boxes, galleries, and node/workflow separation. Source: [InvokeAI Docs](https://invoke-ai.github.io/InvokeAI/)
- Fooocus official repository and inpaint concepts: simple inpaint/outpaint, improve detail/modify content style presets, mask simplicity. Source: [Fooocus GitHub](https://github.com/lllyasviel/Fooocus)
- AUTOMATIC1111 Stable Diffusion WebUI wiki: inpaint area, mask blur, masked content, denoise, and only-masked padding controls. Source: [AUTOMATIC1111 wiki](https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki)
- Stable Diffusion WebUI Forge repository: performance-oriented SD WebUI fork and Forge ecosystem conventions. Source: [Forge GitHub](https://github.com/lllyasviel/stable-diffusion-webui-forge)
- SwarmUI repository/docs: model/workflow UI, Comfy backend orientation, queue/results UX. Source: [SwarmUI GitHub](https://github.com/mcmonkeyprojects/SwarmUI)

Research-supported takeaway: leading local tools converge on the same controls: mask paint/erase/invert/blur/grow, denoise/edit strength, crop/only-masked region with padding, clear model/workflow compatibility, visible progress/cancel, reusable seeds/settings, and non-destructive comparison. DreamForge should adapt those controls behind a simpler task-first UI.

## 7. Competitive Benchmark

| Area | DreamForge verified state | Adopt/adapt/reject |
|---|---|---|
| Mask creation | Brush/erase, subject/background/tap/part selection, clear. No polygon/fill/invert verified in current UI. | Adapt polygon/fill/invert later; add invert/fill first because cheap. |
| Mask refinement | Modal grow/shrink; settings grow/feather/hard mask/Comfy expand. | Adopt clearer Grow, Shrink, Feather, Hard Edge labels. |
| Context handling | Automatic crop-and-stitch for large images; no user preview/control. | Adapt A1111/Invoke style visible crop box and padding control. |
| Inpaint controls | Intent presets, edit strength, grow/feather/expand, model selector. | Keep, but group by Simple vs Advanced. |
| Edit workflows | Qwen, Kontext, img2img routes; no task preset layer for remove/replace/repair/refine. | Adapt Fooocus/Krita task presets, but make canonical defaults backend-owned and surfaced through dry-run. |
| Canvas | Before/after/split compare, zoom/pan, inline mask. No layers/apply-as-layer verified. | Adapt Invoke/Krita non-destructive result handling. |
| Results | Vary buttons, history, compare. No candidate tray/apply/discard verified. | Adapt a small candidate tray first; defer true layers/asset management. |
| Simplicity | Simple mode exists, but inpaint has hidden prerequisites and advanced route labels. | Adopt Fooocus default simplicity. |
| Advanced controls | Many controls exist in settings and model gallery. | Keep advanced panel; do not surface all by default. |
| Model routing | Small capability map plus filename/family heuristics. | Adapt centralized capability registry. |
| Defaults | Strong Qwen/Kontext/Flux Fill defaults and VRAM caps exist. | Keep; add task-specific defaults. |
| Performance | Single GPU worker, VRAM cleanup, crop-stitch, source scaling. | Keep; expose crop policy and benchmark VRAM/runtime. |
| Reliability | Progress, cancel, dependency checks, structured errors. | Keep; add retry/fallback trace for routing decisions. |
| Iteration | History and Vary exist; source/mask/settings reuse incomplete in UI. | Adapt re-edit result with same mask/settings. |
| Prompting | Shared prompt, extra inpaint prompt for detail/modify. | Add inspectable instruction processing. |
| Preservation | Composite for crop/non-Fill paths; preservation toggles for edit. | Add leakage tests and identity/reference presets. |
| Documentation | Some hints/tooltips, route summaries. | Add contextual help only where controls are ambiguous. |

Reject:

- Node graph editing as the default UI. It conflicts with DreamForge’s streamlined desktop identity.
- Exposing every Comfy node parameter in the main canvas.
- Making Agent mode the default for normal edits; use it only when decisions are genuinely ambiguous.

## 8. UX Audit

Persona influence: UX Architect methodology was applied to task flows, mode separation, progressive disclosure, state feedback, and user certainty before generation.

Common flow findings:

- Remove object: achievable through Inpaint + mask + prompt, but the user must know to choose Inpaint and mask the area. Add explicit Remove task.
- Replace object: achievable via Modify content intent, but replacement text and local/global prompt boundaries are unclear.
- Repair face/hand: auto-fix buttons exist; full control depends on quick selection and Improve detail. Good foundation, but needs visible "Repair" preset.
- Change clothing while preserving face: quick clothes/face selection exists; preservation needs clearer "Preserve face/identity" routing and reference handling.
- Change small detail: crop-stitch helps technically, but users cannot see the effective context region.
- Extend image: backend graph exists; UI lacks direct Extend flow.
- Global instruction edit: Edit mode works, but prompt placeholder still says "Describe the shot."
- Multiple sequential edits: history exists, but edit attempts are not grouped as a branch with source/mask/settings.
- Retry same settings: possible by settings persistence, but no explicit retry card.
- Compare candidates: before/after/split exists for one result; no multi-candidate selection tray.

## 9. UI Audit

Persona influence: UI Designer methodology was applied to component hierarchy, visual hierarchy, target controls, accessibility, and high-DPI desktop behavior.

Current strengths:

- Desktop layout is dense and appropriate for a local creative tool.
- Compare controls are simple and keyboard-friendly for split position.
- Mask modal separates tool rail, canvas, quick selects, and actions.
- Buttons generally use lucide icons and compact labels.

UI gaps:

- Main prompt text does not change enough by mode. Edit should say "Describe the change"; Inpaint should say "Describe what goes in the selected area."
- "Comfy expand" is implementation language; users need "Context padding" or "Mask expand for model."
- Inline mask editor has fewer tools than modal; users may miss full-screen controls.
- No context crop overlay.
- No in-canvas mask opacity/color control.
- No explicit Apply as New Layer / Replace / Discard decision after generation.
- No obvious "mask is empty" visual warning until save/generate validation.
- Accessibility gaps likely remain because canvas custom controls need manual screen-reader testing; keyboard mask drawing is not verified.

## 10. Inference and Image-Processing Audit

Verified good foundations:

- White mask means edit region in UI, selection backend, and mask preprocessing.
- Mask alpha is reduced to luminance/selection in UI imports and backend generated masks.
- Grow/feather preprocessing uses PIL MaxFilter and GaussianBlur.
- Large-image small-mask crop-and-stitch avoids wasting effective resolution.
- Generic inpaint uses `VAEEncodeForInpaint`; Flux Fill uses `InpaintModelConditioning` and `DifferentialDiffusion`.
- Non-Fill/crop paths composite generated output back over original using the processed mask.
- VRAM cleanup calls Comfy `/free` and Python GC.

Quality risks:

- Compositing is skipped for Flux Fill unless crop-stitch path is active. If Flux Fill modifies unmasked pixels, DreamForge may return leakage.
- `Image.composite()` with the processed mask preserves unmasked pixels only where mask is black. Feathered edges intentionally blend; tests must measure outside-mask leakage with a threshold.
- There is no color/lighting/grain match postprocess beyond model output and mask blend.
- Crop padding is fixed by constants and mask grow/feather. It should be inspectable and overrideable.
- Very small masks can still lack semantic context if crop padding is too small for the object.

## 11. Model-Routing Audit

Persona influence: Multi-Agent Systems Architect methodology was applied to routing contracts, fallback, observability, and avoiding unnecessary agent complexity.

Verified:

- `dreamforge_model_registry.py` defines capabilities for sdxl, sd15, flux, flux_kontext, flux_fill, qwen_image, qwen_image_edit, hidream, and ideogram4.
- `dreamforge_workflow_routing.py` resolves reference roles and normalizes `cn_selection`, `cn_type`, `edit_type`, input path, and plan mode.
- Flux Kontext and Flux Fill detection still include filename/family heuristics.
- Dry-run mode reports readiness, missing inputs, missing resources, and proposed patches.
- Agent and MCP execution are capability-gated and approval-gated.

Gap:

The current registry is a useful start but too coarse for edit/inpaint. It does not fully express native inpaint vs fill inpaint, soft mask support, alpha mask support, crop strategy, instruction-edit support, multiple references, identity conditioning, model-specific dimensions, quantized execution, and low-VRAM requirements.

## 12. Prioritized Gap Analysis

Critical:

- Prove or enforce unmasked pixel preservation for Flux Fill.
- Block inpaint generation before inference when input image or non-empty mask is missing.
- Surface invalid/incompatible model+mode combinations before Comfy graph submission.
- Preserve source image, mask, and settings across retries.

High:

- Backend-owned task presets with model-aware defaults, presented by the frontend.
- Context crop preview and padding control.
- Inspectable final edit instruction/prompt.
- Small result tray with candidate thumbnails, compare, retry same settings, and "use as current source"; defer layers.

Medium:

- Mask invert/fill/opacity/color controls.
- Better identity/reference workflow.
- Human-review benchmark suite.
- UI accessibility pass for custom canvas controls.

## 13. Target User Experience

Simple workflow:

1. Select or import image.
2. Choose task: Remove, Replace, Repair, Refine, Recolor, Relight, Restyle, Extend, or Global Edit.
3. Paint or auto-select target area when the task is local.
4. Type the change instruction.
5. Generate 1-4 candidates.
6. Compare with before/split.
7. Apply as new layer, replace current image, retry, or discard.

Advanced workflow:

- Model, workflow, sampler, scheduler, steps, guidance, denoise/edit strength, seed.
- Mask grow/shrink, feather, blur, hard mask.
- Context crop on/off, padding, target resolution.
- Masked content initialization where supported.
- Reference slots and identity preservation.
- Color match/seam blend options when implemented.
- Batch size and variations.

## 14. Target Technical Architecture

Keep the existing architecture:

React/Tauri UI -> typed GenerationSettings -> Python bridge/worker -> central router -> Comfy graph builder -> mask/crop/composite postprocess -> manifest/lineage.

Add only:

- `backend/dreamforge_model_capabilities.py` or extend `dreamforge_model_registry.py` with a richer capability schema.
- A shared frontend mirror in `apps/desktop/src/lib/modelCapabilities.ts` generated or kept in sync from backend output.
- `EditTask` enum: remove, replace, add, repair, refine, recolor, relight, restyle, extend, global_edit.
- `resolve_edit_task_defaults(task, model_capabilities, settings)` in Python, exposed through bridge dry-run; the frontend displays choices but does not own canonical defaults.
- `inpaint_context_preview` dry-run payload: crop box, padding, effective resolution, mask coverage.
- `final_edit_request` dry-run/manifest payload: user intent, final model instruction, negative prompt, preservation hints, and selected route.

## 15. Proposed UI Component Hierarchy

Main Edit/Inpaint workspace:

- `CanvasPanel`
- `TaskStrip`
  - Purpose: choose Remove/Replace/Repair/Refine/Extend/Global Edit.
  - Default: mode-specific suggested task.
  - Visibility: Edit and Inpaint.
  - Pipeline effect: sets edit task; backend dry-run returns canonical intent/strength/model route defaults.
- `MaskToolbar`
  - Brush, erase, subject, object tap, background, invert, fill, clear.
  - Default: brush.
  - Visibility: Inpaint and local edit tasks.
  - Pipeline effect: writes grayscale mask where white is edit area.
- `MaskEdgePanel`
  - Grow, shrink, feather, hard edge.
  - Default: task preset.
  - Visibility: advanced collapsed by default; summary visible.
  - Pipeline effect: `inpaint_grow`, `inpaint_feather`, `inpaint_hard_mask`.
- `ContextPreviewOverlay`
  - Shows crop box and padding.
  - Default: automatic.
  - Visibility: Inpaint after mask exists.
  - Pipeline effect: context crop strategy/padding fields.
- `InstructionPanel`
  - User instruction, optional masked-region prompt, negative prompt advanced.
  - Default: user instruction only.
  - Pipeline effect: prompt/instruction processing.
- `ResultTray`
  - Candidate thumbnails, before/split compare, apply, apply as layer, replace, retry, discard.
  - Default: hidden until result.
  - Pipeline effect: manifest lineage and project layer/history action.

## 16. Model-Capability Registry Proposal

Extend each model family/item with:

- `text_to_image`
- `image_to_image`
- `native_inpaint`
- `fill_inpaint`
- `outpaint`
- `instruction_edit`
- `kontext_edit`
- `qwen_edit`
- `reference_image_edit`
- `multiple_reference_images`
- `mask_input`
- `soft_mask`
- `requires_vae_encode_for_inpaint`
- `requires_inpaint_model_conditioning`
- `preferred_sampler`
- `preferred_scheduler`
- `preferred_steps`
- `preferred_guidance`
- `preferred_edit_strength_by_task`
- `dimension_alignment`
- `max_megapixels_by_vram`
- `quantized_execution`
- `cpu_offload`
- `required_companions`
- `required_custom_nodes`

First pass fields should be only what current routing consumes: `native_inpaint`, `fill_inpaint`, `instruction_edit`, `kontext_edit`, `qwen_edit`, `mask_input`, `multiple_reference_images`, `preferred_*`, `required_companions`, and `required_custom_nodes`. Add identity, ControlNet, IP-Adapter, alpha-mask, and soft-mask details only when a route actively consumes them.

Routing algorithm:

1. Classify task from explicit UI task first, then instruction text.
2. Determine required inputs: image, mask, references, identity.
3. Filter models/workflows by capabilities and installed resources.
4. Rank native task support first: Flux Fill for local inpaint, Qwen/Kontext for global instruction edit, SDXL/img2img for restyle fallback.
5. Dry-run returns selected route, rejected alternatives, missing inputs/resources, and user override risks.
6. If preferred route fails due missing dependency, offer download/fallback. If inference fails, do not silently switch model; show retry with fallback.

## 17. Prompt and Instruction-Processing Proposal

Persona influence: Image Prompt Engineer methodology was applied to separating instruction types and preserving original user text.

Add an inspectable request object:

```json
{
  "task": "replace",
  "scope": "masked_region",
  "user_instruction": "replace the mug with a glass vase",
  "model_prompt": "In the selected region, replace the mug with a clear glass vase. Preserve the surrounding table, lighting, camera angle, reflections, and background.",
  "negative_prompt": "distorted edges, seams, blur, duplicate objects",
  "preservation": ["unmasked_pixels", "lighting", "composition"],
  "model_family": "flux_fill"
}
```

Task mapping:

- Remove: requires mask; prompt emphasizes plausible background continuation.
- Replace/Add: requires mask; optional reference; higher strength.
- Repair/Improve detail: mask or auto-selection; lower strength; preserve identity.
- Change color/material/clothing: mask recommended; preserve shape/identity unless user says otherwise.
- Relight/Restyle: global edit unless mask present.
- Extend: outpaint; requires direction/canvas expansion.

Keep original user instruction in manifests and dry-run. Never hide the rewritten prompt.

## 18. Benchmark and Testing Strategy

Add `docs/benchmarks/edit-inpaint/` metadata and scripts later. Minimum cases:

- Small face correction
- Hand repair
- Object removal
- Object replacement
- Clothing replacement with face preservation
- Text removal
- Background repair
- Texture continuation
- Outpainting
- Identity-sensitive edit
- Product edit
- Architecture edit
- Very small mask
- Large mask
- Border-touching mask
- Hair/transparent edge
- Low-res source
- High-res source

For each store:

- Source, mask, instruction, model, workflow, seed, resolution, settings, runtime, peak VRAM, output, expected behavior.

Automated checks:

- Mask geometry round-trip.
- Non-empty mask validation.
- Crop box and stitch size.
- Pixel leakage outside original binary mask plus tolerance band.
- Manifest lineage contains source, mask, task, route, seed, settings.
- Dry-run rejects missing image/mask.
- Cancellation leaves no stuck generation state.

Human rubric:

- Prompt adherence, mask adherence, outside-mask preservation, seam visibility, color/lighting consistency, identity consistency, detail quality, repeatability.

## 19. Phased Implementation Roadmap

### Phase 0: Critical Correctness

1. Flux Fill outside-mask leakage test
   - Problem: Flux Fill path may skip final compositing.
   - Evidence: `dreamforge_generation.py` composites crop and non-Fill paths; Flux Fill full-image path is trusted.
   - Solution: add benchmark/unit integration hook that compares unmasked pixels; if leakage occurs, composite Flux Fill too.
   - Files: `dreamforge_generation.py`, `dreamforge_krita_resources.py`, `backend/tests/test_krita_resources.py`.
   - Risk: Medium.
   - Complexity: Small.
   - Acceptance: outside-mask pixels match source except feather tolerance.

2. Non-empty mask preflight
   - Problem: generation can reach backend with empty/invalid masks from settings.
   - Evidence: modal blocks export, but backend should guard trust boundary.
   - Solution: validate mask bbox after resize/preprocess; return `invalid_request`.
   - Files: `dreamforge_generation.py`, `dreamforge_krita_resources.py`.
   - Risk: Low.
   - Complexity: Small.
   - Acceptance: dry/live run rejects empty masks before Comfy.

3. Context crop dry-run payload
   - Problem: automatic crop is invisible.
   - Evidence: crop-and-stitch emits progress only during generation.
   - Solution: expose crop box, padding, crop resolution in dry-run/readiness.
   - Files: `dreamforge_cli_direct.py`, `dreamforge_krita_resources.py`, frontend dry-run panel.
   - Risk: Low.
   - Complexity: Medium.
   - Acceptance: Inpaint UI can preview crop before generation.

### Phase 0.5: Routing Observability

4. Prompt inspection
   - Problem: rewritten model request is hidden, making edit/inpaint routing hard to debug.
   - Evidence: UI has user prompt and preservation toggles, but no verified final model instruction preview.
   - Solution: add final request preview to dry-run and manifest with both user intent and final model instruction.
   - Files: `dreamforge_prompt_pipeline.py`, `dreamforge_generation.py`, `WorkflowPlanPanel.tsx`.
   - Risk: Low.
   - Complexity: Small.
   - Acceptance: dry-run and manifests show user instruction, final model prompt, negative prompt, preservation hints, and route.

### Phase 1: Quality and Reliability

5. Task presets
   - Problem: Default/Detail/Modify is too coarse.
   - Solution: add Remove, Replace, Repair, Refine, Extend, Global Edit mapping to existing settings, with canonical defaults resolved in Python and returned via dry-run.
   - Files: `dreamforge_inpaint_intent.py`, `dreamforge_workflow_planner.py`, `lib/inpaintIntent.ts`, `EditFamilySettingsPanel.tsx`.
   - Risk: Low.
   - Complexity: Medium.
   - Acceptance: one click asks backend for route/strength/mask defaults; frontend/backend do not drift.

6. Minimal model capability registry pass
   - Problem: routing still mixes registry and filename checks.
   - Solution: extend only capabilities used by current routing and make dry-run explain decisions.
   - Files: `dreamforge_model_registry.py`, `dreamforge_workflow_routing.py`, tests.
   - Risk: Medium.
   - Complexity: Medium.
   - Acceptance: tests cover qwen/kontext/fill/img2img/incompatible fallback.

### Phase 2: UX and UI

7. Inpaint workspace task strip and clearer labels
   - Problem: users must infer workflows.
   - Solution: add compact task controls; rename "Comfy expand."
   - Files: `CanvasPanel.tsx`, `EditFamilySettingsPanel.tsx`, `PromptBar.tsx`.
   - Risk: Low.
   - Complexity: Medium.
   - Acceptance: common tasks need image, mask/select, instruction, generate.

8. Result tray
   - Problem: one result preview is not enough for iterative edits.
   - Solution: first pass is candidate thumbnails, compare, retry same settings, and "use as current source." Defer apply-as-layer and asset-management behavior.
   - Files: `CanvasPanel.tsx`, history/manifest utilities.
   - Risk: Medium.
   - Complexity: Medium.
   - Acceptance: candidate choice is traceable, and retry/source reuse does not lose original source/mask/settings.

9. Accessibility pass
   - Problem: canvas interactions are custom and not fully keyboard/screen-reader verified.
   - Solution: keyboard equivalents for mask actions, labeled icon buttons, focus states, live status.
   - Files: mask components, prompt/canvas controls.
   - Risk: Low.
   - Complexity: Medium.
   - Acceptance: WCAG 2.2 AA manual keyboard flow for edit/inpaint.

### Phase 3: Advanced Editing

10. Extend/outpaint UI
   - Problem: backend graph exists without first-class UX.
   - Solution: direction handles, expansion size, feather, preview.
   - Files: `CanvasPanel.tsx`, `EditFamilySettingsPanel.tsx`, `dreamforge_comfy_workflows.py`.
   - Risk: Medium.
   - Complexity: Medium.

11. Optional segmentation upgrades
   - Problem: rembg/heuristics are useful but limited.
   - Solution: optional SAM/Impact/YOLO packs behind approval/download.
   - Files: `dreamforge_inpaint_selection.py`, dependency catalog.
   - Risk: Medium.
   - Complexity: Large.

12. Identity/reference conditioning
   - Problem: preservation hints are not always enforceable.
   - Solution: explicit reference slots and identity route when assets available.
   - Files: `ReferenceSlotsEditor.tsx`, `dreamforge_identity.py`, IPAdapter graph builders.
   - Risk: High.
   - Complexity: Large.

## 20. Risks and Regression Controls

- Generate-mode regressions: preserve `sanitizeSettingsForStudioMode()` behavior and add route matrix tests.
- Model compatibility: all new routing must go through dry-run before live generation.
- Pixel preservation: add golden tests around mask preprocessing/compositing.
- VRAM: keep crop-stitch and source megapixel caps; benchmark before raising defaults.
- Agent complexity: keep Agent mode advisory/approval-gated; do not require agents for normal edits.
- Custom nodes: keep missing-node detection and companion download approval.

## 21. Definition of Done

- Inpaint with a mask preserves unmasked pixels by test.
- Dry-run explains selected task, model, workflow, user intent, final model instruction, mask status, crop/context region, and missing resources.
- Simple mode supports Remove/Replace/Repair/Refine/Extend without exposing Comfy terms.
- Advanced mode exposes strength, mask edge, context padding, model/workflow, seed, sampler, scheduler, steps, guidance.
- Result application is non-destructive and records lineage.
- Benchmark suite includes representative source/mask/instruction/settings/result records.
- No Generate-mode route tests regress.

## Implementation Checklist

- [x] Add backend non-empty mask validation.
- [x] Add Flux Fill outside-mask leakage regression test.
- [x] Add inpaint crop/context dry-run payload.
- [x] Add prompt/instruction inspection to dry-run and manifest.
- [x] Add backend-owned task preset enum and defaults.
- [x] Rename/clarify mask edge controls in UI.
- [x] Extend model capability registry only for current routing fields.
- [x] Add context crop overlay.
- [x] Add small result tray: thumbnails, compare, retry same settings, use as source.
- [x] Add outpaint UI.
- [x] Add edit/inpaint benchmark folder and manifest schema.
- [x] Run accessibility audit for keyboard/screen-reader paths.

Remaining validation: run real Flux Fill leakage samples and a manual screen-reader pass before calling the feature release-ready.

## Verification Boundaries

Verified from code: UI components, state flow, Tauri/bridge/worker lifecycle, routing, Comfy graph builders, mask preprocessing, crop-stitch, compositing, dependency checks, agent/MCP approval gates, and existing tests listed above.

Supported by external research: competitor control sets, canvas/result workflow expectations, crop/padding/inpaint-control conventions, and node/workflow examples.

Reasonable architectural inference: richer capability registry and task presets can be added incrementally because current route normalization and dry-run already exist.

Requires prototype validation: Flux Fill leakage behavior across real models, whether Flux Fill needs forced compositing, color/lighting match postprocess, SAM/segmentation quality, result tray workflow ergonomics, and benchmark score thresholds.
