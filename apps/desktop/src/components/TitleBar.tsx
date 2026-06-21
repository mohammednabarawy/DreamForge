import { Minus, Settings, Square, User, X } from "lucide-react";
import { isTauri } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { BRAND } from "../lib/brand";
import type { EngineState } from "../lib/engine";
import type { UiExperience } from "../lib/experienceUi";

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
  profileLabel?: string;
  profileDetail?: string;
  experience?: UiExperience;
  onExperienceChange?: (experience: UiExperience) => void;
  onOpenAppSettings?: () => void;
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
  gpuName,
  vramGb,
  mpsAvailable,
  profileLabel = "Local profile",
  profileDetail,
  experience = "pro",
  onExperienceChange,
  onOpenAppSettings,
}: Props) {
  const readyDetail =
    engineState === "ready" && gpuName
      ? mpsAvailable
        ? `${gpuName} · unified memory`
        : vramGb != null
          ? `${gpuName} · ${vramGb} GB`
          : gpuName
      : null;

  const runWindowAction = (action: (win: ReturnType<typeof getCurrentWindow>) => void) => {
    if (!isTauri()) return;
    action(getCurrentWindow());
  };

  return (
    <header className="grid h-12 shrink-0 grid-cols-[1fr_auto_1fr] items-center border-b border-dfui-border/60 bg-dfui-panel/80 px-3 backdrop-blur-glass">
      <div
        data-tauri-drag-region
        className="flex min-w-0 cursor-default items-center gap-2.5"
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

      <div className="flex justify-center px-2">
        {onExperienceChange ? (
          <ExperienceToggle
            experience={experience}
            onChange={onExperienceChange}
          />
        ) : null}
      </div>

      <div className="flex min-w-0 items-center justify-end gap-1">
        <div className="mr-1 flex min-w-0 items-center gap-2">
          <span
            className={`h-2 w-2 shrink-0 rounded-full ${ENGINE_DOT[engineState]}`}
            title={`Engine: ${engineState}`}
            aria-hidden
          />
          <span
            className="hidden max-w-[140px] truncate font-mono text-[10px] uppercase tracking-wider text-dfui-muted lg:inline"
            title={bootMessage}
          >
            {engineState === "booting" || engineState === "restarting"
              ? bootMessage || engineState
              : readyDetail || engineState}
          </span>
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
        <div className="flex items-center gap-1">
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
