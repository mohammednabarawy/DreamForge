import { AlertTriangle, CheckCircle2, Download, ExternalLink, LoaderCircle, RotateCcw, Search, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { downloadQueueStatus, enqueueDownload, type DownloadItem } from "../lib/discover";
import { settingsPatchFromRecipe } from "../lib/recipe";
import {
  relocateDownloadedModel,
  resolveRecipeCivitaiResources,
  saveRecipeToLibrary,
  searchRecipeDiscovery,
  type CivitaiRecipeResource,
  type RecipeDiscoveryItem,
} from "../lib/studioBridge";
import type { GenerationSettings, LoraGalleryItem, ModelGalleryItem } from "../lib/tauri-api";
import { openExternalUrl } from "../lib/externalLinks";

type Props = {
  onChange: (patch: Partial<GenerationSettings>) => void;
  modelGallery: ModelGalleryItem[];
  loraGallery: LoraGalleryItem[];
  onRefreshInventory: () => void;
  onSaveStudioSettings?: (patch: { seed_random?: boolean }) => void | Promise<void>;
};

type RecipeDependency = {
  key: string;
  kind: "model" | "lora";
  label: string;
  weight: number;
  installed: string;
  resource?: CivitaiRecipeResource;
};

type Provider = "all" | "civitai_images" | "lexica";
const RECIPE_LIBRARY_KEY = "dreamforge.recipeLibrary.v1";

function readSavedRecipes(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(RECIPE_LIBRARY_KEY) ?? "[]");
    return Array.isArray(value) ? value.filter((id): id is string => typeof id === "string") : [];
  } catch {
    return [];
  }
}

function identity(value: string) {
  return value.split(/[\\/]/).pop()?.toLowerCase().replace(/\.(safetensors|ckpt|pt|pth|bin|gguf)$/i, "").trim() ?? "";
}

function recipeLoras(recipe: Record<string, unknown>) {
  return Array.isArray(recipe.loras) ? recipe.loras.flatMap((entry) => {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) return [];
    const row = entry as Record<string, unknown>;
    if (typeof row.filename !== "string" || !row.filename.trim()) return [];
    return [{ filename: row.filename, weight: typeof row.weight === "number" ? row.weight : 1 }];
  }) : [];
}

