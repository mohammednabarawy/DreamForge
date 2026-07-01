# DreamForge ComfyUI Workflow Support Plan

Date: 2026-06-30

## Purpose

This plan translates the ComfyUI workflows in `D:\ComfyUI_windows_portable\ComfyUI\user\default\workflows` into a safe DreamForge implementation roadmap. The goal is to add useful workflow capabilities inside the app without duplicating existing DreamForge features, replacing stronger current implementations, or adding fragile one-off workflow imports where a maintained native graph builder is better.

The plan is based on:

- Review of 38 local ComfyUI workflow JSON files.
- Review of current DreamForge backend graph builders, routing, recipes, desktop UI surfaces, and tests.
- Web research for current Qwen, Ideogram4, ControlNet restoration, outfit segmentation, RMBG, Ultimate SD Upscale, Nunchaku guidance, and dynamic ComfyUI workflow-ingestion patterns.

## Non-Negotiable Guardrails

1. **Do not replace better current DreamForge implementations.**
   - Keep existing native graph builders in `backend/dreamforge_comfy_workflows.py` as the primary implementation path.
   - Use imported ComfyUI workflows only as references for settings, dependencies, and UX, not as hard-coded monolithic templates unless a feature truly requires it.

2. **Do not duplicate already-supported features.**
   - Qwen Image/Edit, HiDream O1, Ideogram4, Flux/Krea/Nunchaku, Ultimate SD Upscale, ControlNet, inpaint/outpaint, IP-Adapter, FaceID, and face-detail paths already exist in some form.
   - New work should extend these surfaces through presets, routing, capability checks, and UI affordances.

3. **Prefer DreamForge-native route builders for core tools, but plan a bounded custom-workflow sandbox.**
   - Native builders allow settings validation, model inventory resolution, Render/Linux path safety, preflight checks, lints/tests, and consistent UI behavior.
   - Direct workflow-template execution should not replace core builders, but DreamForge needs a controlled **Custom Tools / Pro Sandbox** path so advanced users can run new ComfyUI patterns without waiting for a first-party release.
   - Imported workflows must be schema-parsed, dependency-checked, and mapped onto DreamForge inputs (`prompt`, `negative_prompt`, reference slots, masks, output nodes) instead of executed as opaque JSON.

4. **Keep user experience workflow-like and avoid top-level feature clutter.**
   - For Qwen multi-image edit and similar prompt-guided models, the default UI should be: attach images, reference them as `image 1`, `image 2`, `image 3`, and let the prompt guide the model.
   - Advanced per-image roles, weights, and stop-at controls should remain available but not dominate the default flow.
   - New recipes such as Photo Restore, Outfit Transfer, Cutout Compose, and Portrait Master should live under a grouped **Creative Toolbox** surface rather than becoming separate top-level app modes.
   - When the prompt contains `image 1`, `image 2`, or `image 3`, the matching thumbnail should highlight to confirm the binding without large instructional panels.

5. **Every new feature needs preflight and fallback behavior.**
   - Check ComfyUI node availability via `object_info`.
   - Check model assets via DreamForge inventory and companion-download helpers.
   - If custom nodes are missing, fail with actionable remediation rather than silently falling back to a different behavior.

## Current DreamForge Coverage

### Qwen Image / Qwen Image Edit

Current support:

- `backend/dreamforge_comfy_workflows.py`
  - `comfy_qwen_image_txt2img`
  - `comfy_qwen_image_edit`
  - `comfy_qwen_image_edit_plus`
  - `_apply_qwen_model_sampling`
  - `_apply_qwen_lightning_lora`
  - `_maybe_scale_qwen_pixels`
  - `_qwen_preserve_source_pixels`
- `backend/dreamforge_krita_recipes.py`
  - `qwen_image_edit` recipe with Qwen 2509/2511 model names, `cfg=1.0`, `sampler=euler`, `scheduler=simple`, `qwen_image_shift=3.1`.
- `apps/desktop/src/lib/multiImageCompose.ts`
  - Newer UI routing pattern: attach multiple images and prompt them as `image 1`, `image 2`, `image 3`.
