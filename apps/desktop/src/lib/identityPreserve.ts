import type { ModelDependencyItem, ModelGalleryItem } from "./tauri-api";
import type { GenerationSettings } from "./tauri-api";
import {
  selectIdentityGenerateModel,
  type IdentityGenerateRoute,
} from "./model-selection";
import { qwenEdit2511LightningPatch } from "./qwenEditDefaults";
import { ipAdapterAssetsReady } from "./easyModeRouting";

export type IdentityMode =
  | "preserve_face"
  | "kontext"
  | "qwen_edit"
  | "ipadapter_faceid"
  | "auto";

const VALID_IDENTITY_MODES = new Set<IdentityMode>([
  "preserve_face",
  "kontext",
  "qwen_edit",
  "ipadapter_faceid",
  "auto",
]);

const LEGACY_IDENTITY_ALIASES: Record<string, IdentityMode> = {
  face: "preserve_face",
  faceid: "preserve_face",
  face_id: "preserve_face",
};

export function normalizeIdentityMode(
  value: string | undefined | null,
): IdentityMode | undefined {
  const key = (value ?? "").trim().toLowerCase();
  if (VALID_IDENTITY_MODES.has(key as IdentityMode)) {
    return key as IdentityMode;
  }
  return LEGACY_IDENTITY_ALIASES[key];
}

export function isIdentityPreservationActive(settings: GenerationSettings): boolean {
  return Boolean(
    settings.preserve_character ||
      settings.face_preservation ||
      normalizeIdentityMode(settings.identity_mode),
  );
}

export function faceIdAssetsReady(
  modelMissing: ModelDependencyItem[] = [],
  studioMissing: ModelDependencyItem[] = [],
  imagePromptMissing: ModelDependencyItem[] = [],
): boolean {
  if (!ipAdapterAssetsReady(modelMissing, studioMissing, imagePromptMissing)) {
    return false;
  }
  const haystack = [...modelMissing, ...studioMissing, ...imagePromptMissing]
    .map((item) =>
      [item.id, item.filename, item.relative, item.expected_path]
        .filter(Boolean)
        .join(" "),
    )
    .join(" ")
    .toLowerCase();
  const blockers = ["faceid", "face-id", "insightface"];
  return !blockers.some((token) => haystack.includes(token));
}

export function galleryHasFaceIdStack(gallery: ModelGalleryItem[]): boolean {
  const haystack = gallery
    .map((item) =>
      [item.engine_name, item.relative_path, item.category, item.family]
        .filter(Boolean)
        .join(" "),
    )
    .join(" ")
    .toLowerCase();
  return haystack.includes("faceid") || haystack.includes("face-id");
}

function referencePath(settings: GenerationSettings): string {
  return (
    settings.input_image?.trim() ||
    settings.reference_image?.trim() ||
    ""
  );
}

function patchForKontextIdentity(
  ref: string,
  model?: string,
): Partial<GenerationSettings> {
  return {
    reference_role: "restyle",
    workflow_mode: "generate",
    input_image: ref,
    reference_image: ref,
    preserve_character: true,
    face_preservation: true,
    identity_mode: "preserve_face",
    edit_type: "kontext",
    edit_strength: 0.92,
    cn_selection: "None",
    cn_type: "None",
    steps: 20,
    ...(model ? { model } : {}),
  };
}

function patchForQwenIdentity(
  ref: string,
  model?: string,
): Partial<GenerationSettings> {
  return {
    reference_role: "restyle",
    workflow_mode: "generate",
    input_image: ref,
    reference_image: ref,
    preserve_character: true,
    face_preservation: true,
    identity_mode: "preserve_face",
    edit_type: "qwen_edit",
    edit_strength: 1.0,
    cn_selection: "None",
    cn_type: "None",
    ...qwenEdit2511LightningPatch(),
    ...(model ? { model } : {}),
  };
}

