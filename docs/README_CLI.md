# DreamForge CLI (Command Line Interface)

This is a custom Command Line Interface for DreamForge, allowing you to generate images programmatically without launching the web browser. It supports advanced features like model selection, custom styles, LoRAs, and batch generation.

## 🤖 MCP Server (For Agents)

The recommended way for AI agents to interact with DreamForge is via the **MCP Server**. The server exposes 14 tools including image generation, editing, model discovery, and output searching.

```powershell
# Start the MCP server
.\python_embeded\python.exe dreamforge_mcp_server.py
```
See `AI_INSTRUCTIONS.md` and `DREAMFORGE_AGENT_SKILL.md` for details.

## DreamForge desktop (Tauri)

Native split-pane studio UI (Sessions · Canvas · Inspector) with a Rust ↔ Python bridge — no separate API server. See [desktop/README.md](desktop/README.md). From repo root: `dreamforge.bat`.

## 🚀 Quick Start (CLI)

A batch file has been created in the root directory for easy access:

```powershell
.\dreamforge-cli.bat --prompt "a beautiful landscape" --output "landscape.png"
```

For agent-grade generation, prefer an intent recipe plus a creative brief:

```powershell
.\dreamforge-cli.bat ^
  --use-case product_ad ^
  --subject "sculptural wireless headphones" ^
  --composition "centered product on brushed titanium pedestal" ^
  --lighting "soft studio lighting, realistic reflections" ^
  --brand-colors "graphite, titanium, warm white" ^
  --negative-prompt "text, letters, watermark" ^
  --validate-output
```

This writes a manifest JSON next to the output unless `--no-manifest` is passed.

## 🛠️ Usage & Arguments

### Basic Usage

```powershell
.\dreamforge-cli.bat --prompt "your prompt" --aspect-ratio "1024x1024"
```

### Advanced Usage

```powershell
.\dreamforge-cli.bat ^
  --prompt "cyberpunk detective, neon rain" ^
  --negative-prompt "bright, sunny" ^
  --steps 30 ^
  --cfg-scale 7.0 ^
  --style "DreamForge V2" --style "DreamForge Cyberpunk" ^
  --base-model "juggernautXL_v8Rundiffusion.safetensors" ^
  --lora "sd_xl_offset_example-lora_1.0.safetensors:0.5" ^
  --image-number 2 ^
  --output "detective.png"
```

### Argument Reference

| Category | Argument | Description | Default |
| :--- | :--- | :--- | :--- |
| **Core** | `--prompt` | **(Required)** The positive prompt text. | N/A |
| | `--use-case` | Professional recipe: `product_ad`, `arabic_poster`, `social_post`, `cinematic_scene`, `infographic`, `image_edit`, `fast_draft`, etc. | none |
| | `--brand-kit` | JSON file with brand name, colors, tone, typography, materials, forbidden terms. | N/A |
| | `--subject`, `--composition`, `--lighting`, `--camera`, `--brand-colors`, `--materials` | Creative-brief fields compiled into the prompt. | N/A |
| | `--negative-prompt` | valid negative prompt text. | "" |
| | `--output` | Output filename. Relative command run location. | N/A |
| | `--edit-type` | `auto`, `kontext`, `inpaint`, `img2img`, `qwen_edit` | `auto` |
| | `--seed` | Seed number for reproducibility. `-1` is random. | -1 |
| | `--image-number` | Number of images to generate in a row. | 1 |
| | `--validate-output` | Check generated files for size, nonblank pixels, and basic contrast. | false |
| | `--manifest-path` / `--no-manifest` | Control machine-readable generation manifest output. | auto |
| **Performance** | `--performance` | Preset: `Speed`, `Quality`, `Extreme Speed`. | Speed |
| | `--steps` | Exact number of sampling steps (overrides performance). | N/A |
| | `--aspect-ratio` | Dimensions (e.g., `1152x896`, `1024x1024`). | 1152x896 |
| | `--cfg-scale` | Guidance scale (how strictly to follow prompt). | 7.0 |
| | `--sharpness` | Image sharpness filter strength. | 2.0 |
| | `--sampler` | Sampler method name. | dpmpp_2m_sde_gpu |
| | `--scheduler` | Scheduler name. | karras |
| **Models** | `--base-model` | Filename of the base checkpoint. | (Config Default) |
| | `--refiner-model` | Filename of the refiner checkpoint. | (Config Default) |
| | `--refiner-switch` | Step ratio to switch to refiner (0.0-1.0). | 0.5 |
| | `--lora` | Load LoRA: `filename:weight`. Use flag multiple times. | N/A |
| **Styles** | `--styles` | One or more DreamForge style names after the flag. | `DreamForge V2` |
| **Control** | `--cn-cpds` | CPDS reference image for soft structure/layout guidance. | N/A |
| | `--cn-canny` / `--structure-image` | PyraCanny reference image for edge/sketch/silhouette guidance. | N/A |
| | `--input-image --vary-strength` | Low-denoise img2img/vary refinement. | N/A |

