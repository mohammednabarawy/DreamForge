# Phase 0 — Current System Audit

> Deliverable for Phase 0 of `DreamForge_Discover_Library_Improved_Implementation_Plan.md`.
> No code was changed in this phase. This document maps today's architecture so that
> "Discover & Library" replaces/extracts existing behavior without regressing it.

## 1. Stack at a glance

- **Desktop app:** Tauri 2 + React 19 + TypeScript at `apps/desktop` (renderer in `src/`, Rust shell in `src-tauri/`).
- **Backend:** Python 3.10 embedded runtime (`python_embeded`) under `backend/`; a long-lived Python sidecar
  (`backend/dreamforge_desktop_bridge.py`) is spawned by Rust and speaks NDJSON over stdin/stdout.
- **Inference engine:** ComfyUI v0.26.0 (vendored under `engines/comfyui`), managed as a subprocess by
  `backend/dreamforge_comfy_server.py`. Job queue is a RuinedFooocus-style async worker surfaced by
  `backend/dreamforge_engine.py`. No InvokeAI runtime dependency exists.
- **Model store:** `models/` is a **junction** → `D:\krita_server\models`; Comfy subfolders
  (`checkpoints`, `diffusion_models`, `loras`, `vae`, `controlnet`, `upscale_models`, `text_encoders`, …).

## 2. Current data flow (renderer → backend)

```
React component
  → src/lib/tauri-api.ts or src/lib/studioBridge.ts (typed wrappers)
  → invoke("bridge_invoke", { cmd, params })          [generic passthrough]
  → src-tauri/src/lib.rs  PythonSidecar
  → backend/dreamforge_desktop_bridge.py  handle_request → HANDLERS[cmd]
  → domain module(s) → (optionally) ComfyUI via dreamforge_comfy_server.py
```

- Rust `invoke_handler` (src-tauri/src/lib.rs) exposes ~60 `#[tauri::command]`s plus the generic
  `bridge_invoke`. `bridge_invoke` forwards any `cmd_*` handler by name.
- `HANDLERS` registry lives at `dreamforge_desktop_bridge.py` (~70 entries, incl. `STUDIO_HANDLERS`).
- Events flow back through `worker_events.json` (polled at 250 ms) and Tauri events
  (`download-progress`, `download-complete`, generation status, etc.).

## 3. Existing "Discover"/marketplace surface

| Concern | Where today | Notes |
|---|---|---|
| Marketplace UI | `src/components/MarketplaceTab.tsx` | Browser-side `fetch("https://civitai.com/api/v1/models")` — **no backend proxy**, filters `Checkpoint|LORA`, requires user CivitAI key. |
| Discover host | `src/components/InspectorPanel.tsx` | Tab `"discover"` renders MarketplaceTab; other tabs: models/loras/styles/settings/automation. |
| Gallery rendering | `ThumbnailGallery.tsx`, `StyleThumbnailGrid.tsx`, `LoraStackPanel.tsx` | `asset://` protocol + LRU thumbnail cache (`thumbnail-cache.ts`). |
| Download pipeline | Rust `download_model` + `backend/dreamforge_model_downloader.py` | `.part` staging, atomic rename, progress/completion events, resumable Range requests, SHA256 verify, `download_manifest.json`. |
| Post-download placement | `relocate_downloaded_model` (bridge `cmd_relocate_downloaded_model`) | Moves into category folder. |
| Library-like surfaces | `HistoryPanel` (outputs), models/loras galleries, "Starter Pack" in AppSettingsModal | Starter Pack (`getStarterPackItems`) is the closest existing "curated discovery" flow. |

## 4. Existing backend building blocks (reuse, don't rebuild)

- **Downloader** — `backend/dreamforge_model_downloader.py`: HF / CivitAI / direct HTTPS, category map
  (`CATEGORY_FOLDERS`), `verify_sha256`, `download_model(...)`, content-disposition filename parsing, persistent manifest.
- **Inventory & gallery** — `backend/dreamforge_cli_inventory.py`, `dreamforge_comfy_models.py`,
  `dreamforge_model_library_cache.py`: scan/classify model folders; cached JSON at `backend/cache/model_library/`
  (`manifest.json`, `inventory.json`, `model_gallery.json`, `lora_gallery.json`) with fingerprint invalidation.
- **Capabilities** — `backend/dreamforge_model_registry.py`: `FAMILY_CAPABILITIES`, `supports_capability`,
  `model_capabilities_for_model`, `required_capabilities_for_request`, `explain_model_capability_match`.
- **Compute/VRAM** — `backend/dreamforge_vram_profiles.py` (profile tiers), `dreamforge_gpu_detect.py`
  (device/vendor/vram_mb/recommended profile), `argparser.py` lowvram/normalvram/etc.
