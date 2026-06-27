# Edit/Inpaint Canvas Accessibility Audit

Date: 2026-06-26

## Scope

- Canvas preview compare controls
- Zoom/pan controls
- Inline inpaint mask editor
- Result candidate tray
- Edit/inpaint task controls

## Implemented

- Canvas preview is keyboard focusable and labeled as an image canvas region.
- Canvas keyboard controls:
  - `+` / `=`: zoom in
  - `-` / `_`: zoom out
  - `0`: reset view
  - arrow keys: pan when zoomed
  - `Shift` + arrow keys: larger pan step
- Before/after split handle exposes `role="slider"` with arrow-key adjustment.
- Mask tool buttons expose `aria-label` through their titles.
- Inline mask editor keyboard controls:
  - `B` or `P`: paint
  - `E`: erase
  - `[` / `]`: brush size
  - `Esc`: clear mask
- Result tray exposes `role="region"` and `role="listbox"` / `role="option"` for candidates.
- Outpaint and context overlays are labeled where they convey planning information.

## Manual Checks Still Required

- Screen-reader pass in Windows Narrator or NVDA.
- High-contrast Windows theme check.
- Keyboard-only full flow:
  1. Attach source image.
  2. Enter Inpaint.
  3. Paint or select mask.
  4. Dry-run and inspect crop/context.
  5. Generate multiple candidates.
  6. Select a candidate and use it as source.
- Reduced-motion preference review for Framer Motion canvas transitions.

## Known Limits

- Freehand brush painting is still pointer-first. Keyboard shortcuts select tools and brush sizes, but do not draw strokes without pointer input.
- Outpaint preview is a directional planning overlay, not an exact expanded-canvas render.