## 🤖 AI Agent Integration

If you want to teach an AI agent to use this tool, provide it with the following specification:

### Tool: `generate_image_dreamforge`

**Description:** Generates images locally using DreamForge via CLI.
**Execution:** `D:\\DreamForge\dreamforge-cli.bat`

**Parameters:**
*   `prompt`: String, or use `use_case` + `subject`
*   `use_case`: String recipe (`product_ad`, `arabic_poster`, `social_post`, `thumbnail`, `cinematic_scene`, `infographic`, `signage`)
*   `brand_kit`: JSON path
*   `subject`, `composition`, `lighting`, `camera`, `brand_colors`, `materials`: creative brief strings
*   `negative_prompt`: String
*   `output`: String (Filename)
*   `aspect_ratio`: String (e.g., "1024x1024")
*   `base_model`: String (Checkpoint filename)
*   `style`: List[String] (Style names)
*   `lora`: List[String] (Format "name:weight")
*   `steps`: Integer
*   `cfg_scale`: Float
*   `vram_profile`: `"16gb"` for RTX 5060 Ti 16 GB, `"8gb"` for 8 GB cards, `"5gb"` for very low VRAM, or `"auto"`
*   `check_fake_text`: Boolean with `--validate-output` — flag likely gibberish label regions
*   `dry_run`: Boolean, resolve the full plan without loading GPU models
*   `input_image`: String, used for img2img, Flux Kontext, and Qwen-Image-Edit style edits
*   `cn_cpds`, `cn_canny`, `structure_image`: Reference image paths
*   `validate_output`: Boolean
*   `manifest_path`: String

**Notes:**
*   Output is saved relative to `D:\\DreamForge\backend\\` if a relative path is given in python, but the batch wrapper usually handles CWD. Absolute paths are recommended for the `--output` argument to ensure files are saved exactly where intended.
*   Every professional run should keep the manifest. It records prompt, model, styles, LoRAs, seed, dimensions, references, output paths, and validation warnings.

## Agent Recipes And Brand Kits

Recipes choose sane defaults for model, style, aspect ratio, performance, steps, and negative prompts. They do not replace explicit flags; any user-supplied flag still wins.

```powershell
.\dreamforge-cli.bat --dry-run --use-case product_ad --subject "luxury headphones" --brand-colors "black and gold"
.\arabic-poster-cli.bat --dry-run --use-case arabic_poster --arabic-text "تصميم فاخر" --subject "luxury perfume campaign" --font "decotype naskh"
```

Example `brand.json`:

```json
{
  "brand_name": "Noor Studio",
  "colors": ["black", "champagne gold", "ivory"],
  "tone": "premium, calm, editorial",
  "typography": "high contrast Arabic headline",
  "materials": ["glass", "polished marble", "brushed metal"],
  "forbidden": ["discount badge", "fake logo", "extra text"]
}
```

Use it with either CLI:

```powershell
.\dreamforge-cli.bat --use-case product_ad --subject "perfume bottle" --brand-kit brand.json --validate-output
.\arabic-poster-cli.bat --use-case arabic_poster --arabic-text "تصميم فاخر" --subject "luxury perfume campaign" --brand-kit brand.json --validate-output
```

## Arabic/Text Image CLI

For posters, signs, ads, and Arabic text, use the dedicated text pipeline instead of asking SDXL to spell the text directly:

```powershell
.\arabic-poster-cli.bat ^
  --use-case arabic_poster ^
  --preset pro_text ^
  --arabic-text "مستقبل الذكاء الاصطناعي" ^
  --scene-prompt "premium technology poster" ^
  --subject "glass AI assistant device on a desk" ^
  --composition "centered product with clean negative space for headline" ^
  --lighting "soft studio lighting with realistic reflections" ^
  --brand-colors "deep blue, white, subtle cyan accents" ^
  --output "outputs\arabic_ai_poster.png"
```

Useful presets:

| Preset | Best for |
| :--- | :--- |
| `pro_text` | Nano Banana / Image-style blended poster text. Uses Quality, harmonization, CPDS text guide, export scaling, and one final crisp repaint to avoid duplicate text layers. |
| `clean_graphic` | Sharp brand graphics where exact text matters more than painted-in texture. |
| `neon_sign` | Glowing sign text integrated into a scene. |
| `balanced` | Manual control with conservative defaults. |

Extra controls:

| Argument | Description |
| :--- | :--- |
| `--prompt-profile nano_banana_pro` | Adds a structured, studio-quality prompt profile with stronger layout and text-zone wording. |
| `--use-case arabic_poster` | Applies professional Arabic poster defaults: `pro_text`, Quality, model/style routing, text-safe negatives, and manifest output. |
| `--brand-kit brand.json` | Adds brand colors, tone, typography, materials, and forbidden terms to the generation plan. |
| `--subject`, `--composition`, `--location`, `--visual-style`, `--lighting`, `--camera` | Optional creative-brief fields that compile into a clearer scene prompt. |
| `--harmonize 0.25-0.45` | Low-denoise img2img blend; higher values integrate more but can deform letters. |
| `--final-text-pass 0.25-1.0` | Optional pre-export exact text repair. Do not combine it with the default `pro_text` crisp export repaint unless you intentionally want multiple text layers. |
| `--text-guide harmonize` | Uses a rendered text reference with CPDS ControlNet to preserve text structure during harmonization. |
| `--max-lines N` | Auto-wraps and shrinks Arabic text to fit within N lines. |
| `--no-wrap` | Disables automatic wrapping. |
| `--export-scale 2` or `--export-width 4096` | Exports a larger final image after generation; `pro_text` defaults to 2x with a crisp text repaint. |
| `--no-crisp-export-text` | Disables preset-enabled final crisp repaint if you want to use only `--final-text-pass`. |
| `--validate-output` | Adds basic file/size/nonblank/contrast checks to the manifest. |

The important limitation is still real: local SDXL/DreamForge cannot spell Arabic reliably inside the diffusion model itself. This CLI gets close to modern text-image systems by combining exact RTL rendering with controlled image harmonization.

If text appears doubled, use only one repair method. The default `pro_text` path now uses harmonization plus one final crisp repaint; avoid adding `--final-text-pass` unless you also pass `--no-crisp-export-text`.

## Discover Local Models, Styles, Presets, and Fonts

The CLIs can now expose the real assets installed on this machine.

```powershell
# List checkpoints, diffusion models, UNets, text encoders, LoRAs, VAEs, ControlNets, presets, and styles
.\dreamforge-cli.bat --list-models

# Same inventory from the Arabic poster CLI
.\arabic-poster-cli.bat --list-models

# List installed system fonts that can be passed to --font
.\arabic-poster-cli.bat --list-fonts

# Filter fonts
.\arabic-poster-cli.bat --list-fonts --font-filter arab

# Machine-readable output for agents/scripts
.\dreamforge-cli.bat --list-models --json
.\arabic-poster-cli.bat --list-inventory --inventory-json
```

