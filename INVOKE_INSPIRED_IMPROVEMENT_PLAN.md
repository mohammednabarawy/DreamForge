# Invoke-inspired DreamForge improvement plan

Reviewed 2026-07-30 against:

- `invoke-ai/launcher` commit `f31ee36688bcf7128647af831470209b7f5f8dc7`
- `invoke-ai/InvokeAI` commit `01a8315ab61cf6f9e3579fc82561fc567ae1cf2e`

## Product boundary

DreamForge keeps its Tauri desktop shell, Python bridge, workflow policy, model layout, and managed ComfyUI execution engine. This work adopts useful launcher and library-management patterns; it does not embed InvokeAI, replace ComfyUI, introduce Electron, or create a second model database.

## Review findings

| Area | Useful Invoke pattern | DreamForge today | Decision |
| --- | --- | --- | --- |
| Install | Location -> version/configure -> review -> progress, resumable state, repair | Pinned resumable bootstrap and repair already exist, but first run cannot choose the data root | Add a first-run data-root picker and clearer storage validation; keep pinned ComfyUI recipes |
| Runtime | Explicit process states, logs, recovery actions, update visibility | Engine health/restart/logs are already stronger and ComfyUI-aware | Keep the lifecycle; add a compact diagnostics/status surface and release check |
| Models | Search/filter/sort, install queue states, scan/reidentify, safe bulk actions | Civitai discovery, dependency downloads, cache, classification, and conservative organizer exist; organizer has no UI and gallery metadata is thin | Expose dry-run-first organization, add size/date metadata and filters, harden downloads |
| Styles | Search, grouped built-in/user presets, active-preset clarity | Large thumbnail library and backend groups exist; UI is a single long search list | Add groups plus local Favorites and Recent without changing recipe format |
| Workflows | Search/sort/tagged library and explicit import | DreamForge has curated templates and custom Comfy workflow import | Keep current workflow contracts; do not import Invoke nodes or backend |
| Updates | Launcher self-update plus app version selection | Source-based beta releases; no signed updater channel | Add non-destructive release visibility now; defer in-app binary replacement until signed artifacts exist |

## Implementation

### 1. First-run setup and diagnostics

- [x] Let users choose the DreamForge data root before installation.
- [x] Recompute the managed models path and disk check for the chosen drive.
- [x] Show runtime paths, disk state, model-folder warnings, and one-click folder access in App Settings.
- [x] Provide a copyable, secret-free diagnostics snapshot.

### 2. Model library and downloads

- [x] Add file size and modified time to the cached model gallery payload.
- [x] Add model family filtering and useful sorting while retaining mode-aware recommendations.
- [x] Expose the existing conservative organizer as Preview then Apply safe moves; never include low-confidence files automatically.
- [x] Validate download URLs, avoid forwarding tokens to unrelated hosts, keep atomic `.part` writes, and reject incomplete responses.
- [x] Refresh the visible model library after successful downloads or organization.

### 3. Styles

- [x] Use the existing backend style groups in the desktop grid.
- [x] Add local Favorites and Recent filters with no backend schema migration.
- [x] Keep selection reversible and show the number of matching styles.

### 4. Releases and licensing

- [x] Show current/latest GitHub release state and open the release page on request.
- [x] Add an upstream notice for the Apache-2.0 Invoke projects and document that DreamForge remains GPLv3.
- [x] Do not add an auto-updater until CI produces signed, platform-specific artifacts.

### 5. Verification gates

- [x] Focused Python tests for runtime/bootstrap and model-library metadata.
- [x] Rust tests/checks for download URL rules and desktop command compilation.
- [x] Desktop TypeScript production build.
- [x] Full relevant backend test slice and `git diff --check`.
- [x] Review the final diff without overwriting pre-existing custom-tool changes.

## Verification record

- Focused backend slice: 22 passed.
- Rust desktop tests: 4 passed; desktop commands compiled.
- Desktop production build: passed (existing bundle-size and mixed-import warnings remain).
- Visual smoke checks: first-run setup, settings, models, and styles at 1440x900 and 900x700; no page errors in the mocked desktop bridge views.
- `git diff --check`: passed (Git only reported the repository's existing LF-to-CRLF notices).
- Extra full backend run: 820 passed, 3 skipped, 2 failed in unchanged `dreamforge_errors.py` / `dreamforge_preflight.py` behavior. The failures are recorded rather than folded into this feature diff: DepthAnything Hub errors map to `generation_failed`, and the Flux VRAM fixture now reports a preflight error.

## Deliberately not ported

- Electron, `uv`-managed Invoke environments, Invoke's SQL model records, Invoke workflow nodes, and Invoke's model-loading/cache backend: these duplicate or replace working DreamForge/ComfyUI layers.
- Pause/resume for model downloads: DreamForge currently has single-request Tauri downloads, not a durable job service. Adding pause/resume without persistent jobs would be unreliable; the current scope hardens completion and failure behavior first.
- Automatic binary replacement: safe only after release signing, updater manifests, rollback behavior, and CI artifact publication are in place.

## License note

Invoke launcher and InvokeAI are Apache-2.0. DreamForge is GPLv3. The implementation is written against DreamForge's existing architecture and retains upstream attribution in `THIRD_PARTY_NOTICES.md`; no Invoke branding or backend code is bundled.
