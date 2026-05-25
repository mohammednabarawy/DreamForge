import { ChevronLeft, ChevronRight, RefreshCw, Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  browseImages,
  imageBrowserMetadata,
  reindexImageLibrary,
} from "../lib/studioBridge";
import { readImagePreviewQueued } from "../lib/preview-queue";
import { setImagePathDragData } from "../lib/referenceImage";

type Props = {
  onSelectPath?: (path: string) => void;
};

export function ImageLibraryPanel({ onSelectPath }: Props) {
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [items, setItems] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [rangeText, setRangeText] = useState("");
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [metaText, setMetaText] = useState("");
  const [thumbs, setThumbs] = useState<Record<string, string>>({});

  const load = useCallback(async (p: number, q: string) => {
    setLoading(true);
    try {
      const res = await browseImages(p, q);
      setItems(res.items);
      setPage(res.page);
      setPages(Math.max(1, res.pages));
      setRangeText(res.range_text ?? "");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(1, search);
  }, []);

  useEffect(() => {
    let cancelled = false;
    for (const path of items.slice(0, 24)) {
      void readImagePreviewQueued(path)
        .then((r) => {
          if (!cancelled) {
            setThumbs((prev) => ({ ...prev, [path]: r.data_url }));
          }
        })
        .catch(() => {});
    }
    return () => {
      cancelled = true;
    };
  }, [items]);

  const select = async (path: string) => {
    setSelected(path);
    onSelectPath?.(path);
    try {
      const res = await imageBrowserMetadata(path);
      setMetaText(res.text ?? "");
    } catch {
      setMetaText("");
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex gap-1.5 border-b border-dfui-border/40 p-2">
        <div className="relative flex-1">
          <Search
            size={12}
            className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-dfui-muted"
          />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void load(1, search);
            }}
            placeholder="Filter library…"
            className="df-input w-full py-1.5 pl-7 pr-2 text-xs"
          />
        </div>
        <button
          type="button"
          title="Search"
          className="rounded-md border border-dfui-border/50 px-2 text-[10px] text-dfui-muted hover:text-dfui-fg"
          onClick={() => void load(1, search)}
        >
          Go
        </button>
        <button
          type="button"
          title="Reindex outputs"
          className="rounded-md border border-dfui-border/50 p-1.5 text-dfui-muted hover:text-dfui-fg"
          onClick={() => {
            void reindexImageLibrary().then((res) => {
              setItems(res.items);
              setPages(Math.max(1, res.pages));
              setPage(1);
            });
          }}
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {rangeText && (
        <p className="px-2 py-1 font-mono text-[9px] text-dfui-tertiary">{rangeText}</p>
      )}

      <div className="flex-1 overflow-y-auto p-2">
        {items.length === 0 ? (
          <p className="py-6 text-center text-xs text-dfui-muted">
            No indexed images. Run reindex after generations land in your outputs
            folder.
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-1.5">
            {items.map((path) => (
              <button
                key={path}
                type="button"
                draggable
                onDragStart={(e) => setImagePathDragData(e.dataTransfer, path)}
                onClick={() => void select(path)}
                className={`overflow-hidden rounded-md border text-left transition ${
                  selected === path
                    ? "border-dfui-accent/60 ring-1 ring-dfui-accent/30"
                    : "border-dfui-border/40 hover:border-dfui-accent/30"
                }`}
              >
                {thumbs[path] ? (
                  <img
                    src={thumbs[path]}
                    alt=""
                    className="aspect-square w-full object-cover"
                  />
                ) : (
                  <div className="aspect-square bg-dfui-bg/50" />
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between border-t border-dfui-border/40 px-2 py-1.5">
        <button
          type="button"
          disabled={page <= 1}
          className="rounded p-1 text-dfui-muted disabled:opacity-30"
          onClick={() => void load(page - 1, search)}
        >
          <ChevronLeft size={16} />
        </button>
        <span className="font-mono text-[10px] text-dfui-tertiary">
          {page} / {pages}
        </span>
        <button
          type="button"
          disabled={page >= pages}
          className="rounded p-1 text-dfui-muted disabled:opacity-30"
          onClick={() => void load(page + 1, search)}
        >
          <ChevronRight size={16} />
        </button>
      </div>

      {metaText && (
        <pre className="max-h-28 overflow-y-auto border-t border-dfui-border/40 p-2 font-mono text-[9px] leading-snug text-dfui-tertiary whitespace-pre-wrap">
          {metaText}
        </pre>
      )}
    </div>
  );
}
