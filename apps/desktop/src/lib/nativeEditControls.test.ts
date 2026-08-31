import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ReferenceImageControl } from "../components/ReferenceImageControl";
import { ReferenceSlotsEditor } from "../components/ReferenceSlotsEditor";
import { EditFamilySettingsPanel } from "../components/EditFamilySettingsPanel";
import { applyIdentityAtSubmit } from "./identityPreserve";
import { applyMultiImageComposeAtSubmit } from "./multiImageCompose";
import { applyExplicitReferenceRoleParams } from "./generateReferenceParams";
import { applyReferencesAtSubmit } from "./referenceSlots";
import { buildGenerateReferencePatch } from "./referenceImage";
import { buildEasyCreateReferencePatch } from "./easyModeRouting";
import { sanitizeSettingsForStudioMode } from "./routeResolution";
import type { GenerationSettings, ModelGalleryItem } from "./tauri-api";

const models = ["krea2", "flux_kontext", "qwen_image_edit"].map(family =>
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
  next = applyReferencesAtSubmit(next, mode);
  next = applyMultiImageComposeAtSubmit(next, mode, models);
  return applyIdentityAtSubmit(next, models, { studioMode: mode });
}

describe("native editing without legacy identity controls", () => {
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
      expect(next.input_image).toBe("source.png");
      expect(next.references?.map(slot => slot.path)).toEqual(["source.png", "subject.png"]);
    }
  });
  it("preserves Toolbox/custom and inpaint settings, and Photo Restore's detail pass", () => {
    for (const mode of ["toolbox", "inpaint"] as const) {
      expect(sanitizeSettingsForStudioMode(mode, legacy)).toMatchObject({ identity_verify: true, face_preservation: true });
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
        modelGallery: models, isInpaint: false, routedModelLabel: "Krea 2", showEditStrength: true, onChange: noop })));
    expect(html).not.toMatch(/Keep face \/ character|Verify likeness|Face guidance|Not a character|Face in this image|Similarity/);
    expect(html).toContain("Add image");
    expect(html).toContain("Identity Edit v1.2 is applied automatically");
    expect(html).toContain("Preservation hints");
  });
});
