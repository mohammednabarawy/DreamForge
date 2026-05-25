# DreamForge Reliability Plan

> Research-backed roadmap for making DreamForge a dependable AI image generation
> studio: stable generation, clear error messages, automatic model organization,
> and predictable user experience.

## TL;DR — What we are doing

1. **Auto-organize models by architecture.** Read the `.safetensors` header
   (no GPU, no full load) to classify each file as
   `checkpoint / diffusion_model / vae / text_encoder / lora / controlnet / clip_vision / upscale_model`
   and which family (SDXL, SD 1.5, Flux, Flux Kontext, Flux 2, HiDream, HiDream
   O1, Qwen Image, Qwen Edit, SD3, etc.). Then move it to the canonical
   ComfyUI folder (`models/checkpoints/`, `models/diffusion_models/`,
   `models/text_encoders/`, ...). Dry-run by default, apply on explicit
   confirmation.
2. **Structured generation errors.** Every failure mode emits a stable code
   (`out_of_memory`, `model_not_found`, `model_file_unreadable`,
   `missing_companion`, `missing_input_image`, `invalid_input_image`,
   `unsupported_model_format`, `disk_full`, `worker_crashed`,
   `generation_cancelled`). The UI maps each code to a short, actionable
   message and a "what to do" hint.
3. **Preflight.** Before sampling, we check: model file exists & is readable,
   companion CLIP/VAE for Flux/HiDream/Qwen exist, free disk space ≥ 1 GB,
   VRAM headroom looks plausible (warn under estimated requirement).
4. **OOM resilience.** Set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`
   by default. Catch `torch.cuda.OutOfMemoryError` and surface
   `out_of_memory` with a concrete suggestion (lower VRAM profile, lower
   resolution, smaller batch, switch to a quantized variant we found in the
   inventory).
5. **Worker auto-recovery.** When the worker dies mid-generation we already
   restart it; we now also surface the killed-by-OOM signal where possible
   (Linux `dmesg`, Windows event log handle is best-effort), and never get
   stuck in "booting" — the UI gets a definitive `worker_crashed` event.

The remaining sections explain the why behind each piece and call out the
remaining work.

---

## Research notes (May 2026)

Sources surveyed:

* **ComfyUI canonical layout** (`folder_paths.py`, `extra_model_paths.yaml.example`):
  `models/checkpoints`, `models/diffusion_models` (alias `models/unet`),
  `models/text_encoders` (alias `models/clip`), `models/vae`,
  `models/clip_vision`, `models/loras`, `models/controlnet`,
  `models/upscale_models`, `models/embeddings`, `models/vae_approx`.
* **Architecture detection without loading**:
  * `lora_unet_double_blocks_*` / `single_blocks_*` → Flux (incl. Kontext).
  * `double_stream_modulation_img.lin.weight` → Flux 2.
  * `joint_blocks.*` → SD3.
  * `lora_te2_` / `text_encoder_2` / `conditioner.embedders.1.` /
    `model.diffusion_model.label_emb.*` → SDXL.
  * `cond_stage_model.*` + `input_blocks.*` and no SDXL signature → SD 1.5.
  * `diffusion_model.*` (no `model.` prefix) → Wan / video diffusion.
  * Qwen Image: filename contains `qwen` (no upstream-stable tensor token
    yet); `edit` substring = `qwen_image_edit`.
  * HiDream: filename contains `hidream`; `o1` substring = `hidream_o1`
    (built-in tokenizer, must live under `checkpoints/`).
  * Comfy/SDNext also use **file-size heuristics** as a fallback
    (SDXL ≈ 6.5 GB fp16, SD3.5-Large ≈ 18 GB, Flux 20–40 GB, fp8 ≈ 11 GB).
* **Fooocus / Forge OOM experience** (lllyasviel issues):
  * Set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`.
  * If the user is at the edge of VRAM, encourage `--lowvram` /
    `--attention-split` and a system swap file ≥ 20 GB.
  * After an OOM the process is unreliable; restart is the safe answer.
* **Best-practice for "studio" UX** (InvokeAI, Forge, Krita-AI):
  * Inventory tab listing _every_ file by category with a "fix placement"
    button.
  * Preflight that says "this run will need ~12 GB VRAM; you have 8 GB —
    recommend `--lowvram`".
  * Always show the **structured reason** on failure, not a raw traceback.

---

## Canonical model layout (target state)

```
backend/models/
├── checkpoints/          # Full SD/SDXL/SD3 with bundled CLIP+VAE; HiDream-O1
├── diffusion_models/     # UNet-only weights (Flux, Flux Kontext, Flux 2,
│   │                      HiDream I1, Qwen Image, Wan, etc.)
│   └── (unet/)           # legacy alias, still scanned
├── text_encoders/        # CLIP-L, CLIP-G, T5-XXL, Mistral-3-Small (Flux 2),
│   │                      Qwen-2.5-VL, Gemma-4
│   └── (clip/)           # legacy alias, still scanned
├── vae/                  # ae.safetensors (Flux), flux2-vae, qwen_image_vae,
│                          sdxl_vae, ...
├── clip_vision/          # CLIP vision models
├── loras/                # LoRAs + their .txt sidecars
├── controlnet/           # ControlNet weights
├── upscale_models/       # ESRGAN / RealESRGAN / SwinIR
├── embeddings/           # Textual-inversion
├── inpaint/              # SD inpainting models
├── vae_approx/           # TAESD previews
└── inbox/                # CivitAI handler drop zone
```

