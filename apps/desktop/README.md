# DreamForge (Tauri)

Native desktop shell for local DreamForge generation — split-pane studio UI with Rust ↔ Python bridge (no separate API server).

## Prerequisites

1. **Node.js** 20+
2. **Rust** (`rustup`) — `cargo` on PATH (or use the launcher `.bat`, which prepends `%USERPROFILE%\.cargo\bin`)
3. Repo root with Python runtime (`python_embeded\` after `setup.bat`, or `venv\`) and model weights

## Run (dev)

From repo root:

```bat
dreamforge.bat
```

The studio UI loads immediately while the GPU engine boots in the background (like the Gradio web UI). **Generate** stays disabled until the engine is ready.

Engine supervision (inspired by LTX Desktop patterns, adapted for Tauri):

- Phased boot messages (`loading_pytorch`, `loading_pipeline`, …) via `worker.events` and `get_engine_status`
- GPU name / VRAM in the status bar when CUDA is available
- `get_generation_progress` polled every 500ms during renders (phase + percent)
- Single-flight generation (Rust + Python worker return `generation_in_progress`)
- Auto-restart of the GPU worker up to twice after an unexpected exit (not during an active job)

### Production build (faster startup)

```bat
cd apps\desktop
npm run tauri build
```

Install from `apps\desktop\src-tauri\target\release\bundle\`.

### Classic Gradio UI (parity / fallback)

Same Python surface as before the desktop shell:

```bat
dreamforge-ui.bat
```

Or from repo root:

```bat
dreamforge-ui-embed.bat
```

If port **1420** is stuck after a crash:

```bat
stop-dreamforge.bat
dreamforge.bat
```

## Environment

```bat
set DREAMFORGE_ROOT=D:\DreamForge\backend
```

(Points the bridge at the Python backend root; defaults to `backend/` under the repo if unset.)

## Brand assets

Canonical files live under `public/branding/` and are mirrored into the Gradio WebUI at `backend/html/`:

| File | Use |
|------|-----|
| `logo-icon.png` | Favicon, title bar icon, Tauri bundle icons (`icon.ico`, `icon.icns`, `32x32.png`, …) |
| `logo-wordmark.png` | Horizontal lockup with tagline (title bar, canvas empty state) |
| `background.png` | Desktop shell backdrop + Gradio page background |

After replacing artwork, sync and regenerate bundle icons from the repo root:

```bat
python_embeded\python.exe scripts\sync-branding.py
```

Or from `apps\desktop` only:

```bat
..\..\python_embeded\python.exe scripts\regenerate-icons.py
```

(`regenerate-icons.py` center-crops `logo-icon.png` to a square before writing `.ico` / `.icns`.)

## Layout

- **Left:** Sessions (outputs grouped by folder)
- **Center:** Canvas + prompt
- **Right:** Models, style presets, generation settings

## Reliable generation

DreamForge runs inference in a **long-lived GPU engine process** (stdout JSON + `outputs/dreamforge/logs/worker.events` backup). Boot logs: `outputs/dreamforge/logs/worker.log`. Per-job logs: `outputs/dreamforge/logs/<job-id>.log`. The desktop shell should stay open while the GPU works.

If the engine fails to start, use **Restart GPU engine** in the canvas overlay or inspect `worker.log`.

- Use **Dry run** to validate settings before spending GPU time
- **Cancel** stops the active job
- If generation fails, read the **Generation log** panel and the log file path shown in status
- Large previews are downscaled automatically so the UI does not run out of memory

If the app closes with `STATUS_CONTROL_C_EXIT`, that is usually **Ctrl+C** in the terminal — avoid pressing `Y` on "Terminate batch job?" while a render is running.
