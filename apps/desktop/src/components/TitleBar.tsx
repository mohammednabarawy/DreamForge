import { Minus, Square, X } from "lucide-react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { BRAND } from "../lib/brand";
import type { EngineState } from "../lib/engine";

const ENGINE_DOT: Record<EngineState, string> = {
  booting: "bg-amber-400 animate-pulse",
  ready: "bg-emerald-400",
  generating: "bg-dfui-forge animate-pulse",
  failed: "bg-red-400",
  restarting: "bg-amber-400 animate-pulse",
};

type Props = {
  engineState?: EngineState;
  bootMessage?: string;
  gpuName?: string | null;
  vramGb?: number | null;
  mpsAvailable?: boolean | null;
};

export function TitleBar({
  engineState = "booting",
  bootMessage,
  gpuName,
  vramGb,
  mpsAvailable,
}: Props) {
  const readyDetail =
    engineState === "ready" && gpuName
      ? mpsAvailable
        ? `${gpuName} · unified memory`
        : vramGb != null
          ? `${gpuName} · ${vramGb} GB`
          : gpuName
      : null;
  const win = getCurrentWindow();

  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-dfui-border/60 bg-dfui-panel/80 px-3 backdrop-blur-glass">
      <div
        data-tauri-drag-region
        className="flex flex-1 cursor-default items-center gap-2.5"
      >
        <img
          src={BRAND.logoIcon}
          alt=""
          className="h-8 w-8 shrink-0 rounded-md object-contain shadow-glow"
          draggable={false}
        />
        <img
          src={BRAND.logoWordmark}
          alt={BRAND.name}
          className="h-7 max-w-[min(200px,38vw)] shrink object-contain object-left"
          draggable={false}
        />
      </div>
      <div className="mr-2 flex items-center gap-2">
        <span
          className={`h-2 w-2 rounded-full ${ENGINE_DOT[engineState]}`}
          title={`Engine: ${engineState}`}
          aria-hidden
        />
        <span
          className="hidden max-w-[220px] truncate font-mono text-[10px] uppercase tracking-wider text-dfui-muted sm:inline"
          title={bootMessage}
        >
          {engineState === "booting" || engineState === "restarting"
            ? bootMessage || engineState
            : readyDetail || engineState}
        </span>
      </div>
      <div className="flex items-center gap-1">
        <button
          type="button"
          className="rounded-md p-1.5 text-dfui-muted hover:bg-dfui-surface-hover hover:text-dfui-fg"
          onClick={() => void win.minimize()}
          aria-label="Minimize"
        >
          <Minus size={16} />
        </button>
        <button
          type="button"
          className="rounded-md p-1.5 text-dfui-muted hover:bg-dfui-surface-hover hover:text-dfui-fg"
          onClick={() => void win.toggleMaximize()}
          aria-label="Maximize"
        >
          <Square size={14} />
        </button>
        <button
          type="button"
          className="rounded-md p-1.5 text-dfui-muted hover:bg-red-500/20 hover:text-red-300"
          onClick={() => void win.close()}
          aria-label="Close"
        >
          <X size={16} />
        </button>
      </div>
    </header>
  );
}
