import { Minus, RefreshCw, Settings, Square, User, X } from "lucide-react";
import { isTauri } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { BRAND } from "../lib/brand";
import {
  engineRestartControlState,
  engineStatusDisplay,
  type EngineState,
  type EngineStatusTone,
} from "../lib/engine";
import type { UiExperience } from "../lib/experienceUi";

const ENGINE_TONE_DOT: Record<EngineStatusTone, string> = {
  ready: "bg-emerald-400",
  busy: "bg-dfui-forge animate-pulse",
  warn: "bg-amber-400 animate-pulse",
  error: "bg-red-400",
};

const ENGINE_TONE_PILL: Record<EngineStatusTone, string> = {
  ready: "border-emerald-500/25 bg-emerald-500/10 text-emerald-100",
  busy: "border-dfui-forge/30 bg-dfui-forge/10 text-dfui-fg",
  warn: "border-amber-500/25 bg-amber-500/10 text-amber-100",
  error: "border-rose-500/30 bg-rose-500/10 text-rose-100",
};

type Props = {
  engineState?: EngineState;
  bootMessage?: string;
  workerReady?: boolean;
  restarting?: boolean;
  gpuName?: string | null;
  vramGb?: number | null;
  mpsAvailable?: boolean | null;
  profileLabel?: string;
  profileDetail?: string;
  experience?: UiExperience;
  onExperienceChange?: (experience: UiExperience) => void;
  onOpenAppSettings?: () => void;
  onRestartEngine?: () => void;
};

function ExperienceToggle({
  experience,
  onChange,
}: {
  experience: UiExperience;
  onChange: (next: UiExperience) => void;
}) {
  const isEasy = experience === "simple";
  return (
    <div
      data-tauri-drag-region={false}
      className="flex rounded-lg border border-dfui-border/55 bg-dfui-bg/50 p-0.5 shadow-sm"
      role="group"
      aria-label="Interface experience"
    >
      <button
        type="button"
        onClick={() => onChange("simple")}
        className={`rounded-md px-3 py-1 text-[10px] font-semibold transition ${
          isEasy
            ? "bg-dfui-accent/20 text-dfui-accent shadow-sm"
            : "text-dfui-muted hover:text-dfui-fg"
        }`}
        title="Easy mode — focused Create, Edit, Fix, and Enhance flows"
        aria-pressed={isEasy}
      >
        Easy
      </button>
      <button
        type="button"
        onClick={() => onChange("pro")}
        className={`rounded-md px-3 py-1 text-[10px] font-semibold transition ${
          !isEasy
            ? "bg-dfui-accent/20 text-dfui-accent shadow-sm"
            : "text-dfui-muted hover:text-dfui-fg"
        }`}
        title="Pro mode — model library, batch tools, agent, and full inspector"
        aria-pressed={!isEasy}
      >
        Pro
      </button>
    </div>
  );
}

