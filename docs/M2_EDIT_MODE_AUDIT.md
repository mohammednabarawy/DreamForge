# M2 Edit Mode Audit Checklist

Tracks **Edit / Inpaint / Upscale** polish against `DREAMFORGE_V2_IMPLEMENTATION_PLAN.md` M2.  
Primary files: `InspectorPanel.tsx`, `CanvasPanel.tsx`, `generationReadiness.ts`, `useDreamForge.ts`.

## Slice 1 — Done

| Item | File(s) | Status |
| --- | --- | --- |
| Edit-family inspector: default to Settings, hide Discover/Models/LoRAs/Styles unless Advanced | `InspectorPanel.tsx` | Done |
| Edit-family panel: routed model label, edit strength, preserve-face, plan hint | `InspectorPanel.tsx` | Done |
| Plan settings snapshot + freshness check | `workflowPlanActions.ts`, `studioBridge.ts` | Done |
| Edit family: Generate plans first, then runs via approved plan | `useDreamForge.ts`, `workflowPlanActions.ts` | Done |
| Readiness blocks run when edit plan missing/stale/not ready | `generationReadiness.ts`, `useDreamForge.ts` | Done |
| Plan card visible before edit GPU work | `CanvasPanel.tsx` | Done |
| PromptBar copy for edit family (Plan vs Generate) | `PromptBar.tsx` | Done |

## Slice 2 — Done

| Item | File(s) | Status |
| --- | --- | --- |
| Preserve character / style / text toggles → planner hints | `InspectorPanel.tsx`, `dreamforge_mode_contract.py`, `WorkflowPlanPanel.tsx` | Done |
| Inpaint feather / expand controls in inspector | `InspectorPanel.tsx`, `dreamforge_generation.py`, CLI/bridge | Done |
| Hide sampler/steps/CFG in edit family unless Advanced | `InspectorPanel.tsx` | Done |
| Canvas handoff: send to edit/inpaint/upscale clears stale upscale state | `useDreamForge.ts`, `referenceImage.ts` | Done |
| Companion download from edit-family plan actions | `WorkflowPlanPanel.tsx`, `downloadMissingCompanions` | Done |

## Slice 3 — Done (automated)

| Item | File(s) | Status |
| --- | --- | --- |
| Acceptance: plan card before routed edit work | `CanvasPanel.tsx`, `test_generation_routing.py` | Done (UI + dry-run contract tests) |
| Acceptance: Kontext edit does not use stale `upscale_image` at runtime | `referenceImage.ts`, `useDreamForge.ts` | Done (`sanitizeEditFamilySettings` before dry-run/run) |
| Acceptance: edit strength overrides reach runtime | `dreamforge_cli_direct.py`, `test_generation_routing.py` | Done (`settings.edit_strength` in dry-run plan) |
| Inpaint mask grow/feather in plan path | `test_generation_routing.py` | Done (`test_inpaint_dry_run_carries_mask_controls`) |

Manual spot-check (optional): switch Edit → Inpaint via canvas handoff and confirm plan refreshes before Run plan.

## M1 cross-check (mostly done)

| Item | File(s) | Status |
| --- | --- | --- |
| Mode contract in dry-run / plan panel | `dreamforge_mode_contract.py`, `WorkflowPlanPanel.tsx` | Done |
| Generate preserves explicit model | backend tests | Done |
| Inpaint requires mask in readiness | `generationReadiness.ts` | Done |
