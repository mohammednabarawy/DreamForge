import type { ReferenceRole } from "./referenceRole";
import { inferReferenceRole } from "./referenceRole";
import type { GenerationSettings } from "./tauri-api";
import type { StudioMode } from "./model-selection";

export type ReferenceSlot = {
  path: string;
  role: ReferenceRole;
  weight?: number;
  stop_at?: number;
  structure_type?: string;
};

export const MAX_REFERENCE_SLOTS = 4;
export const DEFAULT_SLOT_WEIGHT = 0.75;
export const DEFAULT_SLOT_STOP_AT = 1.0;

export type ReferenceSlotMixIssue = {
  code: string;
  message: string;
};

function clamp(value: number, min: number, max: number, fallback: number): number {
  if (!Number.isFinite(value)) return fallback;
  return Math.max(min, Math.min(max, value));
}

export function normalizeReferenceSlot(raw: Partial<ReferenceSlot>): ReferenceSlot | null {
  const path = (raw.path ?? "").trim();
  if (!path) return null;
  const role = (raw.role ?? "image_prompt") as ReferenceRole;
  return {
    path,
    role,
    weight: clamp(raw.weight ?? DEFAULT_SLOT_WEIGHT, 0, 2, DEFAULT_SLOT_WEIGHT),
    stop_at: clamp(raw.stop_at ?? DEFAULT_SLOT_STOP_AT, 0, 1, DEFAULT_SLOT_STOP_AT),
    structure_type: raw.structure_type?.trim() || undefined,
  };
}

export function legacySlotFromSettings(
  settings: GenerationSettings,
  studioMode: StudioMode = "generate",
): ReferenceSlot | null {
  const role = inferReferenceRole(settings, studioMode);
  const path =
    settings.reference_image?.trim() ||
    settings.input_image?.trim() ||
    settings.upscale_image?.trim() ||
    "";
  if (!path || !role) return null;
  const slot: ReferenceSlot = {
    path,
    role,
    weight: settings.reference_weight ?? settings.edit_strength ?? DEFAULT_SLOT_WEIGHT,
    stop_at: settings.cn_stop ?? DEFAULT_SLOT_STOP_AT,
  };
  if (role === "structure") {
    slot.structure_type = settings.cn_type ?? "canny";
  }
  return slot;
}

export function coerceReferenceSlots(
  settings: GenerationSettings,
  studioMode: StudioMode = "generate",
): ReferenceSlot[] {
  const raw = settings.references ?? [];
  const fromArray = raw
    .map((item) => normalizeReferenceSlot(item))
    .filter((item): item is ReferenceSlot => Boolean(item))
    .slice(0, MAX_REFERENCE_SLOTS);
  if (fromArray.length) return fromArray;
  const legacy = legacySlotFromSettings(settings, studioMode);
  return legacy ? [legacy] : [];
}

export function syncLegacyFromPrimarySlot(
  settings: GenerationSettings,
  slots: ReferenceSlot[],
): Partial<GenerationSettings> {
  const primary = slots[0];
  if (!primary) {
    return {
      input_image: undefined,
      reference_image: undefined,
      reference_role: undefined,
      upscale_image: undefined,
    };
  }
  const patch: Partial<GenerationSettings> = {
    references: slots,
    reference_role: primary.role,
    reference_weight: primary.weight,
    cn_stop: primary.stop_at,
  };
  if (primary.role === "image_prompt") {
    patch.reference_image = primary.path;
    patch.input_image = undefined;
    patch.workflow_mode = "ipadapter";
  } else if (primary.role === "restyle") {
    patch.input_image = primary.path;
    patch.reference_image = primary.path;
    patch.edit_strength = primary.weight ?? settings.edit_strength;
    patch.workflow_mode = "generate";
  } else if (primary.role === "structure") {
    patch.reference_image = primary.path;
    patch.input_image = undefined;
    patch.cn_selection = "Custom...";
    patch.cn_type = primary.structure_type ?? "canny";
    patch.cn_strength = primary.weight ?? 1;
    patch.workflow_mode = "controlnet";
  } else if (primary.role === "upscale") {
    patch.upscale_image = primary.path;
    patch.input_image = undefined;
  } else if (primary.role === "inpaint") {
    patch.input_image = primary.path;
  } else {
    patch.input_image = primary.path;
    patch.reference_image = primary.path;
  }
  return patch;
}

export function normalizeReferenceSettings(
  settings: GenerationSettings,
  studioMode: StudioMode = "generate",
): GenerationSettings {
  const slots = coerceReferenceSlots(settings, studioMode);
  if (!slots.length) return settings;
  return { ...settings, ...syncLegacyFromPrimarySlot(settings, slots) };
}

