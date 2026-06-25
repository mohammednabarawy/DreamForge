import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  bootPhaseLabel,
  COMFY_NOT_READY_REASON,
  engineLabel,
  isComfyServerReady,
  type EngineState,
} from "../lib/engine";
import {
  mergeLiveProgress,
  type LiveProgress,
} from "../lib/generationProgressUi";
import { studioPrepareFallbackLabel } from "../lib/loadingMessages";
import {
  describeError,
  describeWarning,
  plainErrorLine,
  shortErrorLine,
  type FriendlyError,
} from "../lib/errors";
import { parseInventoryResponse } from "../lib/inventory";
import {
  hydrateInventoryFromSnapshot,
  readModelLibrarySnapshot,
  writeModelLibrarySnapshot,
} from "../lib/modelLibraryCache";
import {
  findGalleryModel,
  modelBasename,
  modelMatches,
  resolveActiveModel,
  selectIdeogram4GalleryModel,
  type StudioMode,
  type StyleRecipe,
} from "../lib/model-selection";
import { isAdvancedMode, isSimpleExperience, type UiExperience } from "../lib/experienceUi";
import { ideogram4SettingsDefaults, looksLikeIdeogramJson } from "../lib/ideogram4Ui";
import { resolveAspectPresets } from "../lib/aspectPresets";
import { enhancePrefsFromAppConfig, shouldAutoEnhanceOnGenerate } from "../lib/promptEnhance";
import { inpaintModelWarning } from "../lib/inpaintModel";
import { upscaleModelWarning } from "../lib/upscaleModel";
import { enforceCreativeTaskSettings, enforceCreativeTaskSettingsRemote, planStudioModeSwitch } from "../lib/creativeTask";
import { defaultTemplateIdForMode } from "../lib/creativeTemplates";
import { useCreativeTask } from "./useCreativeTask";
import {
  buildEditRoutingPatch,
  editModelWarning,
  isQwenEditModel,
} from "../lib/editModel";
import { excerptPrompt, HISTORY_PAGE_SIZE } from "../lib/historyUtils";
import { settingsFromManifestBundle } from "../lib/historyActions";
import {
  DEFAULT_SESSION_ID,
  groupOutputsBySession,
  mergeSessionList,
  outputPathForSession,
  sanitizeSessionId,
  uniqueSessionId,
  type OutputSession,
  type SessionMeta,
} from "../lib/sessions";
import {
  loadActiveSessionId,
  loadLastSelectedManifest,
  loadSessionRegistry,
  purgeHistoryMetadataForManifest,
  saveActiveSessionId,
  saveLastSelectedManifest,
  saveSessionRegistry,
} from "../lib/historyStorage";
import {
  cancelGeneration,
  checkModelDependencies,
  dryRun,
  GenerationSettings,
  getEngineStatus,
  getGenerationBundle,
  getGenerationProgress,
  getInventory,
  getLoraGallery,
  getModelGallery,
  getUiDefaults,
  refreshModelLibraryCache,
  invokeGeneration,
  deleteOutput,
  deleteOutputImage,
  deleteSession,
  listOutputsPage,
  revealPathInExplorer,
  searchOutputsPage,
  listStyles,
  notifyDone,
  onGenerationFinished,
  onGenerationPreview,
  onGenerationStarted,
  onOutputsChanged,
  onWorkerReady,
  onWorkerStatus,
  onWorkerBootProgress,
  onWorkerFailed,
  onWorkerDead,
  onEngineHealthStatus,
  onGenerationProgress,
  onGenerationBusy,
  onGenerationWarning,
  OutputItem,
  readJobLog,
  readLivePreview,
  readWorkerLog,
  restartGpuWorker,
  syncDesktopVramProfile,
  freeWorkerVram,
  resolveModelProfile,
  type LoraGalleryItem,
  type InventoryPayload,
  type ModelGalleryItem,
  type ModelDependencyItem,
  type UiDefaults,
  type RepairAction,
} from "../lib/tauri-api";
import { clearThumbnailCache } from "../lib/thumbnail-cache";
import {
  cleanupCanvasPreviewUrls,
  finalPreviewUrlForPath,
  normalizePreviewPath,
  resolveCanvasPreviewUrl,
} from "../lib/preview-display";
import { prepareGenerationFromAgentPrompt } from "../lib/parseAgentPrompt";
import { qwenEdit2511LightningPatch } from "../lib/qwenEditDefaults";
import { computeGenerateReadiness } from "../lib/generationReadiness";
import {
  lowerVramProfile,
  resolveVramProfile,
  type VramProfile,
} from "../lib/vramProfiles";
import { useCompanionDownload } from "./useCompanionDownload";
import {
  DEFAULT_MAX_LORA_STACK,
  hasLora,
  parseLoraList,
  removeLora,
  upsertLora,
} from "../lib/loraStack";
import {
  aggregateLoraKeywords,
  checkStudioResources,
  checkImagePromptResources,
  clearUserStyleProfile,
  downloadCompanionEntries,
  ensureCreativeTaskReady,
  exportUserStyleProfile,
  getUserStyleProfile,
  getAppConfig,
  getLoraInfo,
  getStudioSettings,
  enhanceStudioPrompt,
  listAgentProviders,
  planAgentInstruction,
  runAutomation,
  saveAppConfig,
  saveStudioSettings,
  saveUserStyleProfile,
  testAgentProvider,
  type AgentPlanSnapshot,
  type AgentTranscriptMessage,
  type AgentProviderPreset,
  type AgentProviderTestResult,
  type DreamForgeAppConfig,
  type DreamForgeAppConfigPatch,
  type StudioSettings,
  type UserStyleProfile,
  type WorkflowReadiness,
} from "../lib/studioBridge";
import {
  appendExtraReferencePath,
  buildClearReferenceImagePatch,
  buildGenerateIdentityReferencePatch,
  buildReferenceImagePatch,
  defaultReferenceEditStrength,
  referenceStatusLabel,
  removeExtraReferenceAt,
  resolveGenerationImagePaths,
  resolveReferenceImagePath,
  sanitizeEditFamilySettings,
  type ReferenceImageMode,
} from "../lib/referenceImage";
import {
  isGenerateReferenceWorkflow,
  resolveEffectiveRoute,
  sanitizeSettingsForStudioMode,
} from "../lib/routeResolution";
import { buildEasyCreateReferencePatch } from "../lib/easyModeRouting";
import { applyExplicitReferenceRoleParams } from "../lib/generateReferenceParams";
import { applyUpscalePresetAtSubmit } from "../lib/upscalePresets";
import {
  applyReferencesAtSubmit,
  normalizeReferenceSettings,
  appendReferenceSlot,
  coerceReferenceSlots,
} from "../lib/referenceSlots";
import { applyAutoEnhanceAtSubmit, patchForEnhanceTarget, type EnhanceTarget } from "../lib/autoEnhance";
import { applyIdentityAtSubmit } from "../lib/identityPreserve";
import {
  describeImageToPrompt,
  resolveDescribeImagePath,
} from "../lib/describeImage";
import { importImageMetadata, mergeMetadataPatch } from "../lib/imageMetadata";
import {
  applyVaryAmountAtSubmit,
  buildVarySettingsPatch,
  type VaryAmount,
} from "../lib/varyImage";
import { applyHiDreamPerformanceAtSubmit } from "../lib/hidreamPerformance";
import {
  buildPlanSnapshotFromDryRun,
  canRunApprovedPlan,
  resolvePlannedSettings,
  computePlanSettingsSnapshot,
  editFamilyPlanState,
  planBlockedByLocalInputsOnly,
  shouldSurfaceWorkflowPlan,
} from "../lib/workflowPlanActions";
import { isEditFamilyMode } from "../lib/generationReadiness";
import {
  customNodeItemsFromActions,
} from "../lib/companionAssets";

function companionItemsFromActions(actions?: RepairAction[]) {
  return (
    actions
      ?.filter((action) => action.action === "download_model_companions")
      .flatMap((action) =>
        Array.isArray(action.missing)
          ? (action.missing as ModelDependencyItem[])
          : [],
      ) ?? []
  );
}

function dependencyKey(item: ModelDependencyItem): string {
  return `${item.id ?? ""}|${item.url ?? ""}|${item.filename ?? ""}|${item.relative ?? ""}|${item.expected_path ?? ""}`;
}

function mergeDependencyItems(...groups: Array<ModelDependencyItem[] | undefined>): ModelDependencyItem[] {
  const merged: ModelDependencyItem[] = [];
  const keys = new Set<string>();
  for (const group of groups) {
    for (const item of group ?? []) {
      const key = dependencyKey(item);
      if (keys.has(key)) continue;
      keys.add(key);
      merged.push(item);
    }
  }
  return merged;
}

function recordValue(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value ? (value as Record<string, unknown>) : undefined;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)) : [];
}

function actionList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    : [];
}

function missingDependencyLabels(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) =>
    typeof item === "object" && item
      ? String(
          (item as Record<string, unknown>).name ??
            (item as Record<string, unknown>).id ??
            JSON.stringify(item),
        )
      : String(item),
  );
}

function uniqueStrings(items: string[]): string[] {
  return [...new Set(items.filter(Boolean))];
}

