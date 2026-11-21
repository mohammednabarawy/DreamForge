import {
  AlertCircle,
  ArrowDownWideNarrow,
  ArrowUpNarrowWide,
  ChevronDown,
  ChevronRight,
  LayoutGrid,
  List,
  Plus,
  RefreshCw,
  Search,
  Star,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  hasFavoriteManifest,
  loadCollapsedDateGroups,
  loadFavoriteManifests,
  loadHistoryScope,
  loadHistoryViewMode,
  normalizeManifestKey,
  saveCollapsedDateGroups,
  saveFavoriteManifests,
  saveHistoryScope,
  saveHistoryViewMode,
  toggleFavoriteInSet,
  type HistoryScope,
  type HistorySortOrder,
  type HistoryViewMode,
} from "../lib/historyStorage";
import { groupHistoryByDate, parseHistoryTimestamp } from "../lib/historyUtils";
import type { OutputSession } from "../lib/sessions";
import type { OutputItem, OutputModelSummary } from "../lib/tauri-api";
import { HistoryItemRow } from "./HistoryItemRow";

type Props = {
  sessions: OutputSession[];
  sessionCounts?: Record<string, number>;
  availableModels?: OutputModelSummary[];
  modelFilter?: string;
  onModelFilterChange?: (model: string) => void;
  sortOrder?: HistorySortOrder;
  onSortOrderChange?: (order: HistorySortOrder) => void;
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
  outputsError?: string | null;
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
  sessionCounts = {},
  availableModels = [],
  modelFilter = "",
  onModelFilterChange,
  sortOrder = "newest",
  onSortOrderChange,
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
  outputsError = null,
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
  const didMountSearchRef = useRef(false);
  const loadMoreSentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const syncFavorites = () => setFavorites(loadFavoriteManifests());
    window.addEventListener("dreamforge-favorites-changed", syncFavorites);
    return () =>
      window.removeEventListener("dreamforge-favorites-changed", syncFavorites);
  }, []);

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
    const dir = sortOrder === "oldest" ? 1 : -1;
    items.sort((a, b) => (parseHistoryTimestamp(a) - parseHistoryTimestamp(b)) * dir);
    const filteredByScope =
      scope === "favorites"
        ? items.filter((item) => hasFavoriteManifest(favorites, item.manifest_path))
        : items;
    if (!modelFilter) return filteredByScope;
    const targetModel = modelFilter.toLowerCase();
    return filteredByScope.filter(
      (item) =>
        item.model_name.toLowerCase() === targetModel ||
        item.model_stem.toLowerCase() === targetModel,
    );
  }, [sessions, scope, activeSessionId, favorites, sortOrder, modelFilter]);

  const dateGroups = useMemo(
    () => groupHistoryByDate(flatItems, sortOrder),
    [flatItems, sortOrder],
  );

  const visibleItems = useMemo(() => {
    const list: OutputItem[] = [];
    for (const group of dateGroups) {
      if (collapsedDates[group.id]) continue;
      list.push(...group.items);
    }
    return list;
  }, [dateGroups, collapsedDates]);

  const setView = (mode: HistoryViewMode) => {
    setViewMode(mode);
    saveHistoryViewMode(mode);
  };

  const setScopeFilter = (next: HistoryScope) => {
    setScope(next);
    saveHistoryScope(next);
    onRefreshRef.current();
  };

  const toggleFavorite = (manifestPath: string) => {
    const next = toggleFavoriteInSet(favorites, manifestPath);
    setFavorites(next);
    saveFavoriteManifests(next);
  };

  const toggleDateGroup = (id: string) => {
    setCollapsedDates((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      saveCollapsedDateGroups(next);
      return next;
    });
  };

  // Debounced search refresh — skip initial mount to avoid racing with boot refreshOutputs().
  useEffect(() => {
    if (!didMountSearchRef.current) {
      didMountSearchRef.current = true;
      return;
    }
    const t = window.setTimeout(() => onRefreshRef.current(), 250);
    return () => window.clearTimeout(t);
  }, [outputSearch]);

  // Infinite-scroll auto-load when user nears bottom of history list.
  useEffect(() => {
    const sentinel = loadMoreSentinelRef.current;
    if (!sentinel || !onLoadMore || loadingOutputs || outputsLoaded >= outputsTotal) {
      return;
    }
    if (typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          onLoadMore();
        }
      },
      { rootMargin: "160px" },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [onLoadMore, loadingOutputs, outputsLoaded, outputsTotal]);

  const selectedKey = normalizeManifestKey(selected?.manifest_path);
  const hasActiveFilters = Boolean(
    outputSearch.trim() || scope !== "all" || modelFilter,
  );
  const remainingCount = Math.max(0, outputsTotal - outputsLoaded);

  const handleListKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (visibleItems.length === 0) return;
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const target = event.target as HTMLElement | null;
    if (target && (target.tagName === "INPUT" || target.tagName === "SELECT" || target.tagName === "TEXTAREA")) {
      return;
    }
    event.preventDefault();
    const currentIndex = visibleItems.findIndex(
      (item) => normalizeManifestKey(item.manifest_path) === selectedKey,
    );
    const delta = event.key === "ArrowDown" ? 1 : -1;
    const nextIndex =
      currentIndex < 0
        ? delta > 0
          ? 0
          : visibleItems.length - 1
        : Math.max(0, Math.min(visibleItems.length - 1, currentIndex + delta));
    const nextItem = visibleItems[nextIndex];
    if (nextItem) {
      onSelect(nextItem);
    }
  };

  const clearAllFilters = () => {
    if (outputSearch) onOutputSearchChange("");
    if (modelFilter && onModelFilterChange) onModelFilterChange("");
    if (scope !== "all") setScopeFilter("all");
  };

  return (
    <aside className="flex h-full min-h-0 min-w-0 flex-col glass-panel rounded-none border-y-0 border-l-0">
      <div className="flex items-center justify-between border-b border-dfui-border/60 px-2 py-2">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-dfui-tertiary">
          History
        </p>
        {outputsTotal > 0 && (
          <span className="rounded bg-dfui-bg/60 px-1.5 py-0.5 font-mono text-[9px] text-dfui-tertiary">
            {outputsTotal}
          </span>
        )}
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
            {sessions.map((s) => {
              const count = sessionCounts[s.id] ?? s.items.length;
              return (
                <option key={s.id} value={s.id}>
                  {s.label}
                  {count > 0 ? ` (${count})` : ""}
                </option>
              );
            })}
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
                  {favorites.size > 0 && (
                    <span className="font-mono text-[9px] opacity-75">
                      {favorites.size}
                    </span>
                  )}
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
            type="text"
            value={outputSearch}
            onChange={(e) => onOutputSearchChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape" && outputSearch) {
                e.preventDefault();
                onOutputSearchChange("");
              }
            }}
            placeholder="Search prompts, models, styles…"
            className="w-full rounded-lg border border-dfui-border/60 bg-dfui-bg/40 py-1.5 pl-7 pr-6 font-mono text-[10px] text-dfui-fg placeholder:text-dfui-tertiary focus:border-dfui-accent/40 focus:outline-none"
          />
          {outputSearch && (
            <button
              type="button"
              aria-label="Clear search"
              title="Clear search"
              onClick={() => onOutputSearchChange("")}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-dfui-tertiary hover:text-dfui-fg"
            >
              <X size={11} />
            </button>
          )}
        </div>

        {onModelFilterChange && (availableModels.length > 1 || modelFilter) && (
          <select
            aria-label="Filter history by model"
            value={modelFilter}
            onChange={(e) => onModelFilterChange(e.target.value)}
            className="w-full rounded-lg border border-dfui-border/60 bg-dfui-bg/40 py-1 pl-2 pr-6 font-mono text-[10px] text-dfui-fg focus:border-dfui-accent/40 focus:outline-none"
            title="Filter history by model"
          >
            <option value="">All models</option>
            {availableModels.map((m) => (
              <option key={m.name} value={m.name}>
                {m.stem} ({m.count})
              </option>
            ))}
          </select>
        )}

        <div className="flex items-center justify-between gap-1">
          <p className="min-w-0 truncate text-[10px] text-dfui-tertiary">
            {outputSearch.trim() || modelFilter
              ? `${flatItems.length} match${flatItems.length === 1 ? "" : "es"}`
              : `${flatItems.length} shown · ${outputsLoaded} of ${outputsTotal || outputsLoaded} loaded`}
          </p>
          <div className="flex shrink-0 items-center gap-0.5">
            {onSortOrderChange && (
              <button
                type="button"
                title={
                  sortOrder === "newest"
                    ? "Sorted newest first — click for oldest first"
                    : "Sorted oldest first — click for newest first"
                }
                aria-label="Toggle sort order"
                onClick={() =>
                  onSortOrderChange(sortOrder === "newest" ? "oldest" : "newest")
                }
                className="rounded-md border border-dfui-border/60 p-1 text-dfui-muted hover:border-dfui-accent/40 hover:text-dfui-fg"
              >
                {sortOrder === "newest" ? (
                  <ArrowDownWideNarrow size={12} />
                ) : (
                  <ArrowUpNarrowWide size={12} />
                )}
              </button>
            )}
            <button
              type="button"
              title="List view"
              aria-label="List view"
              aria-pressed={viewMode === "list"}
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
              aria-label="Grid view"
              aria-pressed={viewMode === "grid"}
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
              title="Refresh library"
              aria-label="Refresh library"
            >
              <RefreshCw
                size={12}
                className={loadingOutputs ? "animate-spin" : undefined}
              />
            </button>
          </div>
        </div>
      </div>

      {outputsError && (
        <div className="mx-2 mt-2 flex items-start gap-1.5 rounded-lg border border-red-400/35 bg-red-500/10 px-2 py-1.5 text-[10px] text-red-200">
          <AlertCircle size={13} className="mt-0.5 shrink-0 text-red-300" />
          <div className="min-w-0 flex-1">
            <p className="font-medium">Couldn&apos;t refresh history</p>
            <p className="truncate text-[9px] text-red-200/80" title={outputsError}>
              {outputsError}
            </p>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            className="shrink-0 rounded border border-red-300/40 px-1.5 py-0.5 text-[9px] font-medium hover:bg-red-500/20"
          >
            Retry
          </button>
        </div>
      )}

      <div
        className="flex-1 overflow-y-auto p-2 focus:outline-none"
        tabIndex={0}
        onKeyDown={handleListKeyDown}
        aria-label="Generation history"
      >
        {loadingOutputs && dateGroups.length === 0 ? (
          <div className={viewMode === "grid" ? "grid grid-cols-2 gap-1.5" : "space-y-1.5"}>
            {Array.from({ length: 6 }).map((_, idx) => (
              <div
                key={idx}
                className="animate-pulse rounded-lg border border-dfui-border/30 bg-dfui-bg/40 p-1.5"
              >
                <div
                  className={
                    viewMode === "grid"
                      ? "aspect-square w-full rounded bg-dfui-panel/70"
                      : "flex gap-2"
                  }
                >
                  {viewMode === "list" && (
                    <>
                      <div className="h-11 w-11 shrink-0 rounded bg-dfui-panel/70" />
                      <div className="flex-1 space-y-1.5 py-1">
                        <div className="h-2.5 w-3/4 rounded bg-dfui-panel/70" />
                        <div className="h-2 w-1/2 rounded bg-dfui-panel/50" />
                      </div>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : dateGroups.length === 0 ? (
          <div className="space-y-2 px-2 py-8 text-center text-xs leading-relaxed text-dfui-muted">
            <p>
              {hasActiveFilters
                ? scope === "session" && !outputSearch.trim() && !modelFilter
                  ? `No generations in ${activeLabel} yet.`
                  : "No generations match your filters."
                : (
                  <>
                    No generations yet. Outputs save under{" "}
                    <span className="font-mono text-dfui-data">outputs/</span>.
                  </>
                )}
            </p>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearAllFilters}
                className="rounded-md border border-dfui-border/70 px-2.5 py-1 text-[10px] text-dfui-secondary hover:border-dfui-accent/40 hover:text-dfui-fg"
              >
                Clear filters
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {dateGroups.map((group) => {
              const collapsed = collapsedDates[group.id] ?? false;
              return (
                <section key={group.id}>
                  <button
                    type="button"
                    onClick={() => toggleDateGroup(group.id)}
                    className="mb-1 flex w-full items-center gap-0.5 rounded px-0.5 py-0.5 text-left hover:bg-dfui-bg/40"
                    title={collapsed ? "Expand group" : "Collapse group"}
                  >
                    <span className="shrink-0 text-dfui-tertiary">
                      {collapsed ? (
                        <ChevronRight size={14} />
                      ) : (
                        <ChevronDown size={14} />
                      )}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-[10px] font-semibold uppercase tracking-wide text-dfui-tertiary">
                      {group.label}
                    </span>
                    <span className="font-mono text-[9px] text-dfui-tertiary">
                      {group.items.length}
                    </span>
                  </button>
                  {!collapsed && (
                    <ul
                      className={
                        viewMode === "grid"
                          ? "grid grid-cols-2 gap-1"
                          : "space-y-1"
                      }
                    >
                      {group.items.map((item) => {
                        const isItemActive =
                          normalizeManifestKey(item.manifest_path) === selectedKey &&
                          selectedKey !== "";
                        return (
                          <HistoryItemRow
                            key={item.manifest_path}
                            item={item}
                            active={isItemActive}
                            viewMode={viewMode}
                            favorite={hasFavoriteManifest(favorites, item.manifest_path)}
                            scrollToken={isItemActive ? historyScrollToken : undefined}
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
                        );
                      })}
                    </ul>
                  )}
                </section>
              );
            })}
          </div>
        )}

        {onLoadMore && outputsLoaded < outputsTotal && (
          <div ref={loadMoreSentinelRef} className="mt-3">
            <button
              type="button"
              disabled={loadingOutputs}
              onClick={onLoadMore}
              className="w-full rounded-lg border border-dfui-border/60 py-2 text-[10px] text-dfui-secondary hover:border-dfui-accent/40 hover:text-dfui-fg disabled:opacity-50"
            >
              {loadingOutputs
                ? "Loading…"
                : `Load more (${remainingCount} remaining)`}
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