- Tests already cover Qwen single edit, Plus edit, raw/preserve resolution path, and multi-reference routing.

What not to duplicate:

- Do not add a separate Qwen workflow-template executor for `image_qwen_image_edit_2509*.json`.
- Do not remove the raw-latent preserve-resolution path; it is better for layout/text fidelity than the stock `TextEncodeQwenImageEditPlus` VAE-rescale path when precision matters.

Safe improvement:

- Add a named **Qwen 2509 Lightning 4-step** preset that uses the existing graph builder and existing LoRA resolution logic.

### Ideogram4

Current support:

- `backend/dreamforge_comfy_workflows.py`
  - `comfy_ideogram4_txt2img`
  - `comfy_ideogram4_img2img`
  - `comfy_ideogram4_inpaint`
  - `_ideogram4_graph_params`
  - `_ideogram4_build_dual_unet_guider`
  - `_ideogram4_build_sampler_decode_save`
- `backend/dreamforge_prompt/ideogram4.py`
  - Mode resolution and scheduler params.
- Desktop:
  - `IdeogramCaptionTemplatesMenu`
  - `IdeogramJsonPreview`
  - `IdeogramLayoutModal`
  - Layout builder bridge functions in `apps/desktop/src/lib/studioBridge.ts`.

What not to duplicate:

- Do not replace DreamForge's existing Ideogram4 JSON/template/layout UI with KJNodes-specific UI.
- Do not require `Ideogram4PromptBuilderKJ` as a dependency. DreamForge already has an internal schema/template path.

Safe improvement:

- Improve the existing visual JSON caption builder with object cards, bbox editing, palettes, and "natural prompt to structured JSON" generation.

### HiDream O1

Current support:

- `backend/dreamforge_comfy_workflows.py`
  - `comfy_hidream_o1_dev_txt2img`
  - `comfy_hidream_o1_reference_images`
  - `HiDreamO1ReferenceImages`
  - `ModelNoiseScale`
  - `SamplerLCM`
  - `SamplerCustom`
- `backend/dreamforge_hidream_o1_profiles.py`
  - Lightning, Speed, Quality profiles.
- Desktop:
  - HiDream performance preview and profile application in `apps/desktop/src/lib/hidreamPerformance.ts` and `hidreamO1Profiles.ts`.

What not to duplicate:

- Do not add a second HiDream graph based on local workflow JSON.
- Do not force IP-Adapter for HiDream O1 references; HiDream O1 has native reference conditioning.

Safe improvement:

- Consider testing workflow value `ModelNoiseScale=7.5` against current DreamForge `7.6`. Treat as an A/B candidate, not a guaranteed better default.

### Ultimate SD Upscale / Enhance

Current support:

- `backend/dreamforge_comfy_workflows.py`
  - `comfy_upscale_basic`
  - `comfy_ultimate_sd_upscale`
  - `comfy_pid_flux_upscale`
- `backend/dreamforge_upscale_defaults.py`
- `backend/dreamforge_upscale_presets.py`
- Desktop settings already expose many upscale parameters through `GenerationSettings`.

What not to duplicate:

- Do not add separate `ultimate upscale.json`, `medo upscale.json`, or `THE Ultimate UPscaler...json` runners.
- Keep DreamForge's current upscale presets and use workflow settings only as new preset variants.

Safe improvement:

- Add a **Fast 4x ESRGAN/Ultimate** preset and a **Faithful 2x** preset based on current best-practice ranges.

### ControlNet, Inpaint, Outpaint, Face Detail

Current support:

- `backend/dreamforge_comfy_workflows.py`
  - `comfy_controlnet_basic`
  - `comfy_ipadapter_controlnet_hybrid`
  - `comfy_flux_fill_inpaint`
  - `comfy_inpaint_basic`
  - `comfy_outpaint_basic`
  - `comfy_face_detail_basic`
- Tests already check ControlNet, inpaint, outpaint, and FaceDetailer behavior.

What not to duplicate:

- Do not add another generic ControlNet route if current `controlnet_basic` and hybrid routes already cover it.
- Do not replace inpaint mask preprocessing and crop/stitch behavior unless measured quality improves.

Safe improvement:

- Add specific task-level recipes: Photo Restore and Outfit Transfer, built on top of existing ControlNet/inpaint primitives.

### Flux / Krea / Nunchaku / GGUF

Current support:

- `backend/dreamforge_comfy_workflows.py`
  - Krea and Flux family graph builders.
  - Nunchaku/SVDQ-aware loader behavior in model-loader helpers.
- DreamForge already handles GGUF and diffusion-model categories in multiple paths.

What not to duplicate:

- Do not add a standalone `nunchaku-flux.1-dev.json` executor.
- Treat Nunchaku workflow data as loader/preflight validation, not a separate feature surface.

Safe improvement:

- Add clearer model inventory detection and UI hints for Nunchaku INT4/FP4 Flux variants.

## Workflow Inventory Summary

### Qwen Image / Qwen Edit Workflows

Local files:

- `image_qwen_image.json`
- `image_qwen_image_edit.json`
- `image_qwen_image_edit_2509.json`
- `image_qwen_image_edit_2509_2.json`
- `image_qwen_image_edit_2509_NSFW.json`

Observed settings:

- Qwen image txt2img: `1328x1328`, `20 steps`, `cfg=1`, `euler`, `simple`, `ModelSamplingAuraFlow=3.1`.
- Qwen edit: `TextEncodeQwenImageEdit` / `TextEncodeQwenImageEditPlus`, `ImageScaleToTotalPixels`, `ModelSamplingAuraFlow=3`, `CFGNorm=1`.
- 2509 Lightning workflows: `4 steps`, `cfg=1`, `euler`, `simple`, Lightning LoRA, up to 3 input images.

External research:

- Qwen Image Edit 2509 supports 1-3 reference images and prompt-guided multi-image composition.
- Lightning 4-step guidance: `4 steps`, `cfg=1.0`, `euler`, `simple`; CFG above ~1.5 can degrade Lightning results.
- Required assets usually include Qwen Edit diffusion model, `qwen_2.5_vl_7b_fp8_scaled`, `qwen_image_vae`, and Lightning LoRA.

DreamForge action:

- Add preset, not a new graph.
- Preserve current raw-latent path for high-fidelity edits.

### Ideogram4 Workflows

Local files:

- `image_ideogram4_t2i.json`
- `image_ideogram4_t2i by oneway.json`

Observed settings:

- Structured JSON captions.
- `Ideogram4Scheduler`.
- Quality/Default/Turbo presets:
  - Quality: `48 steps`, `mu=0.0`, `std=1.5`.
  - Default: `20 steps`, `mu=0.0`, `std=1.75`.
  - Turbo: `12 steps`, `mu=0.5`, `std=1.75`.
- `Ideogram4PromptBuilderKJ` appears in one workflow, but DreamForge should not depend on it.

External research:

- Ideogram4 is trained on structured JSON captions; JSON reduces prompt ambiguity and false-positive safety blocking compared with plain text in some workflows.
- Official/open-source workflows support natural language for quick use and structured JSON for precise layout, palettes, typography, and bboxes.

DreamForge action:

- Expand existing internal Ideogram UI; do not add KJNodes dependency.

### HiDream O1 Workflow

Local files:

- `hidream_o1_image DEV.json`

Observed settings:

- `HiDreamO1ReferenceImages`.
- `EmptyHiDreamO1LatentImage` at `2048x2048`.
- `ModelNoiseScale=7.5`.
- `SamplerLCM [1, 1, 2.5]`.
- `BasicScheduler normal`, `28 steps`.

DreamForge action:

- Keep current native implementation.
- A/B test `7.5` vs `7.6`.

### Photo Restore Workflow

Local files:

- `restore photo.json`

Observed settings:

