# Krea 2 editing and supplied workflow review

Reviewed `D:/ComfyUI_windows_portable/ComfyUI/user/default/workflows/KERA-2-EDIT EASY workflow.json` on 2026-08-31. The original file and the separate portable ComfyUI installation were not modified. Its saved prompt is example workflow data, not an instruction to change application behavior.

## Using DreamForge

Open **Edit**, select **krea2TurboFP8_krea2TURBO.safetensors**, attach a source, and describe the change. The Identity Edit v1.2 LoRA is applied automatically at 0.75. To change its strength, add that same LoRA in the existing LoRA controls; it is applied once at your chosen weight. Older identity-edit LoRAs are rejected on this v1.2 route instead of being mixed with it.

The Edit panel names the route and explains the input order: source/scene first, optional subject second. Two separate images feed both the patch and the grounded encoder; they are not collaged. More than two inputs produce a clear error. Keep Face retains the selected Krea model. Generate/restyle still uses the existing Krea img2img path.

Sampling settings and requested output dimensions remain yours. Turbo at 8 steps, CFG 1, Euler/simple is a useful starting point. Instruction editing samples a fresh latent at denoise 1; the ordinary denoise slider is hidden for this route. The negative branch is image-grounded with an empty prompt, including when CFG is above 1. No extra general-purpose framework or frontend dependency was added.

## Findings in the supplied graph

The 16-node graph uses Krea Turbo ConvRot INT8, Qwen3-VL 4B (`CLIPLoader type=krea2`), Identity Edit v1.2 at 0.75, the 2x Wan image VAE, and an 8-step Euler/simple sampler at CFG 1 and denoise 1.

- **Hidden links:** sixteen ordinary links do not describe the entire graph. Eleven `extra.ue_links` provide model, VAE, image, and CLIP connections through Anything Everywhere. A raw API conversion that ignores them loses required inputs. DreamForge builds explicit API links instead.
- **Duplicate reference:** the broadcaster connects the same image to both `image` and `image_b` on grounded encoding and to both pixel-reference inputs on the model patch. For a single-source edit, the B inputs should be absent. They now exist only when a distinct second input is supplied.
- **Pre-encoding:** the source patch's `target_latent` was unconnected. DreamForge connects it to the same empty latent as the sampler, allowing pixel-path VAE encoding before sampling.
- **Grounding:** the saved cap is 4096, although the source is first resized to height 1024. DreamForge uses the node's 768 default for its grounded encoder; this is independent of output resolution.
- **Decode:** the supplied workflow uses a specialized 2x Wan VAE and VAE Utils decoder, with tiling disabled. DreamForge retains its existing Qwen image VAE and native decode/tiling helper, producing the requested native resolution. This integration does not reproduce the separate 2x decoder effect; use Enhance for upscaling.

The author's guidance supports paired image/latent conditioning, leaving B disconnected for single-image edits, preconnecting target_latent, and keeping outputs within approximately 2 megapixels. Raw with about 20 steps and CFG 3 is recommended for difficult removals. These are recommendations, not settings silently imposed by DreamForge. See the [node author's README](https://github.com/lbouaraba/comfyui-krea2edit).

## Runtime verification and limits

The pinned node pack `comfyui-krea2edit` at `86f886dac23013d88996e3a2e99093ba44d322fb` is installed in DreamForge's managed engine and registered for its existing installation/recovery path. The needed models were already present, including in the configured external model library.

**FP8 rendered successfully:** ComfyUI accepted the DreamForge graph and completed 8 steps at 608 x 768, CFG 1, Euler/simple, seed 2, in about 46 seconds. Visual inspection confirmed the yellow shirt became black with the person, pose, and background recognizable; this is a sample, not a guarantee of identity fidelity. The existing shirt logo was retained. Artifacts are in `outputs/dreamforge/krea2-validation/` (`source.png`, `result.png`, `comparison.jpg`, `prompt.json`, `history.json`).

**ConvRot INT8 is now verified:** after the user explicitly requested the shared runtime upgrade, DreamForge was upgraded from ComfyUI v0.26.0 to stable v0.34.0 (`12d5279438bfefc058a269eae805ceab6047777f`), with comfy-kitchen 0.2.31. The exact `Krea2_Turbo_convrot_int8mixed.safetensors` checkpoint now completes full application edits at 608 x 768, 8 steps, CFG 1, Euler/simple. The earlier `KeyError: int8_tensorwise` occurred on the old runtime and is resolved. See `outputs/dreamforge/kitchen-validation/` for the matched attention tests and saved generation manifests.

The separate portable ComfyUI installation and original workflow remain unchanged. See [ComfyUI v0.34.0](https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.34.0) and its [pinned dependencies](https://github.com/Comfy-Org/ComfyUI/blob/v0.34.0/requirements.txt).

Regression coverage includes stale Kontext/Qwen edit selections, Keep Face, one/two-image graph wiring, LoRA deduplication and missing-LoRA errors, unsupported INT8 diagnostics, and preservation of restyle routing. The desktop TypeScript/Vite production build passes. This does not claim manual verification of every desktop control or GPU validation of Raw/two-image editing.

**Full application path also passed:** `run_generation` completed with Keep Face enabled, the FP8 model retained, all eight steps honored, and `app-result.png` plus its generation manifest saved. Output validation reported a nonblank 608 x 768 image with no warnings. `app-result.json` and `events.json` record this separate run; `comparison.jpg` now compares the source against this application result. The combined focused suite passed **269 tests**; `git diff --check` and the desktop production build passed. Vite reported existing chunk-size/dynamic-import warnings. No packaged Tauri executable was rebuilt or manually clicked through.
