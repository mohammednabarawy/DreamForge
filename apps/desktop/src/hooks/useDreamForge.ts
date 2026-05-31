import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  bootPhaseLabel,
  engineLabel,
  generationPhaseLabel,
  type EngineState,
} from "../lib/engine";
import {
  describeError,
  describeWarning,
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
  selectCuratedModelForMode,
  type StudioMode,
  type StyleRecipe,
} from "../lib/model-selection";
import { excerptPrompt, HISTORY_PAGE_SIZE } from "../lib/historyUtils";
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
  loadSessionRegistry,
  saveActiveSessionId,
  saveSessionRegistry,
} from "../lib/historyStorage";
import {
  cancelGeneration,
  checkModelDependencies,
  dryRun,
  GenerationSettings,
  getEngineStatus,
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
import {
  computeGenerateReadiness,
  vramProfileFromHardware,
} from "../lib/generationReadiness";
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
  clearUserStyleProfile,
  exportUserStyleProfile,
  getUserStyleProfile,
  getAppConfig,
  getLoraInfo,
  getStudioSettings,
  deleteReferencePack,
  deleteIdentity,
  listAgentProviders,
  listIdentities,
  listReferencePacks,
  planAgentInstruction,
  saveAppConfig,
  saveIdentity,
  saveReferencePack,
  saveStudioSettings,
  saveUserStyleProfile,
  testAgentProvider,
  type AgentPlanSnapshot,
  type AgentTranscriptMessage,
  type AgentProviderPreset,
  type AgentProviderTestResult,
  type DreamForgeAppConfig,
  type DreamForgeAppConfigPatch,
  type IdentityRecord,
  type ReferencePack,
  type StudioSettings,
  type UserStyleProfile,
  type WorkflowReadiness,
} from "../lib/studioBridge";
import {
  appendExtraReferencePath,
  buildClearReferenceImagePatch,
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
  planBlocksDirectGenerate,
  resolvePlannedSettings,
  computePlanSettingsSnapshot,
  editFamilyPlanState,
} from "../lib/workflowPlanActions";
import { isEditFamilyMode } from "../lib/generationReadiness";

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