- `DepthAnythingV2Preprocessor`.
- `LineArtPreprocessor`.
- Multiple `ControlNetApplyAdvanced` nodes with strengths roughly `0.1`, `0.2`, `0.5`.
- `ImageScaleToTotalPixels nearest-exact`, `2 MP`.
- KSampler: `6 steps`, `cfg=1.5`, `dpmpp_2s_ancestral_cfg_pp`, `karras`.

External research:

- Common restoration patterns combine structure preservation via ControlNet depth/lineart/openpose with face enhancement/detail restoration and optional upscale.
- ControlNet Union can simplify model dependencies if control type selection is handled correctly.

DreamForge action:

- Implement a task-level **Restore Photo** recipe.
- Use existing ControlNet/inpaint/detailer primitives.
- Do not replace generic ControlNet.

### Outfit Transfer Workflows

Local files:

- `outfit-to-outfit-controlnet.json`
- `outfit-to-outfit-controlnet-2.json`
- `outfit-to-outfit-manual-mask.json`
- `workflow-comfyui---outfit-to-outfit-controlnet-model-ATd5EuWsQ2OvCwT85R0W-cgtips-openart.ai.json`

Observed settings:

- `LayerMask: SegformerB2ClothesUltra`.
- Clothing segmentation masks.
- SDXL ControlNet Union or ControlNet loaders.
- Inpaint/mask-constrained KSampler variations.
- Common samplers: `dpmpp_2m karras`, `dpmpp_sde karras`.

External research:

- `SegformerB2ClothesUltra` is used for fast automated clothing masks.
- Virtual try-on workflows depend heavily on accurate body region selection and clean outfit reference images.
- For reliability, support manual masks as an override.

DreamForge action:

- Implement as **Outfit Transfer** task, not as generic reference-image behavior.
- Require explicit user confirmation of garment region or mask.

### RMBG / Product Compose Workflows

Local files:

- `put it here workflow .json`
- `free put it here workflow .json`

Observed settings:

- `RMBG` with BEN2-like background removal.
- `ImageResizeKJv2`.
- `ReferenceLatent`.
- Kontext-like composition.
- `GrowMask`, mask-to-image, blending nodes.

External research:

- `ComfyUI-RMBG` supports BEN2, RMBG-2.0, INSPYRENET, BiRefNet, SAM, GroundingDINO, and outputs both image and mask.
- RMBG is useful for product/person cutout workflows and foreground/background compositing.

DreamForge action:

- Add **Cutout Compose** or **Put Object Here** task after Restore Photo/Outfit Transfer.
- Consider a Python-native or Comfy-node path only after dependency review.

### Upscale Workflows

Local files:

- `ultimate upscale.json`
- `medo upscale.json`
- `medo Workflow2.json`
- `THE Ultimate UPscaler (with hidream o1)).json`
- `THE Ultimate UPscaler (with hidream o1))-edited.json`
- `the_writer_fantasy_light_show___woman_comfyworkflows.json`

Observed settings:

- `UltimateSDUpscale`.
- Common denoise range: `0.2` to `0.5`.
- Tile sizes: `512`, `1024`.
- Fast local workflow: `4x`, `4 steps`, `cfg=8`, `euler normal`, `denoise=0.2`, tile `1024`.
- High-quality SDXL workflow: face/detail repair, tiled upscale, denoise around `0.26`.

External research:

- Denoise `0.15-0.35` is typical for faithful upscales; `0.2-0.5` is a broader range.
- `512x512` tiles are a safe default; larger tiles reduce count but increase VRAM.
- Padding `64-128` helps context; seam-fix modes are useful when tile artifacts appear.

DreamForge action:

- Keep current upscale implementation.
- Add preset variants only.

### Nunchaku Flux Workflow

Local files:

- `nunchaku-flux.1-dev.json`
- `Flux1-Krea-FP8-GGUF.json`

Observed settings:

- Nunchaku-specific loader.
- `BasicScheduler simple`, `8 steps`, denoise `1`.
- `FluxGuidance=3.5`.
- `SamplerCustomAdvanced`.

External research:

