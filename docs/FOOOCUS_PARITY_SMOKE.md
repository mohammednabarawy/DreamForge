# Fooocus parity manual smoke checklist
#
# Run after backend tests + `npm run build` + `python scripts/audit_feature_surfaces.py`.
# Mark each item when verified on a machine with models installed.

- [ ] **Create + reference (restyle)** — attach image, generate with prompt
- [ ] **Image prompt** — Pro role Image prompt, IP-Adapter assets or restyle fallback
- [ ] **Structure / ControlNet** — structure slot or role, generate
- [ ] **Inpaint default** — mask region, default intent, generate
- [ ] **Inpaint improve_detail** — lower strength detail pass
- [ ] **Inpaint modify_content** — full-strength masked replace
- [ ] **Vary subtle / strong** — canvas Vary buttons on a result
- [ ] **Upscale 1.5× / 2× / Fast 2×** — preset chips in Enhance inspector
- [ ] **PiD upscale** — when PiD assets present, upscale method routes to pid_flux
- [ ] **Extract** — each type: canny, depth, openpose, lineart, scribble, hed
- [ ] **Auto-fix face** — canvas Fix Face or Enhance panel
- [ ] **Keep face / character** — reference + checkbox, Kontext/Qwen route
- [ ] **Describe** — Describe button fills prompt from image
- [ ] **Metadata import** — Shift+drop PNG with embedded parameters