Font usage:

```powershell
.\arabic-poster-cli.bat ^
  --preset clean_graphic ^
  --arabic-text "القهوة سر الصباح" ^
  --scene-prompt "premium coffee product advertisement" ^
  --font "arial" ^
  --output "outputs\coffee_arabic.png"
```

`--font` accepts a full `.ttf/.otf/.ttc` path or an exposed font alias such as `arial`, `tahoma`, `segoeui`, `arabtype`, or any alias shown by `--list-fonts`.

Model usage:

```powershell
.\arabic-poster-cli.bat ^
  --preset pro_text ^
  --base-model "juggernautXL_v8Rundiffusion.safetensors" ^
  --arabic-text "عرض خاص" ^
  --scene-prompt "premium product advertisement" ^
  --subject "luxury perfume bottle" ^
  --composition "centered product, empty space for headline" ^
  --font "tahoma" ^
  --output "outputs\perfume_offer.png"
```

Good starting model choices visible in this install include:

| Goal | Try |
| :--- | :--- |
| General SDXL quality | `juggernautXL_v8Rundiffusion.safetensors` |
| Realistic products/people | `RealVisXL_V5.0_fp16.safetensors`, `realvisxlV50_v50Bakedvae.safetensors`, `epicrealismXL_vxiAbeast.safetensors` |
| Stock/ad style | `realisticStockPhoto_v20.safetensors` |
| Inpaint workflows | `juggernautxl_inpaint.safetensors`, `dreamshaperXL_lightningInpaint.safetensors` |

Modern model families are now discovered from `backend\\models\diffusion_models`, `backend\\models\unet`, and `backend\\models\text_encoders` in addition to classic checkpoints. This matters for Flux, HiDream, Qwen-Image/Edit, Flux2, Z-Image, Hunyuan, Wan, and GGUF/SVDQ/FP8 variants.

### HiDream-O1-Image (DreamForge + Comfy native)