- Nunchaku supports quantized Flux variants with INT4/FP4 model choices depending on GPU architecture.
- Typical Flux dev quality still benefits from `20-30 steps`; `8 steps` is a speed-oriented profile.

DreamForge action:

- Add better detection/preflight and UI profile labels for Nunchaku Flux.
- Do not add a separate graph if current loader helpers already support the family.

## Phased Implementation Roadmap

### Phase 0 - Safety Review and Test Baseline

Goal: protect current behavior before adding anything.

Tasks:

- Run current backend targeted suites:
  - `backend/tests/test_comfy_workflows.py`
  - `backend/tests/test_generation_routing.py`
  - `backend/tests/test_krita_recipes.py`
  - `backend/tests/test_ideogram4_prompt.py`
  - `backend/tests/test_upscale_presets.py`
- Add a route capability matrix in tests covering:
  - Qwen multi-image compose.
  - Qwen raw-latent preserve mode.
  - HiDream O1 native refs.
  - Ideogram4 JSON prompt modes.
  - ControlNet/inpaint/upscale route separation.

Acceptance criteria:

- No current graph builder is replaced.
- All existing tests pass.
- New tests describe behavior before implementation begins.

### Phase 1 - Qwen 2509/2511 Workflow-Like Compose Polish

Goal: match the local Qwen 2509 workflow UX and settings while preserving DreamForge's better raw-latent fidelity path.

Implementation:

- Add `qwen_lightning_profile` or extend `qwen_edit_mode` with a `lightning_4step` preset.
- When a 4-step Lightning LoRA is detected:
  - `steps=4`
  - `cfg=1.0`
  - `sampler=euler`
  - `scheduler=simple` by default, with optional `beta` only if model testing confirms better local results.
  - `qwen_lightning_strength=1.0`
  - `qwen_image_shift=3.0` for 2509, keep `3.1` for current 2511/default unless tests show otherwise.
- Keep `raw_plus`/preserve-resolution path available and auto-enabled for text/layout preservation.
- Add a compact prompt placeholder/helper:
  - `Try: "Use image 1 as the person, image 2 as the outfit, image 3 as the background."`
  - Do not add large instructional panels in the reference list.
- Enforce Qwen's 3-image total cap in UI when the selected/auto-routed model is Qwen Edit.

Files likely touched:

- `backend/dreamforge_krita_recipes.py`
- `backend/dreamforge_generation.py`
- `backend/dreamforge_comfy_workflows.py`
- `apps/desktop/src/lib/qwenPreserveAtSubmit.ts`
- `apps/desktop/src/lib/multiImageCompose.ts`
- `apps/desktop/src/components/PromptBar.tsx`
- `apps/desktop/src/components/ReferenceSlotsEditor.tsx`

Tests:

- Verify 4-step LoRA preference chooses 4-step LoRA when present.
- Verify 8-step fallback remains available.
- Verify raw-latent path is not disabled by 4-step preset.
- Verify UI caps Qwen compose references at 3.

### Phase 2 - Creative Toolbox

Goal: add high-value tools ("Restore Photo", "Outfit Transfer", "Cutout Compose") inside DreamForge in a unified Creative Toolbox grouping.

Implementation:
- Add `edit_task` choices for `"photo_restore"`, `"outfit_transfer"`, and `"cutout_compose"`.
- Use existing inpaint/controlnet primitives where possible.
- **Photo Restore**:
  - Add preprocessors: Depth Anything V2/V3, LineArt, Canny fallback.
  - Add ControlNet Union routing with low strengths.
- **Outfit Transfer**:
  - Add SegformerB2ClothesUltra for automatic mask, with manual mask fallback.
  - Prefer Qwen Edit multi-image compose, falling back to Flux Fill.
- **Cutout Compose**:
  - If `ComfyUI-RMBG` exists, use `RMBG` or BEN2 node.
  - Harmonize lighting and perspective with Qwen/Kontext.

Files likely touched:
- `backend/dreamforge_comfy_workflows.py`
- `backend/dreamforge_generation.py`
- `backend/dreamforge_workflow_planner.py`
- `apps/desktop/src/lib/creativeTask.ts`
- `apps/desktop/src/components/CreativeToolboxPanel.tsx`

