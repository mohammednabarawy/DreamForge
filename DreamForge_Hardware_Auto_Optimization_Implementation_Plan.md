# DreamForge Hardware Auto-Detection and Optimization Plan

Status: implemented in the managed ComfyUI path; unsupported hardware validation remains explicit
Date: 2026-08-03

## Outcome

DreamForge should detect the actual compute backend before starting its managed ComfyUI worker, choose a safe hardware policy, recommend models that fit that policy, and adapt after real generation telemetry without silently changing the user's prompt, seed, model, or requested quality profile.

The duplicated `NVIDIA 8 GB` entry in the request is represented once.

## Evidence used

- ComfyUI supports NVIDIA, AMD, Apple Silicon, Intel, and CPU, but each requires the matching PyTorch/runtime build. CPU mode uses `--cpu` and is expected to be slow.
- ComfyUI defines `--lowvram`, `--novram`, `--reserve-vram`, Dynamic VRAM, async offload, and attention flags. Its `--fast` features are explicitly experimental and may reduce quality or crash, so DreamForge must not enable them globally without a capability and benchmark gate.
- ComfyUI's current AMD guidance prefers ROCm. Windows AMD support is experimental and limited to recent RDNA generations; DirectML is a fallback, not a preferred automatic backend.
- ComfyUI recommends MPS for Apple Silicon. PyTorch exposes MPS allocator high/low watermarks and CPU fallback controls; these are safer controls for unified memory than forcing every 16/24 GB Mac into `--highvram`.

Primary references:

- https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/cli_args.py
- https://github.com/Comfy-Org/ComfyUI/blob/master/README.md
- https://docs.comfy.org/installation/system_requirements
- https://docs.comfy.org/installation/desktop/macos
- https://docs.pytorch.org/docs/stable/mps_environment_variables.html

## Current DreamForge findings

| Severity | Finding | Evidence in the repository | Impact |
| --- | --- | --- | --- |
| High | Hardware classes are too coarse | `dreamforge_vram_profiles.py` only has discrete 5/8/16 GB and MPS 4/8/16/24 GB profiles | 12/24/32 GB cards and 32 GB Macs are routed through the wrong policy |
| High | Vendor/backend data is discarded after detection | `gpu_telemetry()` returns CUDA/MPS booleans and memory but not vendor, backend, GPU architecture, driver, or Torch build | NVIDIA CUDA, AMD ROCm, and an unsupported CUDA-like device can receive the same tuning |
| High | AMD fallback detection is incomplete | `dreamforge_gpu_detect.py` has NVIDIA `nvidia-smi` fallback but no Windows CIM, Linux `rocminfo`, `lspci`, or DRM sysfs path | AMD can be misreported as CPU-only when the installed Torch build cannot initialize it |
| Medium | Detection thresholds are duplicated | Python, Rust, and TypeScript independently resolve Auto | Thresholds can drift and produce a UI profile different from the worker profile |
| Medium | `--fast fp16_accumulation` is enabled too broadly | `dreamforge_comfy_launch.py` defaults it without checking vendor or GPU architecture | Older NVIDIA and non-NVIDIA paths can get an unvalidated optimization |
| Medium | MPS 16/24 GB currently forces `--highvram` | `comfy_launch_extra_args()` | Keeping models resident can starve macOS because GPU and OS share unified memory |
| Medium | Model-fit estimates are architecture-only | `dreamforge_compute_profile.py` does not include resolution, batch, text encoder, VAE, ControlNet, LoRA, or backend overhead | “Fits” can still OOM on a real workflow |
| Low | The UI cannot explain Auto | Settings shows a profile selector but not the detected backend, active launch flags, confidence, or fallback reason | Users cannot verify or safely override optimization |

## Target hardware classification

Keep vendor/backend separate from memory tier. Do not encode everything into one ambiguous `8gb` string.

