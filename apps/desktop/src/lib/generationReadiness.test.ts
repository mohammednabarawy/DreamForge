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
