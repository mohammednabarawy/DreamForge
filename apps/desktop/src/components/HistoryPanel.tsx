import {
  ChevronDown,
  ChevronRight,
  LayoutGrid,
  List,
  Plus,
  RefreshCw,
  Search,
  Star,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  loadCollapsedDateGroups,
  loadFavoriteManifests,
  loadHistoryScope,
  loadHistoryViewMode,
  saveCollapsedDateGroups,
  saveFavoriteManifests,
  saveHistoryScope,
  saveHistoryViewMode,
  type HistoryScope,
  type HistoryViewMode,
} from "../lib/historyStorage";
import { groupHistoryByDate } from "../lib/historyUtils";
import type { OutputSession } from "../lib/sessions";
import type { OutputItem } from "../lib/tauri-api";
import { HistoryItemRow } from "./HistoryItemRow";

type Props = {
  sessions: OutputSession[];
  activeSessionId: string;
  onSaveSessionChange: (sessionId: string) => void;
  onCreateSession: (name: string) => void;
  selected: OutputItem | null;
  onSelect: (item: OutputItem) => void;
  onRefresh: () => void;
  onLoadMore?: () => void;
  outputsTotal?: number;
  outputsLoaded?: number;
  loadingOutputs?: boolean;
  outputSearch: string;
  onOutputSearchChange: (query: string) => void;
  onReusePrompt: (item: OutputItem) => void;
  onEditThis?: (item: OutputItem) => void;
  onFixRegion?: (item: OutputItem) => void;
  onEnhance?: (item: OutputItem) => void;
  simpleHistoryLabels?: boolean;
  onOpenFolder: (path: string) => void;
  onCopyPath: (path: string) => void;
  onDeleteGeneration: (item: OutputItem) => void;
  onDeleteImage: (item: OutputItem, imagePath: string) => void;
  onDeleteSession?: (session: OutputSession) => void;
  historyScrollToken?: number;
};

const SCOPE_OPTIONS: { id: HistoryScope; label: string }[] = [
  { id: "all", label: "All" },
  { id: "session", label: "This project" },
  { id: "favorites", label: "Favorites" },
];

