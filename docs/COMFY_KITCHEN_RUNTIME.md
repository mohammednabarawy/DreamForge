# Managed ComfyUI and kitchen attention validation

Validated on 2026-08-31 in `D:/DreamForge` on an RTX 5060 Ti (16 GB).

## Runtime

- ComfyUI upgraded from v0.26.0 to stable **v0.34.0**, commit `12d5279438bfefc058a269eae805ceab6047777f`.
- comfy-kitchen **0.2.31**, comfy-aimdo **0.4.15**, Comfy frontend **1.49.6**, templates **0.11.48**, embedded docs **0.5.10**.
- Existing Python **3.10.9**, PyTorch **2.8.0+cu128**, torchvision **0.23.0+cu128**, torchaudio **2.8.0+cu128** retained. No model downloads or edits to the separate portable ComfyUI installation.
- App recipe and readiness pins were updated together. Existing model paths, custom nodes, and generation settings were retained.

Official references: [ComfyUI release](https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.34.0), [release requirements](https://github.com/Comfy-Org/ComfyUI/blob/v0.34.0/requirements.txt), [kitchen source](https://github.com/Comfy-Org/comfy-kitchen), [native attention selector](https://github.com/Comfy-Org/ComfyUI/blob/v0.34.0/comfy/ldm/modules/attention.py).

## Selection and recovery

DreamForge's shared launch policy uses the native `--use-ck-attention` flag in automatic mode only on NVIDIA CUDA after checking the installed core supports the flag and exercising the selected GPU's kitchen kernels. Masked/unmasked FP16 and, when supported, BF16 probes must produce finite results close to PyTorch SDPA. The probe does not consume the generation RNG and is cached per GPU for the worker session. Restart the app after runtime/package changes.

A kitchen attention execution failure gets at most one retry with PyTorch through the existing generation execution boundary. The prompt graph, seed, steps, resolution, and other sampling settings are unchanged. A visible progress event explains the fallback. PyTorch remains selected for the remainder of that worker session. Unrelated model-quantization failures are not treated as attention failures; existing OOM recovery is retained. Externally attached servers are not restarted by this recovery.

`DREAMFORGE_COMFY_ATTENTION=pytorch` forces SDPA; `kitchen`/`ck` requests kitchen with safe availability fallback; `off` keeps ComfyUI's ordinary selection. Existing explicit Sage/Flash preferences still work. The experimental `--fast` gate is separate and has not been enabled.

Automatic mode keeps SD 1.5/SDXL text-to-image jobs up to 768 x 768 equivalent pixel area on PyTorch through the native `ModelAttentionBackend` node: the matched small-image runs showed kitchen slower or tied. This does not restart ComfyUI, change sampling settings, rewrite custom-tool workflows, override an existing attention patch, or affect an explicit `kitchen` selection. Krea and larger jobs retain kitchen. The selected exception appears in progress and the generation settings.

ComfyUI's separate quantization dispatch disables kitchen's CUDA registry backend below CUDA 13; that warning remains. The native attention kernel calls were verified working independently. Full CUDA quantization acceleration is not claimed: upgrading Torch would also require compatible builds of the installed Torch-2.8-bound Sage/Nunchaku extensions. Their working versions were retained.

## Regression evidence

- Final full backend suite: **1,114 passed, 3 skipped** (absent carousel workflow fixtures), run from `backend/`.
- Desktop TypeScript/Vite production build passed; existing chunk-size and dynamic-import warnings remain.
- Required custom-node declarations are all present. Registered nodes increased from 1,524 to 1,632. The 17 removed upstream cloud nodes have no references in the 467 tracked app and saved-workflow files scanned. See `node-compatibility.json` for the exact list.
- `pip check` has the same pre-existing DirectML-versus-CUDA torch/torchvision conflicts as before; no new conflicts were introduced. Nunchaku's Z-Image loader and the optional LayerStyle clothes node were already unavailable and remain outside the live render coverage.

Evidence directory: `outputs/dreamforge/kitchen-validation/`. It contains the before-install package/requirements/pin snapshots, dependency resolution report, node schemas, complete test output, per-run results/manifests/images, and server logs.

## Live regression repair

A full masked edit exposed a pre-existing conditional `from PIL import Image` in `run_generation` that shadowed the module import and raised `UnboundLocalError` outside the cutout branch. Removing that redundant import fixes all sibling image paths. The rerun passed with automatic kitchen selection; all 222,169 pixels outside the mask plus a 12-pixel edge band were identical to the source. See `inpaint-integrity.json` and the preserved initial failure record.

## Performance and verification boundary

Matched runs use the same model, source, prompt, seed sequence, dimensions, steps, and sampling settings. Each attention mode gets one cold/warm-up generation plus two measured generations per model. End-to-end times include app/HTTP/decode/output work; they are observations from this machine, not a universal speed guarantee. Attention is quantized, so outputs can differ despite matching seeds. Small workloads can be slower even when long-sequence attention kernels are faster.

The kernel-only benchmark measured 2.91x and 4.27x speedups at 4,096 tokens (head dimensions 64 and 128); the 1,024-token unmasked D64 case was slower (0.66x). These figures are not whole-generation speedups. See `kernel-benchmark.json`.

Live results are recorded in `matrix-pytorch.json` and `matrix-kitchen.json`. The normal `dreamforge.bat` launcher runs `tauri dev` against these source files, so the changes apply on its next launch. No standalone packaged Tauri executable has been rebuilt or manually clicked through. Arbitrary third-party workflows, all video/audio models, AMD, Apple Silicon, and multi-GPU hardware have not been GPU-tested here.


### Measured warm end-to-end results

| Case | PyTorch median | Forced kitchen median | Observed change |
| --- | ---: | ---: | --- |
| SD 1.5, 512 x 512, 8 steps | 3.23 s | 3.73 s | 15.6% slower |
| SDXL Lightning, 768 x 768, 4 steps | 3.87 s | 3.93 s | 1.5% slower |
| Krea FP8 edit, 608 x 768, 8 steps | 27.69 s | 26.33 s | 4.9% faster |
| Krea ConvRot INT8 edit, 608 x 768, 8 steps | 39.80 s | 38.83 s | 2.4% faster |

These are two warm samples per case; small timing differences are not statistically established. Automatic mode retains native PyTorch attention for the small SD text-to-image cases, verified in six additional full app renders with the native model attention node present. The matched SD 1.5 and SDXL automatic-mode sample pixels were identical to the PyTorch baseline. Kitchen stays available explicitly and remains automatic for Krea/larger jobs.

Live execution passed for SD 1.5, SDXL, Krea FP8 edits, the supplied Krea ConvRot INT8 checkpoint with Identity Edit LoRA, masked editing with upload/crop/stitch, restyle, Flux Schnell, ControlNet, Ultimate SD Upscale, and outpaint. Generation paths used the real app pipeline; the last three additional branch tests used DreamForge's native graph builders and shared execution boundary. The initial low-denoise outpaint smoke left underfilled borders; a separate 20-step full-denoise render filled them, without changing any app defaults. Output previews were inspected; this is not a claim that every prompt or every model produces an ideal image.

Visuals: `attention-comparison.jpg`, `workflow-comparison.jpg`, `kitchen-outpaint-full.png`. See [Krea workflow review](KREA2_EDIT_WORKFLOW_REVIEW.md) for the original graph findings and reference mapping.