const ASPECT_PRESETS = [
  "1024x1024",
  "1152x896",
  "896x1152",
  "1344x768",
  "768x1344",
];

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
  const [liveProgress, setLiveProgress] = useState<{
    percentage: number;
    title: string;
  } | null>(null);
  const [generating, setGenerating] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [lastJobId, setLastJobId] = useState<string | null>(null);
  const [generationLog, setGenerationLog] = useState<string>("");
  const [agentPlan, setAgentPlan] = useState<AgentPlanSnapshot | null>(null);
  const [agentTranscript, setAgentTranscript] = useState<AgentTranscriptMessage[]>([]);
  const [planRunBusy, setPlanRunBusy] = useState(false);
  const agentPlanRef = useRef(agentPlan);
  agentPlanRef.current = agentPlan;
  const [engineState, setEngineState] = useState<EngineState>("booting");
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
  const [styleRecipes, setStyleRecipes] = useState<StyleRecipe[]>([]);
  const [modelFilter, setModelFilter] = useState("");
  const [loraFilter, setLoraFilter] = useState("");
  const [lockFamilyDefaults, setLockFamilyDefaults] = useState(true);
  const [profileHints, setProfileHints] = useState<string[]>([]);
  const [galleryLoading, setGalleryLoading] = useState(false);
  const [studioSettings, setStudioSettings] = useState<StudioSettings | null>(
    null,
  );
  const [appConfig, setAppConfig] = useState<DreamForgeAppConfig | null>(null);
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
  const [referencePacks, setReferencePacks] = useState<ReferencePack[]>([]);
  const [identities, setIdentities] = useState<IdentityRecord[]>([]);
  const [agentPlannedMode, setAgentPlannedMode] = useState<StudioMode | null>(
    null,
  );
  const [imageNumberMax, setImageNumberMax] = useState(8);
  const [inpaintMaskOpen, setInpaintMaskOpen] = useState(false);
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
  const companionDownload = useCompanionDownload();
  const companionDownloadBusy = companionDownload.busy;

  const refreshWorkerLog = useCallback(async () => {
    try {
      const { tail } = await readWorkerLog();
      if (tail) setWorkerLogTail(tail);
    } catch {
      /* log not available yet */
    }
  }, []);

  const generatingRef = useRef(false);
  const lightningPromptKeyRef = useRef("");
  const workerReadyRef = useRef(false);
  const vramProfileAutoAppliedRef = useRef(false);
  const prevVramProfileRef = useRef<string>("16gb");
  const runRestartEngineRef = useRef<(() => Promise<void>) | null>(null);
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
        setLiveProgress({
          percentage: p.percentage ?? 0,
          title: p.title ?? "",
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
    [setCanvasPreview, jobId, lastJobId, previewSignature],
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
    vram_profile: "16gb",
    aspect_ratio: "1024x1024",
    style: "product_ad",
    image_number: 1,
    negative_prompt: "",
    steps: 20,
    cfg_scale: 3.5,
    output: outputPathForSession(loadActiveSessionId()),
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
        const offset = opts?.append ? outputs.length : (opts?.offset ?? 0);
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
          setHistoryScrollToken((t) => t + 1);
        } else if (!opts?.keepSelection) {
          setSelected((prev) => {
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
    [outputs.length],
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
          lock_family_defaults: lockFamilyDefaults,
        });
        const profile = res.profile;
        const hints = (profile.hints ?? []).map((h) =>
          h.replace(/<[^>]+>/g, ""),
        );
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
        setSettings((s) => ({ ...s, ...patch }));
        return profile;
      } catch {
        return null;
      }
    },
    [settings.performance, lockFamilyDefaults],
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
        packs,
        identityRecords,
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
        listReferencePacks().catch(() => []),
        listIdentities().catch(() => []),
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
      if (lockFamilyDefaults && profileModel) {
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
      setReferencePacks(packs);
      setIdentities(identityRecords);
      studioCatalogLoadedRef.current = true;
    } catch (e) {
      setStatus(`Studio catalog error: ${String(e)}`);
    } finally {
      setGalleryLoading(false);
    }
  }, [applyModelProfile, lockFamilyDefaults]);

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
      if (p.status !== "booting" || workerReadyRef.current) {
        return;
      }
      setEngineState("booting");
      setBootMessage("Starting GPU engine process...");
      setStatus("Loading DreamForge GPU engine...");
    }).then((u) => unsubs.push(() => u()));
    void onWorkerBootProgress((p) => {
      if (workerReadyRef.current) return;
      const phase = p.phase ?? "loading_pipeline";
      if (phase === "ready") return;
      const msg = p.message ?? "Loading…";
      setEngineState("booting");
      setBootPhase(phase);
      setBootMessage(bootPhaseLabel(phase, msg));
      setStatus(bootPhaseLabel(phase, msg));
    }).then((u) => unsubs.push(() => u()));
    void onWorkerReady((p) => {
      workerReadyRef.current = true;
      setWorkerReady(true);
      setEngineState("ready");
      setBootPhase("ready");
      setBootMessage("");
      if (p.gpu_name) setGpuName(p.gpu_name);
      if (p.vram_gb != null) setVramGb(p.vram_gb);
      const gpuHint =
        p.gpu_name && p.vram_gb != null
          ? ` — ${p.gpu_name} (${p.vram_gb} GB VRAM)`
          : p.gpu_name
            ? ` — ${p.gpu_name}`
            : "";
      setStatus(`Engine ready — live GPU preview enabled${gpuHint}`);
      setWorkerLogTail("");
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
      const short = tail.split("\n").filter(Boolean).slice(-3).join(" ");
      setBootMessage(short || friendly.title);
      setStatus(
        wasGenerating
          ? `Generation failed — ${friendly.title}${short ? `: ${short.slice(0, 120)}` : ""}`
          : `${friendly.title}${short ? `: ${short.slice(0, 120)}` : ""}`,
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
      const phase = p.phase ?? "sampling";
      const pct = p.progress ?? 0;
      setLiveProgress({
        percentage: pct,
        title: generationPhaseLabel(phase, p.message),
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
      const short = tail.split("\n").filter(Boolean).slice(-2).join(" ");
      setStatus(
        `${friendly.title}${short ? ` — ${short}` : friendly.message ? ` — ${friendly.message}` : ""}`,
      );
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
      setLiveProgress({ percentage: 0, title: "Starting generation…" });
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
      } else {
        const friendly = describeError(p);
        setLastError(friendly);
        const tailHint = p.log_tail?.split("\n").filter(Boolean).slice(-3).join(" ");
        setStatus(
          shortErrorLine(p) +
            (tailHint ? ` (log: ${tailHint.slice(0, 80)})` : ""),
        );
        if (friendly.recoverable && friendly.failureReport?.auto_retry === true) {
          setStatus(`${friendly.title} — restarting GPU engine…`);
          window.setTimeout(() => {
            void runRestartEngineRef.current?.();
          }, 400);
        }
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
    applyFinalCanvasPreview,
  ]);

  useEffect(() => {
    void loadStudioCatalog();
  }, [loadStudioCatalog]);

  useEffect(() => {
    if (!workerReady) return;
    void refreshOutputs();
  }, [workerReady, refreshOutputs]);

  const applyEngineStatus = useCallback((s: Awaited<ReturnType<typeof getEngineStatus>>) => {
    // eslint-disable-next-line no-console
    console.debug("[DF] engine_status", {
      ready: s.ready,
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
    if ((s.ready || s.events_ready) && !vramProfileAutoAppliedRef.current) {
      const detected = vramProfileFromHardware(
        s.vram_gb ?? null,
        s.mps_available ?? null,
      );
      vramProfileAutoAppliedRef.current = true;
      setSettings((prev) =>
        prev.vram_profile === detected ? prev : { ...prev, vram_profile: detected },
      );
      prevVramProfileRef.current = detected;
    }
    if (s.ready || s.events_ready) {
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
      s.boot_message?.trim() ||
      (phase === "loading_pipeline"
        ? "Loading generation pipeline…"
        : bootPhaseLabel(phase, ""));
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
      if (workerReadyRef.current) return;
      sync();
    }, 1000);
    return () => clearInterval(id);
  }, [applyEngineStatus]);

  useEffect(() => {
    if (!generating) return;
    const poll = () => {
      void getGenerationProgress()
        .then((p) => {
          if (!p.running && p.phase === "idle") return;
          const phase = p.phase ?? "sampling";
          const pct = typeof p.progress === "number" ? p.progress : 0;
          setLiveProgress({
            percentage: pct,
            title: generationPhaseLabel(phase, p.message),
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
  }, [generating, setCanvasPreview, previewSignature]);

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

  const patchSettings = useCallback((patch: Partial<GenerationSettings>) => {
    if (patch.model !== undefined) {
      userPickedModelRef.current = true;
    }
    setSettings((s) => {
      const next = { ...s, ...patch };
      settingsRef.current = next;
      return next;
    });
  }, []);

  const refreshReferencePacks = useCallback(async () => {
    try {
      const packs = await listReferencePacks();
      setReferencePacks(packs);
      return packs;
    } catch {
      return [];
    }
  }, []);

  const mergeReferencePaths = useCallback((...groups: Array<string[] | undefined>) => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const group of groups) {
      for (const item of group ?? []) {
        const path = item.trim();
        if (!path || seen.has(path)) continue;
        seen.add(path);
        out.push(path);
      }
    }
    return out.length ? out : undefined;
  }, []);

  const attachReferencePack = useCallback(
    (packId: string) => {
      const pack = referencePacks.find((item) => item.id === packId);
      const identity = identities.find((item) => item.id === settingsRef.current.identity_id);
      if (!pack) {
        patchSettings({
          reference_pack_id: undefined,
          reference_pack_role: undefined,
          reference_images: mergeReferencePaths(identity?.image_paths),
        });
        setStatus("Reference pack cleared");
        return;
      }
      patchSettings({
        reference_pack_id: pack.id,
        reference_pack_role: pack.type,
        reference_images: mergeReferencePaths(pack.image_paths, identity?.image_paths),
      });
      setStatus(`Attached reference pack: ${pack.name}`);
    },
    [identities, mergeReferencePaths, patchSettings, referencePacks],
  );

  const createReferencePackFromCurrent = useCallback(
    async (
      name: string,
      type: ReferencePack["type"] = "style",
      meta?: { tags?: string[]; notes?: string },
    ) => {
      const imagePaths = [
        settingsRef.current.input_image,
        settingsRef.current.upscale_image,
        ...(settingsRef.current.reference_images ?? []),
        selected?.images?.[0],
      ].filter((item): item is string => Boolean(item?.trim()));
      if (!imagePaths.length) {
        setStatus("Attach or select image(s) before creating a reference pack");
        return null;
      }
      try {
        const pack = await saveReferencePack({
          name,
          type,
          image_paths: imagePaths,
          tags: meta?.tags ?? [],
          notes: meta?.notes ?? "",
          preferred_use_cases: [type],
        });
        setReferencePacks((prev) => [pack, ...prev.filter((item) => item.id !== pack.id)]);
        const identity = identities.find((item) => item.id === settingsRef.current.identity_id);
        patchSettings({
          reference_pack_id: pack.id,
          reference_pack_role: pack.type,
          reference_images: mergeReferencePaths(pack.image_paths, identity?.image_paths),
        });
        setStatus(`Saved reference pack: ${pack.name}`);
        return pack;
      } catch (e) {
        setStatus(`Save reference pack failed: ${String(e)}`);
        return null;
      }
    },
    [identities, mergeReferencePaths, patchSettings, selected],
  );

  const removeReferencePack = useCallback(
    async (packId: string) => {
      if (!packId) return;
      try {
        const deleted = await deleteReferencePack(packId);
        if (!deleted) {
          setStatus("Reference pack was already gone");
        } else {
          setStatus("Reference pack deleted");
        }
        setReferencePacks((prev) => prev.filter((item) => item.id !== packId));
        if (settingsRef.current.reference_pack_id === packId) {
          const identity = identities.find((item) => item.id === settingsRef.current.identity_id);
          patchSettings({
            reference_pack_id: undefined,
            reference_pack_role: undefined,
            reference_images: mergeReferencePaths(identity?.image_paths),
          });
        }
      } catch (e) {
        setStatus(`Delete reference pack failed: ${String(e)}`);
      }
    },
    [identities, mergeReferencePaths, patchSettings],
  );

  const refreshIdentities = useCallback(async () => {
    try {
      const records = await listIdentities();
      setIdentities(records);
      return records;
    } catch {
      return [];
    }
  }, []);

  const attachIdentity = useCallback(
    (identityId: string) => {
      const identity = identities.find((item) => item.id === identityId);
      const pack = referencePacks.find((item) => item.id === settingsRef.current.reference_pack_id);
      if (!identity) {
        patchSettings({
          identity_id: undefined,
          identity_role: undefined,
          identity_mode: undefined,
          face_preservation: undefined,
          reference_images: mergeReferencePaths(pack?.image_paths),
        });
        setStatus("Identity cleared");
        return;
      }
      patchSettings({
        identity_id: identity.id,
        identity_role: identity.type,
        reference_images: mergeReferencePaths(pack?.image_paths, identity.image_paths),
      });
      setStatus(`Attached identity: ${identity.name}`);
    },
    [identities, mergeReferencePaths, patchSettings, referencePacks],
  );

  const createIdentityFromCurrent = useCallback(
    async (name: string, type: IdentityRecord["type"] = "style") => {
      const imagePaths = [
        settingsRef.current.input_image,
        settingsRef.current.upscale_image,
        ...(settingsRef.current.reference_images ?? []),
        selected?.images?.[0],
      ].filter((item): item is string => Boolean(item?.trim()));
      if (!imagePaths.length) {
        setStatus("Attach or select image(s) before creating an identity");
        return null;
      }
      try {
        const identity = await saveIdentity({
          name,
          type,
          image_paths: imagePaths,
          reference_pack_ids: settingsRef.current.reference_pack_id
            ? [settingsRef.current.reference_pack_id]
            : [],
          tags: [],
          metadata: {},
          embeddings: {},
          embedding_status: "not_extracted",
        });
        setIdentities((prev) => [identity, ...prev.filter((item) => item.id !== identity.id)]);
        const pack = referencePacks.find((item) => item.id === settingsRef.current.reference_pack_id);
        patchSettings({
          identity_id: identity.id,
          identity_role: identity.type,
          reference_images: mergeReferencePaths(pack?.image_paths, identity.image_paths),
        });
        setStatus(`Saved identity: ${identity.name}`);
        return identity;
      } catch (e) {
        setStatus(`Save identity failed: ${String(e)}`);
        return null;
      }
    },
    [mergeReferencePaths, patchSettings, referencePacks, selected],
  );

  const removeIdentity = useCallback(
    async (identityId: string) => {
      if (!identityId) return;
      try {
        const deleted = await deleteIdentity(identityId);
        if (!deleted) {
          setStatus("Identity was already gone");
        } else {
          setStatus("Identity deleted");
        }
        setIdentities((prev) => prev.filter((item) => item.id !== identityId));
        if (settingsRef.current.identity_id === identityId) {
          const pack = referencePacks.find((item) => item.id === settingsRef.current.reference_pack_id);
          patchSettings({
            identity_id: undefined,
            identity_role: undefined,
            identity_mode: undefined,
            face_preservation: undefined,
            reference_images: mergeReferencePaths(pack?.image_paths),
          });
        }
      } catch (e) {
        setStatus(`Delete identity failed: ${String(e)}`);
      }
    },
    [mergeReferencePaths, patchSettings, referencePacks],
  );

  const syncOutputPathForSession = useCallback(
    (sessionId: string) => {
      const sid = sessionId.trim() || DEFAULT_SESSION_ID;
      const current = settingsRef.current;
      const kind = current.upscale_image
        ? "upscale"
        : current.input_image
          ? current.edit_type === "inpaint"
            ? "inpaint"
            : "edit"
          : "gen";
      patchSettings({ output: outputPathForSession(sid, kind) });
    },
    [patchSettings],
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
      setStatus(`Active session: ${session?.label ?? id}`);
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
      const sid = item.session?.trim();
      if (sid && sid !== activeSessionIdRef.current) {
        setActiveSessionId(sid);
        saveActiveSessionId(sid);
        syncOutputPathForSession(sid);
      }
    },
    [sessions, syncOutputPathForSession],
  );

  const reuseOutputPrompt = useCallback(
    (item: OutputItem) => {
      patchSettings({
        prompt: item.prompt || settingsRef.current.prompt,
        model: item.model_name || settingsRef.current.model,
        seed: item.seed,
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
          `Delete "${label}" and its image file(s)? This cannot be undone.`,
        )
      ) {
        return;
      }
      try {
        await deleteOutput(item.manifest_path);
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
        await deleteOutputImage(item.manifest_path, imagePath);
        removeDeletedFromSelection(undefined, imagePath);
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
      if (mode !== "generate" && !appConfig?.ui.advanced_mode) {
        setStatus(
          "Switch to Generate mode or enable advanced mode to override routed edit models",
        );
        return;
      }
      userPickedModelRef.current = true;
      patchSettings({ model: item.engine_name });
      const profile = await applyModelProfile(item);
      if (profile?.hints?.length) {
        setStatus(profile.hints[0].replace(/<[^>]+>/g, "").slice(0, 160));
      }
    },
    [appConfig?.ui.advanced_mode, appConfig?.ui.studio_mode, applyModelProfile, patchSettings],
  );

  const setStyle = useCallback(
    (style: string) => {
      const recipe = styleRecipes.find((item) => item.id === style);
      const patch: Partial<GenerationSettings> = { style };
      if (recipe?.styles?.length) {
        patch.styles = [...recipe.styles];
      } else {
        patch.styles = [];
      }
      if (recipe?.performance) {
        patch.performance = recipe.performance;
      }
      if (recipe?.aspect_ratio) {
        patch.aspect_ratio = recipe.aspect_ratio.replace("×", "x");
      }
      if (recipe?.prompt_prefix && !settings.prompt?.trim()) {
        patch.prompt = recipe.prompt_prefix;
      }
      if (!userPickedModelRef.current && style) {
        const model = resolveActiveModel(
          modelGalleryAll,
          settings.model,
          style,
          styleRecipes,
          false,
        );
        if (model) patch.model = model;
      }
      patchSettings(patch);
    },
    [modelGalleryAll, patchSettings, settings.model, settings.prompt, styleRecipes],
  );

  const activeModelLabel = useMemo(() => {
    const hit = modelGalleryAll.find((m) => modelMatches(m, settings.model));
    if (hit) return modelBasename(hit.caption);
    if (settings.model) return modelBasename(settings.model);
    return "No model selected";
  }, [modelGalleryAll, settings.model]);

  const toggleLoraGallery = useCallback(
    async (name: string) => {
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
      setAgentPlan({
        source,
        message: res.message,
        mode: res.mode,
        applied: applyPlan ? planPatch : undefined,
        proposed: planPatch,
        actions: res.actions,
        downloads: res.downloads,
        operations: res.operations,
        dynamic_preset: res.dynamic_preset,
        mode_contract: res.mode_contract,
        workflow_plan: res.workflow_plan,
        workflow_blueprint: res.workflow_blueprint,
        readiness: res.readiness,
        reference_pack:
          typeof res.reference_pack === "object" && res.reference_pack
            ? (res.reference_pack as AgentPlanSnapshot["reference_pack"])
            : undefined,
        identity_reference:
          typeof res.identity_reference === "object" && res.identity_reference
            ? (res.identity_reference as AgentPlanSnapshot["identity_reference"])
            : undefined,
      });
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
            ? `Agent configured ${res.mode} mode`
            : res.message || "Agent configured the workflow"
          : "Agent plan ready for review",
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

  const runDryRun = useCallback(async () => {
    if ((appConfig?.ui.studio_mode ?? "generate") === "agent") {
      await runAgentInstruction(false);
      return;
    }
    setStatus("Planning…");
    try {
      const studioMode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
      const sanitized = sanitizeEditFamilySettings(
        settingsRef.current,
        studioMode,
      );
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
      const extra =
        prepared.hints.length > 0 ? `${prepared.hints[0]} ` : "";
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
      setAgentPlan({
        source: "dry-run",
        message: `${hint}${extra}`.trim() || "Dry-run plan",
        mode: typeof planPayload.mode === "string" ? (planPayload.mode as StudioMode) : studioMode,
        settings_snapshot: computePlanSettingsSnapshot(prepared.settings, studioMode),
        proposed: prepared.settings,
        operations: Array.isArray(planPayload.operations)
          ? planPayload.operations.map((item) => String(item))
          : undefined,
        readiness,
        mode_contract:
          typeof planPayload.mode_contract === "object" && planPayload.mode_contract
            ? (planPayload.mode_contract as AgentPlanSnapshot["mode_contract"])
            : undefined,
        reference_pack:
          typeof planPayload.reference_pack === "object" && planPayload.reference_pack
            ? (planPayload.reference_pack as AgentPlanSnapshot["reference_pack"])
            : undefined,
        identity_reference:
          typeof planPayload.identity_reference === "object" && planPayload.identity_reference
            ? (planPayload.identity_reference as AgentPlanSnapshot["identity_reference"])
            : undefined,
        workflow_blueprint: workflowBlueprint,
      });
      setStatus(
        prepared.applied.length
          ? `Dry-run ready (${prepared.applied.join(", ")})`
          : "Dry-run ready",
      );
    } catch (e) {
      setStatus(`Dry-run failed: ${String(e)}`);
    }
  }, [appConfig?.ui.studio_mode, runAgentInstruction, settings, selected, modelGalleryAll, patchSettings]);

  const startGeneration = useCallback(
    async (
      preparedSettings: GenerationSettings,
      meta?: { mapped?: string; hint?: string; studioMode?: StudioMode },
    ) => {
      const studioMode =
        meta?.studioMode ??
        ((appConfig?.ui.studio_mode ?? "generate") as StudioMode);
      const sanitized = sanitizeEditFamilySettings(preparedSettings, studioMode);
      const prompt = (sanitized.prompt ?? "").trim();
      if (!prompt) {
        setStatus("Enter a prompt before generating");
        return false;
      }
      if (!sanitized.model) {
        setStatus("Select a base model");
        return false;
      }
      const readiness = computeGenerateReadiness({
        workerReady,
        generating: generatingRef.current,
        engineState,
        engineLabel: engineLabel(engineState, bootMessage),
        prompt,
        model: sanitized.model ?? "",
        modelDependenciesReady: modelDependencies.ready,
        missingCompanionCount: modelDependencies.missing.length,
        studioMissingAssetCount: studioResources.missing.length,
        settings: sanitized,
        modelGallery: modelGalleryAll,
        studioMode,
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
      const output = sanitized.upscale_image
        ? outputPathForSession(sid, "upscale")
        : sanitized.input_image
          ? outputPathForSession(
              sid,
              sanitized.edit_type === "inpaint" ? "inpaint" : "edit",
            )
          : outputPathForSession(sid, "gen");

      let params: GenerationSettings = {
        ...sanitized,
        prompt,
        output,
        validate_output: true,
        use_comfy_server: true,
      };
      const activeModel = findGalleryModel(modelGalleryAll, params.model ?? "");
      const modelFamily = (activeModel?.family ?? "").toLowerCase();
      if (modelFamily === "qwen_image_edit" && params.input_image?.trim()) {
        if (params.edit_type !== "inpaint") {
          params = {
            ...params,
            edit_type: "qwen_edit",
            cn_selection: "None",
            cn_type: "None",
          };
        }
        if (params.edit_strength == null || params.edit_strength <= 0) {
          params = { ...params, edit_strength: 1.0 };
        }
      }
      if (params.lora?.length && !params.lora_keywords?.trim()) {
        try {
          const kw = await aggregateLoraKeywords(params.lora);
          if (kw) params = { ...params, lora_keywords: kw };
        } catch {
          /* optional */
        }
      }

      setGenerating(true);
      generatingRef.current = true;
      setEngineState("generating");
      const mapped = meta?.mapped ? ` · ${meta.mapped}` : "";
      const hint = meta?.hint ? ` · ${meta.hint}` : "";
      setStatus(
        `Generating with ${modelBasename(params.model ?? "model")}…${mapped}${hint}`,
      );
      setAgentPlan(null);
      setGenerationLog("");
      lastPreviewSigRef.current = "";
      setLiveProgress({ percentage: 0, title: "Starting generation…" });
      patchSettings({ output });

      try {
        const resolvedParams = await resolveGenerationImagePaths(params);
        const res = await invokeGeneration(resolvedParams);
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
          setStatus(`Start failed: ${msg}`);
        }
        return false;
      }
    },
    [
      appConfig?.ui.studio_mode,
      patchSettings,
      startLogPoll,
      workerReady,
      engineState,
      bootMessage,
      modelDependencies,
      studioResources.missing.length,
      modelGalleryAll,
    ],
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
    userPickedModelRef.current = false;
    patchSettings(plan.proposed);
    if (plan.mode && plan.mode !== "agent") {
      await saveAppConfigPatch({ ui: { studio_mode: plan.mode } });
      setAgentPlannedMode(null);
    }
    setAgentPlan({ ...plan, applied: plan.proposed });
    setStatus(
      plan.mode && plan.mode !== "agent"
        ? `Plan applied — switched to ${plan.mode} mode`
        : "Plan applied — click Run plan to start generation",
    );
  }, [patchSettings, saveAppConfigPatch]);

  const runApprovedPlan = useCallback(async () => {
    const plan = agentPlanRef.current;
    if (!plan) {
      setStatus("No plan to run");
      return;
    }
    if (plan.readiness?.ready === false) {
      setStatus("Plan is not ready — resolve missing inputs or models first");
      return;
    }
    setPlanRunBusy(true);
    try {
      const merged = resolvePlannedSettings(plan, settingsRef.current);
      userPickedModelRef.current = false;
      patchSettings(merged);
      const targetMode =
        plan.mode && plan.mode !== "agent"
          ? plan.mode
          : ((appConfig?.ui.studio_mode ?? "generate") as StudioMode);
      if (plan.mode && plan.mode !== "agent" && plan.mode !== appConfig?.ui.studio_mode) {
        await saveAppConfigPatch({ ui: { studio_mode: plan.mode } });
        setAgentPlannedMode(null);
      }
      setAgentPlan({ ...plan, applied: merged });

      const prepared = prepareGenerationFromAgentPrompt(merged, {
        selectedImagePath: selected?.images?.[0],
        modelGallery: modelGalleryAll,
      });
      if (prepared.applied.length || prepared.hints.length) {
        patchSettings(prepared.settings);
      }
      const mapped =
        prepared.applied.length > 0
          ? `mapped ${prepared.applied.join(", ")}`
          : undefined;
      const hint = prepared.hints.length > 0 ? prepared.hints[0] : undefined;
      await startGeneration(prepared.settings, {
        mapped,
        hint,
        studioMode: targetMode,
      });
    } finally {
      setPlanRunBusy(false);
    }
  }, [
    appConfig?.ui.studio_mode,
    modelGalleryAll,
    patchSettings,
    saveAppConfigPatch,
    selected,
    startGeneration,
  ]);

  const runGenerate = useCallback(async () => {
    const studioMode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
    if (studioMode === "agent") {
      await runAgentInstruction(true);
      return;
    }
    if (isEditFamilyMode(studioMode)) {
      const snapshot = computePlanSettingsSnapshot(
        settingsRef.current,
        studioMode,
      );
      const plan = agentPlanRef.current;
      const planState = editFamilyPlanState(plan, studioMode, snapshot);
      if (planState === "none" || planState === "stale") {
        await runDryRun();
        setStatus(
          planState === "stale"
            ? "Settings changed — review the updated plan card, then Run plan"
            : "Review the routed plan on the canvas, then Run plan",
        );
        return;
      }
      if (planState === "not_ready") {
        setStatus("Plan is not ready — resolve missing setup in the plan card");
        return;
      }
      await runApprovedPlan();
      return;
    }
    if (
      planBlocksDirectGenerate(
        agentPlanRef.current,
        appConfig?.agent.approval_required,
        { studioMode },
      )
    ) {
      setStatus("Review the plan card — use Run plan to start generation");
      return;
    }
    const prepared = prepareGenerationFromAgentPrompt(settingsRef.current, {
      selectedImagePath: selected?.images?.[0],
      modelGallery: modelGalleryAll,
    });
    if (prepared.applied.length || prepared.hints.length) {
      patchSettings(prepared.settings);
    }
    const mapped =
      prepared.applied.length > 0
        ? `mapped ${prepared.applied.join(", ")}`
        : undefined;
    const hint = prepared.hints.length > 0 ? prepared.hints[0] : undefined;
    await startGeneration(prepared.settings, { mapped, hint });
  }, [
    appConfig?.ui.studio_mode,
    appConfig?.agent.approval_required,
    runAgentInstruction,
    runDryRun,
    runApprovedPlan,
    selected,
    modelGalleryAll,
    patchSettings,
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
      await restartGpuWorker();
      void getEngineStatus().then(applyEngineStatus);
      void loadStudioCatalog(true);
    } catch (e) {
      setEngineState("failed");
      await refreshWorkerLog();
      setBootMessage(String(e));
      setStatus(`Restart failed: ${String(e)}`);
    } finally {
      setRestarting(false);
    }
  }, [refreshWorkerLog, loadStudioCatalog, applyEngineStatus]);
  runRestartEngineRef.current = () => runRestartEngine();

  useEffect(() => {
    if (!workerReady || restarting) return;
    const current = settings.vram_profile ?? "16gb";
    if (prevVramProfileRef.current === current) return;
    prevVramProfileRef.current = current;
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
    companionDownload.phase,
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
  const generateReadiness = useMemo(
    () =>
      computeGenerateReadiness({
        workerReady,
        generating,
        engineState,
        engineLabel: engineLabel(engineState, bootMessage),
        prompt: settings.prompt ?? "",
        model: settings.model ?? "",
        modelDependenciesReady: modelDependencies.ready,
        missingCompanionCount: modelDependencies.missing.length,
        studioMissingAssetCount: studioResources.missing.length,
        settings,
        modelGallery: modelGalleryAll,
        studioMode,
        editPlanState: isEditFamilyMode(studioMode) ? editPlanState : undefined,
      }),
    [
      workerReady,
      generating,
      engineState,
      bootMessage,
      settings,
      modelDependencies,
      studioResources.missing.length,
      modelGalleryAll,
      studioMode,
      editPlanState,
    ],
  );
  const planApprovalPending =
    studioMode !== "agent" &&
    planBlocksDirectGenerate(agentPlan, appConfig?.agent.approval_required, {
      studioMode,
      settingsSnapshot: planSettingsSnapshot,
    });
  const effectiveGenerateReadiness = useMemo(() => {
    if (planApprovalPending && !isEditFamilyMode(studioMode)) {
      return {
        ok: false as const,
        reason: "Review the plan card — use Run plan to start generation",
        missingCompanions: false as const,
      };
    }
    return generateReadiness;
  }, [planApprovalPending, generateReadiness, studioMode]);
  const missingDownloadCount =
    modelDependencies.missing.length + studioResources.missing.length;

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
      const patch = buildReferenceImagePatch(resolved, mode, (suffix) =>
        outputPathForSession(
          activeSessionIdRef.current || DEFAULT_SESSION_ID,
          suffix === "upscale"
            ? "upscale"
            : suffix === "inpaint"
              ? "inpaint"
              : "edit",
        ),
      );
      if (mode !== "upscale") {
        const activeModel = findGalleryModel(
          modelGalleryAll,
          settingsRef.current.model ?? "",
        );
        const family = activeModel?.family ?? "";
        if (settingsRef.current.edit_strength == null || settingsRef.current.edit_strength <= 0) {
          patch.edit_strength = defaultReferenceEditStrength(
            { ...settingsRef.current, ...patch },
            family,
          );
        }
      }
      patchSettings(patch);
      setAgentPlan(null);
      if (mode === "inpaint") {
        setInpaintMaskOpen(true);
        setStatus(`Attached ${referenceStatusLabel(mode, resolved)} - paint a fresh mask`);
      } else {
        setStatus(`Attached ${referenceStatusLabel(mode, resolved)}`);
      }
    },
    [modelGalleryAll, patchSettings],
  );

  const clearReferenceImage = useCallback(() => {
    patchSettings(buildClearReferenceImagePatch());
    setStatus("Reference image cleared");
  }, [patchSettings]);

  const attachExtraReferenceImage = useCallback(
    async (path: string) => {
      const resolved = await resolveReferenceImagePath(path);
      const patch = appendExtraReferencePath(settingsRef.current, resolved);
      if (!Object.keys(patch).length) {
        setStatus("Control reference already attached");
        return;
      }
      patchSettings(patch);
      const count = (patch.reference_images ?? []).length;
      setStatus(`Added control reference (${count} total)`);
    },
    [patchSettings],
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
      const res = await checkModelDependencies(model, performance);
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
      await saveAppConfigPatch({ ui: { studio_mode: mode } });
      setAgentPlannedMode(null);
      setAgentPlan(null);
      if (mode === "generate") {
        setStatus("Generation mode - model library selection is unlocked");
        return;
      }
      if (mode === "agent") {
        setStatus("Agent mode - describe the workflow and let the agent configure it");
        return;
      }

      const routedModel = selectCuratedModelForMode(
        mode,
        modelGalleryAll,
        settingsRef.current.model,
      );
      const patch: Partial<GenerationSettings> = {
        model: routedModel,
        style: "image_edit",
        performance: "Flux",
      };
      if (mode === "edit") {
        patch.edit_type = "kontext";
        patch.edit_strength = settingsRef.current.edit_strength ?? 0.98;
        patch.cn_selection = "None";
        patch.cn_type = "None";
        // Match Krita Flux Kontext presets (Flux - Euler simple): avoid over-capping steps.
        patch.steps = Math.min(Math.max(settingsRef.current.steps ?? 20, 20), 28);
        patch.upscale_image = undefined;
        patch.upscale_method = undefined;
        patch.inpaint_mask_path = undefined;
        const src =
          selected?.images?.[0] ?? settingsRef.current.input_image ?? "";
        if (src.trim()) patch.input_image = src.trim();
      }
      if (mode === "inpaint") {
        patch.edit_type = "inpaint";
        patch.edit_strength = settingsRef.current.edit_strength ?? 0.9;
        patch.cn_selection = "Custom...";
        patch.cn_type = "inpaint";
        patch.steps = Math.min(Math.max(settingsRef.current.steps ?? 20, 20), 28);
        patch.upscale_image = undefined;
        patch.upscale_method = undefined;
        patch.inpaint_mask_path = undefined;
        const src =
          selected?.images?.[0] ?? settingsRef.current.input_image ?? "";
        if (src.trim()) patch.input_image = src.trim();
      }
      if (mode === "upscale") {
        patch.style = "image_edit";
        patch.edit_type = "auto";
        patch.input_image = undefined;
        patch.inpaint_mask_path = undefined;
        patch.cn_selection = "Custom...";
        patch.cn_type = "upscale";
        patch.upscale_method = "fast_2x";
        const src =
          selected?.images?.[0] ??
          settingsRef.current.upscale_image ??
          settingsRef.current.input_image ??
          "";
        if (src.trim()) patch.upscale_image = src.trim();
      }
      userPickedModelRef.current = false;
      patchSettings(patch);
      if (routedModel) void refreshModelDependencies(routedModel);
      const defaultStatus = `${mode[0].toUpperCase()}${mode.slice(1)} mode - DreamForge will auto-route curated tools`;
      setStatus(defaultStatus);
    },
    [
      modelGalleryAll,
      patchSettings,
      refreshModelDependencies,
      saveAppConfigPatch,
      selected,
    ],
  );

  const useSelectedImageFor = useCallback(
    async (mode: "edit" | "inpaint" | "upscale") => {
      const path = selected?.images?.[0];
      if (!path) {
        setStatus("Select a session image first");
        return;
      }
      setAgentPlan(null);
      const currentMode = (appConfig?.ui.studio_mode ?? "generate") as StudioMode;
      if (currentMode !== mode) {
        await setStudioMode(mode);
        if (mode === "inpaint") {
          setInpaintMaskOpen(true);
          setStatus("Attached image for inpaint — paint a fresh mask");
        } else {
          setStatus(`Switched to ${mode} mode with selected image`);
        }
        return;
      }
      const mapped: ReferenceImageMode =
        mode === "upscale" ? "upscale" : mode === "inpaint" ? "inpaint" : "reference";
      const resolved = await resolveReferenceImagePath(path);
      patchSettings(
        buildReferenceImagePatch(resolved, mapped, (suffix) =>
          outputPathForSession(
            activeSessionIdRef.current || DEFAULT_SESSION_ID,
            suffix === "upscale"
              ? "upscale"
              : suffix === "inpaint"
                ? "inpaint"
                : "edit",
          ),
        ),
      );
      if (mapped === "inpaint") {
        setInpaintMaskOpen(true);
        setStatus(`Attached ${referenceStatusLabel(mapped, resolved)} - paint a fresh mask`);
      } else {
        setStatus(`Attached ${referenceStatusLabel(mapped, resolved)}`);
      }
    },
    [appConfig?.ui.studio_mode, patchSettings, selected, setStudioMode],
  );

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
    setStatus("Preparing companion download approval…");
    try {
      const res = model
        ? await checkModelDependencies(
            model,
            settingsRef.current.performance ?? null,
          )
        : { missing: [] as ModelDependencyItem[], ready: true };
      const fromModel = res.missing ?? [];
      const fromStudio = studioResources.missing;
      const fromPlan =
        companionItemsFromActions(plan?.readiness?.recommended_actions as RepairAction[] | undefined);
      const merged: ModelDependencyItem[] = [];
      const keys = new Set<string>();
      for (const item of [
        ...fromModel,
        ...fromStudio,
        ...fromPlan,
        ...fromErrorReport,
        ...fromErrorDetails,
      ]) {
        const k = `${item.id ?? ""}|${item.url ?? ""}|${item.filename ?? ""}|${item.relative ?? ""}`;
        if (keys.has(k)) continue;
        keys.add(k);
        merged.push(item);
      }
      setModelDependencies({
        missing: fromModel,
        ready: res.ready ?? fromModel.length === 0,
      });
      if (merged.length === 0) {
        setStatus("All companion files are already present");
        return;
      }
      companionDownload.start(model || "workflow-assets", merged);
      setStatus(`Review download approval for ${merged.length} companion file(s)`);
    } catch (e) {
      setStatus(`Could not list companions: ${String(e)}`);
    }
  }, [companionDownload, lastError, studioResources.missing]);

  useEffect(() => {
    const model = settings.model?.trim();
    if (!model) return;
    if (companionDownload.phase !== "done" && companionDownload.phase !== "error") {
      return;
    }
    void refreshModelDependencies(model).then((deps) => {
      if (deps.ready) {
        setLastError((prev) =>
          prev?.code === "missing_model_dependencies" ? null : prev,
        );
        setStatus("Companion files ready — you can generate now");
        void loadStudioCatalog(true);
      } else if (companionDownload.phase === "error") {
        setStatus("Some companion downloads failed — see download log");
        setLastError(
          describeError({
            code: "missing_model_dependencies",
            message: `Still missing ${deps.missing.length} companion file(s).`,
          }),
        );
      }
    });
  }, [
    companionDownload.phase,
    settings.model,
    refreshModelDependencies,
    loadStudioCatalog,
  ]);

  const lowerVramProfile = useCallback(() => {
    const current = settingsRef.current.vram_profile ?? "16gb";
    const next =
      current === "16gb" ? "8gb" : current === "8gb" ? "5gb" : "5gb";
    patchSettings({ vram_profile: next });
    setStatus(`VRAM profile set to ${next}`);
  }, [patchSettings]);

  useEffect(() => {
    void refreshModelDependencies(settings.model);
  }, [settings.model, settings.performance, refreshModelDependencies]);

  useEffect(() => {
    const model = settings.model?.trim();
    if (!model) return;
    const perf = (settings.performance ?? "").trim().toLowerCase();
    if (!["speed", "lightning", "lcm"].includes(perf)) {
      lightningPromptKeyRef.current = "";
      return;
    }
    const activeModel = findGalleryModel(modelGalleryAll, model);
    if ((activeModel?.family ?? "").toLowerCase() !== "qwen_image_edit") return;
    if (companionDownload.open || companionDownload.busy) return;

    const promptKey = `${model}|${perf}`;
    void refreshModelDependencies(model).then((deps) => {
      const lightningMissing = deps.missing.filter(
        (item) => item.id === "lora_qwen_edit_lightning_4step",
      );
      if (lightningMissing.length === 0) {
        lightningPromptKeyRef.current = "";
        return;
      }
      if (lightningPromptKeyRef.current === promptKey) return;
      lightningPromptKeyRef.current = promptKey;
      companionDownload.start(model, lightningMissing);
      setStatus("Qwen Speed/Lightning needs the Lightning LoRA — approve download");
    });
  }, [
    settings.model,
    settings.performance,
    modelGalleryAll,
    companionDownload.open,
    companionDownload.busy,
    companionDownload,
    refreshModelDependencies,
  ]);

  const referenceModelFamily = useMemo(() => {
    const item = findGalleryModel(modelGalleryAll, settings.model ?? "");
    return item?.family ?? "";
  }, [modelGalleryAll, settings.model]);

  const mentionTargets = useMemo(() => {
    const models = modelGalleryAll.map((m) => ({
      kind: "model" as const,
      label: modelBasename(m.caption),
      value: m.engine_name,
    }));
    const styles = styleRecipes.slice(0, 150).map((recipe) => ({
      kind: "style" as const,
      label: recipe.original_name
        ? recipe.original_name.replace(/^Style:\s*/, "")
        : recipe.id.replace(/_/g, " "),
      value: recipe.id,
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
    companionDownloadBusy,
    refreshModelDependencies,
    downloadMissingCompanions,
    companionDownload,
    lowerVramProfile,
    canGenerate: effectiveGenerateReadiness.ok,
    generateBlockReason: effectiveGenerateReadiness.reason,
    needsCompanionDownload: effectiveGenerateReadiness.missingCompanions,
    uiDefaults,
    modelGallery,
    loraGallery,
    modelFilter,
    setModelFilter,
    loraFilter,
    setLoraFilter,
    lockFamilyDefaults,
    setLockFamilyDefaults,
    profileHints,
    galleryLoading,
    userStyleProfile,
    userStyleProfilePath,
    referencePacks,
    refreshReferencePacks,
    attachReferencePack,
    createReferencePackFromCurrent,
    deleteReferencePack: removeReferencePack,
    identities,
    refreshIdentities,
    attachIdentity,
    createIdentityFromCurrent,
    deleteIdentity: removeIdentity,
    setUserStyleMemoryEnabled,
    clearUserStyleMemory,
    exportUserStyleMemory,
    refreshUserStyleProfile,
    selectModelGallery,
    toggleLoraGallery,
    styleRecipes,
    aspectPresets: uiDefaults?.aspect_ratios?.map((a) =>
      a.replace("×", "x"),
    ) ?? ASPECT_PRESETS,
    mentionTargets,
    runDryRun,
    runGenerate,
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
    openOutputInExplorer,
    copyOutputPath,
    deleteOutputManifest,
    deleteOutputImageFile,
    deleteOutputSession,
    refreshStudioCatalog: () => loadStudioCatalog(true),
    selectGalleryImage: (path: string) => {
      void setCanvasPreviewFromPath(path);
    },
    studioSettings,
    saveStudioSettings: saveStudioSettingsPatch,
    appConfig,
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
    setInpaintMaskPath: (path: string) =>
      patchSettings({ inpaint_mask_path: path }),
  };
}