export function HistoryPanel({
  sessions,
  activeSessionId,
  onSaveSessionChange,
  onCreateSession,
  selected,
  onSelect,
  onRefresh,
  onLoadMore,
  outputsTotal = 0,
  outputsLoaded = 0,
  loadingOutputs = false,
  outputSearch,
  onOutputSearchChange,
  onReusePrompt,
  onEditThis,
  onFixRegion,
  onEnhance,
  simpleHistoryLabels = false,
  onOpenFolder,
  onCopyPath,
  onDeleteGeneration,
  onDeleteImage,
  onDeleteSession,
  historyScrollToken = 0,
}: Props) {
  const [scope, setScope] = useState<HistoryScope>(() => loadHistoryScope());
  const [collapsedDates, setCollapsedDates] = useState<Record<string, boolean>>(
    () => loadCollapsedDateGroups(),
  );
  const [viewMode, setViewMode] = useState<HistoryViewMode>(() =>
    loadHistoryViewMode(),
  );
  const [favorites, setFavorites] = useState<Set<string>>(() =>
    loadFavoriteManifests(),
  );
  const [newSessionOpen, setNewSessionOpen] = useState(false);
  const [newSessionName, setNewSessionName] = useState("");
  const onRefreshRef = useRef(onRefresh);
  onRefreshRef.current = onRefresh;

  const activeLabel = useMemo(() => {
    const s = sessions.find((x) => x.id === activeSessionId);
    return s?.label ?? activeSessionId;
  }, [sessions, activeSessionId]);

  const flatItems = useMemo(() => {
    const items: OutputItem[] = [];
    for (const session of sessions) {
      if (scope === "session" && session.id !== activeSessionId) continue;
      items.push(...session.items);
    }
    items.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
    if (scope === "favorites") {
      return items.filter((item) => favorites.has(item.manifest_path));
    }
    return items;
  }, [sessions, scope, activeSessionId, favorites]);

  const dateGroups = useMemo(
    () => groupHistoryByDate(flatItems),
    [flatItems],
  );

  const setView = (mode: HistoryViewMode) => {
    setViewMode(mode);
    saveHistoryViewMode(mode);
  };

  const setScopeFilter = (next: HistoryScope) => {
    setScope(next);
    saveHistoryScope(next);
  };

  const toggleFavorite = (manifestPath: string) => {
    setFavorites((prev) => {
      const next = new Set(prev);
      if (next.has(manifestPath)) next.delete(manifestPath);
      else next.add(manifestPath);
      saveFavoriteManifests(next);
      return next;
    });
  };

  const toggleDateGroup = (id: string) => {
    setCollapsedDates((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      saveCollapsedDateGroups(next);
      return next;
    });
  };

  useEffect(() => {
    const t = window.setTimeout(() => onRefreshRef.current(), 280);
    return () => window.clearTimeout(t);
  }, [outputSearch]);

  return (
    <aside className="flex h-full min-h-0 min-w-0 flex-col glass-panel rounded-none border-y-0 border-l-0">
      <div className="border-b border-dfui-border/60 px-2 py-2">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-dfui-tertiary">
          History
        </p>
      </div>

      <div className="space-y-2 border-b border-dfui-border/60 px-2 py-2">
        <div className="flex items-center gap-1">
          <label
            className="shrink-0 text-[10px] text-dfui-tertiary"
            htmlFor="save-session-select"
          >
            Save to
          </label>
          <select
            id="save-session-select"
            value={activeSessionId}
            onChange={(e) => onSaveSessionChange(e.target.value)}
            className="min-w-0 flex-1 rounded-lg border border-dfui-accent/30 bg-dfui-bg/50 py-1.5 pl-2 pr-6 font-mono text-[10px] text-dfui-fg focus:border-dfui-accent/50 focus:outline-none"
            title="New generations save under this project folder"
          >
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
                {s.items.length > 0 ? ` (${s.items.length})` : ""}
              </option>
            ))}
          </select>
          <button
            type="button"
            title="New project"
            onClick={() => {
              setNewSessionOpen((v) => !v);
              setNewSessionName("");
            }}
            className="shrink-0 rounded-lg border border-dfui-border/60 p-1.5 text-dfui-muted hover:border-dfui-accent/40 hover:text-dfui-fg"
          >
            <Plus size={14} />
          </button>
          {onDeleteSession && activeSessionId !== "root" && (
            <button
              type="button"
              title={`Delete project ${activeLabel}`}
              onClick={() => {
                const session = sessions.find((s) => s.id === activeSessionId);
                if (session) onDeleteSession(session);
              }}
              className="shrink-0 rounded-lg border border-dfui-border/60 p-1.5 text-dfui-muted hover:border-red-400/50 hover:text-red-300"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>

        {newSessionOpen && (
          <form
            className="flex gap-1"
            onSubmit={(e) => {
              e.preventDefault();
              onCreateSession(newSessionName);
              setNewSessionOpen(false);
              setNewSessionName("");
            }}
          >
            <input
              type="text"
              value={newSessionName}
              onChange={(e) => setNewSessionName(e.target.value)}
              placeholder="Project name…"
              autoFocus
              className="min-w-0 flex-1 rounded-lg border border-dfui-border/60 bg-dfui-bg/40 px-2 py-1.5 font-mono text-[10px] text-dfui-fg placeholder:text-dfui-tertiary focus:border-dfui-accent/40 focus:outline-none"
            />
            <button
              type="submit"
              className="shrink-0 rounded-lg border border-dfui-accent/40 bg-dfui-accent/10 px-2 py-1 text-[10px] font-medium text-dfui-fg hover:bg-dfui-accent/20"
            >
              Add
            </button>
          </form>
        )}

        <p className="truncate text-[10px] text-dfui-tertiary">
          New images save to{" "}
          <span className="font-mono text-dfui-data">
            outputs/{activeSessionId === "root" ? "" : `${activeSessionId}/`}
          </span>
          · {activeLabel}
        </p>

        <div className="flex flex-wrap gap-1">
          {SCOPE_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => setScopeFilter(opt.id)}
              className={`rounded-md border px-2 py-0.5 text-[10px] font-medium transition ${
                scope === opt.id
                  ? "border-dfui-accent/45 bg-dfui-accent/15 text-dfui-fg"
                  : "border-dfui-border/60 text-dfui-muted hover:text-dfui-fg"
              }`}
            >
              {opt.id === "favorites" ? (
                <span className="inline-flex items-center gap-1">
                  <Star size={10} />
                  {opt.label}
                </span>
              ) : (
                opt.label
              )}
            </button>
          ))}
        </div>

        <div className="relative">
          <Search
            size={12}
            className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-dfui-tertiary"
          />
          <input
            type="search"
            value={outputSearch}
            onChange={(e) => onOutputSearchChange(e.target.value)}
            placeholder="Search prompts, models…"
            className="w-full rounded-lg border border-dfui-border/60 bg-dfui-bg/40 py-1.5 pl-7 pr-2 font-mono text-[10px] text-dfui-fg placeholder:text-dfui-tertiary focus:border-dfui-accent/40 focus:outline-none"
          />
        </div>

        <div className="flex items-center justify-between gap-1">
          <p className="min-w-0 truncate text-[10px] text-dfui-tertiary">
            {outputSearch.trim()
              ? `${flatItems.length} match${flatItems.length === 1 ? "" : "es"}`
              : `${flatItems.length} shown · ${outputsLoaded} of ${outputsTotal || outputsLoaded} loaded`}
          </p>
          <div className="flex shrink-0 items-center gap-0.5">
            <button
              type="button"
              title="List view"
              onClick={() => setView("list")}
              className={`rounded-md border p-1 ${
                viewMode === "list"
                  ? "border-dfui-accent/40 text-dfui-fg"
                  : "border-dfui-border/60 text-dfui-muted"
              }`}
            >
              <List size={12} />
            </button>
            <button
              type="button"
              title="Grid view"
              onClick={() => setView("grid")}
              className={`rounded-md border p-1 ${
                viewMode === "grid"
                  ? "border-dfui-accent/40 text-dfui-fg"
                  : "border-dfui-border/60 text-dfui-muted"
              }`}
            >
              <LayoutGrid size={12} />
            </button>
            <button
              type="button"
              onClick={onRefresh}
              disabled={loadingOutputs}
              className="rounded-md border border-dfui-border/60 p-1 text-dfui-muted hover:border-dfui-accent/40 hover:text-dfui-fg disabled:opacity-50"
              title="Refresh"
            >
              <RefreshCw
                size={14}
                className={loadingOutputs ? "animate-spin" : undefined}
              />
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {loadingOutputs && dateGroups.length === 0 ? (
          <p className="px-2 py-8 text-center text-xs text-dfui-muted">
            Loading history…
          </p>
        ) : dateGroups.length === 0 ? (
          <p className="px-2 py-8 text-center text-xs leading-relaxed text-dfui-muted">
            {outputSearch.trim() || scope === "favorites"
              ? "No generations match your filters."
              : scope === "session"
                ? `No generations in ${activeLabel} yet.`
                : (
                  <>
                    No generations yet. Outputs save under{" "}
                    <span className="font-mono text-dfui-data">outputs/</span>.
                  </>
                )}
          </p>
        ) : (
          <div className="space-y-3">
            {dateGroups.map((group) => {
              const collapsed = collapsedDates[group.id] ?? false;
              return (
                <section key={group.id}>
                  <div className="mb-1 flex items-center gap-0.5 px-0.5">
                    <button
                      type="button"
                      onClick={() => toggleDateGroup(group.id)}
                      className="shrink-0 rounded p-0.5 text-dfui-tertiary hover:text-dfui-fg"
                      title={collapsed ? "Expand" : "Collapse"}
                    >
                      {collapsed ? (
                        <ChevronRight size={14} />
                      ) : (
                        <ChevronDown size={14} />
                      )}
                    </button>
                    <p className="min-w-0 flex-1 truncate text-[10px] font-semibold uppercase tracking-wide text-dfui-tertiary">
                      {group.label}
                    </p>
                    <span className="font-mono text-[9px] text-dfui-tertiary">
                      {group.items.length}
                    </span>
                  </div>
                  {!collapsed && (
                    <ul
                      className={
                        viewMode === "grid"
                          ? "grid grid-cols-2 gap-1"
                          : "space-y-1"
                      }
                    >
                      {group.items.map((item) => (
                        <HistoryItemRow
                          key={item.manifest_path}
                          item={item}
                          active={
                            selected?.manifest_path === item.manifest_path
                          }
                          viewMode={viewMode}
                          favorite={favorites.has(item.manifest_path)}
                          scrollToken={
                            selected?.manifest_path === item.manifest_path
                              ? historyScrollToken
                              : undefined
                          }
                          onSelect={onSelect}
                          onToggleFavorite={toggleFavorite}
                          onReusePrompt={onReusePrompt}
                          onEditThis={onEditThis}
                          onFixRegion={onFixRegion}
                          onEnhance={onEnhance}
                          simpleLabels={simpleHistoryLabels}
                          onOpenFolder={onOpenFolder}
                          onCopyPath={onCopyPath}
                          onDeleteGeneration={onDeleteGeneration}
                          onDeleteImage={onDeleteImage}
                        />
                      ))}
                    </ul>
                  )}
                </section>
              );
            })}
          </div>
        )}

        {onLoadMore &&
          !outputSearch.trim() &&
          scope !== "favorites" &&
          outputsLoaded < outputsTotal && (
            <button
              type="button"
              disabled={loadingOutputs}
              onClick={onLoadMore}
              className="mt-3 w-full rounded-lg border border-dfui-border/60 py-2 text-[10px] text-dfui-secondary hover:border-dfui-accent/40 hover:text-dfui-fg disabled:opacity-50"
            >
              {loadingOutputs ? "Loading…" : "Load more"}
            </button>
          )}
      </div>
    </aside>
  );
}
