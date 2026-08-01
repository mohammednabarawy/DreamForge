# DreamForge Studio — Final Implementation Plan
## Dual-Mode Discover & Library Architecture, Asset Engine, Recipe System, and Workflow Compatibility Compiler

**Status:** Implementation-ready architecture  
**Prepared:** 31 July 2026  
**Target:** DreamForge Studio desktop application  
**Primary goal:** Transform DreamForge into a privacy-first local AI creative studio where users can discover community assets online, acquire them safely, manage them locally, and recreate or execute compatible generations without turning DreamForge into a ComfyUI clone.

## Implementation progress (1 August 2026)

The plan is being delivered incrementally against the existing ComfyUI-backed desktop app. The current worktree contains the first functional slices:

| Phase | State | Evidence |
|---|---|---|
| 0 — Existing-system audit | Complete | `docs/discover-library/current-system-audit.md` |
| 1 — Domain foundation | Implemented slice | Asset types/registry/scanner, SHA256 identity, compute profile, capabilities, Recipe v2, bridge handlers, focused tests |
| 2 — Dual-mode UI + local library | Implemented slice | Persisted Discover/Library surface and Library Models/LoRAs/Styles/Generate/Automate navigation; existing local galleries and LoRA stack remain the execution source |
| 3 — Provider/download foundation | Implemented slice | Backend Civitai + Hugging Face providers, isolated cached search, credential status, persistent queue, pause/resume/cancel, verification, focused tests |
| 4 — Models & LoRAs discovery UX | Implemented slice | Provider-neutral cards, file variants, architecture gate, compute-aware recommendation, install state, focused tests |
| 5 — Recipe & Prompt Discovery | Implemented slice | Portable Recipe v2 Save/Load/Recreate, image-metadata import, and browse-only Civitai Images/Lexica metadata cards with Recreate/Save actions |
| 6 — Styles | Local slice implemented | Offline custom-style store, Fooocus JSON import, normalized architecture/source metadata, and refresh into the existing style picker |
| 7 — Official workflow discovery | Local slice implemented | Browse-only Discover → Workflows tab backed by the first-party Comfy template registry; templates can be bookmarked locally and never auto-execute |
| 8 — Workflow compatibility | Conservative analysis slice implemented | Non-executing analyzer returns exactly `NATIVE`, `ADAPTABLE`, `COMFY_ONLY`, or `INVALID`, extracts dependencies, blocks command/URL/path-traversal signals, and is exposed in Discover → Workflows |
| 9 — Native workflow execution | Recipe-only slice implemented | High-confidence native graphs compile to portable Recipe v2 and can be exported; no graph is executed or partially translated |
| 10 — Automation | Implemented slice | Recipe v2 batch/folder/matrix automation, deterministic seed sweeps, previews, cancellation, and export reuse the existing ComfyUI-backed worker |

Verification boundary for this snapshot: the focused metadata/recipe-discovery/automation/recipe/provider/style/workflow/bridge suite passes (131 tests) and the desktop production build passes. The remaining phases are intentionally not marked complete until their end-to-end acceptance criteria are implemented and tested.

---

# 1. Executive Summary

DreamForge Studio will adopt a strict two-mode product model:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            PRIMARY DUAL-MODE TOGGLE                         │
│                     [ 🌐 Discover ]   |   [ 📦 Library ]                    │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
             ┌──────────────────────────┴──────────────────────────┐
             ▼                                                     ▼
┌──────────────────────────────┐                     ┌──────────────────────────────┐
│          🌐 DISCOVER         │                     │          📦 LIBRARY          │
│   Find • Evaluate • Acquire  │                     │    Own • Configure • Run     │
├──────────────────────────────┤                     ├──────────────────────────────┤
│ 📦 Models                    │                     │ 📦 Models                    │
│ 🎨 LoRAs                     │                     │ 🎨 LoRAs                     │
│ 🎭 Styles                    │                     │ 🎭 Styles                    │
│ 🔄 Workflows                 │                     │ ⚙️ Generate                  │
│ 💡 Prompts                   │                     │ ⚡ Automate                  │
└──────────────────────────────┘                     └──────────────────────────────┘
```

The architecture is based on six core principles:

1. **Discover is provider-agnostic.** UI components must never be coupled directly to Civitai, Hugging Face, Lexica, GitHub, or ComfyUI.
2. **The Library is the source of truth for local execution.** Online content cannot directly execute arbitrary code.
3. **Files and logical assets are different concepts.** SHA256 identifies a physical file, not an entire logical model.
4. **Every generation can be represented by a portable `DreamForgeRecipe`.**
5. **Workflow compatibility is capability-driven.** DreamForge translates supported semantics instead of trying to emulate every ComfyUI node.
6. **Security is fail-closed.** Unknown workflows, unknown custom nodes, corrupted downloads, and unresolved dependencies must never partially execute.

The resulting product flow becomes:

```text
Discover
   ↓
Evaluate
   ↓
Acquire
   ↓
Verify
   ↓
Register
   ↓
Resolve Dependencies
   ↓
Check Capabilities
   ↓
Recreate / Execute Locally
```

No proprietary cloud backend is required.

---

# 2. Product & UX Architecture

## 2.1 Primary Modes

### 🌐 Discover

Purpose:

> Find, inspect, evaluate, and acquire assets or generation recipes from trusted community sources.

Tabs:

- 📦 Models
- 🎨 LoRAs
- 🎭 Styles
- 🔄 Workflows
- 💡 Prompts

### 📦 Library

Purpose:

> Own, select, configure, combine, and execute local DreamForge assets.

Tabs:

- 📦 Models
- 🎨 LoRAs
- 🎭 Styles
- ⚙️ Generate
- ⚡ Automate

---

## 2.2 Discover Should Expand Beyond the Narrow Inspector

The current right inspector is appropriate for generation controls, but not for browsing large model galleries or workflow graphs.

When `Discover` is selected, use an expanded workspace or overlay:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🌐 Discover    [ Search assets...                        ] [ Provider: All ] │
│ Models | LoRAs | Styles | Workflows | Prompts              [ Filters ▾ ]    │
├───────────────────────────────────────┬─────────────────────────────────────┤
│                                       │                                     │
│  Asset / Workflow / Prompt Gallery    │  Detail Inspector                   │
│                                       │                                     │
│  ┌────────┐ ┌────────┐ ┌────────┐     │  Preview                            │
│  │ Card   │ │ Card   │ │ Card   │     │  Author / Source                    │
│  └────────┘ └────────┘ └────────┘     │  Architecture                       │
│                                       │  Files / Variants                   │
│  ┌────────┐ ┌────────┐ ┌────────┐     │  License / Permissions              │
│  │ Card   │ │ Card   │ │ Card   │     │  Compatibility                     │
│  └────────┘ └────────┘ └────────┘     │  Dependencies                      │
│                                       │                                     │
│                                       │  [ Download ] / [ Recreate ]        │
└───────────────────────────────────────┴─────────────────────────────────────┘
```

After installation:

```text
[ 📥 Download ]
      ↓
[ ⏳ Downloading 63% ]
      ↓
[ ✓ Installed ]   [ ⚡ Use in Studio ]
```

---

# 3. Non-Negotiable Architecture Rules

## 3.1 React Components Must Stay Thin

React components may:

