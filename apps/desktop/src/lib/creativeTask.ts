import type { GenerationSettings, ModelGalleryItem } from "./tauri-api";
import { resolveCreativeTask } from "./studioBridge";
import {
  findGalleryModel,
  modelBasename,
  selectCuratedModelForMode,
  type StudioMode,
} from "./model-selection";
import {
  buildEditRoutingPatch,
  DEFAULT_FLUX_KONTEXT_EDIT_MODEL,
  DEFAULT_QWEN_EDIT_MODEL,
  isEditCapableModel,
  isQwenEditModel,
  selectFluxKontextEditModel,
  selectQwenEditModel,
} from "./editModel";
import { isPhotoRestoreTask, patchForPhotoRestoreTask } from "./photoRestore";
import { ideogram4SettingsDefaults } from "./ideogram4Ui";
import { qwenEdit2511LightningPatch } from "./qwenEditDefaults";
import {
  DEFAULT_FLUX_FILL_MODEL,
  enforceInpaintJobSettings,
  isInpaintCapableModel,
  selectCuratedInpaintModel,
} from "./inpaintModel";
import { resolveVramProfile, type VramProfile } from "./vramProfiles";
import { applyCreativeTemplateDefaults } from "./creativeTemplates";
import {
  applyUpscaleFallbacks,
  UPSCALE_SETTINGS_DEFAULTS,
} from "./upscaleDefaults";
import { applyUpscalePresetAtSubmit, patchForUpscalePreset } from "./upscalePresets";
import { applyAutoEnhanceAtSubmit } from "./autoEnhance";
import { applyHiDreamPerformanceAtSubmit } from "./hidreamPerformance";
import { selectCuratedUpscaleModel } from "./upscaleModel";

export type CreativeTaskContext = {
  studioMode: StudioMode;
  gallery: ModelGalleryItem[];
  settings: GenerationSettings;
  vramProfile?: VramProfile | string;
  vramGb?: number | null;
  mpsAvailable?: boolean | null;
  advancedMode?: boolean;
  selectedImage?: string;
  userPickedModel?: boolean;
};

function vramTier(profile: VramProfile): "5gb" | "8gb" | "16gb" {
  if (profile === "5gb" || profile === "mps_4gb") return "5gb";
  if (profile === "8gb" || profile === "mps_8gb") return "8gb";
  return "16gb";
}

/** Tighten steps / cfg on low-VRAM tiers (mirrors backend apply_vram_quality_defaults). */
export function applyVramQualityDefaults(
  settings: GenerationSettings,
  studioMode: StudioMode,
  vramProfile: VramProfile | string | undefined,
  vramGb: number | null = null,
  mpsAvailable: boolean | null = null,
): GenerationSettings {
  const resolved = resolveVramProfile(vramProfile, vramGb, mpsAvailable);
  const tier = vramTier(resolved);
  const next = { ...settings };
  const steps = next.steps ?? 20;
  const cfg = next.cfg_scale ?? 7;

  if (tier === "5gb") {
    if (studioMode === "edit" && next.edit_type === "qwen_edit") {
      next.performance = "Lightning";
      next.steps = Math.min(steps, 8);
      next.cfg_scale = Math.min(cfg, 1.5);
    } else if (studioMode === "edit") {
      next.steps = Math.min(steps, 12);
      next.cfg_scale = Math.min(cfg, 5);
    } else if (studioMode === "inpaint") {
      next.steps = Math.min(steps, 12);
    } else if (studioMode === "generate") {
      next.steps = Math.min(steps, 20);
    }
  } else if (tier === "8gb" && (studioMode === "edit" || studioMode === "inpaint")) {
    next.steps = Math.min(steps, 20);
  }
  return next;
}

