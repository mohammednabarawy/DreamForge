import {
  Copy,
  ExternalLink,
  Images,
  MoreHorizontal,
  RotateCcw,
  Star,
  Trash2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  excerptPrompt,
  formatRelativeTime,
  modelBadgeLabel,
} from "../lib/historyUtils";
import type { OutputItem } from "../lib/tauri-api";
import { setImagePathDragData } from "../lib/referenceImage";
import { Thumb } from "./Thumb";

type Props = {
  item: OutputItem;
  active: boolean;
  viewMode: "list" | "grid";
  favorite: boolean;
  scrollToken?: number;
  onSelect: (item: OutputItem) => void;
  onToggleFavorite: (manifestPath: string) => void;
  onReusePrompt: (item: OutputItem) => void;
  onOpenFolder: (path: string) => void;
  onCopyPath: (path: string) => void;
  onDeleteGeneration: (item: OutputItem) => void;
  onDeleteImage?: (item: OutputItem, imagePath: string) => void;
};

export function HistoryItemRow({
  item,
  active,
  viewMode,
  favorite,
  scrollToken,
  onSelect,
  onToggleFavorite,
  onReusePrompt,
  onOpenFolder,
  onCopyPath,
  onDeleteGeneration,
  onDeleteImage,
}: Props) {
  const rowRef = useRef<HTMLLIElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const thumb = item.images[0];
  const imageCount = item.images.length;
  const timeIso = item.created_at ?? item.timestamp;
  const badge = modelBadgeLabel(item.model_stem, item.model_family);
  const promptExcerpt = excerptPrompt(item.prompt);

  useEffect(() => {
    if (scrollToken && active && rowRef.current) {
      rowRef.current.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [scrollToken, active]);

  const openPath = thumb ?? item.manifest_path;

  return (
    <li
      ref={rowRef}
      className={viewMode === "grid" ? "min-w-0" : undefined}
      data-manifest={item.manifest_path}
    >
      <div
        className={`group relative rounded-lg border transition ${
          active
            ? "border-dfui-accent/50 bg-dfui-accent/10"
            : "border-transparent hover:border-dfui-border/40 hover:bg-dfui-bg/40"
        } ${viewMode === "grid" ? "p-1" : "p-1.5"}`}
      >
        <button
          type="button"
          draggable={!!thumb}
          onDragStart={(e) => {
            if (thumb) setImagePathDragData(e.dataTransfer, thumb);
          }}
          onClick={() => onSelect(item)}
          className={`flex w-full text-left ${
            viewMode === "grid" ? "flex-col gap-1" : "gap-2"
          }`}
        >
          {thumb && (
            <Thumb
              path={thumb}
              className={
                viewMode === "grid"
                  ? "aspect-square w-full rounded-md"
                  : "h-11 w-11 shrink-0 rounded-md"
              }
            />
          )}
          <div className="min-w-0 flex-1">
            <div className="flex items-start gap-1">
              <p className="min-w-0 flex-1 truncate text-[10px] font-medium text-dfui-fg">
                {item.title || "Untitled"}
              </p>
              {imageCount > 1 && (
                <span
                  className="inline-flex shrink-0 items-center gap-0.5 rounded bg-dfui-bg/80 px-1 font-mono text-[8px] text-dfui-tertiary"
                  title={`${imageCount} images`}
                >
                  <Images size={9} />
                  {imageCount}
                </span>
              )}
            </div>
            {promptExcerpt && (
              <p className="mt-0.5 line-clamp-2 text-[9px] leading-snug text-dfui-muted">
                {promptExcerpt}
              </p>
            )}
            <div className="mt-1 flex flex-wrap items-center gap-1">
              <span className="rounded bg-dfui-bg/60 px-1 font-mono text-[8px] text-dfui-data">
                {badge}
              </span>
              <span className="font-mono text-[8px] text-dfui-tertiary">
                {formatRelativeTime(timeIso)}
              </span>
            </div>
          </div>
        </button>

        <div
          className={`absolute top-1 flex gap-0.5 ${
            viewMode === "grid" ? "right-1" : "right-1.5"
          }`}
        >
          <button
            type="button"
            title={favorite ? "Remove favorite" : "Favorite"}
            onClick={(e) => {
              e.stopPropagation();
              onToggleFavorite(item.manifest_path);
            }}
            className={`rounded p-0.5 ${
              favorite
                ? "text-amber-400"
                : "text-dfui-tertiary opacity-0 group-hover:opacity-100"
            }`}
          >
            <Star size={12} fill={favorite ? "currentColor" : "none"} />
          </button>
          <button
            type="button"
            title="Actions"
            onClick={(e) => {
              e.stopPropagation();
              setMenuOpen((o) => !o);
            }}
            className="rounded p-0.5 text-dfui-tertiary opacity-0 group-hover:opacity-100 hover:text-dfui-fg"
          >
            <MoreHorizontal size={12} />
          </button>
        </div>

        {menuOpen && (
          <>
            <button
              type="button"
              className="fixed inset-0 z-10 cursor-default"
              aria-label="Close menu"
              onClick={() => setMenuOpen(false)}
            />
            <ul className="absolute right-0 top-6 z-20 min-w-[9.5rem] rounded-md border border-dfui-border/80 bg-dfui-panel py-1 text-[10px] shadow-lg">
              <li>
                <button
                  type="button"
                  className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-dfui-accent/10"
                  onClick={() => {
                    setMenuOpen(false);
                    onReusePrompt(item);
                  }}
                >
                  <RotateCcw size={11} />
                  Reuse prompt
                </button>
              </li>
              <li>
                <button
                  type="button"
                  className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-dfui-accent/10"
                  onClick={() => {
                    setMenuOpen(false);
                    onOpenFolder(openPath);
                  }}
                >
                  <ExternalLink size={11} />
                  Open folder
                </button>
              </li>
              {thumb && (
                <li>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-dfui-accent/10"
                    onClick={() => {
                      setMenuOpen(false);
                      onCopyPath(thumb);
                    }}
                  >
                    <Copy size={11} />
                    Copy image path
                  </button>
                </li>
              )}
              {thumb && onDeleteImage && (
                <li>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-2 py-1.5 text-left text-red-300 hover:bg-red-500/10"
                    onClick={() => {
                      setMenuOpen(false);
                      onDeleteImage(item, thumb);
                    }}
                  >
                    <Trash2 size={11} />
                    {imageCount > 1 ? "Delete image only" : "Delete image"}
                  </button>
                </li>
              )}
              {imageCount > 1 && (
                <li>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-2 py-1.5 text-left text-red-300 hover:bg-red-500/10"
                    onClick={() => {
                      setMenuOpen(false);
                      onDeleteGeneration(item);
                    }}
                  >
                    <Trash2 size={11} />
                    Delete all images
                  </button>
                </li>
              )}
            </ul>
          </>
        )}
      </div>
    </li>
  );
}