- render UI;
- capture user input;
- dispatch commands;
- subscribe to state.

React components must **not**:

- fetch provider APIs directly;
- own download logic;
- calculate hashes;
- inspect executable workflow dependencies;
- store API tokens;
- parse model files;
- decide workflow compatibility.

All of that belongs in the service/domain layer.

---

## 3.2 Network and Secret Handling Must Live Outside the Renderer

For a desktop app, provider API calls, token handling, file downloads, and filesystem access should run in the desktop backend/main process rather than directly inside the React renderer.

Use the application's existing desktop bridge (Electron IPC, Tauri commands, or equivalent).

Conceptually:

```text
React UI
   ↓
Typed Desktop Bridge
   ↓
Discovery / Download / Asset Services
   ↓
Internet + Filesystem
```

Rules:

- never expose provider tokens to React state;
- never store tokens in `localStorage`;
- never put tokens in query strings when a Bearer header is supported;
- never log authorization headers;
- use the OS secure credential store or the app's existing secret-store abstraction.

---

# 4. Core Domain Model

# 4.1 Logical Asset vs Physical File

**Important correction:** SHA256 must identify a physical file, not the entire conceptual model.

A single model can contain:

- multiple versions;
- multiple precision variants;
- multiple formats;
- split diffusion / encoder / VAE files;
- quantized variants.

Recommended domain shape:

```typescript
export type AssetKind =
  | "checkpoint"
  | "diffusion_model"
  | "lora"
  | "vae"
  | "text_encoder"
  | "controlnet"
  | "adapter"
  | "embedding"
  | "upscaler"
  | "workflow"
  | "style"
  | "recipe";

export interface ProviderRef {
  provider: string;
  providerAssetId?: string;
  providerVersionId?: string;
  url?: string;
}

export interface AssetFile {
  id: string;

  // Canonical physical-file identity.
  sha256?: string;

  filename: string;
  sizeBytes?: number;
  localPath?: string;

  format?: "safetensors" | "ckpt" | "bin" | "gguf" | "pt" | "pth" | "json" | string;
  precision?: "fp32" | "fp16" | "bf16" | "fp8" | "int8" | "int4" | string;

  role: AssetKind;

  providerRefs: ProviderRef[];

  integrity?: {
    verified: boolean;
    sourceHash?: string;
    verifiedAt?: string;
  };
}

export interface AssetVersion {
  id: string;
  name: string;
  architecture?: string;
  baseModels?: string[];
  files: AssetFile[];
  triggerWords?: string[];
  createdAt?: string;
}

export interface DreamForgeAsset {
  id: string;                 // DreamForge logical asset ID
  kind: AssetKind;
  name: string;
  author?: string;

  architecture?: string;
  providerRefs: ProviderRef[];
  versions: AssetVersion[];

  license?: {
    id?: string;
    name?: string;
    url?: string;
    commercialUse?: string;
  };

  metadata: Record<string, unknown>;
}
```

---

# 4.2 Asset Registry

Create:

```text
AssetRegistry
AssetScanner
AssetResolver
AssetMetadataService
```

Responsibilities:

### `AssetRegistry`

Persistent local inventory:

- logical assets;
- versions;
- physical files;
- SHA256;
- paths;
- install state;
- provider references;
- metadata;
- last verification time.

### `AssetScanner`

Scans configured model directories and detects:

- new files;
- removed files;
- moved files;
- changed files.

Avoid hashing every multi-GB model on every startup.

Use a two-stage strategy:

```text
Fast fingerprint
(size + modification time + platform file ID where available)
          ↓
Changed / unknown?
          ↓
SHA256 background verification
```

When a file is downloaded by DreamForge, calculate SHA256 **during the download stream** so no second full-disk read is needed.

### `AssetResolver`

Resolves:

```text
Provider model/version
        ↕
DreamForge logical asset
        ↕
Installed local files
        ↕
Required runtime components
```

Example answer:

```text
Z-Image-Turbo
Architecture: Z-Image
Diffusion model: installed
Text encoder: installed
VAE: missing
Recommended action: Download missing VAE
```

---

# 5. Capability Registry

Add a first-class `CapabilityRegistry`.

This is critical for keeping workflow translation independent from ComfyUI node names.

```typescript
export interface CapabilityRegistry {
  architectures: Set<string>;
  operations: Set<string>;
  assetRoles: Set<AssetKind>;
  samplers: Set<string>;
  schedulers: Set<string>;

  supports(input: CapabilityQuery): CapabilityResult;
}
```

Example capabilities:

```text
architectures
├── sd15
├── sdxl
├── flux.1
├── flux.2
├── qwen-image
├── qwen-image-edit
├── hidream
├── z-image
├── krea-2
└── future architectures...

operations
├── text2img
├── img2img
├── inpaint
├── outpaint
├── image_edit
├── controlnet
├── lora_stack
├── upscale
├── face_detail
└── batch
```

Do **not** hard-code `Qwen2.5-VL` as an image-generation architecture.

For Qwen-Image pipelines, Qwen/VL components can instead appear as a text-encoder dependency.

Example:

```text
Architecture: Qwen-Image
Role: diffusion_model

Dependency:
Role: text_encoder
Family: Qwen2.5-VL
```

---

# 6. Compute Profile & VRAM Estimator

## 6.1 Backend-Neutral Compute Profile

Do not place Apple-specific fields such as `mpsAvailable` into a universal GPU interface.

Use:

```typescript
export interface ComputeProfile {
  backend: "cuda" | "rocm" | "directml" | "mps" | "cpu" | string;

  deviceName?: string;
  totalVramMb?: number;
  freeVramMb?: number;

  systemRamMb: number;

  supportsFp16: boolean;
  supportsBf16: boolean;
  supportsFp8: boolean;

  unifiedMemory: boolean;
}
```

---

## 6.2 Dynamic VRAM Estimation

First implementation:

```text
VRAM estimate =
  architecture
+ precision
+ quantization
+ resolution
+ latent count
+ encoder requirements
+ VAE
+ LoRA stack
+ attention backend
+ offload policy
```

UI:

```text
Estimated peak VRAM     9.3 GB
Recommended headroom   10.5 GB
Available              12.0 GB
Status                 🟢 Compatible
Confidence             Medium
```

Compatibility states:

- 🟢 Compatible
- 🟡 Compatible with offload / quantization
- 🔴 Insufficient local memory
- ⚪ Unknown / not yet benchmarked

### Self-Calibrating Estimator

After successful generations, record:

- architecture;
- precision;
- resolution;
- batch size;
- LoRA count;
- backend;
- GPU;
- actual peak allocated VRAM;
- actual peak reserved VRAM;
- system RAM impact.

Use this local telemetry to refine future predictions.

Never upload private generation data for this feature.

Upstream VRAM metadata may be used as a **hint**, not as authoritative truth.

---

# 7. Universal DreamForge Recipe — v2

The previous recipe shape was still too focused on basic text-to-image.

Use a more general contract:

```typescript
export type ResourceRole =
  | "checkpoint"
  | "diffusion_model"
  | "text_encoder"
  | "vae"
  | "lora"
  | "controlnet"
  | "adapter"
  | "embedding"
  | "upscaler";

export interface RecipeResource {
  role: ResourceRole;
  asset: AssetRef;
  weight?: number;
  enabled?: boolean;
  triggerWords?: string[];
}

export interface DreamForgeRecipe {
  schema: "dreamforge.recipe";
  version: 2;

  id: string;
  title: string;

  prompts: {
    positive: string;
    negative?: string;
  };

  inputs?: {
    images?: ImageRef[];
    mask?: ImageRef;
    controlImages?: ImageRef[];
  };

  resources: RecipeResource[];

  generation: {
    seed?: number;
    width?: number;
    height?: number;
    batchSize?: number;

    sampler?: string;
    scheduler?: string;
    steps?: number;
    cfg?: number;
    denoise?: number;

    performanceMode?: string;
  };

  style?: StyleRef;

  provenance: {
    provider: string;
    sourceUrl?: string;
    author?: string;
    importedAt: string;
  };

  metadata?: Record<string, unknown>;
}
```

This one recipe can represent:

- text-to-image;
- image-to-image;
- inpainting;
- Qwen-Image-Edit;
- ControlNet;
- multi-LoRA generation;
- split-model pipelines;
- upscale stages;
- imported community generations.

Primary user action:

```text
[ Recreate in Studio ]
```

not merely:

```text
[ Copy Prompt ]
```

---

# 8. Provider Architecture

## 8.1 Provider Contract

```typescript
export type ProviderCapability =
  | "model_search"
  | "lora_search"
  | "prompt_search"
  | "workflow_search"
  | "style_source"
  | "asset_download"
  | "hash_lookup";

export interface DiscoveryProvider {
  readonly id: string;
  readonly capabilities: Set<ProviderCapability>;

  search(query: DiscoveryQuery): Promise<DiscoveryPage>;
  getAsset(ref: ProviderAssetRef): Promise<NormalizedAsset>;
  getFiles?(ref: ProviderAssetRef): Promise<NormalizedFile[]>;
  resolveDownload?(ref: ProviderFileRef): Promise<ResolvedDownload>;
}
```

UI must ask providers what they support instead of assuming every provider supports every tab.

---

# 9. Verified Online Asset Sources & Correct Fetching Links

> The endpoints and upstream locations below were rechecked against current public documentation and repositories on **31 July 2026**. Provider responses can still evolve, so all integrations must use defensive parsing and contract tests.

---

## 9.1 Civitai — Models, LoRAs, Images / Prompt Metadata

### Current documentation

Civitai moved its REST API documentation away from the older GitHub Wiki.

**Current documentation root:**

```text
https://developer.civitai.com/site/reference/
```

**Site API base:**

```text
https://civitai.com/api/v1
```

### Recommended endpoints

Search/browse models:

```text
GET https://civitai.com/api/v1/models
```

Example:

```text
GET https://civitai.com/api/v1/models?query=flux&limit=20
```

LoRA discovery:

```text
GET https://civitai.com/api/v1/models?types=LORA&query={query}
```

Model details:

```text
GET https://civitai.com/api/v1/models/{modelId}
```

Model-version details:

```text
GET https://civitai.com/api/v1/model-versions/{modelVersionId}
```

Resolve a Civitai version from SHA256:

```text
GET https://civitai.com/api/v1/model-versions/by-hash/{sha256}
```

Community generations / prompt metadata:

```text
GET https://civitai.com/api/v1/images
```

Canonical model-version download:

```text
GET https://civitai.com/api/download/models/{modelVersionId}
```

### Authentication

Prefer:

```http
Authorization: Bearer <CIVITAI_API_TOKEN>
```

Do **not** put tokens in persistent URLs unless absolutely required by an upstream limitation because URLs can leak through logs/history.

### Download implementation notes

The download service must:

- follow redirects;
- respect `Content-Disposition`;
- support authenticated/gated assets;
- retain provider file/version IDs;
- verify SHA256 when the upstream hash is available;
- never bypass gated models, creator restrictions, or required account/license acceptance.

### Important robustness rule

Civitai response fields can be absent for some resources.

Examples:

- sample-image generation metadata may be missing;
- license/permission fields may vary by model;
- new model categories can appear.

Normalize unknown or missing fields instead of failing the entire result.

---

## 9.2 Hugging Face Hub — Models, LoRAs, Encoders, VAEs, Split Pipelines

### Official Hub API documentation

```text
https://huggingface.co/docs/hub/en/api
```

### Official OpenAPI specification

```text
https://huggingface.co/.well-known/openapi.json
```

### Official TypeScript library

Use the official package where practical:

```text
@huggingface/hub
```

Recommended SDK operations:

```text
listModels()
listFiles()
downloadFile()
```

### REST discovery endpoint

```text
GET https://huggingface.co/api/models
```

Example:

```text
GET https://huggingface.co/api/models?search=qwen-image&pipeline_tag=text-to-image
```

Model-repository details:

```text
GET https://huggingface.co/api/models/{owner}/{repo}
```

### Direct file-download route

Canonical pattern:

```text
https://huggingface.co/{owner}/{repo}/resolve/{revision}/{path}
```

Example:

```text
https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors
```

For reproducible installs, prefer a commit SHA instead of `main` once a recipe is saved:

```text
https://huggingface.co/{owner}/{repo}/resolve/{commitSha}/{path}
```

### Authentication

For gated/private repositories:

```http
Authorization: Bearer <HF_TOKEN>
```

DreamForge must surface:

```text
🔒 Gated repository
Access must be granted on Hugging Face before DreamForge can download it.
```

Never attempt to bypass gating.

### Metadata useful to AssetResolver

Hugging Face model cards support metadata including:

```text
license
base_model
base_model_relation
pipeline_tag
library_name
tags
```

Use these as hints for normalization and compatibility, but do not assume community metadata is always correct.

---

## 9.3 Lexica — Prompt Discovery

### Official documentation

```text
https://lexica.art/docs
```

### Search endpoint

```text
GET https://lexica.art/api/v1/search?q={query}
```

Example:

```text
GET https://lexica.art/api/v1/search?q=cinematic%20portrait
```

The documented search endpoint returns an image-result collection.

Use Lexica as:

```text
Prompt inspiration / discovery provider
```

not as the authoritative source for modern model compatibility.

Imported Lexica results should be converted to `DreamForgeRecipe` only when enough metadata exists; otherwise create a partial recipe and mark missing fields.

---

# 9.4 Fooocus — Style Recipe Seed Source

Fooocus is now in limited long-term support and is centered around SDXL, so it should **not** become DreamForge's permanent style backend.

Treat it as an upstream import source for the initial DreamForge Style Library.

### Official style directory

```text
https://github.com/lllyasviel/Fooocus/tree/main/sdxl_styles
```

### Raw upstream files

```text
https://raw.githubusercontent.com/lllyasviel/Fooocus/main/sdxl_styles/sdxl_styles_diva.json
https://raw.githubusercontent.com/lllyasviel/Fooocus/main/sdxl_styles/sdxl_styles_fooocus.json
https://raw.githubusercontent.com/lllyasviel/Fooocus/main/sdxl_styles/sdxl_styles_marc_k3nt3l.json
https://raw.githubusercontent.com/lllyasviel/Fooocus/main/sdxl_styles/sdxl_styles_mre.json
https://raw.githubusercontent.com/lllyasviel/Fooocus/main/sdxl_styles/sdxl_styles_sai.json
https://raw.githubusercontent.com/lllyasviel/Fooocus/main/sdxl_styles/sdxl_styles_twri.json
```