export function enforceEditJobSettings(
  settings: GenerationSettings,
  studioMode: StudioMode,
  gallery: ModelGalleryItem[],
  advancedMode?: boolean,
): GenerationSettings {
  if (studioMode !== "edit") return settings;
  if (isPhotoRestoreTask(settings)) {
    const restorePatch = patchForPhotoRestoreTask(settings, gallery);
    return {
      ...settings,
      ...restorePatch,
      upscale_image: undefined,
      upscale_method: undefined,
      inpaint_mask_path: undefined,
    };
  }
  if ((settings.edit_task ?? "").toLowerCase() === "outfit_transfer") {
    const hasMask = Boolean(settings.inpaint_mask_path?.trim());
    if (hasMask) {
      return {
        ...settings,
        model:
          selectCuratedInpaintModel(gallery) ||
          settings.model ||
          DEFAULT_FLUX_FILL_MODEL,
        style: "image_edit",
        edit_type: "inpaint",
        cn_selection: "Custom...",
        cn_type: "inpaint",
        inpaint_intent: "modify_content",
        edit_strength: settings.edit_strength ?? 1,
        upscale_image: undefined,
        upscale_method: undefined,
      };
    }
    const qwenPatch = qwenEdit2511LightningPatch();
    const requestedQwenMode = (settings.qwen_edit_mode ?? "").trim().toLowerCase();
    return {
      ...settings,
      ...qwenPatch,
      model: selectQwenEditModel(gallery) || DEFAULT_QWEN_EDIT_MODEL,
      qwen_edit_mode:
        requestedQwenMode && requestedQwenMode !== "auto"
          ? settings.qwen_edit_mode
          : "plus",
      upscale_image: undefined,
      upscale_method: undefined,
      inpaint_mask_path: undefined,
    };
  }
  const current = gallery.find((item) => item.engine_name === settings.model);
  const defaultModel =
    selectFluxKontextEditModel(gallery) || DEFAULT_FLUX_KONTEXT_EDIT_MODEL;
  const userModel = settings.model?.trim();
  const userPickedCapable =
    Boolean(userModel) &&
    Boolean(current) &&
    isEditCapableModel(current!);
  const effectiveModel =
    userPickedCapable || (advancedMode && userModel)
      ? userModel!
      : userModel || defaultModel;
  const effectiveItem =
    gallery.find((item) => item.engine_name === effectiveModel) ?? current;
  return {
    ...settings,
    model: effectiveModel,
    style: settings.style ?? "image_edit",
    ...buildEditRoutingPatch(effectiveItem),
    upscale_image: undefined,
    upscale_method: undefined,
    inpaint_mask_path: undefined,
  };
}

export function enforceUpscaleJobSettings(
  settings: GenerationSettings,
  studioMode: StudioMode,
): GenerationSettings {
  if (studioMode !== "upscale") return settings;
  if (settings.enhance_auto_fix || settings.enhance_target) {
    return applyAutoEnhanceAtSubmit({
      ...settings,
      style: "image_edit",
      inpaint_mask_path: undefined,
    });
  }
  return applyUpscalePresetAtSubmit({
    ...settings,
    ...applyUpscaleFallbacks(settings),
    style: "image_edit",
    edit_type: "auto",
    cn_selection: "Custom...",
    cn_type: "upscale",
    input_image: undefined,
    inpaint_mask_path: undefined,
  });
}

/** Unified submit guard for Create / Edit / Fix region / Enhance. */
export function enforceCreativeTaskSettings(
  settings: GenerationSettings,
  ctx: Omit<CreativeTaskContext, "settings">,
): GenerationSettings {
  const { studioMode, gallery, advancedMode, vramProfile, vramGb, mpsAvailable } =
    ctx;
  let next = applyCreativeTemplateDefaults(settings, studioMode);
  if (studioMode === "edit") {
    next = enforceEditJobSettings(next, studioMode, gallery, advancedMode);
  } else if (studioMode === "inpaint") {
    next = enforceInpaintJobSettings(next, studioMode, gallery, advancedMode);
  } else if (studioMode === "upscale") {
    next = enforceUpscaleJobSettings(next, studioMode);
  }
  if (next.post_upscale && (studioMode === "edit" || studioMode === "inpaint")) {
    next = {
      ...next,
      upscale_image: undefined,
      upscale_method: undefined,
      ...applyUpscaleFallbacks(next),
    };
  }
  if (studioMode === "generate" || studioMode === "agent") {
    const modelItem = gallery.find((item) => item.engine_name === next.model);
    next = applyHiDreamPerformanceAtSubmit(
      next,
      modelItem?.family,
      next.model,
    );
  }
  return applyVramQualityDefaults(
    next,
    studioMode,
    vramProfile ?? settings.vram_profile,
    vramGb ?? null,
    mpsAvailable ?? null,
  );
}

