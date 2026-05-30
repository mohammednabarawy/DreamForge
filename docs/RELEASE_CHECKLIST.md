# DreamForge Release Checklist

Use this before tagging a release or shipping a desktop build to testers.

## 1. Environment

- [ ] Fresh clone: `setup.bat` (Windows) or `./setup.sh` (macOS/Linux)
- [ ] `verify.bat` passes (entrypoints, imports, launcher paths)
- [ ] At least one checkpoint/UNet present under `backend/models/` for smoke generation

## 2. Backend tests

From repo root with embedded Python (Windows):

```bat
python_embeded\python.exe -m pytest backend\tests\test_dynamic_presets.py backend\tests\test_edit_lineage.py backend\tests\test_workflow_planner.py backend\tests\test_krita_resources.py backend\tests\test_errors.py backend\tests\test_brain_planning.py backend\tests\test_generation_routing.py -q
```

Broader gate (when full deps installed):

```bat
python_embeded\python.exe -m pytest backend\tests\ -q
```

- [ ] Focused AI OS / planner / MCP tests green
- [ ] No new secrets or `.env` files staged

## 3. Desktop

```bat
cd apps\desktop
npm run build
```

- [ ] Typecheck + Vite production build succeeds
- [ ] Optional: `npm run tauri build` on a release machine
- [ ] Smoke: launch `dreamforge.bat`, worker reaches **ready**, dry-run or short generate

## 4. CLI / MCP smoke

```bat
dreamforge-cli.bat --dry-run --prompt "smoke test landscape" --json
dreamforge-mcp.bat
```

- [ ] CLI `--json` dry-run returns `ready` or actionable `missing_dependencies`
- [ ] MCP `get_mcp_capabilities` lists expected tools
- [ ] MCP `dry_run` works; execution tools respect `approved=true` when required

## 5. Sample workflows

- [ ] TXT2IMG: SDXL or Flux Schnell at `1024x1024`
- [ ] Edit: Flux Kontext with `--input-image`
- [ ] Optional: Arabic poster CLI dry-run
- [ ] Manifest written with `lineage` block on edit jobs

## 6. Documentation

- [ ] [README.md](../README.md) mentions **local-only** image execution
- [ ] [TROUBLESHOOTING.md](TROUBLESHOOTING.md) covers Comfy, models, nodes, VRAM
- [ ] [README_CLI.md](README_CLI.md) and [dreamforge_mcp_instructions.md](dreamforge_mcp_instructions.md) current
- [ ] [DREAMFORGE_AI_OS_ROADMAP.md](DREAMFORGE_AI_OS_ROADMAP.md) evidence section updated

## 7. Research analyzer (optional)

If refreshing Comfy workflow research:

- [ ] Analyzer writes under `.research/` or `outputs/` only — **no tracked file churn** in `git status`

## 8. Sign-off

- [ ] Version / changelog note prepared (if tagging)
- [ ] License and third-party notices unchanged or updated deliberately
- [ ] PR targets `main`
