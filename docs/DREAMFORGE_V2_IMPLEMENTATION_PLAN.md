# DREAMFORGE V2 IMPLEMENTATION PLAN

## Identity-Aware Creative Operating System

Last updated: 2026-05-27

This document is the V2 product and implementation plan for DreamForge based on the current repository state, `docs/EDITING_ORCHESTRATION_PLAN.md`, `docs/DREAMFORGE_AI_OS_ROADMAP.md`, and the Cursor review pasted into this thread.

V2 keeps the original north star:

- DreamForge is not a ComfyUI node front-end.
- DreamForge is a local creative operating system for generation, editing, upscaling, typography, identity, and agent-guided workflows.
- The default UX should expose intent, identity, references, masks, and creative goals rather than raw ControlNet/IPAdapter/workflow internals.
- Power users must still keep normal local image-generation controls.

## Review Decision

The previous V2 plan had the right product vision, but it was not grounded enough in the current codebase. The main corrections are:

1. DreamForge V2 has three product families from the start:
   - Generate
   - Edit family: Edit, Inpaint, Upscale
   - Agent

2. The current desktop already exposes five studio modes:
   - `generate`
   - `edit`
   - `inpaint`
   - `upscale`
   - `agent`

3. V2 must be Python-first and incremental.
   - Python owns orchestration, routing, planning, model readiness, Comfy workflow construction, memory, lineage, and agent runtime.
   - Tauri/Rust remains the desktop command shell and UI bridge unless a later migration is explicitly scheduled.
   - Do not create parallel Rust `GenerationService`, `EditService`, `IdentityRegistry`, or `ModelRegistry` implementations that duplicate the working Python engine.

4. The implementation plan must start from what is already shipped, not from a greenfield architecture.

5. `docs/EDITING_ORCHESTRATION_PLAN.md` remains the lower-level editing/router architecture reference. This V2 plan is the higher-level product and milestone plan.

## Current Project Status

The following systems already exist or are partially implemented and should be extended rather than replaced.

| Area | Current owner/files | Status |
| --- | --- | --- |
| Shared engine facade | `backend/dreamforge_engine.py` | Exists. GUI, CLI, REST, MCP, and agents can route through the same core. |
| Generation runtime | `backend/dreamforge_generation.py`, `backend/modules/image_pipeline.py` | Exists. Preserve this path. |
| Local Comfy runtime | `backend/dreamforge_comfy_*`, managed Comfy server/client/workflows | Exists. Keep Comfy hidden behind DreamForge workflows by default. |
| Model routing/readiness | `backend/dreamforge_model_registry.py`, `backend/dreamforge_cli_inventory.py`, `backend/dreamforge_workflow_planner.py` | Exists. Continue capability-driven local routing. |
| Flux Kontext local edit | `backend/dreamforge_generation.py`, `backend/modules/image_pipeline.py`, `backend/dreamforge_comfy_workflows.py` | Exists. Local target is Kontext Dev via Comfy. |
| Qwen Image/Edit | `backend/dreamforge_comfy_workflows.py`, `backend/dreamforge_comfy_models.py`, tests | Exists but should stay dependency-gated/beta for editing until smoke quality is reliable. |
| Arabic poster pipeline | `backend/arabic_poster_pipeline.py`, `backend/dreamforge_arabic_composite.py` | Exists and is a differentiator. Generalize instead of replacing. |
| Style recipes | `backend/dreamforge_style_recipes.py`, `backend/dreamforge_agent_tools.py` | Exists. Treat as canonical creative preset system. |
| Agent/brain planning | `backend/dreamforge_brain.py`, `backend/dreamforge_app_config.py`, `backend/dreamforge_agent_runtime.py` | Exists. Productize rather than restart. |
| Local agent runtime settings | `apps/desktop/src/components/InspectorPanel.tsx`, `backend/dreamforge_app_config.py` | Exists. Needs refinement toward local open-source model choices only. |
| Desktop modes | `apps/desktop/src/hooks/useDreamForge.ts`, `apps/desktop/src/App.tsx` | Exists. Current `StudioMode` already includes generate/edit/inpaint/upscale/agent. |
| Dependency actions | `CompanionDownloadModal`, `ReliabilityBanner`, `download_model_companions` | Exists. Reuse for edit/agent missing assets. |
| Memory/lineage | `dreamforge_user_style_profile.py`, `dreamforge_dynamic_presets.py`, `dreamforge_edit_lineage.py` | Exists. Extend toward identity/reference packs. |

