# DreamForge Enhancement Plan — InvokeAI Launcher Analysis & Integration

## Background

After deep review of [invoke-ai/launcher](https://github.com/invoke-ai/launcher/) (Electron + React + TypeScript), the main [invoke-ai/InvokeAI](https://github.com/invoke-ai/InvokeAI) backend, and the full DreamForge codebase, this plan identifies the highest-impact improvements to adopt — keeping DreamForge's ComfyUI backend and unique strengths (Arabic text, MCP server, style recipes, multi-engine editing).

### Key Findings: InvokeAI vs DreamForge

| Feature | InvokeAI | DreamForge (Current) | Verdict |
|---|---|---|---|
| **Installation** | uv-based venv, GPU picker, repair mode, cancellation, version pinning | git clone + pip, manual setup.bat | **Adopt**: Guided install flow |
| **Model Manager** | UI-based model browser, HuggingFace/CivitAI import, metadata tagging, family detection | File scan only (no `family` metadata), no download UI | **Adopt**: Enriched model metadata |
| **Face/Identity** | IP-Adapter + Face Tools (MediaPipe), diffusers-based | Kontext/Qwen primary + IP-Adapter FaceID retry, InsightFace cosine verification | **DreamForge is stronger** — but has a critical bug |
| **Workflow System** | Node-based editor, JSON workflows | 139K lines of ComfyUI workflow builder, 80+ style recipes | **DreamForge is stronger** |
| **Update Mechanism** | Auto-update via electron-updater, version picker | Manual git pull | **Adopt**: Self-update logic |
| **Error Handling** | PTY terminal, XTerm log viewer | stderr log files | **Adopt**: Better error surfaces |

### Critical Bug Found (Already Partially Fixed)

`_pick_faceid_checkpoint()` was looking for nonexistent `gallery` key and `family: "sdxl"` metadata in the inventory. Fix was applied in this session (prior to this plan).

---

## Phase 1: Fix Critical Bugs & Core Stability (Immediate)

> [!CAUTION]
> These are broken right now and block core functionality.

### 1.1 Complete the FaceID Checkpoint Detection Fix

#### [MODIFY] [dreamforge_identity.py](file:///d:/DreamForge/backend/dreamforge_identity.py)
- ✅ Already fixed: `_pick_faceid_checkpoint()` now scans by filename + size heuristics
- Still needed: Run the test suite to confirm no regressions

#### [MODIFY] [test_identity.py](file:///d:/DreamForge/backend/tests/test_identity.py)
- ✅ Already added: 4 new tests for the real inventory shape
- Fix the one failing test (`test_pick_faceid_checkpoint_matches_sdxl_by_name` — needs `dreamforge_cli_inventory` mock path corrected)

### 1.2 Enrich Model Inventory with Family Metadata

The root cause of the FaceID bug is that `_file_info()` returns bare file data with no semantic metadata. Every downstream consumer (`_pick_faceid_checkpoint`, `_pick_kontext_checkpoint`, `_pick_qwen_edit_checkpoint`) must resort to fragile filename heuristics.

#### [MODIFY] [dreamforge_cli_inventory.py](file:///d:/DreamForge/backend/dreamforge_cli_inventory.py)

Add a `detect_model_family()` function that infers family from:
1. Filename patterns (sdxl, flux, kontext, qwen, hidream, sd15, sd3)
2. File size ranges (SDXL > 2.5GB, SD1.5 ~2GB, Flux ~12-24GB)
3. A `model_families.json` sidecar cache that can be manually overridden

Enrich `_file_info()` to add `"family"` and `"category"` fields:
```python
def _file_info(path, root, category=None):
    stat = path.stat()
    rel = path.relative_to(root).as_posix()
    size_mb = round(stat.st_size / (1024 * 1024), 2)
    return {
        "name": path.name,
        "stem": path.stem,
        "relative_path": rel,
        "path": str(path),
        "size_mb": size_mb,
        "family": detect_model_family(path.name, size_mb, category),
        "category": category,
    }
```

---

## Phase 2: Model Management Improvements (High Impact)

Inspired by InvokeAI's Model Manager, but adapted for DreamForge's ComfyUI backend.

### 2.1 Model Download Manager

#### [NEW] [dreamforge_model_downloader.py](file:///d:/DreamForge/backend/dreamforge_model_downloader.py)

A unified download manager that:
- Accepts HuggingFace URLs, CivitAI URLs, or direct download links
- Shows progress (bytes/total, speed, ETA)
- Validates SHA256 after download
- Places files in the correct ComfyUI model subfolder by type
- Supports resume for interrupted downloads
- Tracks download history in a JSON manifest

### 2.2 Model Health Check CLI

#### [NEW] [dreamforge_model_health.py](file:///d:/DreamForge/backend/dreamforge_model_health.py)

A single command that:
- Scans all model directories for corrupt/incomplete files
- Checks for missing companion models (e.g., VAE for SDXL, CLIP for Flux)
- Reports missing FaceID stack components
- Suggests downloads for commonly needed models
- Validates model-to-node compatibility

### 2.3 Starter Model Pack Command

#### [MODIFY] [dreamforge_cli_direct.py](file:///d:/DreamForge/backend/dreamforge_cli_direct.py)

Add `dreamforge install-starter-pack` that downloads a curated set:
- SDXL base + SDXL VAE
- Flux Schnell fp8 (for fast drafts)
- IP-Adapter FaceID SDXL + LoRA + InsightFace buffalo_l
- 4x-UltraSharp upscaler
- CLIP Vision for IP-Adapter

---

## Phase 3: Installation & Setup Improvements (High Impact)

Inspired by InvokeAI launcher's guided install flow.

### 3.1 GPU Auto-Detection

#### [NEW] [dreamforge_gpu_detect.py](file:///d:/DreamForge/backend/dreamforge_gpu_detect.py)

Auto-detect GPU type and VRAM on startup:
```python
def detect_gpu() -> dict:
    """Returns {vendor, model, vram_mb, recommended_profile}"""
```
- NVIDIA: via `nvidia-smi` or `pynvml`
- AMD: via `rocm-smi`
- Intel: via sysinfo
- Map to VRAM profiles automatically (already have `dreamforge_vram_profiles.py`)

### 3.2 Interactive First-Run Setup

#### [MODIFY] [dreamforge_bootstrap.py](file:///d:/DreamForge/backend/dreamforge_bootstrap.py)

Add a first-run wizard that:
1. Detects GPU and recommends VRAM profile
2. Asks for model storage location (or uses default)
3. Offers starter model pack download
4. Validates ComfyUI installation
5. Runs preflight checks
6. Writes a `.dreamforge_setup_ok` marker

### 3.3 Repair Mode

#### [NEW] [dreamforge_repair.py](file:///d:/DreamForge/backend/dreamforge_repair.py)

Inspired by InvokeAI launcher's repair mode:
- Re-install ComfyUI custom nodes
- Verify Python dependencies
- Clear ComfyUI cache
- Re-download corrupt models
- Reset config to defaults (with backup)

---

## Phase 4: Identity & Face Consistency Improvements (Medium Impact)

> [!IMPORTANT]
> DreamForge's identity system is already stronger than InvokeAI's (multi-route: Kontext → Qwen → FaceID with InsightFace verification). These improvements make it more robust and user-friendly.

### 4.1 Face Verification Report

#### [MODIFY] [dreamforge_identity.py](file:///d:/DreamForge/backend/dreamforge_identity.py)

When `verify_identity_outputs()` reports `"failed"`, include:
- Reference face crop thumbnail path
- Best-match output face crop thumbnail path
- Side-by-side comparison data for the UI
- Specific suggestions (e.g., "Try increasing FaceID weight" or "Use a frontal reference photo")

### 4.2 Multi-Reference Face Blending

#### [MODIFY] [dreamforge_identity.py](file:///d:/DreamForge/backend/dreamforge_identity.py)

Support `references: [{path: "a.png"}, {path: "b.png"}]` where multiple reference images of the same person improve consistency. Average the InsightFace embeddings for better matching.

### 4.3 Automatic Face Preprocessing

#### [NEW] [dreamforge_face_prep.py](file:///d:/DreamForge/backend/dreamforge_face_prep.py)

Before sending to FaceID pipeline:
- Auto-crop to face with 2x padding
- Normalize lighting/contrast
- Detect face angle and warn if profile (>30° off-center)
- Resize to optimal resolution for the IP-Adapter model

---

## Phase 5: UX & Workflow Improvements (Medium Impact)

### 5.1 Generation History & Metadata

#### [MODIFY] [dreamforge_output_index.py](file:///d:/DreamForge/backend/dreamforge_output_index.py)

Enrich output metadata to include:
- Full generation parameters (model, steps, CFG, sampler, seed)
- Identity verification score (if applicable)
- Style recipe used
- Generation time
- Searchable tags (auto-generated from prompt)

### 5.2 Workflow Templates Library

#### [NEW] [dreamforge_workflow_templates.py](file:///d:/DreamForge/backend/dreamforge_workflow_templates.py)

Pre-built workflow templates for common tasks:
- Portrait with face consistency
- Product photography
- Comic panel series (same character)
- Before/after comparison
- Style transfer with identity preservation

### 5.3 Better Error Surfaces

#### [MODIFY] [dreamforge_errors.py](file:///d:/DreamForge/backend/dreamforge_errors.py)

Inspired by InvokeAI launcher's PTY log viewer:
- Structured error categories (model missing, VRAM OOM, network, ComfyUI crash)
- Each error type has a human-readable explanation + fix suggestion
- Errors surface in the desktop UI as dismissible notifications (not just log files)

---

## Phase 6: Self-Update & Version Management (Lower Priority)

### 6.1 Version Check on Startup

#### [MODIFY] [dreamforge_bootstrap.py](file:///d:/DreamForge/backend/dreamforge_bootstrap.py)

Check GitHub releases on startup (non-blocking):
- Compare current version with latest release
- Show notification if update available
- Offer one-click update (git pull + dependency refresh)

### 6.2 ComfyUI Custom Node Auto-Update

#### [MODIFY] [dreamforge_comfy_manager.py](file:///d:/DreamForge/backend/dreamforge_comfy_manager.py)

Check if installed custom nodes have newer commits:
- Track current commit hash for each node pack
- On startup, check for updates (configurable: auto/manual/never)
- Update with rollback support

---

## Open Questions

> [!IMPORTANT]
> Please clarify these before I start implementation:

1. **Priority order**: Should I start with Phase 1+2 (model management fixes) or Phase 3 (installation)? Phase 1 is already partially done.

2. **Desktop app scope**: The desktop app uses Tauri + React. Should improvements focus on the Python backend (CLI/API), the desktop UI, or both?

3. **Model download sources**: Should the model downloader support CivitAI API (requires API key), HuggingFace only, or both?

4. **Starter pack contents**: Are the suggested models in §2.3 the right ones, or do you want different defaults?

---

## Verification Plan

### Automated Tests
```bash
cd d:\DreamForge
d:\DreamForge\python_embeded\python.exe -m pytest backend\tests\ -v
```

### Manual Verification
- Run `dreamforge health-check` to verify model detection
- Generate an identity-preservation job and confirm FaceID retry triggers
- Test starter pack download on a clean install
