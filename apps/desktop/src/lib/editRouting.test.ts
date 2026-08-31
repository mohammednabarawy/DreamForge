import { describe, expect, it } from "vitest";
import { buildEditRoutingPatch } from "./editModel";
import { applyIdentityAtSubmit } from "./identityPreserve";
import { maxReferenceImagesForFamily, resolveReferenceModelFamily } from "./multiImageCompose";
import { coerceReferenceSlots } from "./referenceSlots";
import type { GenerationSettings, ModelGalleryItem } from "./tauri-api";

const krea = { engine_name: "krea.safetensors", family: "krea2" } as ModelGalleryItem;
const qwen = { engine_name: "qwen-edit.safetensors", family: "qwen_image_edit" } as ModelGalleryItem;

describe("Krea edit submission", () => {
  it("retains Krea, explicit sampling settings, and source/subject order with Keep Face", () => {
    const original = { model: krea.engine_name, prompt: "change the shirt", steps: 13, cfg_scale: 2.5,
      width: 608, height: 768, seed: 42, preserve_character: true,
      input_image: "source.png", references: [
        { path: "source.png", role: "source_edit" }, { path: "subject.png", role: "image_prompt" }],
      edit_type: "qwen_edit" } as GenerationSettings;
    const routed = { ...original, ...buildEditRoutingPatch(krea) };
    const submitted = applyIdentityAtSubmit(routed, [krea, qwen], { studioMode: "edit" });
    expect(submitted).toMatchObject({ model: krea.engine_name, edit_type: "auto", steps: 13,
      cfg_scale: 2.5, width: 608, height: 768, seed: 42 });
    expect(resolveReferenceModelFamily(submitted, "edit", [krea, qwen], "krea2")).toBe("krea2");
    expect(coerceReferenceSlots(submitted, "edit", 2).map(slot => slot.path)).toEqual(["source.png", "subject.png"]);
    expect(maxReferenceImagesForFamily("krea2", "edit")).toBe(2);
    expect(maxReferenceImagesForFamily("krea2", "generate")).toBe(4);
  });
  it("restores the appropriate route when switching back to Qwen", () => {
    expect(buildEditRoutingPatch(qwen).edit_type).toBe("qwen_edit");
    expect(buildEditRoutingPatch(krea).edit_type).toBe("auto");
  });
});