Tests:
- Missing dependencies give actionable errors (e.g. Segformer, RMBG).
- Existing paths remain unchanged.
- Output path handles mask previews if needed.



### Phase 3 - Upscale Preset Improvements

Goal: incorporate workflow and web-researched upscale defaults as presets, not replacement defaults.

Implementation:

- Add preset names:
  - `faithful_2x`: denoise `0.2-0.25`, tile `768-1024`, padding `64`.
  - `fast_4x`: `4 steps`, `cfg=8`, `euler`, `normal`, denoise `0.2`, tile `1024`, upscaler ESRGAN/UltraSharp if installed.
  - `detail_2x`: denoise `0.3-0.35`, tile `512-768`, padding `96-128`.
- Keep existing presets intact and expose new ones as alternatives.
- Add warnings when `upscale_by >= 4` with large tiles on low VRAM.

Files likely touched:

- `backend/dreamforge_upscale_presets.py`
- `backend/dreamforge_upscale_defaults.py`
- `apps/desktop/src/components/GenerationSettingsPanel.tsx`

Tests:

- Existing upscale preset tests remain valid.
- New presets produce expected parameter patches.

### Phase 4 - Ideogram4 Layout Builder Enhancement

Goal: improve current Ideogram support using the workflow's structured-caption ideas without requiring KJNodes.

Implementation:

- Extend existing layout modal:
  - Object cards with text/description.
  - Normalized bbox editing.
  - Palette picker.
  - Background/style fields.
  - "Generate JSON from natural prompt" action.
- Add validation before submit:
  - Required top-level keys.
  - Aspect ratio consistency.
  - Valid bbox ranges.
  - Valid hex colors.
- Keep `natural` mode for quick generation, but prefer JSON for posters/text-heavy layouts.

Files likely touched:

- `apps/desktop/src/components/IdeogramLayoutModal.tsx`
- `apps/desktop/src/components/IdeogramJsonPreview.tsx`
- `backend/dreamforge_prompt/ideogram4.py`
- `backend/dreamforge_desktop_bridge.py`

Tests:

- Existing Ideogram prompt tests remain valid.
- Add malformed JSON validation tests.
- Add layout-to-caption roundtrip tests.



### Phase 5 - Custom Tools / Pro Sandbox

Goal: let advanced users run carefully validated ComfyUI workflow JSONs without turning every new node trend into a hard-coded DreamForge feature.

Implementation:

- Add a **Custom Tools** entry under the Creative Toolbox, not a top-level mode.
- Import a ComfyUI workflow JSON into a saved local tool definition.
- Parse graph schema and identify bindable nodes:
  - `LoadImage`, image upload nodes, and mask nodes map to DreamForge reference slots.
  - `CLIPTextEncode`, Qwen text encoders, and common prompt nodes map to prompt and negative prompt boxes.
  - Checkpoint, LoRA, VAE, ControlNet, upscaler, and custom-node references map to inventory/preflight requirements.
  - Save/output nodes map to DreamForge's normal output manifest path.
- Let users expose selected widgets as tool controls with labels, ranges, defaults, and descriptions.
- Store the imported tool as metadata plus the original workflow JSON; do not mutate the source file.
- Execute only after dependency validation passes.

Risks:

- Opaque workflows can hide incompatible nodes, missing assets, unsafe paths, or fragile custom-node assumptions.
- Imported controls can overwhelm users if every widget is exposed by default.
- Node schemas drift quickly, so parser errors must be readable and recoverable.

Guardrails:

- Keep native builders as the default for core DreamForge features.
- Import workflows as expert tools with clear warnings and dependency checks.
- Start with image workflows only: text/image generation, edit, inpaint, reference compose, restore, segmentation, and upscale.
- Do not allow imported workflow JSONs to bypass path normalization, model inventory checks, or output manifest handling.

## Dependency Plan

### Core / Already Expected