export function TitleBar({
  engineState = "booting",
  bootMessage,
  workerReady = false,
  restarting = false,
  gpuName,
  vramGb,
  mpsAvailable,
  profileLabel = "Local profile",
  profileDetail,
  experience = "pro",
  onExperienceChange,
  onOpenAppSettings,
  onRestartEngine,
}: Props) {
  const status = engineStatusDisplay({
    engineState,
    bootMessage,
    workerReady,
    restarting,
    gpuName,
    vramGb,
    mpsAvailable,
  });
  const restartControl = engineRestartControlState({
    engineState,
    workerReady,
    restarting,
  });
  const showRestart = Boolean(onRestartEngine) && restartControl.visible;

  const runWindowAction = (action: (win: ReturnType<typeof getCurrentWindow>) => void) => {
    if (!isTauri()) return;
    action(getCurrentWindow());
  };

  const handleTitleBarPointerDown = (event: React.PointerEvent<HTMLElement>) => {
    if (!isTauri() || event.button !== 0) return;
    const target = event.target as HTMLElement | null;
    // Keep controls clickable. The title bar itself, branding, status, and
    // other empty areas should start a native window drag on pointer-down.
    if (target?.closest("button, input, textarea, select, [data-tauri-drag-region='false']")) {
      return;
    }
    void getCurrentWindow().startDragging();
  };

  return (
    <header
      data-tauri-drag-region
      onPointerDown={handleTitleBarPointerDown}
      className="grid h-12 shrink-0 cursor-move grid-cols-[1fr_auto_1fr] items-center border-b border-dfui-border/60 bg-dfui-panel/80 px-3 backdrop-blur-glass select-none"
    >
      <div className="flex min-w-0 cursor-default items-center">
        <img
          src={BRAND.logoWordmark}
          alt={BRAND.name}
          className="h-7 max-w-[min(220px,40vw)] shrink object-contain object-left"
          draggable={false}
        />
      </div>

      <div className="flex justify-center px-2">
        {onExperienceChange ? (
          <ExperienceToggle
            experience={experience}
            onChange={onExperienceChange}
          />
        ) : null}
      </div>

      <div className="flex min-w-0 items-center justify-end gap-1">
        <div className="mr-1 flex min-w-0 items-center gap-1.5">
          <div
            className={`hidden min-w-0 items-center gap-1.5 rounded-md border px-2 py-1 sm:inline-flex ${ENGINE_TONE_PILL[status.tone]}`}
            title={status.title}
          >
            <span
              className={`h-1.5 w-1.5 shrink-0 rounded-full ${ENGINE_TONE_DOT[status.tone]}`}
              aria-hidden
            />
            <span className="max-w-[min(160px,24vw)] truncate font-mono text-[10px] uppercase tracking-wide">
              {status.label}
            </span>
          </div>
          {showRestart ? (
            <button
              type="button"
              data-tauri-drag-region={false}
              onClick={onRestartEngine}
              disabled={restartControl.disabled}
              className={`inline-flex shrink-0 items-center gap-1 rounded-md border px-1.5 py-1 text-[10px] font-medium transition disabled:cursor-not-allowed disabled:opacity-70 ${
                status.tone === "error"
                  ? "border-rose-400/40 bg-rose-500/15 text-rose-100 hover:bg-rose-500/25"
                  : "border-amber-400/35 bg-amber-500/10 text-amber-100 hover:bg-amber-500/20"
              }`}
              title={
                restartControl.disabled
                  ? "Restarting GPU engine…"
                  : engineState === "failed"
                    ? "Restart GPU engine"
                    : "GPU engine is not ready — restart"
              }
              aria-label="Restart GPU engine"
            >
              <RefreshCw
                size={11}
                className={restartControl.disabled ? "animate-spin" : undefined}
              />
              <span className="hidden md:inline">
                {restartControl.disabled ? "Restarting" : "Restart"}
              </span>
            </button>
          ) : null}
          <div className="hidden items-center gap-1.5 border-l border-dfui-border/50 pl-2 sm:flex">
            <span
              className="inline-flex max-w-[120px] items-center gap-1.5 truncate rounded-md border border-dfui-border/50 bg-dfui-bg/40 px-2 py-1 text-[10px] text-dfui-secondary"
              title={profileDetail ?? profileLabel}
            >
              <User size={12} className="shrink-0 text-dfui-accent" />
              <span className="truncate">{profileLabel}</span>
            </span>
            {onOpenAppSettings && (
              <button
                type="button"
                data-tauri-drag-region={false}
                onClick={onOpenAppSettings}
                className="inline-flex items-center gap-1 rounded-md border border-dfui-border/50 bg-dfui-bg/40 px-2 py-1 text-[10px] font-medium text-dfui-secondary transition hover:border-dfui-accent/40 hover:text-dfui-fg"
                title="App settings"
                aria-label="Open app settings"
              >
                <Settings size={13} />
                <span className="hidden xl:inline">Settings</span>
              </button>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1" data-tauri-drag-region={false}>
          <button
            type="button"
            className="rounded-md p-1.5 text-dfui-muted hover:bg-dfui-surface-hover hover:text-dfui-fg"
            onClick={() => runWindowAction((win) => void win.minimize())}
            aria-label="Minimize"
          >
            <Minus size={16} />
          </button>
          <button
            type="button"
            className="rounded-md p-1.5 text-dfui-muted hover:bg-dfui-surface-hover hover:text-dfui-fg"
            onClick={() => runWindowAction((win) => void win.toggleMaximize())}
            aria-label="Maximize"
          >
            <Square size={14} />
          </button>
          <button
            type="button"
            className="rounded-md p-1.5 text-dfui-muted hover:bg-red-500/20 hover:text-red-300"
            onClick={() => runWindowAction((win) => void win.close())}
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>
      </div>
    </header>
  );
}
