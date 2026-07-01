import type { StudioMode } from "./model-selection";

export type GenerationSection =
  | "creativeTemplate"
  | "upscalePanel"
  | "editFamilyPanel"
  | "toolboxPanel"
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
  isEdit: boolean;
  isInpaint: boolean;
  isUpscale: boolean;
  isToolbox: boolean;
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
}): GenerationTabContext {
  const studioMode = input.studioMode;
  const activeModelLower = input.activeModelLabel.toLowerCase();
  const isModernModel =
    activeModelLower.includes("flux") ||
    activeModelLower.includes("qwen") ||
    activeModelLower.includes("hidream") ||
    activeModelLower.includes("sd3") ||
    activeModelLower.includes("ideogram") ||
    activeModelLower.includes("krea");

  return {
    studioMode,
    advancedMode: input.advancedMode,
    isModernModel,
    isQwenModel: input.isQwenModel,
    isIdeogramModel: activeModelLower.includes("ideogram"),
    showGenerateLikeSettings: input.showGenerateLikeSettings,
    showEditStrength: input.showEditStrength,
    customPerf: input.customPerf,
    isEdit: studioMode === "edit",
    isInpaint: studioMode === "inpaint",
    isUpscale: studioMode === "upscale",
    isToolbox: studioMode === "toolbox",
    isGenerateFamily: isGenerateFamilyMode(studioMode),
  };
}

/** Whether a Generation-tab block should render for the active studio mode. */
export function generationSectionVisible(
  section: GenerationSection,
  ctx: GenerationTabContext,
): boolean {
  switch (section) {
    case "creativeTemplate":
      return Boolean(ctx.advancedMode) && !ctx.isUpscale;
    case "upscalePanel":
      return ctx.isUpscale;
    case "editFamilyPanel":
      return ctx.isEdit || ctx.isInpaint;
    case "toolboxPanel":
      return ctx.isToolbox;
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
        ctx.advancedMode &&
          ((ctx.isGenerateFamily && ctx.showGenerateLikeSettings) ||
            ctx.isEdit ||
            ctx.isInpaint ||
            ctx.isToolbox),
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
    return ["discover", "models", "settings"];
  }
  if (simpleInspectorLocked) {
    return ["discover", "settings", "models"];
  }
  if (isInpaint) {
    return powerUserInspector
      ? ["discover", "models", "loras", "settings", "automation"]
      : ["discover", "models", "settings"];
  }
  if (studioMode === "edit" || studioMode === "toolbox") {
    return powerUserInspector
      ? ["discover", "models", "loras", "settings", "automation"]
      : ["discover", "models", "settings"];
  }
  if (isGenerateFamilyMode(studioMode)) {
    return powerUserInspector
      ? ["discover", "models", "loras", "styles", "settings", "automation"]
      : ["discover", "models", "styles", "settings"];
  }
  return ["discover", "models", "settings"];
}

export const MODE_AUTO_SUMMARY: Partial<Record<string, string>> = {
  generate:
    "Auto: best create route · performance preset · VRAM detect · optional reference guidance",
  edit: "Auto: best edit model · describe the change · performance preset",
  inpaint: "Auto: Flux Fill inpaint · mask from canvas · named intent presets",
  upscale: "Auto: SDXL upscale route · tile settings tuned for quality",
  toolbox: "Auto: Native tools and custom ComfyUI workflow imports",
};
