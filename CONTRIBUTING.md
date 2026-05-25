# Contributing to DreamForge

Thank you for your interest in DreamForge. This project is built for local, private AI image creation — and it gets better when more people test it, document it, and extend it.

You do not need to be a diffusion expert to help. Clear bug reports, small fixes, and documentation improvements are valuable contributions.

## Ways to participate

| Area | Examples |
|------|----------|
| **Bug reports** | Crashes, wrong routing, OOM on your GPU, UI glitches — include steps and logs |
| **Features** | Desktop studio UX, CLI recipes, MCP tools, Gradio polish, Arabic poster edge cases |
| **Documentation** | README, setup guides, troubleshooting, agent/MCP examples |
| **Tests** | `backend/tests/`, desktop flows, `verify.bat` gaps on Windows or macOS |
| **Translations** | UI strings, docs (keep technical terms accurate) |

Open a [GitHub Issue](https://github.com/mohammednabarawy/DreamForge/issues) to discuss larger ideas before a big pull request.

## Getting started

1. **Fork** the repository and clone your fork.
2. Run **first-time setup** from the repo root (see [README.md](README.md)):
   - Windows: `setup.bat`
   - macOS / Linux: `./setup.sh`
3. Create a branch from `main`:

   ```bash
   git checkout main
   git pull origin main
   git checkout -b your-name/short-description
   ```

4. Make your changes and run relevant checks:

   ```bat
   verify.bat
   ```

   Or targeted tests:

   ```bat
   python_embeded\python.exe -m pytest backend\tests\ -q
   ```

   Desktop (if you touched `apps/desktop/`):

   ```bat
   cd apps\desktop
   npm run build
   ```

5. **Commit** with a clear message (what changed and why).
6. Open a **pull request** against `main` with:
   - What you changed
   - How you tested it (OS, GPU, which launcher you used)
   - Screenshots for UI changes when helpful

## Pull request guidelines

- Keep PRs **focused** — one feature or fix per PR when possible.
- Match existing style in the files you edit (Python, TypeScript, Rust).
- Do not commit model weights, generated images, `python_embeded/`, `venv/`, or API keys.
- If you change user-facing behavior, update **README** or **docs/** as needed.

## Project layout (where to look)

| Path | What lives here |
|------|-----------------|
| `apps/desktop/` | Tauri + React studio UI |
| `backend/` | CLI, MCP, bridges, diffusion engine, Gradio modules |
| `docs/` | CLI reference, agent integration guides |
| `scripts/` | Setup helpers, branding sync, smoke tests |

## GPU / environment notes for testers

When reporting generation issues, please include:

- OS and GPU (e.g. Windows 11, RTX 4060 Ti 16 GB, or M-series Mac)
- VRAM profile if relevant (`16gb`, `8gb`, `5gb`, `mps`)
- Model/checkpoint name (if not default)
- Whether you used desktop, CLI, MCP, or Gradio UI

## Code of conduct

Be respectful and constructive. We are here to build useful tools together — assume good intent, give actionable feedback, and welcome newcomers.

## License

By contributing, you agree that your contributions will be licensed under the same terms as the project. The engine stack under `backend/` is GPLv3 — see [backend/LICENSE](backend/LICENSE).

## Questions?

- **Bugs and features:** [GitHub Issues](https://github.com/mohammednabarawy/DreamForge/issues)
- **Pull requests:** [GitHub Pull Requests](https://github.com/mohammednabarawy/DreamForge/pulls)

We appreciate every issue filed, doc fixed, and line of code reviewed. Thank you for helping DreamForge grow.
