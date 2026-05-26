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
  findGalleryModel,
  modelBasename,
  modelMatches,
  resolveActiveModel,
  selectCuratedModelForMode,
  type StudioMode,
  type UseCaseRecipe,
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
  invokeGeneration,
  deleteOutput,
  deleteOutputImage,
  deleteSession,
  listOutputsPage,
  revealPathInExplorer,
  searchOutputsPage,
  listUseCases,
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
  type ModelGalleryItem,
  type ModelDependencyItem,
  type UiDefaults,
} from "../lib/tauri-api";
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
  getAppConfig,
  getLoraInfo,
  getStudioSettings,
  listAgentProviders,
  planAgentInstruction,
  saveAppConfig,
  saveStudioSettings,
  testAgentProvider,
  type AgentProviderPreset,
  type AgentProviderTestResult,
  type DreamForgeAppConfig,
  type DreamForgeAppConfigPatch,
  type StudioSettings,
} from "../lib/studioBridge";
import {
  buildClearReferenceImagePatch,
  buildReferenceImagePatch,
  referenceStatusLabel,
  resolveGenerationImagePaths,
  resolveReferenceImagePath,
  type ReferenceImageMode,
} from "../lib/referenceImage";

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
  const [inventory, setInventory] = useState(
    parseInventoryResponse({ categories: {}, styles: [], style_groups: [] }),
  );
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
  const [planPreview, setPlanPreview] = useState<string | null>(null);
  const [engineState, setEngineState] = useState<EngineState>("booting");
  const [status, setStatus] = useState<string>("Starting GPU engine…");
  const [workerReady, setWorkerReady] = useState(false);
  const [workerLogTail, setWorkerLogTail] = useState("");
  const [restarting, setRestarting] = useState(false);
  const [uiDefaults, setUiDefaults] = useState<UiDefaults | null>(null);
  const [modelGalleryAll, setModelGalleryAll] = useState<ModelGalleryItem[]>([]);
  const [loraGalleryAll, setLoraGalleryAll] = useState<LoraGalleryItem[]>([]);
  const studioCatalogLoadedRef = useRef(false);
  const userPickedModelRef = useRef(false);
  const useCasesRef = useRef<UseCaseRecipe[]>([]);
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
    "Starting GPU engine…",
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

  const setCanvasPreview = useCallback((url: string | null, path?: string) => {
    if (url && url === previewUrlRef.current) return;
    previewUrlRef.current = url;
    if (path) {
      canvasPreviewPathRef.current = normalizePreviewPath(path);
    } else if (!url) {
      canvasPreviewPathRef.current = "";
    }
    setPreviewUrl(url);
  }, []);

  const setCanvasPreviewFromPath = useCallback(
    async (path: string) => {
      const norm = normalizePreviewPath(path);
      if (norm && norm === canvasPreviewPathRef.current && previewUrlRef.current) {
        return;
      }
      const url = await finalPreviewUrlForPath(path);
      if (url) setCanvasPreview(url, path);
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
        (jobId === previewJobId || lastJobId === previewJobId);
      if (!generatingRef.current && !isFinal && !activeJob) {
        return;
      }
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
      if (url) {
        lastPreviewSigRef.current = url.slice(0, 96);
        lastPreviewEventAtRef.current = Date.now();
        setCanvasPreview(url, p.preview_path);
        return;
      }
      if (p.has_preview && !isFinal) {
        try {
          const r = await readLivePreview();
          const fallback = await resolveCanvasPreviewUrl({
            data_url: r.data_url,
            preview_path: r.path,
            live: true,
          });
          if (fallback) {
            lastPreviewSigRef.current = fallback.slice(0, 96);
            lastPreviewEventAtRef.current = Date.now();
            setCanvasPreview(fallback, r.path);
          }
        } catch {
          /* preview file not ready yet */
        }
      }
    },
    [setCanvasPreview, jobId, lastJobId],
  );

  const [settings, setSettings] = useState<GenerationSettings>({
    prompt: "Premium product hero shot, studio lighting, clean negative space",
    model: "",
    vram_profile: "16gb",
    aspect_ratio: "1024x1024",
    styles: ["Style: sai-enhance", "Style: sai-photographic"],
    use_case: "product_ad",
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

  const loadStudioCatalog = useCallback(async (force = false) => {
    if (studioCatalogLoadedRef.current && !force) {
      return;
    }
    setGalleryLoading(true);
    try {
      const [
        models,
        loras,
        raw,
        defaults,
        useCaseRes,
        studio,
        app,
        providers,
      ] = await Promise.all([
        getModelGallery(""),
        getLoraGallery(""),
        getInventory(),
        getUiDefaults(),
        listUseCases(),
        getStudioSettings().catch(() => null),
        getAppConfig().catch(() => null),
        listAgentProviders().catch(() => []),
      ]);
      const recipes = (useCaseRes.use_cases ?? []) as UseCaseRecipe[];
      useCasesRef.current = recipes;
      setModelGalleryAll(models);
      setLoraGalleryAll(loras);
      setInventory(parseInventoryResponse(raw as Record<string, unknown>));
      setUiDefaults(defaults);
      let profileModel = "";
      setSettings((prev) => {
        const nextModel = resolveActiveModel(
          models,
          prev.model,
          prev.use_case,
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
        void notifyDone("DreamForge", "Your image finished rendering.");
        const result = (p as { result?: { images?: Array<{ path: string }> } })
          .result;
        const paths =
          result?.images?.map((i) => i.path).filter(Boolean) ?? [];
        const primary = paths[0] ?? p.preview_path;
        if (primary) {
          void setCanvasPreviewFromPath(primary);
        } else {
          void (async () => {
            const url = await resolveCanvasPreviewUrl({
              data_url: p.data_url,
              preview_path: p.preview_path,
              final: true,
            });
            if (url) setCanvasPreview(url, p.preview_path);
          })();
        }
        void refreshOutputs({ selectNewest: true });
      } else {
        const friendly = describeError(p);
        setLastError(friendly);
        const tailHint = p.log_tail?.split("\n").filter(Boolean).slice(-3).join(" ");
        setStatus(
          shortErrorLine(p) +
            (tailHint ? ` (log: ${tailHint.slice(0, 80)})` : ""),
        );
        if (
          friendly.recoverable &&
          (friendly.code === "out_of_memory" || friendly.code === "worker_crashed")
        ) {
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
    setCanvasPreviewFromPath,
  ]);

  useEffect(() => {
    if (!workerReady) return;
    void loadStudioCatalog();
    void refreshOutputs();
  }, [workerReady, loadStudioCatalog, refreshOutputs]);

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
      if (staleMs < 900) {
        return;
      }
      void readLivePreview()
        .then(async (r) => {
          const url = await resolveCanvasPreviewUrl({
            data_url: r.data_url,
            preview_path: r.path,
            live: true,
          });
          if (url && url.slice(0, 96) !== lastPreviewSigRef.current) {
            lastPreviewSigRef.current = url.slice(0, 96);
            lastPreviewEventAtRef.current = Date.now();
            setCanvasPreview(url, r.path);
          }
        })
        .catch(() => {});
    };
    poll();
    const id = setInterval(poll, 800);
    return () => clearInterval(id);
  }, [generating, setCanvasPreview]);

  useEffect(() => () => cleanupCanvasPreviewUrls(), []);

  useEffect(() => {
    if (generating) return;
    const path = selected?.images?.[0];
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

  const setUseCase = useCallback(
    (use_case: string) => {
      const patch: Partial<GenerationSettings> = { use_case };
      if (!userPickedModelRef.current && use_case) {
        const model = resolveActiveModel(
          modelGalleryAll,
          settings.model,
          use_case,
          useCasesRef.current,
          false,
        );
        if (model) patch.model = model;
      }
      patchSettings(patch);
    },
    [modelGalleryAll, patchSettings, settings.model],
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
            ? `Agent provider connected (${res.latency_ms} ms)`
            : `Agent provider test failed: ${res.detail}`,
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
        setStatus(`Agent provider test failed: ${String(e)}`);
        return res;
      } finally {
        setAgentProviderBusy(false);
      }
    },
    [appConfig, saveAppConfigPatch],
  );

  const runAgentInstruction = useCallback(async (applyPlan: boolean) => {
    const instruction = (settingsRef.current.prompt ?? "").trim();
    if (!instruction) {
      setStatus("Tell the agent what you want DreamForge to do");
      return;
    }
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
      if (res.mode && res.mode !== "agent") {
        setAgentPlannedMode(res.mode);
      }
      if (applyPlan && Object.keys(patch).length > 0) {
        userPickedModelRef.current = false;
        patchSettings(patch);
        if (res.mode && res.mode !== "agent") {
          await saveAppConfigPatch({ ui: { studio_mode: res.mode } });
          setAgentPlannedMode(null);
        }
      }
      setPlanPreview(
        JSON.stringify(
          {
            source: res.source,
            provider: res.provider_model
              ? `${res.provider ?? "provider"} / ${res.provider_model}`
              : res.source,
            message: res.message,
            mode: res.mode,
            applied: applyPlan ? patch : {},
            proposed: patch,
            actions: res.actions,
            downloads: res.downloads,
            next: applyPlan
              ? "Workflow settings were applied and the routed mode was opened. Review dependency prompts, then run."
              : "Review this plan, then press Apply plan to update DreamForge settings.",
          },
          null,
          2,
        ),
      );
      setStatus(
        applyPlan
          ? res.mode && res.mode !== "agent"
            ? `Agent configured ${res.mode} mode`
            : res.message || "Agent configured the workflow"
          : "Agent plan ready for review",
      );
    } catch (e) {
      setStatus(`Agent planning failed: ${String(e)}`);
    }
  }, [
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
      const prepared = prepareGenerationFromAgentPrompt(settingsRef.current, {
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
      setPlanPreview(`${hint}${extra}\n${JSON.stringify(res.plan ?? res, null, 2)}`);
      setStatus(
        prepared.applied.length
          ? `Dry-run ready (${prepared.applied.join(", ")})`
          : "Dry-run ready",
      );
    } catch (e) {
      setStatus(`Dry-run failed: ${String(e)}`);
    }
  }, [appConfig?.ui.studio_mode, runAgentInstruction, settings, selected, modelGalleryAll, patchSettings]);

  const runGenerate = useCallback(async () => {
    if ((appConfig?.ui.studio_mode ?? "generate") === "agent") {
      await runAgentInstruction(true);
      return;
    }
    const prepared = prepareGenerationFromAgentPrompt(settingsRef.current, {
      selectedImagePath: selected?.images?.[0],
      modelGallery: modelGalleryAll,
    });
    if (prepared.applied.length || prepared.hints.length) {
      patchSettings(prepared.settings);
    }

    const prompt = (prepared.settings.prompt ?? "").trim();
    if (!prompt) {
      setStatus("Enter a prompt before generating");
      return;
    }
    if (!prepared.settings.model) {
      setStatus("Select a base model");
      return;
    }
    const readiness = computeGenerateReadiness({
      workerReady,
      generating: generatingRef.current,
      engineState,
      engineLabel: engineLabel(engineState, bootMessage),
      prompt,
      model: prepared.settings.model ?? "",
      modelDependenciesReady: modelDependencies.ready,
      missingCompanionCount: modelDependencies.missing.length,
      settings: prepared.settings,
      modelGallery: modelGalleryAll,
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
      return;
    }
    if (!workerReady) {
      setStatus(engineLabel(engineState, bootMessage));
      return;
    }
    if (generatingRef.current) {
      setStatus("Generation already in progress");
      return;
    }

    const sid = activeSessionIdRef.current || DEFAULT_SESSION_ID;
    const output = prepared.settings.upscale_image
      ? outputPathForSession(sid, "upscale")
      : prepared.settings.input_image
        ? outputPathForSession(
            sid,
            prepared.settings.edit_type === "inpaint" ? "inpaint" : "edit",
          )
        : outputPathForSession(sid, "gen");

    let params: GenerationSettings = {
      ...prepared.settings,
      prompt,
      output,
      validate_output: true,
    };
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
    const mapped =
      prepared.applied.length > 0
        ? ` · mapped ${prepared.applied.join(", ")}`
        : prepared.hints.length > 0
          ? ` · ${prepared.hints[0]}`
          : "";
    setStatus(`Generating with ${modelBasename(params.model ?? "model")}…${mapped}`);
    setPlanPreview(null);
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
    } catch (e) {
      setGenerating(false);
      generatingRef.current = false;
      const msg = String(e);
      if (msg.includes("generation_in_progress")) {
        setStatus("Generation already in progress — wait or cancel first");
      } else {
        setStatus(`Start failed: ${msg}`);
      }
    }
  }, [
    settings,
    appConfig?.ui.studio_mode,
    runAgentInstruction,
    selected,
    modelGalleryAll,
    patchSettings,
    startLogPoll,
    workerReady,
    engineState,
    bootMessage,
    modelDependencies,
    modelGalleryAll,
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
        settings,
        modelGallery: modelGalleryAll,
        studioMode: (appConfig?.ui.studio_mode ?? "generate") as StudioMode,
      }),
    [
      workerReady,
      generating,
      engineState,
      bootMessage,
      settings,
      modelDependencies,
      modelGalleryAll,
      appConfig?.ui.studio_mode,
    ],
  );

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

  const useSelectedImageFor = useCallback(
    async (mode: "edit" | "inpaint" | "upscale") => {
      const path = selected?.images?.[0];
      if (!path) {
        setStatus("Select a session image first");
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
      setStatus(`Attached ${referenceStatusLabel(mapped, resolved)}`);
    },
    [patchSettings, selected],
  );

  const attachReferenceImage = useCallback(
    async (path: string, mode: ReferenceImageMode) => {
      const resolved = await resolveReferenceImagePath(path);
      patchSettings(
        buildReferenceImagePatch(resolved, mode, (suffix) =>
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
      setStatus(`Attached ${referenceStatusLabel(mode, resolved)}`);
    },
    [patchSettings],
  );

  const clearReferenceImage = useCallback(() => {
    patchSettings(buildClearReferenceImagePatch());
    setStatus("Reference image cleared");
  }, [patchSettings]);

  const refreshModelDependencies = useCallback(async (modelName?: string) => {
    const model = (modelName ?? settingsRef.current.model ?? "").trim();
    if (!model) {
      const empty = { missing: [] as ModelDependencyItem[], ready: true };
      setModelDependencies(empty);
      return empty;
    }
    try {
      const res = await checkModelDependencies(model);
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
        use_case: "image_edit",
        performance: "Flux",
      };
      if (mode === "edit") {
        patch.edit_type = "kontext";
        patch.edit_strength = settingsRef.current.edit_strength ?? 0.98;
        patch.cn_selection = "None";
        patch.cn_type = "None";
        patch.steps = Math.min(settingsRef.current.steps ?? 20, 16);
        patch.upscale_image = undefined;
        const src =
          selected?.images?.[0] ?? settingsRef.current.input_image ?? "";
        if (src.trim()) patch.input_image = src.trim();
      }
      if (mode === "inpaint") {
        patch.edit_type = "inpaint";
        patch.edit_strength = settingsRef.current.edit_strength ?? 0.9;
        patch.cn_selection = "Custom...";
        patch.cn_type = "inpaint";
        patch.steps = Math.min(settingsRef.current.steps ?? 20, 16);
        patch.upscale_image = undefined;
        const src =
          selected?.images?.[0] ?? settingsRef.current.input_image ?? "";
        if (src.trim()) patch.input_image = src.trim();
      }
      if (mode === "upscale") {
        patch.use_case = "image_edit";
        patch.edit_type = "auto";
        patch.input_image = undefined;
        patch.inpaint_mask_path = undefined;
        patch.cn_selection = "Custom...";
        patch.cn_type = "upscale";
        patch.upscale_method = "2x";
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
      setStatus(
        `${mode[0].toUpperCase()}${mode.slice(1)} mode - DreamForge will auto-route curated tools`,
      );
    },
    [
      modelGalleryAll,
      patchSettings,
      refreshModelDependencies,
      saveAppConfigPatch,
      selected,
    ],
  );

  const downloadMissingCompanions = useCallback(async () => {
    const model = (settingsRef.current.model ?? "").trim();
    if (!model) {
      setStatus("Select a model first");
      return;
    }
    setStatus("Opening companion download…");
    try {
      const res = await checkModelDependencies(model);
      setModelDependencies({
        missing: res.missing ?? [],
        ready: res.ready ?? (res.missing?.length ?? 0) === 0,
      });
      companionDownload.start(model, res.missing ?? []);
    } catch (e) {
      setStatus(`Could not list companions: ${String(e)}`);
    }
  }, [companionDownload]);

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
  }, [settings.model, refreshModelDependencies]);

  const mentionTargets = useMemo(() => {
    const models = modelGalleryAll.map((m) => ({
      kind: "model" as const,
      label: modelBasename(m.caption),
      value: m.engine_name,
    }));
    const styles = inventory.styles.slice(0, 150).map((s) => ({
      kind: "style" as const,
      label: s.replace(/^Style:\s*/, ""),
      value: s,
    }));
    return [...models, ...styles];
  }, [modelGalleryAll, inventory]);

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
    setUseCase,
    activeModelLabel,
    inventory,
    generating,
    jobId,
    logJobId: jobId ?? lastJobId,
    generationLog,
    planPreview,
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
    companionDownloadBusy,
    refreshModelDependencies,
    downloadMissingCompanions,
    companionDownload,
    lowerVramProfile,
    canGenerate: generateReadiness.ok,
    generateBlockReason: generateReadiness.reason,
    needsCompanionDownload: generateReadiness.missingCompanions,
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
    selectModelGallery,
    toggleLoraGallery,
    aspectPresets: uiDefaults?.aspect_ratios?.map((a) =>
      a.replace("×", "x"),
    ) ?? ASPECT_PRESETS,
    mentionTargets,
    runDryRun,
    runGenerate,
    runCancel,
    useSelectedImageFor,
    attachReferenceImage,
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
