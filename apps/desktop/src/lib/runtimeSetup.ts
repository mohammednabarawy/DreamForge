import { invoke } from "@tauri-apps/api/core";
import { bridgeInvoke } from "./studioBridge";

export type ModelsSource = "managed" | "external";

export type RuntimeConfig = {
  version?: number;
  data_root: string;
  models_root: string;
  models_source: ModelsSource;
  setup_complete: boolean;
  setup_version?: number;
  comfy_root?: string;
};

export type RuntimePaths = {
  backend_root: string;
  data_root: string;
  models_root: string;
  outputs_root: string;
  comfy_root: string;
  config_path: string;
};

export type ModelsFolderValidation = {
  ok: boolean;
  path: string;
  warnings: string[];
  errors: string[];
  known_subdirs: string[];
};

export type RuntimeStatus = {
  ok: boolean;
  config: RuntimeConfig;
  paths: RuntimePaths;
  models_validation: ModelsFolderValidation;
  system: {
    platform: string;
    disk_free_gb: number;
    disk_total_gb: number;
    disk_ok: boolean;
    packaged: boolean;
  };
  needs_setup_wizard: boolean;
};

export type SetupProgress = {
  ok: boolean;
  steps: string[];
  completed_steps: string[];
  current_step: string;
  current_message?: string;
  log_lines?: string[];
  error: string;
  progress_pct: number;
  setup_complete: boolean;
  recipe_fingerprint?: string;
};

export type SetupGateStatus = {
  setup_complete: boolean;
  data_root: string;
  models_root: string;
  backend_root: string;
};

export async function getSetupGateStatus(): Promise<SetupGateStatus> {
  return invoke<SetupGateStatus>("get_setup_gate_status");
}

export async function getRuntimeStatus(): Promise<RuntimeStatus> {
  return bridgeInvoke<RuntimeStatus>("get_runtime_status", {});
}

export async function applyRuntimePreferences(params: {
  data_root?: string;
  models_root?: string;
  models_source: ModelsSource;
  setup_complete?: boolean;
}): Promise<{
  ok: boolean;
  config: RuntimeConfig;
  models_validation: ModelsFolderValidation;
  paths: Pick<RuntimePaths, "data_root" | "models_root" | "comfy_root">;
}> {
  return bridgeInvoke("apply_runtime_preferences", params);
}

export async function validateModelsFolder(
  path: string,
  create = false,
): Promise<ModelsFolderValidation> {
  return bridgeInvoke<ModelsFolderValidation>("validate_models_folder", {
    path,
    create,
  });
}

export async function getSetupProgress(): Promise<SetupProgress> {
  return bridgeInvoke<SetupProgress>("get_setup_progress", {});
}

export async function runBootstrapStep(step: string): Promise<{
  ok: boolean;
  error?: string;
  step?: string;
  progress?: SetupProgress;
}> {
  return bridgeInvoke("run_bootstrap_step", { step });
}

export async function resetSetupState(clearMarkers = false): Promise<{
  ok: boolean;
  cleared_markers?: string[];
  progress?: SetupProgress;
}> {
  return bridgeInvoke("reset_setup_state", { clear_markers: clearMarkers });
}

export async function repairInstallation(clearMarkers = false): Promise<{
  ok: boolean;
  error?: string;
  progress?: SetupProgress;
  setup_complete?: boolean;
}> {
  return bridgeInvoke("repair_installation", { clear_markers: clearMarkers });
}

export async function finalizeSetup(): Promise<{
  ok: boolean;
  setup_complete: boolean;
  config: RuntimeConfig;
}> {
  return bridgeInvoke("finalize_setup", {});
}

export async function startEngineAfterSetup(): Promise<void> {
  await invoke("start_engine_after_setup");
}

export const SETUP_STEP_LABELS: Record<string, string> = {
  prepare_directories: "Prepare folders",
  install_embedded_python: "Install python_embeded runtime",
  install_dreamforge_stack: "Install DreamForge Python stack",
  install_comfyui: "Install ComfyUI engine",
  install_comfy_deps: "Install ComfyUI Python dependencies",
  install_custom_nodes: "Install custom nodes",
  configure_comfy_models: "Configure model paths",
  verify_engine: "Verify engine",
};
