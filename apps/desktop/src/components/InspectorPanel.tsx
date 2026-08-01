import {
  Boxes,
  ChevronLeft,
  ChevronRight,
  Globe,
  Layers,
  LayoutGrid,
  Palette,
  RefreshCw,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  isFluxFillModel,
  sortGalleryForInpaintMode,
} from "../lib/inpaintModel";
import { inspectorTabsForMode } from "../lib/generationTabVisibility";
import {
  sortGalleryForUpscaleMode,
} from "../lib/upscaleModel";
import {
  isFluxKontextEditModel,
  sortGalleryForEditMode,
} from "../lib/editModel";
import {
  modelMatches,
  isEditFamilyMode,
  modelBasename,
  selectCuratedModelForMode,
  type StudioMode,
  type StyleRecipe,
} from "../lib/model-selection";
import { ThumbnailGallery, type GalleryTile } from "./ThumbnailGallery";
import type {
  GenerationSettings,
  LoraGalleryItem,
  ModelGalleryItem,
  UiDefaults,
} from "../lib/tauri-api";
import { StyleThumbnailGrid } from "./StyleThumbnailGrid";
import { MarketplaceTab } from "./MarketplaceTab";
import { LoraStackPanel } from "./LoraStackPanel";
import { GenerationSettingsPanel } from "./GenerationSettingsPanel";
import { AutomationPanel } from "./AutomationPanel";
import { RecipeActions } from "./RecipeActions";
import { DiscoverWorkflowTab } from "./DiscoverWorkflowTab";
import { DiscoverRecipeTab } from "./DiscoverRecipeTab";
import {
  aggregateLoraKeywords,
  importFooocusStyles,
  listWorkflowTemplates,
  type DiscoverWorkflowTemplate,
  type StudioSettings,
} from "../lib/studioBridge";
import {
  loadDiscoverLibrarySurface,
  loadDiscoverLibraryTab,
  saveDiscoverLibrarySurface,
  saveDiscoverLibraryTab,
  loadDiscoverTab,
  saveDiscoverTab,
  type DiscoverLibrarySurface,
  type DiscoverLibraryTab,
  type DiscoverTab,
} from "../lib/discover";
import { DEFAULT_MAX_LORA_STACK } from "../lib/loraStack";
import type { StyleGroup } from "../lib/inventory";

type Tab = "discover" | "discover_recipes" | "discover_workflows" | "models" | "loras" | "styles" | "settings" | "automation";
type ModelSort = "recommended" | "name" | "newest" | "largest" | "family";

function formatModelSize(bytes?: number): string {
  if (!bytes) return "";
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  return `${Math.max(1, Math.round(bytes / 1024 ** 2))} MB`;
}

type Props = {
  settings: GenerationSettings;
  onChange: (patch: Partial<GenerationSettings>) => void;
  modelGallery: ModelGalleryItem[];
  loraGallery: LoraGalleryItem[];
  modelFilter: string;
  onModelFilterChange: (value: string) => void;
  loraFilter: string;
  onLoraFilterChange: (value: string) => void;
  profileHints: string[];
  galleryLoading?: boolean;
  onSelectModel: (item: ModelGalleryItem) => void;
  onToggleLora: (name: string) => void;
  stylesList: StyleRecipe[];
  styleGroups: StyleGroup[];
  aspectPresets: string[];
  uiDefaults: UiDefaults | null;
  onRefreshInventory: () => void;
  activeModelLabel: string;
  studioMode: string;
  onStyleChange: (styleId: string) => void;
  modelDependencies?: { missing: Array<{ id?: string; relative?: string; note?: string }>; ready: boolean };
  companionDownloadBusy?: boolean;
  onDownloadCompanions?: () => void;
  onInstallCompanionItems?: (items: import("../lib/tauri-api").ModelDependencyItem[]) => void;
  onRefreshModelDependencies?: () => void;
  studioSettings?: StudioSettings | null;
  onSaveStudioSettings?: (patch: StudioSettings) => void | Promise<void>;
  advancedMode?: boolean;
  simpleExperience?: boolean;
  imageNumberMax?: number;
  civitaiApiKey?: string;
  generating?: boolean;
  vramGb?: number | null;
  mpsAvailable?: boolean | null;
  onAutomationStatus?: (message: string) => void;
  onRunAutomationBatch?: (runner: () => Promise<{ ok: boolean }>) => void;
  onRefreshOutputs?: () => void;
  onBeforeAutomationRun?: () => Promise<boolean>;
  onRevealPath?: (path: string) => void;
  onExecuteWorkflowRecipe?: (recipe: Record<string, unknown>, source?: string) => Promise<boolean>;
};

