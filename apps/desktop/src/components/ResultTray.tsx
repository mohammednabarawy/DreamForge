import { Check, ImageIcon, RefreshCw, Upload } from "lucide-react";
import { pathToAssetUrl } from "../lib/preview-display";
import type { EnhanceTarget } from "../lib/autoEnhance";

type Props = {
  images: string[];
  activePath?: string | null;
  sourcePath?: string | null;
  onSelect: (path: string) => void;
  onRetry?: () => void;
  onUseAsSource?: (path: string) => void;
  retryBusy?: boolean;
  onVaryImage?: (amount: "subtle" | "strong") => void;
  onAutoEnhance?: (target: EnhanceTarget) => void;
};

export function ResultTray({
  images,
  activePath,
  sourcePath,
  onSelect,
  onRetry,
  onUseAsSource,
  retryBusy,
  onVaryImage,
  onAutoEnhance,
}: Props) {
  if (images.length === 0) return null;

  return (
    <div
      className="absolute bottom-6 left-1/2 z-20 flex max-w-[min(42rem,92vw)] -translate-x-1/2 flex-col gap-1.5 rounded-lg border border-dfui-border/70 bg-dfui-panel/95 px-2 py-2 shadow-glass backdrop-blur-md"
      role="region"
      aria-label="Generation candidates"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 px-0.5">
        <p className="font-mono text-[9px] uppercase tracking-wider text-dfui-tertiary">
          Candidates ({images.length})
        </p>
        <div className="flex flex-wrap items-center gap-1.5">
          {onVaryImage ? (
            <div className="flex items-center gap-1 rounded-md border border-dfui-border/50 bg-dfui-bg/40 px-1.5 py-0.5 text-[10px]">
              <span className="text-dfui-tertiary">Vary:</span>
              <button
                type="button"
                onClick={() => onVaryImage("subtle")}
                className="rounded px-1.5 py-0.5 text-dfui-secondary hover:bg-dfui-surface hover:text-dfui-fg"
                title="Light img2img variation"
              >
                Subtle
              </button>
              <button
                type="button"
                onClick={() => onVaryImage("strong")}
                className="rounded px-1.5 py-0.5 text-dfui-secondary hover:bg-dfui-surface hover:text-dfui-fg"
                title="Stronger img2img variation"
              >
                Strong
              </button>
            </div>
          ) : null}
          {onAutoEnhance ? (
            <div className="flex items-center gap-1 rounded-md border border-dfui-border/50 bg-dfui-bg/40 px-1.5 py-0.5 text-[10px]">
              <span className="text-dfui-tertiary">Fix:</span>
              <button
                type="button"
                onClick={() => onAutoEnhance("face")}
                className="rounded px-1.5 py-0.5 text-dfui-secondary hover:bg-dfui-surface hover:text-dfui-fg"
                title="Detect & fix faces"
              >
                Face
              </button>
              <button
                type="button"
                onClick={() => onAutoEnhance("hands")}
                className="rounded px-1.5 py-0.5 text-dfui-secondary hover:bg-dfui-surface hover:text-dfui-fg"
                title="Detect & fix hands"
              >
                Hands
              </button>
              <button
                type="button"
                onClick={() => onAutoEnhance("eyes")}
                className="rounded px-1.5 py-0.5 text-dfui-secondary hover:bg-dfui-surface hover:text-dfui-fg"
                title="Detect & fix eyes"
              >
                Eyes
              </button>
            </div>
          ) : null}
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              disabled={retryBusy}
              className="inline-flex items-center gap-1 rounded-md border border-dfui-border/60 px-2 py-1 text-[10px] text-dfui-secondary hover:border-dfui-accent/40 hover:text-dfui-fg disabled:opacity-50"
              aria-label="Retry generation with same settings"
            >
              <RefreshCw size={11} />
              Retry
            </button>
          ) : null}
          {onUseAsSource && activePath ? (
            <button
              type="button"
              onClick={() => onUseAsSource(activePath)}
              disabled={activePath === sourcePath}
              className="inline-flex items-center gap-1 rounded-md border border-dfui-border/60 px-2 py-1 text-[10px] text-dfui-secondary hover:border-dfui-accent/40 hover:text-dfui-fg disabled:opacity-50"
              aria-label="Use selected candidate as current source image"
            >
              <Upload size={11} />
              Use as source
            </button>
          ) : null}
        </div>
      </div>
      {images.length > 1 ? <div
        className="flex gap-1.5 overflow-x-auto pb-0.5"
        role="listbox"
        aria-label="Select a candidate image"
      >
        {images.map((path, index) => {
          const active = path === activePath;
          const url = pathToAssetUrl(path);
          return (
            <button
              key={path}
              type="button"
              role="option"
              aria-selected={active}
              aria-label={`Candidate ${index + 1}${active ? ", selected" : ""}`}
              onClick={() => onSelect(path)}
              className={`relative h-14 w-14 shrink-0 overflow-hidden rounded-md border transition ${
                active
                  ? "border-dfui-accent ring-2 ring-dfui-accent/35"
                  : "border-dfui-border/60 hover:border-dfui-accent/35"
              }`}
            >
              {url ? (
                <img
                  src={url}
                  alt=""
                  className="h-full w-full object-cover"
                  draggable={false}
                />
              ) : (
                <span className="flex h-full w-full items-center justify-center bg-dfui-surface text-dfui-tertiary">
                  <ImageIcon size={16} />
                </span>
              )}
              {active ? (
                <span className="absolute right-0.5 top-0.5 rounded-full bg-dfui-accent p-0.5 text-white">
                  <Check size={10} />
                </span>
              ) : null}
            </button>
          );
        })}
      </div> : null}
    </div>
  );
}