| Hardware class | Backend | Memory tier |
| --- | --- | --- |
| CPU-only | CPU | system RAM aware |
| NVIDIA 4–6 GB | CUDA | 5 GB |
| NVIDIA 8 GB | CUDA | 8 GB |
| NVIDIA 12 GB | CUDA | 12 GB |
| NVIDIA 16 GB | CUDA | 16 GB |
| NVIDIA 24 GB+ | CUDA | 24 GB |
| NVIDIA 32 GB+ | CUDA | 32 GB |
| AMD 4–8 GB | ROCm or experimental Windows ROCm | 5/8 GB |
| AMD 8–12 GB | ROCm or experimental Windows ROCm | 8/12 GB |
| AMD 16 GB+ | supported backend required | 16 GB |
| AMD ROCm Linux 16 GB+ | ROCm | 16/24/32 GB from measured VRAM |
| Apple Silicon 8 GB | MPS | 8 GB unified |
| Apple Silicon 16 GB | MPS | 16 GB unified |
| Apple Silicon 24 GB+ | MPS | 24 GB unified |
| Apple Silicon 32 GB+ | MPS | 32 GB unified |

Canonical hardware result:

```text
vendor, backend, os, device_name, device_count
gpu_architecture, compute_capability
total_vram_mb, free_vram_mb
total_ram_mb, available_ram_mb
torch_version, cuda_version, hip_version, mps_available
support_level: supported | experimental | fallback | unavailable
profile_id, detection_sources, confidence, warnings
```

## Initial ComfyUI policy matrix

These are safe starting candidates, not final “best” settings. Phase 5 benchmarks promote or demote them.

| Hardware | Initial managed ComfyUI policy | Generation safety ceiling |
| --- | --- | --- |
| CPU-only | `--cpu`; no accelerated attention or `--fast` | batch 1, 512–640 px default, disable live preview by default, prefer SD1.5 |
| NVIDIA 4–6 GB | Dynamic VRAM when supported with 0.6 GB reserve; otherwise `--lowvram --reserve-vram 0.75` | batch 1, 512–768 px, VAE tiling, SD1.5 or compact quantized model |
| NVIDIA 8 GB | Dynamic VRAM + 0.8 GB reserve; legacy `--lowvram --reserve-vram 1` | batch 1, 768–1024 px, VAE tiling for modern models |
| NVIDIA 12 GB | Dynamic VRAM + 1 GB reserve; legacy low-VRAM on Windows and default smart memory on Linux | batch 1 at 1024 px; batch 2 only after fit check |
| NVIDIA 16 GB | Dynamic VRAM + 1.5 GB Windows reserve / 1 GB Linux reserve | 1024–1344 px; modern FP8/FP4 models; batch remains family-aware |
| NVIDIA 24 GB+ | Dynamic/default smart memory + 1–1.25 GB reserve; no forced `--highvram` | 1024–1536 px; larger models and batch 2 when estimated fit passes |
| NVIDIA 32 GB+ | Dynamic/default smart memory + 1.5 GB reserve | full local model stacks; batch and resolution still estimated per workflow |
| AMD 4–8 GB ROCm | `--lowvram`, 0.5–0.75 GB reserve; stock smart memory; no NVIDIA-only fast flags | batch 1, 512–768 px, SD1.5 first |
| AMD 8–12 GB ROCm | `--lowvram`, 0.75–1 GB reserve; PyTorch attention only when the detected ROCm/GFX pair passes smoke tests | batch 1, 768–1024 px, SDXL preferred |
| AMD 16 GB+ | default smart memory with 1 GB reserve; backend-specific attention gate | 1024 px default; quantized transformer models only when validated |
| AMD ROCm Linux 16 GB+ | same memory policy; optionally benchmark AOTriton and TunableOp per GFX architecture | 1024–1344 px after benchmark |
| AMD Windows experimental | only select native experimental PyTorch for supported RDNA 3/3.5/4 identifiers; never silently fall back to DirectML | conservative tier; unsupported cards get an explicit CPU fallback message |
| Apple Silicon 8 GB | MPS, default/low-memory behavior, MPS allocator limit, CPU fallback for unsupported ops; never `--highvram` | batch 1, 512–768 px, SD1.5 |
| Apple Silicon 16 GB | MPS default smart memory; allocator high watermark below system exhaustion; no `--highvram` | batch 1, 768–1024 px, SDXL |
| Apple Silicon 24 GB+ | MPS default smart memory; reserve OS headroom through allocator policy | batch 1 at 1024 px; Flux Schnell only after benchmark |
| Apple Silicon 32 GB+ | MPS default smart memory with measured OS headroom | 1024 px modern models; large edit stacks require fit check |