Normalize these into DreamForge's own schema.

```typescript
export interface DreamForgeStyle {
  id: string;
  name: string;

  promptPrefix?: string;
  promptSuffix?: string;
  negativePrompt?: string;

  preferredArchitectures?: string[];
  recommended?: {
    cfg?: number;
    steps?: number;
    sampler?: string;
    scheduler?: string;
  };

  provenance: {
    source: string;
    sourceUrl?: string;
    license?: string;
  };
}
```

Do not dynamically depend on Fooocus availability at runtime after the styles have been imported into DreamForge.

---

# 9.5 ComfyUI Official Workflow Templates — Primary Workflow Catalog

This should be the **primary online workflow source** for the first workflow-discovery implementation.

### Official repository

```text
https://github.com/Comfy-Org/workflow_templates
```

### Official workflow index

```text
https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/index.json
```

The index currently exposes useful discovery metadata such as:

- title;
- description;
- tags;
- model names;
- open-source indicator;
- size;
- upstream VRAM hint;
- usage;
- input/output media;
- thumbnail paths.

### Workflow file pattern

```text
https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/{templateName}.json
```

Example:

```text
https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/image_z_image_turbo.json
```

### Thumbnail / preview pattern

Take the thumbnail path from the index and prepend:

```text
https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/
```

For example:

```text
thumbnail path:
output/image_z_image_turbo.png

resolved URL:
https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/output/image_z_image_turbo.png
```

### Optional bundle metadata

```text
https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/bundles.json
```

### Why this source is valuable

Official templates can include model dependency metadata directly in node properties.

For example, official workflows can contain:

```json
{
  "models": [
    {
      "name": "qwen_3_4b.safetensors",
      "url": "https://huggingface.co/.../resolve/main/...",
      "directory": "text_encoders"
    }
  ]
}
```

The dependency resolver should use this metadata before trying filename heuristics.

---

# 9.6 ComfyUI Workflow Schemas

### Latest saved-workflow schema

```text
https://docs.comfy.org/specs/workflow_json
```

DreamForge must support:

```text
ComfyUI Workflow JSON v1.0     ← primary
ComfyUI Workflow JSON v0.4     ← legacy import
ComfyUI API / prompt format
PNG-embedded workflow metadata
```

### API workflow format documentation

```text
https://docs.comfy.org/development/api-development/workflow-api-format
```

Do not make DreamForge's internal representation depend on either Comfy format.

Always normalize into an internal IR first.

---

# 9.7 Comfy Registry — Custom Node Metadata & Security

### Official API base

```text
https://api.comfy.org
```

### List registered nodes

```text
GET https://api.comfy.org/nodes
```

### Search nodes

```text
GET https://api.comfy.org/nodes/search
```

### Get installable version metadata

```text
GET https://api.comfy.org/nodes/{nodeId}/install
```

Specific version:

```text
GET https://api.comfy.org/nodes/{nodeId}/install?version={semver}
```

### List versions of a node

```text
GET https://api.comfy.org/nodes/{nodeId}/versions
```

### Resolve multiple node versions

```text
POST https://api.comfy.org/bulk/nodes/versions
```

Registry responses can include useful security/compatibility metadata such as:

- status;
- deprecated flag;
- dependencies;
- supported OS;
- supported accelerators;
- supported ComfyUI version;
- `tags_admin`;
- download URL.

### Security documentation

```text
https://docs.comfy.org/installation/install_custom_node
```

DreamForge must never silently install or execute a custom Python node.

---

# 9.8 OpenArt — Do Not Use as a Provider Right Now

OpenArt's current official help center states that **no public API is currently available**.

Therefore:

```text
❌ Do not scrape OpenArt.
❌ Do not build a required DreamForge provider around undocumented endpoints.
❌ Do not depend on historical workflow URLs.
```

Allowed:

```text
✓ Local JSON import
✓ Local PNG-with-workflow import
✓ User-selected file import
✓ Future provider if OpenArt releases a documented public API
```

---

# 10. Source Priority Matrix

| Asset Type | Primary Source | Secondary Source | Notes |
|---|---|---|---|
| Checkpoints / diffusion models | Civitai | Hugging Face | Normalize logical model + file variants |
| LoRAs | Civitai | Hugging Face | Preserve trigger words and base-model hints |
| VAEs / encoders / split pipeline assets | Hugging Face | Civitai / workflow metadata | HF is especially useful for split pipelines |
| Styles | DreamForge local schema | Fooocus import | Fooocus is seed data, not permanent backend |
| Prompts | Civitai Images | Lexica | Import into Recipe where metadata permits |
| Workflows | Official ComfyUI workflow templates | Local user imports | Add more providers only through documented APIs |
| Custom-node metadata | Comfy Registry | None initially | Never auto-execute untrusted node code |

---

# 11. Discovery Service Architecture

```text
src/services/discovery/
├── DiscoveryService.ts
├── ProviderRegistry.ts
├── DiscoveryCache.ts
│
├── providers/
│   ├── CivitaiProvider.ts
│   ├── HuggingFaceProvider.ts
│   ├── LexicaProvider.ts
│   ├── FooocusStyleProvider.ts
│   └── ComfyTemplateProvider.ts
│
└── normalization/
    ├── AssetNormalizer.ts
    ├── CivitaiNormalizer.ts
    ├── HuggingFaceNormalizer.ts
    ├── PromptNormalizer.ts
    ├── StyleNormalizer.ts
    └── WorkflowCatalogNormalizer.ts
```

`DiscoveryService` responsibilities:

- search all selected providers in parallel;
- provider timeout isolation;
- response caching;
- pagination;
- normalize results;
- deduplicate cross-provider matches;
- rank results;
- filter NSFW/safety flags according to user settings;
- return partial results if one provider is unavailable.

One provider failing must not blank the entire Discover screen.

---

# 12. Download Architecture

```text
src/services/downloads/
├── DownloadManager.ts
├── DownloadQueue.ts
├── DownloadWorker.ts
├── DownloadPersistence.ts
├── HashVerifier.ts
├── DiskSpaceGuard.ts
└── DownloadResolver.ts
```

Required behavior:

```text
Queued
  ↓
Resolving URL
  ↓
Checking disk
  ↓
Downloading to .part
  ↓
Pause / resume when supported
  ↓
SHA256 verification
  ↓
Security validation
  ↓
Atomic move to final path
  ↓
AssetRegistry registration
  ↓
Installed
```

Requirements:

- persistent queue survives app restart;
- pause/resume;
- retry with exponential backoff;
- cancellation;
- redirects;
- `Content-Disposition`;
- progress by bytes;
- speed and ETA;
- disk-space preflight;
- temporary `.part` file;
- atomic final rename;
- incremental SHA256;
- duplicate detection;
- configurable destination;
- auth headers held only in backend memory;
- redact secrets from logs.

If upstream provides an expected SHA256:

```text
Expected hash != downloaded hash
          ↓
Delete/quarantine file
          ↓
Mark FAILED_INTEGRITY
          ↓
Never register as usable
```

---

# 13. Multi-LoRA Stack Builder

Local Library LoRA panel:

