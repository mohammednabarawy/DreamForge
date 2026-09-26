/**
 * Model capabilities metadata for UI badges, tooltips, and guidance.
 * Aligns with backend/modules/model_capabilities.py.
 */

export type ModelCapability = {
  family: string;
  displayName: string;
  strengths: string[];
  limitations: string[];
  bestFor: string;
  tips: string;
  nsfwLevel: "explicit" | "soft" | "none";
  badges: string[];
  speedTier: "fast" | "medium" | "slow";
  loraEcosystem: "rich" | "growing" | "limited" | "none";
};

export const MODEL_CAPABILITIES: Record<string, ModelCapability> = {
  krea2: {
    family: "krea2",
    displayName: "Krea 2 Turbo",
    strengths: ["photorealism", "lighting", "composition", "identity_edit", "speed"],
    limitations: ["explicit_anatomy", "text_rendering", "lora_ecosystem"],
    bestFor: "Photorealistic portraits, identity-preserving edits, architectural scenes",
    tips: "Use descriptive photographic prose. For explicit content, pair with Flux + dedicated LoRAs. Identity Edit mode preserves faces while changing body/clothing.",
    nsfwLevel: "soft",
    badges: ["📸 Photo", "✏️ Edit", "⚡ Fast"],
    speedTier: "fast",
    loraEcosystem: "limited",
  },
  flux: {
    family: "flux",
    displayName: "Flux Dev",
    strengths: ["versatility", "prompt_adherence", "lora_ecosystem", "explicit_anatomy", "text_rendering"],
    limitations: ["speed", "vram_usage"],
    bestFor: "General purpose, LoRA-heavy workflows, text in images, explicit content with dedicated LoRAs",
    tips: "Best LoRA ecosystem. Use Flux Dev for quality, Schnell for speed. Kontext mode for identity-preserving edits.",
    nsfwLevel: "explicit",
    badges: ["📸 Photo", "🎨 Art", "🧩 LoRA", "🔞 Explicit"],
    speedTier: "medium",
    loraEcosystem: "rich",
  },
  flux_kontext: {
    family: "flux_kontext",
    displayName: "Flux Kontext",
    strengths: ["identity_edit", "prompt_adherence", "consistency"],
    limitations: ["speed", "vram_usage"],
    bestFor: "Identity-preserving edits, character consistency, scene changes while keeping the same person",
    tips: "Best for changing scenes/outfits while preserving a person's face. Works with Flux LoRAs.",
    nsfwLevel: "explicit",
    badges: ["✏️ Edit", "👤 Identity", "🧩 LoRA"],
    speedTier: "medium",
    loraEcosystem: "rich",
  },
  sdxl: {
    family: "sdxl",
    displayName: "SDXL",
    strengths: ["lora_ecosystem", "controlnet", "explicit_anatomy", "speed", "community"],
    limitations: ["natural_language_understanding", "text_rendering"],
    bestFor: "Mature LoRA ecosystem, ControlNet workflows, anime/stylized art, explicit content",
    tips: "Largest LoRA and ControlNet ecosystem. Best with tag-style prompts. Use dedicated NSFW checkpoints for explicit content.",
    nsfwLevel: "explicit",
    badges: ["🎨 Art", "🧩 LoRA", "🔞 Explicit", "⚡ Fast"],
    speedTier: "fast",
    loraEcosystem: "rich",
  },
  sd15: {
    family: "sd15",
    displayName: "SD 1.5",
    strengths: ["speed", "low_vram", "lora_ecosystem", "controlnet"],
    limitations: ["resolution", "detail", "natural_language_understanding"],
    bestFor: "Low-VRAM systems, fast iteration, legacy LoRA collections",
    tips: "Best at 512×512. Very fast with a huge legacy LoRA library.",
    nsfwLevel: "explicit",
    badges: ["⚡ Fast", "🧩 LoRA", "💾 Low VRAM"],
    speedTier: "fast",
    loraEcosystem: "rich",
  },
  qwen_image: {
    family: "qwen_image",
    displayName: "Qwen Image",
    strengths: ["text_rendering", "multilingual", "understanding"],
    limitations: ["explicit_anatomy", "speed"],
    bestFor: "Text-heavy images, multilingual prompts, design mockups",
    tips: "Best text rendering of any model. Understands Chinese, Arabic, and other scripts.",
    nsfwLevel: "soft",
    badges: ["📝 Text", "🌍 Multilingual"],
    speedTier: "medium",
    loraEcosystem: "growing",
  },
  qwen_image_edit: {
    family: "qwen_image_edit",
    displayName: "Qwen Image Edit",
    strengths: ["precision_edit", "text_rendering", "instruction_following"],
    limitations: ["explicit_anatomy", "speed"],
    bestFor: "Precise instruction-based edits, text changes, localized modifications",
    tips: "Give clear editing instructions rather than full scene descriptions.",
    nsfwLevel: "soft",
    badges: ["✏️ Edit", "📝 Text", "🎯 Precise"],
    speedTier: "medium",
    loraEcosystem: "limited",
  },
  "qwen_image_2.1": {
    family: "qwen_image_2.1",
    displayName: "Qwen Image 2.1",
    strengths: ["precision_edit", "text_rendering", "instruction_following", "multilingual"],
    limitations: ["explicit_anatomy", "speed"],
    bestFor: "Reference-guided generation, semantic edits, masks, and transparent PNGs",
    tips: "Use ordered <image1> tags for references and describe what should remain unchanged.",
    nsfwLevel: "soft",
    badges: ["✏️ Edit", "🖼️ References", "📝 Text"],
    speedTier: "medium",
    loraEcosystem: "limited",
  },
  hidream_o1: {
    family: "hidream_o1",
    displayName: "HiDream o1",
    strengths: ["artistic_quality", "composition", "lighting"],
    limitations: ["speed", "vram_usage", "lora_ecosystem"],
    bestFor: "Artistic compositions, cinematic scenes, creative explorations",
    tips: "Produces highly artistic results with expressive lighting.",
    nsfwLevel: "soft",
    badges: ["🎨 Art", "🎬 Cinematic"],
    speedTier: "slow",
    loraEcosystem: "limited",
  },
  z_image: {
    family: "z_image",
    displayName: "Z-Image Turbo",
    strengths: ["speed", "photorealism"],
    limitations: ["lora_ecosystem", "explicit_anatomy"],
    bestFor: "Fast photorealistic generation, real-time previews",
    tips: "Very fast turbo model for quick iterations.",
    nsfwLevel: "soft",
    badges: ["📸 Photo", "⚡ Fast"],
    speedTier: "fast",
    loraEcosystem: "limited",
  },
  ideogram4: {
    family: "ideogram4",
    displayName: "Ideogram 4",
    strengths: ["text_rendering", "typography", "design", "prompt_adherence"],
    limitations: ["explicit_anatomy", "lora_ecosystem", "vram_usage"],
    bestFor: "Text-heavy images, logos, posters, design work, typography",
    tips: "Best-in-class text rendering and typography.",
    nsfwLevel: "none",
    badges: ["📝 Text", "🎨 Design", "🔤 Typography"],
    speedTier: "medium",
    loraEcosystem: "none",
  },
};