Rules shared by every tier:

1. Sampler, scheduler, CFG, and steps remain model-family recipe settings, not hardware settings.
2. Hardware may constrain maximum resolution, batch size, preview frequency, VAE tiling, and offload policy.
3. Never enable `--fast` globally. Gate each feature by backend, GPU architecture, Torch version, model family, and a passing quality/performance benchmark.
4. Never auto-select DirectML when a supported backend is unavailable. Explain the fallback and let the user choose CPU or install a compatible runtime.
5. An OOM retry may change only memory controls, batch, or resolution with a visible notice; prompt/model/seed/style must remain unchanged.

## Implementation phases

### Phase 1 — Canonical detection contract

- Extend `dreamforge_gpu_detect.py` to detect hardware before and after Torch initialization.
- Windows: use `nvidia-smi` plus CIM/`Win32_VideoController`; distinguish NVIDIA, AMD, and Intel.
- Linux: use Torch first, then `nvidia-smi`, `rocminfo`, `/sys/class/drm`, and `lspci` fallbacks.
- macOS: use MPS plus `system_profiler` and total/available unified memory.
- Detect NVIDIA compute capability, AMD GFX architecture, Torch CUDA/HIP versions, free VRAM, total RAM, and available RAM.
- Return detection sources and confidence so partial detection is not presented as certainty.
- Make backend Python authoritative. Rust and TypeScript consume the resolved profile instead of independently recomputing thresholds.

Acceptance:

- Deterministic fixture tests for every requested hardware class.
- Unknown/unsupported AMD never becomes NVIDIA CUDA or a silent CPU profile.
- Multi-GPU systems report every device and select a default using usable VRAM and backend support, with manual override retained.

### Phase 2 — Complete profiles and migration

- Add discrete 12/24/32 GB tiers and MPS 32 GB.
- Preserve existing profile IDs as accepted aliases and migrate saved settings without data loss.
- Separate `hardware_backend` from `memory_tier` in `ComputeProfile`.
- Replace duplicated Python/Rust/TypeScript threshold tables with backend-resolved values and a shared UI display contract.
- Add profile lowering order for OOM recovery across every vendor/tier.

Acceptance:

- Existing `auto`, `5gb`, `8gb`, `16gb`, and MPS settings still load.
- Auto resolves identically in backend status, Tauri state, Settings, manifests, and recipe export.

### Phase 3 — Vendor-aware ComfyUI launch policy

- Refactor `dreamforge_comfy_launch.py` around the canonical hardware result.
- NVIDIA: keep Dynamic VRAM when ComfyUI/Torch supports it; use legacy low-VRAM only when necessary; gate Sage/Flash and fp16 accumulation by actual capability.
- AMD ROCm: identify `torch.version.hip`; use ROCm-safe attention; expose AOTriton/TunableOp only after architecture-specific smoke tests.
- AMD Windows: select a native experimental runtime only for supported RDNA architectures; keep DirectML explicit and marked fallback.
- Apple: remove automatic `--highvram`; set conservative MPS allocator limits and CPU fallback environment; keep an advanced manual override.
- CPU: clean `--cpu` path with preview throttling and RAM/disk-space preflight.
- Store the exact effective flags and environment in engine status and generation manifests.

Acceptance:

- Table-driven tests assert exact flags and environment for every requested class.
- Unsupported flags never reach another vendor.
- Engine restart applies the new policy exactly once and reports it visibly.

### Phase 4 — Workflow-aware fit and model routing

- Extend VRAM estimation to include model file/quantization, text encoders, VAE, ControlNet/IP-Adapter, LoRAs, resolution, batch, preview decode, and backend overhead.
- Use the installed model library as the candidate pool; do not recommend a missing model.
- Establish per-tier starters from the reviewed library:
  - CPU/4–6 GB: SD1.5 (`majicmixRealistic_v7` or `dreamshaper_8`).
  - 8 GB: SDXL Lightning (`epicrealismXL...Lightning`) with compact modern models as benchmarked alternatives.
  - 12 GB: quantized Flux Dev (`svdq-fp4...flux.1-dev`) after compatibility validation.
  - NVIDIA 16 GB: Ideogram 4 or HiDream O1 by task.
  - NVIDIA 24/32 GB: Flux Dev generation and Qwen/Flux Kontext editing by measured fit.
  - AMD: prefer SD1.5/SDXL FP16 until each quantized transformer path is proven on the detected backend.
  - Apple: SD1.5/SDXL first; promote Flux Schnell on 24/32 GB only after MPS benchmarks.
