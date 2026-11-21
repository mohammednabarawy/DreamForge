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
  formatExactDateTime,
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
    <button
      type="button"
      aria-label={title ?? "Preview image; drag to attach"}
      draggable
      onMouseDown={() => primeImagePathDragSession(path)}
      onClick={(event) => {
        event.stopPropagation();
        onSelect?.();
      }}
      onDragStart={(event) => {
        setImagePathDragData(event.dataTransfer, path);
        event.stopPropagation();
        // Avoid setDragImage(<img>) — WebView2 treats it as a native file drag and drops custom MIME.
      }}
      onDragEnd={() => scheduleClearImagePathDragSession()}
      className={`group/thumb relative shrink-0 cursor-grab overflow-hidden rounded-md border border-transparent active:cursor-grabbing hover:border-df-blue/40 ${className}`}
      title={title ?? "Click to preview · drag to attach"}
    >
      <Thumb path={path} className="h-full w-full" />
      <span className="pointer-events-none absolute bottom-0.5 right-0.5 rounded bg-black/55 p-0.5 text-white opacity-0 transition group-hover/thumb:opacity-100">
        <GripVertical size={10} />
      </span>
    </button>
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
  const menuBtnRef = useRef<HTMLButtonElement>(null);
  const lastScrolledTokenRef = useRef<number | undefined>(undefined);
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuOpensUp, setMenuOpensUp] = useState(false);
  const images = item.images.filter(Boolean);
  const thumb = images[0];
  const imageCount = images.length;
  const timeIso = item.created_at || item.timestamp;
  const relativeTime = formatRelativeTime(timeIso);
  const exactTime = formatExactDateTime(timeIso);
  const badge = modelBadgeLabel(item.model_stem, item.model_family);
  const promptExcerpt = excerptPrompt(item.prompt);
  const resolutionLabel =
    item.width && item.height ? `${item.width}×${item.height}` : null;

  useEffect(() => {
    if (!scrollToken || !active || !rowRef.current) return;
    if (lastScrolledTokenRef.current === scrollToken) return;
    lastScrolledTokenRef.current = scrollToken;
    rowRef.current.scrollIntoView({ block: "nearest", behavior: "auto" });
  }, [scrollToken, active]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        setMenuOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [menuOpen]);

  const openMenuWithPlacement = () => {
    const anchor = menuBtnRef.current ?? rowRef.current;
    if (anchor) {
      const rect = anchor.getBoundingClientRect();
      setMenuOpensUp(rect.bottom > window.innerHeight - 250);
    } else {
      setMenuOpensUp(false);
    }
    setMenuOpen(true);
  };

  const openPath = thumb ?? item.manifest_path;
  const hasCreativeActions = Boolean(thumb && (onEditThis || onFixRegion || onEnhance));
  const canDeleteSingleImage = imageCount > 1 && Boolean(onDeleteImage);
  const previewItem = (path = thumb) =>
    onSelect({
      ...item,
      images: path ? [path, ...images.filter((image) => image !== path)] : images,
    });

  const thumbGrid =
    imageCount > 1 && viewMode === "grid" ? (
      <div className="relative grid grid-cols-2 gap-0.5">
        {images.slice(0, 4).map((path, index) => (
          <DraggableHistoryThumb
            key={path}
            path={path}
            className="aspect-square w-full"
            title={`Click to preview · drag image ${index + 1} of ${imageCount}`}
            onSelect={() => previewItem(path)}
          />
        ))}
        {imageCount > 4 && (
          <span className="pointer-events-none absolute bottom-1 right-1 rounded bg-black/70 px-1 font-mono text-[8px] text-white">
            +{imageCount - 4}
          </span>
        )}
      </div>
    ) : thumb ? (
      <DraggableHistoryThumb
        path={thumb}
        className={viewMode === "grid" ? "aspect-square w-full" : "h-12 w-12"}
        title={
          imageCount > 1
            ? `Click to preview · drag image 1 of ${imageCount}`
            : "Click to preview · drag to attach"
        }
        onSelect={() => previewItem(thumb)}
      />
    ) : null;

  return (
    <li
      ref={rowRef}
      className={viewMode === "grid" ? "min-w-0" : undefined}
      data-manifest={item.manifest_path}
      onContextMenu={(event) => {
        event.preventDefault();
        openMenuWithPlacement();
      }}
    >
      <div
        className={`group relative rounded-lg border transition ${
          active
            ? "border-dfui-accent/55 bg-dfui-accent/12 shadow-[inset_0_0_0_1px_rgba(99,102,241,0.12)]"
            : "border-transparent hover:border-dfui-border/50 hover:bg-dfui-bg/45"
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
            onClick={() => previewItem(thumb)}
            className={`min-w-0 flex-1 text-left focus:outline-none`}
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-start gap-1 pr-7">
                <p
                  className="min-w-0 flex-1 truncate text-[10px] font-medium text-dfui-fg"
                  title={item.title || "Untitled"}
                >
                  {item.title || "Untitled"}
                </p>
                {imageCount > 1 && (
                  <span
                    className="inline-flex shrink-0 items-center gap-0.5 rounded bg-dfui-bg/80 px-1 font-mono text-[8px] text-dfui-tertiary"
                    title={`${imageCount} images — click or drag any thumbnail`}
                  >
                    <Images size={9} />
                    {imageCount}
                  </span>
                )}
              </div>
              {promptExcerpt && (
                <p
                  className="mt-0.5 line-clamp-2 text-[9px] leading-snug text-dfui-muted"
                  title={item.prompt}
                >
                  {promptExcerpt}
                </p>
              )}
              <div className="mt-1 flex flex-wrap items-center gap-1">
                <span
                  title={item.model_name || badge}
                  className="max-w-full truncate rounded bg-dfui-bg/65 px-1 font-mono text-[8px] text-dfui-data"
                >
                  {badge}
                </span>
                {resolutionLabel && viewMode === "list" && (
                  <span className="rounded bg-dfui-bg/50 px-1 font-mono text-[8px] text-dfui-tertiary">
                    {resolutionLabel}
                  </span>
                )}
                {relativeTime && (
                  <span
                    className="font-mono text-[8px] text-dfui-tertiary"
                    title={exactTime || undefined}
                  >
                    {relativeTime}
                  </span>
                )}
              </div>
            </div>
          </button>
        </div>

        {viewMode === "list" && imageCount > 1 && (
          <div className="mt-1.5 flex items-center gap-1 overflow-x-auto pb-0.5">
            {images.slice(0, 6).map((path, index) => (
              <DraggableHistoryThumb
                key={path}
                path={path}
                className="h-7 w-7"
                title={`Preview / drag image ${index + 1} of ${imageCount}`}
                onSelect={() => previewItem(path)}
              />
            ))}
            {imageCount > 6 && (
              <span className="px-1 font-mono text-[8px] text-dfui-tertiary">
                +{imageCount - 6}
              </span>
            )}
          </div>
        )}

        {hasCreativeActions && (
          <div className="mt-1 flex flex-wrap gap-0.5 opacity-0 transition group-hover:opacity-100 group-focus-within:opacity-100">
            {onEditThis && (
              <button
                type="button"
                title={simpleLabels ? "Edit this" : "Edit image"}
                onClick={(e) => {
                  e.stopPropagation();
                  onEditThis(item);
                }}
                className="inline-flex items-center gap-0.5 rounded bg-dfui-bg/80 px-1.5 py-0.5 text-[8px] text-dfui-secondary hover:bg-dfui-accent/15 hover:text-dfui-fg"
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
                className="inline-flex items-center gap-0.5 rounded bg-dfui-bg/80 px-1.5 py-0.5 text-[8px] text-dfui-secondary hover:bg-dfui-accent/15 hover:text-dfui-fg"
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
                className="inline-flex items-center gap-0.5 rounded bg-dfui-bg/80 px-1.5 py-0.5 text-[8px] text-dfui-secondary hover:bg-dfui-accent/15 hover:text-dfui-fg"
              >
                <Sparkles size={9} />
                Enhance
              </button>
            )}
          </div>
        )}

        <div
          className={`absolute top-1 flex gap-0.5 rounded bg-dfui-panel/75 backdrop-blur-sm ${
            viewMode === "grid" ? "right-1" : "right-1.5"
          }`}
        >
          <button
            type="button"
            title={favorite ? "Remove favorite" : "Favorite"}
            aria-label={favorite ? "Remove favorite" : "Add favorite"}
            aria-pressed={favorite}
            onClick={(e) => {
              e.stopPropagation();
              onToggleFavorite(item.manifest_path);
            }}
            className={`rounded p-0.5 transition ${
              favorite
                ? "text-amber-400"
                : "text-dfui-tertiary opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 hover:text-amber-300"
            }`}
          >
            <Star size={12} fill={favorite ? "currentColor" : "none"} />
          </button>
          <button
            ref={menuBtnRef}
            type="button"
            title="Actions"
            aria-label="Generation actions"
            aria-expanded={menuOpen}
            onClick={(e) => {
              e.stopPropagation();
              if (menuOpen) setMenuOpen(false);
              else openMenuWithPlacement();
            }}
            className={`rounded p-0.5 text-dfui-tertiary transition hover:text-dfui-fg ${
              menuOpen
                ? "opacity-100 text-dfui-fg"
                : "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
            }`}
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
              onClick={(e) => {
                e.stopPropagation();
                setMenuOpen(false);
              }}
            />
            <ul
              className={`absolute right-0 z-20 min-w-[10rem] rounded-md border border-dfui-border/80 bg-dfui-panel py-1 text-[10px] shadow-xl ${
                menuOpensUp ? "bottom-7" : "top-6"
              }`}
            >
              {thumb && onEditThis && (
                <li>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left hover:bg-dfui-accent/10"
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
                    className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left hover:bg-dfui-accent/10"
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
                    className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left hover:bg-dfui-accent/10"
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
                  className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left hover:bg-dfui-accent/10"
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
                  className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left hover:bg-dfui-accent/10"
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
                    className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left hover:bg-dfui-accent/10"
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
              {thumb && canDeleteSingleImage && (
                <li>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-red-300 hover:bg-red-500/10"
                    onClick={() => {
                      setMenuOpen(false);
                      onDeleteImage!(item, thumb);
                    }}
                  >
                    <Trash2 size={11} />
                    Delete image only
                  </button>
                </li>
              )}
              <li>
                <button
                  type="button"
                  className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-red-300 hover:bg-red-500/10"
                  onClick={() => {
                    setMenuOpen(false);
                    onDeleteGeneration(item);
                  }}
                >
                  <Trash2 size={11} />
                  {canDeleteSingleImage ? "Delete all images" : "Delete generation"}
                </button>
              </li>
            </ul>
          </>
        )}
      </div>
    </li>
  );
}
