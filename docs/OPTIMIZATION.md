# DreamForge — Optimization & Hardware Guide

DreamForge runs on a wide range of hardware: **24 GB NVIDIA workstations down to 4 GB GPUs, Apple Silicon, AMD/Intel via DirectML, and CPU-only systems**. This guide explains how the engine picks defaults, what to tune for each tier, and how to fix the most common failure modes.

The first time you start the desktop app, DreamForge picks a VRAM profile automatically. You only have to read this guide when you want to push past that default — or when something has gone wrong.

---

## 1. Hardware tiers at a glance

| Tier | Typical GPU | DreamForge default | Recommended models |
|------|-------------|--------------------|--------------------|
| **24 GB+** | RTX 3090 / 4090 / 5090, A6000, M3 Ultra | `--normalvram` (16 GB UI preset) | Anything: Flux fp16, SDXL 1.0, HiDream, Qwen Image, Z-Image |
| **14-16 GB** | RTX 4070 Ti / 4080 / 5070, M3 Max | `--normalvram` | Flux fp8 / GGUF Q8, SDXL, Z-Image Turbo |
| **8-12 GB** | RTX 3060 / 4060 / 4070, RX 7700 | `--lowvram --cpu-vae` (8 GB UI preset) | Flux fp8 or GGUF **Q5_K_S**, SDXL pruned, Z-Image Turbo |
| **6-7 GB** | RTX 3050 / 2060, RX 6600 | `--lowvram --cpu-vae` | Flux **GGUF Q4_K_S**, SD 1.5, SDXL Lightning Lite |
| **4-5 GB** | GTX 1650 / 1060, integrated | `--novram --cpu-vae` (5 GB UI preset) | SD 1.5, Z-Image Turbo, Flux GGUF Q3/Q2 |
| **No GPU / CPU only** | Modern CPUs (8c+) | `--cpu` (set `DREAMFORGE_CPU_ONLY=1`) | SD 1.5, SDXL Lightning, GGUF Q4 (slow but works) |
| **AMD / Intel on Windows** | RX 6000/7000, Arc A-series | `--directml` if torch-directml installed | SDXL, SD 1.5; Flux via GGUF |
| **Apple Silicon** | M1/M2/M3/M4 | `--normalvram` (MPS) | Z-Image Turbo, SDXL, Flux fp8 |

DreamForge's auto-detection lives in `backend/dreamforge_desktop_worker.py::_desktop_worker_argv()`. It reads GPU VRAM **and** system RAM, then picks the right combination of `--lowvram` / `--novram` / `--cpu-vae`. You can override it at any time via the **VRAM profile** dropdown in the Inspector, or the env vars below.

---

## 2. Why "I have a beefy GPU but it still crashes"

The most common Windows failure is **`OSError: The paging file is too small (os error 1455)`**. This is **not** a GPU error — it is Windows refusing to commit enough virtual memory while a checkpoint is being parsed into system RAM.

Typical peak system-RAM requirements when DreamForge loads a model:

| Model | File size | Peak system RAM during load |
|-------|-----------|------------------------------|
| SD 1.5 (pruned) | ~2 GB | ~4 GB |
| SDXL 1.0 | ~6.5 GB | ~10 GB |
| Flux fp8 schnell/dev | ~17 GB | ~25-27 GB |
| Flux fp16 | ~23 GB | ~36 GB |
| HiDream I1 / Flux 2 Klein 9B | ~18 GB | ~28 GB |

If your **free** system RAM at the moment of generation is below "peak load", Windows reaches into the page file. If the page file is too small / fragmented / on a full drive, you get error 1455.

**DreamForge now runs a preflight that warns about this before the load starts** (`low_system_ram` event). The warning lists exact suggestions for your situation.

On startup, DreamForge also enables **comfy-aimdo** mmap loading when that package is installed (bundled with the embedded Python). That avoids reading the entire Flux fp8 file into commit space at once — the difference between a ~25 GB spike and mapping the file on disk. You should see `Large-model mmap loader enabled (comfy-aimdo)` in boot logs when it is active.

### Quick fixes

1. **Free RAM** — Close browsers, Discord, games, Photoshop, etc.
2. **Increase the Windows paging file:**
   - `Win+R` → `sysdm.cpl` → Advanced → Performance Settings → Advanced → **Virtual memory** → Change.
   - Uncheck *Automatically manage*.
   - Pick a drive with **plenty of free space** (avoid an almost-full `C:`).
   - Custom size: **Initial = total RAM in MB**, **Maximum = 2x total RAM in MB** (e.g., 32 GB RAM → 32768 / 65536).
   - OK → **Reboot**.
3. **Use a smaller / quantized variant** — see Section 3.
4. **Switch to the 8 GB or 5 GB profile** in the Inspector. That passes `--cpu-vae` and reduces peak RAM.

---

## 3. Pick the right model variant for your VRAM

Full-precision weights are wasted on most consumer GPUs. Quantized variants give nearly identical quality with a fraction of the memory.

| You have | Use this for Flux | Use this for SDXL |
|----------|-------------------|--------------------|
| 24 GB+ VRAM | `flux1-dev` fp16 | SDXL 1.0 base + refiner |
| 12-16 GB VRAM | `flux1-dev-fp8` or GGUF Q8 | SDXL 1.0 |
| 8-10 GB VRAM | **GGUF Q5_K_S** (city96) | SDXL pruned |
| 6-7 GB VRAM | GGUF Q4_K_S | SDXL Lightning Lite, SD 1.5 |
| 4-5 GB VRAM | GGUF Q3 / Q2 | SD 1.5 only |