- Keep task-aware model choice: text/layout, photorealism, editing, and identity are separate rankings.

Acceptance:

- Recommendation explains model, backend, estimated peak memory, expected resolution, and any missing companion.
- “Recommended” means the complete workflow fits, not only the main checkpoint file.

### Phase 5 — Reproducible hardware benchmark harness

- Add a CLI benchmark that runs without changing user settings.
- Fixed scenarios: SD1.5 baseline, SDXL baseline, and one modern transformer appropriate to the tier.
- Fixed prompts/seeds/resolutions with one warm-up and at least five measured runs per scenario.
- Record boot time, model-load time, time to first preview, generation time, images/minute, peak VRAM, peak RAM, offload volume, thermals when available, OOM/recovery events, and output validation.
- Compare candidate attention/fast flags against the safe baseline. Promote only when median speed improves materially and output validation/visual QA shows no quality regression.
- Store results keyed by hardware fingerprint, driver, OS, Torch, ComfyUI version, model hash, and policy version.

Initial gates:

- 10 sequential generations without OOM or worker death.
- 100% nonblank, correctly sized outputs.
- No automatic fast flag without a passing same-seed quality comparison.
- Report median and p95; do not declare a winner from one run.

### Phase 6 — Adaptive runtime recovery

- On the first OOM, unload models and retry once with the next safer memory policy.
- Preserve prompt, model, seed, sampler, steps, CFG, references, and styles.
- If resolution or batch must change, require a visible confirmation unless the user enabled automatic safe retry.
- Persist successful policy hints per hardware fingerprint and model family, not globally.
- Invalidate learned hints when driver, Torch, ComfyUI, GPU, or model hash changes.

Acceptance:

- No infinite restart/retry loop.
- A failed aggressive policy cannot become the next startup default.
- Recovery reason and changed settings appear in status, logs, and manifest.

### Phase 7 — Settings and diagnostics UI

- Show Detected hardware, backend, support level, memory tier, active launch policy, and detection confidence.
- Keep `Auto` as default and retain manual override plus Reset to detected.
- Add “Run hardware benchmark” as an explicit user action; do not generate benchmark images silently.
- Display unsupported/experimental AMD guidance with exact detected GFX/RDNA information.
- Show why a model is recommended or blocked on this device.

Acceptance:

- Normal users see one Auto summary; advanced details remain expandable.
- Compact-window QA and keyboard/screen-reader basics pass.

### Phase 8 — Packaging and CI matrix

- Build/select platform-specific runtimes: Windows NVIDIA CUDA, Windows AMD experimental where supported, Linux CUDA, Linux ROCm, macOS arm64 MPS, and CPU fallback.
- Validate wheel/runtime compatibility before download or engine start.
- Add unit fixtures for every hardware class and real-hardware smoke jobs where runners exist.
- Publish a support matrix distinguishing supported, experimental, and fallback paths.

Acceptance:

- Clean installation selects the correct runtime without first importing an incompatible Torch build.
- Every release records tested driver/Torch/ComfyUI versions and known limitations.

## Planned file surface

- `backend/dreamforge_gpu_detect.py`
- `backend/dreamforge_vram_profiles.py`
- `backend/dreamforge_compute_profile.py`
- `backend/dreamforge_comfy_launch.py`
- `backend/dreamforge_progress.py`
- `backend/dreamforge_desktop_worker.py`
- `apps/desktop/src-tauri/src/lib.rs`
- `apps/desktop/src/lib/vramProfiles.ts`
- `apps/desktop/src/lib/tauri-api.ts`
- Settings/engine-status UI components
- Focused detection, launch-policy, routing, migration, and benchmark tests

Reuse the existing profile, launch, telemetry, and model-ranking modules. Do not introduce a second hardware framework.

