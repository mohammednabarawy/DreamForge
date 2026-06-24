import type { GenerationSettings } from "./tauri-api";
import { buildRestyleReferencePatch } from "./referenceImage";

export type VaryAmount = "subtle" | "strong";

export const VARY_AMOUNTS: Array<{
  id: VaryAmount;
  label: string;
  short: string;
  strength: number;
  hint: string;
}> = [
  {
    id: "subtle",
    label: "Vary subtle",
    short: "Subtle",
    strength: 0.3,
    hint: "Light img2img variation — keeps composition close to the source.",
  },
  {
    id: "strong",
    label: "Vary strong",
    short: "Strong",
    strength: 0.6,
    hint: "Stronger variation — more change while keeping the same prompt.",
  },
];

export function varyStrength(amount: VaryAmount): number {
  return VARY_AMOUNTS.find((item) => item.id === amount)?.strength ?? 0.3;
}

export function normalizeVaryAmount(value: string | undefined | null): VaryAmount | undefined {
  const key = (value ?? "").trim().toLowerCase();
  if (key === "subtle" || key === "strong") return key;
  return undefined;
}

/** Patch settings to re-run img2img on an existing output (Fooocus-style Vary). */
export function buildVarySettingsPatch(
  imagePath: string,
  amount: VaryAmount,
  outputFor: (suffix: string) => string,
  modelFamily?: string,
): Partial<GenerationSettings> {
  const strength = varyStrength(amount);
  return {
    ...buildRestyleReferencePatch(
      imagePath,
      { output: outputFor("gen") },
      modelFamily,
    ),
    vary_amount: amount,
    edit_strength: strength,
    workflow_mode: "generate",
  };
}

export function applyVaryAmountAtSubmit(
  params: GenerationSettings,
): GenerationSettings {
  const amount = normalizeVaryAmount(params.vary_amount);
  if (!amount) return params;
  const strength = varyStrength(amount);
  const refPath =
    params.input_image?.trim() || params.reference_image?.trim() || "";
  if (!refPath) return params;
  return {
    ...params,
    reference_role: "restyle",
    workflow_mode: "generate",
    input_image: refPath,
    reference_image: params.reference_image?.trim() || refPath,
    cn_selection: "Custom...",
    cn_type: "img2img",
    edit_type: "auto",
    edit_strength: params.edit_strength ?? strength,
    vary_amount: amount,
  };
}
