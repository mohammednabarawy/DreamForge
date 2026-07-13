# DreamForge

**Local AI image creation studio** — desktop app, headless CLI, Gradio WebUI, and MCP tools for agents. Run SDXL, Flux, HiDream, Qwen, Z-Image, Krea, Ideogram, and more on your own GPU.

**Image generation and editing run on your machine.** Optional cloud LLM providers are used only for agent *planning* text when you configure them.

**Repository:** [github.com/mohammednabarawy/DreamForge](https://github.com/mohammednabarawy/DreamForge)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](backend/LICENSE)
[![Release](https://img.shields.io/github/v/release/mohammednabarawy/DreamForge?include_prereleases&label=release)](https://github.com/mohammednabarawy/DreamForge/releases)
[![GitHub issues](https://img.shields.io/github/issues/mohammednabarawy/DreamForge)](https://github.com/mohammednabarawy/DreamForge/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/mohammednabarawy/DreamForge)](https://github.com/mohammednabarawy/DreamForge/pulls)

> **Beta (v0.2.0-beta)** — DreamForge is ready for **builders and contributors**: clone the repo, run `setup.bat` (Windows) or `./setup.sh` (macOS/Linux), add models under `models/`, then launch with `dreamforge.bat`. This is **not** yet a one-click public installer; release tags are source-based until automated desktop builds land ([#15](https://github.com/mohammednabarawy/DreamForge/issues/15)). See [Project status](#project-status) below.

## Why DreamForge?

- **Private by default** — models, prompts, and images stay on your machine (local ComfyUI / DreamForge worker).
- **Runs on almost anything** — 24 GB workstations down to 4 GB GPUs, Apple Silicon, AMD/Intel via DirectML, and CPU-only fallback. See the [Optimization & Hardware Guide](docs/OPTIMIZATION.md).
- **Multiple surfaces** — desktop studio, classic Gradio WebUI, CLI, or MCP for automation.
- **Production-minded** — VRAM profiles, dry-runs, manifests, multi-reference routing, and agent recipes.

## Project status

| | |
|---|---|
| **Current release** | [v0.2.0-beta](https://github.com/mohammednabarawy/DreamForge/releases/tag/v0.2.0-beta) (pre-release) |
| **Primary surface** | Tauri desktop studio (`dreamforge.bat` / `./dreamforge.sh`) |
| **Also available** | CLI (`dreamforge-cli.bat`), MCP (`dreamforge-mcp.bat`), Gradio WebUI (`backend/launch.py`) |
| **Models** | You provide checkpoints / LoRAs under `models/` or point settings at an existing ComfyUI models folder |
| **Not included yet** | Signed installers on GitHub releases, auto-updater, bundled model weights |

Recent beta work focuses on **multi-reference generation** (face, structure, style, and edit sources), **mode-aware reference handling** in the desktop UI, and **broader edit/inpaint model routing** across Flux Kontext, Qwen Edit, IP-Adapter, Krea, Z-Image, and Ideogram families.

## Features

- **Desktop app (Tauri)** — Split-pane studio (Sessions · Canvas · Inspector) with a Rust ↔ Python bridge.
- **Multi-reference workflows** — Attach multiple reference images with roles (prompt/face, structure, restyle, edit source). Routing adapts per model family: chained latents for Flux Kontext, stitched inputs for Krea/Z-Image/Ideogram, IP-Adapter + ControlNet hybrids, and Qwen Edit Plus.
- **Edit & inpaint** — Studio modes route to the right ComfyUI workflow for semantic edits, masked inpaint, and upscale.
- **Headless CLI** — PowerShell-friendly generation with use-case recipes, brand kits, and validation.
- **MCP server** — Tools for Claude and other MCP clients (`dry_run`, `generate_image`, `edit_image`, model discovery, and more).
- **Classic Gradio WebUI** — Full engine UI for power users (`backend/launch.py`).
- **Multi-family routing** — Inventory across checkpoints, diffusion models, UNets, text encoders, and GGUF weights.

## Participate — we welcome contributors

DreamForge is an open project. Your help matters whether you write code, improve docs, report bugs, or test on different GPUs.

| Action | Link |
|--------|------|
| Pick up a task | [Open issues](https://github.com/mohammednabarawy/DreamForge/issues) — labeled `help wanted` |
| Report a bug or request a feature | [New issue](https://github.com/mohammednabarawy/DreamForge/issues/new) |
| Submit a fix or feature | [Open a pull request](https://github.com/mohammednabarawy/DreamForge/compare) |
| Read the full guide | [CONTRIBUTING.md](CONTRIBUTING.md) |

**High-impact areas right now:** release automation ([#15](https://github.com/mohammednabarawy/DreamForge/issues/15)), multi-reference test coverage ([#16](https://github.com/mohammednabarawy/DreamForge/issues/16)), reference routing diagnostics ([#17](https://github.com/mohammednabarawy/DreamForge/issues/17)), and contributor setup docs ([#19](https://github.com/mohammednabarawy/DreamForge/issues/19)).

Fork `main`, run `setup.bat` or `./setup.sh`, and send a PR — maintainers will review and help you iterate.

## Repository layout

```
DreamForge/
├── dreamforge.bat                 # Launch Tauri desktop (dev)
├── dreamforge-cli.bat             # Headless generation CLI
├── dreamforge-mcp.bat             # MCP server for agents
├── setup.bat / setup.sh           # First-time install
├── verify.bat                     # Post-install smoke checks
├── apps/desktop/                  # Tauri + React studio UI
├── backend/                       # Python backend (CLI, MCP, engine, launch.py)
├── docs/                          # CLI reference, agent guides, troubleshooting
└── scripts/                       # Setup, branding sync, smoke tests
```

Generated images and model weights are **not** committed. Place checkpoints under `models/` (or symlink from an existing ComfyUI install).

## Prerequisites

| Component | Purpose |
|-----------|---------|
| **Windows 10/11** | Primary target (NVIDIA CUDA) |
| **macOS 14+ (Apple Silicon)** | MPS via Metal |
| **Linux** | Supported via `setup.sh` (NVIDIA CUDA or CPU fallback) |
| **NVIDIA GPU** | CUDA (16 GB recommended; `8gb` / `5gb` profiles supported) |
| **Python 3.10+** | For `setup.bat` / `setup.sh` |
| **Model files** | `.safetensors` / `.gguf` under `models/` |
| **Node.js 20+** | Desktop app |
| **Rust (rustup)** | Desktop app — `cargo` on PATH |

## First-time setup

**Windows**

```bat
setup.bat
```

**macOS / Linux**

```bash
chmod +x setup.sh DreamForge.command dreamforge.sh
./setup.sh
```

On **Apple Silicon**, use **native arm64 Node** for the desktop app (`node -p process.arch` should print `arm64`). Setup requires Python 3.10+ and automatically preserves an incompatible Rosetta environment as `venv.incompatible/` before rebuilding a native arm64 `venv/`. The macOS launchers also repair missing Tauri/Rollup native bindings when npm skips optional platform packages.

`./setup.sh` clones **ComfyUI** into `engines/comfyui/` (with legacy fallbacks under `backend/repositories/ComfyUI`).

Then verify:

```bat
verify.bat
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for developer workflow and testing expectations.

**Options:** `setup.bat --skip-torch`, `--skip-npm`, `--venv`

**Models:** Setup does not download multi-GB checkpoints. Add weights under `models/checkpoints/` before generating.

**Optional:** Face/identity reference workflows may require additional ComfyUI nodes and models. See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) if IP-Adapter or FaceID stacks are missing.

## Quick start

### Desktop studio (recommended)

**macOS:** `./DreamForge.command` or `./dreamforge.sh`

Use **arm64 Node 20+** (`nvm use 24` or Homebrew). If Tauri reports a missing native binding, run:

```bash
cd apps/desktop && rm -rf node_modules package-lock.json && npm install
```

**Windows:**

```bat
dreamforge.bat
```

If port 5173 is stuck: `stop-dreamforge.bat` then `dreamforge.bat` again.

See [apps/desktop/README.md](apps/desktop/README.md) for branding and troubleshooting.

### CLI

```bat
dreamforge-cli.bat --prompt "a beautiful landscape at golden hour" --output landscape.png
```

### MCP (for AI agents)

```bat
dreamforge-mcp.bat
```

Run `dry_run` before heavy jobs. See [docs/DREAMFORGE_AGENT_SKILL.md](docs/DREAMFORGE_AGENT_SKILL.md) and [docs/AI_INSTRUCTIONS.md](docs/AI_INSTRUCTIONS.md).

### Classic Gradio WebUI

From the repo root after setup:

```bat
python_embeded\python.exe backend\launch.py
```

macOS/Linux (with `venv` activated):

```bash
python backend/launch.py
```

## VRAM profiles

| Profile | Typical hardware |
|---------|------------------|
| `16gb` | RTX 4060 Ti / 5060 Ti 16 GB |
| `8gb` | 8 GB discrete GPU |
| `5gb` | Very tight VRAM |
| `mps_24gb` | Apple Silicon — ~24 GB unified memory tier |
| `mps_16gb` | Apple Silicon — ~16 GB unified memory tier |
| `mps_8gb` | Apple Silicon — ~8 GB unified memory tier |
| `mps_4gb` | Apple Silicon — 8 GB RAM or less |
| `auto` | Detect CUDA VRAM or Mac unified memory |

On Mac, the desktop Inspector lists **Apple Silicon** profiles separately from **NVIDIA** profiles. `auto` picks a Mac tier from installed RAM when MPS is available.

Use `--dry-run` on the CLI to resolve the plan without loading the GPU.

## Documentation

| Doc | Contents |
|-----|----------|
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute, PR workflow, testing |
| [docs/README_CLI.md](docs/README_CLI.md) | CLI arguments, `--json`, MCP |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Comfy, model paths, missing nodes, VRAM, security |
| [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md) | Pre-release test gate |
| [docs/AI_INSTRUCTIONS.md](docs/AI_INSTRUCTIONS.md) | Agent integration |
| [docs/DREAMFORGE_AGENT_SKILL.md](docs/DREAMFORGE_AGENT_SKILL.md) | Use cases, model families |
| [docs/dreamforge_mcp_instructions.md](docs/dreamforge_mcp_instructions.md) | MCP tool guidance |
| [apps/desktop/README.md](apps/desktop/README.md) | Tauri app setup |
| [backend/readme.md](backend/readme.md) | Engine notes |

## Outputs

Generations default to `outputs/` (gitignored). The desktop app and CLI write JSON **manifests** next to images (prompt, model, routing, validation, and **edit lineage** when applicable). Local **style memory** is stored at `outputs/dreamforge/memory/user_style_profile.json` (opt-in; manage in desktop Settings).

## Branding

Assets live in `apps/desktop/public/branding/` and are mirrored to `backend/html/` for Gradio. After updating logos:

```bat
python_embeded\python.exe scripts\sync-branding.py
```

## Development

- **Setup:** `setup.bat` or `./setup.sh` after every clone.
- **Backend:** `backend/launch.py` or imports from the desktop bridge.
- **Desktop:** `cd apps\desktop && npm run tauri dev`
- **Tests:** `python_embeded\python.exe -m pytest backend\tests\ -q`

Set `DREAMFORGE_ROOT` to the `backend/` folder when needed (launchers set this automatically).

## Branching

All development targets **`main`** (the default branch on GitHub). Open pull requests against `main` only.

## License

The generation stack under `backend/` includes third-party components; see [backend/LICENSE](backend/LICENSE) (GPLv3). Refer to repository notices for upstream attribution.

## Acknowledgments

DreamForge builds on the open diffusion ecosystem (Stable Diffusion XL, Flux, and community checkpoints). Model support depends on what you install under `models/`.