## Product Model

### 1. Generate Mode

Generate mode remains the default power-user surface.

User workflow:

```text
Prompt
Negative prompt
Model / LoRA / style / recipe
Sampler / steps / CFG / seed / size
Generate
Streaming result to canvas
```

Generate mode must preserve:

- Text-to-image
- Image-to-image
- Batch generation
- Seed control
- Manual model selection
- LoRA selection
- Style recipes
- Aspect ratio and resolution controls
- Sampler, scheduler, CFG, steps
- Queue and streaming preview
- Save to gallery
- Send result to Edit, Inpaint, Upscale, or Agent

Routing rule:

- Generate honors the user-selected model by default.
- The router may recommend a model or apply dynamic presets only when the user opts into an automatic path.
- Generate mode must not be collapsed into Agent mode.

### 2. Edit Family: Edit, Inpaint, Upscale

The edit family is curated and dependency-aware.

User workflow:

```text
Open image
Optional mask or target region (inpaint)
Instruction
Generate
  → dry-run plans route locally
  → routed settings appear in Settings tab
  → generation starts immediately
Adjust Settings if result is wrong
Generate again to replan and rerun
```

Edit family modes should feel like a professional image editor, not a model picker.

**Desktop orchestration rule (shipped):**

- Do **not** block the user on a canvas plan card with separate Apply / Run plan buttons.
- **Generate** is the single primary action: plan → apply routed settings to the Settings inspector → run when ready.
- **Dry run** (non-agent modes) applies the routed settings to Settings only; it does not start GPU work.
- If planning fails readiness (missing mask, companions, etc.), apply whatever settings are valid, show a clear status message, and let the user fix inputs in Settings before pressing Generate again.
- Dry-run responses must include `proposed_patch` from the backend so routed model/edit/inpaint fields actually reach the UI (not just the pre-plan input snapshot).

Primary surfaces:

- Edit: global/context-aware edits, character consistency, style preservation
- Inpaint: region edits, object removal, localized replacement, outpaint
  - **Smart mask** toolbar: subject, background, clothes, face/body heuristics, tap-to-select
  - **Mask UX:** user sees the full photo with a pale red quick-mask overlay on the selection; grayscale mask is internal/export-only for the inpaint pipeline
- Upscale: detail, print, face, or creative enhancement

Simple controls:

- Preserve face
- Preserve character
- Preserve style
- Preserve text
- Stronger edit / softer edit
- Mask feather/expand when relevant
- Expert override only behind advanced mode

Routing rule:

- Edit/Inpaint/Upscale use routed local stacks by default.
- The UI shows what DreamForge will use and why.
- Missing assets show dependency actions before GPU work starts.
- Expert override is allowed, but the UI must mark the run as user-overridden.

### 3. Agent Mode

Agent mode is a creative operator, not a replacement for Generate or Edit.

User workflow:

```text
Describe goal
Agent inspects context
Agent applies routed settings to Settings tab
Generate plans locally and runs (or Dry run / Ask agent applies settings only)
Agent explains result in transcript; user adjusts Settings and regenerates if needed
```

Agent mode should:

- Detect the task: generate, edit, inpaint, upscale, typography, composite, or multi-step workflow
- Detect Arabic/text needs
- Detect identity/reference needs
- Choose Generate/Edit/Inpaint/Upscale as tools
- Build a reviewable plan internally (dry-run / brain patch)
- Surface required models/tools/downloads via status and Settings, not a blocking canvas card
- Require approval for downloads and expensive GPU work in v1
- Keep image execution local
- Keep agent reasoning local with open-source models only

## Architecture Policy

### Python-first orchestration

Current authoritative runtime and planning code is Python. V2 work should extend these Python modules first:

| Need | Preferred owner |
| --- | --- |
| Shared public execution facade | `backend/dreamforge_engine.py` |
| Generation and edit execution | `backend/dreamforge_generation.py` |
| Comfy workflow builders | `backend/dreamforge_comfy_workflows.py` |
| Model family detection/readiness | `backend/dreamforge_cli_inventory.py`, `backend/dreamforge_model_registry.py` |
| Task planning | `backend/dreamforge_brain.py`, `backend/dreamforge_workflow_planner.py` |
| App config/agent settings | `backend/dreamforge_app_config.py` |
| Agent runtime | `backend/dreamforge_agent_runtime.py` |
| Arabic/text integration | `backend/arabic_poster_pipeline.py`, `backend/dreamforge_arabic_composite.py` |
| Memory/lineage | `backend/dreamforge_user_style_profile.py`, `backend/dreamforge_edit_lineage.py` |

### Tauri/Rust role

Rust/Tauri should provide:

- Desktop commands
- Local file dialogs
- Bridge calls
- App shell integration
- Security boundaries
- UI state persistence when appropriate

Rust/Tauri should not duplicate:

- Model routing
- Comfy workflow generation
- Agent planning
- Identity/reference storage logic
- Python engine queue behavior

Any future Rust migration must be a separate architecture decision with parity tests.

### Comfy role

Comfy remains a runtime, not the product model.

Use Comfy for:

- Local workflow execution
- Flux Kontext
- Qwen Image/Edit
- ControlNet/IPAdapter/FaceDetailer/upscaler graphs
- Managed server reuse of local models

Do not expose Comfy node graphs in the default UX.

## Model Reality

DreamForge V2 is local open-source-model only. Image models, editing models, upscalers, and agent reasoning models must run locally.

| Model family | V2 status |
| --- | --- |
| Flux Kontext Dev/local | Primary local context-aware edit target. Keep improving routed use. |
| Qwen Image/Edit | Local Comfy path exists. Keep for typography/text edits when dependencies and smoke gates pass. |
| Flux Fill/inpaint | Curated local inpaint target when available; otherwise use existing fallback route. |
| GLM Image | Only in scope if a local open-source checkpoint/runtime is integrated and tested in this repo. |
| Upscalers | Use existing local upscaler readiness and workflow planner actions. |
| Face/identity models | Future identity track: InsightFace/IPAdapter FaceID or equivalent, dependency-gated. |

## V2 Milestones

These milestones are ordered for visible user value and low risk. They replace the previous fifteen greenfield phases.

### M0 - Reconcile Plans And Baseline

Goal: make the roadmap executable from the current repo state.

Work:

- Treat this document as the V2 product plan.
- Treat `docs/EDITING_ORCHESTRATION_PLAN.md` as the lower-level edit/router architecture reference.
- Treat `docs/DREAMFORGE_AI_OS_ROADMAP.md` as the current implementation status ledger.
- Audit existing tests and note the current focused gate command in the release checklist.
- Keep `Generate` default and power-user friendly.

Done when:

- The docs no longer imply a Rust rewrite.
- The docs consistently describe Generate, Edit family, and Agent.
- The current shipped systems are listed as foundations, not future greenfield tasks.

### M1 - Mode Contracts And Plan Honesty

Goal: every mode says exactly what it will do before expensive work starts.

Work:

- Formalize the mode contract around current `StudioMode`.
- Ensure Generate preserves explicit model/settings unless Auto/Agent applies changes.
- Ensure Edit/Inpaint/Upscale route through task-aware local plans.
- Make dry-run/plan output drive the **Settings tab** before GPU work:
  - selected operation
  - selected local model/workflow
  - dependencies
  - fallback
  - expected mode
  - whether user settings were overridden
- Return `proposed_patch` from `build_plan()` / dry-run so desktop applies routed model and edit fields correctly.
- Align desktop, CLI, REST, MCP, and agent plan outputs.

Primary files:

- `backend/dreamforge_engine.py`
- `backend/dreamforge_generation.py`
- `backend/dreamforge_cli_direct.py` (`proposed_patch` in dry-run payload)
- `backend/dreamforge_brain.py`
- `backend/dreamforge_workflow_planner.py`
- `backend/dreamforge_app_config.py`
- `apps/desktop/src/hooks/useDreamForge.ts` (`planApplyAndRun`)
- `apps/desktop/src/lib/workflowPlanActions.ts`