- ComfyUI core nodes:
  - `TextEncodeQwenImageEditPlus`
  - `ReferenceLatent`
  - `Ideogram4Scheduler`
  - `HiDreamO1ReferenceImages`
  - `UltimateSDUpscale`
  - `ControlNetApplyAdvanced`

### Optional Feature Dependencies

- Photo Restore:
  - ControlNet auxiliary preprocessors.
  - Depth Anything V2/V3.
  - LineArt preprocessor.
  - ControlNet Union SDXL/Flux models.
  - Impact Pack/SAM/Ultralytics for optional face detail.

- Outfit Transfer:
  - `ComfyUI_LayerStyle` or Segformer Ultra Fast nodes.
  - Segformer clothing model assets.

- Cutout Compose:
  - `ComfyUI-RMBG`.
  - BEN2/RMBG-2.0/BiRefNet assets.

- Nunchaku:
  - `ComfyUI-nunchaku`.
  - INT4/FP4 model variants depending on GPU.

## Testing Strategy

1. **Graph unit tests**
   - Verify each new route builds the expected node classes.
   - Verify existing routes are unchanged.

2. **Routing tests**
   - Generate vs Edit vs Inpaint vs Upscale modes must not cross-route incorrectly.
   - Multi-image compose must not steal structure/ControlNet jobs.

3. **Dependency/preflight tests**
   - Missing custom nodes produce `missing_custom_node_pack` or equivalent actionable error.
   - Missing models produce `missing_model_dependencies` with install suggestions.

4. **UI tests / lint**
   - TypeScript lints for new settings.
   - Reference UI must stay compact.
   - Advanced controls must not obscure default attach-and-prompt flow.

5. **Manual smoke tests**
   - Qwen: 2-image and 3-image compose.
   - Photo Restore: old/low-res portrait.
   - Outfit Transfer: source person + garment reference + manual mask.
   - Upscale: 2x faithful and 4x fast.
   - Ideogram4: natural prompt and structured JSON.

## Implementation Priority

### Highest Impact / Lowest Risk

1. Qwen 2509/2511 4-step Lightning preset.
2. Qwen compact prompt helper and 3-image cap.
3. Upscale preset additions.
4. Ideogram4 layout builder polish.

### Medium Risk / High Value

5. Creative Toolbox grouping (Photo Restore, Outfit Transfer, Cutout Compose).

### Large Feature

6. Custom Tools / Pro Sandbox workflow importer.
7. Visual workflow-binding editor for imported tool inputs.

## External Research References

- Qwen Image Edit 2509 multi-image workflow:
  - https://www.runcomfy.com/comfyui-workflows/qwen-image-edit-2509-in-comfyui-multi-image-merge-edit
  - https://www.stablediffusiontutorials.com/2025/09/qwen-image-edit-2509.html
  - https://sbcode.net/genai/qwen-lighting-lora/
- Ideogram4:
  - https://docs.comfy.org/tutorials/image/ideogram/ideogram-v4
  - https://docs.comfy.org/built-in-nodes/Ideogram4Scheduler
  - https://github.com/ideogram-oss/ComfyUI-Ideogram4/blob/main/README.md
- Photo restore / ControlNet:
  - https://learn.thinkdiffusion.com/old-photo-restoration-with-comfyui/
  - https://www.runcomfy.com/comfyui-workflows/restore-old-photos-using-comfyui
  - https://apatero.com/blog/controlnet-union-one-model-all-controls-guide-2025
- Outfit segmentation:
  - https://comfyai.run/documentation/LayerMask:%20SegformerB2ClothesUltra
  - https://www.runcomfy.com/comfyui-nodes/ComfyUI-Segformer_Ultra_Fast/segformer-b2-clothes-ultra-batch
  - https://github.com/asutermo/ComfyUI-Flux-TryOff
- RMBG:
  - https://github.com/1038lab/ComfyUI-RMBG
  - https://1038lab.github.io/ComfyUI-RMBG/
  - https://comfy.icu/node/RMBG
