# Style thumbnails

DreamForge style cards use preview images stored here, following the **Fooocus / RuinedFooocus** convention:

- Directory: `backend/assets/style_thumbnails/`
- Filename: style display name with spaces and colons replaced by underscores, `.jpg` extension  
  Example: `Style: sai-enhance` → `Style_sai-enhance.jpg`

Recipe presets can also use `{style_id}.jpg` (e.g. `product_ad.jpg`).

## Sync previews

```powershell
# Copy from a local Fooocus/RuinedFooocus install if present
python scripts/sync_style_thumbnails.py

# Download Fooocus upstream samples from GitHub
python scripts/sync_style_thumbnails.py --download
```

Add or replace any missing JPG/PNG here; the desktop Styles tab resolves thumbnails at runtime via absolute paths from the bridge.