Acceptance tests:

- Generate with explicit model keeps that model.
- Edit with input image defaults to Kontext when text editing is not requested.
- Text/Arabic edit routes to Arabic hybrid or Qwen path only when suitable.
- Inpaint requires image + mask or returns a clear missing-input plan.
- Generate in edit family applies dry-run settings to Settings and runs in one action (no canvas plan card gate).
- Agent plan cannot run GPU work without approval when approval is required (downloads still approval-gated).

### M2 - Edit Mode V1 Product Polish

Goal: make Edit/Inpaint/Upscale feel like a finished guided product, using existing backend capability.

Work:

- Edit: instruction box, preserve toggles, source image, revision/result actions; routed values visible in Settings.
- Inpaint: smart selection (`backend/dreamforge_inpaint_selection.py`), mask modal with photo + pale red overlay (not B&W mask preview), feather/expand controls.
- Upscale: image target, quality goal, routed upscaler; missing assets via companion download flow.
- **Generate flow:** `planApplyAndRun` — dry-run → patch Settings from `proposed_patch` → start generation when ready.
- **Dry run flow:** same planning path, apply Settings only, no GPU run.
- Hide raw model choice by default in edit family modes.
- Keep expert override available behind advanced mode.
- Use `CompanionDownloadModal` and `ReliabilityBanner` for missing edit assets.
- Make "send to edit/inpaint/upscale" from canvas/gallery reliable.
- Remove blocking canvas `WorkflowPlanPanel` from the default edit/generate path (Settings tab is the review surface).

Primary files:

- `apps/desktop/src/hooks/useDreamForge.ts`
- `apps/desktop/src/lib/workflowPlanActions.ts`
- `apps/desktop/src/App.tsx`
- `apps/desktop/src/components/InspectorPanel.tsx`
- `apps/desktop/src/components/InpaintMaskModal.tsx`
- `backend/dreamforge_inpaint_selection.py`
- `backend/dreamforge_desktop_bridge.py`
- `apps/desktop/src/components/CompanionDownloadModal.tsx`
- `apps/desktop/src/components/ReliabilityBanner.tsx`

Acceptance tests:

- Desktop build passes.
- Generate in edit/inpaint/upscale applies routed settings to Settings and runs without a plan-card stop.
- Dry run applies routed settings without starting GPU work.
- Inpaint smart mask shows photo + pale red selection overlay; exported mask remains grayscale internal-only.
- Missing companion actions open the download approval modal.
- Edit strength and manual sampling overrides actually reach runtime when enabled.
- Kontext edit does not accidentally send stale `upscale_image`.

### M3 - Reference Packs Before Full Identity Registry

Goal: deliver practical identity/reference value before building a full face-embedding subsystem.

Work:

- Add lightweight named reference packs:
  - person
  - character
  - product
  - brand
  - style
- Store pack metadata locally with image paths, tags, notes, and preferred use cases.
- Let Generate/Edit/Agent attach packs as reference inputs.
- Feed pack metadata into planner/router prompts and dry-run summaries.
- Avoid automatic face detection/embedding in this milestone.

Primary files:

- New or extended local storage under `outputs/dreamforge/memory/` or `backend/settings/`
- `backend/dreamforge_user_style_profile.py`
- `backend/dreamforge_brain.py`
- `backend/dreamforge_app_config.py`
- `apps/desktop/src/hooks/useDreamForge.ts`
- New desktop reference-pack panel/component

Acceptance tests:

- User can create a pack from selected images.
- Pack can be attached to Generate/Edit/Agent plan.
- Plan output names the attached pack and intended role.
- Removing a pack does not delete source images unless explicitly requested.

### M4 - Identity Registry V1

Goal: promote reference packs into a true identity system after the simple workflow proves useful.

Work:

- Add SQLite-backed identity registry only after M3 is stable.
- Support identity types:
  - Person
  - Character
  - Product
  - Brand
  - Style
  - Location
- Add optional embeddings:
  - face embedding
  - CLIP/style embedding
  - palette/composition metadata
