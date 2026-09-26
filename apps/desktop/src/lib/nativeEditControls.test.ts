import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ReferenceImageControl } from "../components/ReferenceImageControl";
import { ReferenceSlotsEditor } from "../components/ReferenceSlotsEditor";
import { EditFamilySettingsPanel } from "../components/EditFamilySettingsPanel";
import { PromptBar } from "../components/PromptBar";
import { ResultTray } from "../components/ResultTray";
import { applyIdentityAtSubmit } from "./identityPreserve";
import { applyMultiImageComposeAtSubmit } from "./multiImageCompose";
import { applyExplicitReferenceRoleParams } from "./generateReferenceParams";
import { applyReferencesAtSubmit } from "./referenceSlots";
import { activeReferencePath, buildGenerateReferencePatch, imageTaskForRequest, isExplicitImageEditRequest } from "./referenceImage";
import { planStudioModeSwitch } from "./creativeTask";
import { buildEasyCreateReferencePatch } from "./easyModeRouting";
import { sanitizeSettingsForStudioMode } from "./routeResolution";
import type { GenerationSettings, ModelGalleryItem } from "./tauri-api";

const models = ["krea2", "flux_kontext", "qwen_image_2.1"].map(family =>
  ({ family, engine_name: `${family}.safetensors` }) as ModelGalleryItem);
const legacy = {
  prompt: "Keep the same person, change the shirt", input_image: "source.png",
  reference_image: "source.png", reference_role: "source_edit", steps: 13,
  cfg_scale: 2.5, width: 608, height: 768, seed: 42, lora: ["krea2_identity_edit_v1_2.safetensors:0.75"],
  preserve_character: true, face_preservation: true, identity_mode: "ipadapter_faceid",
  identity_verify: true, identity_retry: true, identity_similarity_threshold: 0.6,
  references: [
    { path: "source.png", role: "source_edit", character_id: "character_a", face_index: 1 },
    { path: "subject.png", role: "image_prompt", character_id: "character_b", character_region: "left" },
  ],
} as GenerationSettings;

function submit(settings: GenerationSettings, mode: "generate" | "edit", family: string) {
  let next = sanitizeSettingsForStudioMode(mode, settings);
  next = applyExplicitReferenceRoleParams(next, mode, family, { ipAdapterReady: false }).params;
  next = applyReferencesAtSubmit(next, mode, family);
  next = applyMultiImageComposeAtSubmit(next, mode, models);
  return applyIdentityAtSubmit(next, models, { studioMode: mode });
}

