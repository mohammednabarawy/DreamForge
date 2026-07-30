import { useEffect, useMemo, useState } from "react";
import { Star } from "lucide-react";
import type { StyleRecipe } from "../lib/model-selection";
import type { StyleGroup } from "../lib/inventory";
import { ThumbnailGallery, type GalleryTile } from "./ThumbnailGallery";

const FAVORITES_KEY = "dreamforge.styleFavorites.v1";
const RECENT_KEY = "dreamforge.styleRecent.v1";

function readStoredIds(key: string): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(key) ?? "[]");
    return Array.isArray(value) ? value.filter((id): id is string => typeof id === "string") : [];
  } catch {
    return [];
  }
}

function writeStoredIds(key: string, ids: string[]) {
  try {
    localStorage.setItem(key, JSON.stringify(ids));
  } catch {
    /* private mode or storage quota */
  }
}

type Props = {
  styles: StyleRecipe[];
  groups: StyleGroup[];
  filter: string;
  onFilterChange: (value: string) => void;
  onSelect: (styleId: string) => void;
  activeStyle?: string;
};

export function StyleThumbnailGrid({
  styles,
  groups,
  filter,
  onFilterChange,
  onSelect,
  activeStyle,
}: Props) {
  const [group, setGroup] = useState("all");
  const [favorites, setFavorites] = useState<string[]>(() => readStoredIds(FAVORITES_KEY));
  const [recent, setRecent] = useState<string[]>(() => readStoredIds(RECENT_KEY));
  const q = filter.trim().toLowerCase();

  useEffect(() => {
    if (!activeStyle || activeStyle === "none") return;
    setRecent((current) => {
      const next = [activeStyle, ...current.filter((id) => id !== activeStyle)].slice(0, 20);
      writeStoredIds(RECENT_KEY, next);
      return next;
    });
  }, [activeStyle]);

  const groupIds = useMemo(
    () => new Set(groups.find((item) => item.id === group)?.items.map((item) => item.id) ?? []),
    [group, groups],
  );

  const filteredStyles = useMemo(() => {
    const filtered = styles.filter((s) => {
      const idValue = typeof s.id === "string" ? s.id : "";
      if (group === "favorites" && !favorites.includes(idValue)) return false;
      if (group === "recent" && !recent.includes(idValue)) return false;
      if (!['all', 'favorites', 'recent'].includes(group) && !groupIds.has(idValue)) return false;
      if (!q) return true;
      const id = idValue.toLowerCase();
      const orig = (typeof s.original_name === "string" ? s.original_name : "").toLowerCase();
      return id.includes(q) || orig.includes(q);
    });
    if (group === "recent") {
      filtered.sort((a, b) => recent.indexOf(String(a.id)) - recent.indexOf(String(b.id)));
    }
    return filtered;
  }, [favorites, group, groupIds, q, recent, styles]);

  const tiles: GalleryTile[] = useMemo(() => {
    return filteredStyles.map((s) => {
      const originalName = typeof s.original_name === "string" ? s.original_name : "";
      const rawLabel = originalName
        ? originalName.replace(/^Style:\s*/i, "")
        : typeof s.id === "string"
          ? s.id
          : "Style";
      const label = rawLabel
        .split(/[_-]/)
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");

      return {
        key: typeof s.id === "string" ? s.id : `style-${label}`,
        value: typeof s.id === "string" ? s.id : "",
        label,
        thumbnailPath: s.thumbnail,
        selected: activeStyle === s.id,
        badge: favorites.includes(String(s.id)) ? "Favorite" : s.models && s.models.length > 0 ? "Preset" : undefined,
      };
    });
  }, [activeStyle, favorites, filteredStyles]);

  const activeIsFavorite = Boolean(activeStyle && favorites.includes(activeStyle));

  const toggleActiveFavorite = () => {
    if (!activeStyle || activeStyle === "none") return;
    setFavorites((current) => {
      const next = current.includes(activeStyle)
        ? current.filter((id) => id !== activeStyle)
        : [activeStyle, ...current];
      writeStoredIds(FAVORITES_KEY, next);
      return next;
    });
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <p className="shrink-0 text-xs text-dfui-muted">
        Pick a style to apply its recipe and SDXL fragments. Click the active tile again to clear.
      </p>
      <div className="flex shrink-0 gap-2">
        <input
          value={filter}
          onChange={(e) => onFilterChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") onFilterChange("");
          }}
          placeholder="Search styles…"
          className="df-input min-w-0 flex-1 px-2.5 py-1.5 text-xs"
        />
        <select
          value={group}
          onChange={(e) => setGroup(e.target.value)}
          className="df-select max-w-36 px-2 py-1.5 text-xs"
          aria-label="Filter style group"
        >
          <option value="all">All groups</option>
          <option value="favorites">Favorites</option>
          <option value="recent">Recent</option>
          {groups.map((item) => (
            <option key={item.id} value={item.id}>{item.label}</option>
          ))}
        </select>
      </div>
      <div className="flex shrink-0 items-center justify-between gap-2 text-[10px] text-dfui-muted">
        <span>{filteredStyles.length} of {styles.length} styles</span>
        {activeStyle && activeStyle !== "none" && (
          <button
            type="button"
            onClick={toggleActiveFavorite}
            className={`inline-flex items-center gap-1 rounded px-1.5 py-1 ${activeIsFavorite ? "text-amber-300" : "text-dfui-muted hover:text-dfui-fg"}`}
            aria-pressed={activeIsFavorite}
          >
            <Star size={11} fill={activeIsFavorite ? "currentColor" : "none"} />
            {activeIsFavorite ? "Favorited" : "Favorite active"}
          </button>
        )}
      </div>
      <div className="df-gallery-pane">
        <ThumbnailGallery
          items={tiles}
          emptyMessage="No styles match your search."
          onSelect={onSelect}
          multiSelect={false}
        />
      </div>
    </div>
  );
}
