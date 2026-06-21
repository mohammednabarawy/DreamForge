import { useCallback, useState } from "react";
import { thumbnailAssetUrl } from "../lib/thumbnail-cache";

export type GalleryTile = {
  key: string;
  value?: string;
  label: string;
  sublabel?: string;
  thumbnailPath?: string;
  selected?: boolean;
  badge?: string;
};

type Props = {
  items: GalleryTile[];
  emptyMessage?: string;
  onSelect: (key: string) => void;
  multiSelect?: boolean;
};

function TileThumb({ path, label }: { path?: string; label: string }) {
  const [broken, setBroken] = useState(false);

  const onError = useCallback(() => setBroken(true), []);

  const src = broken ? null : thumbnailAssetUrl(path);

  if (src) {
    return (
      <img
        src={src}
        alt=""
        className="h-full w-full object-cover opacity-90 transition-opacity group-hover:opacity-75"
        loading="lazy"
        decoding="async"
        onError={onError}
      />
    );
  }

  const initial = label.trim().charAt(0).toUpperCase() || "?";
  return (
    <div className="flex h-full w-full items-center justify-center bg-dfui-panel font-mono text-lg text-dfui-muted">
      {initial}
    </div>
  );
}

export function ThumbnailGallery({
  items,
  emptyMessage = "Nothing to show.",
  onSelect,
  multiSelect = false,
}: Props) {
  if (items.length === 0) {
    return (
      <p className="py-10 text-center text-xs text-dfui-muted">{emptyMessage}</p>
    );
  }

  return (
    <div className="df-gallery-grid">
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          title={item.label}
          onClick={() => onSelect(item.value ?? item.key)}
          className={`group df-gallery-tile ${
            item.selected ? "df-gallery-tile-active" : "df-gallery-tile-idle"
          }`}
        >
          <div className="absolute inset-0">
            <TileThumb path={item.thumbnailPath} label={item.label} />
          </div>
          <div className="df-gallery-tile-caption">
            <p className="line-clamp-2 text-[11px] font-semibold leading-tight text-white">
              {item.label}
            </p>
            {item.sublabel && (
              <p className="mt-0.5 truncate text-[9px] text-gray-300">
                {item.sublabel}
              </p>
            )}
          </div>
          {item.badge && (
            <span className="absolute left-1.5 top-1.5 rounded bg-black/55 px-1.5 py-0.5 font-mono text-[8px] text-white backdrop-blur">
              {item.badge}
            </span>
          )}
          {multiSelect && item.selected && (
            <span className="absolute right-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-dfui-accent text-[10px] font-bold text-dfui-bg shadow-sm">
              ✓
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
