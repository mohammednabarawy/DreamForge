import { findGalleryModel } from "./model-selection";
import type { GenerationSettings, ModelGalleryItem } from "./tauri-api";

export type AgentPromptPrepareOptions = {
  selectedImagePath?: string;
  modelGallery?: ModelGalleryItem[];
};

export type AgentPromptPrepareResult = {
  settings: GenerationSettings;
  applied: string[];
  hints: string[];
};

const AGENT_SCENE_KEYS = [
  "identity_preservation",
  "scene_prompt_en",
  "scene_prompt_ar",
] as const;

const INPUT_IMAGE_KEYS = [
  "input_image",
  "reference_image",
  "reference_image_path",
  "input_image_path",
] as const;

const PASSTHROUGH_KEYS: (keyof GenerationSettings)[] = [
  "model",
  "aspect_ratio",
  "seed",
  "steps",
  "cfg_scale",
  "sampler",
  "scheduler",
  "styles",
  "lora",
  "performance",
  "vram_profile",
  "use_case",
  "edit_type",
  "edit_strength",
  "subject",
  "lighting",
  "camera",
  "image_number",
  "cn_selection",
  "cn_type",
];

function coercePromptText(prompt: unknown): string {
  if (prompt == null) return "";
  if (Array.isArray(prompt)) {
    return prompt
      .map(String)
      .map((s) => s.trim())
      .filter(Boolean)
      .join(", ");
  }
  return String(prompt);
}

function coerceNegative(negative: unknown): string | undefined {
  if (negative == null) return undefined;
  if (Array.isArray(negative)) {
    return negative
      .map(String)
      .map((s) => s.trim())
      .filter(Boolean)
      .join(", ");
  }
  const text = String(negative).trim();
  return text || undefined;
}