/** History selection must not override an explicit inpaint/edit source image. */
export function selectedImageForCreativeTask(
  studioMode: StudioMode,
  settings: GenerationSettings,
  historyImage?: string,
): string {
  const history = (historyImage ?? "").trim();
  if (studioMode === "inpaint" || studioMode === "edit") {
    return (settings.input_image ?? history).trim();
  }
  if (studioMode === "upscale") {
    return (settings.upscale_image ?? settings.input_image ?? history).trim();
  }
  return history || (settings.input_image ?? "").trim();
}

/** Backend-authoritative routing for edit / inpaint / upscale tasks. */
export async function enforceCreativeTaskSettingsRemote(
  settings: GenerationSettings,
  ctx: Omit<CreativeTaskContext, "settings">,
): Promise<GenerationSettings> {
  const {
    studioMode,
    gallery,
    advancedMode,
    vramProfile,
    vramGb,
    mpsAvailable,
    selectedImage,
    userPickedModel,
  } = ctx;

  if (studioMode === "generate" || studioMode === "agent") {
    return enforceCreativeTaskSettings(settings, ctx);
  }

  try {
    const res = await resolveCreativeTask({
      studio_mode: studioMode,
      settings,
      model_gallery: gallery,
      vram_profile: vramProfile ?? settings.vram_profile ?? null,
      advanced_mode: advancedMode ?? false,
      user_picked_model: userPickedModel ?? false,
      selected_image: selectedImageForCreativeTask(studioMode, settings, selectedImage),
      enforce: true,
    });
    if (res.patch) {
      const merged = { ...settings, ...res.patch };
      return applyVramQualityDefaults(
        merged,
        studioMode,
        vramProfile ?? settings.vram_profile,
        vramGb ?? null,
        mpsAvailable ?? null,
      );
    }
  } catch {
    /* fall back to local guards */
  }
  return enforceCreativeTaskSettings(settings, ctx);
}

export type StudioModeSwitchInput = CreativeTaskContext & {
  previousMode: StudioMode;
  userPickedModel: boolean;
};

export type StudioModeSwitchPlan = {
  patch: Partial<GenerationSettings>;
  routedModel: string;
  routedModelItem?: ModelGalleryItem;
  profileItem?: ModelGalleryItem;
  useIdeogramRoute: boolean;
  useQwenEditRoute: boolean;
  refUpdates: {
    userPickedModel?: boolean;
    userPickedLoras?: boolean;
    userPickedStyle?: boolean;
  };
  statusMessage: string;
};

function studioModeDefaultStatus(
  mode: StudioMode,
  routedModel: string,
  advancedMode?: boolean,
): string {
  const routedLabel = modelBasename(routedModel);
  if (mode === "inpaint") {
    return routedModel
      ? `Inpaint mode - ${routedLabel} selected. Pick any Flux Fill or SDXL inpaint checkpoint in the inspector.`
      : "Inpaint mode - install Flux Fill or an SDXL inpaint checkpoint";
  }
  if (mode === "upscale") {
    return advancedMode
      ? `Enhance mode - default SDXL upscale (${routedLabel}). Pro: pick any checkpoint including Flux.`
      : routedModel
        ? `Enhance mode - SDXL upscale defaults (${routedLabel}). SDXL checkpoints work best with Ultimate SD Upscale.`
        : "Enhance mode - install an SDXL checkpoint for Ultimate SD Upscale";
  }
  if (mode === "edit") {
    return routedModel
      ? `Edit mode - default edit model selected (${routedLabel}). User overrides stay visible in the inspector.`
      : "Edit mode - default edit model is missing; review the asset download prompt";
  }
  return `${mode[0].toUpperCase()}${mode.slice(1)} mode - configured defaults are applied for this mode`;
}

