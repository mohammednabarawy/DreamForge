# Inpaint Smart Selection

Samsung Gallery / Photoshop-style mask tools in the desktop inpaint mask modal.

## UX

- **Quick selects**: Subject, Background, Clothes, Face, Eyes, Hands, Legs, Feet
- **Tap object / Tap background**: click on canvas (Object Eraser-style region pick)
- **Brush / Erase**: manual refinement
- **Add to mask / Replace mask**: merge behavior for successive selections

## Backend

`backend/dreamforge_inpaint_selection.py` + bridge command `generate_inpaint_selection_mask`.

| Selection | Method |
| --- | --- |
| subject, person | rembg foreground alpha |
| background | inverted subject |
| clothes | subject minus head region |
| face | YOLO face bbox if `models/ultralytics/bbox/face_yolov8*.pt` exists, else heuristic |
| eyes | ellipses within face region |
| hands | YOLO hand model if present, else side-band heuristic |
| legs / feet | vertical bands on subject bbox |
| tap_object | color flood fill + rembg component fallback |
| tap_background | inverted tap region |

Masks are written under `outputs/dreamforge/temp/inpaint_masks/`.

## Improving precision

Install Ultralytics bbox weights under `models/ultralytics/bbox/` for sharper face/hand detection.