```text
┌────────────────────────────────────────────────┐
│ LoRA Stack                                     │
├────────────────────────────────────────────────┤
│ ✓ Cinematic Detail      0.65    [────────●──]  │
│ ✓ Character Identity    0.90    [──────────●]  │
│ ✓ Lighting Style        0.35    [─────●─────]  │
│                                                │
│ VRAM estimate: +0.7 GB                         │
│ Compatibility: 🟢                              │
│                                                │
│ [ + Add LoRA ] [ Save Stack as Preset ]        │
└────────────────────────────────────────────────┘
```

Each item stores:

```typescript
{
  assetRef,
  enabled,
  weight,
  triggerWords,
  baseArchitecture,
  compatibility
}
```

Weight control:

```text
-2.0 ... +2.0
```

Do not silently inject trigger words.

Instead provide:

```text
[ Insert Trigger Words ]
```

Add reusable stack presets:

```text
Character Setup
Product Photography
Anime Detail Stack
Architectural Visualization
```

---

# 14. Workflow Compatibility Compiler

A ComfyUI workflow is an executable graph, not just a generation preset.

DreamForge must never blindly execute imported graphs.

## 14.1 Compiler Pipeline

```text
External Workflow
      ↓
FormatDetector
      ├── Comfy v1.0
      ├── Comfy v0.4
      ├── Comfy API format
      ├── PNG metadata
      └── Unknown
      ↓
Schema Validator
      ↓
Workflow Normalizer
      ↓
DreamForge Graph IR
      ↓
Node / Semantic Analyzer
      ↓
Dependency Resolver
      ↓
Security Analyzer
      ↓
CapabilityRegistry
      ↓
Compatibility Compiler
      ↓
┌─────────────────────────────────────────────────────────┐
│ 🟢 NATIVE │ 🟡 ADAPTABLE │ 🔴 COMFY-ONLY │ ⚫ INVALID │
└─────────────────────────────────────────────────────────┘
```

---

# 14.2 Internal Workflow IR

Create a DreamForge-owned intermediate representation.

```typescript
export interface WorkflowIR {
  id: string;
  source: WorkflowSource;

  inputs: WorkflowInput[];
  outputs: WorkflowOutput[];

  nodes: WorkflowIRNode[];
  edges: WorkflowIREdge[];

  assets: WorkflowAssetRequirement[];

  subgraphs?: WorkflowIR[];

  metadata: Record<string, unknown>;
}
```

Benefits:

- Comfy schema upgrades do not infect execution code;
- v0.4 and v1.0 become equivalent internally;
- API-format imports become equivalent internally;
- future non-Comfy workflow formats can reuse the compiler.

---

# 14.3 Subgraph Support Is Required

Modern official ComfyUI workflows can contain:

```text
definitions.subgraphs
```

Do not assume every workflow is a flat node list.

The parser must recursively normalize:

- root graph;
- subgraphs;
- proxy widgets;
- graph inputs;
- graph outputs;
- model metadata attached to subgraph nodes.

---

# 14.4 Node Classification

Every node is classified into one of:

```text
CORE_SEMANTIC
KNOWN_TRANSLATABLE
CUSTOM_REGISTERED
CUSTOM_UNKNOWN
UI_ONLY
UNSUPPORTED
```

Examples of semantic operations:

```text
load_model
load_text_encoder
encode_prompt
create_latent
sample
decode_vae
load_image
load_mask
apply_lora
apply_control
upscale
save_output
```

Translation should target semantics, not literal Comfy node names.

---

# 14.5 Compatibility Tiers

### 🟢 Native

Requirements:

- all executable semantics supported by DreamForge;
- architecture supported;
- assets resolvable;
- no unknown executable custom-node behavior;
- settings can be mapped without destructive ambiguity.

Action:

```text
[ Run in DreamForge ]
```

### 🟡 Adaptable

Requirements:

- workflow mostly maps to DreamForge;
- unsupported elements have known safe replacements;
- conversion changes are explainable.

Action:

```text
[ Review Conversion ]
```

Example:

```text
Original scheduler: xyz
DreamForge equivalent: abc

Unsupported preview node removed.
Output behavior unchanged.
```

User accepts conversion before execution.

### 🔴 Comfy-only

Examples:

- custom Python node with no DreamForge semantic equivalent;
- unsupported video/audio branch;
- unknown side effects;
- unsupported architecture;
- graph behavior cannot be reproduced confidently.

Actions:

```text
[ Inspect Workflow ]
[ Save to Library ]
[ View Dependencies ]
```

Do not pretend the workflow can run natively.

### ⚫ Invalid

Examples:

- malformed JSON;
- corrupt PNG metadata;
- broken links;
- impossible graph references.

Action:

```text
Import rejected with diagnostic report.
```

No partial execution.

---

# 15. Workflow Dependency Resolver

Resolver order:

```text
1. Explicit model metadata in workflow node properties
2. SHA256 / provider IDs
3. Comfy Registry node IDs
4. Exact filename match
5. Normalized filename match
6. Provider search
7. User resolution
```

Dependency types:

```text
checkpoint
diffusion model
text encoder
VAE
LoRA
ControlNet
adapter
embedding
upscaler
custom node
```

Dependency report:

```text
Workflow: Z-Image Turbo

✓ diffusion model
  z_image_turbo_bf16.safetensors

✓ text encoder
  qwen_3_4b.safetensors

✕ VAE
  ae.safetensors
  [ Download ]

Compatibility: 🟡 Waiting for dependency
```

---

# 16. Custom Node Security Engine

Imported custom nodes are untrusted executable code.

Rules:

1. Never auto-install.
2. Never execute on import.
3. Query Comfy Registry metadata first.
4. Show repository/source.
5. Show version.
6. Show registry status.
7. Show deprecation/security tags.
8. Show declared Python dependencies.
9. Require explicit user action.
10. Unknown non-registry code receives a stronger warning.
11. DreamForge-native workflow execution must not depend on installing a custom node unless that behavior is intentionally supported through an isolated compatibility mode.

Example UI:

```text
Impact Pack
Registry ID: ...
Version: 8.x
Source: Comfy Registry
Status: Active
Python dependencies: 7
Required by: FaceDetailer

DreamForge native equivalent: Available

Recommendation:
Use DreamForge native Face Detail implementation.

[ Inspect ] [ Use Native Equivalent ]
```

The best path is usually **translation**, not Python-node installation.

---

# 17. Discovery Tabs

## 17.1 Models

Card fields:

- preview;
- name;
- author;
- provider;
- architecture;
- model type;
- latest version;
- download count where available;
- size;
- compatible precision variants;
- license indicator;
- local install state.

Detail view:

```text
Model
 └─ Version
     ├─ FP16
     ├─ BF16
     ├─ FP8
     ├─ INT8
     ├─ GGUF
     └─ other provider files
```

Recommend variants using `ComputeProfile`.

Never hide manual variant selection.

---

## 17.2 LoRAs

Show:

- base architecture;
- trigger words;
- example images;
- recommended weight if provided;
- trained version;
- file size;
- compatibility;
- local duplicate state.

Install into the configured DreamForge LoRA library directory.

---

## 17.3 Styles

Sources:

```text
DreamForge built-in
DreamForge user styles
Imported Fooocus styles
Future documented providers
```

Actions:

```text
[ Preview ]
[ Save to My Styles ]
[ Apply ]
```

---

## 17.4 Workflows

Primary provider:

```text
Comfy-Org/workflow_templates
```

Card:

- thumbnail;
- title;
- description;
- model family;
- input type;
- output type;
- open-source indicator;
- upstream size hint;
- compatibility badge.

Actions vary by compiler result:

```text
🟢 [ Run in DreamForge ]
🟡 [ Review Conversion ]
🔴 [ Inspect / Save ]
```

---

## 17.5 Prompts

Sources:

- Civitai Images;
- Lexica.

Show available metadata:

```text
Prompt
Negative prompt
Model
Model hash
LoRAs
Seed
Sampler
Scheduler
Steps
CFG
Resolution
```

Primary actions:

```text
[ Recreate in Studio ]
[ Copy Prompt ]
[ Save Recipe ]
```

If metadata is incomplete:

```text
Recipe completeness: 65%
Missing: exact model, scheduler
```

Never fabricate missing parameters.

---

# 18. Persistence

Recommended persisted entities:

```text
assets
asset_versions
asset_files
provider_refs
download_jobs
recipes
styles
workflow_imports
workflow_dependencies
benchmark_profiles
user_provider_settings
```

Preferred implementation:

- use the app's existing persistence layer if robust;
- otherwise use SQLite for metadata/indexes;
- JSON remains the interchange/export format.

Do not store giant provider responses indefinitely.

Use normalized metadata plus a bounded cache.

---

# 19. Suggested Source Tree

```text
apps/desktop/src/
│
├── components/
│   ├── InspectorPanel.tsx
│   ├── DiscoverHubView.tsx
│   ├── LocalAssetsView.tsx
│   │
│   ├── discover/
│   │   ├── DiscoverHeader.tsx
│   │   ├── DiscoverFilters.tsx
│   │   ├── AssetGrid.tsx
│   │   ├── AssetDetailPanel.tsx
│   │   ├── ModelsDiscoverTab.tsx
│   │   ├── LorasDiscoverTab.tsx
│   │   ├── StylesDiscoverTab.tsx
│   │   ├── WorkflowsDiscoverTab.tsx
│   │   └── PromptsDiscoverTab.tsx
│   │
│   └── library/
│       ├── ModelsLibraryTab.tsx
│       ├── LoraStackPanel.tsx
│       ├── StylesLibraryTab.tsx
│       ├── GenerationPanel.tsx
│       └── AutomationPanel.tsx
│
├── domain/
│   ├── assets/
│   │   ├── types.ts
│   │   └── architecture.ts
│   ├── recipes/
│   │   └── DreamForgeRecipe.ts
│   ├── workflows/
│   │   ├── WorkflowIR.ts
│   │   └── compatibility.ts
│   └── compute/
│       └── ComputeProfile.ts
│
├── services/
│   ├── discovery/
│   │   ├── DiscoveryService.ts
│   │   ├── ProviderRegistry.ts
│   │   ├── DiscoveryCache.ts
│   │   ├── providers/
│   │   │   ├── CivitaiProvider.ts
│   │   │   ├── HuggingFaceProvider.ts
│   │   │   ├── LexicaProvider.ts
│   │   │   ├── FooocusStyleProvider.ts
│   │   │   └── ComfyTemplateProvider.ts
│   │   └── normalization/
│   │       ├── AssetNormalizer.ts
│   │       ├── CivitaiNormalizer.ts
│   │       ├── HuggingFaceNormalizer.ts
│   │       ├── PromptNormalizer.ts
│   │       └── StyleNormalizer.ts
│   │
│   ├── assets/
│   │   ├── AssetRegistry.ts
│   │   ├── AssetScanner.ts
│   │   ├── AssetResolver.ts
│   │   └── AssetMetadataService.ts
│   │
│   ├── capabilities/
│   │   └── CapabilityRegistry.ts
│   │
│   ├── compute/
│   │   ├── ComputeProfileService.ts
│   │   └── VramEstimator.ts
│   │
│   ├── downloads/
│   │   ├── DownloadManager.ts
│   │   ├── DownloadQueue.ts
│   │   ├── DownloadWorker.ts
│   │   ├── DownloadPersistence.ts
│   │   ├── DownloadResolver.ts
│   │   ├── DiskSpaceGuard.ts
│   │   └── HashVerifier.ts
│   │
│   ├── workflows/
│   │   ├── WorkflowFormatDetector.ts
│   │   ├── WorkflowParser.ts
│   │   ├── WorkflowNormalizer.ts
│   │   ├── WorkflowAnalyzer.ts
│   │   ├── DependencyResolver.ts
│   │   ├── WorkflowSecurityAnalyzer.ts
│   │   ├── CompatibilityCompiler.ts
│   │   ├── InputBinder.ts
│   │   └── WorkflowValidator.ts
│   │
│   └── recipes/
│       ├── RecipeManager.ts
│       ├── RecipeImporter.ts
│       └── RecipeExporter.ts
│
└── stores/
    ├── discoverStore.ts
    └── libraryStore.ts
```

---

# 20. Existing UI Files

## MODIFY

```text
apps/desktop/src/components/InspectorPanel.tsx
```

Responsibilities after refactor:

- primary mode toggle;
- mount correct view;
- no provider business logic.

## NEW

```text
apps/desktop/src/components/DiscoverHubView.tsx
apps/desktop/src/components/LocalAssetsView.tsx
```

Refactor existing marketplace components into the new provider-driven Discover system instead of duplicating logic.

---

# 21. Implementation Roadmap

# Phase 0 — Existing-System Audit

Before changing behavior:

1. map current model-loading flow;
2. map current LoRA flow;
3. map generation settings state;
4. map renderer ↔ desktop backend boundaries;
5. identify existing download code;
6. identify persistence system;
7. identify model-directory configuration;
8. document current supported architecture families.

Deliverable:

```text
docs/discover-library/current-system-audit.md
```

**Acceptance criteria**

- no code changes needed for this phase;
- current behavior is documented well enough to preserve it.

---

# Phase 1 — Domain Foundation

Implement:

- core Asset types;
- logical asset vs file identity;
- AssetRegistry;
- AssetScanner;
- SHA256 engine;
- ComputeProfile;
- CapabilityRegistry;
- Recipe v2 schema.

Do not build online discovery yet.

**Acceptance criteria**

- existing locally installed models are indexed;
- identical files in different paths resolve to the same SHA256 identity;
- split pipeline resources can be represented;
- current model execution still works unchanged.

---

# Phase 2 — Dual-Mode UI + Local Library

Implement:

```text
[ Discover | Library ]
```

Library tabs:

- Models;
- LoRAs;
- Styles;
- Generate;
- Automate placeholder if automation is not yet implemented.

Implement Multi-LoRA stack builder and presets.

**Acceptance criteria**

- active mode persists;
- active subtab persists;
- model selection still controls the current engine;
- LoRA stacking works with current generation;
- no regression to existing workspace.

---

# Phase 3 — Provider & Download Foundation

Implement:

- `ProviderRegistry`;
- `DiscoveryService`;
- provider response cache;
- secure provider credentials;
- persistent DownloadManager;
- file verification.

Add:

- Civitai provider;
- Hugging Face provider.

**Acceptance criteria**

