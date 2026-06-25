/** Families that use AiBrain LLM enhancement (generate mode). */
export type EnhanceStrength = "minimal" | "balanced" | "rich";

export const ENHANCE_STRENGTH_OPTIONS: Array<{
  id: EnhanceStrength;
  label: string;
}> = [
  { id: "minimal", label: "Minimal" },
  { id: "balanced", label: "Balanced" },
  { id: "rich", label: "Rich" },
];

const MODERN_LLM_GENERATE_FAMILIES = new Set([
  "flux",
  "flux_kontext",
  "flux_fill",
  "flux2",
  "sd3",
  "qwen",
  "qwen_image",
  "hidream",
  "hidream_o1",
  "krea2",
  "z_image",
  "hunyuan",
]);

export function isModernLlmGenerateFamily(family: string | undefined | null): boolean {
  const fam = (family ?? "").trim().toLowerCase();
  if (!fam || fam === "ideogram4") return false;
  if (MODERN_LLM_GENERATE_FAMILIES.has(fam)) return true;
  return (
    fam.startsWith("flux") ||
    fam.startsWith("qwen") ||
    fam.startsWith("hidream") ||
    fam === "sd3" ||
    fam === "krea2" ||
    fam === "z_image" ||
    fam === "hunyuan"
  );
}

export function shouldAutoEnhanceOnGenerate(
  family: string | undefined | null,
  studioMode: string,
  autoEnhanceEnabled: boolean | undefined,
): boolean {
  if (!autoEnhanceEnabled) return false;
  if ((studioMode || "generate") !== "generate") return false;
  return isModernLlmGenerateFamily(family);
}

export function enhancePrefsFromAppConfig(
  appConfig: { ui?: Record<string, unknown> } | null | undefined,
): { enhance_strength: EnhanceStrength; use_flufferizer: boolean } {
  const ui = appConfig?.ui ?? {};
  const rawStrength = String(ui.enhance_strength ?? "balanced").toLowerCase();
  const enhance_strength: EnhanceStrength =
    rawStrength === "minimal" || rawStrength === "rich" ? rawStrength : "balanced";
  return {
    enhance_strength,
    use_flufferizer: ui.use_flufferizer !== false,
  };
}
