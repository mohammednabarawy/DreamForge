# DreamForge AI OS Roadmap

> North star: DreamForge should become a local creative operating system for image generation, editing, upscaling, compositing, and agent automation. Image work stays local. Optional providers are for the decision brain only.

Last updated: 2026-05-27

## Progress

- [x] Preserve local-only image execution as the product rule.
- [x] Prefer Krita-style managed ComfyUI with `extra_model_paths.yaml` so existing local models are reused.
- [x] Add first structured AI Brain planning slice for CLI, REST, MCP, and desktop bridge.
- [x] Build a shared DreamForge Engine core used equally by GUI, WebUI, CLI, REST, MCP, and agents.
- [x] Research public ComfyUI workflow patterns and convert them into DreamForge template logic.
- [x] Add robust workflow planner, operation resolver, model router, and failure repair.
  - Planner, resolver, model router, exact dependency actions, and first structured failure reports are implemented.
- [ ] Make DreamForge usable as a local image infrastructure service for other agents.
  - AgentRuntime with capability gates and approved execution is implemented; broader agent tool surface still expanding.

## Non-Negotiables

- [x] Image generation, image editing, inpainting, upscaling, and compositing are local-only.
- [x] No online image generator providers are part of the image execution layer.
- [x] Optional providers are only brain runtimes: embedded llama.cpp, Ollama, LM Studio, llama.cpp server, or trusted local OpenAI-compatible endpoints.
- [x] All public surfaces call the same core engine instead of duplicating GUI, CLI, MCP, and REST logic.
- [x] Public agent interfaces expose tasks and tools, not fragile raw ComfyUI graph internals.
- [ ] Downloaded public workflows are treated as research inputs only, never executed blindly.

## Phase 0 - Foundation

Goal: stabilize the current local Comfy and agent-facing foundation.

- [x] Use managed ComfyUI server logic inspired by Krita AI Diffusion.
- [x] Generate/maintain ComfyUI model path config against DreamForge's existing `backend/models` symlink or folder.
- [x] Route edit/inpaint/upscale through managed Comfy where needed.
- [x] Add initial AI Brain JSON planning schema.
- [x] Add CLI `--brain-plan`.
- [x] Add REST `POST /brain/plan`.
- [x] Add MCP `plan_workflow`.
- [x] Add desktop bridge `brain_plan`.
- [x] Add tests for structured brain fallback and local-only image backend.

Test gate:

- [x] Backend compile passes for touched Python modules.
- [x] Brain planner tests pass.
- [x] Managed Comfy workflow/routing tests pass.
- [ ] Desktop/WebUI plan-preview flows verified end to end after UI wiring.
  - Desktop: plan card Apply / Run / Dismiss wired; Generate blocked until Run plan when approval is required; **Style preset** block shows `dynamic_preset` from intent + memory.
  - WebUI: Agent Plan accordion executes brain decisions through AgentRuntime + shared plan execution helper.

## Phase 1 - Public ComfyUI Workflow Research Agent

Goal: understand how real ComfyUI users solve common generation, editing, upscaling, and compositing tasks, then convert recurring patterns into DreamForge planner logic.

- [x] Add a safe research script that downloads workflow JSON/PNG/WebP artifacts into `.research/comfy_workflow_research`.
- [x] Analyze downloaded artifacts without executing workflows.
- [x] Classify workflows by task: txt2img, img2img, inpaint, outpaint, upscale, ControlNet, IPAdapter/reference, face/detail repair, Flux, SDXL, compositing.
- [x] Emit `workflow_index.json` and `ANALYSIS.md` with common node patterns.
- [ ] Expand seed sources beyond official examples and first public galleries.
- [x] Add a curated allowlist of reusable workflow patterns that DreamForge should encode as first-party builders.
- [ ] Add source/license notes for every downloaded workflow artifact before any pattern is copied into product logic.

Research source priorities:

- [ ] Official ComfyUI examples and docs.
- [ ] Public workflow galleries with downloadable workflows.
- [ ] GitHub repositories containing workflow JSON or workflow PNG metadata.
- [ ] Hugging Face repositories containing workflow JSON or PNG metadata.
- [ ] Articles/tutorials only as pattern evidence, not as copied implementation.

Test gate:

- [x] Research analyzer unit tests classify API-format and UI-format workflow graphs.
- [x] Research analyzer unit tests extract embedded Comfy metadata from PNG text chunks.
- [ ] Research report contains at least one artifact or page from each approved source class.
- [ ] No downloaded workflow is executed during research.

## Phase 2 - Shared DreamForge Engine Core

Goal: make GUI, WebUI, CLI, REST, MCP, and agents call the same application core.

- [x] Create a `DreamForgeEngine` facade for `generate`, `edit`, `inpaint`, `upscale`, `plan`, `list_models`, `list_outputs`, and `analyze_project`.
- [x] Move duplicated CLI/MCP/REST request normalization behind shared request/response helpers.
- [x] Preserve existing CLI flags and desktop bridge commands for compatibility.
- [x] Return structured JSON for every agent-facing call.
- [x] Keep long-running GPU execution single-flight to avoid parallel Comfy/DreamForge conflicts.

Test gate:

- [x] CLI, MCP, REST, and desktop bridge produce equivalent dry-run plans for the same request.
- [x] Existing generation/edit/upscale tests remain green.
- [x] Entry-point smoke verification covers CLI, MCP import, REST health, and desktop bridge `--once`.


## Phase 3 - Workflow Planner And Operation Resolver

Goal: translate user intent into ordered local workflow steps.

- [x] Define stable operations: `generate_image`, `edit_image`, `inpaint`, `remove_object`, `replace_background`, `outpaint`, `style_transfer`, `character_consistency`, `upscale`, `face_detail`, `text_integrate`, `composite_layers`.
- [x] Add operation resolver that maps natural language and canvas state to operations.
- [x] Add workflow planner that turns operations into first-party workflow templates.
- [x] Add planner warnings, required inputs, required models, optional nodes, and approval cues.
- [x] Use public workflow research to choose robust node patterns, not to execute arbitrary downloaded graphs.
- [x] Convert ControlNet structure blueprint into an executable native Comfy API builder for preprocessed control images.
- [x] Convert outpaint/canvas extend blueprint into an executable native Comfy API builder.
- [x] Convert hires/two-pass blueprint into an executable native Comfy API builder.
- [x] Add initial model/tool/input readiness checks against the local inventory for each template.
- [x] Convert planned IPAdapter/reference guidance blueprint into a guarded executable Comfy API builder with readiness gates for `ComfyUI_IPAdapter_plus`, IPAdapter models, and CLIP vision models.
- [x] Convert planned area-composition blueprint into an executable native Comfy API builder using regional `ConditioningSetArea`/`ConditioningCombine`.
- [x] Wire brain patches and generation routing for `workflow_mode`, ControlNet, IPAdapter, area composition, outpaint, and hires builders.
- [x] Expand readiness checks into exact per-template companion/download actions.

Test gate:

- [x] Intent fixtures produce expected operations and modes.
- [x] Missing masks, missing input images, model resources, and optional custom nodes produce structured warnings.
- [x] Plans remain valid JSON and use local Comfy image backend.

## Phase 4 - Model Router And Local Resource Awareness

Goal: choose local models and settings from task, hardware, and installed inventory.

- [x] Add model capability registry for SD15, SDXL, Flux, Flux Kontext, Flux Fill, Qwen Image/Edit, ControlNet, IPAdapter, FaceDetailer, and upscalers.
- [x] Add VRAM-aware routing using GPU info, model family, quantization, and current Comfy readiness.
- [x] Prefer local fast models for batches and local quality models for final renders.
- [x] Add fallback routes/actions when a model, node pack, or companion file is missing.
- [x] Keep user-selected models first-class in pure generation mode.

Test gate:

- [x] Router fixtures cover 5GB, 8GB, 16GB, and no-GPU profiles.
- [x] Missing companion files produce clear dependency actions.
- [x] Generation mode still honors explicit user model choices.

## Phase 5 - Desktop And WebUI Creative OS

Goal: make the UI feel like a guided creative tool instead of a raw workflow launcher.

- [x] Add Agent/Brain plan cards near the canvas.
- [x] Show operation sequence, required inputs, selected local models, dependency state, and approval/run controls.
- [x] Keep raw model/workflow controls available as expert overrides.
- [x] Add mode-specific UI for Generate, Edit, Inpaint, Upscale, Composite, and Agent.
- [x] Add WebUI parity for plan preview and managed Comfy routing.

Test gate:

- [x] Desktop build passes.
- [x] Plan cards do not start GPU work until approved.
- [x] Edit/Inpaint/Upscale flows show local model/dependency status.
- [x] WebUI can call the same backend plan endpoint.

## Phase 6 - CLI, REST, MCP, And Agent Runtime

Goal: make DreamForge usable by other agents and scripts.

- [x] Expand CLI around intent-level commands: `generate`, `edit`, `remove-object`, `inpaint`, `upscale`, `plan`, `serve`.
- [ ] Add JSON output mode for every command.
  - Generation, dry-run, brain-plan, and inventory listing support `--json`; remaining inventory subcommands still human-first.
- [x] Expand MCP tools around tasks, not raw workflow graphs.
- [x] Expose MCP resources for outputs, models, projects, sessions, and history.
- [x] Add `AgentRuntime` with safe tools: canvas, layer, workflow, model, project, generation, and vision helpers.
  - Initial runtime covers plan, execute, generate/edit/inpaint/upscale, list_models, list_outputs, and analyze_project.
- [ ] Add capability-based permissions for MCP and agent tools.
  - MCP and AgentRuntime both enforce capability sets and explicit execution approval.

Test gate:

- [x] MCP tool schemas import cleanly.
- [x] Agent can plan without GPU work.
- [x] Agent can execute approved local jobs through the same queue.
- [x] MCP never exposes arbitrary shell/filesystem execution.

## Phase 7 - Workflow Self-Healing

Goal: recover from common ComfyUI failures automatically.

- [x] Detect missing nodes, missing models, invalid inputs, VRAM errors, and unsupported workflow classes.
- [x] Add repair actions: replace node pattern, reduce resolution, switch model route, disable optional stage, retry with safer settings.
- [x] Add a structured failure report for UI, CLI, REST, and MCP.
- [x] Add retry limits and user approval for expensive retries.

Test gate:

- [x] Failure fixtures produce expected repair actions.
- [x] VRAM fallback lowers memory safely.
- [x] Missing nodes never trigger arbitrary custom-node installation without user approval.

## Phase 8 - Memory, Presets, And Adaptation

Goal: let DreamForge learn local user preferences without cloud dependency.

- [x] Add `UserStyleProfile` for favorite models, styles, aspect ratios, settings, and workflows.
  - Local JSON profile at `outputs/dreamforge/memory/user_style_profile.json`; records successful jobs and feeds planning hints.
- [x] Add dynamic preset generation from intent and style history.
  - `dreamforge_dynamic_presets.py` merges intent keywords, UserStyleProfile, and USE_CASE recipes during brain planning.
- [x] Track edit lineage, plan hash, source images, masks, and output artifacts.
  - Manifest `lineage` block via `dreamforge_edit_lineage.py` (plan hash, sources, mask, workflow plan, outputs).
- [x] Add opt-in project memory and clear reset/export controls.
  - Desktop Settings tab: enable/disable, clear, export JSON; bridge commands `get/save/clear/export_user_style_profile`.

Test gate:

- [x] Memory writes are local and inspectable.
  - UserStyleProfile writes to local JSON under `outputs/dreamforge/memory/`.
- [x] User can disable, clear, and export memory.
  - Desktop toggles + bridge handlers; `clear_profile()` / `export_profile()` on backend.