/** Settings patch + side-effect hints when switching to edit / inpaint / upscale. */
export function planStudioModeSwitch(
  input: StudioModeSwitchInput,
): StudioModeSwitchPlan {
  const {
    studioMode: mode,
    previousMode,
    gallery,
    settings,
    selectedImage,
    userPickedModel,
    advancedMode,
  } = input;

  const refUpdates: StudioModeSwitchPlan["refUpdates"] = {};

  const routedModel = selectCuratedModelForMode(
    mode,
    gallery,
    settings.model,
  );
  const routedModelItem = routedModel
    ? findGalleryModel(gallery, routedModel)
    : undefined;
  const routedFamily = (routedModelItem?.family ?? "").toLowerCase();
  const useIdeogramRoute = routedFamily === "ideogram4";
  const useQwenEditRoute =
    mode === "edit" &&
    routedModelItem != null &&
    (routedFamily === "qwen_image_edit" || isQwenEditModel(routedModelItem));
  const effectiveModel =
    routedModel ||
    (mode === "inpaint"
      ? DEFAULT_FLUX_FILL_MODEL
      : mode === "edit"
        ? DEFAULT_FLUX_KONTEXT_EDIT_MODEL
        : "");

  const patch: Partial<GenerationSettings> = {
    model: effectiveModel || routedModel,
    style: "image_edit",
    performance: "Lightning",
  };
  if (useIdeogramRoute) {
    Object.assign(patch, ideogram4SettingsDefaults());
  }

  if (mode === "edit") {
    const enteringEdit = previousMode !== "edit";
    if (enteringEdit) {
      refUpdates.userPickedModel = false;
      refUpdates.userPickedLoras = false;
      refUpdates.userPickedStyle = false;
      patch.lora = [];
    }
    const currentItem = findGalleryModel(gallery, settings.model ?? "");
    const manualEdit =
      userPickedModel &&
      Boolean(currentItem) &&
      isEditCapableModel(currentItem!);
    const editModelItem = manualEdit
      ? currentItem
      : (routedModelItem ?? findGalleryModel(gallery, effectiveModel));
    patch.model = manualEdit ? settings.model : effectiveModel || routedModel;
    if (!manualEdit) {
      refUpdates.userPickedModel = false;
    }
    Object.assign(patch, buildEditRoutingPatch(editModelItem));
    if (useIdeogramRoute) {
      Object.assign(patch, ideogram4SettingsDefaults());
    } else if (
      useQwenEditRoute ||
      (editModelItem && isQwenEditModel(editModelItem))
    ) {
      Object.assign(patch, qwenEdit2511LightningPatch());
      patch.performance = "Lightning";
    } else {
      patch.performance = "Lightning";
      patch.steps = Math.min(Math.max(settings.steps ?? 20, 20), 28);
    }
    patch.upscale_image = undefined;
    patch.upscale_method = undefined;
    patch.inpaint_mask_path = undefined;
    const src = (selectedImage ?? settings.input_image ?? "").trim();
    if (src) patch.input_image = src;
  }

  if (mode === "inpaint") {
    const enteringInpaint = previousMode !== "inpaint";
    const prevInput = settings.input_image?.trim() ?? "";
    const newInput = (selectedImage ?? settings.input_image ?? "").trim();
    const sameInput = Boolean(newInput && newInput === prevInput);

    patch.edit_type = "inpaint";
    patch.edit_strength = settings.edit_strength ?? 0.9;
    patch.cn_selection = "Custom...";
    patch.cn_type = "inpaint";
    patch.steps = Math.min(Math.max(settings.steps ?? 20, 20), 28);
    patch.upscale_image = undefined;
    patch.upscale_method = undefined;
    if (newInput) patch.input_image = newInput;
    if (!sameInput) {
      patch.inpaint_mask_path = undefined;
    }
    if (enteringInpaint) {
      refUpdates.userPickedModel = false;
      refUpdates.userPickedLoras = false;
      refUpdates.userPickedStyle = false;
      patch.lora = [];
    }
    const currentItem = findGalleryModel(gallery, settings.model ?? "");
    const manualInpaint =
      userPickedModel &&
      Boolean(currentItem) &&
      isInpaintCapableModel(currentItem!);
    patch.model = manualInpaint
      ? settings.model
      : effectiveModel || selectCuratedInpaintModel(gallery);
    if (!manualInpaint) {
      refUpdates.userPickedModel = false;
    }
  }

  if (mode === "upscale") {
    const enteringUpscale = previousMode !== "upscale";
    if (enteringUpscale) {
      Object.assign(patch, UPSCALE_SETTINGS_DEFAULTS, patchForUpscalePreset("2x"));
      refUpdates.userPickedModel = false;
      refUpdates.userPickedLoras = false;
      refUpdates.userPickedStyle = false;
      patch.lora = [];
    } else {
      Object.assign(patch, applyUpscaleFallbacks(settings));
      patch.style = "image_edit";
      patch.edit_type = "auto";
      patch.cn_selection = "Custom...";
      patch.cn_type = "upscale";
    }
    patch.input_image = undefined;
    patch.inpaint_mask_path = undefined;
    const currentItem = findGalleryModel(gallery, settings.model ?? "");
    const manualUpscale = userPickedModel && Boolean(currentItem);
    const upscaleModel = selectCuratedUpscaleModel(gallery);
    patch.model = manualUpscale ? settings.model : upscaleModel || effectiveModel || routedModel;
    if (!manualUpscale) {
      refUpdates.userPickedModel = false;
    }
    const src = (
      selectedImage ??
      settings.upscale_image ??
      settings.input_image ??
      ""
    ).trim();
    if (src) patch.upscale_image = src;
  }

  if (mode !== "inpaint" && mode !== "edit" && mode !== "upscale") {
    refUpdates.userPickedModel = false;
    refUpdates.userPickedLoras = false;
    refUpdates.userPickedStyle = false;
  }

  const profileItem =
    mode === "edit"
      ? (findGalleryModel(gallery, patch.model ?? "") ?? routedModelItem)
      : routedModelItem;

  return {
    patch,
    routedModel,
    routedModelItem,
    profileItem,
    useIdeogramRoute,
    useQwenEditRoute,
    refUpdates,
    statusMessage: studioModeDefaultStatus(
      mode,
      effectiveModel || routedModel,
      advancedMode,
    ),
  };
}

/** Mode-switch patch for edit / inpaint / upscale (delegates to planStudioModeSwitch). */
export function resolveCreativeTaskPatch(
  ctx: CreativeTaskContext & {
    previousMode?: StudioMode;
    userPickedModel?: boolean;
  },
): Partial<GenerationSettings> {
  const { studioMode, previousMode, userPickedModel, ...rest } = ctx;
  if (studioMode === "generate" || studioMode === "agent") {
    return {};
  }
  return planStudioModeSwitch({
    studioMode,
    previousMode: previousMode ?? studioMode,
    userPickedModel: userPickedModel ?? false,
    ...rest,
  }).patch;
}

export function isManualCreativeModel(
  item: ModelGalleryItem | undefined,
  studioMode: StudioMode,
): boolean {
  if (!item) return false;
  if (studioMode === "inpaint") return isInpaintCapableModel(item);
  if (studioMode === "edit") {
    return isEditCapableModel(item);
  }
  return true;
}
