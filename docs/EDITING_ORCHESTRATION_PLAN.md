# DreamForge Editing Orchestration — Implementation Plan

> **North star:** DreamForge should have three professional modes: **Generation Studio** for open model/library exploration, **Editing Studio** for curated multi-model orchestration, and **Agent Studio** for conversational creative operation — user intent in, planned pipeline out — with DreamForge’s differentiator in **Arabic-aware cinematic editing** and **creative state** across turns.

This plan converts the product/architecture brainstorming into executable phases grounded in the current repo (`dreamforge_generation.py`, `image_pipeline.py`, desktop worker/bridge, MCP, `arabic_poster_pipeline.py`).

**Related tracking:** GitHub epic [#14](https://github.com/mohammednabarawy/DreamForge/issues/14), project [DreamForge Core Roadmap](https://github.com/users/mohammednabarawy/projects/5).

---

## 1. Strategic principles (non-negotiable)

| Principle | Implication for DreamForge |
|-----------|----------------------------|
| No “one perfect model” | Route by **task**, not checkpoint |
| Compete on orchestration, not raw gen | Invest in router, masks, conditioning, repair, memory |
| Three-mode product model | **Generate** lets users choose any local/discovered model; **Edit/Inpaint/Upscale** auto-routes through curated model/tool stacks; **Agent** chats with the user, plans, configures, and executes |
| Intent-driven UX | “Replace background” not “pick Flux + CFG + sampler” |
| Separate understanding from generation | Reference/condition **extractors** feed the router; models only integrate |
| Stateful editing | Persist edit lineage, anchors, latent hints — don’t full-regen every turn |
| Arabic niche | Hybrid: **deterministic text render** + diffusion **integration** (existing poster pipeline extended) |

**Do not optimize editing for:** beating closed models by asking users to pick the perfect checkpoint.  
**Do optimize editing for:** controllability, consistency, local ownership, precision, automation.

**Important UX split:** the model library and Discover flow remain first-class in **Generation mode**. They move out of the critical path only for **Edit / Inpaint / Upscale**, where DreamForge should choose the required models, LoRAs, masks, ControlNet tools, upscalers, and repair passes automatically. **Agent mode** sits above both: it can ask clarifying questions, translate rough instructions into a plan, configure the right mode, and execute after user approval.

---

## 2. Target architecture — four layers

Today everything collapses into `run_generation()` → `async_worker` → `image_pipeline.process()`. The target splits responsibilities:

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 4 — UX (Desktop, CLI, MCP, future Web)                    │
│   Intent: "Edit character", "Fix Arabic headline", "Inpaint sky" │
└────────────────────────────┬────────────────────────────────────┘
                             │ stable JSON: EditIntent / GenerationJob
┌────────────────────────────▼────────────────────────────────────┐
│ Layer 3 — Workflow / Automation                                   │
│   Batch JSONL, MCP tools, Comfy sidecar graphs (#1–#3), agents    │
└────────────────────────────┬────────────────────────────────────┘
                             │ EditPlan (ordered steps)
┌────────────────────────────▼────────────────────────────────────┐
│ Layer 2 — Creative Intelligence (NEW — core product)              │
│   EditRouter, ConditionGraph, MaskEngine, RepairGraph, EditMemory │
└────────────────────────────┬────────────────────────────────────┘
                             │ RuntimeJob (model id, tensors, masks)
┌────────────────────────────▼────────────────────────────────────┐
│ Layer 1 — Model Runtime (stabilize existing)                      │
│   image_pipeline, VRAM profiles, preflight, worker, mmap loaders   │
└─────────────────────────────────────────────────────────────────┘
```

### Layer boundaries

| Layer | Owns | Must NOT own |
|-------|------|--------------|
| **L1 Runtime** | Inference, quantization, scheduling, caching, boot | Task semantics, UI copy |
| **L2 Intelligence** | Task→pipeline planning, conditioning, masks, repair order | Comfy node graphs (L3), React components (L4) |
| **L3 Workflow** | Graphs, batch, MCP orchestration, Comfy JSON | Direct tensor code |
| **L4 UX** | Modes, progressive disclosure, canvas/mask tools | Model family logic |

**Single front door for L2:** `backend/dreamforge_edit_router.py` (new) called from `run_generation()` before `async_worker`.

---

## 3. Current state (repo audit summary)

### What already works

- **Flux Kontext** path: auto in `image_pipeline` when Flux UNet + input image; explicit `edit_type=kontext` in `dreamforge_generation.py`
- **Inpaint**: mask via `InpaintMaskModal` → `inpaint_mask_path` → `_attach_inpaint_mask()`
- **Qwen Image Edit**: branch in pipeline when `has_qwen_encode`; **experimental** (EVALUATION_REPORT: CLIP/pairing issues)
- **Arabic poster**: `arabic_poster_pipeline.py` — 3-phase compositing (deterministic text + blend)
- **Agent recipes**: `USE_CASE_RECIPES`, `MODEL_FAMILY_HINTS` in `dreamforge_agent_tools.py`
- **Desktop**: worker + bridge; preview pipeline; LoRA stack improvements (recent)
- **MCP**: 14 tools including `edit_image`, `dry_run`, `recommend_model`

### Critical gaps

| Gap | Where it hurts |
|-----|----------------|
| **No EditRouter module** | Routing split across generation, UI (`referenceImage.ts`), MCP, pipeline |
| **MCP `edit_image` skips `--edit-type`** | Wrong pipeline for inpaint/qwen vs kontext (#5) |
| **Mode confusion in UX** | Discover / Models are good for generation, but should not drive Edit/Inpaint/Upscale decisions |
| **No ConditionGraph** | IPAdapter, depth, face, style refs are ad hoc or missing |
| **No MaskEngine** | Manual mask only; no SAM2, feather, semantic expand |
| **No RepairGraph** | Single-pass output; no face/hand/typography repair chain |
| **No EditMemory** | Each generate is stateless; Kontext multi-turn not persisted |
| **Three execution paths** | Worker, MCP subprocess CLI, bridge — can duplicate GPU (#10) |
| **Qwen not production** | Blocked on CLIP/mmproj smoke (#6, #7) |

---

## 4. Core subsystems (specifications)

### 4.1 Edit Router (`dreamforge_edit_router.py`)

**Input:** `EditIntent` (task, images, masks, refs, constraints, vram tier, locale)

**Output:** `EditPlan` — ordered steps with model ids from the curated registry for edit/inpaint/upscale tasks. Pure generation can still honor user-selected models.

Example tasks (v1 enum):

| Task ID | User-facing label | Default pipeline (high level) |
|---------|-------------------|-------------------------------|
| `create_image` | Create | User-selected model from library/discover, with optional recipe defaults |
| `edit_global` | Edit image | Flux Kontext |
| `edit_local` | Inpaint region | FLUX Fill / inpaint + MaskEngine |
| `expand_canvas` | Expand / outpaint | Kontext or Fill (TBD benchmark) |
| `replace_background` | Replace background | segment → mask → Fill/Kontext |
| `character_consistency` | Keep same face/character | identity anchor + Kontext |
| `style_transfer` | Style transfer | Kontext + style ref weight |
| `typography_edit` | Edit text / poster | Arabic hybrid OR Qwen (beta) |
| `typography_integrate` | Place Arabic text | render layer + Kontext/Qwen integrate |
| `product_photo` | Product shot | t2i recipe + optional refine |
| `upscale` | Upscale | existing upscale path |
| `repair_artifacts` | Fix faces/hands/text | RepairGraph sub-steps |

**Router responsibilities:**

1. If `task=create_image`, preserve the selected model/LoRA/style controls from Generation Studio.
2. If `task=edit_*`, `inpaint`, `typography_*`, or `upscale`, map the task to curated model(s), LoRAs, tools, and `edit_type`.
3. Attach **preflight** (deps, VRAM, smoke gates for Qwen, SAM2, FLUX Fill, upscalers).
4. Emit missing dependency actions: `required`, `optional`, `downloadable`, `manual_install`.
5. Build **ConditionGraph** weights.
6. Emit **human-readable plan** for `dry_run` / UI “Review plan”.
7. Keep advanced overrides available, but require an explicit “override routed plan” action for editing modes.

**Integration point:**

```python
# dreamforge_generation.run_generation() — after job normalize, before async_worker
plan = edit_router.plan(job, hardware=detect_hardware())
job = plan.to_generation_job()  # existing job shape + extensions
emit_event("edit-plan", plan.summary())
```

### 4.2 Mode-Aware Model Policy + Curated Registry (`backend/settings/curated_models.json` + loader)

Do **not** remove the model library globally. Split model policy by mode:

| Mode | Model behavior | UX behavior |
|------|----------------|-------------|
| **Generation Studio** | User can choose any model from local library or Discover; LoRAs/styles remain manual and exploratory | Discover / Models / Styles are visible and primary |
| **Editing Studio** | Router auto-selects curated models, LoRAs, tools, masks, ControlNet, repair, and upscalers by task | Show the plan and dependency status; hide raw model choice behind expert override |
| **Agent Studio** | LLM planner configures Generate/Edit/Inpaint/Upscale from natural-language instruction | Prompt bar becomes chat; agent asks clarifying questions, builds a plan, requests downloads/approval, then runs tools |

The curated registry is a **capability-tagged dependency map** for editing workflows:

| Capability | Curated model(s) | Notes |
|------------|------------------|-------|
| `generate.fast` | flux1-schnell-fp8 | Previews |
| `generate.quality` | flux1-dev-fp8 | General |
| `edit.kontext` | flux1-dev-kontext_fp8_scaled | Primary editor |
| `edit.fill` | *(add FLUX Fill when in models/)* | Local inpaint |
| `edit.qwen` | Qwen GGUF + paired CLIP | **beta gate only** |
| `edit.typography` | hybrid + optional Qwen | Arabic path preferred |
| `segment.sam2` | SAM2 weights | MaskEngine |
| `upscale` | existing | |
| `identity.face` | IPAdapter FaceID + InsightFace | Phase 4 |

Registry entries: `{ id, files[], vram_min_gb, stability, tasks[], companions[] }`.

Registry entries should also include install metadata:

```json
{
  "id": "edit.kontext",
  "label": "FLUX Kontext Editor",
  "tasks": ["edit_global", "character_consistency"],
  "required_files": [],
  "optional_files": [],
  "download": {
    "kind": "companion_downloader|manual|hf",
    "url": null,
    "notes": "Show download prompt if missing"
  },
  "fallback": "edit.global.img2img"
}
```

**Advanced editing override:** still calls `list_models` / inventory, but the UI must mark the run as user-overridden and skip quality guarantees.

### 4.3 Condition Graph (`dreamforge_conditioning.py`)

Unified structure (stored in job + session):

```yaml
conditioning:
  identity:   { source: path, weight: 0.92 }
  composition: { source: original, weight: 0.75 }
  style:      { source: path, weight: 0.55 }
  typography: { preserve: true, source: rendered_layer.png }
  structure:  { type: depth|canny|pose, weight: 0.6 }
  lighting:   { source: path, weight: 0.4 }
```

**Phase 1:** schema + passthrough to existing Kontext/img2img.  
**Phase 3:** extractors (depth, segmentation maps) + multi-ref weights.  
**Phase 4:** IPAdapter FaceID path.

### 4.4 Mask Intelligence (`dreamforge_mask_engine.py`)

Pipeline steps (composable):

1. `segment_object` — SAM2 (point/box/text prompt)
2. `edge_refine` — morphological + edge-aware
3. `semantic_expand` — context-aware dilation
4. `feather` — Gaussian / latent blur
5. `confidence_score` — reject bad masks before GPU

**UI:** mask debug overlay, feather slider (progressive disclosure).

**Deps:** optional `segment-anything-2` model in `models/`; graceful fallback to manual mask.

### 4.5 Reference Engine (`dreamforge_reference_engine.py`)

Extractors (lazy, cached per session):

- Identity embedding (InsightFace) — Phase 4
- Style embedding (CLIP / EVA) — Phase 3
- Color palette
- Composition / depth map
- Typography regions (OCR bbox for Arabic/ Latin)

Output feeds ConditionGraph; does **not** call diffusion.

### 4.6 Repair Graph (`dreamforge_repair_graph.py`)

Post-primary-edit optional chain:

```
primary_edit → detect_defects → face_repair → hand_repair → typography_cleanup → color_harmonize → upscale
```

Each step is a **small routed sub-job** (may no-op). Start with **manual toggles** (“Fix face”, “Sharpen text region”); later auto-detect.

### 4.7 Creative State / Edit Memory (`dreamforge_edit_memory.py`)

Per **session** store (JSON alongside output index):

- Edit history (prompt, task, plan hash)
- Identity anchors (face embedding path)
- Last latent metadata if runtime exposes it (future)
- Mask lineage (parent mask id)
- ConditionGraph snapshot per turn

**Enables:** “Edit 3: change jacket color but keep face from Edit 1.”

Kontext is the first consumer; design storage **model-agnostic**.

### 4.8 Arabic Typography Hybrid (`dreamforge_typography_pipeline.py`)

Extend `arabic_poster_pipeline.py` into general **typography integrate** task:

| Stage | Tech | Owner |
|-------|------|--------|
| 1. Shape text | HarfBuzz / browser render / existing poster fonts | Deterministic |
| 2. Layout map | PNG alpha + bbox JSON | Deterministic |
| 3. Integrate | Kontext or Qwen with **mask on glyph interior frozen** | L2 router |
| 4. Validate | Arabic OCR similarity score | Optional retry loop |

**Training stance:** do **not** fine-tune Qwen for glyph generation first; fine-tune/prompt for **preservation + integration**.

### 4.9 Agent Studio (`dreamforge_agent_orchestrator.py`)

Agent mode should turn the prompt bar into a conversational creative operator. The user can type rough instructions like:

> “Make this a cinematic Arabic poster, keep the face, add rain, make the title in elegant Thuluth style.”

The agent should:

1. Understand the request and ask short clarifying questions only when required.
2. Choose the right mode: Generate, Edit, Inpaint, Upscale, Typography, or multi-step workflow.
3. Build an `EditIntent` / `GenerationJob` plus `ConditionGraph`.
4. Call `plan_edit` / dry-run to get the real pipeline.
5. Detect missing providers, models, LoRAs, or tools.
6. Offer downloads for local embedded models or required editing assets.
7. Show a reviewable plan before expensive GPU work.
8. Execute through the same backend queue/router as the rest of DreamForge.
9. Continue the conversation using EditMemory and session history.

#### Agent provider policy

Agent mode should support multiple reasoning providers:

| Provider type | Examples | UX |
|---------------|----------|----|
| User API provider | OpenAI, Anthropic, Gemini, OpenRouter, local OpenAI-compatible endpoints | User adds key/base URL in Settings |
| Local desktop model | Gemma small model, Qwen small instruct, Phi, Llama small GGUF | Download on request; private/offline option |
| Existing local server | LM Studio, Ollama, llama.cpp server | Auto-detect or configure endpoint |

The first version should use a provider abstraction instead of hardcoding one API:

```python
class AgentProvider:
    def chat(self, messages, tools, context) -> AgentResponse:
        ...
```

Suggested files:

| File | Purpose |
|------|---------|
| `backend/dreamforge_agent_orchestrator.py` | Conversation planner, tool policy, plan execution |
| `backend/dreamforge_agent_providers.py` | OpenAI-compatible, local GGUF, Ollama/LM Studio adapters |
| `backend/settings/agent_providers.json` | Saved provider preferences, local model metadata |
| `backend/settings/agent_models.json` | Downloadable embedded planner models |
| `apps/desktop/src/components/AgentPanel.tsx` | Chat transcript, plan cards, approval buttons |
| `apps/desktop/src/lib/agent.ts` | Tauri bridge client for agent calls |

#### Agent tools

Agent mode should not manipulate UI state directly. It should use explicit backend tools:

| Tool | Purpose |
|------|---------|
| `inspect_current_session` | Read selected image, prompt, refs, mask status, active mode |
| `set_generation_settings` | Configure model/prompt/styles only in Generate mode |
| `create_edit_intent` | Build routed edit/inpaint/upscale intent |
| `plan_edit` | Get EditPlan and dependencies |
| `download_dependency` | Download required agent/edit assets with user approval |
| `run_generation` | Execute approved plan through the queue |
| `explain_plan` | Summarize what DreamForge will do in plain language |

#### Safety and control

- The agent can configure settings automatically, but expensive GPU runs and downloads should require explicit user approval in v1.
- The agent should show changed settings before running: mode, model/tool stack, references, mask behavior, output count, estimated VRAM.
- For local/offline users, the app should offer a small embedded planner model download when no provider is configured.
- Provider credentials stay local; no prompt/image is sent to cloud providers unless the user chooses that provider.

---

## 5. Desktop UX transformation — three professional modes

### 5.1 Top-level mode switch

The desktop app should stop using one Inspector layout for every job. Add a clear top-level mode switch:

| Mode | Primary user mental model | Main controls |
|------|---------------------------|---------------|
| **Generate** | “I want to explore models, styles, LoRAs, prompts.” | Prompt, model library, Discover, LoRA stack, styles, generation settings |
| **Edit** | “I want to change this image reliably.” | Input image, edit task, references, mask/region tools, plan preview, missing dependency prompts |
| **Inpaint** | “I want to change this region.” | Image, mask canvas, mask assistant, routed fill model, feather/expand controls |
| **Upscale** | “I want to improve this output.” | Image, scale/quality target, auto-selected upscaler/refiner, dependency status |
| **Agent** | “I want to describe what I need and let DreamForge configure it with me.” | Chat prompt bar, provider selector, plan cards, approval/run controls |

Generation mode keeps the current **Discover / Models / Styles / Settings** pattern. Editing modes use **Creative Capabilities** instead of asking the user to pick the model first:

| Nav item | Maps to task(s) |
|----------|-----------------|
| Create | `create_image` |
| Edit | `edit_global`, `character_consistency` |
| Inpaint | `edit_local` + MaskEngine |
| Expand | `expand_canvas` |
| Typography | `typography_edit`, `typography_integrate` |
| Style | `style_transfer` |
| Poster / Arabic | `typography_*` + existing poster recipes |
| Automation | batch / MCP (#11–#13) |
| Advanced | Expert plan override, raw params, model override |

**Models tab behavior:**

- In **Generate**, Models and Discover are visible and primary.
- In **Edit / Inpaint / Upscale**, Models and Discover are not primary controls. The router picks the stack. The user sees “DreamForge will use: FLUX Kontext + SAM2 + refiner” with a dependency/download status.
- In **Agent**, Models/Discover are available only when the agent intentionally chooses Generate mode or asks the user to pick a creative model. Otherwise the agent configures the routed workflow.
- Expert users can open **Advanced override**, but the UI should clearly say the routed quality path has been overridden.

### 5.2 Prompt bar behavior by mode

The prompt bar should be mode-aware:

| Mode | Prompt bar behavior |
|------|---------------------|
| **Generate** | Classic image prompt. User controls model, LoRAs, styles. |
| **Edit/Inpaint/Upscale** | Task instruction for the selected image/region; backend turns it into `EditIntent`. |
| **Agent** | Chat input. User can describe goals, constraints, references, Arabic text, desired style, and the agent works interactively. |

Agent mode should support a transcript directly near the canvas, with compact plan cards:

```text
User: Make this a luxury Arabic perfume poster.
Agent: I need the Arabic headline and whether to preserve the current bottle.
User: نعم، preserve bottle. Text: عطر المساء
Agent plan:
  - Render Arabic headline exactly
  - Segment bottle and preserve it
  - Replace background with cinematic dark gold lighting
  - Integrate typography and run upscale
  - Missing: FLUX Kontext editor, download required
```

### 5.3 Intent flow for editing modes

1. User picks capability
2. Attach image / paint mask / add refs
3. Router creates an **EditPlan**
4. UI checks required models/tools/LoRAs
5. If missing, show a dependency card: what is missing, why it is needed, download/install action, fallback if available
6. User reviews plan; models/tools are summarized, not exposed as the main decision
7. Generate → session updates **EditMemory**
8. Optional repair toggles on result

### 5.4 Agent flow

1. User switches to Agent mode or starts an instruction with agent intent.
2. If no provider is configured, show provider choices: API provider, local server, or download small embedded model.
3. Agent reads current session context.
4. Agent asks concise clarifying questions if required.
5. Agent creates a proposed workflow using Generate/Edit/Inpaint/Upscale tools.
6. UI shows a plan card with settings changes, dependencies, estimated cost/VRAM, and approval buttons.
7. User approves downloads and/or run.
8. Agent executes through the queue and reports results.
9. Agent can continue iterating using EditMemory.

### 5.5 Dependency/download UX

When an edit mode needs assets that are missing, the app should notify before GPU work starts:

| Missing item | UI action |
|--------------|-----------|
| Downloadable companion model | Show “Download required editing model” button using existing `CompanionDownloadModal` pattern |
| Manual model install | Show exact expected folder and filename |
| Optional quality tool | Allow run with warning and show expected quality loss |
| No viable fallback | Block run with a clear missing requirement |

This should reuse and extend the current dependency surface:

- `modelDependencies`
- `CompanionDownloadModal`
- `ReliabilityBanner`
- `generationReadiness`
- future `EditPlan.dependencies[]`
- future `AgentPlan.dependencies[]`

### 5.6 Progressive disclosure

| Beginner | Advanced (same engine) |
|----------|-------------------------|
| “Replace sky” | mask feather, condition weights, regional denoise |
| “Fix Arabic title” | OCR threshold, integration strength, font override |
| “Make this poster premium” | agent plan graph, provider, tool calls, model overrides |

### 5.7 Desktop component direction

| Component | Change |
|-----------|--------|
| `App.tsx` | Own `studioMode`: `generate`, `edit`, `inpaint`, `upscale`, `agent`; pass it to canvas and inspector |
| `CanvasPanel.tsx` | Show mode-specific primary actions, agent transcript, and plan/dependency cards |
| `InspectorPanel.tsx` | In Generate mode keep Discover/Models/Styles/Settings; in edit modes show Task/References/Mask/Plan/Advanced |
| `AgentPanel.tsx` | Chat transcript, provider state, plan cards, approve/download/run actions |
| `MarketplaceTab.tsx` | Remains available in Generate mode; not the default surface for Edit/Inpaint/Upscale |
| `InpaintMaskModal.tsx` | Becomes part of the Inpaint mode workflow with feather/expand/debug controls |
| `useDreamForge.ts` | Stores mode, asks router/agent for plan, merges dependency state with model dependencies |

---

## 6. API contracts

### 6.1 `EditIntent` (extends GenerationJob — aligns with #9)

```json
{
  "schema_version": 1,
  "task": "typography_integrate",
  "prompt": "integrate headline naturally with cinematic lighting",
  "input_image": "outputs/.../base.png",
  "inpaint_mask_path": null,
  "conditioning": { "typography": { "source": ".../text_layer.png", "preserve": true } },
  "constraints": { "preserve_identity": true, "locale": "ar" },
  "repair": { "face": false, "typography": true },
  "advanced": { "model_override": null, "steps": null }
}
```

### 6.2 `EditPlan` (router output)

```json
{
  "task": "typography_integrate",
  "steps": [
    { "id": "mask", "engine": "mask_engine", "op": "typography_region" },
    { "id": "integrate", "engine": "runtime", "model": "edit.kontext", "edit_type": "kontext" },
    { "id": "ocr_validate", "engine": "typography", "op": "validate_ar" }
  ],
  "curated_models": ["flux1-dev-kontext_fp8_scaled.safetensors"],
  "dependencies": [
    {
      "id": "edit.kontext",
      "label": "FLUX Kontext editor",
      "required": true,
      "status": "missing",
      "action": "download"
    }
  ],
  "warnings": [],
  "estimated_vram_gb": 12
}
```

### 6.3 Stable entrypoints

| Surface | Calls |
|---------|--------|
| Desktop Generate | User-selected model/LoRA/style → `run_generation(job)`; optional dry-run |
| Desktop Edit/Inpaint/Upscale | `plan_edit(intent)` → dependency check/download prompt → `run_generation(job)` |
| Desktop Agent | `agent_chat(message, context)` → `AgentPlan` → approval/download/run |
| MCP | `edit_image`, `plan_edit`, `enqueue_generation` (#11) |
| CLI Generate | Existing model flags stay available |
| CLI Edit/Inpaint/Upscale | `--task` + `--plan-json` or compiled from flags |
| CLI Agent | Optional later: `dreamforge-agent --instruction "..." --approve-plan` |
| Bridge | `dry_run` returns EditPlan JSON + dependencies for UI |

---

## 7. Phased implementation

### Phase 0 — Foundation (align with GitHub Q1: #5, #9, #10)

**Goal:** One job shape, one GPU owner, honest edit routing.

| Work item | Files | Done when |
|-----------|-------|-----------|
| `GenerationJob` / `EditIntent` schema v1 | `backend/dreamforge_job_schema.py`, tests | CLI batch + worker validate same JSON |
| GPU queue / mutex | `dreamforge_desktop_bridge.py`, worker | MCP/CLI enqueue; no parallel GPU |
| Fix MCP `--edit-type` | `dreamforge_mcp_server.py`, `dreamforge_cli_direct.py` | inpaint/kontext/qwen_edit smoke tests |
| `dry_run` returns router preview | bridge + MCP | Desktop can show plan before GPU |

**Duration estimate:** 2–3 weeks  
**Issues:** #5, #9, #10

---

### Phase 1 — Edit Router + Mode-Aware Curated Registry

**Goal:** Generation remains user-selectable; Edit/Inpaint/Upscale use task-based routed stacks with dependency reporting.

| Work item | Files | Done when |
|-----------|-------|-----------|
| `dreamforge_edit_router.py` | new + tests `test_edit_router.py` | All v1 tasks return EditPlan |
| `curated_models.json` + loader | `backend/settings/`, inventory integration | Edit/Inpaint/Upscale use curated stacks; Generate can use any library model |
| Dependency resolver | router + bridge | Missing edit assets return required/optional/download/manual actions |
| Wire router into `run_generation` | `dreamforge_generation.py` | `edit_type`/`cn_*` set by router for edit modes only |
| Map `USE_CASE_RECIPES` → tasks | `dreamforge_agent_tools.py` | Single source of truth |
| MCP `plan_edit` tool | `dreamforge_mcp_server.py` | Agents get plan without GPU |
| Deprecate implicit edit routing in UI | `referenceImage.ts` | Edit UI sends `task`, not conflicting cn_type; Generate UI keeps model selection |

**Duration estimate:** 3–4 weeks  
**New issues suggested:** Edit Router epic (sub-tasks)

---

### Phase 2 — Mask Intelligence + Structural Guidance

**Goal:** Professional inpaint/local edit quality.

| Work item | Files | Done when |
|-----------|-------|-----------|
| `dreamforge_mask_engine.py` | new | feather, expand, refine ops |
| SAM2 integration (optional model) | mask engine + preflight | Point/box segment → mask |
| Desktop mask UX upgrade | `InpaintMaskModal.tsx`, canvas overlay | SAM assist + debug view |
| Structure extractors (depth, canny) | `dreamforge_reference_engine.py` | Feeds ConditionGraph |
| FLUX Fill in curated stack | models + pipeline path | `edit_local` uses Fill when available |
| ControlNet modular hooks | `controlnet.py`, router | Structure weight in plan |

**Duration estimate:** 4–6 weeks  
**Depends:** Phase 1

---

### Phase 3 — Multi-Reference + Conditioning Graph

**Goal:** Independent weighted refs (face, style, pose, typography).

| Work item | Done when |
|-----------|-----------|
| ConditionGraph schema in job + session | Desktop + worker round-trip |
| Multiple ref slots in UI | Per-ref weight sliders (Advanced) |
| Style / composition extractors | Router uses weights in plan |
| LAMIC or IPAdapter-style path (research spike) | Document + prototype one ref type |

**Duration estimate:** 4–6 weeks  
**Depends:** Phase 2

---

### Phase 4 — Repair Graph + Identity

**Goal:** “Magically polished” multi-pass without user tuning.

| Work item | Done when |
|-----------|-----------|
| `dreamforge_repair_graph.py` | Chained sub-jobs after primary edit |
| InsightFace + IPAdapter FaceID | `character_consistency` task |
| Face / hand repair steps | Optional toggles + auto-detect stub |
| Typography cleanup pass | Arabic OCR re-check |

**Duration estimate:** 6–8 weeks  
**Depends:** Phase 3

---

### Phase 5 — Edit Memory (Creative State)

**Goal:** Iterative editing without drift.

| Work item | Done when |
|-----------|-----------|
| `dreamforge_edit_memory.py` | Session dir stores history + anchors |
| Router reads memory on `edit_*` tasks | “Preserve identity from turn 1” works |
| Desktop session UI shows edit timeline | Branch/continue from prior turn |
| Kontext multi-turn strategy | Documented + tested 4-turn scenario |

**Duration estimate:** 3–4 weeks  
**Depends:** Phase 1; best with Phase 4

---

### Phase 6 — Arabic Typography Excellence

**Goal:** Best-in-class Arabic poster/text integration locally.

| Work item | Done when |
|-----------|-----------|
| Generalize `arabic_poster_pipeline` → `typography_integrate` | Router task uses hybrid path |
| Text engine stage (deterministic render) | RTL, fonts, diacritics correct |
| Integration-only diffusion | Mask freezes glyph interiors |
| OCR validation loop | Retry or warn on glyph damage |
| Qwen beta path (#6, #7) | Optional for “edit existing text in scene” only |

**Duration estimate:** 6–10 weeks (parallel with 4–5)  
**Issues:** #6, #7, #8; differentiator milestone

---

### Phase 7 — UX Overhaul (Two-Mode Desktop)

**Goal:** Product feels like a professional studio: open model exploration for generation, routed precision workflows for editing.

| Work item | Done when |
|-----------|-----------|
| Top-level mode switch | Generate / Edit / Inpaint / Upscale are visually distinct |
| Generate inspector | Discover, Models, Styles, LoRAs remain first-class |
| Edit inspector | Task, references, masks, plan, dependencies; models hidden unless override |
| Review plan step | Shows EditPlan from dry_run |
| Missing dependency prompt | Required edit assets can be downloaded or clearly installed |
| Edit wizard (#8) | Kontext / Inpaint / Typography flows |
| Automation panel (#12) | Batch + queue visible |
| Architecture docs + diagrams | This doc + `docs/architecture/` diagrams |
| Examples gallery | Before/after Arabic + edit chains |

**Duration estimate:** 4–6 weeks ongoing  
**Issues:** #8, #12, #13

---

### Phase 8 — Agent Studio

**Goal:** Prompt bar can become an AI creative operator that chats, configures, plans, downloads missing assets with approval, and runs workflows.

| Work item | Done when |
|-----------|-----------|
| Agent provider abstraction | OpenAI-compatible provider works from settings |
| Local embedded model registry | App can offer a small planner model download when no API provider is configured |
| `dreamforge_agent_orchestrator.py` | Converts chat instruction into plan/settings/tool calls |
| Agent tools | Can inspect session, set settings, create edit intent, plan edit, request downloads, run approved job |
| Desktop Agent mode | Prompt bar becomes chat; transcript and plan cards render near canvas |
| Approval gates | Downloads and GPU runs require user confirmation in v1 |
| Privacy UX | UI clearly shows whether provider is cloud, local server, or embedded local |

**Duration estimate:** 4–6 weeks for v1  
**Depends:** Phase 0 queue, Phase 1 router

---

### Phase 9 — Comfy + Agent Graphs (optional power layer)

**Goal:** Power users run custom graphs without breaking curated path.

| Work item | Issues |
|-----------|--------|
| Comfy sidecar + workflow registry + execute | #1–#4 |
| MCP `run_workflow`, `batch_run` | #11 |
| Agent Studio graph execution | new |

**Depends:** Phase 0 queue; parallel to Phase 3+

---

## 8. Testing strategy

| Layer | Tests |
|-------|--------|
| Router | `test_edit_router.py` — every task maps to valid curated model + edit_type |
| Schema | `test_job_schema.py` — round-trip CLI ↔ worker |
| Mode policy | Generate jobs preserve user-selected model; edit/inpaint/upscale jobs ignore casual model selection and use routed stack |
| Dependencies | Missing curated edit assets produce required/optional/download/manual statuses |
| Agent providers | Provider config validates cloud/local/embedded modes without leaking keys |
| Agent planning | Instruction fixtures produce expected mode/settings/EditIntent/tool calls |
| Agent approvals | Downloads and GPU runs are blocked until explicit approval |
| Mask | Unit tests on feather/expand; golden mask PNGs |
| Typography | OCR similarity on fixture posters; no GPU |
| Integration | Smoke: kontext edit, inpaint+mask, typography_integrate |
| MCP | `edit_image` passes edit_type; `plan_edit` matches worker plan |
| Regression | Existing `test_generation_routing.py` updated to router |

**Benchmark page (future):** `docs/benchmarks/EDITING.md` — Kontext vs Fill vs hybrid Arabic on fixed fixtures.

---

## 9. GitHub issue mapping

| Phase | Existing issues | Action |
|-------|-------------------|--------|
| 0 | #5, #9, #10 | Keep; add acceptance criteria linking EditIntent |
| 1 | — | **Create:** Edit Router, Curated registry |
| 2 | — | **Create:** MaskEngine, SAM2, FLUX Fill |
| 3 | — | **Create:** ConditionGraph, multi-ref UI |
| 4 | — | **Create:** RepairGraph, identity |
| 5 | — | **Create:** EditMemory / creative state |
| 6 | #6, #7, #8 | Extend bodies with hybrid typography architecture |
| 7 | #8, #12, #13 | UX + docs |
| 8 | — | **Create:** Agent Studio, provider abstraction, embedded planner model download |
| 9 | #1–#4, #11 | Comfy + MCP v2 |

Update epic #14 checklist to reference this document.

---

## 10. Risks and non-goals

### Risks

| Risk | Mitigation |
|------|------------|
| Scope explosion (“giant AI toolbox”) | Free exploration is contained in Generate mode; editing tasks are finite enum v1 |
| Users feel model choice was removed | Keep Discover/Models first-class in Generate; add explicit expert override in edit modes |
| Agent does too much without consent | Require approval for downloads, GPU jobs, and provider changes in v1 |
| Cloud provider privacy surprise | Provider badge and confirmation before sending prompt/image context off-machine |
| Local planner model is weak | Use it for planning/configuration, not final image reasoning; allow cloud/local server upgrade |
| Three execution paths diverge | Router + schema mandatory for all paths (Phase 0) |
| Qwen instability blocks typography | Hybrid path default; Qwen beta gated (#6) |
| SAM2 / IPAdapter deps heavy | Optional components; preflight + download docs |
| Breaking power users | Advanced Mode retains full model list |

### Non-goals (v1)

- Beating NanoBanana / GPT Image on general one-shot quality
- Full fine-tune of Qwen for Arabic glyph generation
- Replacing ComfyUI for arbitrary node graphs in default UX
- Cloud sync / accounts

---

## 11. Immediate next steps (recommended order)

1. **Merge Phase 0** (#5, #9, #10) — schema, queue, MCP edit_type  
2. **Implement mode policy** — Generate honors user-selected models; Edit/Inpaint/Upscale call router  
3. **Implement Edit Router skeleton** — 4 routed tasks first: `edit_global`, `edit_local`, `typography_integrate`, `upscale`  
4. **Add `plan_edit` MCP + desktop dry-run panel** — return plan plus dependency/download actions  
5. **Curated registry JSON** — dependency map for editing stacks, not a replacement for generation library  
6. **Desktop mode switch** — Generate keeps Discover/Models; Edit/Inpaint/Upscale show task plan + missing downloads  
7. **Extend Arabic hybrid** — wire `typography_integrate` to poster pipeline  
8. **Agent provider abstraction** — OpenAI-compatible first, local embedded download path second  
9. **Agent mode UI** — prompt bar becomes chat with plan cards and approval buttons  

---

## 12. Architecture visibility (docs to add)

| Document | Purpose |
|----------|---------|
| `docs/architecture/FOUR_LAYERS.md` | Layer diagram + module map |
| `docs/architecture/EDIT_ROUTER.md` | Task table + plan examples |
| `docs/architecture/ARABIC_TYPOGRAPHY.md` | Hybrid pipeline deep dive |
| `docs/benchmarks/EDITING.md` | Quality metrics |

These support open-source credibility and onboarding — called out in brainstorming as missing today.

---

*Last updated: 2026-05-25 — derived from product brainstorming + repo audit.*