- search both sources;
- provider failure isolation;
- download queue survives restart;
- pause/resume works where server supports range requests;
- hashes are verified;
- files are registered after successful download;
- gated models fail with a clear auth/access message rather than a generic error.

---

# Phase 4 — Models & LoRAs Discover UX

Implement:

- model cards;
- LoRA cards;
- model versions;
- file variants;
- compatibility;
- install state;
- compute-aware recommendation.

**Acceptance criteria**

- same installed file discovered from two providers is not downloaded twice once its SHA256 is known;
- user can manually override recommended file variant;
- unsupported architecture is clearly marked before download.

---

# Phase 5 — Recipe & Prompt Discovery

Implement:

- Civitai Images;
- Lexica;
- RecipeImporter;
- Recipe completeness score;
- `Recreate in Studio`;
- `Save Recipe`.

**Acceptance criteria**

- known generation metadata maps correctly;
- missing values remain missing;
- recreation never invents a model, seed, sampler, or CFG;
- local recipe can be exported/imported.

---

# Phase 6 — Styles

Implement:

- DreamForgeStyle schema;
- import Fooocus style JSON;
- local custom styles;
- previews;
- save/apply.

**Acceptance criteria**

- imported Fooocus style remains usable offline;
- style does not depend on runtime access to GitHub;
- architecture preference is visible.

---

# Phase 7 — Official Workflow Discover

Implement:

- `ComfyTemplateProvider`;
- official index parsing;
- workflow thumbnail resolver;
- workflow JSON download;
- initial dependency extraction;
- save to Library.

At this stage, execution is not required.

**Acceptance criteria**

- official template index is browseable;
- workflow JSON imports safely;
- model metadata embedded in nodes is detected;
- no imported workflow executes automatically.

---

# Phase 8 — Workflow Compiler

Implement:

- v1.0;
- v0.4;
- API format;
- PNG metadata;
- subgraphs;
- IR;
- semantic classifier;
- dependency resolver;
- Comfy Registry metadata resolver;
- security analyzer;
- 4-state compatibility.

**Acceptance criteria**

Every workflow returns exactly one state:

```text
NATIVE
ADAPTABLE
COMFY_ONLY
INVALID
```

Unknown workflow semantics cannot produce `NATIVE`.

---

# Phase 9 — Native Workflow Execution

Start with narrow, high-confidence patterns.

Recommended order:

1. basic text-to-image;
2. basic LoRA text-to-image;
3. img2img;
4. inpaint;
5. split-model text-to-image;
6. ControlNet;
7. image-edit architectures;
8. advanced pipelines only when explicit semantic support exists.

**Acceptance criteria**

- conversion report is deterministic;
- imported settings are visible before execution;
- no unsupported graph is partially executed;
- engine errors include workflow provenance.

---

# Phase 10 — Automation

After Library and Recipe systems are stable:

- generation matrix;
- prompt variations;
- seed sweeps;
- model/LoRA comparison;
- queued recipes;
- batch export.

Automation should consume the same `DreamForgeRecipe`, not invent a separate generation configuration format.

Current implementation slice: `recipe_batch` loads a local Recipe v2 file, `recipe_folder` queues valid local Recipe v2 files, and `recipe_matrix` compares typed model/LoRA variants across a seed sweep. All dispatch through the existing ComfyUI-backed automation worker. Remote queued-recipe catalogs and richer matrix sources remain follow-up work.

---

# 22. Testing Plan

## 22.1 Provider Contract Tests

Mock and validate:

```text
Civitai normal response
Civitai missing metadata
Civitai auth failure
Civitai rate limit
Civitai redirect download

HF public model
HF gated model
HF repo with split files
HF LoRA
HF model with missing card metadata

Lexica normal search
Lexica empty results
Lexica malformed/partial item

Comfy template index
Comfy missing workflow file
Fooocus style import
```

---

## 22.2 Asset Registry Tests

```text
same SHA256, different filenames
same SHA256, different provider
same logical model, different precision
file moved locally
file deleted locally
file modified after registration
corrupt partial download
```

---

## 22.3 Download Tests

```text
normal download
redirect
pause
resume
cancel
retry
restart recovery
disk-full preflight
wrong SHA256
content-length unavailable
Content-Disposition filename
auth-expired mid-download
duplicate-after-download detection
```

---

## 22.4 Workflow Fixture Suite

Required fixtures:

```text
Comfy v1.0 basic SDXL
Comfy v1.0 with subgraph
Comfy v0.4 legacy workflow
Comfy API format
PNG embedded workflow

FLUX workflow
Qwen-Image workflow
Qwen-Image-Edit workflow
HiDream workflow
Z-Image workflow

LoRA stack workflow
ControlNet workflow
Inpaint workflow
Face-detail workflow

missing checkpoint
missing text encoder
missing VAE
missing LoRA

registered custom node
unknown custom node
deprecated custom node
flagged custom node

broken link
corrupt JSON
invalid node reference
recursive/invalid subgraph
unsupported media workflow
```

---

## 22.5 Critical Safety Test

This test must always pass:

```text
UNKNOWN OR MALFORMED WORKFLOW
          ↓
NO EXECUTION
NO PARTIAL EXECUTION
NO CUSTOM CODE INSTALL
CLEAR DIAGNOSTIC
```

---

# 23. Build & Quality Gates

Run at minimum:

```bash
npx tsc --noEmit
npm run lint
npm run test
npm run build
```

If the repository uses different commands, use its existing equivalents.

Add targeted unit tests for domain/services rather than relying only on UI tests.

---

# 24. Performance Requirements

Discover should not block generation.

Required:

- virtualized card grid for large result sets;
- thumbnail lazy loading;
- request cancellation on query change;
- debounce search;
- bounded cache;
- provider pagination;
- background hashing;
- download worker limits;
- no full model rehash on every launch.

Suggested defaults:

```text
Provider search concurrency: 3–5
Large-file download concurrency: 1–2
Thumbnail/image requests: independent lightweight queue
```

Make these configurable internally.

---

# 25. Offline & Failure Behavior

DreamForge remains a local studio when internet is unavailable.

Offline:

```text
Discover → Offline message + cached results if available
Library  → Fully functional
Generation → Fully functional
Recipes → Fully functional
Installed workflows → Inspectable / runnable according to compatibility
```

Never make local generation dependent on a provider being online.

---

# 26. Licensing & Provenance

Every imported/downloaded item should retain provenance:

```text
provider
source URL
provider asset ID
provider version ID
author
license
download timestamp
SHA256
```

If license is unknown:

```text
License: Unknown — review source before commercial use
```

Do not infer commercial permission from an absent field.

---

# 27. Logging & Diagnostics

Structured events:

```text
DISCOVERY_SEARCH
PROVIDER_FAILURE
DOWNLOAD_STARTED
DOWNLOAD_RESUMED
DOWNLOAD_VERIFIED
DOWNLOAD_HASH_FAILED
ASSET_REGISTERED
WORKFLOW_IMPORTED
WORKFLOW_CLASSIFIED
WORKFLOW_DEPENDENCY_MISSING
WORKFLOW_SECURITY_BLOCK
RECIPE_APPLIED
GENERATION_VRAM_SAMPLE
```

Never log:

- access tokens;
- Authorization headers;
- private prompt content unless the current DreamForge logging policy already intentionally does so and the user has enabled it.

