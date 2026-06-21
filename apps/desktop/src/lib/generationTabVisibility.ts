import type { StudioMode } from "./model-selection";

export type GenerationSection =
  | "creativeTemplate"
  | "referencePack"
  | "identity"
  | "upscalePanel"
  | "editFamilyPanel"
  | "performance"
  | "aspectRatio"
  | "imageNumber"
  | "autoNegative"
  | "promptSeed"
  | "customSampling"
  | "controlNet"
  | "qwen"
  | "promptHelpers"
  | "hardware";

export type GenerationTabContext = {
  studioMode: StudioMode | string;
  advancedMode?: boolean;
  isModernModel: boolean;
  isQwenModel: boolean;
  isIdeogramModel: boolean;
  showGenerateLikeSettings: boolean;
  showEditStrength: boolean;
  customPerf: boolean;
  hasReferencePack: boolean;
  hasIdentity: boolean;
  isEdit: boolean;
  isInpaint: boolean;
  isUpscale: boolean;
  isExtract: boolean;
  isGenerateFamily: boolean;
};

export function isGenerateFamilyMode(mode: string): boolean {
  return mode === "generate" || mode === "agent";
}

export function buildGenerationTabContext(input: {
  studioMode: string;
  advancedMode?: boolean;
  activeModelLabel: string;
  isQwenModel: boolean;
  showGenerateLikeSettings: boolean;
  showEditStrength: boolean;
  customPerf: boolean;
  referencePackSubtitle?: string;
  identitySubtitle?: string;
}): GenerationTabContext {
  const studioMode = input.studioMode;
  const activeModelLower = input.activeModelLabel.toLowerCase();
  const isModernModel =
    activeModelLower.includes("flux") ||
    activeModelLower.includes("qwen") ||
    activeModelLower.includes("hidream") ||
    activeModelLower.includes("sd3") ||
    activeModelLower.includes("ideogram");

  return {
    studioMode,
    advancedMode: input.advancedMode,
    isModernModel,
    isQwenModel: input.isQwenModel,
    isIdeogramModel: activeModelLower.includes("ideogram"),
    showGenerateLikeSettings: input.showGenerateLikeSettings,
    showEditStrength: input.showEditStrength,
    customPerf: input.customPerf,
    hasReferencePack: Boolean(input.referencePackSubtitle?.trim()),
    hasIdentity: Boolean(input.identitySubtitle?.trim()),
    isEdit: studioMode === "edit",
    isInpaint: studioMode === "inpaint",
    isUpscale: studioMode === "upscale",
    isExtract: studioMode === "extract",
    isGenerateFamily: isGenerateFamilyMode(studioMode),
  };
}

/** Whether a Generation-tab block should render for the active studio mode. */
export function generationSectionVisible(
  section: GenerationSection,
  ctx: GenerationTabContext,
): boolean {
  if (ctx.isExtract) {
    return false;
  }

  switch (section) {
    case "creativeTemplate":
      return Boolean(ctx.advancedMode) && !ctx.isUpscale;
    case "referencePack":
      return ctx.hasReferencePack && (ctx.isGenerateFamily || ctx.isEdit);
    case "identity":
      return ctx.hasIdentity && (ctx.isGenerateFamily || ctx.isEdit);
    case "upscalePanel":
      return ctx.isUpscale;
    case "editFamilyPanel":
      return ctx.isEdit || ctx.isInpaint;
    case "performance":
      return !ctx.isUpscale;
    case "aspectRatio":
      return ctx.isGenerateFamily && ctx.showGenerateLikeSettings;
    case "imageNumber":
      return ctx.isGenerateFamily && ctx.showGenerateLikeSettings;
    case "autoNegative":
      return ctx.isGenerateFamily && !ctx.isModernModel;
    case "promptSeed":
      return !ctx.isUpscale;
    case "customSampling":
      return Boolean(
        (ctx.isGenerateFamily && ctx.showGenerateLikeSettings) ||
          (ctx.advancedMode && (ctx.isEdit || ctx.isInpaint)),
      );
    case "controlNet":
      return ctx.isGenerateFamily && !ctx.isModernModel && Boolean(ctx.advancedMode);
    case "qwen":
      return ctx.isQwenModel && (ctx.isEdit || ctx.isGenerateFamily) && Boolean(ctx.advancedMode);
    case "promptHelpers":
      return ctx.isGenerateFamily && !ctx.isModernModel && Boolean(ctx.advancedMode);
    case "hardware":
      return Boolean(ctx.advancedMode) && !ctx.isUpscale;
    default:
      return false;
  }
}

export type InspectorTabId =
  | "discover"
  | "models"
  | "loras"
  | "styles"
  | "refs"
  | "settings"
  | "automation";

export function inspectorTabsForMode(input: {
  studioMode: StudioMode | string;
  simpleInspectorLocked: boolean;
  powerUserInspector: boolean;
  isEditFamily: boolean;
  isInpaint: boolean;
  isUpscale: boolean;
}): InspectorTabId[] {
  const { studioMode, simpleInspectorLocked, powerUserInspector, isInpaint, isUpscale } = input;

  if (isUpscale) {
    return ["models", "settings"];
  }
  if (studioMode === "extract") {
    return ["settings"];
  }
  if (simpleInspectorLocked) {
    return ["settings", "models", "refs"];
  }
  if (isInpaint) {
    return powerUserInspector
      ? ["models", "loras", "settings", "refs", "automation"]
      : ["models", "settings", "refs"];
  }
  if (studioMode === "edit") {
    return powerUserInspector
      ? ["models", "loras", "settings", "refs", "automation"]
      : ["models", "settings", "refs"];
  }
  if (isGenerateFamilyMode(studioMode)) {
    return powerUserInspector
      ? ["models", "loras", "styles", "settings", "refs", "automation"]
      : ["models", "styles", "settings", "refs"];
  }
  return ["models", "settings", "refs"];
}

export const MODE_AUTO_SUMMARY: Partial<Record<string, string>> = {
  generate:
    "Auto: model route · performance preset · VRAM detect · seed (random default)",
  edit: "Auto: Flux Kontext route · edit graph · performance preset · VRAM detect",
  inpaint: "Auto: Flux Fill route · inpaint graph · mask from canvas · performance preset",
  agent: "Auto: planned route · performance preset · VRAM detect",
};