- Add dependency-gated face preservation with InsightFace/IPAdapter FaceID or the selected local equivalent.
- Cache extracted metadata locally.
- Allow identity attach in Generate/Edit/Agent.

Primary files:

- New `backend/dreamforge_identity_registry.py`
- New tests under `backend/tests/`
- Desktop identity/reference panel
- `backend/dreamforge_workflow_planner.py`
- `backend/dreamforge_cli_inventory.py`

Acceptance tests:

- SQLite registry can create/update/delete/search identities.
- Identity references round-trip through plans without running GPU work.
- Missing identity dependencies produce dependency actions, not crashes.
- Face/identity paths are optional and do not block ordinary edit/generate.

### M5 - Agent Studio Productization

Goal: turn the existing brain/runtime into a first-class conversational creative mode.

Work:

- Keep agent runtime configuration local and clear:
  - local embedded model
  - Ollama/LM Studio/llama.cpp server
- Make runtime badges explicit: embedded local model or local server.
- Use open-source reasoning models only.
- Show a chat transcript near the canvas (no blocking plan card for routine runs).
- Agent can inspect current session, propose setting changes, attach references, request downloads, and run approved jobs.
- Agent must use DreamForge tools, not mutate UI invisibly.
- **Generate** in agent mode: apply brain patch → local dry-run → patch Settings → run when ready (same `planApplyAndRun` path after agent routing).

Primary files:

- `backend/dreamforge_agent_runtime.py`
- `backend/dreamforge_brain.py`
- `backend/dreamforge_app_config.py`
- `backend/dreamforge_desktop_bridge.py`
- `apps/desktop/src/hooks/useDreamForge.ts`
- `apps/desktop/src/components/AgentTranscriptPanel.tsx`
- `apps/desktop/src/components/InspectorPanel.tsx`

Acceptance tests:

- Agent can plan without GPU.
- Agent cannot execute without approval when approval is required.
- Agent plan can configure Generate/Edit/Inpaint/Upscale.
- Agent planning works with local open-source runtimes only.
- Local image execution remains local.

### M6 - Arabic Typography Excellence

Goal: make Arabic and mixed-language design a visible DreamForge advantage.

Work:

- Generalize the existing Arabic poster pipeline into a reusable text integration task.
- Keep deterministic text rendering as the default for exact glyphs.
- Use diffusion for integration, lighting, scene blending, and background coherence.
- Add validation warnings when OCR/text preservation is likely weak.
- Route text replacement carefully:
  - existing exact poster/composite path for generated layouts
  - Qwen Edit only when dependencies are ready and the task fits
  - Kontext/inpaint fallback when text is not required to be exact

Primary files:

- `backend/arabic_poster_pipeline.py`
- `backend/dreamforge_arabic_composite.py`
- `backend/dreamforge_brain.py`
- `backend/dreamforge_generation.py`
- `backend/tests/test_arabic_composite.py`
- `backend/tests/test_brain_planning.py`

Acceptance tests:

- Arabic/text intent maps to `text_integrate` or Arabic composite path.
- Exact Arabic poster generation does not rely on diffusion-only text.
- Qwen text edit remains dependency-gated.
- Plan preview explains whether text is rendered deterministically or edited by model.

### M7 - Local Model Expansion

Goal: expand DreamForge through local open-source model families only.

Work:

- Add new model families only when they can run locally through DreamForge/Comfy or another local runtime.
- Require capability tags, dependency readiness, and smoke tests before adding a model to routed edit/agent paths.
- Keep local execution as the only execution mode.
- Do not add hosted/API image providers.
- Do not add hosted/API agent brain providers.

Acceptance tests:

- Local generation/edit works without any network model configuration.
- New model families have local readiness checks and dependency actions.
- Plans label local model/runtime choices clearly.

### M8 - Future Power Layer

Do not implement as part of V2 product polish unless explicitly scheduled:

- Default node graph editor
- Full arbitrary Comfy workflow builder UI
- Automatic graph synthesis
- Agentic ControlNet graph creation
- Region system beyond current area composition foundations
- Full Rust backend rewrite
- Cloud sync/accounts
- Hosted/API image models
- Hosted/API agent brain providers
- Fine-tuning Qwen for Arabic glyph generation

