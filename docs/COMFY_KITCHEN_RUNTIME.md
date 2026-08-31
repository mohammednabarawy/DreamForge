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

## Follow-up reliability improvements

Archive updates now validate a staged download before replacing installed files. Existing ComfyUI models, custom nodes, inputs, outputs, user files, and extra model path configuration are preserved. Replaced files are backed up under the engine parent directory's `.dreamforge-backups`; caught replacement failures restore prior files. Git updates refuse tracked local edits and retain `refs/dreamforge/previous`. This is file replacement rollback, not a power-loss transaction or a complete Python-environment rollback.

Dependency installs constrain the installed Torch, torchvision, torchaudio, Sage, Nunchaku, xformers and Triton versions. The shared pip installer resolves a dry run first; Manager child installers inherit the constraints. Before/after import and GPU probes plus `pip check` reject new regressions without marking setup ready. Existing dependency conflicts remain reported separately. Non-GPU dependencies are still installed in place.

Edit resource checks now follow the selected model. Krea Edit checks and offers the pinned Identity Edit v1.2 LoRA and its custom node pack; selecting another edit family does not request Krea assets. The desktop test command and CI now run the existing readiness tests plus edit routing and boot diagnostic regressions.

### Measured attention selection

Settings > Hardware > Optimize attention runs matched full generations for the selected model and size: one warm-up and five measured samples per backend. Seeds differ across samples and match between backends, avoiding cached sampler results. All outputs and the requested native backend must validate; forced benchmark runs do not retry with another attention or OOM policy. Kitchen needs a median win above 5%; otherwise PyTorch wins. The cached choice is keyed by GPU, driver, runtime package versions/core file timestamps, model file identity, mode and dimensions. Changed runtime/model keys stop using the old result. Manual backend choices, custom-tool graphs, existing attention patches and generation settings remain authoritative. Edit benchmarking currently supports Krea 2.

The live optimizer check rendered three measured samples plus a warm-up per backend for SD 1.5 at 512 x 512, four steps: PyTorch median **2.8489 s**, Kitchen **3.2537 s**. It selected PyTorch; a subsequent automatic run confirmed that selection. These short measurements do not establish an overall speedup or image-quality equivalence.

### Worker startup repair

The reported allocator warning was not an exception: the worker event log subsequently contained a Kitchen-enabled `ready` event. The GUI had used the indented source line printed by the warning as its failure message. Boot diagnostics now retain the real boot cause, and a confirmed healthy engine clears a stale boot failure.

DreamForge no longer sets `expandable_segments:True` by default on Windows (the installed Torch build does not support it); explicit user allocator configuration remains untouched. The Kitchen kernel check now runs in a hidden disposable Python process with a **60-second timeout**. A timeout or native crash falls back to the standard attention policy instead of blocking or terminating the worker. This retains kernel correctness checks without unbounded native/JIT work in the IPC worker.

The isolated GPU probe passed in **7.98 s**. The complete worker attachment, ready event and graceful shutdown passed in **13.42 s**, without the allocator warning or stopping the user's existing server. This is a real worker boot against a running managed ComfyUI, not a fresh ComfyUI cold-start timing. See the [upstream allocator tests](https://github.com/pytorch/pytorch/blob/main/test/test_cuda_expandable_segments.py) and [Kitchen source](https://github.com/Comfy-Org/comfy-kitchen).

Final follow-up checks: **1,124 backend tests passed, 3 skipped** (absent carousel fixtures); **12 desktop tests passed**; TypeScript/Vite production build passed with existing bundle warnings. The production npm audit reported zero vulnerabilities.

### Dynamic VRAM allocation recovery

A final live render exposed `CLIPTextEncode: VBAR allocation failed` in comfy-aimdo despite the worker being ready. The common generation retry boundary now recognizes this specific allocation failure and retries once with legacy VRAM handling for the worker session, without changing the prompt graph, seed, dimensions or sampling settings. The shared launcher now passes `--disable-dynamic-vram` when its existing override is set; merely selecting `--lowvram` did not disable Dynamic VRAM in the new runtime. Both ordinary OOM and VBAR recovery leave externally attached servers alone. Forced attention benchmarks still do not retry under a different memory policy, and changing the dynamic-VRAM/fast policy invalidates old attention measurements.

The recovery policy was GPU-tested in an isolated temporary managed server: Kitchen remained enabled alongside `--disable-dynamic-vram --lowvram --reserve-vram 3`. A warm-up and a distinct-seed measured render both completed; the measured full app call took **4.697 s**. The finished 512 x 512 sample was visually inspected. The original user's ComfyUI process was left running. Automatic VBAR error-to-restart control flow was verified by regression test; the real render verified the resulting legacy configuration. Restart the existing GPU worker once to load all updated launcher code.
