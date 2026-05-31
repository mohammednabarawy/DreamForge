import { useMemo } from "react";
import type { StyleRecipe } from "../lib/model-selection";
import { ThumbnailGallery, type GalleryTile } from "./ThumbnailGallery";

type Props = {
  styles: StyleRecipe[];
  filter: string;
  onFilterChange: (value: string) => void;
  onSelect: (styleId: string) => void;
  activeStyle?: string;
};

export function StyleThumbnailGrid({
  styles,
  filter,
  onFilterChange,
  onSelect,
  activeStyle,
}: Props) {
  const q = filter.trim().toLowerCase();

  const filteredStyles = useMemo(() => {
    return styles.filter((s) => {
      if (!q) return true;
      const id = s.id.toLowerCase();
      const orig = (s.original_name ?? "").toLowerCase();
      return id.includes(q) || orig.includes(q);
    });
  }, [styles, q]);

  const tiles: GalleryTile[] = useMemo(() => {
    return filteredStyles.map((s) => {
      const rawLabel = s.original_name
        ? s.original_name.replace(/^Style:\s*/i, "")
        : s.id;
      const label = rawLabel
        .split(/[_-]/)
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");

      return {
        key: s.id,
        value: s.id,
        label,
        thumbnailPath: s.thumbnail,
        selected: activeStyle === s.id,
        badge: s.models && s.models.length > 0 ? "Preset" : undefined,
      };
    });
  }, [filteredStyles, activeStyle]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <p className="shrink-0 text-xs text-dfui-muted">
        Pick one style — prompts, models, and SDXL fragments come from the recipe.
      </p>
      <input
        value={filter}
        onChange={(e) => onFilterChange(e.target.value)}
        placeholder="Search styles…"
        className="df-input shrink-0 w-full px-2.5 py-1.5 text-xs"
      />
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