These may become separate epics after V2 mode contracts, edit UX, reference packs, identity, agent, and typography are stable.

## Deliverables By Layer

### UX

- Generate remains default and complete.
- Edit/Inpaint/Upscale become guided, routed, dependency-aware experiences; Settings tab is where users review and tweak routed values.
- Agent becomes a real mode with transcript, local runtime state, and approval controls for downloads/GPU when required.
- Reference packs/identity are accessible from all modes.

### Orchestration

- Existing Python engine remains the single owner of image execution.
- Plans/dry-runs are consistent across desktop, CLI, REST, MCP, and agent.
- Routing is deterministic unless an explicit local agent runtime step is used for reasoning.
- Dependency actions are structured and approval-gated.

### Runtime

- Comfy remains managed and hidden by default.
- Local Flux Kontext, Qwen, Arabic composite, inpaint, ControlNet/IPAdapter/upscale paths are used through first-party workflow builders.
- GPU execution remains single-flight.

### Memory

- User style profile and dynamic presets remain opt-in and local.
- Edit lineage remains visible in manifests.
- Reference packs evolve into Identity Registry V1.

## Testing And Verification

Use focused tests tied to changed areas. The release checklist should remain the authoritative command list.

Core gates:

- `backend/tests/test_generation_routing.py`
- `backend/tests/test_model_router.py`
- `backend/tests/test_workflow_planner.py`
- `backend/tests/test_brain_planning.py`
- `backend/tests/test_plan_preview_integration.py`
- `backend/tests/test_agent_runtime.py`
- `backend/tests/test_app_config.py`
- `backend/tests/test_dynamic_presets.py`
- `backend/tests/test_edit_lineage.py`
- `backend/tests/test_arabic_composite.py`
- Desktop build after UI changes

Mode-specific acceptance:

| Mode | Must verify |
| --- | --- |
| Generate | Explicit model/settings survive planning and runtime. |
| Edit | Input image, edit type, edit strength, reference state, and preview streaming are correct. |
| Inpaint | Mask path, edit type, feather/expand settings, and fallback route are correct. |
| Upscale | Uses upscale image, not stale input/edit image state. |
| Agent | Ask agent applies settings; Generate plans and runs locally; downloads require approval; local runtime state is visible. |

## Immediate Next Steps

1. Keep this plan as the V2 product plan and stop using the older Rust service snippets as implementation targets.
2. Continue M3 reference packs UI polish (dedicated panel vs inspector-only) and expand pack roles in planner output.
3. Begin M4 Identity Registry V1 once reference-pack workflow is stable in daily use.
4. Productize Agent mode transcript/history and local-runtime diagnostics (plan card removed from default path).
5. Generalize Arabic poster/text integration as the typography milestone (M6).
6. Add/refresh tests for `proposed_patch` dry-run application and inpaint selection overlay export paths.

## Shipped UX Notes (2026-05-27)

These behaviors are implemented and should be preserved in future milestones:

| Behavior | Rule |
| --- | --- |
| Edit-family Generate | One click: dry-run → apply `proposed_patch` to Settings → run if ready. |
| Dry run button | Plan and apply Settings only; no GPU run. |
| Plan review surface | Settings inspector, not a canvas overlay card. |
| Inpaint mask modal | Visible layer = photo + pale red tint on selection; offscreen grayscale mask for export/pipeline only. |
| Smart mask | Backend selection via `dreamforge_inpaint_selection.py`; UI in `InpaintMaskModal.tsx`. |
| Canvas overlay | Do not reintroduce blocking `WorkflowPlanPanel` for standard generate/edit flows. |

## Non-Negotiables

- Do not break current generation.
- Do not remove manual model/LoRA/sampler/seed control from Generate mode.
- Do not force all users through Agent mode.
- Do not expose Comfy graphs as the default UX.
- Do not duplicate orchestration in Rust while Python owns the working engine.
- Do not add cloud/API image providers.
- Do not add cloud/API agent brain providers.
- Do not make identity/face embeddings block Edit Mode V1.
- Do not run downloads or expensive GPU work without user approval where approval is required.