Prefer redaction by default.

---

# 28. Feature Flags

Introduce high-risk functionality behind flags:

```text
discover.providers.civitai
discover.providers.huggingface
discover.providers.lexica
discover.providers.comfyTemplates

workflows.import
workflows.nativeExecution
workflows.adaptableExecution

downloads.resume
vram.selfCalibration
```

This allows incremental rollout without destabilizing the current Studio.

---

# 29. Migration Strategy

The current Marketplace should not be deleted immediately.

Recommended migration:

```text
Existing Marketplace logic
          ↓
extract provider logic
          ↓
CivitaiProvider
          ↓
new Discover UI
          ↓
remove old Marketplace tab after parity
```

Preserve current application behavior until the replacement passes parity tests.

---

# 30. Definition of Done

The project is complete when all of the following are true:

### Discover

- models browse from Civitai and Hugging Face;
- LoRAs browse from supported providers;
- official Comfy workflows browse safely;
- prompt discovery works;
- styles import into DreamForge schema;
- provider failures degrade gracefully.

### Downloading

- queue persists;
- hashes verify;
- duplicates resolve;
- gated content is handled correctly;
- no secret leaks.

### Library

- local models are indexed;
- split model components are represented;
- multi-LoRA works;
- styles are local;
- generation behavior remains stable.

### Recipes

- community metadata can become a Recipe;
- Recipe can recreate supported configurations;
- missing data is never invented.

### Workflows

- v1.0 supported;
- legacy v0.4 supported;
- API format supported;
- PNG metadata supported;
- subgraphs supported;
- dependencies reported;
- custom-node security enforced;
- workflows are classified Native / Adaptable / Comfy-only / Invalid.

### Architecture

- UI is provider-agnostic;
- execution is capability-driven;
- no remote provider is required for local generation;
- no arbitrary workflow code executes without explicit trust.

---

# 31. Coding-Agent Instructions

When implementing this plan:

1. **Audit existing code before replacing anything.**
2. **Reuse the current DreamForge inference engine.**
3. **Do not add a ComfyUI server dependency.**
4. **Do not attempt to reproduce all of ComfyUI.**
5. **Translate supported workflow semantics into existing DreamForge capabilities.**
6. **Never silently install custom nodes.**
7. **Keep provider logic outside React.**
8. **Keep tokens outside renderer state.**
9. **Preserve current settings and generation behavior.**
10. **Implement phase-by-phase with tests after each phase.**
11. **Do not fabricate provider metadata.**
12. **Do not hard-code API response assumptions where fields can be optional.**
13. **Use upstream IDs + SHA256 + provider provenance.**
14. **Never treat filename alone as identity.**
15. **Prefer official APIs/repositories over scraping.**
16. **If an upstream provider lacks a documented public API, do not build a production dependency on it.**
17. **Unknown workflows must fail safely.**
18. **Every new architecture should enter through `CapabilityRegistry`, not scattered `if/else` checks.**
19. **Every generation configuration should converge on `DreamForgeRecipe`.**
20. **Run typecheck, tests, and production build before declaring a phase complete.**

---

# 32. Final Target Architecture

```text
                     ┌────────────────────┐
                     │     🌐 Discover    │
                     └─────────┬──────────┘
                               │
                     ┌─────────▼──────────┐
                     │ DiscoveryService   │
                     └─────────┬──────────┘
                               │
          ┌────────────────────┼──────────────────────┐
          │                    │                      │
   CivitaiProvider      HuggingFaceProvider    Other Providers
          │                    │                      │
          └────────────────────┼──────────────────────┘
                               ▼
                       Asset Normalization
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
       DreamForgeAsset                   DreamForgeRecipe
              │                                 │
              ▼                                 │
        AssetRegistry                           │
              │                                 │
        AssetResolver                           │
              │                                 │
              ├──────────────┐                  │
              ▼              ▼                  │
     CapabilityRegistry   VramEstimator          │
              │              │                  │
              └──────┬───────┘                  │
                     ▼                          │
              DreamForge Engine ◄───────────────┘
```

Workflow path:

```text
Official / User Workflow
          │
          ▼
   Format Detector
          │
          ▼
  Schema Validation
          │
          ▼
    Workflow IR
          │
     ┌────┴────┐
     ▼         ▼
Dependency   Security
Resolver     Analyzer
     │         │
     └────┬────┘
          ▼
 CapabilityRegistry
          │
          ▼
CompatibilityCompiler
          │
 ┌────────┼───────────────┬─────────────┐
 ▼        ▼               ▼             ▼
Native  Adaptable     Comfy-only      Invalid
 │        │
 ▼        ▼
DreamForge Engine
```

This architecture gives DreamForge the ability to understand external ecosystems without surrendering control of its own inference engine.

---

# 33. Verified Reference Links

## Civitai

- Current API docs: https://developer.civitai.com/site/reference/
- API base: https://civitai.com/api/v1
- Models: https://civitai.com/api/v1/models
- Images: https://civitai.com/api/v1/images
- Model-version pattern: https://civitai.com/api/v1/model-versions/{modelVersionId}
- Hash lookup pattern: https://civitai.com/api/v1/model-versions/by-hash/{sha256}
- Download pattern: https://civitai.com/api/download/models/{modelVersionId}

## Hugging Face

- Hub API docs: https://huggingface.co/docs/hub/en/api
- OpenAPI: https://huggingface.co/.well-known/openapi.json
- Search API: https://huggingface.co/api/models
- File download pattern: https://huggingface.co/{owner}/{repo}/resolve/{revision}/{path}
- JS SDK docs: https://huggingface.co/docs/huggingface.js/en/hub/README
- Model card metadata: https://huggingface.co/docs/hub/en/model-cards

## Lexica

- API docs: https://lexica.art/docs
- Search: https://lexica.art/api/v1/search?q={query}

## Fooocus

- Official repository: https://github.com/lllyasviel/Fooocus
- Official styles directory: https://github.com/lllyasviel/Fooocus/tree/main/sdxl_styles

## ComfyUI

- Workflow JSON schema: https://docs.comfy.org/specs/workflow_json
- Workflow API format: https://docs.comfy.org/development/api-development/workflow-api-format
- Official workflow templates: https://github.com/Comfy-Org/workflow_templates
- Workflow index: https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/index.json
- Comfy Registry overview: https://docs.comfy.org/registry/overview
- Comfy Registry API node list: https://api.comfy.org/nodes
- Custom node security guidance: https://docs.comfy.org/installation/install_custom_node

## OpenArt

- Current help center: https://openart.ai/help
- Current status relevant to DreamForge: no documented public API available; do not use as a required provider.

---

# 34. Final Recommendation

Proceed with the Dual-Mode architecture.

The critical implementation philosophy is:

> **DreamForge should understand external assets and workflows, normalize them into its own domain model, resolve their dependencies, explain compatibility, and execute only the semantics that its own engine supports safely.**

Do not make DreamForge a thin shell around Civitai.

Do not make DreamForge a hidden ComfyUI installation.

Build DreamForge as the independent local engine and studio, with community ecosystems acting as interoperable sources.

The differentiator should become:

```text
Find anything.
Understand what it requires.
Know whether your machine can run it.
Install it safely.
Recreate it locally.
Keep full control.
```