export function inferModelFamily(nameOrPath?: string | null): string {
  if (!nameOrPath) return "unknown";
  const lower = nameOrPath.toLowerCase();
  if (lower.includes("krea2") || lower.includes("krea-2") || lower.includes("krea_2")) return "krea2";
  if (lower.includes("kontext")) return "flux_kontext";
  if (lower.includes("flux")) return "flux";
  if (lower.includes("qwen") && (lower.includes("2.1") || lower.includes("2_1"))) return "qwen_image_2.1";
  if (lower.includes("qwen") && lower.includes("edit")) return "qwen_image_edit";
  if (lower.includes("qwen")) return "qwen_image";
  if (lower.includes("hidream")) return "hidream_o1";
  if (lower.includes("z-image") || lower.includes("z_image")) return "z_image";
  if (lower.includes("ideogram")) return "ideogram4";
  if (lower.includes("sdxl") || lower.includes("xl_base") || lower.includes("juggernautxl") || lower.includes("realvisxl")) return "sdxl";
  if (lower.includes("sd15") || lower.includes("sd1.5") || lower.includes("v1-5") || lower.includes("dreamshaper")) return "sd15";
  return "unknown";
}

export function inferLoraFamily(nameOrPath?: string | null): string {
  if (!nameOrPath) return "unknown";
  const lower = nameOrPath.toLowerCase();
  if (lower.includes("-f1") || lower.includes("_f1") || lower.includes("flux") || lower.includes("klein")) return "flux";
  if (lower.includes("_xl") || lower.includes("-xl") || lower.includes("sdxl") || lower.includes("pony")) return "sdxl";
  if (lower.includes("krea")) return "krea2";
  if (lower.includes("qwen")) return "qwen_image";
  if (lower.includes("sd15") || lower.includes("sd1.5") || lower.includes("v1-5")) return "sd15";
  if (lower.includes("hidream")) return "hidream_o1";
  if (lower.includes("z-image") || lower.includes("z_image")) return "z_image";
  return "unknown";
}

export function isLoraCompatibleWithModel(
  loraName: string,
  modelNameOrFamily?: string | null,
): { compatible: boolean; loraFamily: string; reason?: string } {
  const loraFam = inferLoraFamily(loraName);
  const modelFam = inferModelFamily(modelNameOrFamily);
  if (loraFam === "unknown" || modelFam === "unknown") {
    return { compatible: true, loraFamily: loraFam };
  }

  const matrix: Record<string, string[]> = {
    sdxl: ["sdxl", "sd3"],
    sd15: ["sd15"],
    sd3: ["sd3", "sdxl"],
    flux: ["flux", "flux_kontext", "flux_fill", "flux2", "chroma"],
    flux_kontext: ["flux", "flux_kontext", "flux_fill", "flux2", "chroma"],
    krea2: ["krea2"],
    qwen_image: ["qwen_image", "qwen_image_edit"],
    qwen_image_edit: ["qwen_image", "qwen_image_edit"],
    "qwen_image_2.1": ["qwen_image_2.1"],
    hidream: ["hidream", "hidream_o1"],
    hidream_o1: ["hidream", "hidream_o1"],
    z_image: ["z_image"],
  };

  const allowed = matrix[loraFam] ?? [];
  const compatible = allowed.includes(modelFam);
  return {
    compatible,
    loraFamily: loraFam,
    reason: compatible
      ? undefined
      : `Trained for ${loraFam.toUpperCase()} — no effect on ${modelFam.toUpperCase()}`,
  };
}

export function getModelCapabilities(nameOrPath?: string | null): ModelCapability | undefined {
  const family = inferModelFamily(nameOrPath);
  return MODEL_CAPABILITIES[family];
}
