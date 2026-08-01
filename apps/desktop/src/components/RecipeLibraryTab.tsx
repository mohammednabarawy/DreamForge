import { ExternalLink, FolderOpen, Play, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { deleteRecipeFromLibrary, listRecipeLibrary, resolveRecipeCivitaiResources, type CivitaiRecipeResource, type RecipeLibraryItem } from "../lib/studioBridge";
import { openExternalUrl } from "../lib/externalLinks";
import { enqueueDownload } from "../lib/discover";
import type { LoraGalleryItem, ModelGalleryItem } from "../lib/tauri-api";

type Props = {
  onApply: (recipe: Record<string, unknown>, source?: string) => void;
  onRevealPath?: (path: string) => void;
  modelGallery: ModelGalleryItem[];
  loraGallery: LoraGalleryItem[];
};

function identity(value: string) {
  return value.split(/[\\/]/).pop()?.replace(/\.(safetensors|ckpt|pt|pth|bin)$/i, "").toLowerCase() ?? "";
}

function unresolvedResource(id: string, kind: "model" | "lora", name: string, weight = 1, local = ""): CivitaiRecipeResource {
  return { id, kind, name, version_name: "", model_id: "", model_version_id: "", source_url: "", filename: name, download_url: "", sha256: "", local_engine_name: local, category: kind === "model" ? "checkpoints" : "loras", weight, downloadable: false, error: "No exact Civitai version metadata" };
}

export function RecipeLibraryTab({ onApply, onRevealPath, modelGallery, loraGallery }: Props) {
  const [items, setItems] = useState<RecipeLibraryItem[]>([]);
  const [root, setRoot] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState<RecipeLibraryItem | null>(null);
  const [resources, setResources] = useState<CivitaiRecipeResource[]>([]);
  const [choices, setChoices] = useState<Record<string, string>>({});
  const refresh = useCallback(async () => {
    const result = await listRecipeLibrary();
    if (!result.ok) throw new Error(result.error ?? "Could not load recipes");
    setItems(result.items ?? []);
    setRoot(result.root ?? "");
  }, []);
  useEffect(() => { void refresh().catch((error) => setMessage(String(error))); }, [refresh]);

  const recreate = async (item: RecipeLibraryItem) => {
    const result = await resolveRecipeCivitaiResources(item.recipe);
    const resolved = [...(result.resources ?? [])];
    if (!resolved.length) {
      const model = typeof item.recipe.model === "string" ? item.recipe.model : "";
      const localModel = modelGallery.find((entry) => [entry.engine_name, entry.relative_path, entry.caption].some((value) => identity(value) === identity(model)))?.engine_name ?? "";
      if (model) resolved.push(unresolvedResource("import:model", "model", model, 1, localModel));
      if (Array.isArray(item.recipe.loras)) item.recipe.loras.forEach((entry, index) => {
        if (!entry || typeof entry !== "object" || Array.isArray(entry)) return;
        const row = entry as Record<string, unknown>;
        const name = typeof row.filename === "string" ? row.filename : "";
        const local = loraGallery.find((lora) => [lora.relative_path, lora.name, lora.stem].some((value) => value && identity(value) === identity(name)));
        if (name) resolved.push(unresolvedResource(`import:lora:${index}`, "lora", name, typeof row.weight === "number" ? row.weight : 1, local?.relative_path ?? local?.name ?? ""));
      });
    }
    const missing = resolved.filter((resource) => !resource.local_engine_name);
    if (!missing.length) {
      const localRecipe = { ...item.recipe };
      const model = resolved.find((resource) => resource.kind === "model");
      if (model?.local_engine_name) localRecipe.model = model.local_engine_name;
      const localLoras = resolved.filter((resource) => resource.kind === "lora");
      if (localLoras.length) localRecipe.loras = localLoras.map((resource) => ({ filename: resource.local_engine_name, weight: resource.weight || 1 }));
      onApply(localRecipe, item.path);
      return;
    }
    setPending(item);
    setResources(resolved);
    setChoices(Object.fromEntries(resolved.map((resource) => [resource.id, resource.local_engine_name || (resource.downloadable ? "download" : resource.kind === "lora" ? "skip" : "")])));
    setMessage("Choose original downloads, installed replacements, or skip optional LoRAs.");
  };

  const applyResolved = async () => {
    if (!pending) return;
    const recipe = { ...pending.recipe };
    const queued: string[] = [];
    const loras: Array<{ filename: string; weight: number }> = [];
    for (const resource of resources) {
      const choice = choices[resource.id] ?? "";
      if (choice === "download") {
        const result = await enqueueDownload({ url: resource.download_url, category: resource.category, filename: resource.filename, expected_sha256: resource.sha256, provider: "civitai", provider_asset_id: resource.model_id, provider_version_id: resource.model_version_id });
        if (!result.ok) throw new Error(result.error ?? `Could not queue ${resource.name}`);
        queued.push(resource.name || resource.filename);
      } else if (resource.kind === "model" && choice) {
        recipe.model = choice;
      } else if (resource.kind === "lora" && choice && choice !== "skip") {
        loras.push({ filename: choice, weight: resource.weight || 1 });
      }
    }
    if (queued.length) {
      setMessage(`${queued.length} exact Civitai file${queued.length === 1 ? "" : "s"} queued. Recreate again after installation.`);
      setPending(null);
      return;
    }
    if (resources.some((resource) => resource.kind === "lora")) recipe.loras = loras;
    onApply(recipe, pending.path);
    setPending(null);
  };

  return <div className="flex min-h-0 flex-1 flex-col gap-2">
    <div className="flex items-center gap-2">
      <p className="min-w-0 flex-1 truncate text-[10px] text-dfui-tertiary" title={root}>{items.length} saved recipe{items.length === 1 ? "" : "s"}</p>
      {root && onRevealPath ? <button type="button" onClick={() => onRevealPath(root)} className="rounded p-1.5 text-dfui-muted hover:bg-dfui-surface hover:text-dfui-fg" title="Open recipe folder" aria-label="Open recipe folder"><FolderOpen size={13} /></button> : null}
      <button type="button" onClick={() => void refresh().catch((error) => setMessage(String(error)))} className="rounded p-1.5 text-dfui-muted hover:bg-dfui-surface hover:text-dfui-fg" title="Refresh recipes" aria-label="Refresh recipes"><RefreshCw size={13} /></button>
    </div>
    {message ? <p className="text-[10px] text-amber-200" role="status">{message}</p> : null}
    {pending ? <section className="space-y-2 rounded-lg border border-amber-400/30 bg-amber-500/5 p-2.5" aria-label="Resolve recipe dependencies">
      <p className="text-[10px] font-semibold text-dfui-fg">Resolve missing recipe files</p>
      {resources.map((resource) => <div key={resource.id} className="space-y-1">
        <div className="flex items-center gap-1"><span className="min-w-0 flex-1 truncate text-[9px] text-dfui-secondary">{resource.kind}: {resource.name || resource.filename}</span>{resource.source_url ? <button type="button" onClick={() => void openExternalUrl(resource.source_url)} className="text-dfui-accent" title="Open exact Civitai version" aria-label={`Open Civitai source for ${resource.name}`}><ExternalLink size={10} /></button> : null}</div>
        <select value={choices[resource.id] ?? ""} onChange={(event) => setChoices((current) => ({ ...current, [resource.id]: event.target.value }))} className="df-select w-full px-2 py-1 text-[9px]" aria-label={`Resolve ${resource.name}`}>
          {!choices[resource.id] ? <option value="">Choose replacement…</option> : null}
          {resource.local_engine_name ? <option value={resource.local_engine_name}>Installed: {resource.local_engine_name}</option> : null}
          {resource.downloadable ? <option value="download">Download original: {resource.filename}</option> : null}
          {resource.kind === "model" ? modelGallery.map((model) => <option key={model.relative_path} value={model.engine_name}>{model.caption}</option>) : loraGallery.map((lora) => <option key={lora.relative_path ?? lora.name} value={lora.relative_path ?? lora.name}>{lora.name}</option>)}
          {resource.kind === "lora" ? <option value="skip">Skip this LoRA</option> : null}
        </select>
      </div>)}
      <div className="flex justify-end gap-1.5"><button type="button" onClick={() => setPending(null)} className="rounded border border-dfui-border/50 px-2 py-1 text-[9px] text-dfui-muted">Cancel</button><button type="button" disabled={resources.some((resource) => resource.kind === "model" && !choices[resource.id])} onClick={() => void applyResolved().catch((error) => setMessage(String(error)))} className="rounded border border-dfui-accent/40 bg-dfui-accent/10 px-2 py-1 text-[9px] text-dfui-accent disabled:opacity-40">Continue</button></div>
    </section> : null}
    <div className="min-h-0 flex-1 space-y-2 overflow-y-auto">
      {items.map((item) => {
        const recipe = item.recipe;
        const title = String(recipe.library_id || recipe.positive_prompt || item.filename);
        const completeness = recipe.completeness && typeof recipe.completeness === "object" ? recipe.completeness as Record<string, unknown> : {};
        const sourceUrl = typeof recipe.source_url === "string" ? recipe.source_url : "";
        const settings = recipe.settings && typeof recipe.settings === "object" ? recipe.settings as Record<string, unknown> : {};
        const previewUrl = typeof settings.preview_url === "string" ? settings.preview_url : "";
        return <article key={item.filename} className="rounded-lg border border-dfui-border/50 bg-dfui-bg/30 p-2.5">
          <div className="flex items-start gap-2">
            {previewUrl ? <img src={previewUrl} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer" className="h-12 w-12 shrink-0 rounded-md object-cover" /> : null}
            <div className="min-w-0 flex-1"><h3 className="line-clamp-2 text-[11px] font-semibold text-dfui-fg">{title}</h3><p className="mt-0.5 truncate text-[9px] text-dfui-tertiary">{String(recipe.model || "Model not recorded")} · {Math.round(Number(completeness.score || 0) * 100)}% metadata</p></div>
            {sourceUrl ? <button type="button" onClick={() => void openExternalUrl(sourceUrl)} className="rounded p-1 text-dfui-muted hover:bg-dfui-surface hover:text-dfui-accent" title="Open original source" aria-label={`Open source for ${title}`}><ExternalLink size={12} /></button> : null}
          </div>
          <div className="mt-2 flex items-center gap-1.5">
            <button type="button" onClick={() => void recreate(item).catch((error) => setMessage(String(error)))} className="inline-flex items-center gap-1 rounded border border-dfui-accent/40 bg-dfui-accent/10 px-2 py-1 text-[9px] text-dfui-accent"><Play size={11} /> Recreate</button>
            {onRevealPath ? <button type="button" onClick={() => onRevealPath(item.path)} className="rounded border border-dfui-border/50 p-1 text-dfui-muted hover:text-dfui-fg" title="Show recipe file" aria-label={`Show ${title} file`}><FolderOpen size={11} /></button> : null}
            <button type="button" onClick={() => void deleteRecipeFromLibrary(item.filename).then(refresh).catch((error) => setMessage(String(error)))} className="ml-auto rounded border border-red-400/20 p-1 text-dfui-muted hover:text-red-300" title="Delete recipe" aria-label={`Delete ${title}`}><Trash2 size={11} /></button>
          </div>
        </article>;
      })}
      {!items.length ? <div className="rounded-lg border border-dashed border-dfui-border/60 p-5 text-center text-[10px] text-dfui-tertiary">No saved recipes yet. Import JSON or image metadata from Generate, or save one from Discover.</div> : null}
    </div>
  </div>;
}