export function validateReferenceSlotMix(
  slots: ReferenceSlot[],
): ReferenceSlotMixIssue | null {
  if (slots.length > MAX_REFERENCE_SLOTS) {
    return {
      code: "too_many_slots",
      message: `At most ${MAX_REFERENCE_SLOTS} reference slots are supported.`,
    };
  }
  const roles = slots.map((s) => s.role);
  const structure = roles.filter((r) => r === "structure").length;
  // restyle (img2img) and source_edit (Kontext/Qwen) are both single base
  // images. A base may combine with extra image-prompt references (img2img /
  // edit + IP-Adapter or Kontext reference latents is valid), but two base
  // images make no sense and base + ControlNet has no defined composition.
  const base = roles.filter((r) => r === "restyle" || r === "source_edit").length;
  if (base > 1) {
    return {
      code: "multi_base",
      message: "Only one source / base image is supported.",
    };
  }
  if (structure > 1) {
    return {
      code: "multi_structure",
      message: "Only one structure slot is supported.",
    };
  }
  if (base > 0 && structure > 0) {
    return {
      code: "base_structure_mixed",
      message: "Source / base cannot combine with a structure slot.",
    };
  }
  return null;
}

export function resolveReferenceComposition(slots: ReferenceSlot[]): {
  mode: string;
  ipadapterSlots?: ReferenceSlot[];
  structureSlot?: ReferenceSlot;
} {
  const ipa = slots.filter((s) => s.role === "image_prompt");
  const structure = slots.filter((s) => s.role === "structure");
  const base = slots.filter(
    (s) => s.role === "restyle" || s.role === "source_edit",
  );
  // A restyle/source base keeps the workflow on img2img/Kontext/edit; any extra
  // image-prompt slots ride along as reference latents handled per-model.
  if (base.length) {
    return ipa.length
      ? { mode: "base_reference", ipadapterSlots: ipa }
      : { mode: base[0].role };
  }
  if (ipa.length && structure.length) {
    return {
      mode: "ipadapter_controlnet",
      ipadapterSlots: ipa,
      structureSlot: structure[0],
    };
  }
  if (ipa.length > 1) return { mode: "ipadapter_multi", ipadapterSlots: ipa };
  if (ipa.length === 1) return { mode: "ipadapter", ipadapterSlots: ipa };
  if (structure.length) return { mode: "controlnet", structureSlot: structure[0] };
  return { mode: slots[0]?.role ?? "none" };
}

export function patchPrimaryReferenceSlot(
  settings: GenerationSettings,
  slot: ReferenceSlot,
  studioMode: StudioMode = "generate",
): Partial<GenerationSettings> {
  const slots = [...coerceReferenceSlots(settings, studioMode)];
  if (slots.length) slots[0] = slot;
  else slots.push(slot);
  return syncLegacyFromPrimarySlot(settings, slots);
}

export function appendReferenceSlot(
  settings: GenerationSettings,
  slot: ReferenceSlot,
  studioMode: StudioMode = "generate",
): Partial<GenerationSettings> | null {
  const slots = [...coerceReferenceSlots(settings, studioMode)];
  if (slots.length >= MAX_REFERENCE_SLOTS) return null;
  if (slots.some((item) => item.path === slot.path)) return null;
  slots.push(slot);
  const issue = validateReferenceSlotMix(slots);
  if (issue) return null;
  return syncLegacyFromPrimarySlot(settings, slots);
}

export function updateReferenceSlotAt(
  settings: GenerationSettings,
  index: number,
  patch: Partial<ReferenceSlot>,
  studioMode: StudioMode = "generate",
): Partial<GenerationSettings> | null {
  const slots = [...coerceReferenceSlots(settings, studioMode)];
  if (index < 0 || index >= slots.length) return null;
  const merged = normalizeReferenceSlot({ ...slots[index], ...patch });
  if (!merged) return null;
  slots[index] = merged;
  const issue = validateReferenceSlotMix(slots);
  if (issue) return null;
  return syncLegacyFromPrimarySlot(settings, slots);
}

export function removeReferenceSlotAt(
  settings: GenerationSettings,
  index: number,
  studioMode: StudioMode = "generate",
): Partial<GenerationSettings> {
  const slots = [...coerceReferenceSlots(settings, studioMode)];
  slots.splice(index, 1);
  if (!slots.length) {
    return {
      references: undefined,
      input_image: undefined,
      reference_image: undefined,
      reference_role: undefined,
      upscale_image: undefined,
      reference_images: undefined,
    };
  }
  return syncLegacyFromPrimarySlot(settings, slots);
}

export function applyReferencesAtSubmit(
  settings: GenerationSettings,
  studioMode: StudioMode = "generate",
): GenerationSettings {
  const normalized = normalizeReferenceSettings(settings, studioMode);
  const slots = coerceReferenceSlots(normalized, studioMode);
  const composition = resolveReferenceComposition(slots);
  if (composition.mode === "ipadapter_controlnet") {
    return {
      ...normalized,
      workflow_mode: "ipadapter_controlnet",
      cn_selection: "Custom...",
      cn_type: composition.structureSlot?.structure_type ?? normalized.cn_type ?? "canny",
      cn_strength: composition.structureSlot?.weight ?? normalized.cn_strength ?? 1,
      cn_stop: composition.structureSlot?.stop_at ?? normalized.cn_stop ?? DEFAULT_SLOT_STOP_AT,
    };
  }
  if (composition.mode === "ipadapter_multi") {
    return { ...normalized, workflow_mode: "ipadapter" };
  }
  return normalized;
}

export function slotSupportsWeightControls(role: ReferenceRole): boolean {
  return role === "image_prompt" || role === "structure";
}

export function slotSupportsStopAt(role: ReferenceRole): boolean {
  return role === "image_prompt" || role === "structure";
}
