/** GPU engine lifecycle exposed by the Tauri shell. */
export type EngineState =
  | "booting"
  | "ready"
  | "generating"
  | "failed"
  | "restarting";

export type EngineHealth = "alive" | "booting" | "dead" | "restarting" | "unknown";

const BOOT_PHASE_LABELS: Record<string, string> = {
  starting: "Starting GPU engine…",
  loading_settings: "Loading DreamForge settings and paths…",
  loading_pytorch: "Loading PyTorch and CUDA…",
  loading_pipeline: "Loading generation pipeline…",
  ready: "Engine ready",
};

const GEN_PHASE_LABELS: Record<string, string> = {
  idle: "Ready",
  loading_models: "Loading models…",
  preparing: "Preparing…",
  sampling: "Sampling…",
  finalizing: "Finalizing…",
  complete: "Complete",
};

export function bootPhaseLabel(phase: string | undefined, fallback: string): string {
  if (!phase) return fallback;
  return BOOT_PHASE_LABELS[phase] ?? fallback;
}

export function generationPhaseLabel(
  phase: string | undefined,
  message?: string,
): string {
  if (message?.trim()) return message.trim();
  if (!phase) return "Working…";
  return GEN_PHASE_LABELS[phase] ?? phase;
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
