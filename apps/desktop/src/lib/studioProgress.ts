import type { EngineState } from "./engine";
import { bootPhaseLabel, engineLabel } from "./engine";
import type { LiveProgress } from "./generationProgressUi";
import { generationFooterStatus } from "./generationProgressUi";

export type StudioProgressKind = "idle" | "boot" | "prepare" | "job";

export type StudioProgressView = {
  kind: StudioProgressKind;
  active: boolean;
  title: string;
  percentage: number | null;
  indeterminate: boolean;
};

export function resolveStudioProgress(input: {
  engineState: EngineState;
  bootMessage: string;
  bootPhase?: string;
  generating: boolean;
  liveProgress: LiveProgress | null;
  logSummary?: string;
  companionBootstrapBusy?: boolean;
  companionBootstrapLabel?: string;
  companionBootstrapMessage?: string;
}): StudioProgressView {
  const idle: StudioProgressView = {
    kind: "idle",
    active: false,
    title: "",
    percentage: null,
    indeterminate: false,
  };

  if (input.companionBootstrapBusy) {
    const isPreparingTools =
      input.bootPhase === "preparing_tools" ||
      input.bootPhase === "preparing" ||
      input.bootPhase === "unknown";
    const dynamicMessage =
      input.companionBootstrapMessage?.trim() ||
      (isPreparingTools && input.bootMessage && !input.bootMessage.includes("stopped")
        ? input.bootMessage
        : null);

    return {
      kind: "prepare",
      active: true,
      title:
        dynamicMessage ||
        input.companionBootstrapLabel ||
        "Checking required assets…",
      percentage: null,
      indeterminate: true,
    };
  }

  if (input.generating) {
    const title = generationFooterStatus(
      true,
      input.liveProgress,
      input.logSummary ?? "",
    );
    const pct = input.liveProgress?.percentage ?? null;
    return {
      kind: "job",
      active: true,
      title: title || "Generating…",
      percentage: pct,
      indeterminate: pct == null || pct <= 0,
    };
  }

  if (input.engineState === "booting" || input.engineState === "restarting") {
    const title =
      input.bootMessage.trim() ||
      bootPhaseLabel(input.bootPhase) ||
      engineLabel(input.engineState, "");
    return {
      kind: "boot",
      active: true,
      title,
      percentage: null,
      indeterminate: true,
    };
  }

  return idle;
}

/** Hide the global status chip when the canvas progress strip already covers it. */
export function shouldHideGlobalStatusForProgress(input: {
  engineState: EngineState;
  generating: boolean;
  companionBootstrapBusy?: boolean;
}): boolean {
  return (
    Boolean(input.companionBootstrapBusy) ||
    input.generating ||
    input.engineState === "booting" ||
    input.engineState === "restarting"
  );
}