describe("native editing without legacy identity controls", () => {
  it("offers prompt enhancement in both Create and Edit", () => {
    const noop = () => {};
    for (const studioMode of ["generate", "edit"] as const) {
      const html = renderToStaticMarkup(createElement(PromptBar, {
        settings: legacy, studioMode, onChange: noop,
        mentions: [], generating: false, workerReady: true, canGenerate: true,
        onDryRun: noop, onEnhancePrompt: noop, onGenerate: noop, onCancel: noop,
        onAttachReferenceImage: noop, onClearReferenceImage: noop,
        activeModelLabel: "Qwen Image 2.1",
      }));
      expect(html).toContain('aria-label="Enhance prompt"');
    }
  });
  it("routes an explicit source change to Qwen Edit without a mode switch", () => {
    const settings = { ...legacy, prompt: "Edit the reference photo: change his shirt", input_image: undefined,
      reference_image: "explicit.png" };
    expect(isExplicitImageEditRequest(settings)).toBe(true);
    expect(isExplicitImageEditRequest({ ...settings, prompt: "Put the people from <image1> and <image2> together" })).toBe(false);
    expect(imageTaskForRequest(settings)).toBe("edit");
    expect(activeReferencePath(settings, "edit")).toBe("explicit.png");
    const html = renderToStaticMarkup(createElement(PromptBar, {
      settings, studioMode: imageTaskForRequest(settings), referenceModelFamily: "qwen_image_2.1",
      onChange: () => {}, mentions: [], generating: false,
      workerReady: true, canGenerate: true, onDryRun: () => {}, onGenerate: () => {},
      onCancel: () => {}, onAttachReferenceImage: () => {}, onClearReferenceImage: () => {},
      activeModelLabel: "Qwen Image 2.1",
    }));
    expect(html).toContain("Create &amp; Edit");
    expect(html).toContain("Auto · Qwen Image 2.1 edit");
    expect(html).toContain("Edit image");
    expect(html).not.toContain("Switch to Edit");
    const plan = planStudioModeSwitch({ studioMode: "edit", previousMode: "generate", gallery: models,
      settings, selectedImage: "history.png", userPickedModel: false, advancedMode: false });
    expect(plan.patch).toMatchObject({ input_image: "explicit.png", performance: "Quality", steps: 40,
      cfg_scale: 1, sampler: "euler", scheduler: "simple" });
  });
  it("keeps reference-guided creation on the selected generator and masks on Qwen Edit", () => {
    for (const model of ["ideogram4.safetensors", "sdxl.safetensors", "qwen_image_2.1.safetensors"]) {
      const base = { ...legacy, model, prompt: "Create a studio portrait using <image1> and <image2>" };
      expect(imageTaskForRequest(base)).toBe("generate");
      expect(imageTaskForRequest({ ...base, prompt: "Make the people in <image1> and <image2> together in one photo" })).toBe("generate");
      expect(imageTaskForRequest({ ...base, prompt: "Change <image1> to a blue shirt" })).toBe("edit");
      expect(imageTaskForRequest({ ...base, inpaint_mask_path: "mask.png" })).toBe("edit");
      expect(imageTaskForRequest({ ...base, input_image: undefined, reference_image: undefined, references: [] })).toBe("generate");
    }
    expect(sanitizeSettingsForStudioMode("edit", {
      ...legacy, workflow_mode: "generate", inpaint_mask_path: "mask.png",
    })).toMatchObject({ workflow_mode: "edit", reference_role: "inpaint", edit_type: "inpaint", cn_type: "inpaint" });
  });
  it("shows Qwen's requested inputs and the actual result dimensions separately", () => {
    const noop = () => {};
    const html = renderToStaticMarkup(createElement(PromptBar, {
      settings: { ...legacy, prompt: "Put <image1> and <image2> on a transparent background PNG", inpaint_mask_path: "mask.png" },
      studioMode: "edit", referenceModelFamily: "qwen_image_2.1",
      onChange: noop, mentions: [], generating: false,
      workerReady: true, canGenerate: true, onDryRun: noop, onGenerate: noop,
      onCancel: noop, onAttachReferenceImage: noop, onClearReferenceImage: noop,
      activeModelLabel: "Qwen Image 2.1",
    }));
    expect(html).toContain("Requested 608×768 · 2 references · masked edit · transparent background requested");
    expect(html).toContain("Edit image");
    expect(html).not.toContain("Sharpen 2×");
    const tray = renderToStaticMarkup(createElement(ResultTray, {
      images: ["output.png"], activePath: "output.png",
      outputInfo: { width: 1024, height: 1024, format: "PNG", transparent: false }, onSelect: noop,
    }));
    expect(tray).toContain("Actual 1024×1024 PNG · Opaque");
    expect(renderToStaticMarkup(createElement(ResultTray, {
      images: ["alpha.png"], activePath: "alpha.png",
      outputInfo: { width: 1024, height: 1024, format: "PNG", transparent: true }, onSelect: noop,
    }))).toContain("Has transparency");
  });
  it("shows ordered Qwen references without inactive strength or required-mask controls", () => {
    const noop = () => {};
    const html = renderToStaticMarkup(createElement(ReferenceImageControl, {
      settings: { ...legacy, model: "qwen_image_2.1.safetensors", prompt: "Put both people together" },
      modelFamily: "qwen_image_2.1", studioMode: "edit",
      onAttach: noop, onClear: noop, onPatchSettings: noop, onOpenInpaintMask: noop,
      onEditStrengthChange: noop,
    }));
    expect(html).toContain("Insert &lt;image1&gt; into prompt");
    expect(html).toContain("Insert &lt;image2&gt; into prompt");
    expect(html).toContain("Not named in prompt");
    expect(html).toContain("Paint mask (optional)");
    expect(html).not.toContain("Mask needed");
    expect(html).not.toContain("Strength");
    expect(html).not.toContain("Stop at");
  });
  it("keeps image tags available when extra references use the compact strip", () => {
    const noop = () => {};
    const html = renderToStaticMarkup(createElement(ReferenceImageControl, {
      settings: { ...legacy, references: undefined, reference_images: ["subject.png"], prompt: "Put both together" },
      modelFamily: "qwen_image_2.1", studioMode: "edit", simpleExperience: true,
      onAttach: noop, onAttachExtra: noop, onClear: noop, onPatchSettings: noop,
    }));
    expect(html).toContain("Insert &lt;image1&gt; into prompt");
    expect(html).toContain("Insert &lt;image2&gt; into prompt");
    expect(html).toContain("Not named");
    const promptBar = renderToStaticMarkup(createElement(PromptBar, {
      settings: { ...legacy, references: undefined, reference_images: ["subject.png"] },
      studioMode: "edit", referenceModelFamily: "qwen_image_2.1", experience: "easy",
      onChange: noop, mentions: [], generating: false,
      workerReady: true, canGenerate: true, onDryRun: noop, onGenerate: noop,
      onCancel: noop, onAttachReferenceImage: noop, onClearReferenceImage: noop,
      activeModelLabel: "Qwen Image 2.1",
    }));
    expect(promptBar).toContain("2 references");
  });
  for (const model of models) {
    it(`keeps ${model.family} Edit inputs and sampling, without identity routing or retries`, () => {
      const next = submit({ ...legacy, model: model.engine_name }, "edit", model.family!);
      expect(next).toMatchObject({ model: model.engine_name, prompt: legacy.prompt, steps: 13,
        cfg_scale: 2.5, width: 608, height: 768, seed: 42, lora: legacy.lora,
        preserve_character: false, face_preservation: false, identity_verify: false, identity_retry: false });
      expect(next.identity_mode).toBeUndefined();
      expect(next.references).toEqual([{ path: "source.png", role: "source_edit", weight: 0.75, stop_at: 1 },
        { path: "subject.png", role: "image_prompt", weight: 0.75, stop_at: 1 }]);
      expect(legacy.references?.[0].character_id).toBe("character_a");
    });
  }
  it("does not switch a single-reference Generate model because of old flags or prompt wording", () => {
    const settings = { ...legacy, model: "sdxl.safetensors", references: legacy.references?.slice(0, 1),
      reference_role: "image_prompt", workflow_mode: "ipadapter_faceid" } as GenerationSettings;
    expect(submit(settings, "generate", "sdxl")).toMatchObject({ model: settings.model, steps: 13,
      identity_verify: false, identity_retry: false, workflow_mode: "generate", reference_role: "restyle" });
    expect(buildEasyCreateReferencePatch("source.png", models, () => "output", { modelFamily: "krea2", ipAdapterReady: true }))
      .toMatchObject({ reference_role: "restyle", workflow_mode: "generate" });
    for (const patch of [buildGenerateReferencePatch("source.png", () => "output", { modelFamily: "sdxl" }),
      buildEasyCreateReferencePatch("source.png", models, () => "output", { modelFamily: "sdxl", currentModel: settings.model })]) {
      expect({ ...settings, ...patch }.model).toBe(settings.model);
      expect(patch.preserve_character).not.toBe(true);
    }
  });
  it("keeps multi-image composition and native Qwen/Kontext Generate references without identity flags", () => {
    const composed = submit({ ...legacy, model: "sdxl.safetensors", reference_role: "restyle" }, "generate", "sdxl");
    expect(composed).toMatchObject({ model: "flux_kontext.safetensors", input_image: "source.png", steps: 13,
      preserve_character: false, identity_verify: false });
    for (const model of models.slice(1)) {
      const next = submit({ ...legacy, model: model.engine_name, reference_role: "image_prompt" }, "generate", model.family!);
      expect(next.model).toBe(model.engine_name);
      expect(next.input_image).toBe(model.family === "qwen_image_2.1" ? undefined : "source.png");
      expect(next.references?.map(slot => slot.path)).toEqual(["source.png", "subject.png"]);
      if (model.family === "qwen_image_2.1") {
        expect(next.workflow_mode).toBe("generate");
        expect(next.references?.map(slot => slot.role)).toEqual(["image_prompt", "image_prompt"]);
      }
    }
  });
  it("normalizes retired modes into Edit and keeps Photo Restore's detail pass", () => {
    for (const mode of ["toolbox", "inpaint"] as const) {
      expect(sanitizeSettingsForStudioMode(mode, legacy)).toMatchObject({ identity_verify: false, face_preservation: false });
    }
    expect(sanitizeSettingsForStudioMode("edit", { ...legacy, edit_task: "photo_restore" }))
      .toMatchObject({ face_preservation: true, identity_verify: false, identity_retry: false });
  });
  it("renders references and native edit controls without the retired identity controls", () => {
    const noop = () => {};
    const html = renderToStaticMarkup(createElement("div", null,
      createElement(ReferenceImageControl, { settings: legacy, studioMode: "generate", onAttach: noop, onClear: noop, onPatchSettings: noop }),
      createElement(ReferenceSlotsEditor, { settings: legacy, showRoles: true, onAddSlot: noop, onUpdateSlot: noop, onRemoveSlot: noop }),
      createElement(EditFamilySettingsPanel, { settings: { ...legacy, model: models[0].engine_name },
        isInpaint: false, routedModelLabel: "Qwen Image 2.1", showEditStrength: false, onChange: noop })));
    expect(html).not.toMatch(/Keep face \/ character|Verify likeness|Face guidance|Not a character|Face in this image|Similarity/);
    expect(html).toContain("Add image");
    expect(html).toContain("Qwen Image 2.1 Edit");
    expect(html).toContain("Preserve from the source");
  });
});
