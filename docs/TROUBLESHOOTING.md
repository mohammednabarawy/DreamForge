# DreamForge Troubleshooting

DreamForge runs **image generation locally** on your machine. Prompts, models, and outputs are not sent to a cloud inference API unless you explicitly configure a separate LLM provider for agent planning.

## Quick diagnostics

| Symptom | First check |
|---------|-------------|
| Desktop stuck on “Starting GPU engine…” | `verify.bat`, then restart with `stop-dreamforge.bat` → `dreamforge.bat` |
| CLI/MCP fails immediately | Run from repo root; use `python_embeded\python.exe` or `./setup.sh` venv |
| “Model not found” | File exists under `backend/models/` in the correct subfolder (see below) |
| “Missing custom node pack” | Install approved Comfy custom nodes; restart Comfy/worker |
| OOM / CUDA out of memory | Lower `--vram-profile` (`8gb` / `5gb`), resolution, or switch to Schnell/Z-Image |
| Blank or flat output | Run with `--validate-output`; check manifest warnings |

Structured failure reports in the desktop UI include **repair actions** (download companions, switch model, reduce resolution). Expensive installs and retries require explicit approval.

---

## Managed ComfyUI

DreamForge can boot and talk to a local **ComfyUI** instance (`dreamforge_comfy_server.py`).

**Comfy will not start**

- Confirm `backend/repositories/ComfyUI/` exists (setup clones or links it).
- Check `backend/outputs/dreamforge/logs/comfy.server.log`.
- Port conflict: another ComfyUI instance may already use the default port.
- After installing custom nodes, **restart** the worker (`Restart engine` in desktop, or stop/start launchers).

**Generation hangs at “Submitting to ComfyUI…”**

- Open the Comfy log above; missing Python deps in custom nodes are a common cause.
- Run a lightweight dry-run first: `dreamforge-cli.bat --dry-run --prompt "test" --json`.

**Live preview is slow**

- Streaming edits use **fewer steps** (`live_steps` from Krita-derived recipes) during preview; final runs use full recipe steps.

---

## Model paths

Canonical layout (Comfy-compatible):

```
backend/models/
  checkpoints/          # SDXL / SD1.5 full checkpoints
  diffusion_models/     # Flux, HiDream, Qwen UNets
  text_encoders/        # CLIP / T5 / Qwen text encoders
  vae/
  loras/
  controlnet/
  clip_vision/
  upscale_models/
```

**Tips**

- Use `dreamforge-cli.bat --list-models --json` to see what the engine detects.
- `--dry-run` reports `missing_dependencies` and suggested companion downloads.
- Symlinks are supported if they resolve to readable files.
- DreamForge does **not** download multi-GB checkpoints during setup; add weights manually or use the desktop **companion download** flow when prompted.

Set `DREAMFORGE_ROOT` to the `backend/` folder when running scripts outside the launchers.

---

## Missing Comfy custom nodes

Advanced workflows (IP-Adapter, inpaint helpers, ControlNet preprocessors) need packs under:

```
backend/repositories/ComfyUI/custom_nodes/
```

DreamForge ships a **Krita-aligned install recipe** (`dreamforge_krita_recipes.py`) with pinned git versions for required packs.

**Desktop / bridge check** (directory + optional live node registration):

```json
{"cmd":"check_custom_node_packs","params":{"pack_ids":["ComfyUI_IPAdapter_plus"],"use_object_info":true}}
```

If the folder exists but nodes are missing from Comfy’s API, restart Comfy after `git pull` in that pack.

Workflow planner readiness lists `install_custom_node_pack` actions with URL and version — installation always requires **user approval** in the desktop UI.

---

## Low VRAM

| Profile | When to use |
|---------|-------------|
| `16gb` | Default for 16 GB NVIDIA cards |
| `8gb` | 8 GB cards; prefer FP8/Schnell, 768²–1024² |
| `5gb` | Tight VRAM; quantized/GGUF routes, lower step caps |
| `auto` | Let routing decide |

**CLI**

```bat
dreamforge-cli.bat --vram-profile 8gb --dry-run --prompt "hero product" --json
```

**If you still OOM**

- Reduce `--aspect-ratio` or `--width` / `--height`.
- Use `--performance Speed` or `--use-case fast_draft`.
- Close other GPU apps.
- On Windows, ensure sufficient page file; see [OPTIMIZATION.md](OPTIMIZATION.md).

---

## Desktop bridge / worker

- **Worker log tail** appears in the desktop status area when boot fails.
- **Local style memory** lives at `outputs/dreamforge/memory/user_style_profile.json` (opt-in; clear/export in Settings).
- **Plan cards** block Generate until you Approve & Run when agent approval is enabled.

Bridge smoke:

```bat
python_embeded\python.exe backend\dreamforge_desktop_bridge.py --once "{\"cmd\":\"ping\"}"
```

---

## MCP and agents

- Execution tools (`generate_image`, `edit_image`, …) require **`approved=true`** when the server enforces execution approval.
- Call **`dry_run`** before heavy jobs; inspect `ready` and `missing_dependencies`.
- MCP exposes **task-level** workflow blueprints, not arbitrary shell or filesystem access.
- Capabilities: `get_mcp_capabilities()` — disable execution with env/config if needed (see server module).

Planning tools merge **dynamic presets** from intent + local style memory (`dynamic_preset` in brain plan JSON).

---

## Platform notes

| OS | Notes |
|----|--------|
| **Windows 10/11** | Primary target; CUDA NVIDIA; use `setup.bat` and `verify.bat` |
| **macOS (Apple Silicon)** | MPS via Metal; use `./setup.sh` and `DreamForge.command` |
| **Linux** | Supported via `./setup.sh`; ensure CUDA or CPU fallback; path case sensitivity matters for model files |

DirectML / AMD / Intel paths depend on your PyTorch build; see [OPTIMIZATION.md](OPTIMIZATION.md).

---

## Security (local studio)

- **Workflow downloads** from the internet are research inputs only; DreamForge builds first-party templates — do not paste untrusted Comfy graphs into production without review.
- **MCP** binds to local stdio by default; do not expose the MCP process to untrusted networks without authentication.
- **Agent providers** (OpenAI-compatible URLs) are optional and used for **planning text only** unless you explicitly run cloud tools; image generation remains local Comfy/DreamForge.
- **Companion downloads** require approval before fetching model assets from configured URLs.

---

## Still stuck?

1. Run `verify.bat` (or `python scripts/verify_entrypoints.py`).
2. Capture `backend/outputs/dreamforge/logs/comfy.server.log` and the job manifest JSON next to your output.
3. [Open an issue](https://github.com/mohammednabarawy/DreamForge/issues/new) with OS, GPU, VRAM profile, and the structured error `code` field.
