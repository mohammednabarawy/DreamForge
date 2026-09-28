import { describe, expect, it } from "vitest";
import { computeGenerateReadiness } from "./generationReadiness";
import { sanitizeSettingsForStudioMode } from "./routeResolution";

const base = {
  workerReady: true,
  generating: false,
  engineState: "ready",
  engineLabel: "Ready",
  prompt: "replace the sky",
  model: "qwen_image_2.1_int8_convrot.safetensors",
  modelDependenciesReady: true,
  missingCompanionCount: 0,
  modelGallery: [],
} as const;

describe("merged Edit mode", () => {
  it("allows compatible selected editors and blocks incompatible masked edits without replacing the model", () => {
    for (const family of ["krea2", "flux_kontext", "sdxl"]) {
      const model = `${family}.safetensors`;
      const settings = { model, input_image: "source.png", prompt: "Change the shirt" };
      const args = { ...base, model, studioMode: "edit" as const, settings,
        modelGallery: [{ family, engine_name: model }] as Parameters<typeof computeGenerateReadiness>[0]["modelGallery"] };
      expect(computeGenerateReadiness(args).ok).toBe(true);
      const masked = computeGenerateReadiness({ ...args, settings: { ...settings, inpaint_mask_path: "mask.png" } });
      expect(masked.ok).toBe(family !== "krea2");
      if (family === "krea2") expect(masked.reason).toContain("does not support masked editing");
      expect(settings.model).toBe(model);
    }
  });
  it("routes a prompt without references to text-to-image despite stale Edit controls", () => {
    const settings = {
      model: base.model,
      prompt: "Arabic infographic --ar 16:9",
      style: "image_edit",
      edit_type: "qwen_edit" as const,
      cn_selection: "Custom...",
      cn_type: "img2img",
      workflow_mode: "edit",
    };
    expect(computeGenerateReadiness({ ...base, studioMode: "generate", settings }).ok).toBe(true);
    expect(sanitizeSettingsForStudioMode("generate", settings)).toMatchObject({
      style: "none",
      edit_type: "auto",
      cn_selection: "None",
      cn_type: "None",
      workflow_mode: "generate",
    });
  });

  it("requires a mask only when Edit is configured for inpainting", () => {
    const blocked = computeGenerateReadiness({
      ...base,
      studioMode: "edit",
      settings: { input_image: "C:/source.png", edit_type: "inpaint" },
    });
    expect(blocked).toMatchObject({ ok: false, reason: "Create or attach an inpaint mask first" });

    const ready = computeGenerateReadiness({
      ...base,
      studioMode: "edit",
      settings: {
        input_image: "C:/source.png",
        inpaint_mask_path: "C:/mask.png",
        edit_type: "inpaint",
      },
    });
    expect(ready.ok).toBe(true);
  });

  it.each(["inpaint", "toolbox"] as const)(
    "normalizes legacy %s settings into Edit and drops custom workflows",
    (mode) => {
      const next = sanitizeSettingsForStudioMode(mode, {
        custom_tool_id: "custom_123",
        input_image: "C:/source.png",
        inpaint_mask_path: "C:/mask.png",
        edit_type: "inpaint",
      });
      expect(next.custom_tool_id).toBeUndefined();
      expect(next.inpaint_mask_path).toBe("C:/mask.png");
    },
  );
});