- **Workflow parsing** — `backend/dreamforge_comfy_workflow_import.py` (UI vs API format detection,
  `workflow_class_types`), `dreamforge_workflow_planner.py` (TEMPLATE_REGISTRY),
  `dreamforge_custom_tools.py` (workflow-bundle sha256, model slots).
- **Recipes / styles** — `dreamforge_style_recipes.py` (`STYLE_RECIPES`, ~150 entries),
  `dreamforge_krita_recipes.py` (`EDIT_RECIPES`), `backend/settings/creative_templates.json` + `dreamforge_creative_templates.py`.
- **Secrets** — `dreamforge_app_config.py` persists `civitai_api_key` (redacted via `_tail`/`_configured`); never returned raw to renderer.
- **Custom-node installs** — `dreamforge_companion_download.py`, `custom_node_packs`/`install_workflow_models`
  bridge commands; dependency approval modal (`CompanionDownloadModal`).

## 5. Gap analysis vs. the target plan

| Plan requirement | Status today | Work needed |
|---|---|---|
| CivitAI browse behind backend proxy | ✗ Renderer hits CivitAI directly | `CivitaiProvider` in Python; UI switches to bridge search. |
| Hugging Face browse | ✗ None | `HuggingFaceProvider` (Hub API) + card metadata. |
| Lexica prompt discovery | ✗ None | `LexicaProvider` (Phase 5). |
| Multi-source `DiscoveryService` | ✗ None | New orchestrator with failure isolation + cache. |
| Unified `DreamForgeAsset` / AssetRegistry | Partial (gallery JSON is filename-based) | New SHA256-identity registry + SQLite persistence. |
| Capability-driven compatibility gate | Partial (family→capability) | Extend into `CapabilityRegistry` used by Discover cards. |
| `DreamForgeRecipe` v2 (provenance, completeness) | Partial (`STYLE_RECIPES`, creative templates) | New schema with "never invent missing" rule + completeness score. |
| Workflow compatibility compiler (Native/Adaptable/Comfy-only/Invalid) | Partial (workflow import + custom tools) | Phases 7–9; reuse `dreamforge_comfy_workflow_import.py`. |
| Custom-node security (registry + fail-closed) | Partial (approval modal) | Comfy Registry lookup + strict block rules (Phase 8). |
| Official Comfy templates browse | ✗ None | `ComfyTemplateProvider` (Phase 7). |
| Persistent download queue (survives restart) | Partial (manifest records, no queue state) | `DownloadManager` queue + resume (Phase 3). |
| Offline-first guarantees | Library/generation already local | Ensure Discover degrades gracefully; never block generation. |
| License/provenance retention | ✗ Not tracked | Add to asset + recipe records. |
| Feature flags | ✗ None | Add `discover.*` / `workflows.*` / `downloads.*` flags. |

## 6. Migration guardrails (from plan §29)

1. Do **not** delete `MarketplaceTab` until the new Discover UI reaches parity.
2. Keep browser-side CivitAI fetch working until `CivitaiProvider` lands behind the bridge.
3. Preserve `downloadModel`/`relocateDownloadedModel` semantics; new download queue routes through the same
   downloader to keep SHA256 + `.part` + manifest behavior.
4. All new provider logic lives in Python; React stays provider-agnostic and token-free.

## 7. Command surface summary (relevant existing)

Rust commands (src-tauri/src/lib.rs): `get_paths`, `get_inventory`, `get_model_gallery`, `get_lora_gallery`,
`refresh_model_library_cache`, `resolve_model_profile`, `check_model_dependencies`, `download_model`,
`download_model_companions`, `organize_models`, `relocate_downloaded_model`, `parse_comfy_workflow`,
`import_custom_tool_workflow`, `get_starter_pack_items`, `bridge_invoke`, plus lifecycle/status commands.

Bridge handlers (dreamforge_desktop_bridge.py): `cmd_ping`, `cmd_get_paths`, `cmd_get_model_gallery`,
`cmd_get_lora_gallery`, `cmd_refresh_model_library_cache`, `cmd_resolve_model_profile`, `cmd_get_inventory`,
`cmd_list_outputs`, `cmd_search_outputs`, `cmd_list_styles`, `cmd_check_model_dependencies`,
`cmd_download_model_companions`, `cmd_relocate_downloaded_model`, `cmd_organize_models`, `cmd_classify_models`,
`cmd_parse_comfy_workflow`, `cmd_import_custom_tool_workflow`, `cmd_get_starter_pack_items`, … + `STUDIO_HANDLERS`.

## 8. Next step (Phase 1)

Build the domain foundation: asset domain model, `ComputeProfile`/VRAM estimator, `CapabilityRegistry`,
`DreamForgeRecipe` v2, and a SHA256-identity `AssetRegistry` (SQLite) — each with unit tests, then a thin
bridge surface. No UI changes until Phases 2/4.