Each launcher and the desktop bridge already read this tree; we are aligning
**setup**, **`PathManager.DEFAULT_PATHS`**, and the **download surface** to
the same canonical names.

---

## Architecture & role classifier

`backend/modules/model_classifier.py` reads the safetensors header (8-byte
little-endian length, followed by JSON keyed by tensor name). It returns a
`ModelClassification` with:

| Field         | Values                                                                                                                                                                     |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `role`        | `checkpoint`, `diffusion_model`, `vae`, `text_encoder`, `clip_vision`, `lora`, `controlnet`, `upscale_model`, `embedding`, `unknown`                                        |
| `family`      | `sdxl`, `sd15`, `sd3`, `flux`, `flux_kontext`, `flux2`, `hidream`, `hidream_o1`, `qwen_image`, `qwen_image_edit`, `wan`, `z_image`, `hunyuan`, `unknown`                    |
| `target_dir`  | the canonical ComfyUI subfolder (`checkpoints`, `diffusion_models`, ...)                                                                                                   |
| `confidence`  | `high` (tensor-key match), `medium` (size + name combo), `low` (filename only)                                                                                             |
| `reasons`     | human-readable strings explaining the verdict                                                                                                                              |
| `warnings`    | actionable warnings, e.g. "HiDream-O1 needs the built-in tokenizer — place under `checkpoints/`"                                                                            |

Behaviour:

* **Safetensors**: header parsed via direct read (no extra dependency). Reads
  only the first ~64 KB.
* **GGUF**: classified by filename (`gguf` is opaque without a parser).
* **ckpt/pt/pth/bin**: filename + size heuristics; flagged as `low`
  confidence and never auto-moved without `--apply --include-low-confidence`.
* Files already in the correct folder are reported as `role_match=True` and
  skipped by the organizer.

---

## Organizer

`backend/modules/model_organizer.py` walks `backend/models/`, runs each file
through the classifier, and produces a plan:

```jsonc
{
  "models_root": "...\\backend\\models",
  "summary": {"total": 42, "to_move": 7, "ambiguous": 2, "skipped": 31},
  "actions": [
    {
      "source": "checkpoints/flux1-dev-fp8.safetensors",
      "destination": "diffusion_models/flux1-dev-fp8.safetensors",
      "role": "diffusion_model",
      "family": "flux",
      "confidence": "high",
      "reasons": ["tensor key 'model.diffusion_model.double_blocks.0' is Flux UNet"],
      "warnings": []
    }
    // ...
  ],
  "ambiguous": [
    {"source": "...", "reason": "Could be SD 1.5 inpaint or VAE", ...}
  ]
}
```

* `--dry-run` is the default; the CLI never moves unless `--apply` is set.
* On apply, files are moved atomically (`Path.replace`), skipping any
  destination that already exists with the same name + size.
* Ambiguous and low-confidence files are surfaced for the user to resolve
  manually (a one-line CLI hint is printed and the desktop bridge returns
  them so the UI can show a "Confirm placement" dialog).

CLI surface:

```bash
# Dry-run (default; no files moved)
dreamforge-cli inventory --organize

# Apply moves
dreamforge-cli inventory --organize --apply

# JSON output for the desktop UI
dreamforge-cli inventory --organize --json
```

---

## Structured generation errors

Every error currently emitted as `{"type": "error", "error": "..."}` is being
upgraded to:

```jsonc
{
  "type": "error",
  "code": "out_of_memory",          // stable string code
  "message": "Ran out of VRAM (...).",
  "suggestions": [
    "Switch the VRAM profile to 'low' in Settings.",
    "Lower resolution to 1024×1024 or smaller.",
    "Use a quantized variant (look for fp8 / Q4_K)."
  ],
  "details": { "free_gb": 0.3, "needed_gb_est": 11.5 }
}
```

Codes shipped now (others land in follow-up commits):

| Code                       | When                                                                                                                  |
|----------------------------|-----------------------------------------------------------------------------------------------------------------------|
| `missing_input_image`      | image-editing/Kontext/Qwen-Edit run without an input image                                                            |
| `invalid_input_image`      | input image path missing or unreadable                                                                                |
| `missing_model_dependencies` | required companion (CLIP / VAE) is missing for the chosen family                                                    |
| `model_not_found`          | chosen model not present on disk (after restructuring or new install)                                                 |
| `model_file_unreadable`    | safetensors header invalid / file truncated                                                                           |
| `unsupported_model_format` | non-image-model file dropped into a generation folder (e.g. a LoRA in `checkpoints/`)                                 |
| `out_of_memory`            | `torch.cuda.OutOfMemoryError` during sampling                                                                         |
| `disk_full`                | `OSError` ENOSPC while writing outputs                                                                                |
| `worker_crashed`           | GPU worker process died after `ready`                                                                                 |
| `generation_cancelled`     | user pressed Cancel                                                                                                   |