export function tryParseAgentPromptObject(
  raw: string,
): Record<string, unknown> | null {
  const trimmed = raw.trim();
  if (!trimmed.startsWith("{")) return null;
  try {
    const parsed: unknown = JSON.parse(trimmed);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return null;
    }
    return parsed as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function isAgentPromptPayload(obj: Record<string, unknown>): boolean {
  return AGENT_SCENE_KEYS.some((key) => key in obj);
}

export function detectAgentPromptHint(prompt?: string): string | null {
  const raw = (prompt ?? "").trim();
  if (!raw.startsWith("{")) return null;
  const parsed = tryParseAgentPromptObject(raw);
  if (!parsed || !isAgentPromptPayload(parsed)) return null;
  return "Agent JSON detected — prompt, negative, and reference fields apply when you Generate";
}

function wantsIdentityReference(parsed: Record<string, unknown>): boolean {
  const identity = parsed.identity_preservation;
  if (!identity || typeof identity !== "object" || Array.isArray(identity)) {
    return false;
  }
  const block = identity as Record<string, unknown>;
  return Boolean(block.instruction_en || block.instruction_ar || block.priority);
}

function mergeAgentPromptDict(
  settings: GenerationSettings,
  parsed: Record<string, unknown>,
): Partial<GenerationSettings> {
  const patch: Partial<GenerationSettings> = {};
  const parts: string[] = [];

  const identity = parsed.identity_preservation;
  if (identity && typeof identity === "object" && !Array.isArray(identity)) {
    const block = identity as Record<string, unknown>;
    for (const key of ["instruction_en", "instruction_ar"] as const) {
      const value = block[key];
      if (value) parts.push(String(value));
    }
  }

  for (const key of ["scene_prompt_en", "scene_prompt_ar"] as const) {
    const value = parsed[key];
    if (value) parts.push(String(value));
  }

  const existing = coercePromptText(settings.prompt).trim();
  if (parts.length && (!existing || existing.startsWith("{"))) {
    patch.prompt = parts.join("\n\n");
  }

  const negative = coerceNegative(parsed.negative_prompt);
  if (negative && !(settings.negative_prompt ?? "").trim()) {
    patch.negative_prompt = negative;
  }

  for (const key of INPUT_IMAGE_KEYS) {
    const value = parsed[key];
    if (typeof value === "string" && value.trim()) {
      patch.input_image = value.trim();
      break;
    }
  }

  if (typeof parsed.base_model === "string" && parsed.base_model.trim()) {
    patch.model = parsed.base_model.trim();
  } else if (typeof parsed.model === "string" && parsed.model.trim()) {
    patch.model = parsed.model.trim();
  }

  for (const key of PASSTHROUGH_KEYS) {
    if (parsed[key] !== undefined && patch[key] === undefined) {
      (patch as Record<string, unknown>)[key] = parsed[key];
    }
  }

  if (patch.input_image && !patch.edit_type) {
    patch.edit_type = "kontext";
    patch.cn_selection = "Custom...";
    patch.cn_type = "img2img";
    patch.use_case = patch.use_case ?? "image_edit";
  }

  return patch;
}

function resolveInputImage(
  patch: Partial<GenerationSettings>,
  settings: GenerationSettings,
  parsed: Record<string, unknown>,
  selectedImagePath?: string,
): string | undefined {
  for (const key of INPUT_IMAGE_KEYS) {
    const value = parsed[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  if (patch.input_image?.trim()) return patch.input_image.trim();
  if (settings.input_image?.trim()) return settings.input_image.trim();
  if (selectedImagePath?.trim()) return selectedImagePath.trim();
  return undefined;
}

function applyEditDefaults(
  patch: Partial<GenerationSettings>,
  inputImage: string,
): void {
  patch.input_image = inputImage;
  patch.edit_type = patch.edit_type ?? "kontext";
  patch.cn_selection = "Custom...";
  patch.cn_type = patch.cn_type ?? "img2img";
  patch.use_case = patch.use_case ?? "image_edit";
}

function applyIdentityDefaults(
  patch: Partial<GenerationSettings>,
  settings: GenerationSettings,
  parsed: Record<string, unknown>,
  options: AgentPromptPrepareOptions,
  applied: string[],
  hints: string[],
): void {
  if (!wantsIdentityReference(parsed)) return;

  const inputImage = resolveInputImage(
    patch,
    settings,
    parsed,
    options.selectedImagePath,
  );

  if (inputImage) {
    const fromCanvas =
      Boolean(options.selectedImagePath?.trim()) &&
      inputImage === options.selectedImagePath?.trim() &&
      !(settings.input_image ?? "").trim();
    applyEditDefaults(patch, inputImage);
    applied.push(
      fromCanvas ? "input image (canvas selection)" : "input image",
    );

    const hasModel = Boolean(patch.model?.trim() || settings.model?.trim());
    if (hasModel || !options.modelGallery?.length) return;

    const kontext =
      findGalleryModel(
        options.modelGallery,
        "flux1-dev-kontext_fp8_scaled.safetensors",
      ) ??
      options.modelGallery.find((item) =>
        item.engine_name.toLowerCase().includes("kontext"),
      );

    if (kontext) {
      patch.model = kontext.engine_name;
      applied.push("model (Flux Kontext)");
    } else {
      hints.push("For identity preservation, select a Flux Kontext model in Models.");
    }
    return;
  }

  hints.push(
    "Identity JSON needs a reference photo — set Input image in Settings or select a canvas image. Text-only mode will run without face matching.",
  );
}

function collectAppliedFields(
  before: GenerationSettings,
  after: GenerationSettings,
  applied: string[],
): void {
  const note = (label: string, changed: boolean) => {
    if (changed && !applied.includes(label)) applied.push(label);
  };

  note("prompt", (after.prompt ?? "") !== (before.prompt ?? ""));
  note(
    "negative prompt",
    (after.negative_prompt ?? "") !== (before.negative_prompt ?? ""),
  );
  note("input image", (after.input_image ?? "") !== (before.input_image ?? ""));
  note("model", (after.model ?? "") !== (before.model ?? ""));

  for (const key of [
    "aspect_ratio",
    "seed",
    "use_case",
    "edit_type",
  ] as const) {
    note(key.replace("_", " "), after[key] !== before[key]);
  }
}

export function prepareGenerationFromAgentPrompt(
  settings: GenerationSettings,
  options: AgentPromptPrepareOptions = {},
): AgentPromptPrepareResult {
  const applied: string[] = [];
  const hints: string[] = [];
  const rawPrompt = coercePromptText(settings.prompt).trim();

  let agentObj = rawPrompt.startsWith("{")
    ? tryParseAgentPromptObject(rawPrompt)
    : null;

  if (!agentObj) {
    const asRecord = settings as unknown as Record<string, unknown>;
    if (isAgentPromptPayload(asRecord)) {
      agentObj = asRecord;
    }
  }

  if (!agentObj) {
    return { settings: { ...settings }, applied, hints };
  }

  const patch = mergeAgentPromptDict(settings, agentObj);
  applyIdentityDefaults(patch, settings, agentObj, options, applied, hints);

  const next: GenerationSettings = { ...settings, ...patch };
  if (Array.isArray(next.negative_prompt)) {
    next.negative_prompt = coerceNegative(next.negative_prompt);
  }

  collectAppliedFields(settings, next, applied);

  return {
    settings: next,
    applied: [...new Set(applied)],
    hints,
  };
}

export function generationNeedsReferenceImage(
  settings: GenerationSettings,
  modelGallery: ModelGalleryItem[] = [],
): boolean {
  const input = (settings.input_image ?? settings.upscale_image ?? "").trim();
  if (input) return false;

  const active = findGalleryModel(modelGallery, settings.model ?? "");
  const family = (active?.family ?? "").toLowerCase();
  if (family.includes("kontext") || family.includes("qwen_image_edit")) {
    return true;
  }
  const editType = settings.edit_type ?? "auto";
  if (settings.use_case === "image_edit" && editType !== "auto") {
    return true;
  }
  if (
    settings.cn_selection === "Custom..." &&
    (settings.cn_type ?? "None") !== "None"
  ) {
    return true;
  }
  return false;
}