function safeText(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function cleanHtmlText(value: unknown): string {
  return safeText(value).replace(/<[^>]+>/g, "");
}

function dryRunReadinessSnapshot(
  planPayload: Record<string, unknown>,
  workflowBlueprint: Record<string, unknown>,
): WorkflowReadiness | undefined {
  const blueprintReadiness = recordValue(workflowBlueprint.readiness);
  const hasReady = typeof planPayload.ready === "boolean" || typeof blueprintReadiness?.ready === "boolean";
  const readiness: WorkflowReadiness = {
    ready:
      typeof planPayload.ready === "boolean"
        ? planPayload.ready
        : typeof blueprintReadiness?.ready === "boolean"
          ? blueprintReadiness.ready
          : undefined,
    missing_inputs: stringList(blueprintReadiness?.missing_inputs),
    missing_models: uniqueStrings([
      ...stringList(blueprintReadiness?.missing_models),
      ...missingDependencyLabels(planPayload.missing_dependencies),
    ]),
    missing_node_packs: stringList(blueprintReadiness?.missing_node_packs),
    optional_nodes: stringList(blueprintReadiness?.optional_nodes),
    recommended_actions: [
      ...actionList(blueprintReadiness?.recommended_actions),
      ...actionList(planPayload.recommended_actions),
    ],
    warnings: uniqueStrings([
      ...stringList(blueprintReadiness?.warnings),
      ...stringList(planPayload.setup_warnings),
    ]),
  };
  const hasDetails =
    hasReady ||
    Boolean(
      readiness.missing_inputs?.length ||
        readiness.missing_models?.length ||
        readiness.missing_node_packs?.length ||
        readiness.optional_nodes?.length ||
        readiness.recommended_actions?.length ||
        readiness.warnings?.length,
    );
  return hasDetails ? readiness : undefined;
}

export function useDreamForge() {
  const [outputs, setOutputs] = useState<OutputItem[]>([]);
  const [outputsTotal, setOutputsTotal] = useState(0);
  const [outputsHasMore, setOutputsHasMore] = useState(false);
  const [outputsLoading, setOutputsLoading] = useState(false);
  const [outputSearch, setOutputSearch] = useState("");
  const [historyScrollToken, setHistoryScrollToken] = useState(0);
  const outputSearchRef = useRef(outputSearch);
  outputSearchRef.current = outputSearch;
  const [inventory, setInventory] = useState(() => {
    const hydrated = hydrateInventoryFromSnapshot(readModelLibrarySnapshot());
    return hydrated ?? parseInventoryResponse({ categories: {}, styles: [], style_groups: [] });
  });
  const [selected, setSelected] = useState<OutputItem | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [liveProgress, setLiveProgress] = useState<LiveProgress | null>(null);
  const [generating, setGenerating] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [lastJobId, setLastJobId] = useState<string | null>(null);
  const [generationLog, setGenerationLog] = useState<string>("");
  const [agentPlan, setAgentPlan] = useState<AgentPlanSnapshot | null>(null);
  const [agentTranscript, setAgentTranscript] = useState<AgentTranscriptMessage[]>([]);
  const [planRunBusy, setPlanRunBusy] = useState(false);
  const [enhancePromptBusy, setEnhancePromptBusy] = useState(false);
  const [describeImageBusy, setDescribeImageBusy] = useState(false);
  const agentPlanRef = useRef(agentPlan);
  agentPlanRef.current = agentPlan;
  const [engineState, setEngineState] = useState<EngineState>("booting");
  const engineStateRef = useRef(engineState);
  engineStateRef.current = engineState;
  const [status, setStatus] = useState<string>("Starting GPU engine…");
  const [workerReady, setWorkerReady] = useState(false);
  const [workerLogTail, setWorkerLogTail] = useState("");
  const [restarting, setRestarting] = useState(false);
  const [uiDefaults, setUiDefaults] = useState<UiDefaults | null>(null);
  const [modelGalleryAll, setModelGalleryAll] = useState<ModelGalleryItem[]>(
    () => readModelLibrarySnapshot()?.modelGallery ?? [],
  );
  const [loraGalleryAll, setLoraGalleryAll] = useState<LoraGalleryItem[]>(
    () => readModelLibrarySnapshot()?.loraGallery ?? [],
  );
  const studioCatalogLoadedRef = useRef(false);
  const userPickedModelRef = useRef(false);
  const userPickedLorasRef = useRef(false);
  const userPickedStyleRef = useRef(false);
  const [styleRecipes, setStyleRecipes] = useState<StyleRecipe[]>([]);
  const [modelFilter, setModelFilter] = useState("");
  const [loraFilter, setLoraFilter] = useState("");
  const [profileHints, setProfileHints] = useState<string[]>([]);
  const [galleryLoading, setGalleryLoading] = useState(false);
  const [studioSettings, setStudioSettings] = useState<StudioSettings | null>(
    null,
  );
  const [appConfig, setAppConfig] = useState<DreamForgeAppConfig | null>(null);
  const uiExperience = (appConfig?.ui.experience ?? "pro") as UiExperience;
  const advancedMode = isAdvancedMode(uiExperience);
  const [agentProviders, setAgentProviders] = useState<AgentProviderPreset[]>(
    [],
  );
  const [agentProviderTest, setAgentProviderTest] =
    useState<AgentProviderTestResult | null>(null);
  const [agentProviderBusy, setAgentProviderBusy] = useState(false);
  const [userStyleProfile, setUserStyleProfile] = useState<UserStyleProfile | null>(
    null,
  );
  const [userStyleProfilePath, setUserStyleProfilePath] = useState<string>("");
  const [agentPlannedMode, setAgentPlannedMode] = useState<StudioMode | null>(
    null,
  );
  const [imageNumberMax, setImageNumberMax] = useState(8);
  const [inpaintMaskOpen, setInpaintMaskOpen] = useState(false);
  const [inpaintMaskSyncing, setInpaintMaskSyncing] = useState(false);
  const [inpaintCanvasFocus, setInpaintCanvasFocus] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState(() =>
    loadActiveSessionId(),
  );
  const [sessionRegistry, setSessionRegistry] = useState<SessionMeta[]>(() =>
    loadSessionRegistry(),
  );
  const activeSessionIdRef = useRef(activeSessionId);
  activeSessionIdRef.current = activeSessionId;
  const [bootMessage, setBootMessage] = useState<string>(
    "Starting ComfyUI engine…",
  );
  const [bootPhase, setBootPhase] = useState<string>("starting");
  const [gpuName, setGpuName] = useState<string | null>(null);
  const [vramGb, setVramGb] = useState<number | null>(null);
  const [mpsAvailable, setMpsAvailable] = useState<boolean | null>(null);
  const [lastError, setLastError] = useState<FriendlyError | null>(null);
  const [warnings, setWarnings] = useState<FriendlyError[]>([]);
  const [modelDependencies, setModelDependencies] = useState<{
    missing: ModelDependencyItem[];
    ready: boolean;
  }>({ missing: [], ready: true });
  const [studioResources, setStudioResources] = useState<{
    missing: ModelDependencyItem[];
    ready: boolean;
  }>({ missing: [], ready: true });
  const [imagePromptResources, setImagePromptResources] = useState<{
    missing: ModelDependencyItem[];
    ready: boolean;
  }>({ missing: [], ready: true });
  const [companionBootstrapBusy, setCompanionBootstrapBusy] = useState(false);
  const [companionBootstrapMessage, setCompanionBootstrapMessage] = useState("");
  const companionBootstrapBusyRef = useRef(false);
  companionBootstrapBusyRef.current = companionBootstrapBusy;
  const verifyCompanionDownloadsRef = useRef<
    () => Promise<{ ready: boolean; stillMissing: ModelDependencyItem[] }>
  >(async () => ({ ready: true, stillMissing: [] }));
  const companionDownload = useCompanionDownload({
    verifyReady: () => verifyCompanionDownloadsRef.current(),
    requireComfyReady: () => workerReadyRef.current,
  });
  const {
    start: startCompanionDownload,
    open: companionDownloadOpen,
    busy: companionDownloadBusy,
    phase: companionDownloadPhase,
  } = companionDownload;

  const refreshWorkerLog = useCallback(async () => {
    try {
      const { tail } = await readWorkerLog();
      if (tail) setWorkerLogTail(tail);
    } catch {
      /* log not available yet */
    }
  }, []);

  const generatingRef = useRef(false);
  const workerReadyRef = useRef(false);
  type MissingDepsResolveOptions = {
    studioMode?: StudioMode;
    studioMissing?: ModelDependencyItem[];
  };
  const promptMissingCompanionsDownloadRef = useRef<
    ((opts?: MissingDepsResolveOptions) => Promise<boolean>) | null
  >(null);
  const pendingCompanionPrepRef = useRef<MissingDepsResolveOptions | null>(null);
  const assetPrepReadyRef = useRef<{ key: string; at: number } | null>(null);
  const ASSET_PREP_CACHE_MS = 120_000;
  const vramProfileAutoAppliedRef = useRef(false);
  const vramRestartPendingRef = useRef(false);
  const effectiveVramProfileRef = useRef<VramProfile>("auto");
  const runRestartEngineRef = useRef<(() => Promise<void>) | null>(null);
  const setStudioModeRef = useRef<(mode: StudioMode) => Promise<void>>(
    async () => {},
  );
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const logPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastPreviewSigRef = useRef<string>("");
  const lastPreviewEventAtRef = useRef<number>(0);
  const previewUrlRef = useRef<string | null>(null);
  const canvasPreviewPathRef = useRef<string>("");
  const lastSelectedKeyRef = useRef<string>("");
  const previewGenerationRef = useRef(0);
  const finalPreviewAppliedRef = useRef(false);

  const previewSignature = useCallback((url: string) => {
    if (!url.startsWith("data:")) return url;
    return `${url.length}:${url.slice(-256)}`;
  }, []);

  const setCanvasPreview = useCallback(
    (
      url: string | null,
      path?: string,
      opts?: { force?: boolean },
    ) => {
      if (url && url === previewUrlRef.current && !opts?.force) return;
      previewUrlRef.current = url;
      if (path) {
        canvasPreviewPathRef.current = normalizePreviewPath(path);
      } else if (!url) {
        canvasPreviewPathRef.current = "";
      }
      setPreviewUrl(url);
    },
    [],
  );

  const setCanvasPreviewFromPath = useCallback(
    async (path: string, opts?: { force?: boolean }) => {
      const norm = normalizePreviewPath(path);
      if (
        !opts?.force &&
        norm &&
        norm === canvasPreviewPathRef.current &&
        previewUrlRef.current
      ) {
        return;
      }
      const url = await finalPreviewUrlForPath(path);
      if (url) setCanvasPreview(url, path, { force: opts?.force });
    },
    [setCanvasPreview],
  );

  const applyLiveProgress = useCallback(
    (next: Parameters<typeof mergeLiveProgress>[1]) => {
      setLiveProgress((prev) => mergeLiveProgress(prev, next));
    },
    [],
  );

  const applyPreviewPayload = useCallback(
    async (p: {
      job_id?: string;
      data_url?: string;
      preview_path?: string;
      asset_url?: string;
      has_preview?: boolean;
      live?: boolean;
      final?: boolean;
      final_preview?: boolean;
      percentage?: number;
      title?: string;
    }) => {
      const isFinal = Boolean(p.final ?? p.final_preview);
      const previewJobId = (p.job_id ?? "").trim();
      const activeJob =
        previewJobId &&
        generatingRef.current &&
        (jobId === previewJobId || lastJobId === previewJobId);
      if (finalPreviewAppliedRef.current && !isFinal) {
        return;
      }
      if (!generatingRef.current && !isFinal && !activeJob) {
        return;
      }
      const generation = previewGenerationRef.current;
      if (p.percentage != null || p.title) {
        applyLiveProgress({
          percentage: p.percentage,
          title: p.title,
          phase: "sampling",
        });
      }
      const url = await resolveCanvasPreviewUrl({
        data_url: p.data_url,
        preview_path: p.preview_path,
        asset_url: p.asset_url,
        live: !isFinal,
        final: isFinal,
      });
      if (generation !== previewGenerationRef.current) {
        return;
      }
      if (url) {
        if (isFinal) {
          finalPreviewAppliedRef.current = true;
        } else if (finalPreviewAppliedRef.current) {
          return;
        }
        lastPreviewSigRef.current = previewSignature(url);
        lastPreviewEventAtRef.current = Date.now();
        setCanvasPreview(url, p.preview_path, { force: isFinal });
        return;
      }
      if (p.has_preview && !isFinal && generatingRef.current) {
        try {
          const r = await readLivePreview();
          if (generation !== previewGenerationRef.current) {
            return;
          }
          if (finalPreviewAppliedRef.current) {
            return;
          }
          const fallback = await resolveCanvasPreviewUrl({
            data_url: r.data_url,
            preview_path: r.path,
            live: true,
          });
          if (generation !== previewGenerationRef.current) {
            return;
          }
          if (fallback && !finalPreviewAppliedRef.current) {
            lastPreviewSigRef.current = previewSignature(fallback);
            lastPreviewEventAtRef.current = Date.now();
            setCanvasPreview(fallback, r.path);
          }
        } catch {
          /* preview file not ready yet */
        }
      }
    },
    [applyLiveProgress, setCanvasPreview, jobId, lastJobId, previewSignature],
  );

  const applyFinalCanvasPreview = useCallback(
    async (payload: {
      data_url?: string;
      preview_path?: string;
      asset_url?: string;
      result?: { images?: Array<{ path: string }> };
    }) => {
      finalPreviewAppliedRef.current = true;
      const paths =
        payload.result?.images?.map((i) => i.path).filter(Boolean) ?? [];
      const primary = paths[0] ?? payload.preview_path;
      const url = await resolveCanvasPreviewUrl({
        data_url: payload.data_url,
        preview_path: payload.preview_path,
        asset_url: payload.asset_url,
        final: true,
      });
      if (url) {
        setCanvasPreview(url, payload.preview_path || primary, { force: true });
        return;
      }
      if (primary) {
        await setCanvasPreviewFromPath(primary, { force: true });
      }
    },
    [setCanvasPreview, setCanvasPreviewFromPath],
  );

  const [settings, setSettings] = useState<GenerationSettings>({
    prompt: "Premium product hero shot, studio lighting, clean negative space",
    model: "",
    vram_profile: "auto",
    aspect_ratio: "768x768",
    style: "none",
    styles: [],
    image_number: 1,
    negative_prompt: "",
    steps: 20,
    cfg_scale: 3.5,
    output: outputPathForSession(loadActiveSessionId()),
    ...ideogram4SettingsDefaults(),
  });
  const settingsRef = useRef(settings);
  settingsRef.current = settings;

  const sessions = useMemo(
    () =>
      mergeSessionList(
        groupOutputsBySession(outputs),
        sessionRegistry,
        activeSessionId,
      ),
    [outputs, sessionRegistry, activeSessionId],
  );

  const outputsLengthRef = useRef(0);
  outputsLengthRef.current = outputs.length;

  const refreshOutputs = useCallback(
    async (opts?: {
      keepSelection?: boolean;
      selectNewest?: boolean;
      offset?: number;
      append?: boolean;
    }) => {
      setOutputsLoading(true);
      try {
        const q = outputSearchRef.current.trim();
        const offset = opts?.append
          ? outputsLengthRef.current
          : (opts?.offset ?? 0);
        const page = q
          ? await searchOutputsPage(q, {
              limit: HISTORY_PAGE_SIZE,
              offset,
            })
          : await listOutputsPage({
              limit: HISTORY_PAGE_SIZE,
              offset,
            });

        if (opts?.append) {
          setOutputs((prev) => {
            const seen = new Set(prev.map((i) => i.manifest_path));
            const merged = [...prev];
            for (const item of page.items) {
              if (!seen.has(item.manifest_path)) {
                merged.push(item);
                seen.add(item.manifest_path);
              }
            }
            return merged;
          });
        } else {
          setOutputs(page.items);
        }
        setOutputsTotal(page.total);
        setOutputsHasMore(page.hasMore);

        if (opts?.selectNewest && page.items[0]) {
          setSelected(page.items[0]);
          saveLastSelectedManifest(page.items[0].manifest_path);
          setHistoryScrollToken((t) => t + 1);
        } else if (!opts?.keepSelection) {
          const savedManifest = loadLastSelectedManifest();
          const restored = savedManifest
            ? page.items.find((i) => i.manifest_path === savedManifest)
            : null;
          setSelected((prev) => {
            if (restored) return restored;
            if (prev) {
              return (
                page.items.find(
                  (i) => i.manifest_path === prev.manifest_path,
                ) ?? prev
              );
            }
            return page.items[0] ?? null;
          });
        }
      } catch (e) {
        setStatus(`Outputs error: ${String(e)}`);
      } finally {
        setOutputsLoading(false);
      }
    },
    [],
  );

  const loadMoreOutputs = useCallback(() => {
    if (!outputsHasMore || outputsLoading) return;
    void refreshOutputs({ append: true, keepSelection: true });
  }, [outputsHasMore, outputsLoading, refreshOutputs]);

  const debouncedRefreshWhileGenerating = useCallback(() => {
    if (!generatingRef.current) {
      void refreshOutputs();
      return;
    }
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    refreshTimerRef.current = setTimeout(() => {
      void refreshOutputs({ keepSelection: true });
    }, 1200);
  }, [refreshOutputs]);

  const applyModelProfile = useCallback(
    async (item: ModelGalleryItem, performanceOverride?: string) => {
      try {
        const res = await resolveModelProfile({
          caption: item.caption,
          category: item.category,
          relative_path: item.relative_path,
          performance: performanceOverride ?? settings.performance,
          lock_family_defaults: true,
        });
        const profile = res.profile;
        const hints = (profile.hints ?? []).map(cleanHtmlText).filter(Boolean);
        setProfileHints(hints);

        const patch: Partial<GenerationSettings> = {
          model: profile.engine_name,
        };
        if (profile.apply_performance && profile.performance_selection) {
          patch.performance = profile.performance_selection;
        }
        if (profile.clear_styles) patch.styles = [];
        if (profile.clear_negative) patch.negative_prompt = "";
        if (profile.custom_sampling) {
          patch.steps = profile.custom_sampling.custom_steps;
          patch.cfg_scale = profile.custom_sampling.cfg;
          patch.sampler = profile.custom_sampling.sampler_name;
          patch.scheduler = profile.custom_sampling.scheduler;
        }
        if (profile.settings_patch) {
          Object.assign(patch, profile.settings_patch);
        }
        if ((item.family ?? "").toLowerCase() === "ideogram4") {
          Object.assign(patch, ideogram4SettingsDefaults());
        }
        setSettings((s) => ({ ...s, ...patch }));
        return profile;
      } catch {
        return null;
      }
    },
    [settings.performance],
  );

  const refreshUserStyleProfile = useCallback(async () => {
    try {
      const res = await getUserStyleProfile();
      setUserStyleProfile(res.profile);
      setUserStyleProfilePath(res.path ?? "");
      return res.profile;
    } catch {
      return null;
    }
  }, []);

  const setUserStyleMemoryEnabled = useCallback(async (enabled: boolean) => {
    try {
      const res = await saveUserStyleProfile({ enabled });
      setUserStyleProfile(res.profile);
      setStatus(enabled ? "Local style memory enabled" : "Local style memory disabled");
    } catch (e) {
      setStatus(`Style memory update failed: ${String(e)}`);
    }
  }, []);

  const clearUserStyleMemory = useCallback(async () => {
    try {
      const res = await clearUserStyleProfile();
      setUserStyleProfile(res.profile);
      setStatus("Local style memory cleared");
    } catch (e) {
      setStatus(`Clear memory failed: ${String(e)}`);
    }
  }, []);

  const exportUserStyleMemory = useCallback(async () => {
    try {
      const res = await exportUserStyleProfile();
      setUserStyleProfile(res.profile);
      setUserStyleProfilePath(res.path ?? "");
      const blob = new Blob([JSON.stringify(res.profile, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "dreamforge-user-style-profile.json";
      anchor.click();
      URL.revokeObjectURL(url);
      setStatus(`Exported style memory (${res.path})`);
    } catch (e) {
      setStatus(`Export memory failed: ${String(e)}`);
    }
  }, []);

  const loadStudioCatalog = useCallback(async (force = false) => {
    if (studioCatalogLoadedRef.current && !force) {
      return;
    }
    setGalleryLoading(true);
    try {
      if (force) {
        clearThumbnailCache();
        await refreshModelLibraryCache().catch(() => {});
      }
      const fetchOpts = { forceRefresh: force };
      const [
        models,
        loras,
        raw,
        defaults,
        styleIdRes,
        studio,
        app,
        providers,
        styleProfile,
      ] = await Promise.all([
        getModelGallery("", fetchOpts),
        getLoraGallery("", fetchOpts),
        getInventory(fetchOpts),
        getUiDefaults(),
        listStyles(),
        getStudioSettings().catch(() => null),
        getAppConfig().catch(() => null),
        listAgentProviders().catch(() => []),
        getUserStyleProfile().catch(() => null),
      ]);
      const recipes = (styleIdRes.styles ?? []) as StyleRecipe[];
      setStyleRecipes(recipes);
      const inv = parseInventoryResponse(raw as Record<string, unknown>);
      setModelGalleryAll(models);
      setLoraGalleryAll(loras);
      setInventory(inv);
      const rawInventory = raw as InventoryPayload & { models_root?: string };
      writeModelLibrarySnapshot({
        savedAt: Date.now(),
        modelsRoot: rawInventory.models_root,
        modelGallery: models,
        loraGallery: loras,
        inventory: {
          categories: rawInventory.categories ?? {},
          styles: inv.styles,
          style_groups: inv.styleGroups,
          presets: inv.presets,
        },
      });
      setUiDefaults(defaults);
      let profileModel = "";
      setSettings((prev) => {
        const nextModel = resolveActiveModel(
          models,
          prev.model,
          prev.style,
          recipes,
          userPickedModelRef.current,
        );
        profileModel = nextModel;
        if (!nextModel || nextModel === prev.model) return prev;
        return { ...prev, model: nextModel };
      });
      if (profileModel) {
        const item = findGalleryModel(models, profileModel);
        if (item) void applyModelProfile(item);
      }
      if (studio) {
        setStudioSettings(studio);
        setImageNumberMax(
          Math.min(50, Math.max(1, studio.image_number_max ?? 8)),
        );
        setSettings((prev) => ({
          ...prev,
          clip_skip: studio.clip_skip ?? prev.clip_skip,
          auto_negative_prompt:
            studio.auto_negative_prompt ?? prev.auto_negative_prompt,
        }));
      }
      if (app) setAppConfig(app);
      setAgentProviders(providers);
      if (styleProfile?.profile) {
        setUserStyleProfile(styleProfile.profile);
        setUserStyleProfilePath(styleProfile.path ?? "");
      }
      studioCatalogLoadedRef.current = true;
    } catch (e) {
      setStatus(`Studio catalog error: ${String(e)}`);
    } finally {
      setGalleryLoading(false);
    }
  }, [applyModelProfile]);

  const modelGallery = useMemo(() => {
    const q = modelFilter.trim().toLowerCase();
    if (!q) return modelGalleryAll;
    return modelGalleryAll.filter((m) => {
      const hay = `${m.category} ${m.caption} ${m.engine_name}`.toLowerCase();
      return hay.includes(q);
    });
  }, [modelGalleryAll, modelFilter]);

  const loraGallery = useMemo(() => {
    const q = loraFilter.trim().toLowerCase();
    if (!q) return loraGalleryAll;
    return loraGalleryAll.filter((l) => {
      const hay = `${l.name} ${l.stem}`.toLowerCase();
      return hay.includes(q);
    });
  }, [loraGalleryAll, loraFilter]);

  const stopLogPoll = useCallback(() => {
    if (logPollRef.current) {
      clearInterval(logPollRef.current);
      logPollRef.current = null;
    }
  }, []);

  const startLogPoll = useCallback(
    (id: string) => {
      stopLogPoll();
      const poll = async () => {
        try {
          const { tail } = await readJobLog(id);
          if (tail) setGenerationLog(tail);
        } catch {
          /* log not ready yet */
        }
      };
      void poll();
      logPollRef.current = setInterval(() => void poll(), 2500);
    },
    [stopLogPoll],
  );

  useEffect(() => {
    generatingRef.current = generating;
  }, [generating]);

  useEffect(() => {
    workerReadyRef.current = workerReady;
  }, [workerReady]);

  useEffect(() => {
    const unsubs: Array<() => void> = [];
    void onWorkerStatus((p) => {
      if (p.status === "stopped") {
        setWorkerReady(false);
        workerReadyRef.current = false;
        setEngineState("failed");
        setBootMessage(p.message ?? "GPU worker stopped — click Restart GPU engine");
        if (!generatingRef.current) {
          setStatus(p.message ?? "GPU worker stopped — click Restart GPU engine");
        }
        return;
      }
      if (p.status !== "booting" || workerReadyRef.current) {
        return;
      }
      setEngineState("booting");
    }).then((u) => unsubs.push(() => u()));
    void onWorkerBootProgress((p) => {
      const phase = p.phase ?? "loading_pipeline";
      const msg = p.message?.trim() || "Loading…";
      const isAssetPrep = phase === "preparing_tools" || phase === "preparing";
      if (isAssetPrep) {
        if (companionBootstrapBusyRef.current) {
          setCompanionBootstrapMessage(msg);
          setBootPhase(phase);
          setStatus(msg);
        }
        return;
      }
      if (phase === "ready") return;
      const showBoot =
        !workerReadyRef.current ||
        engineStateRef.current === "restarting" ||
        engineStateRef.current === "booting";
      if (!showBoot) return;
      setEngineState(
        engineStateRef.current === "restarting" ? "restarting" : "booting",
      );
      setBootPhase(phase);
      setBootMessage(msg);
      setStatus(msg);
    }).then((u) => unsubs.push(() => u()));
    void onWorkerReady((p) => {
      if (p.gpu_name) setGpuName(p.gpu_name);
      if (p.vram_gb != null) setVramGb(p.vram_gb);
      const mps =
        (p as { mps_available?: boolean }).mps_available ?? mpsAvailable;
      if ((p as { mps_available?: boolean }).mps_available != null) {
        setMpsAvailable((p as { mps_available?: boolean }).mps_available ?? null);
      }
      const hint =
        (p as { vram_profile_hint?: string }).vram_profile_hint ?? null;
      const resolved = resolveVramProfile(
        settingsRef.current.vram_profile ?? "auto",
        p.vram_gb ?? vramGb,
        mps ?? null,
        hint,
      );
      effectiveVramProfileRef.current = resolved;
      if ((settingsRef.current.vram_profile ?? "auto") === "auto") {
        void syncDesktopVramProfile("auto");
      }
      if (!workerReadyRef.current) {
        setEngineState(
          engineStateRef.current === "restarting" ? "restarting" : "booting",
        );
        setBootPhase("starting_comfy");
        setBootMessage("Starting managed ComfyUI server…");
        setStatus("Starting managed ComfyUI server…");
      }
    }).then((u) => unsubs.push(() => u()));
    void onWorkerDead((p) => {
      stopLogPoll();
      const wasGenerating = generatingRef.current;
      if (wasGenerating) {
        setGenerating(false);
        generatingRef.current = false;
        setLiveProgress(null);
      }
      setWorkerReady(false);
      workerReadyRef.current = false;
      setEngineState("failed");
      const tail = p.log_tail ?? "";
      if (tail) setWorkerLogTail(tail);
      else void refreshWorkerLog();
      const friendly = describeError({
        code: "worker_crashed",
        message: p.error ?? undefined,
      });
      setLastError(friendly);
      setBootMessage(friendly.title);
      setStatus(
        wasGenerating
          ? shortErrorLine(friendly)
          : friendly.title,
      );
    }).then((u) => unsubs.push(() => u()));
    void onEngineHealthStatus((p) => {
      if (p.health === "restarting") {
        setEngineState("restarting");
        setBootMessage("Restarting GPU engine…");
      } else if (p.health === "dead") {
        setEngineState("failed");
      }
    }).then((u) => unsubs.push(() => u()));
    void onGenerationProgress((p) => {
      applyLiveProgress({
        phase: p.phase ?? "sampling",
        progress: p.progress,
        message: p.message,
      });
    }).then((u) => unsubs.push(() => u()));
    void onGenerationBusy(() => {
      setStatus("Generation already in progress on the GPU worker");
    }).then((u) => unsubs.push(() => u()));
    void onGenerationWarning((p) => {
      const friendly = describeWarning(p);
      setWarnings((prev) => {
        // De-dupe by code so spammy events don't pile up.
        const filtered = prev.filter((w) => w.code !== friendly.code);
        return [...filtered, friendly].slice(-5);
      });
    }).then((u) => unsubs.push(() => u()));
    void onWorkerFailed((p) => {
      setWorkerReady(false);
      setEngineState("failed");
      const tail = p.log_tail ?? "";
      if (tail) setWorkerLogTail(tail);
      else void refreshWorkerLog();
      const friendly = describeError(p);
      setLastError(friendly);
      setStatus(shortErrorLine(friendly));
      setBootMessage(friendly.title);
    }).then((u) => unsubs.push(() => u()));
    void onOutputsChanged(() => debouncedRefreshWhileGenerating()).then((u) =>
      unsubs.push(() => u()),
    );
    void onGenerationStarted((p) => {
      setEngineState("generating");
      setJobId(p.job_id ?? null);
      if (p.job_id) setLastJobId(p.job_id);
      setGenerationLog("Sampling…\n");
      applyLiveProgress({
        progress: 0,
        title: "Starting generation…",
        phase: "preparing",
      });
      previewGenerationRef.current += 1;
      finalPreviewAppliedRef.current = false;
      canvasPreviewPathRef.current = "";
      previewUrlRef.current = null;
      setLastError(null);
      setWarnings([]);
      lastPreviewEventAtRef.current = Date.now();
      if (p.job_id) startLogPoll(p.job_id);
    }).then((u) => unsubs.push(() => u()));
    void onGenerationPreview((p) => {
      void applyPreviewPayload(p);
    }).then((u) => unsubs.push(() => u()));
    void onGenerationFinished(async (p) => {
      const logJob = (p.job_id ?? jobId ?? lastJobId ?? "").trim();
      if (!p.success && logJob) {
        try {
          const { tail } = await readJobLog(logJob);
          if (tail) setGenerationLog(tail);
          else if (p.log_tail) setGenerationLog(p.log_tail);
        } catch {
          if (p.log_tail) setGenerationLog(p.log_tail);
        }
      } else if (p.log_tail) {
        setGenerationLog(p.log_tail);
      }
      stopLogPoll();
      setGenerating(false);
      generatingRef.current = false;
      setJobId(null);
      setLiveProgress(null);
      setEngineState("ready");
      if (p.success) {
        setStatus("Generation complete");
        setLastError(null);
        void refreshUserStyleProfile();
        void notifyDone("DreamForge", "Your image finished rendering.");
        await applyFinalCanvasPreview({
          data_url: p.data_url,
          preview_path: p.preview_path,
          asset_url: p.asset_url,
          result: (p as { result?: { images?: Array<{ path: string }> } })
            .result,
        });
        void refreshOutputs({ selectNewest: true });
        void freeWorkerVram().catch(() => {});
      } else {
        const friendly = describeError(p);
        setLastError(friendly);
        const nodeItems = customNodeItemsFromActions(
          friendly.failureReport?.repair_actions,
        );
        if (friendly.code === "missing_custom_node_pack" && nodeItems.length > 0) {
          const model = (settingsRef.current.model ?? "").trim() || "workflow-assets";
          startCompanionDownload(model, nodeItems);
          setStatus("Install the required ComfyUI custom node pack, then generate again.");
        } else {
          setStatus(shortErrorLine(friendly));
        }
        // Do not auto-restart the GPU engine here — it races active Comfy jobs and
        // looks like a crash. User can use Restart GPU engine or lower VRAM profile.
      }
    }).then((u) => unsubs.push(() => u()));
    return () => {
      unsubs.forEach((fn) => fn());
      stopLogPoll();
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    };
  }, [
    refreshOutputs,
    debouncedRefreshWhileGenerating,
    startLogPoll,
    stopLogPoll,
    refreshWorkerLog,
    applyPreviewPayload,
    applyLiveProgress,
    applyFinalCanvasPreview,
    startCompanionDownload,
  ]);

  useEffect(() => {
    void (async () => {
      await loadStudioCatalog();
      await refreshOutputs();
    })();
  }, [loadStudioCatalog, refreshOutputs]);

  const applyEngineStatus = useCallback((s: Awaited<ReturnType<typeof getEngineStatus>>) => {
    // eslint-disable-next-line no-console
    console.debug("[DF] engine_status", {
      ready: s.ready,
      comfy_ready: s.comfy_ready,
      events_ready: s.events_ready,
      worker_alive: s.worker_alive,
      worker_running: s.worker_running,
      health: s.health,
      boot_phase: s.boot_phase,
      boot_message: s.boot_message,
    });
    if (s.boot_phase) setBootPhase(s.boot_phase);
    if (s.gpu_name) setGpuName(s.gpu_name);
    if (s.vram_gb != null) setVramGb(s.vram_gb);
    if (s.mps_available != null) setMpsAvailable(s.mps_available);
    const comfyUp = isComfyServerReady(s);
    if (comfyUp) {
      const resolved = resolveVramProfile(
        settingsRef.current.vram_profile ?? "auto",
        s.vram_gb ?? null,
        s.mps_available ?? null,
        s.resolved_vram_profile ?? null,
      );
      effectiveVramProfileRef.current = resolved;
      if (
        !vramProfileAutoAppliedRef.current &&
        (settingsRef.current.vram_profile ?? "auto") === "auto"
      ) {
        vramProfileAutoAppliedRef.current = true;
        void syncDesktopVramProfile("auto");
      }
    }
    if (comfyUp) {
      workerReadyRef.current = true;
      setWorkerReady(true);
      setEngineState(generatingRef.current ? "generating" : "ready");
      setBootMessage("");
      setBootPhase("ready");
      if (s.worker_alive === false && s.worker_running) {
        setEngineState("failed");
        const deadMsg =
          s.boot_message?.trim() ||
          "GPU worker stopped — click Restart GPU engine";
        setBootMessage(deadMsg);
        setStatus(deadMsg);
        setWorkerReady(false);
        workerReadyRef.current = false;
        return;
      }
      const gpuHint =
        s.mps_available
          ? ` — Apple ${s.gpu_name ?? "MPS"} (unified memory)`
          : s.gpu_name && s.vram_gb != null
            ? ` — ${s.gpu_name} (${s.vram_gb} GB VRAM)`
            : s.gpu_name
              ? ` — ${s.gpu_name}`
              : "";
      setStatus(`Engine ready — live GPU preview enabled${gpuHint}`);
      setWorkerLogTail("");
      return;
    }
    if (s.ready && s.events_ready && s.worker_alive !== false) {
      workerReadyRef.current = false;
      setWorkerReady(false);
      const phase = s.boot_phase ?? "starting_comfy";
      const prepMsg = s.boot_message?.trim();
      const isAssetPrep =
        phase === "preparing_tools" || phase === "preparing";
      if (isAssetPrep && prepMsg && companionBootstrapBusyRef.current) {
        setCompanionBootstrapMessage(prepMsg);
        setBootPhase(phase);
        setStatus(prepMsg);
        return;
      }
      const msg =
        prepMsg || bootPhaseLabel(phase) || "Starting managed ComfyUI server…";
      setEngineState(
        s.health === "restarting" ? "restarting" : "booting",
      );
      setBootMessage(msg);
      setBootPhase(phase);
      setStatus(msg);
      return;
    }
    if (s.events_ready && s.worker_alive === false) {
      workerReadyRef.current = false;
      setWorkerReady(false);
      setEngineState("failed");
      const deadMsg =
        s.boot_message?.trim() ||
        "GPU worker stopped — click Restart GPU engine";
      setBootMessage(deadMsg);
      setStatus(deadMsg);
      return;
    }
    if (
      s.health === "dead" &&
      companionBootstrapBusyRef.current &&
      (s.boot_phase === "preparing_tools" || s.boot_phase === "preparing")
    ) {
      const prepMsg = s.boot_message?.trim();
      if (prepMsg) {
        setCompanionBootstrapMessage(prepMsg);
        setStatus(prepMsg);
      }
      return;
    }
    workerReadyRef.current = false;
    setWorkerReady(false);
    if (
      s.health === "dead" ||
      (!s.worker_running && (s.boot_message?.includes("stopped") ?? false))
    ) {
      setEngineState("failed");
      const deadMsg = s.boot_message ?? "GPU worker is not running";
      setBootMessage(deadMsg);
      setStatus(deadMsg);
      return;
    }
    const phase = s.boot_phase ?? "loading_pipeline";
    const msg =
      s.boot_message?.trim() || bootPhaseLabel(phase);
    if (msg) {
      const elapsed =
        s.boot_elapsed_secs != null && s.boot_elapsed_secs > 0
          ? ` (${s.boot_elapsed_secs}s)`
          : "";
      const full = `${msg}${elapsed}`;
      setEngineState(
        s.health === "restarting" ? "restarting" : "booting",
      );
      setBootMessage(full);
      setStatus(full);
    }
  }, []);

  useEffect(() => {
    if (engineState !== "booting" && engineState !== "restarting") return;
    const id = setInterval(() => void refreshWorkerLog(), 4000);
    return () => clearInterval(id);
  }, [engineState, refreshWorkerLog]);

  useEffect(() => {
    const sync = () => {
      void getEngineStatus()
        .then(applyEngineStatus)
        .catch((err) => {
          // eslint-disable-next-line no-console
          console.warn("[DF] get_engine_status failed", err);
        });
    };
    sync();
    const id = setInterval(() => {
      if (workerReadyRef.current && !companionBootstrapBusy) return;
      sync();
    }, 1000);
    return () => clearInterval(id);
  }, [applyEngineStatus, companionBootstrapBusy]);

  useEffect(() => {
    if (!workerReady) return;
    const pending = pendingCompanionPrepRef.current;
    if (!pending) return;
    pendingCompanionPrepRef.current = null;
    void promptMissingCompanionsDownloadRef.current?.(pending);
  }, [workerReady]);

  useEffect(() => {
    if (!generating) return;
    const poll = () => {
      void getGenerationProgress()
        .then((p) => {
          if (!p.running && p.phase === "idle") return;
          applyLiveProgress({
            phase: p.phase ?? "sampling",
            progress: typeof p.progress === "number" ? p.progress : undefined,
            message: p.message,
          });
        })
        .catch(() => {});
      const staleMs = Date.now() - lastPreviewEventAtRef.current;
      if (staleMs < 900 || finalPreviewAppliedRef.current) {
        return;
      }
      void readLivePreview()
        .then(async (r) => {
          if (finalPreviewAppliedRef.current) {
            return;
          }
          const url = await resolveCanvasPreviewUrl({
            data_url: r.data_url,
            preview_path: r.path,
            live: true,
          });
          if (finalPreviewAppliedRef.current) {
            return;
          }
          const sig = url ? previewSignature(url) : "";
          if (url && sig !== lastPreviewSigRef.current) {
            lastPreviewSigRef.current = sig;
            lastPreviewEventAtRef.current = Date.now();
            setCanvasPreview(url, r.path);
          }
        })
        .catch(() => {});
    };
    poll();
    const id = setInterval(poll, 800);
    return () => clearInterval(id);
  }, [generating, setCanvasPreview, previewSignature, applyLiveProgress]);

  useEffect(() => () => cleanupCanvasPreviewUrls(), []);

  useEffect(() => {
    if (generating) return;
    const path = selected?.images?.[0];
    const selectionKey = selected?.manifest_path ?? path ?? "";
    if (selectionKey === lastSelectedKeyRef.current) {
      return;
    }
    lastSelectedKeyRef.current = selectionKey;
    if (!path) {
      if (!canvasPreviewPathRef.current) setCanvasPreview(null);
      return;
    }
    const norm = normalizePreviewPath(path);
    if (norm === canvasPreviewPathRef.current && previewUrlRef.current) {
      return;
    }
    void setCanvasPreviewFromPath(path);
  }, [selected, generating, setCanvasPreview, setCanvasPreviewFromPath]);

  const patchSettings = useCallback(
    (
      patch: Partial<GenerationSettings>,
      meta?: { modelFromStyle?: boolean },
    ) => {
      if (patch.model !== undefined && !meta?.modelFromStyle) {
        userPickedModelRef.current = true;
      }
      if (patch.vram_profile !== undefined) {
        vramRestartPendingRef.current = true;
      }
      setSettings((s) => {
        const next = { ...s, ...patch };
        settingsRef.current = next;
        return next;
      });
    },
    [],
  );

  const syncOutputPathForSession = useCallback(
    (sessionId: string) => {
      const sid = sessionId.trim() || DEFAULT_SESSION_ID;
      const studioMode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
      const route = resolveEffectiveRoute(studioMode, settingsRef.current);
      patchSettings({ output: outputPathForSession(sid, route.outputKind) });
    },
    [appConfig?.ui.studio_mode, patchSettings],
  );

  const switchSession = useCallback(
    (sessionId: string, opts?: { previewFirst?: boolean }) => {
      const id = sessionId.trim() || DEFAULT_SESSION_ID;
      setActiveSessionId(id);
      saveActiveSessionId(id);
      const session = sessions.find((s) => s.id === id);
      if (opts?.previewFirst) {
        const first = session?.items[0]?.images?.[0];
        if (first) void setCanvasPreviewFromPath(first);
      }
      syncOutputPathForSession(id);
      setStatus(`Saving new generations to ${session?.label ?? id}`);
    },
    [sessions, syncOutputPathForSession, setCanvasPreviewFromPath],
  );

  const createSession = useCallback(
    (name: string) => {
      const trimmed = name.trim();
      if (!trimmed) {
        setStatus("Enter a session name");
        return;
      }
      const base = sanitizeSessionId(trimmed);
      if (!base) {
        setStatus("Use letters, numbers, spaces, or underscores only");
        return;
      }
      const taken = new Set([
        ...sessionRegistry.map((s) => s.id),
        ...sessions.map((s) => s.id),
      ]);
      const id = uniqueSessionId(base, taken);
      const label = trimmed;
      setSessionRegistry((prev) => {
        const next = [...prev, { id, label }];
        saveSessionRegistry(next);
        return next;
      });
      switchSession(id);
      setStatus(`Created session “${label}”`);
    },
    [sessionRegistry, sessions, switchSession],
  );

  const selectOutput = useCallback(
    (item: OutputItem) => {
      setSelected(item);
      saveLastSelectedManifest(item.manifest_path);
      const path = item.images?.[0];
      const selectionKey = item.manifest_path ?? path ?? "";
      lastSelectedKeyRef.current = selectionKey;
      if (path) {
        void setCanvasPreviewFromPath(path, { force: true });
      } else if (!canvasPreviewPathRef.current) {
        setCanvasPreview(null);
      }
    },
    [setCanvasPreview, setCanvasPreviewFromPath],
  );

  const reuseOutputPrompt = useCallback(
    async (item: OutputItem) => {
      try {
        const res = await getGenerationBundle(item.manifest_path);
        if (res.ok && res.bundle) {
          patchSettings(
            settingsFromManifestBundle(
              res.bundle as Parameters<typeof settingsFromManifestBundle>[0],
            ),
          );
          setStatus("Loaded full recipe from history");
          return;
        }
      } catch {
        /* fall back to summary fields */
      }
      patchSettings({
        prompt: item.prompt || settingsRef.current.prompt,
        model: item.model_name || settingsRef.current.model,
        seed: item.seed,
        styles: item.styles?.length ? item.styles : settingsRef.current.styles,
      });
      setStatus("Loaded prompt from history");
    },
    [patchSettings],
  );

  const openOutputInExplorer = useCallback(async (path: string) => {
    try {
      await revealPathInExplorer(path);
    } catch (e) {
      setStatus(`Could not open folder: ${String(e)}`);
    }
  }, []);

  const copyOutputPath = useCallback(async (path: string) => {
    try {
      await navigator.clipboard.writeText(path);
      setStatus("Copied path to clipboard");
    } catch (e) {
      setStatus(`Copy failed: ${String(e)}`);
    }
  }, []);

  const removeDeletedFromSelection = useCallback(
    (manifestPath?: string, imagePath?: string) => {
      setSelected((prev) => {
        if (!prev) return null;
        if (manifestPath && prev.manifest_path === manifestPath) {
          return null;
        }
        if (imagePath && prev.images.includes(imagePath)) {
          const nextImages = prev.images.filter((p) => p !== imagePath);
          if (nextImages.length === 0) return null;
          return { ...prev, images: nextImages };
        }
        return prev;
      });
      setOutputs((prev) =>
        prev
          .filter((item) => !manifestPath || item.manifest_path !== manifestPath)
          .map((item) => {
            if (!imagePath || !item.images.includes(imagePath)) return item;
            const nextImages = item.images.filter((p) => p !== imagePath);
            if (nextImages.length === 0) return null;
            return { ...item, images: nextImages };
          })
          .filter((item): item is OutputItem => item !== null),
      );
      if (manifestPath) {
        canvasPreviewPathRef.current = "";
        previewUrlRef.current = null;
        setPreviewUrl(null);
      }
    },
    [],
  );

  const deleteOutputManifest = useCallback(
    async (item: OutputItem) => {
      const label = item.title || excerptPrompt(item.prompt, 40) || "this generation";
      if (
        !window.confirm(
          `Delete "${label}" and all of its files and generation metadata? This cannot be undone.`,
        )
      ) {
        return;
      }
      try {
        await deleteOutput(item.manifest_path);
        purgeHistoryMetadataForManifest(item.manifest_path);
        removeDeletedFromSelection(item.manifest_path);
        setStatus("Deleted generation");
        void refreshOutputs({ keepSelection: true });
      } catch (e) {
        setStatus(`Delete failed: ${String(e)}`);
      }
    },
    [removeDeletedFromSelection, refreshOutputs],
  );

  const deleteOutputImageFile = useCallback(
    async (item: OutputItem, imagePath: string) => {
      const name = imagePath.split(/[/\\]/).pop() ?? "image";
      if (
        !window.confirm(
          `Delete image "${name}"? The manifest will be updated or removed if it was the last file.`,
        )
      ) {
        return;
      }
      try {
        const res = await deleteOutputImage(item.manifest_path, imagePath);
        if (res.manifest_removed) {
          purgeHistoryMetadataForManifest(item.manifest_path);
        }
        removeDeletedFromSelection(
          res.manifest_removed ? item.manifest_path : undefined,
          imagePath,
        );
        setStatus("Deleted image");
        void refreshOutputs({ keepSelection: true });
      } catch (e) {
        setStatus(`Delete failed: ${String(e)}`);
      }
    },
    [removeDeletedFromSelection, refreshOutputs],
  );

  const deleteOutputSession = useCallback(
    async (session: OutputSession) => {
      const noun =
        session.id === "root"
          ? `${session.items.length} root-level generation(s)`
          : `the entire "${session.label}" folder (${session.items.length} generation(s))`;
      if (
        !window.confirm(
          `Delete ${noun}? All manifests and images will be removed. This cannot be undone.`,
        )
      ) {
        return;
      }
      try {
        await deleteSession(session.id);
        for (const item of session.items) {
          purgeHistoryMetadataForManifest(item.manifest_path);
        }
        setSessionRegistry((prev) => {
          const next = prev.filter((s) => s.id !== session.id);
          saveSessionRegistry(next);
          return next;
        });
        if (session.id === activeSessionIdRef.current) {
          switchSession(DEFAULT_SESSION_ID);
        }
        setSelected((prev) =>
          prev && session.items.some((i) => i.manifest_path === prev.manifest_path)
            ? null
            : prev,
        );
        setStatus(`Deleted session ${session.label}`);
        void refreshOutputs();
      } catch (e) {
        setStatus(`Delete failed: ${String(e)}`);
      }
    },
    [refreshOutputs, switchSession],
  );

  const selectModelGallery = useCallback(
    async (item: ModelGalleryItem) => {
      const mode = appConfig?.ui.studio_mode ?? "generate";
      if (
        mode !== "generate" &&
        mode !== "inpaint" &&
        mode !== "edit" &&
        !advancedMode
      ) {
        setStatus(
          "Switch to Generate, Edit, or Inpaint mode, or enable advanced mode to override routed models",
        );
        return;
      }
      userPickedModelRef.current = true;
      const routingPatch =
        mode === "edit" ? buildEditRoutingPatch(item) : {};
      const qwenPatch =
        mode === "edit" && isQwenEditModel(item)
          ? qwenEdit2511LightningPatch()
          : {};
      const ideogramPatch =
        mode === "edit" && (item.family ?? "").toLowerCase() === "ideogram4"
          ? ideogram4SettingsDefaults()
          : {};
      patchSettings({
        model: item.engine_name,
        ...routingPatch,
        ...qwenPatch,
        ...ideogramPatch,
      });
      const warn =
        inpaintModelWarning(item, mode) ??
        upscaleModelWarning(item, mode) ??
        editModelWarning(item, mode);
      const profile = await applyModelProfile(item);
      const hint = cleanHtmlText(profile?.hints?.[0]).slice(0, 160);
      if (warn) {
        setStatus(hint ? `${warn} · ${hint}` : warn);
      } else if (hint) {
        setStatus(hint);
      }
    },
    [advancedMode, appConfig?.ui.studio_mode, applyModelProfile, patchSettings],
  );

  const setStyle = useCallback(
    async (style: string) => {
      const styleId = (style || "none").trim() || "none";
      if (styleId === "none") {
        userPickedStyleRef.current = false;
        patchSettings({ style: "none", styles: [] });
        return;
      }
      if (styleId === settingsRef.current.style) {
        userPickedStyleRef.current = false;
        patchSettings({ style: "none", styles: [] });
        return;
      }
      userPickedStyleRef.current = true;
      const recipe = styleRecipes.find((item) => item.id === styleId);
      const stylePatch: Partial<GenerationSettings> = { style: styleId };
      if (recipe?.styles?.length) {
        stylePatch.styles = [...recipe.styles];
      } else {
        stylePatch.styles = [];
      }
      if (recipe?.performance) {
        stylePatch.performance = recipe.performance;
      }
      if (typeof recipe?.aspect_ratio === "string" && recipe.aspect_ratio.trim()) {
        stylePatch.aspect_ratio = recipe.aspect_ratio.replace("×", "x");
      }
      if (recipe?.prompt_prefix && !settingsRef.current.prompt?.trim()) {
        stylePatch.prompt = recipe.prompt_prefix;
      }

      let routedModel: string | undefined;
      if (!userPickedModelRef.current && style) {
        routedModel = resolveActiveModel(
          modelGalleryAll,
          settingsRef.current.model,
          style,
          styleRecipes,
          false,
        );
      }

      const galleryItem = routedModel
        ? findGalleryModel(modelGalleryAll, routedModel)
        : undefined;

      if (galleryItem) {
        await applyModelProfile(galleryItem, recipe?.performance);
        patchSettings(
          { ...stylePatch, model: galleryItem.engine_name },
          { modelFromStyle: true },
        );
      } else {
        patchSettings(stylePatch);
      }
    },
    [applyModelProfile, modelGalleryAll, patchSettings, styleRecipes],
  );

  const activeModelLabel = useMemo(() => {
    const hit = modelGalleryAll.find((m) => modelMatches(m, settings.model));
    if (hit) return modelBasename(hit.caption);
    if (settings.model) return modelBasename(settings.model);
    return "No model selected";
  }, [modelGalleryAll, settings.model]);

  const toggleLoraGallery = useCallback(
    async (name: string) => {
      userPickedLorasRef.current = true;
      const prev = settings.lora ?? [];
      if (hasLora(prev, name)) {
        patchSettings({ lora: removeLora(prev, name) });
        return;
      }
      if (parseLoraList(prev).length >= DEFAULT_MAX_LORA_STACK) {
        setStatus(
          `LoRA stack limit (${DEFAULT_MAX_LORA_STACK}) — remove one or adjust in web UI settings`,
        );
        return;
      }
      let weight = 1;
      try {
        const info = await getLoraInfo(name);
        weight = info.default_weight ?? 1;
      } catch {
        /* use default */
      }
      patchSettings({ lora: upsertLora(prev, name, weight) });
    },
    [settings.lora, patchSettings],
  );

  const saveStudioSettingsPatch = useCallback(
    async (patch: StudioSettings) => {
      const merged = { ...(studioSettings ?? {}), ...patch };
      await saveStudioSettings(merged);
      setStudioSettings(merged);
      if (merged.image_number_max != null) {
        setImageNumberMax(
          Math.min(50, Math.max(1, merged.image_number_max)),
        );
      }
      setSettings((prev) => ({
        ...prev,
        clip_skip: merged.clip_skip ?? prev.clip_skip,
        auto_negative_prompt:
          merged.auto_negative_prompt ?? prev.auto_negative_prompt,
      }));
    },
    [studioSettings],
  );

  const saveAppConfigPatch = useCallback(
    async (patch: DreamForgeAppConfigPatch) => {
      const merged = {
        ...(appConfig ?? {}),
        ...patch,
        agent: {
          ...(appConfig?.agent ?? {}),
          ...(patch.agent ?? {}),
        },
        privacy: {
          ...(appConfig?.privacy ?? {}),
          ...(patch.privacy ?? {}),
        },
        ui: {
          ...(appConfig?.ui ?? {}),
          ...(patch.ui ?? {}),
        },
      } as DreamForgeAppConfigPatch;
      const saved = await saveAppConfig(merged);
      setAppConfig(saved);
      setStatus("Agent settings saved");
      return saved;
    },
    [appConfig],
  );

  const studioModeForTask = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
  const creativeTask = useCreativeTask({
    studioMode: studioModeForTask,
    gallery: modelGalleryAll,
    vramProfile: settings.vram_profile,
    vramGb,
    mpsAvailable,
    advancedMode,
    selectedImage: selected?.images?.[0],
  });

  const openInpaintMaskEditor = useCallback((options?: { modal?: boolean }) => {
    if (options?.modal) {
      setInpaintMaskOpen(true);
      return;
    }
    setInpaintCanvasFocus(true);
    setStatus("Paint the region to fix on the canvas");
  }, []);

  const openInpaintMaskModal = useCallback(() => {
    openInpaintMaskEditor({ modal: true });
  }, [openInpaintMaskEditor]);

  useEffect(() => {
    if (studioModeForTask !== "inpaint") {
      setInpaintCanvasFocus(false);
    }
  }, [studioModeForTask]);

  useEffect(() => {
    if (!appConfig) return;
    if (uiExperience === "simple" && appConfig.ui.studio_mode === "agent") {
      void saveAppConfigPatch({ ui: { studio_mode: "generate" } });
    }
  }, [appConfig, saveAppConfigPatch, uiExperience]);

  const runAgentProviderTest = useCallback(
    async (patch?: DreamForgeAppConfigPatch) => {
      setAgentProviderBusy(true);
      setAgentProviderTest(null);
      try {
        const config = patch ? await saveAppConfigPatch(patch) : appConfig ?? undefined;
        const res = await testAgentProvider(config ? { ...config } : undefined);
        setAgentProviderTest(res);
        setStatus(
          res.ok
            ? `Agent runtime connected (${res.latency_ms} ms)`
            : `Agent runtime test failed: ${res.detail}`,
        );
        return res;
      } catch (e) {
        const res = {
          ok: false,
          provider: appConfig?.agent.provider ?? "agent",
          model: appConfig?.agent.model ?? "",
          latency_ms: 0,
          detail: String(e),
        };
        setAgentProviderTest(res);
        setStatus(`Agent runtime test failed: ${String(e)}`);
        return res;
      } finally {
        setAgentProviderBusy(false);
      }
    },
    [appConfig, saveAppConfigPatch],
  );

  const appendAgentTranscript = useCallback(
    (message: Omit<AgentTranscriptMessage, "id" | "created_at">) => {
      const entry: AgentTranscriptMessage = {
        ...message,
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        created_at: new Date().toISOString(),
      };
      setAgentTranscript((prev) => [...prev.slice(-23), entry]);
      return entry;
    },
    [],
  );

  const runAgentInstruction = useCallback(async (applyPlan: boolean) => {
    const instruction = (settingsRef.current.prompt ?? "").trim();
    if (!instruction) {
      setStatus("Tell the agent what you want DreamForge to do");
      return;
    }
    appendAgentTranscript({
      role: "user",
      text: instruction,
      status: applyPlan ? "applied" : "planned",
    });
    setStatus(applyPlan ? "Agent is applying the workflow..." : "Agent is planning the workflow...");
    try {
      const res = await planAgentInstruction({
        instruction,
        settings: settingsRef.current,
        selected_image: selected?.images?.[0],
        model_gallery: modelGalleryAll.map((m) => ({
          category: m.category,
          relative_path: m.relative_path,
          caption: m.caption,
          engine_name: m.engine_name,
          family: m.family,
          thumbnail_path: "",
        })),
      });
      const patch = res.patch ?? {};
      const planPatch: Partial<GenerationSettings> = { ...patch };
      if (res.workflow_plan?.length) {
        planPatch.workflow_plan = res.workflow_plan as GenerationSettings["workflow_plan"];
        planPatch.execute_workflow_plan = res.workflow_plan.length > 1;
      }
      if (res.mode && res.mode !== "agent") {
        setAgentPlannedMode(res.mode);
      }
      if (applyPlan && Object.keys(planPatch).length > 0) {
        userPickedModelRef.current = false;
        patchSettings(planPatch);
        if (res.mode && res.mode !== "agent") {
          await saveAppConfigPatch({ ui: { studio_mode: res.mode } });
          setAgentPlannedMode(null);
        }
      }
      const source = res.provider_model
        ? `${res.provider ?? "provider"} / ${res.provider_model}`
        : res.source;
      setAgentPlan(null);
      appendAgentTranscript({
        role: "assistant",
        text: res.message || "Agent planned a DreamForge workflow.",
        source,
        mode: res.mode,
        actions: res.actions,
        status: applyPlan ? "applied" : "planned",
      });
      setStatus(
        applyPlan
          ? res.mode && res.mode !== "agent"
            ? `Route applied in Settings (${res.mode}) — adjust if needed, then Generate`
            : res.message || "Route applied in Settings — adjust if needed, then Generate"
          : "Agent plan ready — use Generate to apply and run",
      );
    } catch (e) {
      appendAgentTranscript({
        role: "assistant",
        text: `Agent planning failed: ${String(e)}`,
        status: "error",
      });
      setStatus(`Agent planning failed: ${String(e)}`);
    }
  }, [
    appendAgentTranscript,
    modelGalleryAll,
    patchSettings,
    saveAppConfigPatch,
    selected,
  ]);

  const startGeneration = useCallback(
    async (
      preparedSettings: GenerationSettings,
      meta?: { mapped?: string; hint?: string; studioMode?: StudioMode },
    ) => {
      const studioMode =
        meta?.studioMode ??
        ((appConfig?.ui.studio_mode ?? "generate") as StudioMode);
      let sanitized = sanitizeEditFamilySettings(preparedSettings, studioMode);
      sanitized = await enforceCreativeTaskSettingsRemote(sanitized, {
        studioMode,
        gallery: modelGalleryAll,
        advancedMode: advancedMode,
        vramProfile: sanitized.vram_profile ?? settingsRef.current.vram_profile,
        vramGb,
        mpsAvailable,
        selectedImage: selected?.images?.[0],
        userPickedModel: userPickedModelRef.current,
      });
      const prompt = (sanitized.prompt ?? "").trim();
      if (!prompt && studioMode !== "upscale") {
        setStatus("Enter a prompt before generating");
        return false;
      }
      if (!sanitized.model) {
        setStatus("Select a base model");
        return false;
      }
      const mergedMissingCount = mergeDependencyItems(
        modelDependencies.missing,
        studioResources.missing,
        companionItemsFromActions(
          agentPlanRef.current?.readiness?.recommended_actions as RepairAction[] | undefined,
        ),
        companionItemsFromActions(lastError?.failureReport?.repair_actions),
        companionItemsFromActions(
          (lastError?.details?.recommended_actions as RepairAction[] | undefined) ?? [],
        ),
      ).length;
      const readiness = computeGenerateReadiness({
        workerReady,
        generating: generatingRef.current,
        engineState,
        engineLabel: engineLabel(engineState, bootMessage),
        prompt,
        model: sanitized.model ?? "",
        modelDependenciesReady:
          modelDependencies.ready &&
          studioResources.ready &&
          mergedMissingCount === 0,
        missingCompanionCount: mergedMissingCount,
        studioMissingAssetCount: studioResources.missing.length,
        settings: sanitized,
        modelGallery: modelGalleryAll,
        studioMode,
        inpaintMaskSyncing,
      });
      if (!readiness.ok) {
        setStatus(readiness.reason);
        if (readiness.missingCompanions) {
          setLastError(
            describeError({
              code: "missing_model_dependencies",
              message: readiness.reason,
            }),
          );
          await promptMissingCompanionsDownloadRef.current?.();
        }
        return false;
      }
      if (!workerReady) {
        setStatus(engineLabel(engineState, bootMessage));
        return false;
      }
      if (generatingRef.current) {
        setStatus("Generation already in progress");
        return false;
      }

      const sid = activeSessionIdRef.current || DEFAULT_SESSION_ID;
      const route = resolveEffectiveRoute(studioMode, sanitized);
      const output = outputPathForSession(sid, route.outputKind);

      let params: GenerationSettings = {
        ...sanitized,
        prompt,
        output,
        validate_output: true,
        use_comfy_server: true,
        workflow_mode:
          sanitized.workflow_mode ??
          (studioMode === "generate" ? "generate" : studioMode),
      };
      const activeModel = findGalleryModel(modelGalleryAll, params.model ?? "");
      const modelFamily = (activeModel?.family ?? "").toLowerCase();
      const routed = applyExplicitReferenceRoleParams(
        params,
        studioMode,
        modelFamily,
        {
          modelMissing: modelDependencies.missing,
          studioMissing: studioResources.missing,
          imagePromptMissing: imagePromptResources.missing,
        },
      );
      params = routed.params;
      const routeWarning = routed.warning;
      params = applyVaryAmountAtSubmit(params);
      params = applyUpscalePresetAtSubmit(params);
      params = applyReferencesAtSubmit(params, studioMode);
      params = applyAutoEnhanceAtSubmit(params);
      params = applyIdentityAtSubmit(params, modelGalleryAll, {
        studioMode,
        modelMissing: modelDependencies.missing,
        studioMissing: studioResources.missing,
        imagePromptMissing: imagePromptResources.missing,
      });
      params = await enforceCreativeTaskSettingsRemote(params, {
        studioMode,
        gallery: modelGalleryAll,
        advancedMode: advancedMode,
        vramProfile: params.vram_profile ?? settingsRef.current.vram_profile,
        vramGb,
        mpsAvailable,
        selectedImage: selected?.images?.[0],
        userPickedModel: userPickedModelRef.current,
      });
      params = applyHiDreamPerformanceAtSubmit(
        params,
        modelFamily,
        params.model,
      );
      if (params.lora?.length && !params.lora_keywords?.trim()) {
        try {
          const kw = await aggregateLoraKeywords(params.lora);
          if (kw) params = { ...params, lora_keywords: kw };
        } catch {
          /* optional */
        }
      }

      const activeModelForEnhance = findGalleryModel(modelGalleryAll, params.model ?? "");
      const enhanceFamily = activeModelForEnhance?.family?.toLowerCase() ?? "";
      const needsIdeogramEnhance =
        enhanceFamily === "ideogram4" &&
        params.prompt &&
        !looksLikeIdeogramJson(params.prompt) &&
        studioMode === "generate";
      const needsModernLlmEnhance =
        shouldAutoEnhanceOnGenerate(
          enhanceFamily,
          studioMode,
          appConfig?.ui.auto_enhance_on_generate,
        ) && Boolean(params.prompt?.trim());

      if (needsIdeogramEnhance || needsModernLlmEnhance) {
        setStatus("Enhancing prompt...");
        try {
          const res = await enhanceStudioPrompt({
            ...params,
            studio_mode: studioMode,
            ...enhancePrefsFromAppConfig(appConfig),
          });
          if (res.ok && res.prompt) {
            params.prompt = res.prompt;
            patchSettings({ prompt: res.prompt });
          }
        } catch (e) {
          console.warn("Prompt enhancement failed:", e);
        }
      }

      setGenerating(true);
      generatingRef.current = true;
      setEngineState("generating");
      const mapped = meta?.mapped ? ` · ${meta.mapped}` : "";
      const hint = meta?.hint ? ` · ${meta.hint}` : "";
      const routeHint = routeWarning ? `${routeWarning} · ` : "";
      setStatus(
        `${routeHint}Generating with ${modelBasename(params.model ?? "model")}…${mapped}${hint}`,
      );
      setAgentPlan(null);
      setGenerationLog("");
      lastPreviewSigRef.current = "";
      applyLiveProgress({
        progress: 0,
        title: "Starting generation…",
        phase: "preparing",
      });
      patchSettings({ output });

      try {
        const resolvedParams = await resolveGenerationImagePaths(params);
        const vramSlot = resolvedParams.vram_profile ?? "auto";
        const vramForJob = resolveVramProfile(
          vramSlot,
          vramGb,
          mpsAvailable,
          effectiveVramProfileRef.current,
        );
        const res = await invokeGeneration({
          ...resolvedParams,
          vram_profile:
            vramSlot === "auto" ? vramForJob : (resolvedParams.vram_profile ?? vramForJob),
        });
        setJobId(res.job_id);
        setLastJobId(res.job_id);
        if (res.job_id) startLogPoll(res.job_id);
        return true;
      } catch (e) {
        setGenerating(false);
        generatingRef.current = false;
        const msg = String(e);
        if (msg.includes("generation_in_progress")) {
          setStatus("Generation already in progress — wait or cancel first");
        } else {
          setStatus(`Start failed: ${plainErrorLine(msg)}`);
        }
        return false;
      }
    },
    [
      appConfig?.ui.studio_mode,
      appConfig?.ui.auto_enhance_on_generate,
      advancedMode,
      patchSettings,
      startLogPoll,
      workerReady,
      engineState,
      bootMessage,
      modelDependencies,
      studioResources,
      lastError,
      modelGalleryAll,
      vramGb,
      mpsAvailable,
    ],
  );

  const applyPlanSnapshot = useCallback(
    async (plan: AgentPlanSnapshot) => {
      const base = settingsRef.current;
      const merged = resolvePlannedSettings(plan, base);
      const preserveModel = userPickedModelRef.current && Boolean(base.model?.trim());
      const preserveLoras =
        userPickedLorasRef.current && (base.lora?.length ?? 0) > 0;
      const preserveStyle =
        userPickedStyleRef.current &&
        Boolean(base.style?.trim()) &&
        base.style !== "image_edit" &&
        base.style !== merged.style;
      if (preserveModel) merged.model = base.model;
      if (preserveLoras) merged.lora = base.lora;
      if (preserveStyle) {
        merged.style = base.style;
        merged.styles = base.styles;
      }
      userPickedModelRef.current = preserveModel;
      userPickedLorasRef.current = preserveLoras;
      userPickedStyleRef.current = preserveStyle;
      patchSettings(merged);
      const targetMode =
        plan.mode && plan.mode !== "agent"
          ? plan.mode
          : ((appConfig?.ui.studio_mode ?? "generate") as StudioMode);
      if (plan.mode && plan.mode !== "agent" && plan.mode !== appConfig?.ui.studio_mode) {
        const currentMode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
        const keepGenerateTab =
          currentMode === "generate" && isGenerateReferenceWorkflow(merged);
        if (!keepGenerateTab) {
          await saveAppConfigPatch({ ui: { studio_mode: plan.mode } });
          setAgentPlannedMode(null);
        }
      }
      return { merged, targetMode };
    },
    [appConfig?.ui.studio_mode, patchSettings, saveAppConfigPatch],
  );

  const planApplyAndRun = useCallback(
    async ({ run }: { run: boolean }) => {
      const studioMode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
      setStatus(run ? "Planning and starting…" : "Planning route…");
      setPlanRunBusy(true);
      try {
        const sanitized = sanitizeEditFamilySettings(settingsRef.current, studioMode);
        const prepared = prepareGenerationFromAgentPrompt(sanitized, {
          selectedImagePath: selected?.images?.[0],
          modelGallery: modelGalleryAll,
        });
        if (prepared.applied.length) {
          patchSettings(prepared.settings);
        }
        const res = await dryRun(prepared.settings);
        const hint =
          prepared.applied.length > 0
            ? `Agent JSON mapped: ${prepared.applied.join(", ")}. `
            : "";
        const extra = prepared.hints.length > 0 ? `${prepared.hints[0]} ` : "";
        const planPayload =
          typeof res.plan === "object" && res.plan
            ? (res.plan as Record<string, unknown>)
            : {};
        const workflowBlueprint =
          typeof planPayload.workflow_blueprint === "object" && planPayload.workflow_blueprint
            ? (planPayload.workflow_blueprint as Record<string, unknown>)
            : Object.keys(planPayload).length > 0
              ? planPayload
              : { raw: res.plan ?? res };
        const readiness = dryRunReadinessSnapshot(planPayload, workflowBlueprint);
        const plan = buildPlanSnapshotFromDryRun({
          planPayload,
          workflowBlueprint,
          baseSettings: prepared.settings,
          studioMode,
          readiness,
          message: `${hint}${extra}`.trim() || "Dry-run plan",
        });
        const blocked = canRunApprovedPlan(plan, readiness);

        if (!run) {
          if (shouldSurfaceWorkflowPlan(plan)) {
            setAgentPlan(plan);
          } else {
            setAgentPlan(null);
          }
          setStatus(
            blocked.ok
              ? "Plan ready for review"
              : blocked.reason ?? "Plan needs setup before it can run",
          );
          return;
        }
        if (!blocked.ok) {
          if (run && planBlockedByLocalInputsOnly(readiness)) {
            setStatus(blocked.reason ?? "Complete required inputs in Settings, then Generate again");
            return;
          }
          if (shouldSurfaceWorkflowPlan(plan)) {
            setAgentPlan(plan);
          } else {
            setAgentPlan(null);
          }
          if (await promptMissingCompanionsDownloadRef.current?.()) {
            setStatus("Download required assets, then Generate again");
          } else {
            setStatus(blocked.reason ?? "Fix Settings, then Generate again");
          }
          return;
        }

        const { targetMode } = await applyPlanSnapshot(plan);

        if (run) {
          const mergedForCheck = sanitizeEditFamilySettings(
            settingsRef.current,
            targetMode,
          );
          const localReady = computeGenerateReadiness({
            workerReady: workerReadyRef.current,
            generating: false,
            engineState: engineState,
            engineLabel: "",
            prompt: mergedForCheck.prompt ?? "",
            model: mergedForCheck.model ?? "",
            modelDependenciesReady: true,
            missingCompanionCount: 0,
            settings: mergedForCheck,
            modelGallery: modelGalleryAll,
            studioMode: targetMode,
            inpaintMaskSyncing,
          });
          if (!localReady.ok && !localReady.missingCompanions) {
            setStatus(localReady.reason);
            return;
          }
        }

        if (await promptMissingCompanionsDownloadRef.current?.()) return;

        const finalPrepared = prepareGenerationFromAgentPrompt(settingsRef.current, {
          selectedImagePath: selected?.images?.[0],
          modelGallery: modelGalleryAll,
        });
        if (finalPrepared.applied.length || finalPrepared.hints.length) {
          patchSettings(finalPrepared.settings);
        }
        const mapped =
          finalPrepared.applied.length > 0
            ? `mapped ${finalPrepared.applied.join(", ")}`
            : undefined;
        const runHint =
          finalPrepared.hints.length > 0 ? finalPrepared.hints[0] : undefined;
        await startGeneration(finalPrepared.settings, {
          mapped,
          hint: runHint,
          studioMode: targetMode,
        });
      } catch (e) {
        setStatus(`Planning failed: ${String(e)}`);
      } finally {
        setPlanRunBusy(false);
      }
    },
    [
      appConfig?.ui.studio_mode,
      applyPlanSnapshot,
      modelGalleryAll,
      patchSettings,
      selected,
      startGeneration,
    ],
  );

  const runDryRun = useCallback(async () => {
    if ((appConfig?.ui.studio_mode ?? "generate") === "agent") {
      await runAgentInstruction(false);
      return;
    }
    await planApplyAndRun({ run: false });
  }, [appConfig?.ui.studio_mode, planApplyAndRun, runAgentInstruction]);

  const runEnhancePrompt = useCallback(async () => {
    const studioMode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
    if (studioMode === "agent") {
      setStatus("Switch to Generate, Edit, Inpaint, or Upscale to enhance prompts");
      return;
    }
    if (studioMode !== "generate") {
      setStatus("Manual prompt enhance is available in Generate mode only");
      return;
    }
    const current = settingsRef.current;
    const prompt = (current.prompt ?? "").trim();
    if (!prompt) {
      setStatus("Enter a prompt to enhance");
      return;
    }
    setEnhancePromptBusy(true);
    setStatus("Enhancing prompt for current model…");
    try {
      const sanitized = sanitizeEditFamilySettings(current, studioMode);
      const res = await enhanceStudioPrompt({
        ...sanitized,
        studio_mode: studioMode,
        ...enhancePrefsFromAppConfig(appConfig),
      });
      const patch: Partial<GenerationSettings> = { prompt: res.prompt };
      if (res.negative_prompt?.trim()) {
        patch.negative_prompt = res.negative_prompt;
      }
      patchSettings(patch);
      setStatus(res.hint ?? "Prompt enhanced");
    } catch (e) {
      setStatus(`Enhance failed: ${String(e)}`);
    } finally {
      setEnhancePromptBusy(false);
    }
  }, [appConfig, patchSettings]);

  const runDescribeImage = useCallback(
    async (imagePath?: string) => {
      const path = (
        imagePath ??
        resolveDescribeImagePath(settingsRef.current, {
          selectedImagePath: selected?.images?.[0],
          canvasPreviewPath: canvasPreviewPathRef.current,
          studioMode: (appConfig?.ui.studio_mode ?? "generate") as StudioMode,
        })
      ).trim();
      if (!path) {
        setStatus("Attach or select an image to describe");
        return;
      }
      setDescribeImageBusy(true);
      setStatus("Describing image…");
      try {
        const res = await describeImageToPrompt(path);
        if (!res.ok || !res.prompt) {
          setStatus(
            res.error === "empty_caption"
              ? "Describe returned no caption — try another image"
              : `Describe failed: ${res.error ?? "unknown"}`,
          );
          return;
        }
        patchSettings({ prompt: res.prompt });
        setStatus("Prompt filled from image description");
      } catch (e) {
        setStatus(`Describe failed: ${String(e)}`);
      } finally {
        setDescribeImageBusy(false);
      }
    },
    [appConfig?.ui.studio_mode, patchSettings, selected],
  );

  const runImportImageMetadata = useCallback(
    async (path: string) => {
      const normalized = path.trim();
      if (!normalized) return;
      setStatus("Reading image metadata…");
      try {
        const res = await importImageMetadata(normalized);
        if (!res.ok || !res.patch) {
          setStatus(
            res.error === "no_generation_metadata"
              ? "No DreamForge or A1111 metadata in this image"
              : "Could not import settings from image",
          );
          return;
        }
        patchSettings(mergeMetadataPatch(settingsRef.current, res.patch));
        setStatus("Imported prompt and settings from image metadata");
      } catch (e) {
        setStatus(`Metadata import failed: ${String(e)}`);
      }
    },
    [patchSettings],
  );

  const dismissAgentPlan = useCallback(() => {
    setAgentPlan(null);
    setAgentPlannedMode(null);
    setStatus("Plan dismissed");
  }, []);

  const applyAgentPlan = useCallback(async () => {
    const plan = agentPlanRef.current;
    if (!plan?.proposed || !Object.keys(plan.proposed).length) {
      setStatus("No plan settings to apply");
      return;
    }
    await applyPlanSnapshot(plan);
    setAgentPlan(null);
    setStatus("Route applied in Settings — adjust if needed, then Generate");
  }, [applyPlanSnapshot]);

  const runApprovedPlan = useCallback(async () => {
    const plan = agentPlanRef.current;
    if (!plan) {
      await planApplyAndRun({ run: true });
      return;
    }
    const blocked = canRunApprovedPlan(plan, plan.readiness);
    if (!blocked.ok) {
      if (await promptMissingCompanionsDownloadRef.current?.()) {
        setStatus("Download required assets, then Generate again");
      } else {
        setStatus(blocked.reason ?? "Plan is not ready yet");
      }
      return;
    }
    setPlanRunBusy(true);
    try {
      const { merged, targetMode } = await applyPlanSnapshot(plan);
      if (await promptMissingCompanionsDownloadRef.current?.()) return;
      const prepared = prepareGenerationFromAgentPrompt(merged, {
        selectedImagePath: selected?.images?.[0],
        modelGallery: modelGalleryAll,
      });
      if (prepared.applied.length || prepared.hints.length) {
        patchSettings(prepared.settings);
      }
      await startGeneration(prepared.settings, {
        mapped:
          prepared.applied.length > 0
            ? `mapped ${prepared.applied.join(", ")}`
            : undefined,
        hint: prepared.hints[0],
        studioMode: targetMode,
      });
    } catch (e) {
      setStatus(`Run plan failed: ${String(e)}`);
    } finally {
      setPlanRunBusy(false);
    }
  }, [
    applyPlanSnapshot,
    modelGalleryAll,
    patchSettings,
    planApplyAndRun,
    selected,
    startGeneration,
  ]);

  const runAutomationBatch = useCallback(
    async (runner: () => Promise<{ ok: boolean }>) => {
      if (generatingRef.current) {
        setStatus("Generation already in progress");
        return false;
      }
      setGenerating(true);
      generatingRef.current = true;
      setEngineState("generating");
      applyLiveProgress({
        progress: 0,
        title: "Running batch…",
        phase: "preparing",
      });
      try {
        const { ok } = await runner();
        return ok;
      } finally {
        setGenerating(false);
        generatingRef.current = false;
        setEngineState(workerReadyRef.current ? "ready" : "booting");
        setLiveProgress(null);
      }
    },
    [applyLiveProgress],
  );

  const runGenerateVariants = useCallback(
    async (count: number) => {
      const studioMode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
      if (studioMode !== "generate") return;
      if (await promptMissingCompanionsDownloadRef.current?.()) return;
      const n = Math.min(imageNumberMax, Math.max(1, Math.round(count)));
      const current = { ...settingsRef.current, image_number: 1 };
      const sanitized = sanitizeEditFamilySettings(current, studioMode);
      const prepared = prepareGenerationFromAgentPrompt(sanitized, {
        selectedImagePath: selected?.images?.[0],
        modelGallery: modelGalleryAll,
      });
      const enforced = enforceCreativeTaskSettings(
        { ...prepared.settings, image_number: 1 },
        {
          studioMode,
          gallery: modelGalleryAll,
          advancedMode: advancedMode,
          vramProfile:
            prepared.settings.vram_profile ?? settingsRef.current.vram_profile,
          vramGb,
          mpsAvailable,
        },
      );
      if (prepared.applied.length) {
        patchSettings(prepared.settings);
      }

      setStatus(`Generating ${n} variant(s)…`);
      await runAutomationBatch(async () => {
        const result = await runAutomation({
          type: "seed_batch",
          count: n,
          studio_mode: studioMode,
          template_id:
            enforced.template_id ?? defaultTemplateIdForMode(studioMode),
          base_settings: enforced,
        });
        if (result.status === "success") {
          setStatus(`Generated ${result.completed ?? n} variant(s)`);
          void refreshOutputs({ selectNewest: true });
          return { ok: true };
        }
        setStatus(
          `Variant batch failed${
            result.failed_at != null ? ` at job ${result.failed_at}` : ""
          }`,
        );
        return { ok: false };
      });
    },
    [
      advancedMode,
      appConfig?.ui.studio_mode,
      imageNumberMax,
      modelGalleryAll,
      mpsAvailable,
      patchSettings,
      refreshOutputs,
      runAutomationBatch,
      selected,
      vramGb,
    ],
  );

  const runGenerate = useCallback(async () => {
    const studioMode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
    if (studioMode !== "agent") {
      if (await promptMissingCompanionsDownloadRef.current?.()) return;
    }
    if (studioMode === "agent") {
      await runAgentInstruction(true);
      return;
    }
    const current = settingsRef.current;
    const usesWorkflowPlan =
      Boolean(current.execute_workflow_plan) &&
      Array.isArray(current.workflow_plan) &&
      current.workflow_plan.length > 0;
    if (studioMode !== "generate" || usesWorkflowPlan) {
      await planApplyAndRun({ run: true });
      return;
    }
    const sanitized = sanitizeEditFamilySettings(current, studioMode);
    const prepared = prepareGenerationFromAgentPrompt(sanitized, {
      selectedImagePath: selected?.images?.[0],
      modelGallery: modelGalleryAll,
    });
    if (prepared.applied.length) {
      patchSettings(prepared.settings);
    }
    const mapped =
      prepared.applied.length > 0
        ? `mapped ${prepared.applied.join(", ")}`
        : undefined;
    const runHint = prepared.hints.length > 0 ? prepared.hints[0] : undefined;
    await startGeneration(prepared.settings, {
      mapped,
      hint: runHint,
      studioMode,
    });
  }, [
    appConfig?.ui.studio_mode,
    modelGalleryAll,
    patchSettings,
    planApplyAndRun,
    runAgentInstruction,
    selected,
    startGeneration,
  ]);

  const runRestartEngine = useCallback(async () => {
    setRestarting(true);
    setEngineState("restarting");
    setWorkerReady(false);
    workerReadyRef.current = false;
    studioCatalogLoadedRef.current = false;
    setBootPhase("starting");
    setBootMessage("Restarting GPU engine…");
    setStatus("Restarting GPU engine…");
    try {
      const slot = settingsRef.current.vram_profile ?? "auto";
      await restartGpuWorker(slot);
      void syncDesktopVramProfile(slot);
      void getEngineStatus().then(applyEngineStatus);
      void loadStudioCatalog(true);
    } catch (e) {
      setEngineState("failed");
      await refreshWorkerLog();
      setBootMessage(String(e));
      setStatus(`Restart failed: ${plainErrorLine(String(e))}`);
    } finally {
      setRestarting(false);
    }
  }, [refreshWorkerLog, loadStudioCatalog, applyEngineStatus]);
  runRestartEngineRef.current = () => runRestartEngine();

  useEffect(() => {
    if (!workerReady || restarting || generatingRef.current) return;
    if (!vramRestartPendingRef.current) return;
    vramRestartPendingRef.current = false;
    void runRestartEngine();
  }, [settings.vram_profile, workerReady, restarting, runRestartEngine]);

  useEffect(() => {
    const mode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
    if (mode === "generate" || mode === "agent") {
      setStudioResources({ ready: true, missing: [] });
      return;
    }
    let cancelled = false;
    void checkStudioResources(
      mode,
      mode === "upscale" ? settings.upscale_method ?? undefined : undefined,
    )
      .then((res) => {
        if (cancelled) return;
        setStudioResources({
          ready: res.ready,
          missing: (res.missing ?? []) as ModelDependencyItem[],
        });
      })
      .catch(() => {
        if (!cancelled) setStudioResources({ ready: true, missing: [] });
      });
    return () => {
      cancelled = true;
    };
  }, [
    appConfig?.ui.studio_mode,
    settings.upscale_method,
    companionDownloadPhase,
  ]);

  useEffect(() => {
    const mode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
    if (mode !== "generate" && mode !== "agent") {
      setImagePromptResources({ ready: true, missing: [] });
      return;
    }
    const hasRef = Boolean(
      settings.reference_image?.trim() ||
        settings.input_image?.trim() ||
        settings.reference_images?.some((item) => item.trim()),
    );
    if (!hasRef) {
      setImagePromptResources({ ready: true, missing: [] });
      return;
    }
    let cancelled = false;
    void checkImagePromptResources()
      .then((res) => {
        if (cancelled) return;
        setImagePromptResources({
          ready: res.ready,
          missing: (res.missing ?? []) as ModelDependencyItem[],
        });
      })
      .catch(() => {
        if (!cancelled) setImagePromptResources({ ready: true, missing: [] });
      });
    return () => {
      cancelled = true;
    };
  }, [
    appConfig?.ui.studio_mode,
    settings.input_image,
    settings.reference_image,
    settings.reference_images,
    companionDownloadPhase,
  ]);

  const studioMode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
  const planSettingsSnapshot = useMemo(
    () => computePlanSettingsSnapshot(settings, studioMode),
    [settings, studioMode],
  );
  const editPlanState = useMemo(
    () => editFamilyPlanState(agentPlan, studioMode, planSettingsSnapshot),
    [agentPlan, studioMode, planSettingsSnapshot],
  );
  const describeImagePath = useMemo(
    () =>
      resolveDescribeImagePath(settings, {
        selectedImagePath: selected?.images?.[0],
        canvasPreviewPath: canvasPreviewPathRef.current,
        studioMode,
      }),
    [settings, selected, previewUrl, studioMode],
  );
  const generateReadiness = useMemo(
    () => {
      const mergedMissingCount = mergeDependencyItems(
        modelDependencies.missing,
        studioResources.missing,
        companionItemsFromActions(
          agentPlan?.readiness?.recommended_actions as RepairAction[] | undefined,
        ),
        companionItemsFromActions(lastError?.failureReport?.repair_actions),
        companionItemsFromActions(
          (lastError?.details?.recommended_actions as RepairAction[] | undefined) ?? [],
        ),
      ).length;
      return computeGenerateReadiness({
        workerReady,
        generating,
        engineState,
        engineLabel: engineLabel(engineState, bootMessage),
        prompt: settings.prompt ?? "",
        model: settings.model ?? "",
        modelDependenciesReady:
          modelDependencies.ready &&
          studioResources.ready &&
          mergedMissingCount === 0,
        missingCompanionCount: mergedMissingCount,
        studioMissingAssetCount: studioResources.missing.length,
        settings,
        modelGallery: modelGalleryAll,
        studioMode,
        editPlanState: isEditFamilyMode(studioMode) ? editPlanState : undefined,
        inpaintMaskSyncing,
      });
    },
    [
      workerReady,
      generating,
      engineState,
      bootMessage,
      settings,
      modelDependencies,
      studioResources,
      agentPlan,
      lastError,
      modelGalleryAll,
      studioMode,
      editPlanState,
      inpaintMaskSyncing,
    ],
  );
  const effectiveGenerateReadiness = useMemo(() => generateReadiness, [generateReadiness]);
  const mergedMissingDependencies = useMemo(
    () =>
      mergeDependencyItems(
        modelDependencies.missing,
        studioResources.missing,
        companionItemsFromActions(
          agentPlan?.readiness?.recommended_actions as RepairAction[] | undefined,
        ),
        companionItemsFromActions(lastError?.failureReport?.repair_actions),
        companionItemsFromActions(
          (lastError?.details?.recommended_actions as RepairAction[] | undefined) ?? [],
        ),
      ),
    [
      agentPlan,
      lastError,
      modelDependencies.missing,
      studioResources.missing,
    ],
  );
  const missingDownloadCount = mergedMissingDependencies.length;

  const runCancel = useCallback(async () => {
    setStatus("Cancelling…");
    try {
      await cancelGeneration();
      stopLogPoll();
      setGenerating(false);
      generatingRef.current = false;
      setJobId(null);
      setEngineState(workerReady ? "ready" : "failed");
      setStatus("Generation cancelled");
    } catch (e) {
      setStatus(`Cancel failed: ${String(e)}`);
    }
  }, [stopLogPoll, workerReady]);

  const attachReferenceImage = useCallback(
    async (path: string, mode: ReferenceImageMode) => {
      const resolved = await resolveReferenceImagePath(path);
      let studioMode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;

      const targetStudio: StudioMode | null =
        mode === "inpaint" && studioMode !== "inpaint"
          ? "inpaint"
          : mode === "upscale" && studioMode !== "upscale"
            ? "upscale"
            : mode === "reference" &&
                studioMode !== "generate" &&
                studioMode !== "edit" &&
                studioMode !== "agent" &&
                studioMode !== "inpaint"
              ? "edit"
              : null;

      if (targetStudio) {
        await setStudioModeRef.current(targetStudio);
        studioMode = targetStudio;
      }

      const activeModel = findGalleryModel(
        modelGalleryAll,
        settingsRef.current.model ?? "",
      );
      const family = activeModel?.family ?? "";
      const sid = activeSessionIdRef.current || DEFAULT_SESSION_ID;
      const outputFor = (suffix: string) =>
        outputPathForSession(
          sid,
          suffix === "upscale"
            ? "upscale"
            : suffix === "inpaint"
              ? "inpaint"
              : studioMode === "generate" && mode === "reference"
                ? "gen"
                : "edit",
        );

      const patch =
        studioMode === "generate" && mode === "reference"
          ? isSimpleExperience(uiExperience)
            ? buildEasyCreateReferencePatch(
                resolved,
                modelGalleryAll,
                outputFor,
                {
                  currentModel: settingsRef.current.model,
                  userPickedModel: userPickedModelRef.current,
                  modelFamily: family,
                  modelMissing: modelDependencies.missing,
                  studioMissing: studioResources.missing,
                  imagePromptMissing: imagePromptResources.missing,
                },
              )
            : buildGenerateIdentityReferencePatch(
                resolved,
                modelGalleryAll,
                outputFor,
                {
                  currentModel: settingsRef.current.model,
                  userPickedModel: userPickedModelRef.current,
                  modelFamily: family,
                },
              )
          : buildReferenceImagePatch(resolved, mode, outputFor, family, studioMode);
      if (patch.model && patch.model !== settingsRef.current.model) {
        userPickedModelRef.current = false;
      }
      if (mode !== "upscale") {
        if (
          settingsRef.current.edit_strength == null ||
          settingsRef.current.edit_strength <= 0
        ) {
          patch.edit_strength = defaultReferenceEditStrength(
            { ...settingsRef.current, ...patch },
            (patch.model ? findGalleryModel(modelGalleryAll, patch.model)?.family : family) ??
              family,
          );
        }
      }
      const mergedPatch = normalizeReferenceSettings(
        sanitizeSettingsForStudioMode(studioMode, {
          ...settingsRef.current,
          ...patch,
        }),
        studioMode,
      );
      patchSettings(mergedPatch);
      setAgentPlan(null);
      if (mode === "inpaint") {
        openInpaintMaskEditor();
        setStatus(
          uiExperience === "simple"
            ? `Attached ${referenceStatusLabel(mode, resolved)} — paint on the canvas`
            : `Attached ${referenceStatusLabel(mode, resolved)} — paint on the canvas or use full-screen mask tools`,
        );
      } else if (studioMode === "generate" && mode === "reference") {
        const routeModel = findGalleryModel(
          modelGalleryAll,
          patch.model ?? settingsRef.current.model ?? "",
        );
        const routeLabel =
          routeModel?.caption ?? routeModel?.engine_name ?? "selected model";
        setStatus(`Reference image attached — img2img with ${routeLabel}`);
      } else {
        setStatus(`Attached ${referenceStatusLabel(mode, resolved)}`);
      }
    },
    [appConfig?.ui.studio_mode, imagePromptResources.missing, modelDependencies.missing, modelGalleryAll, openInpaintMaskEditor, patchSettings, studioResources.missing, uiExperience],
  );

  const clearReferenceImage = useCallback(() => {
    patchSettings(buildClearReferenceImagePatch());
    setStatus("Reference image cleared");
  }, [patchSettings]);

  const attachExtraReferenceImage = useCallback(
    async (path: string) => {
      const resolved = await resolveReferenceImagePath(path);
      const studioMode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
      if (studioMode === "generate" && !isSimpleExperience(uiExperience)) {
        const patch = appendReferenceSlot(
          settingsRef.current,
          {
            path: resolved,
            role: "image_prompt",
            weight: settingsRef.current.reference_weight ?? 0.75,
            stop_at: settingsRef.current.cn_stop ?? 1,
          },
          studioMode,
        );
        if (!patch) {
          setStatus("Could not add reference slot (limit reached or invalid mix)");
          return;
        }
        patchSettings(
          normalizeReferenceSettings({ ...settingsRef.current, ...patch }, studioMode),
        );
        const count = coerceReferenceSlots(patch, studioMode).length;
        setStatus(`Added reference slot (${count} total)`);
        return;
      }
      const patch = appendExtraReferencePath(settingsRef.current, resolved);
      if (!Object.keys(patch).length) {
        setStatus("Control reference already attached");
        return;
      }
      patchSettings(patch);
      const count = (patch.reference_images ?? []).length;
      setStatus(`Added control reference (${count} total)`);
    },
    [appConfig?.ui.studio_mode, patchSettings, uiExperience],
  );

  const removeExtraReferenceImage = useCallback(
    (index: number) => {
      patchSettings(removeExtraReferenceAt(settingsRef.current, index));
      setStatus("Removed control reference");
    },
    [patchSettings],
  );

  const refreshModelDependencies = useCallback(async (modelName?: string) => {
    const model = (modelName ?? settingsRef.current.model ?? "").trim();
    const performance = settingsRef.current.performance ?? null;
    if (!model) {
      const empty = { missing: [] as ModelDependencyItem[], ready: true };
      setModelDependencies(empty);
      return empty;
    }
    try {
      const res = await checkModelDependencies(
        model,
        performance,
      );
      const next = {
        missing: res.missing ?? [],
        ready: res.ready ?? (res.missing?.length ?? 0) === 0,
      };
      setModelDependencies(next);
      return next;
    } catch {
      const fallback = { missing: [] as ModelDependencyItem[], ready: true };
      setModelDependencies(fallback);
      return fallback;
    }
  }, []);

  const setStudioMode = useCallback(
    async (mode: StudioMode) => {
      if (mode === "agent" && (appConfig?.ui.experience ?? "pro") === "simple") {
        mode = "generate";
      }
      const previousMode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
      if (mode !== previousMode) {
        userPickedModelRef.current = false;
      }
      await saveAppConfigPatch({ ui: { studio_mode: mode } });
      setAgentPlannedMode(null);
      setAgentPlan(null);
      if (mode === "generate") {
        userPickedLorasRef.current = false;
        userPickedStyleRef.current = false;
        const sanitized = sanitizeSettingsForStudioMode(
          "generate",
          settingsRef.current,
        );
        const resetPatch = buildClearReferenceImagePatch();
        const ideogram = selectIdeogram4GalleryModel(modelGalleryAll);
        const hasIntentionalReference = Boolean(
          sanitized.input_image?.trim() ||
            sanitized.reference_image?.trim() ||
            sanitized.reference_images?.some((item) => item.trim()),
        );
        const hasStaleCarryover = Boolean(
          settingsRef.current.upscale_image?.trim() ||
            settingsRef.current.inpaint_mask_path?.trim() ||
            settingsRef.current.edit_type === "inpaint" ||
            settingsRef.current.upscale_method?.trim() ||
            (settingsRef.current.edit_type &&
              settingsRef.current.edit_type !== "auto" &&
              !hasIntentionalReference),
        );
        if (ideogram && !hasIntentionalReference) {
          patchSettings({
            ...resetPatch,
            model: ideogram.engine_name,
            ...ideogram4SettingsDefaults(),
          });
          void applyModelProfile(ideogram);
        } else if (hasIntentionalReference) {
          patchSettings(sanitized);
        } else if (hasStaleCarryover) {
          patchSettings(resetPatch);
        }
        setStatus("Generation mode - model library selection is unlocked");
        return;
      }
      if (mode === "agent") {
        setStatus("Agent mode - describe the workflow and let the agent configure it");
        return;
      }

      const plan = planStudioModeSwitch({
        studioMode: mode,
        previousMode,
        gallery: modelGalleryAll,
        settings: settingsRef.current,
        selectedImage: selected?.images?.[0],
        userPickedModel: userPickedModelRef.current,
        advancedMode,
      });

      if (plan.refUpdates.userPickedModel !== undefined) {
        userPickedModelRef.current = plan.refUpdates.userPickedModel;
      }
      if (plan.refUpdates.userPickedLoras !== undefined) {
        userPickedLorasRef.current = plan.refUpdates.userPickedLoras;
      }
      if (plan.refUpdates.userPickedStyle !== undefined) {
        userPickedStyleRef.current = plan.refUpdates.userPickedStyle;
      }

      const mergedSettings = { ...settingsRef.current, ...plan.patch };
      const routedSettings = await enforceCreativeTaskSettingsRemote(mergedSettings, {
        studioMode: mode,
        gallery: modelGalleryAll,
        advancedMode,
        vramProfile: mergedSettings.vram_profile ?? settingsRef.current.vram_profile,
        vramGb,
        mpsAvailable,
        selectedImage: selected?.images?.[0],
        userPickedModel: userPickedModelRef.current,
      });
      patchSettings(routedSettings);

      if (
        plan.profileItem &&
        (plan.useIdeogramRoute || plan.useQwenEditRoute || mode === "edit")
      ) {
        void applyModelProfile(plan.profileItem);
      }
      if (mode === "inpaint" || mode === "edit" || mode === "upscale") {
        let studioMissing: ModelDependencyItem[] = [];
        try {
          const studioRes = await checkStudioResources(
            mode,
            mode === "upscale"
              ? settingsRef.current.upscale_method ?? undefined
              : undefined,
          );
          studioMissing = (studioRes.missing ?? []) as ModelDependencyItem[];
          setStudioResources({
            ready: studioRes.ready ?? studioMissing.length === 0,
            missing: studioMissing,
          });
        } catch {
          /* studio resource probe is best-effort */
        }
        const effectiveModel = routedSettings.model ?? plan.patch.model ?? plan.routedModel;
        if (effectiveModel) {
          void refreshModelDependencies(effectiveModel);
        }
        const prepOpts = { studioMode: mode, studioMissing };
        if (workerReadyRef.current) {
          void promptMissingCompanionsDownloadRef.current?.(prepOpts);
        } else {
          pendingCompanionPrepRef.current = prepOpts;
        }
      } else if (plan.routedModel) {
        void refreshModelDependencies(plan.routedModel);
      }
      setStatus(plan.statusMessage);
    },
    [
      advancedMode,
      appConfig?.ui.studio_mode,
      applyModelProfile,
      modelGalleryAll,
      mpsAvailable,
      patchSettings,
      refreshModelDependencies,
      saveAppConfigPatch,
      selected,
      vramGb,
    ],
  );
  setStudioModeRef.current = setStudioMode;

  const attachImageForCreativeMode = useCallback(
    async (
      mode: "edit" | "inpaint" | "upscale",
      imagePath?: string | null,
    ) => {
      userPickedModelRef.current = false;
      const path = (imagePath ?? selected?.images?.[0] ?? "").trim();
      if (!path) {
        setStatus("Select a session image first");
        return;
      }
      setAgentPlan(null);
      const currentMode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
      if (currentMode !== mode) {
        await setStudioMode(mode);
        if (mode === "inpaint") {
          openInpaintMaskEditor();
          setStatus(
            uiExperience === "simple"
              ? "Attached image — paint the fix region on the canvas"
              : "Attached image — paint on the canvas or open full-screen mask tools",
          );
        } else {
          setStatus(
            mode === "edit"
              ? "Edit mode — describe your change and generate"
              : "Enhance mode — image attached",
          );
        }
      }
      const mapped: ReferenceImageMode =
        mode === "upscale" ? "upscale" : mode === "inpaint" ? "inpaint" : "reference";
      const resolved = await resolveReferenceImagePath(path);
      const activeModel = findGalleryModel(
        modelGalleryAll,
        settingsRef.current.model ?? "",
      );
      const family = activeModel?.family ?? "";
      patchSettings(
        buildReferenceImagePatch(
          resolved,
          mapped,
          (suffix) =>
            outputPathForSession(
              activeSessionIdRef.current || DEFAULT_SESSION_ID,
              suffix === "upscale"
                ? "upscale"
                : suffix === "inpaint"
                  ? "inpaint"
                  : "edit",
            ),
          family,
          mode,
        ),
      );
      if (mapped === "inpaint") {
        if (currentMode === mode) {
          patchSettings({ inpaint_mask_path: undefined });
          openInpaintMaskEditor();
        }
        setStatus(
          uiExperience === "simple"
            ? `Attached ${referenceStatusLabel(mapped, resolved)} — paint on the canvas`
            : `Attached ${referenceStatusLabel(mapped, resolved)} - paint a fresh mask`,
        );
      } else if (currentMode === mode) {
        setStatus(`Attached ${referenceStatusLabel(mapped, resolved)}`);
      }
    },
    [
      appConfig?.ui.studio_mode,
      modelGalleryAll,
      openInpaintMaskEditor,
      patchSettings,
      selected,
      setStudioMode,
      uiExperience,
    ],
  );

  const useSelectedImageFor = useCallback(
    async (mode: "edit" | "inpaint" | "upscale") => {
      await attachImageForCreativeMode(mode);
    },
    [attachImageForCreativeMode],
  );

  const historyEditThis = useCallback(
    async (item: OutputItem) => {
      const path = item.images[0];
      if (!path) {
        setStatus("No image in this history entry");
        return;
      }
      selectOutput(item);
      void setCanvasPreviewFromPath(path, { force: true });
      await attachImageForCreativeMode("edit", path);
    },
    [attachImageForCreativeMode, selectOutput, setCanvasPreviewFromPath],
  );

  const historyFixRegion = useCallback(
    async (item: OutputItem) => {
      const path = item.images[0];
      if (!path) {
        setStatus("No image in this history entry");
        return;
      }
      selectOutput(item);
      void setCanvasPreviewFromPath(path, { force: true });
      await attachImageForCreativeMode("inpaint", path);
    },
    [attachImageForCreativeMode, selectOutput, setCanvasPreviewFromPath],
  );

  const historyEnhance = useCallback(
    async (item: OutputItem) => {
      const path = item.images[0];
      if (!path) {
        setStatus("No image in this history entry");
        return;
      }
      selectOutput(item);
      void setCanvasPreviewFromPath(path, { force: true });
      await attachImageForCreativeMode("upscale", path);
    },
    [attachImageForCreativeMode, selectOutput, setCanvasPreviewFromPath],
  );

  const runVaryImage = useCallback(
    async (amount: VaryAmount) => {
      const path = (selected?.images?.[0] ?? "").trim();
      if (!path) {
        setStatus("Select a result image to vary");
        return;
      }
      if (await promptMissingCompanionsDownloadRef.current?.()) return;

      const studioMode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
      if (studioMode !== "generate") {
        await setStudioMode("generate");
      }

      const resolved = await resolveReferenceImagePath(path);
      const activeModel = findGalleryModel(
        modelGalleryAll,
        settingsRef.current.model ?? "",
      );
      const family = activeModel?.family ?? "";
      const sid = activeSessionIdRef.current || DEFAULT_SESSION_ID;
      const patch = buildVarySettingsPatch(
        resolved,
        amount,
        (suffix) =>
          outputPathForSession(
            sid,
            suffix === "upscale"
              ? "upscale"
              : suffix === "inpaint"
                ? "inpaint"
                : suffix === "edit"
                  ? "edit"
                  : "gen",
          ),
        family,
      );
      const nextSettings: GenerationSettings = {
        ...settingsRef.current,
        ...patch,
      };
      patchSettings(patch);
      setStatus(
        amount === "subtle"
          ? "Vary subtle — generating light variation…"
          : "Vary strong — generating stronger variation…",
      );
      await startGeneration(nextSettings, { studioMode: "generate" });
    },
    [
      appConfig?.ui.studio_mode,
      modelGalleryAll,
      patchSettings,
      selected,
      setStudioMode,
      startGeneration,
    ],
  );

  const runAutoEnhance = useCallback(
    async (target: EnhanceTarget, options?: { postUpscale?: boolean }) => {
      const path = (selected?.images?.[0] ?? "").trim();
      if (!path) {
        setStatus("Select a result image to enhance");
        return;
      }
      if (await promptMissingCompanionsDownloadRef.current?.()) return;

      let studioMode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
      if (studioMode !== "upscale" && studioMode !== "edit") {
        await setStudioMode("upscale");
        studioMode = "upscale";
      }

      const resolved = await resolveReferenceImagePath(path);
      const patch = patchForEnhanceTarget(target, resolved, {
        postUpscale: options?.postUpscale,
        detectionPrompt: settingsRef.current.enhance_detection_prompt,
        detailPrompt: settingsRef.current.detail_prompt,
      });
      const nextSettings: GenerationSettings = {
        ...settingsRef.current,
        ...patch,
      };
      patchSettings(patch);
      setStatus(`Auto-fix ${target} — generating…`);
      await startGeneration(nextSettings, { studioMode });
    },
    [
      appConfig?.ui.studio_mode,
      patchSettings,
      selected,
      setStudioMode,
      startGeneration,
    ],
  );

  const resolveMergedMissingDependencies = useCallback(
    async (opts?: MissingDepsResolveOptions) => {
    const plan = agentPlanRef.current;
    const plannedModel =
      typeof plan?.proposed?.model === "string" ? plan.proposed.model : "";
    const fromErrorReport = companionItemsFromActions(
      lastError?.failureReport?.repair_actions,
    );
    const fromErrorDetails = companionItemsFromActions(
      (lastError?.details?.recommended_actions as RepairAction[] | undefined) ?? [],
    );
    const model = ((settingsRef.current.model ?? "") || plannedModel).trim();
    let fromModel = modelDependencies.missing;
    if (model) {
      try {
        const res = await checkModelDependencies(
          model,
          settingsRef.current.performance ?? null,
        );
        fromModel = res.missing ?? [];
        setModelDependencies({
          missing: fromModel,
          ready: res.ready ?? fromModel.length === 0,
        });
      } catch {
        fromModel = [];
      }
    }
    let studioMissing = opts?.studioMissing ?? studioResources.missing;
    const studioMode =
      opts?.studioMode ??
      ((appConfig?.ui.studio_mode ?? "generate") as StudioMode);
    if (
      !opts?.studioMissing &&
      (studioMode === "inpaint" || studioMode === "edit" || studioMode === "upscale")
    ) {
      try {
        const studioRes = await checkStudioResources(
          studioMode,
          studioMode === "upscale"
            ? settingsRef.current.upscale_method ?? undefined
            : undefined,
        );
        studioMissing = (studioRes.missing ?? []) as ModelDependencyItem[];
        setStudioResources({
          ready: studioRes.ready ?? studioMissing.length === 0,
          missing: studioMissing,
        });
      } catch {
        /* keep cached studioMissing */
      }
    }
    const fromPlan = companionItemsFromActions(
      plan?.readiness?.recommended_actions as RepairAction[] | undefined,
    );
    const fromCustomNodes = customNodeItemsFromActions(
      lastError?.failureReport?.repair_actions,
    );
    const merged = mergeDependencyItems(
      fromModel,
      studioMissing,
      fromPlan,
      fromErrorReport,
      fromErrorDetails,
      fromCustomNodes,
    );
    return { model: model || "workflow-assets", merged };
  },
    [appConfig?.ui.studio_mode, lastError, modelDependencies.missing, studioResources.missing],
  );

  const promptMissingCompanionsDownload = useCallback(
    async (opts?: MissingDepsResolveOptions): Promise<boolean> => {
      if (companionDownloadOpen || companionDownloadBusy || companionBootstrapBusy) {
        return mergedMissingDependencies.length > 0;
      }
      if (!workerReadyRef.current) {
        if (opts) {
          pendingCompanionPrepRef.current = opts;
        }
        setStatus(COMFY_NOT_READY_REASON);
        return false;
      }
      const plan = agentPlanRef.current;
      const plannedModel =
        typeof plan?.proposed?.model === "string" ? plan.proposed.model : "";
      const model = ((settingsRef.current.model ?? "") || plannedModel).trim();
      const studioMode =
        opts?.studioMode ??
        ((appConfig?.ui.studio_mode ?? "generate") as StudioMode);
      const needsStudio =
        studioMode === "inpaint" || studioMode === "edit" || studioMode === "upscale";
      const prepareLabel = studioPrepareFallbackLabel(studioMode);

      const currentSettings = settingsRef.current;
      const templateId =
        currentSettings.template_id ??
        defaultTemplateIdForMode(
          studioMode,
          currentSettings.post_upscale_enabled,
        );
      const upscaleForPrep =
        studioMode === "upscale"
          ? currentSettings.upscale_method ?? ""
          : currentSettings.post_upscale_enabled
            ? currentSettings.post_upscale ?? "ultimate_sd_upscale"
            : "";
      const prepCacheKey = [
        model,
        studioMode,
        templateId ?? "",
        currentSettings.performance ?? "",
        upscaleForPrep,
      ].join("|");
      const prepCached = assetPrepReadyRef.current;
      if (
        prepCached?.key === prepCacheKey &&
        Date.now() - prepCached.at < ASSET_PREP_CACHE_MS
      ) {
        return false;
      }

      setCompanionBootstrapBusy(true);
      setCompanionBootstrapMessage(prepareLabel);
      setBootPhase("preparing_tools");
      setStatus(prepareLabel);
      try {
        const result = await ensureCreativeTaskReady({
          model: model || undefined,
          studio_mode: needsStudio ? studioMode : undefined,
          upscale_method:
            studioMode === "upscale"
              ? currentSettings.upscale_method ?? undefined
              : currentSettings.post_upscale_enabled
                ? currentSettings.post_upscale ?? "ultimate_sd_upscale"
                : undefined,
          performance: currentSettings.performance ?? null,
          auto_download_tier_a: true,
          auto_download_tier_b: false,
          auto_install_nodes: true,
          template_id: templateId ?? null,
        });
        const lastSetup = result.node_setup?.[result.node_setup.length - 1];
        if (lastSetup) {
          setCompanionBootstrapMessage(lastSetup);
          setStatus(lastSetup);
        }

        if (result.ready) {
          assetPrepReadyRef.current = { key: prepCacheKey, at: Date.now() };
          if (model) {
            setModelDependencies({
              ready: true,
              missing: (result.missing ?? []) as ModelDependencyItem[],
            });
          }
          if (needsStudio) {
            setStudioResources({
              ready: true,
              missing: [],
            });
          }
          if ((result.downloaded_tier_a ?? 0) > 0) {
            setStatus(`Prepared ${result.downloaded_tier_a} helper asset(s)`);
            void loadStudioCatalog(true);
          } else if (model) {
            void refreshModelDependencies(model);
          }
          setLastError((prev) =>
            prev?.code === "missing_model_dependencies" ||
            prev?.code === "missing_custom_node_pack"
              ? null
              : prev,
          );
          return false;
        }

        if (model) {
          await refreshModelDependencies(model);
        }
        if (needsStudio) {
          const studioRes = await checkStudioResources(
            studioMode,
            studioMode === "upscale"
              ? settingsRef.current.upscale_method ?? undefined
              : undefined,
          );
          setStudioResources({
            ready: studioRes.ready ?? (studioRes.missing?.length ?? 0) === 0,
            missing: (studioRes.missing ?? []) as ModelDependencyItem[],
          });
        }

        const nodePacks = (result.missing_node_packs ?? []) as ModelDependencyItem[];
        if (nodePacks.length > 0) {
          startCompanionDownload(model || "workflow-assets", nodePacks);
          setStatus(`Review install approval for ${nodePacks.length} custom node pack(s)`);
          return true;
        }

        const tierB = (result.missing_tier_b ?? []) as ModelDependencyItem[];
        const tierAStill = (result.missing_tier_a ?? []) as ModelDependencyItem[];

        if (tierB.length > 0) {
          startCompanionDownload(model || "workflow-assets", tierB);
          setStatus(`Review download approval for ${tierB.length} large asset(s)`);
          return true;
        }

        if (tierAStill.length > 0) {
          setStatus(`Downloading ${tierAStill.length} helper asset(s)…`);
          try {
            await downloadCompanionEntries(tierAStill);
            if (model) {
              await refreshModelDependencies(model);
            }
            if (needsStudio) {
              const studioRes = await checkStudioResources(
                studioMode,
                studioMode === "upscale"
                  ? settingsRef.current.upscale_method ?? undefined
                  : undefined,
              );
              setStudioResources({
                ready: studioRes.ready ?? (studioRes.missing?.length ?? 0) === 0,
                missing: (studioRes.missing ?? []) as ModelDependencyItem[],
              });
            }
            const recheck = await ensureCreativeTaskReady({
              model: model || undefined,
              studio_mode: needsStudio ? studioMode : undefined,
              upscale_method:
                studioMode === "upscale"
                  ? settingsRef.current.upscale_method ?? undefined
                  : settingsRef.current.post_upscale_enabled
                    ? settingsRef.current.post_upscale ?? "ultimate_sd_upscale"
                    : undefined,
              performance: settingsRef.current.performance ?? null,
              auto_download_tier_a: true,
              auto_download_tier_b: true,
              auto_install_nodes: true,
              template_id:
                settingsRef.current.template_id ??
                defaultTemplateIdForMode(
                  studioMode,
                  settingsRef.current.post_upscale_enabled,
                ) ??
                null,
            });
            if (recheck.ready) {
              assetPrepReadyRef.current = { key: prepCacheKey, at: Date.now() };
              setStatus(
                (recheck.downloaded_tier_a ?? 0) > 0
                  ? `Prepared ${recheck.downloaded_tier_a} helper asset(s)`
                  : "Required assets are ready",
              );
              void loadStudioCatalog(true);
              setLastError((prev) =>
                prev?.code === "missing_model_dependencies" ? null : prev,
              );
              return false;
            }
            const still = (recheck.missing_tier_a ?? []) as ModelDependencyItem[];
            setStatus(
              still.length
                ? `Could not download ${still.length} helper asset(s) — check network or model paths in Settings`
                : "Some required assets are still missing",
            );
          } catch (e) {
            setStatus(`Helper download failed: ${String(e)}`);
          }
          return false;
        }

        const { merged: stillMissing } = await resolveMergedMissingDependencies(opts);
        if (stillMissing.length > 0) {
          startCompanionDownload(model || "workflow-assets", stillMissing);
          setStatus(`Review download approval for ${stillMissing.length} required asset(s)`);
          return true;
        }
        return false;
      } catch (e) {
        setStatus(`Could not prepare assets: ${String(e)}`);
        const { merged } = await resolveMergedMissingDependencies(opts);
        if (merged.length === 0) return false;
        startCompanionDownload(model || "workflow-assets", merged);
        return true;
      } finally {
        setCompanionBootstrapBusy(false);
        setCompanionBootstrapMessage("");
      }
    },
  [
    appConfig?.ui.studio_mode,
    companionBootstrapBusy,
    companionDownloadBusy,
    companionDownloadOpen,
    loadStudioCatalog,
    mergedMissingDependencies.length,
    refreshModelDependencies,
    resolveMergedMissingDependencies,
    startCompanionDownload,
  ],
  );
  promptMissingCompanionsDownloadRef.current = promptMissingCompanionsDownload;
  verifyCompanionDownloadsRef.current = async () => {
    const { merged } = await resolveMergedMissingDependencies();
    return { ready: merged.length === 0, stillMissing: merged };
  };

  const downloadMissingCompanions = useCallback(async () => {
    const plan = agentPlanRef.current;
    const plannedModel =
      typeof plan?.proposed?.model === "string" ? plan.proposed.model : "";
    const fromErrorReport = companionItemsFromActions(
      lastError?.failureReport?.repair_actions,
    );
    const fromErrorDetails = companionItemsFromActions(
      (lastError?.details?.recommended_actions as RepairAction[] | undefined) ?? [],
    );
    const model = ((settingsRef.current.model ?? "") || plannedModel).trim();
    if (!model && fromErrorReport.length === 0 && fromErrorDetails.length === 0) {
      setStatus("Select a model first");
      return;
    }
    if (!workerReadyRef.current) {
      setStatus(COMFY_NOT_READY_REASON);
      return;
    }
    const { merged } = await resolveMergedMissingDependencies();
    if (merged.length === 0) {
      setStatus("All companion files are already present");
      return;
    }
    startCompanionDownload(model || "workflow-assets", merged);
  }, [
    lastError,
    resolveMergedMissingDependencies,
    startCompanionDownload,
  ]);

  useEffect(() => {
    if (companionDownloadPhase !== "done" && companionDownloadPhase !== "error") {
      return;
    }
    const model = settings.model?.trim();
    const mode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
    void (async () => {
      if (model) {
        const deps = await refreshModelDependencies(model);
        if (deps.ready && companionDownloadPhase === "done") {
          setLastError((prev) =>
            prev?.code === "missing_model_dependencies" ||
            prev?.code === "missing_custom_node_pack"
              ? null
              : prev,
          );
        } else if (companionDownloadPhase === "error" && !deps.ready) {
          setLastError(
            describeError({
              code: "missing_model_dependencies",
              message: `Still missing ${deps.missing.length} companion file(s).`,
            }),
          );
        }
      }
      if (mode === "inpaint" || mode === "edit" || mode === "upscale") {
        try {
          const studioRes = await checkStudioResources(
            mode,
            mode === "upscale"
              ? settingsRef.current.upscale_method ?? undefined
              : undefined,
          );
          setStudioResources({
            ready: studioRes.ready ?? (studioRes.missing?.length ?? 0) === 0,
            missing: (studioRes.missing ?? []) as ModelDependencyItem[],
          });
        } catch {
          /* keep cached studio state */
        }
      }
      const { merged } = await resolveMergedMissingDependencies();
      if (merged.length === 0 && companionDownloadPhase === "done") {
        setStatus("Companion files ready — you can generate now");
        void loadStudioCatalog(true);
      } else if (merged.length > 0 && companionDownloadPhase === "done") {
        setStatus(
          `Still missing ${merged.length} asset(s) — close the download log and retry`,
        );
      } else if (merged.length > 0 && companionDownloadPhase === "error") {
        setStatus("Some companion downloads failed — see download log");
      }
    })();
  }, [
    companionDownloadPhase,
    settings.model,
    appConfig?.ui.studio_mode,
    refreshModelDependencies,
    resolveMergedMissingDependencies,
    loadStudioCatalog,
  ]);

  const lowerVramProfileHandler = useCallback(() => {
    const current = settingsRef.current.vram_profile;
    const base = !current || current === "auto"
      ? effectiveVramProfileRef.current
      : current;
    const next = lowerVramProfile(base);
    patchSettings({ vram_profile: next });
    setStatus(`VRAM profile set to ${next}`);
  }, [patchSettings]);

  const modelDepsDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (modelDepsDebounceRef.current) {
      clearTimeout(modelDepsDebounceRef.current);
    }
    modelDepsDebounceRef.current = setTimeout(() => {
      void refreshModelDependencies(settings.model);
    }, 450);
    return () => {
      if (modelDepsDebounceRef.current) {
        clearTimeout(modelDepsDebounceRef.current);
      }
    };
  }, [settings.model, settings.performance, refreshModelDependencies]);

  useEffect(() => {
    assetPrepReadyRef.current = null;
  }, [settings.model, settings.performance, appConfig?.ui.studio_mode]);

  const referenceModelFamily = useMemo(() => {
    const item = findGalleryModel(modelGalleryAll, settings.model ?? "");
    return item?.family ?? "";
  }, [modelGalleryAll, settings.model]);

  const mentionTargets = useMemo(() => {
    const models = modelGalleryAll.map((m) => ({
      kind: "model" as const,
      label: modelBasename(m.caption),
      value: safeText(m.engine_name),
    }));
    const styles = styleRecipes.slice(0, 150).map((recipe) => ({
      kind: "style" as const,
      label: safeText(recipe.original_name)
        ? safeText(recipe.original_name).replace(/^Style:\s*/, "")
        : safeText(recipe.id, "Style").replace(/_/g, " "),
      value: safeText(recipe.id),
    }));
    return [...models, ...styles];
  }, [modelGalleryAll, styleRecipes]);

  const agentRuntimeLabel = useMemo(() => {
    const agent = appConfig?.agent;
    if (!agent) return "Local reasoning runtime";
    const provider = agentProviders.find((item) => item.id === agent.provider);
    const label = provider?.label ?? agent.provider ?? "Local runtime";
    const model = agent.model ? ` · ${agent.model}` : "";
    return `${label}${model}`;
  }, [agentProviders, appConfig]);

  const companionAssetsBusy = companionDownloadBusy || companionBootstrapBusy;

  return {
    outputs,
    sessions,
    activeSessionId,
    switchSession,
    createSession,
    selected,
    setSelected: selectOutput,
    previewUrl,
    liveProgress,
    settings,
    patchSettings,
    setStyle,
    activeModelLabel,
    referenceModelFamily,
    inventory,
    generating,
    jobId,
    logJobId: jobId ?? lastJobId,
    generationLog,
    agentPlan,
    agentTranscript,
    agentRuntimeLabel,
    planRunBusy,
    applyAgentPlan,
    runApprovedPlan,
    dismissAgentPlan,
    clearAgentTranscript: () => setAgentTranscript([]),
    status,
    engineState,
    workerReady,
    bootMessage,
    bootPhase,
    gpuName,
    vramGb,
    mpsAvailable,
    workerLogTail,
    restarting,
    runRestartEngine,
    lastError,
    dismissLastError: () => setLastError(null),
    warnings,
    dismissWarning: (code: string) =>
      setWarnings((prev) => prev.filter((w) => w.code !== code)),
    dismissAllWarnings: () => setWarnings([]),
    modelDependencies,
    studioResources,
    missingDownloadCount,
    companionDownloadBusy: companionAssetsBusy,
    companionBootstrapBusy,
    companionBootstrapMessage,
    creativeTask,
    refreshModelDependencies,
    downloadMissingCompanions,
    companionDownload,
    lowerVramProfile: lowerVramProfileHandler,
    canGenerate: effectiveGenerateReadiness.ok,
    companionBlockedOnly: effectiveGenerateReadiness.companionBlockedOnly,
    generateBlockReason: effectiveGenerateReadiness.reason,
    needsCompanionDownload: effectiveGenerateReadiness.missingCompanions,
    uiDefaults,
    modelGallery,
    loraGallery,
    modelFilter,
    setModelFilter,
    loraFilter,
    setLoraFilter,
    profileHints,
    galleryLoading,
    userStyleProfile,
    userStyleProfilePath,
    setUserStyleMemoryEnabled,
    clearUserStyleMemory,
    exportUserStyleMemory,
    refreshUserStyleProfile,
    selectModelGallery,
    toggleLoraGallery,
    styleRecipes,
    aspectPresets: resolveAspectPresets(uiDefaults?.aspect_ratios),
    mentionTargets,
    runDryRun,
    runEnhancePrompt,
    enhancePromptBusy,
    runDescribeImage,
    describeImageBusy,
    describeImagePath,
    runImportImageMetadata,
    runGenerate,
    runGenerateVariants,
    runAutomationBatch,
    runCancel,
    useSelectedImageFor,
    attachReferenceImage,
    attachExtraReferenceImage,
    removeExtraReferenceImage,
    clearReferenceImage,
    refreshOutputs,
    loadMoreOutputs,
    outputsTotal,
    outputsLoaded: outputs.length,
    outputsHasMore,
    outputsLoading,
    outputSearch,
    setOutputSearch,
    historyScrollToken,
    reuseOutputPrompt,
    historyEditThis,
    historyFixRegion,
    historyEnhance,
    runVaryImage,
    runAutoEnhance,
    openOutputInExplorer,
    copyOutputPath,
    deleteOutputManifest,
    deleteOutputImageFile,
    deleteOutputSession,
    refreshStudioCatalog: () => loadStudioCatalog(true),
    studioSettings,
    saveStudioSettings: saveStudioSettingsPatch,
    appConfig,
    uiExperience,
    advancedMode,
    studioMode: (appConfig?.ui.studio_mode ?? "generate") as StudioMode,
    editPlanState,
    agentPlannedMode,
    setStudioMode,
    agentProviders,
    agentProviderTest,
    agentProviderBusy,
    saveAppConfig: saveAppConfigPatch,
    testAgentProvider: runAgentProviderTest,
    imageNumberMax,
    inpaintMaskOpen,
    setInpaintMaskOpen,
    inpaintMaskSyncing,
    setInpaintMaskSyncing,
    inpaintCanvasFocus,
    setInpaintCanvasFocus,
    openInpaintMaskEditor,
    openInpaintMaskModal,
    setInpaintMaskPath: (path: string) =>
      patchSettings({ inpaint_mask_path: path }),
    setStatusMessage: setStatus,
    ensureCreativeAssetsReady: promptMissingCompanionsDownload,
  };
}