export function DiscoverRecipeTab({ onChange, modelGallery, loraGallery, onRefreshInventory, onSaveStudioSettings }: Props) {
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState<Provider>("civitai_images");
  const [items, setItems] = useState<RecipeDiscoveryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [searched, setSearched] = useState(false);
  const [saved, setSaved] = useState<string[]>(readSavedRecipes);
  const [hasMore, setHasMore] = useState(false);
  const [dependencyItem, setDependencyItem] = useState<RecipeDiscoveryItem | null>(null);
  const [resolverVisible, setResolverVisible] = useState(false);
  const [dependencies, setDependencies] = useState<RecipeDependency[]>([]);
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [resolving, setResolving] = useState(false);
  const [queueIds, setQueueIds] = useState<Record<string, string>>({});
  const [queue, setQueue] = useState<DownloadItem[]>([]);
  const [pendingRecipe, setPendingRecipe] = useState<Record<string, unknown> | null>(null);
  const queryRef = useRef("");
  const pageRef = useRef(1);
  const cursorRef = useRef("");
  const dialogRef = useRef<HTMLDivElement>(null);

  const saveToLibrary = async (item: RecipeDiscoveryItem) => {
    try {
      const result = await saveRecipeToLibrary(item.id, item.recipe);
      if (!result.ok) throw new Error(result.error ?? "Could not save recipe");
      setSaved((current) => {
        if (current.includes(item.id)) return current;
        const next = [...current, item.id];
        try {
          localStorage.setItem(RECIPE_LIBRARY_KEY, JSON.stringify(next));
        } catch {
          /* private mode or storage quota */
        }
        return next;
      });
      setMessage(`Saved to Recipe Library: ${result.filename ?? item.title}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  };

  const search = useCallback(async (append = false) => {
    setLoading(true);
    setSearched(true);
    setError("");
    setMessage("");
    const page = append ? pageRef.current + 1 : 1;
    try {
      const result = await searchRecipeDiscovery({
        query: queryRef.current.trim(),
        provider,
        page,
        limit: 24,
        cursor: append ? cursorRef.current : "",
      });
      setItems((current) => {
        const next = result.items ?? [];
        if (!append) return next;
        const merged = new Map(current.map((item) => [item.id, item]));
        next.forEach((item) => merged.set(item.id, item));
        return [...merged.values()];
      });
      pageRef.current = page;
      cursorRef.current = result.next_cursor ?? "";
      setHasMore(Boolean(result.next_cursor) || (result.providers ?? []).some((entry) => (entry.total ?? 0) > page * 24));
      const failed = (result.providers ?? []).filter((entry) => !entry.ok && entry.error);
      if (!result.items?.length && failed.length) {
        setError(failed.map((entry) => `${entry.provider}: ${entry.error}`).join(" · "));
      }
    } catch (cause) {
      if (!append) setItems([]);
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setLoading(false);
    }
  }, [provider]);

  useEffect(() => {
    void search(false);
  }, [search]);

  const applyRecipe = useCallback(async (recipe: Record<string, unknown>) => {
    try {
      const patch = settingsPatchFromRecipe(recipe);
      if (patch.seed !== undefined && onSaveStudioSettings) {
        await onSaveStudioSettings({ seed_random: false });
      }
      onChange(patch);
      setMessage("Recipe applied to Generate settings; review before running");
      setDependencyItem(null);
      setDependencies([]);
      setChoices({});
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Recipe is not valid");
    }
  }, [onChange, onSaveStudioSettings]);

  const recreate = async (item: RecipeDiscoveryItem) => {
    setResolving(true);
    setError("");
    setMessage("");
    try {
      const resolution = await resolveRecipeCivitaiResources(item.recipe);
      const localModel = (values: string[]) => modelGallery.find((model) =>
        values.some((value) => identity(value) && identity(value) === identity(model.engine_name || model.relative_path || model.caption)),
      )?.engine_name ?? "";
      const localLora = (values: string[]) => loraGallery.find((lora) =>
        values.some((value) => identity(value) && [lora.relative_path, lora.name, lora.stem].some((candidate) => candidate && identity(value) === identity(candidate))),
      );
      const rawLoras = recipeLoras(item.recipe);
      const matchedLoras = new Set<number>();
      const next: RecipeDependency[] = [];
      const modelResource = resolution.resources.find((resource) => resource.kind === "model");
      const recipeModel = typeof item.recipe.model === "string" ? item.recipe.model : "";
      if (modelResource || recipeModel) {
        const values = [modelResource?.filename ?? "", modelResource?.name ?? "", recipeModel];
        next.push({
          key: modelResource?.id ?? "recipe:model",
          kind: "model",
          label: modelResource?.name || recipeModel,
          weight: 1,
          installed: modelResource?.local_engine_name || (!modelResource?.sha256 ? localModel(values) : ""),
          resource: modelResource,
        });
      }
      resolution.resources.filter((resource) => resource.kind === "lora").forEach((resource) => {
        const index = rawLoras.findIndex((lora, candidate) => !matchedLoras.has(candidate)
          && [resource.filename, resource.name].some((value) => identity(value) === identity(lora.filename)));
        if (index >= 0) matchedLoras.add(index);
        const installed = resource.local_engine_name
          ? { name: resource.local_engine_name, relative_path: resource.local_engine_name }
          : !resource.sha256 ? localLora([resource.filename, resource.name, index >= 0 ? rawLoras[index].filename : ""]) : undefined;
        next.push({
          key: resource.id,
          kind: "lora",
          label: resource.name || resource.filename,
          weight: index >= 0 ? rawLoras[index].weight : resource.weight,
          installed: installed?.relative_path ?? installed?.name ?? "",
          resource,
        });
      });
      rawLoras.forEach((lora, index) => {
        if (matchedLoras.has(index)) return;
        const installed = localLora([lora.filename]);
        next.push({
          key: `recipe:lora:${index}`,
          kind: "lora",
          label: lora.filename,
          weight: lora.weight,
          installed: installed?.relative_path ?? installed?.name ?? "",
        });
      });
      const missing = next.some((dependency) => !dependency.installed);
      if (!missing) {
        const localRecipe = { ...item.recipe };
        const model = next.find((dependency) => dependency.kind === "model");
        if (model?.installed) localRecipe.model = model.installed;
        localRecipe.loras = next.filter((dependency) => dependency.kind === "lora").map((dependency) => ({ filename: dependency.installed, weight: dependency.weight }));
        await applyRecipe(localRecipe);
        return;
      }
      setDependencyItem(item);
      setResolverVisible(true);
      setDependencies(next);
      setChoices(Object.fromEntries(next.map((dependency) => [
        dependency.key,
        dependency.installed ? `local:${dependency.installed}` : dependency.resource?.downloadable ? "download" : dependency.kind === "lora" ? "skip" : "",
      ])));
      if (resolution.errors.length) {
        setError(`Some Civitai resources could not be resolved: ${resolution.errors.map((entry) => entry.error).join(" · ")}`);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setResolving(false);
    }
  };

  const resolvedRecipe = useMemo(() => {
    if (!dependencyItem) return null;
    const recipe = { ...dependencyItem.recipe };
    const model = dependencies.find((dependency) => dependency.kind === "model");
    const modelChoice = model ? choices[model.key] : "";
    if (model && modelChoice) recipe.model = modelChoice === "download" ? model.resource?.filename : modelChoice.slice(6);
    recipe.loras = dependencies.filter((dependency) => dependency.kind === "lora" && choices[dependency.key] !== "skip").flatMap((dependency) => {
      const choice = choices[dependency.key];
      const filename = choice === "download" ? dependency.resource?.filename : choice?.startsWith("local:") ? choice.slice(6) : "";
      return filename ? [{ filename, weight: dependency.weight }] : [];
    });
    return recipe;
  }, [choices, dependencies, dependencyItem]);

  const resolveAndApply = async () => {
    if (!resolvedRecipe) return;
    const unresolvedModel = dependencies.find((dependency) => dependency.kind === "model" && !choices[dependency.key]);
    if (unresolvedModel) {
      setError("Choose a local model or download the original model before applying this recipe.");
      return;
    }
    setResolving(true);
    setError("");
    try {
      const downloads = dependencies.filter((dependency) => choices[dependency.key] === "download" && dependency.resource);
      if (!downloads.length) {
        await applyRecipe(resolvedRecipe);
        return;
      }
      const queued = await Promise.all(downloads.map(async (dependency) => {
        const resource = dependency.resource!;
        const result = await enqueueDownload({
          url: resource.download_url,
          category: resource.category,
          filename: resource.filename,
          expected_sha256: resource.sha256,
          provider: "civitai",
          provider_asset_id: resource.model_id,
          provider_version_id: resource.model_version_id,
        });
        if (!result.ok) throw new Error(result.error || `Could not queue ${resource.name}`);
        return [dependency.key, result.item.id] as const;
      }));
      setPendingRecipe(resolvedRecipe);
      setQueueIds(Object.fromEntries(queued));
      setMessage("Original Civitai files added to Download Manager. The recipe will apply after verified installation.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setResolving(false);
    }
  };

  const dismissResolver = () => {
    if (Object.keys(queueIds).length) {
      setResolverVisible(false);
      return;
    }
    setDependencyItem(null);
    setQueueIds({});
    setPendingRecipe(null);
  };

  useEffect(() => {
    if (dependencyItem && resolverVisible) dialogRef.current?.focus();
  }, [dependencyItem, resolverVisible]);

  useEffect(() => {
    if (!Object.keys(queueIds).length || !pendingRecipe) return;
    let alive = true;
    const tick = async () => {
      try {
        const items = await downloadQueueStatus();
        if (!alive) return;
        setQueue(items);
        const watched = Object.values(queueIds).map((id) => items.find((item) => item.id === id)).filter((item): item is DownloadItem => Boolean(item));
        if (watched.some((item) => item.state.startsWith("failed") || item.state === "cancelled")) {
          setError(watched.find((item) => item.state.startsWith("failed") || item.state === "cancelled")?.error || "A required download failed. Choose another file or retry.");
          setQueueIds({});
          return;
        }
        if (watched.length === Object.keys(queueIds).length && watched.every((item) => item.state === "installed")) {
          const readyRecipe = { ...pendingRecipe };
          const downloadedModel = dependencies.find((dependency) => dependency.kind === "model" && queueIds[dependency.key]);
          if (downloadedModel) {
            const item = watched.find((candidate) => candidate.id === queueIds[downloadedModel.key]);
            if (item) {
              const relocation = await relocateDownloadedModel({ path: item.final_path, category: item.category, filename: item.filename });
              const filename = relocation.destination?.split(/[\\/]/).pop() || item.filename;
              readyRecipe.model = relocation.moved && relocation.category && relocation.category !== "checkpoints"
                ? `../${relocation.category}/${filename}`
                : filename;
            }
          }
          onRefreshInventory();
          await applyRecipe(readyRecipe);
          setQueueIds({});
          setPendingRecipe(null);
          setMessage("Required files installed and recipe applied to Generate settings");
        }
      } catch (cause) {
        if (alive) setError(cause instanceof Error ? cause.message : String(cause));
      }
    };
    void tick();
    const timer = window.setInterval(() => void tick(), 2000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [applyRecipe, dependencies, onRefreshInventory, pendingRecipe, queueIds]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-2 overflow-y-auto">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
          Prompt &amp; recipe discovery
        </p>
        <p className="mt-0.5 text-[11px] leading-snug text-dfui-tertiary">
          Recreate preserves recorded generation settings and checks model/LoRA availability before anything is applied.
        </p>
      </div>

      <form
        className="flex gap-1.5"
        aria-label="Search prompt recipes"
        onSubmit={(event) => {
          event.preventDefault();
          void search();
        }}
      >
        <input
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            queryRef.current = event.target.value;
            setHasMore(false);
          }}
          placeholder="Search prompts…"
          aria-label="Prompt search"
          className="df-input min-w-0 flex-1 px-2.5 py-1.5 text-xs"
        />
        <select
          value={provider}
          onChange={(event) => setProvider(event.target.value as Provider)}
          aria-label="Recipe provider"
          className="df-select w-28 px-1.5 py-1.5 text-[10px]"
        >
          <option value="all">All sources</option>
          <option value="civitai_images">Civitai</option>
          <option value="lexica">Lexica</option>
        </select>
        <button
          type="submit"
          disabled={loading}
          className="inline-flex shrink-0 items-center gap-1 rounded-lg bg-df-orange px-2.5 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
        >
          <Search size={13} /> Search
        </button>
      </form>

      {message ? <p className="text-[10px] text-dfui-accent" role="status">{message}</p> : null}
      {error ? <p className="text-[10px] text-red-200" role="alert">{error}</p> : null}
      {loading ? <p className="text-[11px] text-dfui-tertiary">Loading recipe metadata…</p> : null}

      {searched && !loading && !items.length && !error ? (
        <p className="rounded-lg border border-dfui-border/40 px-2.5 py-3 text-[11px] text-dfui-tertiary">
          No metadata-rich recipes found. Try a broader prompt.
        </p>
      ) : null}

      <div className="grid shrink-0 grid-cols-1 gap-2">
        {items.map((item) => {
          const isSaved = saved.includes(item.id);
          const score = item.completeness?.score;
          const recipe = item.recipe;
          const prompt = typeof recipe.positive_prompt === "string" ? recipe.positive_prompt : "";
          return (
            <article key={item.id} className="overflow-hidden rounded-lg border border-dfui-border/50 bg-dfui-bg/25">
              {item.image_url ? (
                <img
                  src={item.image_url}
                  alt={item.title}
                  loading="lazy"
                  decoding="async"
                  referrerPolicy="no-referrer"
                  className="aspect-square w-full object-cover"
                />
              ) : null}
              <div className="space-y-1.5 p-2">
                <div className="flex items-start gap-1">
                  <p className="min-w-0 flex-1 truncate text-[10px] font-semibold text-dfui-fg">{item.title}</p>
                  {isSaved ? (
                    <span className="inline-flex shrink-0 items-center gap-1 rounded bg-emerald-500/15 px-1.5 py-0.5 text-[8px] text-emerald-200" title="In Recipe Library">
                      <CheckCircle2 size={10} /> In Library
                    </span>
                  ) : null}
                  {item.source_url ? (
                    <button type="button" onClick={() => void openExternalUrl(item.source_url)} aria-label={`Open ${item.title} source`} className="text-dfui-tertiary hover:text-dfui-fg">
                      <ExternalLink size={11} />
                    </button>
                  ) : null}
                </div>
                <p className="line-clamp-3 text-[10px] leading-snug text-dfui-tertiary">{prompt || "Prompt unavailable"}</p>
                <p className="text-[9px] text-dfui-muted">
                  {[
                    item.provider,
                    recipe.model,
                    recipe.sampler,
                    recipe.steps ? `${recipe.steps} steps` : "",
                    recipe.cfg_scale ? `CFG ${recipe.cfg_scale}` : "",
                    recipe.aspect_ratio,
                    recipe.seed != null ? `seed ${recipe.seed}` : "",
                  ].filter(Boolean).join(" · ") || (score == null ? "incomplete" : `${Math.round(score * 100)}% complete`)}
                </p>
                <div className="flex gap-1">
                  <button type="button" disabled={resolving} onClick={() => void recreate(item)} className="inline-flex flex-1 items-center justify-center gap-1 rounded border border-dfui-accent/50 px-1.5 py-1 text-[9px] text-dfui-fg hover:bg-dfui-accent/10 disabled:opacity-50">
                    {resolving ? <LoaderCircle size={11} className="animate-spin" /> : <RotateCcw size={11} />} Recreate
                  </button>
                  <button type="button" disabled={isSaved} onClick={() => void saveToLibrary(item)} aria-label={isSaved ? `${item.title} is in Recipe Library` : `Save ${item.title} recipe`} className="inline-flex items-center justify-center rounded border border-dfui-border/50 px-1.5 py-1 text-dfui-secondary hover:text-dfui-fg disabled:text-emerald-300">
                    {isSaved ? <CheckCircle2 size={11} /> : <Download size={11} />}
                  </button>
                </div>
              </div>
            </article>
          );
        })}
      </div>
      {items.length > 0 && hasMore ? (
        <button type="button" onClick={() => void search(true)} disabled={loading} className="mx-auto rounded border border-dfui-border/60 px-4 py-1.5 text-[10px] text-dfui-secondary hover:text-dfui-fg disabled:opacity-50">
          {loading ? "Loading…" : "Load more recipes"}
        </button>
      ) : null}

      {dependencyItem && resolverVisible ? (
        <div
          ref={dialogRef}
          tabIndex={-1}
          onKeyDown={(event) => {
            if (event.key === "Escape") dismissResolver();
          }}
          className="fixed bottom-4 right-4 top-16 z-40 flex w-[min(34rem,calc(100vw-2rem))] outline-none"
          role="dialog"
          aria-modal="false"
          aria-labelledby="recipe-dependencies-title"
        >
          <div className="flex w-full flex-col overflow-hidden rounded-xl border border-dfui-border bg-dfui-panel/98 shadow-2xl backdrop-blur-md">
            <div className="flex items-start gap-3 border-b border-dfui-border/60 p-4">
              <AlertTriangle className="mt-0.5 shrink-0 text-amber-300" size={18} />
              <div className="min-w-0 flex-1">
                <h2 id="recipe-dependencies-title" className="text-sm font-semibold text-dfui-fg">Resolve recipe files</h2>
                <p className="mt-1 text-[11px] text-dfui-tertiary">Download exact Civitai versions, replace them with installed files, or skip optional LoRAs.</p>
              </div>
              <button
                type="button"
                aria-label="Close recipe file resolver"
                title={Object.keys(queueIds).length ? "Downloads continue in Download Manager" : "Close"}
                onClick={dismissResolver}
                className="rounded p-1 text-dfui-tertiary hover:bg-dfui-border/30 hover:text-dfui-fg"
              >
                <X size={16} />
              </button>
            </div>

            <div className="space-y-2 overflow-y-auto p-4">
              {dependencies.map((dependency) => {
                const resource = dependency.resource;
                const queueItem = queue.find((item) => item.id === queueIds[dependency.key]);
                return (
                  <div key={dependency.key} className="rounded-lg border border-dfui-border/60 bg-dfui-bg/30 p-3">
                    <div className="mb-2 flex items-center gap-2">
                      <span className="rounded bg-dfui-border/40 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-dfui-secondary">{dependency.kind}</span>
                      <span className="min-w-0 flex-1 truncate text-xs text-dfui-fg">{dependency.label}</span>
                      {dependency.installed ? <span className="inline-flex items-center gap-1 text-[9px] text-emerald-300"><CheckCircle2 size={10} /> Installed</span> : null}
                      {resource?.source_url ? (
                        <button type="button" onClick={() => void openExternalUrl(resource.source_url)} className="inline-flex items-center gap-1 text-[9px] text-dfui-accent hover:underline">
                          Civitai <ExternalLink size={10} />
                        </button>
                      ) : null}
                    </div>
                    <select
                      value={choices[dependency.key] ?? ""}
                      disabled={Boolean(Object.keys(queueIds).length)}
                      aria-label={`Resolution for ${dependency.label}`}
                      onChange={(event) => setChoices((current) => ({ ...current, [dependency.key]: event.target.value }))}
                      className="df-select w-full px-2 py-1.5 text-[11px]"
                    >
                      {dependency.kind === "model" && !choices[dependency.key] ? <option value="">Choose a model…</option> : null}
                      {resource?.downloadable ? <option value="download">Download original from Civitai — {resource.filename}</option> : null}
                      {dependency.kind === "model" ? modelGallery.map((model) => (
                        <option key={model.engine_name} value={`local:${model.engine_name}`}>Use installed: {model.caption || model.engine_name}</option>
                      )) : loraGallery.map((lora) => {
                        const value = lora.relative_path ?? lora.name;
                        return <option key={value} value={`local:${value}`}>Use installed: {lora.stem || lora.name}</option>;
                      })}
                      {dependency.kind === "lora" ? <option value="skip">Skip this LoRA</option> : null}
                    </select>
                    {resource?.error ? <p className="mt-1 text-[9px] text-amber-200">{resource.error}</p> : null}
                    {queueItem ? (
                      <div className="mt-2 flex items-center gap-2 text-[9px] text-dfui-tertiary" role="status">
                        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-dfui-border/40">
                          <div className="h-full rounded-full bg-dfui-accent transition-all" style={{ width: `${Math.max(0, Math.min(100, queueItem.progress_pct))}%` }} />
                        </div>
                        <span>{queueItem.state === "installed" ? "Installed" : `${queueItem.progress_pct.toFixed(0)}%`}</span>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-dfui-border/60 p-4">
              <button type="button" onClick={dismissResolver} title={Object.keys(queueIds).length ? "Downloads continue in Download Manager" : undefined} className="rounded-lg border border-dfui-border px-3 py-1.5 text-[11px] text-dfui-secondary hover:text-dfui-fg">Cancel</button>
              <button type="button" disabled={resolving || Boolean(Object.keys(queueIds).length)} onClick={() => void resolveAndApply()} className="inline-flex items-center gap-1.5 rounded-lg bg-df-orange px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-50">
                {resolving || Object.keys(queueIds).length ? <LoaderCircle size={12} className="animate-spin" /> : <CheckCircle2 size={12} />}
                {Object.keys(queueIds).length ? "Installing…" : "Resolve & apply"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