The UI side (`useDreamForge.ts`) maps these codes to user-facing strings and
optionally a CTA (e.g. "Lower VRAM profile" button).

---

## Preflight

Before sampling we run `preflight_generation(job, model)`:

* **Model exists**: `_paths.resolve_model_name(...)` → otherwise raise
  `model_not_found`.
* **Companions**: for Flux/HiDream/Qwen, check that the configured CLIPs and
  VAE exist (`backend/modules/path_manager` + `text_encoders`/`clip`).
* **Disk space**: `shutil.disk_usage(outputs_dir).free` must be ≥ 1 GB.
* **VRAM hint**: compare model size + family overhead to `torch.cuda.mem_get_info()`.
  Only a warning, not a hard error — the GPU profile still has the final say.
* **Input image**: validated by `_load_input_image()`.

---

## OOM resilience

* `dreamforge_desktop_worker.py` now exports
  `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` by default
  (overridable via env).
* `dreamforge_generation.py` wraps the sampling section in a
  `try/except torch.cuda.OutOfMemoryError` and emits the structured
  `out_of_memory` code with suggestions tailored to the active VRAM profile.
* After an OOM we call `torch.cuda.empty_cache()` and request the worker to
  recycle (`worker_recycle_recommended` flag in the event) so the next
  generation starts from a clean state.

---

## What just shipped

* `backend/dreamforge_errors.py` — one place that defines every error
  code, message, suggestions, and `from_exception` mapper.
* `backend/dreamforge_preflight.py` — model presence, safetensors header
  sanity, disk-free floor + soft warning, and a VRAM headroom estimator.
  Emits structured `warning` events for advisories and structured
  `error` events for hard stops, wired in **before** sampling starts.
* `backend/dreamforge_desktop_worker.py` — sets
  `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` before torch is
  imported; routes all worker-side failures through `from_exception` so
  every event the desktop sees carries `code`, `message`, `suggestions`,
  `details`, and `recoverable`.
* `backend/dreamforge_generation.py` — wraps the sampling loop in
  OOM/disk-full/exception handlers that emit the structured codes,
  call `torch.cuda.empty_cache()` after an OOM, and now also runs the
  preflight + forwards its warnings + errors.
* `apps/desktop/src-tauri/src/lib.rs` — forwards `code`, `message`,
  `suggestions`, `details`, `recoverable` on `generation-finished` and
  `worker-failed`; introduces a new `generation-warning` event for
  advisories.
* `apps/desktop/src/lib/errors.ts` — `describeError()` / `shortErrorLine()`
  map every backend code to a friendly title/message/suggestion bundle.
* `apps/desktop/src/hooks/useDreamForge.ts` exposes `lastError`,
  `warnings`, `dismissLastError`, `dismissWarning`, `dismissAllWarnings`
  for the UI to render banners / toasts / CTAs.
* `backend/dreamforge_desktop_bridge.py` — `classify_models` and
  `organize_models` JSON-RPC commands with UTF-8-safe stdout.
* Tests: `backend/tests/test_errors.py` (8) +
  `backend/tests/test_preflight.py` (6) +
  `backend/tests/test_model_classifier.py` (18) = **32 green**.

## What is still pending (roadmap)

These need follow-up commits but are scoped:

1. **Auto-download companion files** when the organizer detects a Flux/HiDream
   checkpoint that is missing CLIP/VAE. We have the `pathdb/*.json` catalog;
   the missing piece is a "download all dependencies" button.
2. **Inventory tab in the desktop UI** that lists every model by family with
   the classifier verdict and an "Organize models" button. (Backend ready;
   UI surface tracked as a follow-up.)
3. **Reactive OOM downgrade**: automatically retry once at a lower
   resolution / profile when the first attempt OOMs. Off by default until
   we are confident the retry path is hermetic.
4. **Diffusers-style single-file detection**: ckpt/pt/pth/bin files
   currently rely on filename heuristics; switching to a proper
   `torch.load(map_location='meta')` would lift them to high-confidence.
5. **UI surface for `lastError` + `warnings`** in `App.tsx` (banner +
   suggestion buttons). The hook now exposes both; rendering is the next
   small commit.

---

## How to verify

```bash
# 1. Classify everything currently on disk, no moves
python backend/dreamforge_cli_inventory.py --organize --json

# 2. Move misplaced files
python backend/dreamforge_cli_inventory.py --organize --apply

# 3. Smoke-test the entry points
python scripts/verify_entrypoints.py

# 4. Desktop bridge round-trip
python backend/dreamforge_desktop_bridge.py --once '{"cmd": "organize_models", "params": {}}'
```

The desktop UI exposes the same path under **Settings → Models → Organize**.

