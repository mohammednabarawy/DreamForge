# DreamForge agency skills

Curated [agency-agents](https://github.com/msitarzewski/agency-agents) skills linked into this project for Cursor.

The full agency install lives user-wide at `%USERPROFILE%\.cursor\skills\`. This folder only junctions the subset useful for DreamForge (desktop UI, Python backend, Comfy workflows, deploy).

## Install

From the repo root:

```powershell
.\.cursor\skills\install.ps1
```

Re-run after cloning on a new machine or after updating the user-wide agency install.

## Curated skills

See `agency-manifest.json` for the list. Typical use:

| Skill | When to use |
|-------|-------------|
| `agency-frontend-developer` | React/Tauri UI, inspector, canvas |
| `agency-backend-architect` | Python generation pipeline, routing |
| `agency-ai-engineer` | Model/workflow integration |
| `agency-prompt-engineer` | Prompt templates, Ideogram/Flux |
| `agency-minimal-change-engineer` | Focused diffs, parity fixes |
| `agency-code-reviewer` | Pre-merge review |
| `agency-reality-checker` | Smoke / verification before ship |

User-wide rules (232 agents) remain in `%USERPROFILE%\.cursor\rules\` and are not duplicated in git.
