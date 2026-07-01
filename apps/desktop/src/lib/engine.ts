import { getEngineStatus } from "./tauri-api";

/** GPU engine lifecycle exposed by the Tauri shell. */
export type EngineState =
  | "booting"
  | "ready"
  | "generating"
  | "failed"
  | "restarting";

export type EngineHealth = "alive" | "booting" | "dead" | "restarting" | "unknown";

export const COMFY_NOT_READY_REASON =
  "ComfyUI server is still starting — wait for the engine to finish loading";

/** True when ComfyUI HTTP is up and asset prep is not holding the worker. */
export function isComfyServerReady(status: {
  ready?: boolean;
  comfy_ready?: boolean;
  boot_phase?: string;
}): boolean {
  if (!status.comfy_ready) return false;
  const phase = status.boot_phase ?? "";
  if (phase === "preparing_tools" || phase === "preparing") return false;
  return Boolean(status.ready);
}

/** Poll engine status until ComfyUI HTTP responds (or timeout). */
export async function waitForComfyServerReady(options?: {
  timeoutMs?: number;
  pollMs?: number;
}): Promise<boolean> {
  const timeoutMs = options?.timeoutMs ?? 120_000;
  const pollMs = options?.pollMs ?? 500;
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const status = await getEngineStatus();
      if (isComfyServerReady(status)) return true;
    } catch {
      /* status probe not ready yet */
    }
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
  return false;
}

const BOOT_PHASE_LABELS: Record<string, string> = {
  starting: "Starting GPU engine…",
  starting_comfy: "Starting managed ComfyUI server…",
  loading_settings: "Loading DreamForge settings and paths…",
  loading_pytorch: "Loading PyTorch…",
  loading_pipeline: "Loading generation pipeline…",
  booting: "Booting GPU engine…",
  preparing_tools: "Checking required assets…",
  preparing: "Preparing…",
  ready: "ComfyUI ready",
};

const GEN_PHASE_LABELS: Record<string, string> = {
  idle: "Ready",
  loading_models: "Loading models…",
  preparing: "Preparing…",
  sampling: "Sampling…",
  finalizing: "Finalizing…",
  complete: "Complete",
};

export function bootPhaseLabel(phase: string | undefined, message?: string): string {
  const trimmed = message?.trim();
  if (trimmed) return trimmed;
  if (phase && BOOT_PHASE_LABELS[phase]) return BOOT_PHASE_LABELS[phase];
  return "Loading…";
}

export function generationPhaseLabel(
  phase: string | undefined,
  message?: string,
): string {
  if (message?.trim()) return message.trim();
  if (!phase) return "Working…";
  return GEN_PHASE_LABELS[phase] ?? phase;
}

export type EngineStatusTone = "ready" | "busy" | "warn" | "error";

/** Human-readable engine chip for the title bar. */
export function engineStatusDisplay(options: {
  engineState: EngineState;
  bootMessage?: string;
  workerReady?: boolean;
  restarting?: boolean;
  gpuName?: string | null;
  vramGb?: number | null;
  mpsAvailable?: boolean | null;
}): { label: string; title: string; tone: EngineStatusTone } {
  const boot = options.bootMessage?.trim() ?? "";
  const { engineState, workerReady, gpuName, vramGb, mpsAvailable } = options;

  if (engineState === "ready" && gpuName) {
    const detail = mpsAvailable
      ? `${gpuName} · unified memory`
      : vramGb != null
        ? `${gpuName} · ${vramGb} GB VRAM`
        : gpuName;
    return { label: "Engine ready", title: detail, tone: "ready" };
  }
  if (engineState === "generating") {
    return { label: "Rendering", title: "GPU generation in progress", tone: "busy" };
  }
  if (engineState === "failed") {
    return {
      label: "Engine failed",
      title: boot || "Restart GPU engine from the title bar",
      tone: "error",
    };
  }
  if (engineState === "restarting" || options.restarting) {
    return {
      label: "Restarting…",
      title: boot || "Restarting GPU engine and ComfyUI",
      tone: "warn",
    };
  }
  if (!workerReady) {
    const label = bootPhaseLabel(undefined, boot);
    return {
      label: label.length > 36 ? `${label.slice(0, 33)}…` : label,
      title: boot || "First launch can take 20–90 seconds",
      tone: "warn",
    };
  }
  return {
    label: engineLabel(engineState, boot),
    title: boot,
    tone: engineState === "ready" ? "ready" : "warn",
  };
}

/** Inline title-bar restart control (failed, stuck booting, or restart in progress). */
export function engineRestartControlState(options: {
  engineState: EngineState;
  workerReady: boolean;
  restarting?: boolean;
}): { visible: boolean; disabled: boolean } {
  if (options.engineState === "generating") {
    return { visible: false, disabled: false };
  }
  if (options.restarting || options.engineState === "restarting") {
    return { visible: true, disabled: true };
  }
  if (options.engineState === "failed") {
    return { visible: true, disabled: false };
  }
  if (!options.workerReady && options.engineState !== "ready") {
    return { visible: true, disabled: false };
  }
  return { visible: false, disabled: false };
}

/** @deprecated Use engineRestartControlState */
export function showEngineRestartControl(options: {
  engineState: EngineState;
  workerReady: boolean;
  restarting?: boolean;
}): boolean {
  return engineRestartControlState(options).visible;
}

export function engineLabel(state: EngineState, bootMessage: string): string {
  switch (state) {
    case "booting":
      return bootMessage || "Loading GPU engine…";
    case "ready":
      return "Engine ready";
    case "generating":
      return "Rendering on GPU";
    case "failed":
      return "Engine failed";
    case "restarting":
      return "Restarting GPU engine…";
    default:
      return bootMessage;
  }
}
