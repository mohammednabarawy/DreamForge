import { Download, ExternalLink, RotateCcw, Search } from "lucide-react";
import { useCallback, useState } from "react";
import { settingsPatchFromRecipe } from "../lib/recipe";
import {
  searchRecipeDiscovery,
  type RecipeDiscoveryItem,
} from "../lib/studioBridge";
import type { GenerationSettings } from "../lib/tauri-api";

type Props = {
  onChange: (patch: Partial<GenerationSettings>) => void;
};

type Provider = "all" | "civitai_images" | "lexica";

function saveRecipe(item: RecipeDiscoveryItem) {
  const blob = new Blob([JSON.stringify(item.recipe, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${item.provider}-recipe.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function DiscoverRecipeTab({ onChange }: Props) {
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState<Provider>("all");
  const [items, setItems] = useState<RecipeDiscoveryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const search = useCallback(async () => {
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const result = await searchRecipeDiscovery({
        query: query.trim(),
        provider,
        limit: 24,
      });
      setItems(result.items ?? []);
      const failed = (result.providers ?? []).filter((entry) => !entry.ok && entry.error);
      if (!result.items?.length && failed.length) {
        setError(failed.map((entry) => `${entry.provider}: ${entry.error}`).join(" · "));
      }
    } catch (cause) {
      setItems([]);
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setLoading(false);
    }
  }, [provider, query]);

  const recreate = (item: RecipeDiscoveryItem) => {
    try {
      onChange(settingsPatchFromRecipe(item.recipe));
      setMessage("Recipe applied to Generate settings; review before running");
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Recipe is not valid");
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-2 overflow-y-auto">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-dfui-muted">
          Prompt &amp; recipe discovery
        </p>
        <p className="mt-0.5 text-[11px] leading-snug text-dfui-tertiary">
          Browse metadata only. Recreate applies known fields to Generate; it never runs or downloads a remote image.
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
          onChange={(event) => setQuery(event.target.value)}
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

      {!loading && !items.length && !error ? (
        <p className="rounded-lg border border-dfui-border/40 px-2.5 py-3 text-[11px] text-dfui-tertiary">
          No metadata-rich recipes found. Try a broader prompt.
        </p>
      ) : null}

      <div className="grid min-h-0 grid-cols-2 gap-2">
        {items.map((item) => {
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
                  className="aspect-square w-full object-cover"
                />
              ) : null}
              <div className="space-y-1.5 p-2">
                <div className="flex items-start gap-1">
                  <p className="min-w-0 flex-1 truncate text-[10px] font-semibold text-dfui-fg">{item.title}</p>
                  {item.source_url ? (
                    <a href={item.source_url} target="_blank" rel="noreferrer" aria-label={`Open ${item.title} source`} className="text-dfui-tertiary hover:text-dfui-fg">
                      <ExternalLink size={11} />
                    </a>
                  ) : null}
                </div>
                <p className="line-clamp-3 text-[10px] leading-snug text-dfui-tertiary">{prompt || "Prompt unavailable"}</p>
                <p className="text-[9px] text-dfui-muted">
                  {item.provider} · {score == null ? "incomplete" : `${Math.round(score * 100)}% complete`}
                </p>
                <div className="flex gap-1">
                  <button type="button" onClick={() => recreate(item)} className="inline-flex flex-1 items-center justify-center gap-1 rounded border border-dfui-accent/50 px-1.5 py-1 text-[9px] text-dfui-fg hover:bg-dfui-accent/10">
                    <RotateCcw size={11} /> Recreate
                  </button>
                  <button type="button" onClick={() => saveRecipe(item)} aria-label={`Save ${item.title} recipe`} className="inline-flex items-center justify-center rounded border border-dfui-border/50 px-1.5 py-1 text-dfui-secondary hover:text-dfui-fg">
                    <Download size={11} />
                  </button>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