export function InspectorPanel({
  settings,
  onChange,
  modelGallery,
  loraGallery,
  modelFilter,
  onModelFilterChange,
  loraFilter,
  onLoraFilterChange,
  profileHints,
  galleryLoading,
  onSelectModel,
  onToggleLora,
  stylesList,
  styleGroups,
  aspectPresets,
  uiDefaults,
  onRefreshInventory,
  activeModelLabel,
  studioMode,
  onStyleChange,
  modelDependencies,
  companionDownloadBusy,
  onDownloadCompanions,
  onInstallCompanionItems,
  onRefreshModelDependencies,
  studioSettings,
  onSaveStudioSettings,
  advancedMode = false,
  simpleExperience = false,
  imageNumberMax = 8,
  civitaiApiKey = "",
  generating = false,
  vramGb,
  mpsAvailable,
  onAutomationStatus,
  onRunAutomationBatch,
  onRefreshOutputs,
  onBeforeAutomationRun,
  onRevealPath,
  onExecuteWorkflowRecipe,
}: Props) {
  const [surface, setSurface] = useState<DiscoverLibrarySurface>(() => loadDiscoverLibrarySurface());
  const [libraryTab, setLibraryTab] = useState<DiscoverLibraryTab>(() => loadDiscoverLibraryTab());
  const [discoverTab, setDiscoverTab] = useState<DiscoverTab>(() => loadDiscoverTab());
  const [workflowTemplates, setWorkflowTemplates] = useState<DiscoverWorkflowTemplate[]>([]);
  const [workflowLoading, setWorkflowLoading] = useState(false);
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [styleFilter, setStyleFilter] = useState("");
  const [modelFamily, setModelFamily] = useState("all");
  const [modelSort, setModelSort] = useState<ModelSort>("recommended");

  const tab: Tab = surface === "discover" ? discoverTab : libraryTab;
  const setTab = useCallback((next: Tab) => {
    if (next === "discover" || next === "discover_recipes" || next === "discover_workflows") {
      setDiscoverTab(next);
      saveDiscoverTab(next);
      return;
    }
    setLibraryTab(next);
    saveDiscoverLibraryTab(next);
  }, []);

  const switchSurface = useCallback((next: DiscoverLibrarySurface) => {
    setSurface(next);
    saveDiscoverLibrarySurface(next);
  }, []);

  const handleImportFooocusStyles = useCallback(async (payload: unknown) => {
    const result = await importFooocusStyles(payload);
    if (!result.ok) throw new Error(result.error ?? "Style import failed");
    await onRefreshInventory();
  }, [onRefreshInventory]);

  useEffect(() => {
    if (surface !== "discover" || discoverTab !== "discover_workflows") return;
    let alive = true;
    setWorkflowLoading(true);
    setWorkflowError(null);
    void listWorkflowTemplates()
      .then((result) => {
        if (!alive) return;
        if (!result.ok) throw new Error(result.error ?? "Could not load workflow templates");
        setWorkflowTemplates(result.templates ?? []);
      })
      .catch((error) => {
        if (alive) setWorkflowError(error instanceof Error ? error.message : String(error));
      })
      .finally(() => {
        if (alive) setWorkflowLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [discoverTab, surface]);

  const showEditStrength = Boolean(settings.input_image) || ["kontext", "inpaint", "img2img", "qwen_edit"].includes(settings.edit_type ?? "");
  const isQwenModel = (settings.model ?? activeModelLabel ?? "").toLowerCase().includes("qwen");

  const isEditFamily = isEditFamilyMode(studioMode as StudioMode);
  const powerUserInspector = advancedMode;
  const simpleInspectorLocked = simpleExperience;
  const isUpscale = studioMode === "upscale";
  const isInpaint = studioMode === "inpaint";
  const isEdit = studioMode === "edit";
  /** Create-style aspect / batch controls — not edit, inpaint, or upscale. */
  const showGenerateLikeSettings =
    studioMode === "generate" ||
    studioMode === "agent" ||
    (powerUserInspector && (isEdit || isInpaint));
  const activeStyleId = settings.style;
  const activeLoras = settings.lora ?? [];
  const modelFamilies = useMemo(
    () => Array.from(new Set(modelGallery.map((item) => item.family).filter(Boolean))).sort(),
    [modelGallery],
  );
  const sortedModelGallery = useMemo(() => {
    let gallery = modelGallery.filter((item) => modelFamily === "all" || item.family === modelFamily);
    if (modelSort !== "recommended") {
      gallery = [...gallery].sort((a, b) => {
        if (modelSort === "newest") return (b.modified_at ?? 0) - (a.modified_at ?? 0);
        if (modelSort === "largest") return (b.size_bytes ?? 0) - (a.size_bytes ?? 0);
        if (modelSort === "family") {
          return a.family.localeCompare(b.family) || a.caption.localeCompare(b.caption);
        }
        return a.caption.localeCompare(b.caption);
      });
    }
    gallery = sortGalleryForInpaintMode(gallery, studioMode as StudioMode);
    gallery = sortGalleryForUpscaleMode(gallery, studioMode as StudioMode);
    gallery = sortGalleryForEditMode(gallery, studioMode as StudioMode);
    return gallery;
  }, [modelFamily, modelGallery, modelSort, studioMode]);

  const curatedUpscaleModel = useMemo(
    () =>
      isUpscale
        ? selectCuratedModelForMode("upscale", modelGallery, settings.model)
        : "",
    [isUpscale, modelGallery, settings.model],
  );

  const upscaleModelManual = useMemo(() => {
    if (!isUpscale || !settings.model?.trim()) return false;
    return settings.model !== curatedUpscaleModel;
  }, [curatedUpscaleModel, isUpscale, settings.model]);

  const curatedInpaintModel = useMemo(
    () =>
      isInpaint
        ? selectCuratedModelForMode("inpaint", modelGallery, settings.model)
        : "",
    [isInpaint, modelGallery, settings.model],
  );

  const inpaintModelManual = useMemo(() => {
    if (!isInpaint || !settings.model?.trim()) return false;
    return settings.model !== curatedInpaintModel;
  }, [curatedInpaintModel, isInpaint, settings.model]);

  const curatedEditModel = useMemo(
    () =>
      isEdit ? selectCuratedModelForMode("edit", modelGallery, settings.model) : "",
    [isEdit, modelGallery, settings.model],
  );

  const editModelManual = useMemo(() => {
    if (!isEdit || !settings.model?.trim()) return false;
    return settings.model !== curatedEditModel;
  }, [curatedEditModel, isEdit, settings.model]);

  const routedModelLabel = useMemo(() => {
    if (!isEditFamily) return activeModelLabel;
    if (isUpscale && upscaleModelManual) {
      return activeModelLabel;
    }
    if (isInpaint && inpaintModelManual) {
      return activeModelLabel;
    }
    if (isEdit && editModelManual) {
      return activeModelLabel;
    }
    const routed = selectCuratedModelForMode(
      studioMode as StudioMode,
      modelGallery,
      settings.model,
    );
    return modelBasename(routed || settings.model || activeModelLabel);
  }, [
    activeModelLabel,
    editModelManual,
    inpaintModelManual,
    isEditFamily,
    isInpaint,
    isUpscale,
    upscaleModelManual,
    modelGallery,
    settings.model,
    studioMode,
  ]);

  const editRouteSubtitle = useMemo(() => {
    if (!isEditFamily) return undefined;
    if (isUpscale) {
      return upscaleModelManual
        ? `User override · ${activeModelLabel}`
        : `SDXL upscale · ${modelBasename(curatedUpscaleModel || routedModelLabel) || "missing"}`;
    }
    if (isInpaint) {
      return inpaintModelManual
        ? `User override · ${activeModelLabel}`
        : `Default inpaint · ${modelBasename(curatedInpaintModel || routedModelLabel) || "missing"}`;
    }
    if (isEdit) {
      return editModelManual
        ? `User override · ${activeModelLabel}`
        : `Default edit · ${modelBasename(curatedEditModel || routedModelLabel) || "missing"}`;
    }
    return `Selected · ${routedModelLabel}`;
  }, [
    activeModelLabel,
    curatedEditModel,
    curatedUpscaleModel,
    upscaleModelManual,
    curatedInpaintModel,
    editModelManual,
    inpaintModelManual,
    isEdit,
    isEditFamily,
    isInpaint,
    isUpscale,
    routedModelLabel,
    settings.upscale_method,
  ]);

  const modelTiles: GalleryTile[] = useMemo(
    () =>
      sortedModelGallery.map((m) => {
        const fillBadge = isInpaint && isFluxFillModel(m) ? "Fill" : undefined;
        const kontextBadge = isEdit && isFluxKontextEditModel(m) ? "Kontext" : undefined;
        const categoryBadge = m.category !== "checkpoints" ? m.category : undefined;
        return {
          key: `${m.category}:${m.relative_path}`,
          value: `${m.category}:${m.relative_path}`,
          label: PathLabel(m.caption),
          sublabel: [m.family, formatModelSize(m.size_bytes)].filter(Boolean).join(" · "),
          thumbnailPath: m.thumbnail_path,
          badge: fillBadge ?? kontextBadge ?? categoryBadge,
          selected: modelMatches(m, settings.model),
        };
      }),
    [isInpaint, settings.model, sortedModelGallery],
  );

  const loraTiles: GalleryTile[] = useMemo(
    () =>
      loraGallery.map((l) => ({
        key: l.relative_path ?? l.name,
        value: l.relative_path ?? l.name,
        label: l.stem || l.name,
        sublabel:
          l.relative_path && l.relative_path !== l.name
            ? PathLabel(l.relative_path)
            : undefined,
        thumbnailPath: l.thumbnail_path,
        selected: activeLoras.some((e) =>
          e.startsWith(`${l.relative_path ?? l.name}:`),
        ),
      })),
    [loraGallery, activeLoras],
  );

  const tabs: { id: Tab; label: string; icon: typeof Boxes }[] = useMemo(() => {
    const tabMeta: Record<Tab, { label: string; icon: typeof Boxes }> = {
      discover: { label: "Discover", icon: Globe },
      discover_recipes: { label: "Recipes", icon: Search },
      discover_workflows: { label: "Workflows", icon: LayoutGrid },
      models: { label: "Models", icon: Boxes },
      loras: { label: "LoRAs", icon: Layers },
      styles: { label: "Styles", icon: Palette },
      settings: { label: surface === "library" ? "Generate" : "Generation", icon: SlidersHorizontal },
      automation: { label: surface === "library" ? "Automate" : "Batch", icon: LayoutGrid },
    };
    const ids: Tab[] = surface === "discover"
      ? ["discover", "discover_recipes", "discover_workflows"]
      : inspectorTabsForMode({
          studioMode,
          simpleInspectorLocked,
          powerUserInspector,
          isEditFamily,
          isInpaint,
          isUpscale,
        });
    return ids.map((id) => ({ id, ...tabMeta[id] }));
  }, [
    isEditFamily,
    isInpaint,
    isUpscale,
    powerUserInspector,
    simpleInspectorLocked,
    studioMode,
    surface,
  ]);

  const tabScrollRef = useRef<HTMLDivElement>(null);
  const [canScrollTabsLeft, setCanScrollTabsLeft] = useState(false);
  const [canScrollTabsRight, setCanScrollTabsRight] = useState(false);

  const updateTabScrollHints = useCallback(() => {
    const el = tabScrollRef.current;
    if (!el) return;
    setCanScrollTabsLeft(el.scrollLeft > 4);
    setCanScrollTabsRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }, []);

  useEffect(() => {
    if (!tabs.some((t) => t.id === tab)) {
      setTab(tabs[0]?.id ?? "settings");
    }
  }, [tab, tabs]);

  useEffect(() => {
    if (surface === "library" && isUpscale && tab !== "settings" && tab !== "models") {
      setTab("settings");
    }
  }, [isUpscale, surface, tab]);

  useEffect(() => {
    const el = tabScrollRef.current;
    if (!el) return;
    updateTabScrollHints();
    el.addEventListener("scroll", updateTabScrollHints, { passive: true });
    const ro = new ResizeObserver(updateTabScrollHints);
    ro.observe(el);
    return () => {
      el.removeEventListener("scroll", updateTabScrollHints);
      ro.disconnect();
    };
  }, [updateTabScrollHints, tabs.length]);

  useEffect(() => {
    const el = tabScrollRef.current?.querySelector(
      `[data-tab-id="${tab}"]`,
    ) as HTMLElement | null;
    el?.scrollIntoView({ behavior: "smooth", inline: "nearest", block: "nearest" });
    window.requestAnimationFrame(updateTabScrollHints);
  }, [tab, updateTabScrollHints, tabs.length]);

  const scrollTabs = (direction: -1 | 1) => {
    tabScrollRef.current?.scrollBy({
      left: direction * 112,
      behavior: "smooth",
    });
  };

  const loraTabContent = !isUpscale ? (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="shrink-0 space-y-2">
        <div className="rounded-lg border border-dfui-accent/25 bg-dfui-accent/5 px-2.5 py-2">
          <p className="text-[10px] uppercase tracking-wide text-dfui-muted">
            Active stack
          </p>
          <p className="text-xs text-dfui-secondary">
            {activeLoras.length === 0
              ? "No LoRAs selected — pick tiles below or add from a style recipe."
              : `${activeLoras.length} LoRA${activeLoras.length === 1 ? "" : "s"} in stack`}
          </p>
        </div>
        {activeLoras.length > 0 && (
          <div className="max-h-40 overflow-y-auto rounded-lg border border-dfui-border/40 bg-dfui-bg/20">
            <LoraStackPanel
              lora={activeLoras}
              loraMin={studioSettings?.lora_min ?? 0}
              loraMax={studioSettings?.lora_max ?? 2}
              maxStack={DEFAULT_MAX_LORA_STACK}
              loraKeywords={settings.lora_keywords ?? ""}
              onLoraKeywordsChange={(lora_keywords) =>
                onChange({ lora_keywords })
              }
              onSyncKeywordsFromStack={async () => {
                const kw = await aggregateLoraKeywords(activeLoras);
                onChange({ lora_keywords: kw });
              }}
              onChange={(lora) => onChange({ lora })}
            />
          </div>
        )}
        <div className="flex items-center justify-between gap-2">
          <input
            value={loraFilter}
            onChange={(e) => onLoraFilterChange(e.target.value)}
            placeholder="Filter LoRAs…"
            className="df-input min-w-0 flex-1 px-2.5 py-1.5 text-xs"
          />
          {galleryLoading && (
            <span className="shrink-0 font-mono text-[9px] text-dfui-tertiary">
              loading…
            </span>
          )}
          {activeLoras.length > 0 && (
            <button
              type="button"
              className="shrink-0 text-[10px] text-dfui-tertiary hover:text-dfui-fg"
              onClick={() => onChange({ lora: [] })}
            >
              Clear
            </button>
          )}
        </div>
      </div>
      <div className="df-gallery-pane">
        <ThumbnailGallery
          items={loraTiles}
          multiSelect
          emptyMessage="No LoRAs found."
          onSelect={(name) => onToggleLora(name)}
        />
      </div>
    </div>
  ) : null;

  return (
    <aside className="flex h-full min-h-0 min-w-0 flex-col glass-panel rounded-none border-y-0 border-r-0">
      <div className="shrink-0 border-b border-dfui-border/40 bg-dfui-panel/40 backdrop-blur-md">
        <div className="flex gap-1 px-2 pt-2" role="tablist" aria-label="Asset workspace">
          {(["discover", "library"] as DiscoverLibrarySurface[]).map((item) => (
            <button
              key={item}
              type="button"
              role="tab"
              aria-selected={surface === item}
              onClick={() => switchSurface(item)}
              className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-[10px] font-semibold transition ${
                surface === item
                  ? "border border-dfui-accent/60 bg-dfui-accent/15 text-dfui-fg"
                  : "border border-transparent text-dfui-muted hover:border-dfui-border/50 hover:text-dfui-fg"
              }`}
            >
              {item === "discover" ? <Globe size={12} /> : <Boxes size={12} />}
              {item === "discover" ? "Discover" : "Library"}
            </button>
          ))}
        </div>
        <div className="relative flex items-stretch">
          {canScrollTabsLeft && (
            <>
              <div
                className="pointer-events-none absolute left-8 top-0 z-[1] h-full w-6 bg-gradient-to-r from-dfui-panel/95 to-transparent"
                aria-hidden
              />
              <button
                type="button"
                aria-label="Show previous tabs"
                onClick={() => scrollTabs(-1)}
                className="relative z-[2] flex w-8 shrink-0 items-center justify-center text-dfui-secondary transition hover:bg-dfui-surface-hover/60 hover:text-dfui-fg"
              >
                <ChevronLeft size={16} strokeWidth={2.25} />
              </button>
            </>
          )}
          <div
            ref={tabScrollRef}
            className="df-tab-scroll flex min-w-0 flex-1 gap-1 overflow-x-auto scroll-smooth px-2 py-2"
          >
            {tabs.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                data-tab-id={id}
                onClick={() => setTab(id)}
                className={`flex shrink-0 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-all duration-200 ${
                  tab === id ? "df-tab-active" : "df-tab"
                }`}
              >
                <Icon size={14} />
                {label}
                {id === "styles" && activeStyleId && activeStyleId !== "none" && (
                  <span className="rounded-full bg-dfui-accent/20 px-1.5 font-mono text-[9px] text-dfui-accent">
                    1
                  </span>
                )}
                {id === "loras" && activeLoras.length > 0 && (
                  <span className="rounded-full bg-dfui-accent/20 px-1.5 font-mono text-[9px] text-dfui-accent">
                    {activeLoras.length}
                  </span>
                )}
              </button>
            ))}
          </div>
          {canScrollTabsRight && (
            <>
              <button
                type="button"
                aria-label="Show more tabs"
                onClick={() => scrollTabs(1)}
                className="relative z-[2] flex w-8 shrink-0 items-center justify-center text-dfui-secondary transition hover:bg-dfui-surface-hover/60 hover:text-dfui-fg"
              >
                <ChevronRight size={16} strokeWidth={2.25} />
              </button>
              <div
                className="pointer-events-none absolute right-8 top-0 z-[1] h-full w-6 bg-gradient-to-l from-dfui-panel/95 to-transparent"
                aria-hidden
              />
            </>
          )}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden p-3 text-sm">
        {tab === "discover" && (
          <MarketplaceTab
            civitaiApiKey={civitaiApiKey}
            onRefreshInventory={onRefreshInventory}
          />
        )}

        {tab === "discover_recipes" && <DiscoverRecipeTab onChange={onChange} />}

        {tab === "discover_workflows" && (
          <DiscoverWorkflowTab
            templates={workflowTemplates}
            loading={workflowLoading}
            error={workflowError}
            onExecuteRecipe={onExecuteWorkflowRecipe}
          />
        )}

        {tab === "models" && (
          <InspectorGalleryPane
            footer={
              profileHints.length > 0 ? (
                <ul className="space-y-0.5 rounded-lg border border-dfui-accent/20 bg-dfui-accent/5 px-2 py-1.5">
                  {profileHints.map((h) => (
                    <li
                      key={h}
                      className="text-[10px] leading-snug text-dfui-secondary"
                    >
                      {h}
                    </li>
                  ))}
                </ul>
              ) : undefined
            }
            header={
              <>
                <div className="rounded-lg border border-dfui-accent/25 bg-dfui-accent/5 px-2.5 py-2">
                  <p className="text-[10px] uppercase tracking-wide text-dfui-muted">
                    Active model
                  </p>
                  <p className="truncate font-mono text-xs text-dfui-fg">
                    {activeModelLabel}
                  </p>
                  {modelDependencies && !modelDependencies.ready && (
                    <div className="mt-2 space-y-1.5 border-t border-dfui-border/30 pt-2">
                      <p className="text-[10px] text-amber-200/90">
                        Missing companion files ({modelDependencies.missing.length})
                      </p>
                      <ul className="max-h-24 space-y-0.5 overflow-y-auto text-[9px] text-dfui-tertiary">
                        {modelDependencies.missing.map((m) => (
                          <li
                            key={m.id ?? m.relative}
                            className="font-mono truncate"
                          >
                            {m.relative ?? m.id}
                          </li>
                        ))}
                      </ul>
                      <div className="flex flex-wrap gap-1.5 pt-0.5">
                        {onDownloadCompanions && (
                          <button
                            type="button"
                            disabled={companionDownloadBusy}
                            onClick={() => onDownloadCompanions()}
                            className="rounded-md border border-dfui-accent/40 bg-dfui-accent/10 px-2 py-1 text-[10px] font-medium text-dfui-accent hover:bg-dfui-accent/20 disabled:opacity-50"
                          >
                            {companionDownloadBusy
                              ? "Downloading…"
                              : "Download missing companions"}
                          </button>
                        )}
                        {onRefreshModelDependencies && (
                          <button
                            type="button"
                            onClick={() => onRefreshModelDependencies()}
                            className="rounded-md border border-dfui-border/50 px-2 py-1 text-[10px] text-dfui-muted hover:text-dfui-fg"
                          >
                            Recheck
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <input
                    value={modelFilter}
                    onChange={(e) => onModelFilterChange(e.target.value)}
                    placeholder="Filter checkpoints, Flux, HiDream…"
                    className="df-input min-w-0 flex-1 px-2.5 py-1.5 text-xs"
                  />
                  {galleryLoading && (
                    <span className="shrink-0 font-mono text-[9px] text-dfui-tertiary">
                      loading…
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={onRefreshInventory}
                    disabled={galleryLoading}
                    className="rounded-md border border-dfui-border/50 p-1.5 text-dfui-muted hover:text-dfui-fg disabled:opacity-50"
                    aria-label="Refresh model library"
                    title="Refresh model library"
                  >
                    <RefreshCw size={13} className={galleryLoading ? "animate-spin" : ""} />
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <select
                    value={modelFamily}
                    onChange={(e) => setModelFamily(e.target.value)}
                    className="df-select min-w-0 px-2 py-1.5 text-[10px]"
                    aria-label="Filter model family"
                  >
                    <option value="all">All families</option>
                    {modelFamilies.map((family) => <option key={family} value={family}>{family}</option>)}
                  </select>
                  <select
                    value={modelSort}
                    onChange={(e) => setModelSort(e.target.value as ModelSort)}
                    className="df-select min-w-0 px-2 py-1.5 text-[10px]"
                    aria-label="Sort models"
                  >
                    <option value="recommended">Recommended</option>
                    <option value="name">Name</option>
                    <option value="newest">Newest files</option>
                    <option value="largest">Largest files</option>
                    <option value="family">Family</option>
                  </select>
                </div>
                <p className="text-[9px] text-dfui-tertiary">{sortedModelGallery.length} models</p>
              </>
            }
          >
            <ThumbnailGallery
              items={modelTiles}
              emptyMessage="No models match. Add checkpoints under models/ or refresh."
              onSelect={(key) => {
                const item = sortedModelGallery.find(
                  (m) => `${m.category}:${m.relative_path}` === key,
                );
                if (item) void onSelectModel(item);
              }}
            />
          </InspectorGalleryPane>
        )}

        {tab === "loras" && loraTabContent}

        {tab === "styles" && (
          <StyleThumbnailGrid
            styles={stylesList}
            groups={styleGroups}
            filter={styleFilter}
            onFilterChange={setStyleFilter}
            onSelect={onStyleChange}
            activeStyle={settings.style}
            onImportFooocusStyles={handleImportFooocusStyles}
          />
        )}

        {tab === "settings" && (
          <div className="h-full min-h-0 overflow-y-auto">
            <RecipeActions settings={settings} onChange={onChange} />
            <GenerationSettingsPanel
              settings={settings}
              onChange={onChange}
              aspectPresets={aspectPresets}
              uiDefaults={uiDefaults}
              studioSettings={studioSettings}
              onSaveStudioSettings={onSaveStudioSettings}
              imageNumberMax={imageNumberMax}
              studioMode={studioMode}
              isInpaint={isInpaint}
              showGenerateLikeSettings={showGenerateLikeSettings}
              showEditStrength={showEditStrength}
              routedModelLabel={routedModelLabel}
              editRouteSubtitle={editRouteSubtitle}
              isQwenModel={isQwenModel}
              activeModelLabel={activeModelLabel}
              advancedMode={advancedMode}
              modelGallery={modelGallery}
              onInstallCompanionItems={onInstallCompanionItems}
            />
          </div>
        )}
        {tab === "automation" && onRunAutomationBatch && onAutomationStatus ? (
          <AutomationPanel
            settings={settings}
            studioMode={studioMode as StudioMode}
            modelGallery={modelGallery}
            advancedMode={advancedMode}
            vramGb={vramGb}
            mpsAvailable={mpsAvailable}
            generating={generating}
            onStatus={onAutomationStatus}
            onRefreshOutputs={() => onRefreshOutputs?.()}
            onBeforeRun={onBeforeAutomationRun}
            onRevealPath={(path) => onRevealPath?.(path)}
            onRunBatch={onRunAutomationBatch}
          />
        ) : null}
      </div>
    </aside>
  );
}

function InspectorGalleryPane({
  header,
  footer,
  children,
}: {
  header: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="shrink-0 space-y-2">{header}</div>
      <div className="df-gallery-pane">{children}</div>
      {footer ? <div className="shrink-0">{footer}</div> : null}
    </div>
  );
}

function PathLabel(caption: unknown): string {
  const text = typeof caption === "string" ? caption.trim() : "";
  if (!text) return "Untitled";
  const bracketEnd = text.indexOf("] ");
  if (text.startsWith("[") && bracketEnd > 0) {
    return text.slice(bracketEnd + 2).trim() || "Untitled";
  }
  const parts = text.split(/[/\\]/);
  return parts[parts.length - 1] || text;
}