## Review decisions requested

1. AMD Windows: support only the upstream experimental RDNA 3/3.5/4 native runtime initially, with CPU fallback for older AMD cards. Recommended.
2. Safe OOM retry: automatically retry memory-only changes, but ask before reducing resolution or batch. Recommended.
3. Benchmark: explicit first-run/user-triggered benchmark, then passive learning from normal generations. Recommended.
4. Fast flags: disabled unless the hardware/model combination passes the benchmark gate. Recommended.

## Definition of done

- Every requested hardware class resolves to the correct vendor, backend, memory tier, launch policy, and starter-model shortlist.
- The UI and worker report the same effective profile.
- Vendor-incompatible flags cannot be emitted.
- Real hardware evidence exists for each class claimed as supported; untested classes remain experimental.
- Ten-run stability, output validation, median/p95 timing, peak-memory capture, and OOM recovery pass for each supported class.
- Manual control remains available, and DreamForge never silently changes creative parameters.

## Implementation record (2026-08-02)

- Phases 1–3 are implemented: canonical Torch/nvidia-smi detection, vendor/backend/profile telemetry, 12/24/32 GB tiers, MPS 32 GB, ROCm-safe launch flags, MPS CPU fallback, and NVIDIA-only fast defaults.

## Implementation record (2026-08-03)

- Direct CLI launches now initialize the same VRAM and runtime policy as the desktop worker before ComfyUI starts.
- GPU detection enumerates every Torch CUDA adapter, every NVIDIA SMI row, and every Windows CIM controller; selection prefers usable supported backend and free/total memory instead of adapter 0.
- Workflow fit estimation keeps model weights resident, scales only activation working-set with resolution/batch, retains unknown-workflow overhead, and accepts VAE/text-encoder/ControlNet/IP-Adapter/LoRA/preview companions.
- Automatic `--fast` is disabled by default and requires an explicit benchmark gate plus CUDA capability; manual opt-in remains available.
- OOM retry lowers the VRAM tier, disables fast flags, restarts managed ComfyUI with the safer launch policy, and persists a device/model-family hint after success.
- `--run-generation` now re-executes through the embedded runtime when needed, performs a warm-up plus configurable measured runs, validates output images, records VRAM and median/p95 timing, and is also exposed as an explicit Settings action.
- Settings now shows architecture, confidence, warnings, fallback reason, active policy, Reset to detected, and Run hardware benchmark. See `DreamForge_Hardware_Support_Matrix.md` for the platform/runtime matrix.
- Current evidence: NVIDIA RTX 5060 Ti embedded-runtime smoke succeeded (warm-up + one measured run, nonblank 512×512 output); deterministic fixtures cover all requested classes. Ten-run and non-NVIDIA real-host evidence still requires those machines/CI runners.
- Phase 4 is implemented for resolution/batch/workflow-overhead-aware fit estimates and the installed-library recommendation path.
- Phase 5 has a deterministic policy benchmark CLI at `backend/dreamforge_hardware_benchmark.py`; real hardware runs are intentionally not faked. The current host smoke generation completed successfully on an NVIDIA GeForce RTX 5060 Ti (15.93 GB, CUDA, `nvidia_16gb`) with a valid 512×512 image and manifest.
- Phase 6 keeps the existing bounded Comfy recovery/lower-profile flow and now persists the effective hardware policy in generation manifests.
- Phase 7 exposes detected hardware, backend, support level, class, and exact launch arguments in Settings.
- Phase 8 keeps runtime selection within the existing managed ComfyUI installation and adds fixture coverage for all requested classes. AMD, Apple, and CPU classes are policy-tested here but not claimed as live hardware-tested on this NVIDIA host.

Verification recorded for this implementation:

- `python -m pytest -p no:cacheprovider -q`: 1098 passed, 3 skipped (the skips are optional user workflow fixtures absent from this checkout).
- `npm run build`: production Vite/TypeScript build passed.
- `cargo check`: passed.
- Live managed-Comfy smoke: NVIDIA GeForce RTX 5060 Ti, 15.93 GB, CUDA; two valid 512×512 RGB generations completed and the final manifest recorded the effective policy.
