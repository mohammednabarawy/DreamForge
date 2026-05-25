# DreamForge

Local AI image generation for Windows — headless CLI, MCP tools for agents, Arabic poster compositing, and a native desktop studio. DreamForge wraps a high-performance diffusion engine (SDXL, Flux, HiDream, Qwen, Z-Image, and more) with routing, VRAM profiles, and production-oriented workflows.

**Repository:** [github.com/mohammednabarawy/DreamForge](https://github.com/mohammednabarawy/DreamForge)

## Features

- **Headless CLI** — Generate from PowerShell or scripts with use-case recipes, brand kits, manifests, and output validation.
- **MCP server** — 14 tools for Claude and other MCP clients (`dry_run`, `generate_image`, `edit_image`, model discovery, output search, and more).
- **Desktop app (Tauri)** — Split-pane studio (Sessions · Canvas · Inspector) with a Rust ↔ Python bridge; no separate API server.
- **Classic web UI** — Full Gradio-style engine UI for power users.
- **Arabic posters** — Three-phase pipeline for exact Arabic/English text (render text in PIL, composite over generated art).
- **Multi-family routing** — Inventory and recommend across checkpoints, diffusion models, UNets, text encoders, and GGUF weights.

## Repository layout

```
DreamForge/
├── dreamforge.bat                 # Launch Tauri desktop (dev)
├── dreamforge-cli.bat             # Headless generation CLI
├── dreamforge-mcp.bat             # MCP server for agents
├── dreamforge-ui.bat              # Classic Gradio web UI
├── dreamforge-ui-anime.bat        # UI preset: anime
├── dreamforge-ui-realistic.bat    # UI preset: realistic
├── dreamforge-arabic-poster.bat   # Arabic poster pipeline
├── dreamforge-fetch-qwen-clip-smoke.bat
├── stop-dreamforge.bat            # Free port 1420 after a crash
├── setup.bat                      # First-time install (Windows)
├── setup.sh                       # First-time install (macOS/Linux)
├── python_embeded/                # Embedded Python (created by setup.bat)
├── apps/
│   └── desktop/                   # Tauri + React studio UI
├── backend/                       # Python backend (CLI, MCP, bridge, diffusion engine)
│   ├── dreamforge_cli_direct.py
│   ├── dreamforge_desktop_bridge.py
│   ├── dreamforge_mcp_server.py
│   ├── arabic_poster_pipeline.py
│   ├── modules/                   # Pipelines, model handler, Gradio UI modules
│   └── models/                    # Weights (gitignored)
├── docs/                          # CLI reference, agent guides
└── scripts/                       # Dev smoke tests
```

Generated images and model weights are **not** committed. Place checkpoints under `backend/models/` (or symlink from your existing install).

## Prerequisites

| Component | Purpose |
|-----------|---------|
| **Windows 10/11** | Primary target platform (NVIDIA CUDA) |
| **macOS 14+ (Apple Silicon)** | MPS-accelerated generation via Metal |
| **NVIDIA GPU** | CUDA generation (16 GB recommended; `8gb` / `5gb` VRAM profiles supported) |
| **Apple Silicon Mac** | MPS generation (unified memory; use `--vram-profile mps`) |
| **Python 3.10+** | Required once to run `setup.bat` / `setup.sh` (Windows setup also installs embedded Python) |
| **Model files** | `.safetensors` / `.gguf` under `backend/models/` (not in git) |
| **Node.js 20+** | Desktop app only |
| **Rust (rustup)** | Desktop app only — `cargo` on PATH |

## First-time setup (after clone)

From the repository root:

**Windows**

```bat
setup.bat
```

This will:

1. Download **embedded Python** into `python_embeded/` (if missing) and configure import paths for `backend/`
2. Install Python dependencies (PyTorch, ComfyUI repos, Gradio stack)
3. Create `backend/models/*`, `outputs/`, and cache folders
4. Run `npm install` for `apps/desktop/`

You need any **Python 3.10+** on PATH once to bootstrap setup (the Windows installer or `py` launcher is fine). After setup, launchers use `python_embeded\python.exe`.

**macOS / Linux**

```bash
chmod +x setup.sh DreamForge.command dreamforge.sh
./setup.sh
```

Creates a `venv/` at the repo root, installs backend dependencies, and installs desktop npm packages.

**Options**

```bat
setup.bat --skip-torch      REM pip pre-reqs only (fast check)
setup.bat --skip-npm        REM backend only
setup.bat --venv            REM use venv/ instead of embedded Python on Windows
```

**Models**

Setup does not download multi-GB checkpoints. Add weights under `backend/models/checkpoints/` (and other folders as needed) before generating.

**Verify**

```bat
verify.bat
```

Smoke-tests CLI, desktop bridge, MCP, web UI entrypoints, and the Tauri build.

## Quick start

### 1. Desktop studio (recommended UI)

**macOS:**
```bash
./DreamForge.command
# Or double-click DreamForge.command in Finder
```

**Windows:**
```bat
dreamforge.bat
```

If the dev server port is stuck after a crash:

```bat
stop-dreamforge.bat
dreamforge.bat
```

See [apps/desktop/README.md](apps/desktop/README.md) for branding assets and troubleshooting.

### 2. CLI — single image

```bat
dreamforge-cli.bat --prompt "a beautiful landscape at golden hour" --output landscape.png
```

Agent-style recipe with validation and manifest:

```bat
dreamforge-cli.bat ^
  --use-case product_ad ^
  --subject "sculptural wireless headphones" ^
  --composition "centered product on brushed titanium pedestal" ^
  --lighting "soft studio lighting" ^
  --brand-colors "graphite, titanium, warm white" ^
  --negative-prompt "text, letters, watermark" ^
  --validate-output
```

### 3. MCP server (for AI agents)

```bat
dreamforge-mcp.bat
```

Always run `dry_run` before heavy jobs. Full tool list and rules: [docs/DREAMFORGE_AGENT_SKILL.md](docs/DREAMFORGE_AGENT_SKILL.md) and [docs/AI_INSTRUCTIONS.md](docs/AI_INSTRUCTIONS.md).

### 4. Arabic poster

```bat
dreamforge-arabic-poster.bat --help
```

### 5. Classic web UI

```bat
dreamforge-ui.bat
```

Presets: `dreamforge-ui-anime.bat`, `dreamforge-ui-realistic.bat`.

## VRAM profiles

Pass `--vram-profile` on the CLI (or equivalent MCP options):

| Profile | Typical hardware |
|---------|------------------|
| `16gb` | RTX 4060 Ti 16 GB, RTX 5060 Ti 16 GB |
| `8gb` | 8 GB cards — smaller resolutions / lighter models |
| `5gb` | Very tight VRAM — draft models only |
| `auto` | Let the stack decide |

Use `--dry-run` to resolve the plan and list missing dependencies without loading the GPU.

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/README_CLI.md](docs/README_CLI.md) | CLI arguments, batch JSONL, MCP overview |
| [docs/AI_INSTRUCTIONS.md](docs/AI_INSTRUCTIONS.md) | Agent integration |
| [docs/DREAMFORGE_AGENT_SKILL.md](docs/DREAMFORGE_AGENT_SKILL.md) | Use cases, model families, 8 GB presets |
| [apps/desktop/README.md](apps/desktop/README.md) | Tauri app setup |
| [backend/readme.md](backend/readme.md) | Engine notes and upstream lineage |

