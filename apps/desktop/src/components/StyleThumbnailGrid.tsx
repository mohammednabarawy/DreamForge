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
      const id = (typeof s.id === "string" ? s.id : "").toLowerCase();
      const orig = (typeof s.original_name === "string" ? s.original_name : "").toLowerCase();
      return id.includes(q) || orig.includes(q);
    });
  }, [styles, q]);

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
        badge: s.models && s.models.length > 0 ? "Preset" : undefined,
      };
    });
  }, [filteredStyles, activeStyle]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <p className="shrink-0 text-xs text-dfui-muted">
        Pick a style to apply its recipe and SDXL fragments. Click the active tile again to clear.
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
