/** Mirrors ssitu/ComfyUI_UltimateSDUpscale `USDU_base_inputs()` widget metadata. */

export const ULTIMATE_SD_NODE = {
  title: "Ultimate SD Upscale",
  category: "image/upscaling",
  description:
    "Upscales an image and runs image-to-image on tiles from the input image.",
} as const;

export const UPSCALE_MODE_TYPES = ["Linear", "Chess", "None"] as const;
export type UpscaleModeType = (typeof UPSCALE_MODE_TYPES)[number];

export const SEAM_FIX_MODES = [
  "None",
  "Band Pass",
  "Half Tile",
  "Half Tile + Intersections",
] as const;
export type SeamFixMode = (typeof SEAM_FIX_MODES)[number];

export const UPSCALE_MODEL_DEFAULT = "4x-UltraSharp.pth";

/** Comfy node ports DreamForge wires automatically (not shown as editable widgets). */
export const ULTIMATE_SD_AUTO_INPUT_KEYS = [
  "image",
  "model",
  "positive",
  "negative",
  "vae",
  "upscale_model",
  "seed",
  "steps",
  "cfg",
  "sampler_name",
  "scheduler",
  "force_uniform_tiles",
  "tiled_decode",
  "batch_size",
  "seam_fix_denoise",
  "seam_fix_width",
  "seam_fix_mask_blur",
  "seam_fix_padding",
] as const;

export type NodeWidgetSpec = {
  key: string;
  label: string;
  tooltip: string;
  kind: "float" | "int" | "enum" | "boolean" | "text";
  min?: number;
  max?: number;
  step?: number;
  options?: readonly string[];
  defaultValue: number | string | boolean;
};

/** User-tunable widgets only — DreamForge handles the rest. */
export const ULTIMATE_SD_USER_WIDGETS: NodeWidgetSpec[] = [
  {
    key: "upscale_by",
    label: "upscale_by",
    tooltip: "The factor to upscale the image by.",
    kind: "float",
    min: 0.05,
    max: 4,
    step: 0.05,
    defaultValue: 2,
  },
  {
    key: "denoise",
    label: "denoise",
    tooltip: "The denoising strength to use for each tile.",
    kind: "float",
    min: 0,
    max: 1,
    step: 0.01,
    defaultValue: 0.25,
  },
  {
    key: "mode_type",
    label: "mode_type",
    tooltip: "The tiling order to use for the redraw step.",
    kind: "enum",
    options: UPSCALE_MODE_TYPES,
    defaultValue: "Chess",
  },
  {
    key: "tile_width",
    label: "tile_width",
    tooltip: "The width of each tile.",
    kind: "int",
    min: 64,
    max: 8192,
    step: 8,
    defaultValue: 1024,
  },
  {
    key: "tile_height",
    label: "tile_height",
    tooltip: "The height of each tile.",
    kind: "int",
    min: 64,
    max: 8192,
    step: 8,
    defaultValue: 1024,
  },
  {
    key: "mask_blur",
    label: "mask_blur",
    tooltip: "The blur radius for the mask.",
    kind: "int",
    min: 0,
    max: 64,
    step: 1,
    defaultValue: 8,
  },
  {
    key: "tile_padding",
    label: "tile_padding",
    tooltip: "The padding to apply between tiles.",
    kind: "int",
    min: 0,
    max: 8192,
    step: 8,
    defaultValue: 64,
  },
  {
    key: "seam_fix_mode",
    label: "seam_fix_mode",
    tooltip: "The seam fix mode to use.",
    kind: "enum",
    options: SEAM_FIX_MODES,
    defaultValue: "None",
  },
];

/** @deprecated Use ULTIMATE_SD_USER_WIDGETS */
export const ULTIMATE_SD_WIDGETS = ULTIMATE_SD_USER_WIDGETS;

export type NodeInputSpec = {
  key: string;
  label: string;
  type: string;
  tooltip: string;
};

export const ULTIMATE_SD_INPUTS: NodeInputSpec[] = [
  { key: "image", label: "image", type: "IMAGE", tooltip: "The image to upscale." },
  { key: "model", label: "model", type: "MODEL", tooltip: "The model to use for image-to-image." },
  {
    key: "positive",
    label: "positive",
    type: "CONDITIONING",
    tooltip: "The positive conditioning for each tile.",
  },
  {
    key: "negative",
    label: "negative",
    type: "CONDITIONING",
    tooltip: "The negative conditioning for each tile.",
  },
  { key: "vae", label: "vae", type: "VAE", tooltip: "The VAE model to use for tiles." },
];

export const ULTIMATE_SD_AUTO_SUMMARY =
  "Auto: canvas · SDXL model · prompts · upscaler · seed · sampling · VRAM detect";

/** Map Comfy widget keys to GenerationSettings field names. */
export function upscaleSettingsKey(widgetKey: string): string {
  switch (widgetKey) {
    case "denoise":
      return "upscale_denoise";
    case "mode_type":
      return "upscale_mode_type";
    case "tile_width":
      return "upscale_tile_width";
    case "tile_height":
      return "upscale_tile_height";
    case "mask_blur":
      return "upscale_mask_blur";
    case "tile_padding":
      return "upscale_tile_padding";
    case "seam_fix_mode":
      return "upscale_seam_fix_mode";
    case "seam_fix_denoise":
      return "upscale_seam_fix_denoise";
    case "seam_fix_width":
      return "upscale_seam_fix_width";
    case "seam_fix_mask_blur":
      return "upscale_seam_fix_mask_blur";
    case "seam_fix_padding":
      return "upscale_seam_fix_padding";
    case "force_uniform_tiles":
      return "upscale_force_uniform_tiles";
    case "tiled_decode":
      return "upscale_tiled_decode";
    case "upscale_model":
      return "cn_upscale";
    case "cfg":
      return "cfg_scale";
    case "sampler_name":
      return "sampler";
    default:
      return widgetKey;
  }
}
