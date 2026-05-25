import {
  ChevronDown,
  ChevronRight,
  FolderOpen,
  Images,
  LayoutGrid,
  List,
  Plus,
  RefreshCw,
  Search,
  Star,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  loadCollapsedSessions,
  loadFavoriteManifests,
  loadHistoryViewMode,
  saveCollapsedSessions,
  saveFavoriteManifests,
  saveHistoryViewMode,
  type HistoryViewMode,
} from "../lib/historyStorage";
import type { OutputSession } from "../lib/sessions";
import type { OutputItem } from "../lib/tauri-api";
import { HistoryItemRow } from "./HistoryItemRow";
import { ImageLibraryPanel } from "./ImageLibraryPanel";

type Props = {
  sessions: OutputSession[];
  activeSessionId: string;
  onSwitchSession: (sessionId: string) => void;
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
  onOpenFolder: (path: string) => void;
  onCopyPath: (path: string) => void;
  onDeleteGeneration: (item: OutputItem) => void;
  onDeleteImage: (item: OutputItem, imagePath: string) => void;
  onDeleteSession: (session: OutputSession) => void;
  historyScrollToken?: number;
  onLibrarySelect?: (path: string) => void;
};

type SideTab = "sessions" | "library";

export function HistoryPanel({
  sessions,
  activeSessionId,
  onSwitchSession,
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
  onOpenFolder,
  onCopyPath,
  onDeleteGeneration,
  onDeleteImage,
  onDeleteSession,
  historyScrollToken = 0,
  onLibrarySelect,
}: Props) {
  const [tab, setTab] = useState<SideTab>("sessions");
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>(() =>
    loadCollapsedSessions(),
  );
  const [viewMode, setViewMode] = useState<HistoryViewMode>(() =>
    loadHistoryViewMode(),
  );
  const [favorites, setFavorites] = useState<Set<string>>(() =>
    loadFavoriteManifests(),
  );
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [newSessionOpen, setNewSessionOpen] = useState(false);
  const [newSessionName, setNewSessionName] = useState("");

  const activeLabel = useMemo(() => {
    const s = sessions.find((x) => x.id === activeSessionId);
    return s?.label ?? activeSessionId;
  }, [sessions, activeSessionId]);

  const totalInView = useMemo(
    () => sessions.reduce((n, s) => n + s.items.length, 0),
    [sessions],
  );

  const displaySessions = useMemo(() => {
    if (!favoritesOnly) return sessions;
    return sessions
      .map((s) => ({
        ...s,
        items: s.items.filter((i) => favorites.has(i.manifest_path)),
      }))
      .filter((s) => s.items.length > 0);
  }, [sessions, favorites, favoritesOnly]);

  const toggle = (id: string) => {
    setCollapsed((c) => {
      const next = { ...c, [id]: !c[id] };
      saveCollapsedSessions(next);
      return next;
    });
  };

  const setView = (mode: HistoryViewMode) => {
    setViewMode(mode);
    saveHistoryViewMode(mode);
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

  useEffect(() => {
    const t = window.setTimeout(() => onRefresh(), 280);
    return () => window.clearTimeout(t);
  }, [outputSearch, onRefresh]);

  return (
    <aside className="flex h-full min-w-0 flex-col glass-panel rounded-none border-y-0 border-l-0">
      <div className="flex gap-1 border-b border-dfui-border/60 p-2">
        <button
          type="button"
          onClick={() => setTab("sessions")}
          className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg py-1.5 text-[10px] font-medium ${
            tab === "sessions" ? "df-tab-active" : "df-tab"
          }`}
        >
          <FolderOpen size={12} />
          Sessions
        </button>
        <button
          type="button"
          onClick={() => setTab("library")}
          className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg py-1.5 text-[10px] font-medium ${
            tab === "library" ? "df-tab-active" : "df-tab"
          }`}
        >
          <Images size={12} />
          Library
        </button>
      </div>

      {tab === "library" ? (
        <ImageLibraryPanel onSelectPath={onLibrarySelect} />
      ) : (
        <>
          <div className="space-y-2 border-b border-dfui-border/60 px-2 py-2">
            <div className="flex items-center gap-1">
              <label className="sr-only" htmlFor="active-session-select">
                Active session
              </label>
              <select
                id="active-session-select"
                value={activeSessionId}
                onChange={(e) => onSwitchSession(e.target.value)}
                className="min-w-0 flex-1 rounded-lg border border-dfui-accent/30 bg-dfui-bg/50 py-1.5 pl-2 pr-6 font-mono text-[10px] text-dfui-fg focus:border-dfui-accent/50 focus:outline-none"
                title="New generations save under this session folder"
              >
                {sessions.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                    {s.id === activeSessionId ? " · active" : ""}
                    {s.items.length > 0 ? ` (${s.items.length})` : ""}
                  </option>
                ))}
              </select>
              <button
                type="button"
                title="New session"
                onClick={() => {
                  setNewSessionOpen((v) => !v);
                  setNewSessionName("");
                }}
                className="shrink-0 rounded-lg border border-dfui-border/60 p-1.5 text-dfui-muted hover:border-dfui-accent/40 hover:text-dfui-fg"
              >
                <Plus size={14} />
              </button>
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
                  placeholder="Session name…"
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
              Saving to{" "}
              <span className="font-mono text-dfui-data">
                outputs/{activeSessionId === "root" ? "" : `${activeSessionId}/`}
              </span>
              · {activeLabel}
            </p>
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
                  ? `${totalInView} match${totalInView === 1 ? "" : "es"}`
                  : `${displaySessions.length} projects · showing ${outputsLoaded} of ${outputsTotal || outputsLoaded}`}
              </p>
              <div className="flex shrink-0 items-center gap-0.5">
                <button
                  type="button"
                  title="Favorites only"
                  onClick={() => setFavoritesOnly((v) => !v)}
                  className={`rounded-md border p-1 ${
                    favoritesOnly
                      ? "border-amber-500/40 text-amber-400"
                      : "border-dfui-border/60 text-dfui-muted hover:text-dfui-fg"
                  }`}
                >
                  <Star size={12} fill={favoritesOnly ? "currentColor" : "none"} />
                </button>
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
            {loadingOutputs && displaySessions.length === 0 ? (
              <p className="px-2 py-8 text-center text-xs text-dfui-muted">
                Loading history…
              </p>
            ) : displaySessions.length === 0 ? (
              <p className="px-2 py-8 text-center text-xs leading-relaxed text-dfui-muted">
                {outputSearch.trim() || favoritesOnly
                  ? "No generations match your filters."
                  : (
                    <>
                      No generations yet. Outputs are grouped under{" "}
                      <span className="font-mono text-dfui-data">outputs/</span>.
                    </>
                  )}
              </p>
            ) : (
              <ul className="space-y-2">
                {displaySessions.map((session) => {
                  const isCollapsed = collapsed[session.id] ?? false;
                  const isActive = session.id === activeSessionId;
                  return (
                    <li key={session.id}>
                      <div
                        className={`flex items-center gap-0.5 rounded-md px-1 py-1 ${
                          isActive
                            ? "bg-dfui-accent/10 ring-1 ring-dfui-accent/30"
                            : "hover:bg-dfui-accent/5"
                        }`}
                      >
                        <button
                          type="button"
                          onClick={() => toggle(session.id)}
                          className="shrink-0 rounded p-0.5 text-dfui-tertiary hover:text-dfui-fg"
                          title={isCollapsed ? "Expand" : "Collapse"}
                        >
                          {isCollapsed ? (
                            <ChevronRight size={14} />
                          ) : (
                            <ChevronDown size={14} />
                          )}
                        </button>
                        <button
                          type="button"
                          onClick={() => onSwitchSession(session.id)}
                          className={`flex min-w-0 flex-1 items-center gap-1.5 text-left text-xs ${
                            isActive ? "text-dfui-fg" : "text-dfui-secondary"
                          }`}
                          title={
                            isActive
                              ? "Active session — new images save here"
                              : `Switch to ${session.label}`
                          }
                        >
                          <span className="truncate font-medium">{session.label}</span>
                          {isActive && (
                            <span className="shrink-0 rounded bg-dfui-accent/20 px-1 font-mono text-[9px] text-dfui-accent">
                              active
                            </span>
                          )}
                          <span className="ml-auto font-mono text-[10px] text-dfui-tertiary">
                            {session.items.length}
                          </span>
                        </button>
                        <button
                          type="button"
                          title={`Delete session ${session.label}`}
                          onClick={() => onDeleteSession(session)}
                          className="shrink-0 rounded p-1 text-dfui-tertiary hover:bg-red-500/10 hover:text-red-300"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                      {!isCollapsed && (
                        <ul
                          className={`mt-1 pl-1 ${
                            viewMode === "grid"
                              ? "grid grid-cols-2 gap-1"
                              : "space-y-1"
                          }`}
                        >
                          {session.items.map((item) => (
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
                              onOpenFolder={onOpenFolder}
                              onCopyPath={onCopyPath}
                              onDeleteGeneration={onDeleteGeneration}
                              onDeleteImage={onDeleteImage}
                            />
                          ))}
                        </ul>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
            {onLoadMore &&
              !outputSearch.trim() &&
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
        </>
      )}
    </aside>
  );
}
