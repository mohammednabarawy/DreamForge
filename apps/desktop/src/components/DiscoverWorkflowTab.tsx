import { useEffect, useMemo, useState } from "react";
import { Bookmark, Check, CheckCircle2, Download, FileSearch, RefreshCw, Workflow } from "lucide-react";
import { pickWorkflowFile } from "../lib/tauri-api";
import { analyzeWorkflowCompatibility, compileWorkflowIR, compileWorkflowRecipe, downloadWorkflow, saveWorkflowFile, searchWorkflowIndex, type DiscoverWorkflowTemplate, type WorkflowCompatibilityReport, type WorkflowIRCompileResult, type WorkflowIndexItem, type WorkflowRecipeCompileResult } from "../lib/studioBridge";

const STORAGE_KEY = "dreamforge.workflowLibrary.v1";
const INSTALLED_KEY = "dreamforge.workflowInstalled.v1";

function readSaved(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(value) ? value.filter((id): id is string => typeof id === "string") : [];
  } catch {
    return [];
  }
}

function saveSaved(ids: string[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch {
    /* private mode or storage quota */
  }
}

type Props = {
  templates: DiscoverWorkflowTemplate[];
  loading: boolean;
  error?: string | null;
  onApplyRecipe: (recipe: Record<string, unknown>, source?: string) => void;
};

export function DiscoverWorkflowTab({ templates, loading, error, onApplyRecipe }: Props) {
  const [query, setQuery] = useState("");
  const [saved, setSaved] = useState<string[]>(() => readSaved());
  const [installed, setInstalled] = useState<string[]>(() => {
    try {
      const value = JSON.parse(localStorage.getItem(INSTALLED_KEY) ?? "[]");
      return Array.isArray(value) ? value.filter((id): id is string => typeof id === "string") : [];
    } catch {
      return [];
    }
  });
  const [remoteTemplates, setRemoteTemplates] = useState<WorkflowIndexItem[]>([]);
  const [indexBusy, setIndexBusy] = useState(false);
  const [indexError, setIndexError] = useState("");
  const [analysis, setAnalysis] = useState<WorkflowCompatibilityReport | null>(null);
  const [compiled, setCompiled] = useState<WorkflowRecipeCompileResult | null>(null);
  const [ir, setIr] = useState<WorkflowIRCompileResult | null>(null);
  const [analyzedPath, setAnalyzedPath] = useState("");
  const [savedPath, setSavedPath] = useState("");
  const [saveError, setSaveError] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [category, setCategory] = useState("all");
  const [tag, setTag] = useState("all");
  const [source, setSource] = useState<"all" | "open" | "api">("all");
  const q = query.trim().toLowerCase();
  const allTemplates = useMemo<WorkflowIndexItem[]>(
    () => remoteTemplates.length ? remoteTemplates : templates,
    [templates, remoteTemplates],
  );
  const categories = useMemo(() => [...new Set(allTemplates.map((item) => item.category).filter(Boolean) as string[])].sort(), [allTemplates]);
  const tags = useMemo(() => [...new Set(allTemplates.flatMap((item) => item.tags ?? []))].sort(), [allTemplates]);
  const filtered = useMemo(
    () => allTemplates.filter((item) =>
      (!q || `${item.label} ${item.summary} ${item.operation} ${(item.tags ?? []).join(" ")} ${(item.required_models ?? []).join(" ")}`.toLowerCase().includes(q)) &&
      (category === "all" || item.category === category) &&
      (tag === "all" || item.tags?.includes(tag)) &&
      (source === "all" || (source === "open" ? item.open_source === true : item.tags?.includes("API")))
    ),
    [allTemplates, category, q, source, tag],
  );

  const toggleSaved = (id: string) => {
    setSaved((current) => {
      const next = current.includes(id) ? current.filter((item) => item !== id) : [...current, id];
      saveSaved(next);
      return next;
    });
  };

  const inspectPath = async (path: string) => {
    setAnalyzedPath(path);
    setSavedPath("");
    setSaveError("");
    setAnalyzing(true);
    try {
      const report = await analyzeWorkflowCompatibility(path);
      setAnalysis(report);
      setCompiled(await compileWorkflowRecipe(path));
      setIr(await compileWorkflowIR(path));
    } catch (error) {
      setAnalysis({ ok: false, state: "INVALID", reason: error instanceof Error ? error.message : String(error) });
      setCompiled(null);
      setIr(null);
    } finally {
      setAnalyzing(false);
    }
  };

  const analyzeLocalWorkflow = async () => {
    const path = await pickWorkflowFile();
    if (path) await inspectPath(path);
  };

  const loadOfficialIndex = async () => {
    setIndexBusy(true);
    setIndexError("");
    try {
      const result = await searchWorkflowIndex();
      if (!result.ok) throw new Error(result.error ?? "Could not load workflow index");
      setRemoteTemplates(result.items ?? []);
    } catch (error) {
      setIndexError(error instanceof Error ? error.message : String(error));
    } finally {
      setIndexBusy(false);
    }
  };

  useEffect(() => {
    void loadOfficialIndex();
  }, []);

  const downloadRemoteWorkflow = async (item: WorkflowIndexItem) => {
    if (!item.url) return;
    setIndexBusy(true);
    setIndexError("");
    try {
      const result = await downloadWorkflow(item.url, `${item.id}.json`);
      if (!result.ok) throw new Error(result.error ?? "Could not download workflow");
      const path = result.path ?? "";
      if (path) await inspectPath(path);
      setSavedPath(path || result.filename || "workflow saved");
      setInstalled((current) => {
        if (current.includes(item.id)) return current;
        const next = [...current, item.id];
        try {
          localStorage.setItem(INSTALLED_KEY, JSON.stringify(next));
        } catch {
          /* private mode or storage quota */
        }
        return next;
      });
    } catch (error) {
      setIndexError(error instanceof Error ? error.message : String(error));
    } finally {
      setIndexBusy(false);
    }
  };

  const saveLocalWorkflow = async () => {
    if (!analyzedPath) return;
    setAnalyzing(true);
    setSaveError("");
    try {
      const result = await saveWorkflowFile(analyzedPath);
      if (!result.ok) throw new Error(result.error ?? "Could not save workflow");
      setSavedPath(result.path ?? result.filename ?? "saved");
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : String(error));
    } finally {
      setAnalyzing(false);
    }
  };

  const exportRecipe = () => {
    if (!compiled?.recipe) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(compiled.recipe, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "dreamforge-workflow-recipe.json";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="shrink-0 rounded-lg border border-dfui-accent/25 bg-dfui-accent/5 px-2.5 py-2">
        <div className="flex items-center gap-1.5">
          <Workflow size={13} className="text-dfui-accent" />
          <p className="text-[10px] font-semibold text-dfui-fg">Official ComfyUI workflow library</p>
          <span className="ml-auto text-[9px] text-dfui-tertiary">{remoteTemplates.length} official · {saved.length} saved</span>
        </div>
        <p className="mt-1 text-[9px] leading-snug text-dfui-tertiary">
          Browse the official ComfyUI picker catalog. Import downloads a safe copy for compatibility analysis; it never executes automatically.
        </p>
      </div>
      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search workflows…"
        className="df-input shrink-0 px-2.5 py-1.5 text-xs"
        aria-label="Search workflow templates"
      />
      <div className="grid shrink-0 grid-cols-2 gap-1 sm:grid-cols-4">
        <select value={category} onChange={(event) => setCategory(event.target.value)} className="df-select px-1.5 py-1 text-[9px]" aria-label="Workflow category">
          <option value="all">All categories</option>
          {categories.map((value) => <option key={value} value={value}>{value}</option>)}
        </select>
        <select value={tag} onChange={(event) => setTag(event.target.value)} className="df-select px-1.5 py-1 text-[9px]" aria-label="Workflow filter">
          <option value="all">All filters</option>
          {tags.map((value) => <option key={value} value={value}>{value}</option>)}
        </select>
        <select value={source} onChange={(event) => setSource(event.target.value as "all" | "open" | "api")} className="df-select px-1.5 py-1 text-[9px]" aria-label="Workflow source type">
          <option value="all">All workflows</option>
          <option value="open">Open source</option>
          <option value="api">API workflows</option>
        </select>
        <button type="button" onClick={() => void loadOfficialIndex()} disabled={indexBusy} className="inline-flex items-center justify-center gap-1 rounded border border-dfui-border/50 px-2 py-1 text-[9px] text-dfui-secondary hover:text-dfui-fg disabled:opacity-50">
          <RefreshCw size={10} /> {indexBusy ? "Loading…" : "Refresh official"}
        </button>
      </div>
      {indexError && <p className="rounded border border-red-500/30 bg-red-500/10 px-2 py-1 text-[9px] text-red-200">{indexError}</p>}
      <button
        type="button"
        onClick={() => void analyzeLocalWorkflow()}
        disabled={analyzing}
        className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded border border-dfui-border/50 px-2 py-1.5 text-[10px] text-dfui-secondary hover:text-dfui-fg disabled:opacity-50"
      >
        <FileSearch size={12} /> {analyzing ? "Analyzing…" : "Analyze local workflow"}
      </button>
      {analysis && (
        <div className="shrink-0 rounded border border-dfui-border/50 bg-dfui-bg/30 px-2 py-1.5 text-[9px]" role="status">
          <span className={`font-semibold ${analysis.state === "NATIVE" ? "text-emerald-300" : analysis.state === "INVALID" ? "text-red-300" : "text-amber-200"}`}>
            {analysis.state ?? "INVALID"}
          </span>
          <span className="ml-1.5 text-dfui-tertiary">{analysis.reason}</span>
          {!!analysis.dependencies?.length && <p className="mt-1 truncate text-dfui-tertiary">Dependencies: {analysis.dependencies.join(", ")}</p>}
          {ir?.can_execute && <p className="mt-1 text-emerald-200">IR {ir.version} verified · native recipe is safe to execute</p>}
          {analyzedPath && (
            <button type="button" onClick={() => void saveLocalWorkflow()} disabled={analyzing} className="mt-1 inline-flex items-center gap-1 rounded border border-dfui-border/50 px-1.5 py-1 text-[9px] text-dfui-fg hover:bg-dfui-border/20 disabled:opacity-50">
              <Download size={10} /> Save safe copy to Library
            </button>
          )}
          {savedPath && <p className="mt-1 truncate text-emerald-200" role="status">{savedPath}</p>}
          {saveError && <p className="mt-1 text-red-200" role="alert">{saveError}</p>}
          {compiled?.can_recreate && (
            <div className="mt-1 space-y-1">
              <p className="text-dfui-tertiary">
                {String(compiled.recipe?.model ?? "Unknown model")} · {String(compiled.recipe?.sampler ?? "sampler?")} / {String((compiled.recipe?.settings as Record<string, unknown> | undefined)?.scheduler ?? "scheduler?")} · {String(compiled.recipe?.steps ?? "?")} steps · CFG {String(compiled.recipe?.cfg_scale ?? "?")} · {String(compiled.recipe?.aspect_ratio ?? "size?")}
              </p>
              <p className="line-clamp-2 text-dfui-secondary">{String(compiled.recipe?.positive_prompt ?? "")}</p>
              <div className="flex flex-wrap gap-1">
              <button type="button" onClick={exportRecipe} className="inline-flex items-center gap-1 rounded border border-dfui-accent/50 px-1.5 py-1 text-[9px] text-dfui-fg hover:bg-dfui-accent/10">
                <Download size={10} /> Export portable recipe
              </button>
              {ir?.can_execute && <button type="button" onClick={() => onApplyRecipe(compiled.recipe!, analyzedPath)} className="inline-flex items-center gap-1 rounded border border-emerald-400/50 px-1.5 py-1 text-[9px] text-emerald-100 hover:bg-emerald-400/10">
                <Check size={10} /> Use in Generate
              </button>}
              </div>
            </div>
          )}
          {!compiled?.can_recreate && !!compiled?.missing?.length && <p className="mt-1 text-red-200">Recipe unavailable: {compiled.missing.join(", ")}</p>}
        </div>
      )}
      {error && <p className="rounded border border-red-500/30 bg-red-500/10 px-2 py-1.5 text-[10px] text-red-200">{error}</p>}
      <div className="df-gallery-pane space-y-2">
        {(loading || (indexBusy && !remoteTemplates.length)) && <p className="py-8 text-center text-xs text-dfui-muted">Loading workflow templates…</p>}
        {!loading && filtered.map((item) => {
          const isSaved = saved.includes(item.id);
          const isInstalled = installed.includes(item.id);
          return (
            <article key={item.id} className="rounded-lg border border-dfui-border/50 bg-dfui-panel/60 p-2.5">
              <div className="flex items-start gap-2">
                {item.thumbnail_url ? <img src={item.thumbnail_url} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer" className="h-10 w-10 rounded object-cover" /> : null}
                <div className="min-w-0 flex-1">
                  <h3 className="text-xs font-semibold text-dfui-fg">{item.label}</h3>
                  <p className="mt-0.5 text-[9px] uppercase tracking-wide text-dfui-tertiary">{item.category ?? item.mode} · {item.operation}</p>
                </div>
                {isInstalled && <span className="inline-flex shrink-0 items-center gap-1 rounded bg-emerald-500/15 px-1.5 py-1 text-[8px] text-emerald-200" title="In Workflow Library"><CheckCircle2 size={10} /> In Library</span>}
                <button
                  type="button"
                  onClick={() => toggleSaved(item.id)}
                  aria-pressed={isSaved}
                  className={`inline-flex shrink-0 items-center gap-1 rounded border px-2 py-1 text-[9px] ${isSaved ? "border-dfui-accent/60 bg-dfui-accent/15 text-dfui-fg" : "border-dfui-border/50 text-dfui-muted hover:text-dfui-fg"}`}
                >
                  {isSaved ? <Check size={11} /> : <Bookmark size={11} />}
                  {isSaved ? "Bookmarked" : "Bookmark"}
                </button>
                {item.url && <button type="button" onClick={() => void downloadRemoteWorkflow(item)} disabled={indexBusy || isInstalled} className="inline-flex shrink-0 items-center gap-1 rounded border border-dfui-accent/50 px-2 py-1 text-[9px] text-dfui-fg hover:bg-dfui-accent/10 disabled:opacity-50">
                  {isInstalled ? <CheckCircle2 size={11} /> : <Download size={11} />} {isInstalled ? "Installed" : "Import"}
                </button>}
              </div>
              <p className="mt-2 text-[10px] leading-snug text-dfui-secondary">{item.summary}</p>
              <div className="mt-2 flex flex-wrap gap-1">
                {(item.tags ?? []).slice(0, 4).map((value) => <span key={value} className="rounded bg-dfui-accent/10 px-1.5 py-0.5 text-[8px] text-dfui-secondary">{value}</span>)}
                {(item.required_models ?? []).slice(0, 4).map((model) => <span key={model} className="rounded bg-dfui-border/30 px-1.5 py-0.5 text-[8px] text-dfui-tertiary">{model}</span>)}
                {(item.required_node_packs ?? []).slice(0, 3).map((pack) => <span key={pack} className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[8px] text-amber-200">{pack}</span>)}
              </div>
            </article>
          );
        })}
        {!loading && filtered.length === 0 && <p className="py-8 text-center text-xs text-dfui-muted">No workflow templates match.</p>}
      </div>
    </div>
  );
}
