import { useCallback, useEffect, useMemo, useState } from "react";
import type { GenerationSettings, ModelGalleryItem } from "../lib/tauri-api";
import { enforceCreativeTaskSettings } from "../lib/creativeTask";
import { defaultTemplateIdForMode } from "../lib/creativeTemplates";
import type { StudioMode } from "../lib/model-selection";
import {
  previewAutomation,
  type AutomationPreview,
} from "../lib/studioBridge";
import { invokeAutomation, cancelAutomation } from "../lib/tauri-api";

export type AutomationType =
  | "seed_batch"
  | "recipe_batch"
  | "prompt_lines"
  | "prompt_folder"
  | "input_folder";

export type AutomationRunResult = {
  ok: boolean;
  status?: string;
  completed?: number;
  total?: number;
  outputDir?: string | null;
  failedAt?: number;
};

type UseAutomationArgs = {
  settings: GenerationSettings;
  studioMode: StudioMode;
  modelGallery: ModelGalleryItem[];
  advancedMode?: boolean;
  vramGb?: number | null;
  mpsAvailable?: boolean | null;
  generating: boolean;
  onStatus: (message: string) => void;
  onRefreshOutputs: () => void;
  onBeforeRun?: () => Promise<boolean>;
};

export function useAutomation({
  settings,
  studioMode,
  modelGallery,
  advancedMode,
  vramGb,
  mpsAvailable,
  generating,
  onStatus,
  onRefreshOutputs,
  onBeforeRun,
}: UseAutomationArgs) {
  const [automationType, setAutomationType] =
    useState<AutomationType>("seed_batch");
  const [count, setCount] = useState(4);
  const [seedStart, setSeedStart] = useState("");
  const [seedStep, setSeedStep] = useState("1");
  const [inputPath, setInputPath] = useState("");
  const [outputDir, setOutputDir] = useState("");
  const [inputFolderMode, setInputFolderMode] = useState<StudioMode>("upscale");
  const [preview, setPreview] = useState<AutomationPreview | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [lastOutputDir, setLastOutputDir] = useState<string | null>(null);

  const baseSettings = useMemo(
    () =>
      enforceCreativeTaskSettings(settings, {
        studioMode,
        gallery: modelGallery,
        advancedMode,
        vramProfile: settings.vram_profile,
        vramGb: vramGb ?? null,
        mpsAvailable: mpsAvailable ?? null,
      }),
    [
      advancedMode,
      modelGallery,
      mpsAvailable,
      settings,
      studioMode,
      vramGb,
    ],
  );

  const buildSpec = useCallback((): Record<string, unknown> => {
    const templateId =
      baseSettings.template_id ?? defaultTemplateIdForMode(studioMode);
    const spec: Record<string, unknown> = {
      type: automationType,
      automation_type: automationType,
      base_settings: { ...baseSettings, image_number: 1 },
      template_id: templateId,
      studio_mode:
        automationType === "input_folder" ? inputFolderMode : studioMode,
    };
    if (automationType === "seed_batch" || automationType === "recipe_batch") {
      spec.count = count;
      if (seedStart.trim()) spec.seed_start = Number(seedStart);
      if (seedStep.trim()) spec.seed_step = Number(seedStep);
    }
    if (automationType === "recipe_batch") {
      spec.recipe_file = inputPath;
      spec.input_path = inputPath;
    }
    if (automationType === "prompt_lines") {
      spec.prompt_file = inputPath;
      spec.input_path = inputPath;
    }
    if (automationType === "prompt_folder") {
      spec.prompt_folder = inputPath;
      spec.input_path = inputPath;
    }
    if (automationType === "input_folder") {
      spec.input_folder = inputPath;
      spec.input_path = inputPath;
    }
    if (outputDir.trim()) {
      spec.output_dir = outputDir.trim();
    }
    return spec;
  }, [
    automationType,
    baseSettings,
    count,
    inputFolderMode,
    inputPath,
    outputDir,
    seedStart,
    seedStep,
    studioMode,
  ]);

  const refreshPreview = useCallback(async () => {
    setPreviewBusy(true);
    try {
      const result = await previewAutomation(buildSpec());
      setPreview(result);
    } catch {
      setPreview(null);
    } finally {
      setPreviewBusy(false);
    }
  }, [buildSpec]);

  useEffect(() => {
    void refreshPreview();
  }, [refreshPreview]);

  const runBatch = useCallback(async (): Promise<AutomationRunResult> => {
    if (generating) {
      return { ok: false, status: "busy" };
    }
    if (onBeforeRun && (await onBeforeRun())) {
      return { ok: false, status: "blocked" };
    }
    const spec = buildSpec();
    if (automationType !== "seed_batch" && !inputPath.trim()) {
      onStatus("Choose an input file or folder first");
      return { ok: false, status: "missing_input" };
    }
    const totalHint = preview?.job_count ?? count;
    onStatus(`Running automation (0/${totalHint})…`);
    try {
      const result = await invokeAutomation(spec);
      const outputPath = outputDir.trim() || null;
      if (outputPath) {
        setLastOutputDir(outputPath);
      }
      if (result.status === "started") {
        return {
          ok: true,
          status: result.status,
          outputDir: outputPath,
        };
      }
      onStatus(`Automation failed to start`);
      return {
        ok: false,
        status: result.status,
        outputDir: outputPath,
      };
    } catch (e) {
      onStatus(`Automation error: ${String(e)}`);
      return { ok: false, status: "error" };
    }
  }, [
    automationType,
    buildSpec,
    count,
    generating,
    inputPath,
    onBeforeRun,
    onRefreshOutputs,
    onStatus,
    outputDir,
    seedStart,
    seedStep,
    preview?.job_count,
  ]);

  const runCancel = useCallback(async () => {
    onStatus("Cancelling batch…");
    try {
      await cancelAutomation();
    } catch (e) {
      onStatus(`Cancel failed: ${String(e)}`);
    }
  }, [onStatus]);

  return {
    automationType,
    setAutomationType,
    count,
    seedStart,
    setSeedStart,
    seedStep,
    setSeedStep,
    setCount,
    inputPath,
    setInputPath,
    outputDir,
    setOutputDir,
    inputFolderMode,
    setInputFolderMode,
    preview,
    previewBusy,
    refreshPreview,
    runBatch,
    runCancel,
    lastOutputDir,
    canRun:
      !generating &&
      (automationType === "seed_batch" || Boolean(inputPath.trim())),
  };
}
