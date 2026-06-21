import {
  Copy,
  ExternalLink,
  GripVertical,
  Images,
  MoreHorizontal,
  Pencil,
  RotateCcw,
  Sparkles,
  Star,
  Trash2,
  Wand2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  excerptPrompt,
  formatRelativeTime,
  modelBadgeLabel,
} from "../lib/historyUtils";
import type { OutputItem } from "../lib/tauri-api";
import {
  primeImagePathDragSession,
  scheduleClearImagePathDragSession,
  setImagePathDragData,
} from "../lib/referenceImage";
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
  onEditThis?: (item: OutputItem) => void;
  onFixRegion?: (item: OutputItem) => void;
  onEnhance?: (item: OutputItem) => void;
  simpleLabels?: boolean;
  onOpenFolder: (path: string) => void;
  onCopyPath: (path: string) => void;
  onDeleteGeneration: (item: OutputItem) => void;
  onDeleteImage?: (item: OutputItem, imagePath: string) => void;
};

function DraggableHistoryThumb({
  path,
  className,
  title,
  onSelect,
}: {
  path: string;
  className: string;
  title?: string;
  onSelect?: () => void;
}) {
  return (
    <div
      draggable
      onMouseDown={() => primeImagePathDragSession(path)}
      onClick={(event) => {
        event.stopPropagation();
        onSelect?.();
      }}
      onDragStart={(event) => {
        setImagePathDragData(event.dataTransfer, path);
        event.stopPropagation();
        const img = event.currentTarget.querySelector("img");
        if (img instanceof HTMLImageElement && img.complete && img.naturalWidth > 0) {
          const w = Math.min(img.naturalWidth, 96);
          const h = Math.min(img.naturalHeight, 96);
          event.dataTransfer.setDragImage(img, w / 2, h / 2);
        }
      }}
      onDragEnd={() => scheduleClearImagePathDragSession()}
      className={`group/thumb relative shrink-0 cursor-grab overflow-hidden rounded-md border border-transparent active:cursor-grabbing hover:border-df-blue/40 ${className}`}
      title={title ?? "Click to preview · drag to attach"}
    >
      <Thumb path={path} className="h-full w-full" />
      <span className="pointer-events-none absolute bottom-0.5 right-0.5 rounded bg-black/55 p-0.5 text-white opacity-0 transition group-hover/thumb:opacity-100">
        <GripVertical size={10} />
      </span>
    </div>
  );
}

export function HistoryItemRow({
  item,
  active,
  viewMode,
  favorite,
  scrollToken,
  onSelect,
  onToggleFavorite,
  onReusePrompt,
  onEditThis,
  onFixRegion,
  onEnhance,
  simpleLabels = false,
  onOpenFolder,
  onCopyPath,
  onDeleteGeneration,
  onDeleteImage,
}: Props) {
  const rowRef = useRef<HTMLLIElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const images = item.images.filter(Boolean);
  const thumb = images[0];
  const imageCount = images.length;
  const timeIso = item.created_at ?? item.timestamp;
  const badge = modelBadgeLabel(item.model_stem, item.model_family);
  const promptExcerpt = excerptPrompt(item.prompt);

  useEffect(() => {
    if (scrollToken && active && rowRef.current) {
      rowRef.current.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [scrollToken, active]);

  const openPath = thumb ?? item.manifest_path;
  const hasCreativeActions = Boolean(thumb && (onEditThis || onFixRegion || onEnhance));
  const previewItem = () => onSelect(item);

  const thumbGrid =
    imageCount > 1 && viewMode === "grid" ? (
      <div className="grid grid-cols-2 gap-0.5">
        {images.slice(0, 4).map((path, index) => (
          <DraggableHistoryThumb
            key={path}
            path={path}
            className="aspect-square w-full"
            title={`Click to preview · drag image ${index + 1} of ${imageCount}`}
            onSelect={previewItem}
          />
        ))}
      </div>
    ) : thumb ? (
      <DraggableHistoryThumb
        path={thumb}
        className={
          viewMode === "grid"
            ? "aspect-square w-full"
            : "h-11 w-11"
        }
        title={
          imageCount > 1
            ? `Click to preview · drag image 1 of ${imageCount}`
            : "Click to preview · drag to attach"
        }
        onSelect={previewItem}
      />
    ) : null;

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
        <div
          className={`flex w-full text-left ${
            viewMode === "grid" ? "flex-col gap-1" : "gap-2"
          }`}
        >
          {thumbGrid}
          <button
            type="button"
            onClick={() => onSelect(item)}
            className={`min-w-0 flex-1 ${viewMode === "grid" ? "text-left" : ""}`}
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-start gap-1">
                <p className="min-w-0 flex-1 truncate text-[10px] font-medium text-dfui-fg">
                  {item.title || "Untitled"}
                </p>
                {imageCount > 1 && (
                  <span
                    className="inline-flex shrink-0 items-center gap-0.5 rounded bg-dfui-bg/80 px-1 font-mono text-[8px] text-dfui-tertiary"
                    title={`${imageCount} images — drag any thumbnail to attach`}
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
        </div>

        {hasCreativeActions && (
          <div className="mt-1 flex flex-wrap gap-0.5 opacity-0 transition group-hover:opacity-100">
            {onEditThis && (
              <button
                type="button"
                title={simpleLabels ? "Edit this" : "Edit image"}
                onClick={(e) => {
                  e.stopPropagation();
                  onEditThis(item);
                }}
                className="inline-flex items-center gap-0.5 rounded bg-dfui-bg/80 px-1.5 py-0.5 text-[8px] text-dfui-secondary hover:text-dfui-fg"
              >
                <Pencil size={9} />
                {simpleLabels ? "Edit" : "Edit this"}
              </button>
            )}
            {onFixRegion && (
              <button
                type="button"
                title={simpleLabels ? "Fix region" : "Inpaint region"}
                onClick={(e) => {
                  e.stopPropagation();
                  onFixRegion(item);
                }}
                className="inline-flex items-center gap-0.5 rounded bg-dfui-bg/80 px-1.5 py-0.5 text-[8px] text-dfui-secondary hover:text-dfui-fg"
              >
                <Wand2 size={9} />
                {simpleLabels ? "Fix" : "Fix region"}
              </button>
            )}
            {onEnhance && (
              <button
                type="button"
                title="Enhance / upscale"
                onClick={(e) => {
                  e.stopPropagation();
                  onEnhance(item);
                }}
                className="inline-flex items-center gap-0.5 rounded bg-dfui-bg/80 px-1.5 py-0.5 text-[8px] text-dfui-secondary hover:text-dfui-fg"
              >
                <Sparkles size={9} />
                Enhance
              </button>
            )}
          </div>
        )}

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
              {thumb && onEditThis && (
                <li>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-dfui-accent/10"
                    onClick={() => {
                      setMenuOpen(false);
                      onEditThis(item);
                    }}
                  >
                    <Pencil size={11} />
                    {simpleLabels ? "Edit this" : "Edit image"}
                  </button>
                </li>
              )}
              {thumb && onFixRegion && (
                <li>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-dfui-accent/10"
                    onClick={() => {
                      setMenuOpen(false);
                      onFixRegion(item);
                    }}
                  >
                    <Wand2 size={11} />
                    {simpleLabels ? "Fix region" : "Inpaint region"}
                  </button>
                </li>
              )}
              {thumb && onEnhance && (
                <li>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-dfui-accent/10"
                    onClick={() => {
                      setMenuOpen(false);
                      onEnhance(item);
                    }}
                  >
                    <Sparkles size={11} />
                    Enhance
                  </button>
                </li>
              )}
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
                  Reuse settings
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