- [x] Presets remain deterministic enough for tests.
  - `tests/test_dynamic_presets.py` covers intent inference and non-overriding merges.

## Phase 9 - Release Readiness

Goal: make the architecture reliable enough for real users and external agents.

- [x] Update README, CLI docs, MCP instructions, and AI agent skill docs.
- [x] Add troubleshooting for managed Comfy, model paths, missing nodes, and low VRAM.
  - [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- [x] Add compatibility notes for Windows, Linux, and macOS.
  - README prerequisites + TROUBLESHOOTING platform section.
- [x] Add security notes for workflow downloads, MCP permissions, and local endpoints.
  - TROUBLESHOOTING security section; MCP instructions capability/approval notes.
- [x] Add release checklist for tests, desktop build, REST/MCP smoke, and sample workflows.
  - [docs/RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)

Test gate:

- [x] Full focused backend suite passes.
  - Focused gate (embedded Python): dynamic presets, edit lineage, workflow planner, krita resources, errors, brain planning, generation routing — **66 passed** (May 2026).
- [x] Desktop build passes.
- [ ] Research analyzer can refresh report without modifying tracked files.
- [x] Docs mention local-only image execution clearly.

## Current Evidence

- AgentRuntime + plan execution helper tests passed: `tests/test_agent_runtime.py`.
- UserStyleProfile records successful jobs and applies planning hints during brain planning.
- WebUI Agent Plan accordion executes approved brain decisions via AgentRuntime.
- Backend AI OS focused tests passed: `128 passed`.
- Focused MCP/model routing gate passed: `15 passed`.
- Planner/model/generation focused gate passed: `36 passed`.
- Model router fixtures passed for 5GB, 8GB, 16GB, no-GPU, missing companion fallback, and explicit user model preservation.
- Model router now prefers local fast routes for batch/speed requests, local quality routes for final renders, and preserves explicit pure-generation model choices.
- Desktop companion download modal now opens as an approval prompt before downloading missing components.
- Dry-run missing companion smoke/test returns `download_model_companions` and `switch_model` recommended actions.
- Workflow planner readiness now emits exact user-approved `download_model_companions` actions for known Krita-derived ControlNet, IPAdapter, CLIP Vision, Flux Kontext, and upscaler assets.
- Structured failure reports now attach conservative repair actions for OOM, Comfy crashes, missing custom nodes, missing model dependencies, invalid inputs, unsupported workflow classes, and generic generation failures; expensive retries and installs require approval.
- Desktop reliability banner now renders backend failure reports as repair plans, routes failure-report downloads through the companion approval modal, and avoids automatic restart/retry unless the backend explicitly marks a report as auto-retryable.
- Desktop build passed with plan-card UI wiring and companion download approval flow.
- MCP/REST/Engine import smoke passed.
- MCP execution tools require explicit `approved=true`, execute through `DreamForgeEngine`, expose task-level workflow blueprints instead of raw Comfy graphs, and report no arbitrary shell/filesystem capability.
- CLI `plan` subcommand smoke returned structured JSON and preserved `suggested_image_backend: local_comfy`.
- CLI dry-run smoke preserved explicit `qwen-image-edit` selection and restored workflow blueprint readiness.
- Phase 9 docs: [TROUBLESHOOTING.md](TROUBLESHOOTING.md), [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md); README/CLI/MCP/agent docs updated for local-only execution, style memory, lineage, and bridge commands.

## Links For Ongoing Research

- [ComfyUI workflow docs](https://docs.comfy.org/development/core-concepts/workflow)
- [Official ComfyUI examples](https://comfyanonymous.github.io/ComfyUI_examples/)
- [ComfyVault workflow gallery](https://www.comfyvault.app/)
- [ComfyUI Wiki workflow examples](https://comfyui-wiki.com/en/workflows)
- [ComfyGPT paper](https://arxiv.org/abs/2503.17671)
- [ComfySearch paper](https://arxiv.org/abs/2601.04060)
