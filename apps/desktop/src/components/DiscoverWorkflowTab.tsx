import { useMemo, useState } from "react";
import { Bookmark, Check, Workflow } from "lucide-react";
import type { DiscoverWorkflowTemplate } from "../lib/studioBridge";

const STORAGE_KEY = "dreamforge.workflowLibrary.v1";

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
};

export function DiscoverWorkflowTab({ templates, loading, error }: Props) {
  const [query, setQuery] = useState("");
  const [saved, setSaved] = useState<string[]>(() => readSaved());
  const q = query.trim().toLowerCase();
  const filtered = useMemo(
    () => templates.filter((item) => !q || `${item.label} ${item.summary} ${item.operation}`.toLowerCase().includes(q)),
    [q, templates],
  );

  const toggleSaved = (id: string) => {
    setSaved((current) => {
      const next = current.includes(id) ? current.filter((item) => item !== id) : [...current, id];
      saveSaved(next);
      return next;
    });
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="shrink-0 rounded-lg border border-dfui-accent/25 bg-dfui-accent/5 px-2.5 py-2">
        <div className="flex items-center gap-1.5">
          <Workflow size={13} className="text-dfui-accent" />
          <p className="text-[10px] font-semibold text-dfui-fg">ComfyUI workflow templates</p>
          <span className="ml-auto text-[9px] text-dfui-tertiary">{saved.length} saved</span>
        </div>
        <p className="mt-1 text-[9px] leading-snug text-dfui-tertiary">
          Browse-only templates from DreamForge&apos;s local registry. Saving a template never executes or installs a workflow.
        </p>
      </div>
      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search workflows…"
        className="df-input shrink-0 px-2.5 py-1.5 text-xs"
        aria-label="Search workflow templates"
      />
      {error && <p className="rounded border border-red-500/30 bg-red-500/10 px-2 py-1.5 text-[10px] text-red-200">{error}</p>}
      <div className="df-gallery-pane space-y-2">
        {loading && <p className="py-8 text-center text-xs text-dfui-muted">Loading workflow templates…</p>}
        {!loading && filtered.map((item) => {
          const isSaved = saved.includes(item.id);
          return (
            <article key={item.id} className="rounded-lg border border-dfui-border/50 bg-dfui-panel/60 p-2.5">
              <div className="flex items-start gap-2">
                <div className="min-w-0 flex-1">
                  <h3 className="text-xs font-semibold text-dfui-fg">{item.label}</h3>
                  <p className="mt-0.5 text-[9px] uppercase tracking-wide text-dfui-tertiary">{item.mode} · {item.operation}</p>
                </div>
                <button
                  type="button"
                  onClick={() => toggleSaved(item.id)}
                  aria-pressed={isSaved}
                  className={`inline-flex shrink-0 items-center gap-1 rounded border px-2 py-1 text-[9px] ${isSaved ? "border-dfui-accent/60 bg-dfui-accent/15 text-dfui-fg" : "border-dfui-border/50 text-dfui-muted hover:text-dfui-fg"}`}
                >
                  {isSaved ? <Check size={11} /> : <Bookmark size={11} />}
                  {isSaved ? "Saved" : "Save to Library"}
                </button>
              </div>
              <p className="mt-2 text-[10px] leading-snug text-dfui-secondary">{item.summary}</p>
              <div className="mt-2 flex flex-wrap gap-1">
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
