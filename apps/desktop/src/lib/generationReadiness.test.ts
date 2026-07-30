import { describe, expect, it } from "vitest";
import { resolveCustomTool, type CustomTool } from "./customTools";
import { computeGenerateReadiness } from "./generationReadiness";
import { sanitizeSettingsForStudioMode } from "./routeResolution";

const baseTool: CustomTool = {
  id: "custom_123",
  name: "Carousel",
  description: "",
  workflow_path: "C:/Users/test/Carousel.json",
  bindings: {},
};

describe("resolveCustomTool", () => {
  it("falls back to the only tool when the saved id is stale", () => {
    expect(resolveCustomTool([baseTool], "custom_old")?.id).toBe("custom_123");
  });

  it("returns undefined when multiple tools and id is stale", () => {
    const other: CustomTool = { ...baseTool, id: "custom_456", name: "Other" };
    expect(resolveCustomTool([baseTool, other], "custom_old")).toBeUndefined();
  });
});

describe("computeGenerateReadiness toolbox", () => {
  it("allows generate when only one custom tool exists despite stale id", () => {
    const readiness = computeGenerateReadiness({
      workerReady: true,
      generating: false,
      engineState: "ready",
      engineLabel: "Ready",
      prompt: "hello",
      model: "flux.safetensors",
      modelDependenciesReady: true,
      missingCompanionCount: 0,
      settings: {
        custom_tool_id: "custom_stale",
        input_image: "C:/ref.png",
      } as any,
      modelGallery: [],
      studioMode: "toolbox",
      customTools: [baseTool],
    });
    expect(readiness.ok).toBe(true);
  });
});

describe("sanitizeSettingsForStudioMode custom tools", () => {
  it.each(["generate", "edit", "inpaint", "upscale", "agent"] as const)(
    "clears the Toolbox workflow in %s mode",
    (mode) => {
      expect(
        sanitizeSettingsForStudioMode(mode, { custom_tool_id: "custom_123" } as any)
          .custom_tool_id,
      ).toBeUndefined();
    },
  );

  it("keeps the selected workflow in Toolbox mode", () => {
    expect(
      sanitizeSettingsForStudioMode("toolbox", { custom_tool_id: "custom_123" } as any)
        .custom_tool_id,
    ).toBe("custom_123");
  });
});