function patchForFaceIdIdentity(ref: string): Partial<GenerationSettings> {
  return {
    reference_role: "image_prompt",
    workflow_mode: "ipadapter_faceid",
    reference_image: ref,
    input_image: undefined,
    preserve_character: true,
    face_preservation: true,
    identity_mode: "ipadapter_faceid",
    edit_type: "auto",
    cn_selection: "None",
    cn_type: "None",
  };
}

export function resolveIdentityRoute(
  settings: GenerationSettings,
  gallery: ModelGalleryItem[],
  options: {
    modelMissing?: ModelDependencyItem[];
    studioMissing?: ModelDependencyItem[];
    imagePromptMissing?: ModelDependencyItem[];
  } = {},
): {
  route: IdentityGenerateRoute | "img2img" | "none";
  model?: string;
  notice?: string;
} {
  if (!isIdentityPreservationActive(settings)) {
    return { route: "none" };
  }
  const ref = referencePath(settings);
  if (!ref) {
    return { route: "none" };
  }

  const mode = normalizeIdentityMode(settings.identity_mode) ?? "preserve_face";

  if (mode === "ipadapter_faceid") {
    const assetsReady =
      galleryHasFaceIdStack(gallery) &&
      faceIdAssetsReady(
        options.modelMissing,
        options.studioMissing,
        options.imagePromptMissing,
      );
    if (assetsReady) {
      return { route: "ipadapter_faceid" };
    }
    const routed = selectIdentityGenerateModel(gallery);
    if (routed) {
      return {
        route: routed.route,
        model: routed.engine_name,
        notice: "FaceID assets missing; using Kontext/Qwen identity instead.",
      };
    }
    return {
      route: "img2img",
      notice: "FaceID assets missing; using img2img fallback.",
    };
  }

  const routed = selectIdentityGenerateModel(gallery);
  if (routed) {
    return { route: routed.route, model: routed.engine_name };
  }
  return { route: "img2img" };
}

export function patchForKeepFace(
  enabled: boolean,
  settings: GenerationSettings,
): Partial<GenerationSettings> {
  if (!enabled) {
    return {
      preserve_character: false,
      face_preservation: false,
      identity_mode: undefined,
    };
  }
  return {
    preserve_character: true,
    face_preservation: true,
    identity_mode: settings.identity_mode === "ipadapter_faceid"
      ? "ipadapter_faceid"
      : "preserve_face",
  };
}

export function applyIdentityAtSubmit(
  settings: GenerationSettings,
  gallery: ModelGalleryItem[],
  options: {
    studioMode?: string;
    modelMissing?: ModelDependencyItem[];
    studioMissing?: ModelDependencyItem[];
    imagePromptMissing?: ModelDependencyItem[];
  } = {},
): GenerationSettings {
  if (settings.vary_amount || settings.enhance_auto_fix || settings.enhance_target) {
    return settings;
  }
  const studioMode = (options.studioMode ?? "generate").toLowerCase();
  if (studioMode !== "generate" && studioMode !== "agent") {
    return settings;
  }
  if (!isIdentityPreservationActive(settings)) {
    return settings;
  }

  const resolved = resolveIdentityRoute(settings, gallery, options);
  if (resolved.route === "none") {
    return settings;
  }

  const ref = referencePath(settings);
  if (!ref) {
    return settings;
  }

  let patch: Partial<GenerationSettings>;
  if (resolved.route === "kontext") {
    patch = patchForKontextIdentity(ref, resolved.model);
  } else if (resolved.route === "qwen_edit") {
    patch = patchForQwenIdentity(ref, resolved.model);
  } else if (resolved.route === "ipadapter_faceid") {
    patch = patchForFaceIdIdentity(ref);
  } else {
    patch = {
      reference_role: "restyle",
      workflow_mode: "generate",
      input_image: ref,
      reference_image: ref,
      preserve_character: true,
      face_preservation: true,
      identity_mode: "preserve_face",
      edit_type: "auto",
      cn_selection: "Custom...",
      cn_type: "img2img",
    };
  }

  return { ...settings, ...patch };
}
