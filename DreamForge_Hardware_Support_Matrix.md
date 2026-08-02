# DreamForge hardware support matrix

DreamForge keeps ComfyUI as the execution backend and selects the safest runtime policy from the detected adapter. `auto` is always the default; the explicit profile remains available for constrained or shared-memory systems.

| Hardware | Backend | Auto profile | Runtime policy | Status |
|---|---|---|---|---|
| CPU-only | CPU | `no_gpu` | `--cpu`, conservative steps/resolution | supported fallback |
| NVIDIA 4–6 GB | CUDA | `5gb` | low-VRAM streaming | supported, tight |
| NVIDIA 8 GB | CUDA | `8gb` | low-VRAM streaming | supported |
| NVIDIA 12 GB | CUDA | `12gb` | low-VRAM/reserve headroom | supported |
| NVIDIA 16 GB | CUDA | `16gb` | Dynamic VRAM when PyTorch ≥2.8, otherwise low-VRAM on Windows | supported |
| NVIDIA 24 GB+ | CUDA | `24gb` | high-VRAM or Dynamic VRAM | supported |
| NVIDIA 32 GB+ | CUDA | `32gb` | high-VRAM/Dynamic VRAM | supported |
| AMD 4–8 GB | ROCm | `5gb`/`8gb` | low-VRAM + PyTorch cross attention | experimental |
| AMD 8–12 GB | ROCm | `8gb`/`12gb` | low-VRAM + reserve | experimental |
| AMD 16 GB+ | ROCm | `16gb` | low-VRAM + reserve | experimental |
| AMD ROCm Linux 16 GB+ | ROCm | `16gb` | ROCm Linux path + cross attention | experimental, preferred AMD target |
| Apple Silicon 8 GB | MPS | `mps_8gb` | unified-memory reserve | supported with MPS limits |
| Apple Silicon 16 GB | MPS | `mps_16gb` | unified-memory reserve | supported with MPS limits |
| Apple Silicon 24 GB+ | MPS | `mps_24gb` | unified-memory reserve | supported with MPS limits |
| Apple Silicon 32 GB+ | MPS | `mps_32gb` | unified-memory reserve | supported with MPS limits |

The detector evaluates every visible adapter and selects the best supported candidate by vendor priority and available memory. The Settings panel exposes confidence, warnings, architecture, fallback reason, the resolved policy, reset-to-detected, and an explicit benchmark action.

Automatic `--fast` and Sage/Flash attention stay disabled until an explicit success gate exists for a compatible CUDA capability. The current benchmark measures the active safe policy; it does not promote experimental flags without a baseline comparison and visual QA. OOM recovery lowers the profile, disables fast flags, restarts managed ComfyUI with the safer arguments, and persists a model-family/device hint for later jobs.

Validation on the current host covers the NVIDIA path and deterministic fixtures for the other rows. AMD, Apple, CPU-only, multi-adapter, compact-window, and accessibility validation still require those hosts or CI runners.
