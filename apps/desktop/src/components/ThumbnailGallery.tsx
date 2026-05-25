import { useEffect, useState } from "react";
import { readImagePreviewQueued } from "../lib/preview-queue";

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
  columns?: 2 | 3;
  emptyMessage?: string;
  onSelect: (key: string) => void;
  multiSelect?: boolean;
};

function TileThumb({ path, label }: { path?: string; label: string }) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!path) {
      setSrc(null);
      return;
    }
    void readImagePreviewQueued(path)
      .then((res) => {
        if (!cancelled) setSrc(res.data_url ?? null);
      })
      .catch(() => {
        if (!cancelled) setSrc(null);
      });
    return () => {
      cancelled = true;
    };
  }, [path]);

  if (src) {
    return (
      <img
        src={src}
        alt=""
        className="h-full w-full object-contain bg-dfui-bg/80"
        loading="lazy"
      />
    );
  }

  const initial = label.trim().charAt(0).toUpperCase() || "?";
  return (
    <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-dfui-bg to-dfui-surface-hover font-mono text-lg text-dfui-muted">
      {initial}
    </div>
  );
}

export function ThumbnailGallery({
  items,
  columns = 2,
  emptyMessage = "Nothing to show.",
  onSelect,
  multiSelect = false,
}: Props) {
  if (items.length === 0) {
    return (
      <p className="py-8 text-center text-xs text-dfui-muted">{emptyMessage}</p>
    );
  }

  const gridClass =
    columns === 3
      ? "grid grid-cols-3 gap-1.5"
      : "grid grid-cols-2 gap-1.5";

  return (
    <div className={gridClass}>
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          title={item.label}
          onClick={() => onSelect(item.value ?? item.key)}
          className={`group relative flex flex-col overflow-hidden rounded-lg border text-left transition ${
            item.selected
              ? "border-dfui-accent ring-1 ring-dfui-accent/60"
              : "border-dfui-border/60 hover:border-dfui-accent/40"
          }`}
        >
          <div className="aspect-square w-full overflow-hidden">
            <TileThumb path={item.thumbnailPath} label={item.label} />
          </div>
          <div className="border-t border-dfui-border/40 bg-dfui-bg/70 px-1.5 py-1">
            <p className="truncate font-mono text-[9px] leading-tight text-dfui-fg">
              {item.label}
            </p>
            {item.sublabel && (
              <p className="truncate text-[8px] text-dfui-tertiary">
                {item.sublabel}
              </p>
            )}
          </div>
          {item.badge && (
            <span className="absolute left-1 top-1 rounded bg-dfui-bg/90 px-1 py-0.5 font-mono text-[8px] text-dfui-accent">
              {item.badge}
            </span>
          )}
          {multiSelect && item.selected && (
            <span className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-dfui-accent text-[10px] font-bold text-dfui-bg">
              ✓
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