Per [ComfyUI HiDream O1 docs](https://docs.comfy.org/tutorials/image/hidream/hidream-o1) and [HiDream-ai/HiDream-O1-Image](https://github.com/HiDream-ai/HiDream-O1-Image):

| Variant | Steps | CFG | Notes |
| :--- | :---: | :---: | :--- |
| Dev (`*dev*`, `mxfp8`, `fp8`) | **28** | **1.0** | No negative prompt; euler + normal scheduler |
| Full | **50** | **5.0** | Use for editing; optional `HiDreamO1PatchSeamSmoothing` in Comfy |

Agent CLI behavior for `hidream_o1_*` checkpoints:

- Family `hidream_o1` (distinct from legacy HiDream I1 / four-CLIP stack).
- `performance_selection` maps to DreamForge `HiDream` / `HiDream Full` presets in `DreamForge/settings/performance.json`.
- DreamForge **style presets are cleared** (SDXL styles break O1 prompts).
- Minimum **28 steps** enforced even on `8gb` profile (do not use 12-step smoke settings).
- Repackaged weights belong under **`backend/models/checkpoints/`** (Comfy-Org aio). UNet-only files under `diffusion_models/` still run but may skip the built-in tokenizer TE unless the file is a full checkpoint.
- Optional prompt enhancer: `backend/models/text_encoders/gemma4_e4b_it_fp8_scaled.safetensors` (not required for sampling).

Recommended dry-runs:

```powershell
.\dreamforge-cli.bat --dry-run --json --model flux1-dev-fp8 --prompt "professional product hero image" --vram-profile 16gb
.\dreamforge-cli.bat --dry-run --json --model hidream_o1_image_dev_mxfp8 --prompt "cinematic neon city skyline" --vram-profile 16gb
.\dreamforge-cli.bat --dry-run --json --model Qwen_Image_Edit-Q3_K_M --input-image backend\\html\warning.png --prompt "replace visible text with Launch Day" --vram-profile 16gb
.\dreamforge-cli.bat --dry-run --json --model svdq-fp4_r32-flux.1-dev --prompt "clean AI dashboard hero image" --vram-profile 5gb
```

VRAM profiles:

| Profile | Use for | Behavior |
| :--- | :--- | :--- |
| `16gb` | RTX 5060 Ti 16 GB and similar | Adds `--normalvram`, caps default modern jobs to 1344², prefers FP8/mxfp8 Schnell/Dev, HiDream mxfp8. |
| `8gb` | RTX 3070/4060 8 GB class | Adds `--lowvram`, caps to 1024² and 20 steps (HiDream O1 keeps **28** steps). Use `flux1-schnell-fp8`, SDXL Lightning, or tested Q4/SVDQ variants. |
| `5gb` | Very low VRAM | Adds `--lowvram`, caps to 896² and 16 steps. Q2-Q4 GGUF, SVDQ/FP4, compact SD1.5 only. |

Important: 8 GB and 5 GB profiles mean "run compatible low-bit variants with offload and reduced dimensions." Full FP16/BF16 models are not realistic on 8 GB; 5 GB is stricter than 8 GB.

### Model dependencies (Qwen-Image-Edit GGUF)

`Qwen_Image_Edit-*.gguf` requires `backend\\models\clip\qwen_2.5_vl_7b_edit-q2_k.gguf`. Dry-run JSON includes `missing_dependencies` when files are absent.

**One command** to download a compatible CLIP and run a GPU smoke test:

```powershell
.\fetch-qwen-clip-smoke.bat
```

Default installs **Unsloth** `Qwen2.5-VL-7B-Instruct-Q4_K_S.gguf` (works with the GGUF loader). The older pathdb `qwen_2.5_vl_7b_edit-q2_k.gguf` (`pig` architecture) downloads but is rejected by this Comfy build.

Options: `--clip-source unsloth|pig|fp8`, `--skip-download`, `--skip-smoke`, `--vram-profile 8gb`, `--timeout 1800`. Set `HF_TOKEN` for faster Hugging Face downloads if rate-limited.

Fast local smoke tests:

```powershell
.\python_embeded\python.exe -s -m py_compile dreamforge_agent_tools.py arabic_poster_pipeline.py arabic_text_renderer.py dreamforge_cli_direct.py dreamforge_cli_inventory.py test_cli_inventory.py
.\python_embeded\python.exe -s test_cli_inventory.py
```

Dry-run combinations before spending GPU time:

```powershell
.\arabic-poster-cli.bat ^
  --dry-run ^
  --preset pro_text ^
  --base-model "RealVisXL_V5.0_fp16" ^
  --font "decotype naskh" ^
  --arabic-text "تصميم فاخر" ^
  --scene-prompt "luxury perfume campaign" ^
  --subject "crystal perfume bottle" ^
  --composition "centered product with headline space"

.\dreamforge-cli.bat ^
  --dry-run ^
  --prompt "premium product advertisement, no text" ^
  --base-model "juggernautXL_v8Rundiffusion" ^
  --styles "Style: ads-advertising" "Style: sai-photographic" "Style: sai-enhance"
```

## Evaluation Status (2026-05-22)

See `EVALUATION_REPORT.md` for the full matrix.

Verified real generation on RTX 5060 Ti 16 GB:

- `outputs/eval/agent_product_ad_20260522.png` — SDXL Lightning product ad
- `outputs/eval/flux_schnell_smoke_20260522.png` — Flux Schnell FP8
- `outputs/eval/hidream_smoke_20260522.png` — HiDream O1 Dev MXFP8

Still needs work:

- Qwen-Image-Edit (missing GGUF CLIP; FP8 safetensors crashed on load)
- SVDQ/FP4 Flux variants (prior 15+ minute stall)
- Use `--check-fake-text` when SDXL invents label gibberish on product surfaces
