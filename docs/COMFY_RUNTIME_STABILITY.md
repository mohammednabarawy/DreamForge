# ComfyUI runtime stability review

Reviewed 2026-08-31 against the local DreamForge runtime and upstream application implementations.

## Confirmed faults and repairs

- **Replacement worker pipe closed by an old exit callback.** `clear_dead_worker` previously cleared the shared worker slot without checking which process exited. Every clearing caller now supplies the exact child handle. Event pollers and exit/timeout callbacks are scoped to that child, and lifecycle operations are serialized. A real boot failure is no longer mistaken for an intentional restart merely because the engine was booting.
- **A brief HTTP failure latched the backend into a failed state.** Status polling previously cleared worker readiness, preventing subsequent polls from checking recovery. Status is now observational; it retries on later polls. Active generation uses worker execution/error events instead of treating a busy HTTP thread as a crashed GPU engine.
- **Wrong endpoint after a port change.** The desktop now uses the URL emitted by its worker. Python startup checks the current launch's API instead of taking an older URL from the append-only log or accepting any open TCP port.
- **Cleanup affected other installations.** Automatic cleanup now targets Python processes running this managed checkout's `main.py`; it does not discover and kill unrelated ComfyUI servers by their listening ports. Existing model files, custom nodes, and saved settings are unchanged.
- **Incomplete event lines could be discarded.** The event reader advances only through complete newline-delimited records. A subprocess log reader also retains its own process handle across restarts.

## Upstream techniques and their application here

| Technique | Upstream evidence | DreamForge decision |
| --- | --- | --- |
| Explicit process ownership and lifecycle states | [Krita AI Diffusion server](https://github.com/Acly/krita-ai-diffusion/blob/main/ai_diffusion/backend/server.py) starts and monitors its own child, then terminates that child on stop. | Keep the existing managed-worker architecture; repair ownership and stale callbacks instead of introducing another supervisor. |
| Separate self-started and externally managed backends | [SwarmUI ComfyUI backend documentation](https://github.com/mcmonkeyprojects/SwarmUI/blob/master/src/BuiltinExtensions/ComfyUIBackend/README.md) distinguishes these responsibilities. | Do not terminate another installation because it owns port 8188; track this worker's actual endpoint. |
| Queue, WebSocket, and memory-release APIs | [ComfyUI routes](https://docs.comfy.org/development/comfyui-server/comms_routes) document `/prompt`, `/queue`, `/ws`, `/interrupt`, and `/free`; [SwarmUI's backend](https://github.com/mcmonkeyprojects/SwarmUI/blob/master/src/BuiltinExtensions/ComfyUIBackend/ComfyUIAPIAbstractBackend.cs) uses `/free` for unloading. | Keep existing API-based job dispatch, cancellation, and memory recovery. Ordinary prompt, resolution, sampler, or model selection changes do not require a whole-worker reboot. |
| Warm-cache tuning needs measurement | The installed ComfyUI `main.py` resets its executor cache when `/free` requests `free_memory=true`. DreamForge currently requests that cleanup after jobs. | Do not remove the existing cleanup policy during this stability repair. Reducing it is a separate measurable optimization that needs repeated-model timing and RAM/VRAM pressure tests. |

Kitchen attention, Dynamic VRAM, and the installed Torch/custom-node versions are unchanged. This repair does not claim a sampling-speed gain or universal GPU compatibility.

## Validation

- Full backend suite: **1,133 passed, 3 skipped** (the skipped tests require local Carousel fixtures).
- Desktop unit tests: **23 passed**. Rust tests: **6 passed**, including a real child-process pipe regression and an HTTP failure/recovery test using a temporary local server.
- Frontend production build, Rust desktop build, formatting, and whitespace checks passed. Existing Vite chunk-size/mixed-import warnings remain.
- Real desktop IPC: **3 consecutive GPU-worker restarts passed**, including a five-second health check after each restart. Each took approximately 52 seconds including that observation period.
- Real GPU sequence: **Krea2 INT8 Generate (8 steps, 512x512) -> Krea2 FP8 Edit (8 steps) -> Flux Kontext Edit (6 steps) -> Krea2 INT8 Generate (4 steps, 640x512)**. All four jobs completed with valid, nonblank images and no observed worker/backend health failures. The runtime was still healthy after the sequence.
- All four outputs were visually inspected. The Krea2 edit changed a blue mug to red; the low-step Kontext run completed but did not achieve the requested green color. These are lifecycle tests, not editing-quality or speed benchmarks. Kontext's native scale node produced a 1024x1024 image from the 512x512 input.

Local evidence: `.tmp/runtime-stability-restarts.json`, `.tmp/runtime-stability-generations.json`, `.tmp/runtime-stability-final-status.json`, `.tmp/runtime-stability-generations/`, and `.tmp/stability-backend-tests.txt` (not committed). The temporary WebView debugging endpoint was closed after testing. Model weights, generation settings, and the existing GPU optimization policy were preserved.

The live checks cover the RTX 5060 Ti and the listed Krea2/Kontext paths. Other GPUs, Qwen editing, and every Toolbox workflow were not rendered in this run; the automated regression suite covers their existing contracts.