- Ultimate SD Upscale:
  - https://comfyui.dev/docs/guides/nodes/ultimate-sd-upscale
  - https://deepwiki.com/ssitu/ComfyUI_UltimateSDUpscale/1.2-configuration-options
- Nunchaku:
  - https://github.com/nunchaku-ai/ComfyUI-nunchaku/blob/main/example_workflows/nunchaku-flux.1-dev.json
  - https://deepwiki.com/mit-han-lab/ComfyUI-nunchaku/4.1.1-basic-flux-text-to-image-generation
  - https://nunchaku.tech/docs/ComfyUI-nunchaku/get_started/usage.html
- ComfyUI workflow import / schema:
  - https://docs.comfy.org/essentials/core-concepts/workflows
  - https://docs.comfy.org/specs/workflow_json

## Cross-Review Synthesis

This section consolidates two independent reviews: [Comfy workflow analysis](eb2e4d75-fb52-4d82-b946-8cf8ee935b99) and [DreamForge coverage audit](ac92011f-bcee-4ffd-aa75-e5f7f6c7c7ad).

### Confirmed architecture

- The desktop product path is `dreamforge_comfy_workflows.py` plus routing in `dreamforge_generation.py`, `dreamforge_comfy_workflow_import.py`, and `dreamforge_workflow_routing.py`.
- Every new feature must register in `backend/dreamforge_feature_surfaces.py` (`UI_SURFACE_TO_COMFY_MODES`, `COMFY_MODE_GRAPH_BUILDERS`) and pass the feature-surface audit tests.
- Imported workflows should pass through schema parsing and feature-surface validation before execution.

### Additional roadmap items (from workflow review)

| Item | Priority | Notes |
|------|----------|-------|
| Local Ideogram4 model + `Ideogram4Scheduler` | Medium | Prompt/layout stack exists; local `ideogram4_fp8_scaled` generation is not fully wired in `model_classifier.py`. |
| HiDream O1 → Flux2-Klein refine pass | Medium | Optional second-stage refine from ultimate-upscaler workflows; both families already supported separately. |
| Portrait Master parameter panel | Low | Slider-driven portrait prompts + pose/depth CN; new UI, not a new core engine. |
| Offline GLM-4V prompt enhancer | Low | Optional alternative to existing `flux_llm_enhance` / studio enhance; not a replacement. |
| Capability registry expansion | Medium | Align with `docs/plans/dreamforge-edit-inpaint-optimization.md` section 16; reduces filename-heuristic drift. |

### Do-not-regress list (audit highlights)

- `dreamforge_comfy_models.py` family-aware VAE/loader resolution (Qwen vs Z-Image guard).
- Qwen Lightning LoRA auto-resolution and `ReferenceLatent` preserve path.
- `sanitizeSettingsForStudioMode()` / plan-mode field clearing used by route tests.
- Existing Ultimate SD Upscale, ControlNet, IP-Adapter, and inpaint/outpaint graphs.

### Internal references

- `backend/dreamforge_feature_surfaces.py` — UI ↔ comfy mode ↔ builder map.
- `docs/plans/dreamforge-edit-inpaint-optimization.md` — related edit/inpaint plan and capability-registry proposal.
- `scripts/research_comfy_workflows.py` — read-only harness for upstream Comfy node patterns.

## Final Recommendation

The strongest path is not "support every workflow JSON" as templates. DreamForge should absorb the workflows as productized tasks and presets:

- Qwen compose should feel like the Comfy workflow: attach images, prompt with image numbers, generate, and highlight referenced thumbnails as users type.
- Photo Restore, Outfit Transfer, Cutout Compose, and Portrait Master should live inside a Creative Toolbox with dependency-aware setup.
- Ideogram4 should keep DreamForge's internal JSON/layout tooling and grow it into a richer visual builder.
- Custom Tools / Pro Sandbox should arrive after the core image-tool surfaces so advanced users can import validated image workflows without waiting for native support.

This approach keeps DreamForge coherent, preserves current better implementations, and turns the workflow folder into a roadmap rather than a pile of brittle template imports.
