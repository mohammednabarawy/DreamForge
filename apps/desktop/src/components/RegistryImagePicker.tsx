import { FolderOpen, X } from "lucide-react";
import { useMemo, useState } from "react";
import {
  basename,
  handleImagePathDragOver,
  readImagePathFromDrop,
} from "../lib/referenceImage";
import { pickImageFile } from "../lib/tauri-api";

type Props = {
  stagingPaths: string[];
  onStagingChange: (paths: string[]) => void;
  sessionPaths?: string[];
  includeSession?: boolean;
  onIncludeSessionChange?: (value: boolean) => void;
  disabled?: boolean;
};

export function RegistryImagePicker({
  stagingPaths,
  onStagingChange,
  sessionPaths = [],
  includeSession = true,
  onIncludeSessionChange,
  disabled = false,
}: Props) {
  const [dragOver, setDragOver] = useState(false);
  const effectivePaths = useMemo(() => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const path of stagingPaths) {
      const trimmed = path.trim();
      if (!trimmed || seen.has(trimmed)) continue;
      seen.add(trimmed);
      out.push(trimmed);
    }
    if (includeSession) {
      for (const path of sessionPaths) {
        const trimmed = path.trim();
        if (!trimmed || seen.has(trimmed)) continue;
        seen.add(trimmed);
        out.push(trimmed);
      }
    }
    return out;
  }, [includeSession, sessionPaths, stagingPaths]);

  const addImage = async () => {
    if (disabled) return;
    const path = await pickImageFile();
    if (!path?.trim()) return;
    if (stagingPaths.includes(path)) return;
    onStagingChange([...stagingPaths, path]);
  };

  return (
    <div
      className={`space-y-1.5 rounded-md border bg-dfui-bg/20 p-2 transition-colors ${
        dragOver
          ? "border-df-blue/60 bg-df-blue/10 ring-1 ring-df-blue/25"
          : "border-dfui-border/50"
      }`}
      onDragEnterCapture={(event) => {
        if (handleImagePathDragOver(event, disabled)) setDragOver(true);
      }}
      onDragOverCapture={(event) => {
        if (handleImagePathDragOver(event, disabled)) setDragOver(true);
      }}
      onDragEnter={(event) => {
        if (handleImagePathDragOver(event, disabled)) setDragOver(true);
      }}
      onDragOver={(event) => {
        if (handleImagePathDragOver(event, disabled)) setDragOver(true);
      }}
      onDragLeave={(event) => {
        event.stopPropagation();
        if (!(event.currentTarget as HTMLElement).contains(event.relatedTarget as Node)) {
          setDragOver(false);
        }
      }}
      onDrop={(event) => {
        event.preventDefault();
        event.stopPropagation();
        setDragOver(false);
        if (disabled) return;
        const path = readImagePathFromDrop(event.dataTransfer);
        if (!path || stagingPaths.includes(path)) return;
        onStagingChange([...stagingPaths, path]);
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[10px] text-dfui-secondary">
          {effectivePaths.length} image{effectivePaths.length === 1 ? "" : "s"} selected
        </p>
        <button
          type="button"
          disabled={disabled}
          onClick={() => void addImage()}
          className="inline-flex items-center gap-1 rounded-md border border-df-blue/35 bg-df-blue/10 px-2 py-1 text-[10px] font-medium text-df-blue hover:border-df-blue/55 disabled:opacity-50"
        >
          <FolderOpen size={12} />
          Add images…
        </button>
      </div>

      {stagingPaths.length > 0 && (
        <ul className="max-h-24 space-y-1 overflow-y-auto">
          {stagingPaths.map((path) => (
            <li
              key={path}
              className="flex items-center gap-1 rounded border border-dfui-border/40 bg-dfui-panel/40 px-1.5 py-0.5"
            >
              <span className="min-w-0 flex-1 truncate font-mono text-[9px] text-dfui-secondary">
                {basename(path)}
              </span>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onStagingChange(stagingPaths.filter((item) => item !== path))}
                className="shrink-0 rounded p-0.5 text-dfui-muted hover:text-dfui-fg"
                title="Remove image"
              >
                <X size={12} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {sessionPaths.length > 0 && onIncludeSessionChange && (
        <label className="inline-flex items-center gap-1.5 text-[10px] text-dfui-tertiary">
          <input
            type="checkbox"
            checked={includeSession}
            disabled={disabled}
            onChange={(e) => onIncludeSessionChange(e.target.checked)}
            className="accent-dfui-accent"
          />
          Include canvas / attached reference images ({sessionPaths.length})
        </label>
      )}

      {effectivePaths.length === 0 && (
        <p className="text-[10px] leading-snug text-dfui-muted">
          {dragOver
            ? "Drop to add image"
            : "Drag from history, choose files above, or enable canvas images if you already attached one on the prompt bar."}
        </p>
      )}
    </div>
  );
}

export function mergeRegistryImagePaths(
  stagingPaths: string[],
  sessionPaths: string[],
  includeSession: boolean,
): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const path of [...stagingPaths, ...(includeSession ? sessionPaths : [])]) {
    const trimmed = path.trim();
    if (!trimmed || seen.has(trimmed)) continue;
    seen.add(trimmed);
    out.push(trimmed);
  }
  return out;
}
