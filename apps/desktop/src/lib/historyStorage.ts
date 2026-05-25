const COLLAPSED_KEY = "dreamforge_history_collapsed";
const VIEW_KEY = "dreamforge_history_view";
const FAVORITES_KEY = "dreamforge_favorite_manifests";
const ACTIVE_SESSION_KEY = "dreamforge_active_session";
const SESSION_REGISTRY_KEY = "dreamforge_session_registry";

export type StoredSessionMeta = { id: string; label: string };

export type HistoryViewMode = "list" | "grid";

export function loadCollapsedSessions(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(COLLAPSED_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, boolean>;
    return typeof parsed === "object" && parsed ? parsed : {};
  } catch {
    return {};
  }
}

export function saveCollapsedSessions(value: Record<string, boolean>) {
  try {
    localStorage.setItem(COLLAPSED_KEY, JSON.stringify(value));
  } catch {
    /* ignore quota */
  }
}

export function loadHistoryViewMode(): HistoryViewMode {
  try {
    const v = localStorage.getItem(VIEW_KEY);
    return v === "grid" ? "grid" : "list";
  } catch {
    return "list";
  }
}

export function saveHistoryViewMode(mode: HistoryViewMode) {
  try {
    localStorage.setItem(VIEW_KEY, mode);
  } catch {
    /* ignore */
  }
}

export function loadFavoriteManifests(): Set<string> {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as string[];
    return new Set(Array.isArray(parsed) ? parsed : []);
  } catch {
    return new Set();
  }
}

export function saveFavoriteManifests(favs: Set<string>) {
  try {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify([...favs]));
  } catch {
    /* ignore */
  }
}

export function loadActiveSessionId(): string {
  try {
    const v = localStorage.getItem(ACTIVE_SESSION_KEY)?.trim();
    return v || "dreamforge";
  } catch {
    return "dreamforge";
  }
}

export function saveActiveSessionId(sessionId: string) {
  try {
    localStorage.setItem(ACTIVE_SESSION_KEY, sessionId);
  } catch {
    /* ignore */
  }
}

export function loadSessionRegistry(): StoredSessionMeta[] {
  try {
    const raw = localStorage.getItem(SESSION_REGISTRY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as StoredSessionMeta[];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (s) => typeof s?.id === "string" && s.id.trim().length > 0,
    );
  } catch {
    return [];
  }
}

export function saveSessionRegistry(entries: StoredSessionMeta[]) {
  try {
    localStorage.setItem(SESSION_REGISTRY_KEY, JSON.stringify(entries));
  } catch {
    /* ignore */
  }
}
