# DreamForge Improvement Plan (Inspired by InvokeAI)

## 1. Unified Launcher and Environment Manager
**InvokeAI Feature:** Automated Installer/Launcher that manages virtual environments, dependencies, updates, and provides a clear text-based menu for users.
**DreamForge Implementation:** 
- Create a Python-based interactive TUI (Text User Interface) launcher (`dreamforge_launcher.py`) that replaces simple scripts.
- Features: 
  1. "Start DreamForge Server"
  2. "Update DreamForge & ComfyUI"
  3. "Model Manager (Download / Health Check)"
  4. "Repair Environment"
- This makes it extremely easy for non-technical users to manage the app without typing CLI arguments.

## 2. Advanced Model Manager UI
**InvokeAI Feature:** Centralized Model Manager to track metadata, install via HuggingFace Repo IDs, and manage files.
**DreamForge Implementation:**
- Expand `dreamforge_model_downloader.py` into an interactive console tool.
- Allow users to enter a Hugging Face Repo ID or CivitAI URL, and automatically place it in the correct folder (`detect_model_family`).
- Add a "Starter Models" one-click installer in the new Launcher TUI.

## 3. Improved Face/Character Consistency (MediaPipe / InsightFace)
**InvokeAI Feature:** IP-Adapter integration combined with MediaPipe-based "Face Tools" for precise detection, extraction, and masking of faces.
**DreamForge Implementation:**
- We already have `ip-adapter-faceid`. To match InvokeAI's quality, we need to implement `dreamforge_face_prep.py` (which was planned in Phase 4).
- Add logic to automatically crop, align, and mask the reference face using InsightFace/MediaPipe before feeding it into the ComfyUI FaceID node. This significantly improves consistency compared to feeding raw images.

## 4. Advanced Style Transfer (IP-Adapter Style)
**InvokeAI Feature:** "Style Strong" and "Style Precise" IP-Adapter modes.
**DreamForge Implementation:**
- Update `dreamforge_comfy_workflows.py` to support an explicit "Style Transfer" workflow using `IPAdapter Plus` with weight types (e.g., "style transfer" vs "composition").
- Provide simple presets in the UI/CLI like `--style-reference <image> --style-strength high`.

## Implementation Order
1. **Phase A (Usability):** Build `dreamforge_launcher.py` with an interactive menu.
2. **Phase B (Models):** Integrate `dreamforge_model_downloader.py` and `dreamforge_model_health.py` into the Launcher.
3. **Phase C (Face Consistency):** Implement `dreamforge_face_prep.py` for face auto-cropping and alignment.
4. **Phase D (Styles):** Add IP-Adapter style-transfer nodes to ComfyUI workflow generation.
