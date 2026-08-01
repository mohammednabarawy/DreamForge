import { useRef, useState } from "react";
import { Download, FileJson, Image, Library, Upload } from "lucide-react";
import { pickImageFile } from "../lib/tauri-api";
import type { GenerationSettings } from "../lib/tauri-api";
import { importImageMetadata } from "../lib/imageMetadata";
import { settingsPatchFromRecipe } from "../lib/recipe";
import { saveRecipeToLibrary } from "../lib/studioBridge";
export { settingsPatchFromRecipe } from "../lib/recipe";

type Props = {
  settings: GenerationSettings;
  onChange: (patch: Partial<GenerationSettings>) => void;
  onOpenLibrary?: () => void;
};

type RecipePayload = {
  schema_version: "2.0";
  model: string;
  positive_prompt: string;
  negative_prompt: string;
  seed: number | null;
  sampler: string;
  cfg_scale: number;
  steps: number;
  aspect_ratio: string;
  performance: string;
  styles: string[];
  loras: Array<{ filename: string; weight: number }>;
  settings: Pick<GenerationSettings, "scheduler" | "width" | "height" | "denoise" | "clip_skip" | "vram_profile">;
  source: "local_export";
};

function loraParts(value: string) {
  const match = value.match(/^(.*):(-?\d+(?:\.\d+)?)$/);
  return match
    ? { filename: match[1], weight: Number(match[2]) }
    : { filename: value, weight: 1 };
}

function toRecipe(settings: GenerationSettings): RecipePayload {
  return {
    schema_version: "2.0",
    model: settings.model ?? "",
    positive_prompt: settings.prompt ?? "",
    negative_prompt: settings.negative_prompt ?? "",
    seed: settings.seed ?? null,
    sampler: settings.sampler ?? "",
    cfg_scale: settings.cfg_scale ?? 0,
    steps: settings.steps ?? 0,
    aspect_ratio: settings.aspect_ratio ?? "",
    performance: settings.performance ?? "",
    styles: settings.styles ?? [],
    loras: (settings.lora ?? []).map(loraParts),
    settings: {
      scheduler: settings.scheduler,
      width: settings.width,
      height: settings.height,
      denoise: settings.denoise,
      clip_skip: settings.clip_skip,
      vram_profile: settings.vram_profile,
    },
    source: "local_export",
  };
}

function applyRecipe(value: unknown, onChange: Props["onChange"]): string {
  const patch = settingsPatchFromRecipe(value);
  onChange(patch);
  return `${patch.model || "recipe"} loaded`;
}

export function RecipeActions({ settings, onChange, onOpenLibrary }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [imageBusy, setImageBusy] = useState(false);
  const [message, setMessage] = useState("");

  const exportRecipe = () => {
    const blob = new Blob([JSON.stringify(toRecipe(settings), null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "dreamforge-recipe.json";
    anchor.click();
    URL.revokeObjectURL(url);
    setMessage("Recipe exported");
  };

  const saveCurrent = async () => {
    const recipe = toRecipe(settings);
    const result = await saveRecipeToLibrary(`local:${Date.now()}`, recipe);
    if (!result.ok) throw new Error(result.error ?? "Could not save recipe");
    setMessage(`Saved to Recipe Library: ${result.filename ?? "recipe"}`);
    onOpenLibrary?.();
  };

  const load = async (file?: File) => {
    if (!file) return;
    try {
      const recipe = JSON.parse(await file.text()) as Record<string, unknown>;
      const saved = await saveRecipeToLibrary(`import:${file.name}`, recipe);
      if (!saved.ok) throw new Error(saved.error ?? "Could not save imported recipe");
      setMessage(`${applyRecipe(recipe, onChange)} · saved to Library`);
      onOpenLibrary?.();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load recipe");
    }
    if (inputRef.current) inputRef.current.value = "";
  };

  const importImage = async () => {
    const path = await pickImageFile();
    if (!path) return;
    setImageBusy(true);
    try {
      const result = await importImageMetadata(path);
      if (!result.ok || !result.patch) {
        setMessage(
          result.error === "no_generation_metadata"
            ? "No generation metadata found"
            : "Could not read image metadata",
        );
        return;
      }
      onChange(result.patch);
      if (result.recipe) {
        const saved = await saveRecipeToLibrary(`image:${path.split(/[\\/]/).pop() ?? Date.now()}`, result.recipe);
        if (!saved.ok) throw new Error(saved.error ?? "Could not save image recipe");
      }
      setMessage("Image metadata imported and saved to Recipe Library");
      onOpenLibrary?.();
    } catch (error) {
      setMessage(`Image import failed: ${String(error)}`);
    } finally {
      setImageBusy(false);
    }
  };

  return (
    <div className="shrink-0 rounded-lg border border-dfui-accent/25 bg-dfui-accent/5 px-2.5 py-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <FileJson size={13} className="text-dfui-accent" />
        <span className="flex-1 text-[10px] font-semibold text-dfui-fg">Recipe v2</span>
        <button type="button" onClick={() => void saveCurrent().catch((error) => setMessage(String(error)))} className="inline-flex items-center gap-1 rounded border border-dfui-border/50 px-1.5 py-1 text-[9px] text-dfui-secondary hover:text-dfui-fg">
          <Library size={11} /> Library
        </button>
        <button type="button" onClick={exportRecipe} className="inline-flex items-center gap-1 rounded border border-dfui-border/50 px-1.5 py-1 text-[9px] text-dfui-secondary hover:text-dfui-fg">
          <Download size={11} /> Export
        </button>
        <button type="button" onClick={() => inputRef.current?.click()} className="inline-flex items-center gap-1 rounded border border-dfui-border/50 px-1.5 py-1 text-[9px] text-dfui-secondary hover:text-dfui-fg">
          <Upload size={11} /> Import
        </button>
        <button type="button" disabled={imageBusy} onClick={() => void importImage()} className="inline-flex items-center gap-1 rounded border border-dfui-border/50 px-1.5 py-1 text-[9px] text-dfui-secondary hover:text-dfui-fg disabled:opacity-50" title="Import known generation metadata from an image">
          <Image size={11} /> {imageBusy ? "Reading" : "Image"}
        </button>
        <input ref={inputRef} type="file" accept="application/json,.json" className="hidden" onChange={(event) => void load(event.target.files?.[0])} />
      </div>
      <p className="mt-1 truncate text-[9px] text-dfui-tertiary" role="status">
        {message || "Export the current settings or load a recipe without changing the ComfyUI engine."}
      </p>
    </div>
  );
}