**GGUF downloads:**
- Flux Schnell: <https://huggingface.co/city96/FLUX.1-schnell-gguf>
- Flux Dev: <https://huggingface.co/city96/FLUX.1-dev-gguf>
- SD 3.5 Large: <https://huggingface.co/city96/stable-diffusion-3.5-large-gguf>

Place `.gguf` UNet weights under `backend/models/diffusion_models/`, the matching CLIP/T5 under `backend/models/text_encoders/`, and the VAE under `backend/models/vae/`. Use **Settings → Organize models** to verify placement.

> **Important:** Flux UNet-only weights (fp8 *and* GGUF) belong in `diffusion_models/`, **not** `checkpoints/`. The checkpoint path triggers a heavier loader that spikes RAM. The organizer moves them automatically.

---

## 4. Environment variables (advanced)

DreamForge reads these env vars at GPU-worker startup:

| Variable | Effect |
|----------|--------|
| `DREAMFORGE_DESKTOP_VRAM_MODE` | Force a profile: `gpu-only`, `high`, `normal`, `low`, `no`, `cpu`. The Inspector dropdown also writes this. |
| `DREAMFORGE_CPU_ONLY=1` | Force CPU mode (no CUDA / MPS / DirectML), useful for benchmarking and headless servers without a GPU. |
| `DREAMFORGE_NO_CPU_VAE=1` | Disable the auto `--cpu-vae` flag on 6-8 GB cards (skip if you already have plenty of headroom). |
| `DREAMFORGE_EXTRA_WORKER_ARGS` | Pass arbitrary extra Comfy worker flags, e.g. `--cache-none --reserve-vram 1.5`. |
| `PYTORCH_CUDA_ALLOC_CONF` | Pre-set to `expandable_segments:True` for less GPU fragmentation. Override to tune. |
| `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` | Already set by DreamForge; keeps generation offline once models are installed. |

Useful Comfy flags to pass via `DREAMFORGE_EXTRA_WORKER_ARGS`:

- `--cache-none` — Don't cache intermediate node results. Slower for chained runs, **much** lower system-RAM use.
- `--cache-classic` — Old aggressive caching, fastest second run but RAM-hungry.
- `--reserve-vram 1` — Reserve 1 GB of VRAM for the OS / other apps. Stabilizes systems running a second monitor / browser.
- `--force-fp16` — Force fp16 everywhere; saves VRAM on 6-8 GB cards.
- `--bf16-unet` — Run the UNet in bf16; usually a touch faster than fp16 on Ampere+.

---

## 5. Profile by scenario

### Scenario A — Tight system RAM (≤ 16 GB), capable GPU

Symptoms: Loading any large model triggers error 1455 or extremely long pauses. GPU is fine.

Recipe:
1. Increase the page file as in Section 2.
2. Set **8 GB** VRAM profile in the Inspector (gives `--lowvram --cpu-vae`).
3. Prefer **GGUF Q5_K_S** for Flux instead of fp8 (cuts load peak nearly in half).
4. Add `--cache-none` via `DREAMFORGE_EXTRA_WORKER_ARGS` so DreamForge doesn't hold extra tensors between runs.

### Scenario B — Old / low-end GPU (4-6 GB VRAM)

1. Set **5 GB** profile in the Inspector (`--novram --cpu-vae`).
2. Use Flux **GGUF Q3/Q2** or SD 1.5.
3. Render at 512x512 or 640x640; upscale separately with the Upscale pipeline.
4. Keep batch size at 1.

### Scenario C — CPU only

1. Set `DREAMFORGE_CPU_ONLY=1` in your environment (or pick **CPU** in the Inspector).
2. Use SD 1.5 or Z-Image Turbo for fastest CPU generation.
3. Expect 5-30 minutes per 512x512 image on a modern desktop CPU. This is **functional but slow** — use it for offline batch overnight jobs, not interactive iteration.

### Scenario D — AMD / Intel GPU on Windows

1. `pip install torch-directml` into the embedded Python (`python_embeded/python.exe -m pip install torch-directml`).
2. Restart the desktop app. Autodetect will pick `--directml` automatically when DirectML is available and CUDA is not.
3. AMD/Intel still benefit from `--cpu-vae` and `--force-fp16` on ≤ 12 GB cards.

### Scenario E — Apple Silicon (M1/M2/M3/M4)

1. DreamForge auto-detects MPS; no changes needed.
2. Z-Image Turbo and SDXL are the most reliable families.
3. Flux works but is slower than CUDA at the same VRAM tier.

---

## 6. What the preflight tells you

DreamForge emits structured warnings before sampling. Look for these in the desktop app's status panel or the worker log:

| Code | Meaning | What to do |
|------|---------|------------|
| `low_system_ram` | Model file × 1.6 > available RAM | Close apps, increase page file, switch variant |
| `vram_headroom_low` | Estimated VRAM > free VRAM | Lower the resolution or VRAM profile |
| `low_disk_space` | < 2 GB free on output drive | Free space or move `outputs/` |
| `virtual_memory_low` | Windows error 1455 caught | Increase page file, free RAM, restart engine |
| `missing_model_dependencies` | CLIP / T5 / VAE missing for the picked model | Run **Organize models** or download the companions |

A warning never blocks generation — but ignoring one often leads to a hard error a few seconds later.

---

## 7. Reporting hardware issues

If your hardware works in Fooocus / RuinedFooocus / SD.Next but fails in DreamForge, please open an issue at <https://github.com/mohammednabarawy/DreamForge/issues> with:

- GPU make/model and VRAM, total RAM, OS.
- The exact model you're trying to load and where it sits under `backend/models/`.
- The full output of `dreamforge-cli.bat --inventory` (or the Inventory panel in the desktop app).
- The structured preflight events from the log (search for `"type": "warning"` lines).

This makes it possible to ship a fix or a new profile that helps everyone on similar hardware.
