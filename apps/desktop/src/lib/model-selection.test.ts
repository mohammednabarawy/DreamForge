import { expect, it } from "vitest";
import { resolveActiveModel, selectCuratedModelForMode } from "./model-selection";
import type { ModelGalleryItem } from "./tauri-api";

function model(name: string, family: string): ModelGalleryItem {
  return {
    category: "diffusion_models",
    relative_path: name,
    caption: name,
    engine_name: `../diffusion_models/${name}`,
    family,
    thumbnail_path: "",
  };
}

it("defaults generation to installed Krea 2 Turbo FP8 without overriding an explicit choice", () => {
  const gallery = [
    model("ideogram4_fp8_scaled.safetensors", "ideogram4"),
    model("Krea2_Turbo_convrot_int8mixed.safetensors", "krea2"),
    model("krea2TurboFP8_krea2TURBO.safetensors", "krea2"),
    model("krea2_raw.safetensors", "krea2"),
  ];
  const krea = gallery[2].engine_name;
  const ideogram = gallery[0].engine_name;
  expect(resolveActiveModel(gallery, ideogram, "none", [], false)).toBe(krea);
  expect(selectCuratedModelForMode("generate", gallery)).toBe(krea);
  expect(resolveActiveModel(gallery, ideogram, "none", [], true)).toBe(ideogram);
  expect(resolveActiveModel(gallery, "", "my-style", [{ id: "my-style", models: [ideogram] }], false)).toBe(ideogram);
  expect(selectCuratedModelForMode("generate", [gallery[0]])).toBe(ideogram);
});