## Outputs

By default, generations land under `outputs/` (gitignored). The desktop app and CLI can write manifests (JSON) next to images when validation or agent workflows are enabled.

## Branding

Desktop and Gradio UIs use the assets in `apps/desktop/public/branding/` (also copied to `backend/html/` for the classic WebUI). After updating logos, run:

```bat
python_embeded\python.exe scripts\sync-branding.py
```

## Development

- **Setup:** `setup.bat` or `./setup.sh` after every fresh clone.
- **Backend:** Python under `backend/` — launch Gradio via `dreamforge-ui.bat` or import from the desktop bridge.
- **Desktop:** `cd apps\desktop && npm install && npm run tauri dev` (or use `dreamforge.bat` from root).
- **Tests:** `python_embeded\python.exe backend\tests\test_model_ui_defaults.py` (or `venv\Scripts\python.exe` on Windows venv)

Set `DREAMFORGE_ROOT` to the `backend/` folder when tools need an explicit path (the provided `.bat` launchers set this automatically).

## License

The generation stack under `backend/` includes third-party components; see [backend/LICENSE](backend/LICENSE). DreamForge-specific CLI, MCP, desktop shell, and agent tooling are part of this repository’s distribution model—refer to repository history and upstream notices for attribution details.

## Acknowledgments

DreamForge builds on the open diffusion UI ecosystem (Stable Diffusion XL, Flux, and community checkpoints). Engine behavior and model support depend on what you install locally under `backend/models/`.
