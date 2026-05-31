import {
  Bot,
  Boxes,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Globe,
  Layers,
  Palette,
  ShieldCheck,
  SlidersHorizontal,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { modelMatches, type StyleRecipe } from "../lib/model-selection";
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
import {
  aggregateLoraKeywords,
  type AgentProviderPreset,
  type AgentProviderTestResult,
  type DreamForgeAppConfig,
  type DreamForgeAppConfigPatch,
  type StudioSettings,
  type UserStyleProfile,
} from "../lib/studioBridge";
import { DEFAULT_MAX_LORA_STACK } from "../lib/loraStack";

type Tab = "discover" | "models" | "loras" | "styles" | "settings";

type Props = {
  settings: GenerationSettings;
  onChange: (patch: Partial<GenerationSettings>) => void;
  modelGallery: ModelGalleryItem[];
  loraGallery: LoraGalleryItem[];
  modelFilter: string;
  onModelFilterChange: (value: string) => void;
  loraFilter: string;
  onLoraFilterChange: (value: string) => void;
  lockFamilyDefaults: boolean;
  onLockFamilyDefaultsChange: (value: boolean) => void;
  profileHints: string[];
  galleryLoading?: boolean;
  onSelectModel: (item: ModelGalleryItem) => void;
  onToggleLora: (name: string) => void;
  stylesList: StyleRecipe[];
  aspectPresets: string[];
  uiDefaults: UiDefaults | null;
  onRefreshInventory: () => void;
  activeModelLabel: string;
  studioMode: string;
  onStyleChange: (styleId: string) => void;
  modelDependencies?: { missing: Array<{ id?: string; relative?: string; note?: string }>; ready: boolean };
  companionDownloadBusy?: boolean;
  onDownloadCompanions?: () => void;
  onRefreshModelDependencies?: () => void;
  studioSettings?: StudioSettings | null;
  onSaveStudioSettings?: (patch: StudioSettings) => void | Promise<void>;
  appConfig?: DreamForgeAppConfig | null;
  agentProviders?: AgentProviderPreset[];
  agentProviderTest?: AgentProviderTestResult | null;
  agentProviderBusy?: boolean;
  onSaveAppConfig?: (patch: DreamForgeAppConfigPatch) => void | Promise<void>;
  onTestAgentProvider?: (patch?: DreamForgeAppConfigPatch) => void | Promise<void>;
  imageNumberMax?: number;
  userStyleProfile?: UserStyleProfile | null;
  userStyleProfilePath?: string;
  onUserStyleMemoryEnabledChange?: (enabled: boolean) => void | Promise<void>;
  onClearUserStyleMemory?: () => void | Promise<void>;
  onExportUserStyleMemory?: () => void | Promise<void>;
};

const CUSTOM_PERF = "Custom...";

export function InspectorPanel({
  settings,
  onChange,
  modelGallery,
  loraGallery,
  modelFilter,
  onModelFilterChange,
  loraFilter,
  onLoraFilterChange,
  lockFamilyDefaults,
  onLockFamilyDefaultsChange,
  profileHints,
  galleryLoading,
  onSelectModel,
  onToggleLora,
  stylesList,
  aspectPresets,
  uiDefaults,
  onRefreshInventory,
  activeModelLabel,
  studioMode,
  onStyleChange,
  modelDependencies,
  companionDownloadBusy,
  onDownloadCompanions,
  onRefreshModelDependencies,
  studioSettings,
  onSaveStudioSettings,
  appConfig,
  agentProviders = [],
  agentProviderTest,
  agentProviderBusy,
  onSaveAppConfig,
  onTestAgentProvider,
  imageNumberMax = 8,
  userStyleProfile,
  userStyleProfilePath,
  onUserStyleMemoryEnabledChange,
  onClearUserStyleMemory,
  onExportUserStyleMemory,
}: Props) {
  const [tab, setTab] = useState<Tab>("models");
  const [styleFilter, setStyleFilter] = useState("");

  const performances = uiDefaults?.performances ?? [
    "Speed",
    "Quality",
    "Extreme Speed",
    CUSTOM_PERF,
  ];
  const isCustomPerf =
    (settings.performance ?? "Speed") === CUSTOM_PERF ||
    settings.performance === "Custom";
  const showAdvancedSampling = Boolean(appConfig?.ui.advanced_mode) || isCustomPerf;
  const showEditStrength = Boolean(settings.input_image) || ["kontext", "inpaint", "img2img", "qwen_edit"].includes(settings.edit_type ?? "");
  const isQwenModel = (settings.model ?? activeModelLabel).toLowerCase().includes("qwen");

  const activeStyleId = settings.style;
  const activeLoras = settings.lora ?? [];
  const activeProvider = agentProviders.find(
    (p) => p.id === appConfig?.agent.provider,
  );
  const requiresAgentKey = Boolean(activeProvider?.requires_api_key);

  const isUpscale = studioMode === "upscale";

  const modelTiles: GalleryTile[] = useMemo(
    () =>
      modelGallery.map((m) => ({
        key: `${m.category}:${m.relative_path}`,
        value: `${m.category}:${m.relative_path}`,
        label: PathLabel(m.caption),
        sublabel: m.family,
        thumbnailPath: m.thumbnail_path,
        badge: m.category !== "checkpoints" ? m.category : undefined,
        selected: modelMatches(m, settings.model),
      })),
    [modelGallery, settings.model],
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

  const tabs: { id: Tab; label: string; icon: typeof Boxes }[] = useMemo(
    () => [
      { id: "discover", label: "Discover", icon: Globe },
      { id: "models", label: "Models", icon: Boxes },
      ...(!isUpscale
        ? [{ id: "loras" as const, label: "LoRAs", icon: Layers }]
        : []),
      { id: "styles", label: "Styles", icon: Palette },
      { id: "settings", label: "Settings", icon: SlidersHorizontal },
    ],
    [isUpscale],
  );

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
    if (isUpscale && tab === "loras") {
      setTab("models");
    }
  }, [isUpscale, tab]);

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
    <aside className="flex h-full min-w-0 flex-col glass-panel rounded-none border-y-0 border-r-0">
      <div className="relative flex items-stretch border-b border-dfui-border/40 bg-dfui-panel/40 backdrop-blur-md">
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

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden p-3 text-sm">
        {tab === "discover" && (
          <MarketplaceTab
            civitaiApiKey={settings.civitai_api_key ?? ""}
            onApiKeyChange={(key) => onChange({ civitai_api_key: key })}
            onRefreshInventory={onRefreshInventory}
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
                <label className="flex items-center gap-2 text-[11px] text-dfui-muted">
                  <input
                    type="checkbox"
                    checked={lockFamilyDefaults}
                    onChange={(e) =>
                      onLockFamilyDefaultsChange(e.target.checked)
                    }
                    className="accent-dfui-accent"
                  />
                  Apply model family defaults (like web UI)
                </label>

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
                </div>
              </>
            }
          >
            <ThumbnailGallery
              items={modelTiles}
              emptyMessage="No models match. Add checkpoints under models/ or refresh."
              onSelect={(key) => {
                const item = modelGallery.find(
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
            filter={styleFilter}
            onFilterChange={setStyleFilter}
            onSelect={onStyleChange}
            activeStyle={settings.style}
          />
        )}

        {tab === "settings" && (
          <div className="h-full min-h-0 overflow-y-auto">
          <div className="space-y-3">
            {userStyleProfile && onUserStyleMemoryEnabledChange && (
              <div className="space-y-2 rounded-lg border border-dfui-border/50 bg-dfui-bg/30 p-2.5">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-[10px] font-medium uppercase tracking-wide text-dfui-muted">
                      Local style memory
                    </p>
                    <p className="text-[10px] text-dfui-tertiary">
                      Opt-in preferences stored on this machine only
                    </p>
                  </div>
                  <label className="inline-flex items-center gap-1.5 text-[10px] text-dfui-secondary">
                    <input
                      type="checkbox"
                      checked={userStyleProfile.enabled}
                      onChange={(e) =>
                        void onUserStyleMemoryEnabledChange(e.target.checked)
                      }
                      className="accent-dfui-accent"
                    />
                    Enabled
                  </label>
                </div>
                <p className="text-[10px] text-dfui-tertiary">
                  {userStyleProfile.generation_count} remembered job
                  {userStyleProfile.generation_count === 1 ? "" : "s"}
                  {userStyleProfile.favorite_models[0]
                    ? ` · top model: ${userStyleProfile.favorite_models[0]}`
                    : ""}
                </p>
                {userStyleProfilePath && (
                  <p className="truncate font-mono text-[9px] text-dfui-muted">
                    {userStyleProfilePath}
                  </p>
                )}
                <div className="flex flex-wrap gap-1.5">
                  {onExportUserStyleMemory && (
                    <button
                      type="button"
                      onClick={() => void onExportUserStyleMemory()}
                      className="rounded-md border border-dfui-border/60 px-2 py-1 text-[10px] text-dfui-secondary hover:border-dfui-accent/40"
                    >
                      Export JSON
                    </button>
                  )}
                  {onClearUserStyleMemory && (
                    <button
                      type="button"
                      onClick={() => void onClearUserStyleMemory()}
                      className="rounded-md border border-amber-400/30 px-2 py-1 text-[10px] text-amber-200 hover:border-amber-300/50"
                    >
                      Clear memory
                    </button>
                  )}
                </div>
              </div>
            )}
            {appConfig && onSaveAppConfig && (
              <div className="space-y-2 rounded-lg border border-dfui-accent/25 bg-dfui-accent/5 p-2.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Bot size={14} className="text-dfui-accent" />
                    <div>
                      <p className="text-[10px] font-medium uppercase tracking-wide text-dfui-muted">
                        Agent provider
                      </p>
                      <p className="text-[10px] text-dfui-tertiary">
                        Backend-owned config, keys redacted on read
                      </p>
                    </div>
                  </div>
                  {agentProviderTest && (
                    <span
                      className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-1 text-[9px] ${
                        agentProviderTest.ok
                          ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
                          : "border-amber-400/30 bg-amber-400/10 text-amber-200"
                      }`}
                    >
                      {agentProviderTest.ok ? (
                        <CheckCircle2 size={11} />
                      ) : (
                        <XCircle size={11} />
                      )}
                      {agentProviderTest.ok ? "Connected" : "Check failed"}
                    </span>
                  )}
                </div>
                <label className="block">
                  <span className="text-[10px] text-dfui-tertiary">Provider</span>
                  <select
                    value={appConfig.agent.provider}
                    onChange={(e) => {
                      const preset = agentProviders.find(
                        (p) => p.id === e.target.value,
                      );
                      void onSaveAppConfig({
                        agent: {
                          provider: e.target.value,
                          base_url: preset?.base_url ?? appConfig.agent.base_url,
                          model: preset?.default_model ?? appConfig.agent.model,
                        },
                      });
                    }}
                    className="df-select mt-0.5 w-full px-2.5 py-2 text-xs"
                  >
                    {agentProviders.map((provider) => (
                      <option key={provider.id} value={provider.id}>
                        {provider.label}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <label className="block">
                    <span className="text-[10px] text-dfui-tertiary">
                      Base URL
                    </span>
                    <input
                      defaultValue={appConfig.agent.base_url}
                      onBlur={(e) =>
                        void onSaveAppConfig({
                          agent: { base_url: e.target.value },
                        })
                      }
                      className="df-input mt-0.5 w-full px-2 py-1.5 font-mono text-[10px]"
                    />
                  </label>
                  <label className="block">
                    <span className="text-[10px] text-dfui-tertiary">Model</span>
                    <input
                      defaultValue={appConfig.agent.model}
                      onBlur={(e) =>
                        void onSaveAppConfig({
                          agent: { model: e.target.value },
                        })
                      }
                      className="df-input mt-0.5 w-full px-2 py-1.5 font-mono text-[10px]"
                    />
                  </label>
                </div>
                {requiresAgentKey && (
                  <label className="block">
                    <span className="text-[10px] text-dfui-tertiary">API key</span>
                    <input
                      type="password"
                      placeholder={
                        appConfig.agent.api_key_configured
                          ? `Configured ****${appConfig.agent.api_key_tail ?? ""}`
                          : "Paste provider key"
                      }
                      onBlur={(e) => {
                        const apiKey = e.target.value.trim();
                        if (!apiKey) return;
                        void onSaveAppConfig({
                          agent: { api_key: apiKey },
                        });
                        e.currentTarget.value = "";
                      }}
                      className="df-input mt-0.5 w-full px-2 py-1.5 font-mono text-[10px]"
                    />
                  </label>
                )}
                <label className="block">
                  <span className="text-[10px] text-dfui-tertiary">
                    Agent instructions
                  </span>
                  <textarea
                    rows={2}
                    defaultValue={appConfig.agent.custom_instructions}
                    onBlur={(e) =>
                      void onSaveAppConfig({
                        agent: {
                          custom_instructions: e.target.value,
                        },
                      })
                    }
                    className="df-input mt-0.5 w-full resize-none px-2 py-1.5 text-[10px]"
                    placeholder="Prefer Arabic typography workflows, ask before cloud image context…"
                  />
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <label className="flex items-start gap-2 text-[10px] text-dfui-muted">
                    <input
                      type="checkbox"
                      checked={appConfig.agent.approval_required}
                      onChange={(e) =>
                        void onSaveAppConfig({
                          agent: {
                            approval_required: e.target.checked,
                          },
                        })
                      }
                      className="mt-0.5 accent-dfui-accent"
                    />
                    Approve agent workflow changes
                  </label>
                  <label className="flex items-start gap-2 text-[10px] text-dfui-muted">
                    <input
                      type="checkbox"
                      checked={appConfig.privacy.allow_cloud_image_context}
                      onChange={(e) =>
                        void onSaveAppConfig({
                          privacy: {
                            allow_cloud_image_context: e.target.checked,
                          },
                        })
                      }
                      className="mt-0.5 accent-dfui-accent"
                    />
                    Allow cloud image context
                  </label>
                  <label className="flex items-start gap-2 text-[10px] text-dfui-muted">
                    <input
                      type="checkbox"
                      checked={appConfig.ui.advanced_mode}
                      onChange={(e) =>
                        void onSaveAppConfig({
                          ui: { advanced_mode: e.target.checked },
                        })
                      }
                      className="mt-0.5 accent-dfui-accent"
                    />
                    Advanced model overrides
                  </label>
                </div>
                <div className="flex items-center justify-between gap-2 border-t border-dfui-border/30 pt-2">
                  <span className="inline-flex items-center gap-1 text-[10px] text-dfui-tertiary">
                    <ShieldCheck size={12} />
                    {activeProvider?.mode === "cloud"
                      ? "Cloud provider"
                      : activeProvider?.mode === "local"
                        ? "Local provider"
                        : "Custom endpoint"}
                  </span>
                  <button
                    type="button"
                    disabled={agentProviderBusy}
                    onClick={() => void onTestAgentProvider?.()}
                    className="rounded-md border border-dfui-accent/40 bg-dfui-accent/10 px-2 py-1 text-[10px] font-medium text-dfui-accent hover:bg-dfui-accent/20 disabled:opacity-50"
                  >
                    {agentProviderBusy ? "Testing…" : "Test connection"}
                  </button>
                </div>
                {agentProviderTest?.detail && (
                  <p className="break-words font-mono text-[9px] leading-snug text-dfui-tertiary">
                    {agentProviderTest.detail}
                  </p>
                )}
              </div>
            )}
            <label className="block">
              <span className="text-xs text-dfui-muted">Performance (DreamForge)</span>
              <select
                value={settings.performance ?? "Speed"}
                onChange={(e) => onChange({ performance: e.target.value })}
                className="df-select mt-1 w-full px-2.5 py-2 text-xs"
              >
                {performances.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-dfui-muted">VRAM profile</span>
              <select
                value={settings.vram_profile ?? "auto"}
                onChange={(e) =>
                  onChange({
                    vram_profile: e.target.value as GenerationSettings["vram_profile"],
                  })
                }
                className="df-select mt-1 w-full px-2.5 py-2 text-xs"
              >
                <option value="auto">auto</option>
                <option value="16gb">16 GB (RTX 5060 Ti)</option>
                <option value="8gb">8 GB</option>
                <option value="5gb">5 GB</option>
              </select>
            </label>
            {isUpscale && (
              <label className="block">
                <span className="text-xs text-dfui-muted">Upscale method</span>
                <select
                  value={settings.upscale_method ?? "fast_2x"}
                  onChange={(e) => onChange({ upscale_method: e.target.value })}
                  className="df-select mt-1 w-full px-2.5 py-2 text-xs"
                >
                  <option value="fast_2x">Fast 2× (OmniSR)</option>
                  <option value="fast_3x">Fast 3× (OmniSR)</option>
                  <option value="fast_4x">Fast 4× (OmniSR)</option>
                  <option value="quality">High quality 4× (HAT)</option>
                  <option value="sharp">Sharper 4×</option>
                  <option value="default">Quality 4× (NMKD)</option>
                </select>
              </label>
            )}
            {!isUpscale && (
              <label className="block">
                <span className="text-xs text-dfui-muted">Aspect ratio</span>
                <select
                  value={settings.aspect_ratio ?? "1024x1024"}
                  onChange={(e) => onChange({ aspect_ratio: e.target.value })}
                  className="df-select mt-1 w-full px-2.5 py-2 text-xs"
                >
                  {aspectPresets.map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {!isUpscale && (
              <label className="block">
                <span className="text-xs text-dfui-muted">
                  Image count — {settings.image_number ?? 1}
                </span>
                <input
                  type="range"
                  min={1}
                  max={imageNumberMax}
                  value={settings.image_number ?? 1}
                  onChange={(e) =>
                    onChange({ image_number: Number(e.target.value) })
                  }
                  className="mt-1 w-full accent-dfui-accent"
                />
              </label>
            )}
            <label className="flex items-center gap-2 text-[11px] text-dfui-muted">
              <input
                type="checkbox"
                checked={settings.auto_negative_prompt ?? false}
                onChange={(e) =>
                  onChange({ auto_negative_prompt: e.target.checked })
                }
                className="accent-dfui-accent"
              />
              Auto negative prompt (web UI)
            </label>
            <label className="block">
              <span className="text-xs text-dfui-muted">CLIP skip</span>
              <input
                type="number"
                min={1}
                max={12}
                value={settings.clip_skip ?? studioSettings?.clip_skip ?? 1}
                onChange={(e) =>
                  onChange({ clip_skip: Number(e.target.value) })
                }
                className="df-input mt-1 w-full px-2.5 py-1.5 font-mono text-xs"
              />
            </label>
            {onSaveStudioSettings && studioSettings && (
              <div className="grid grid-cols-2 gap-2">
                <label className="block">
                  <span className="text-[10px] text-dfui-tertiary">
                    LoRA weight min
                  </span>
                  <input
                    type="number"
                    step={0.05}
                    defaultValue={studioSettings.lora_min ?? 0}
                    onBlur={(e) =>
                      void onSaveStudioSettings({
                        lora_min: Number(e.target.value),
                      })
                    }
                    className="df-input mt-0.5 w-full font-mono text-[10px]"
                  />
                </label>
                <label className="block">
                  <span className="text-[10px] text-dfui-tertiary">
                    LoRA weight max
                  </span>
                  <input
                    type="number"
                    step={0.05}
                    defaultValue={studioSettings.lora_max ?? 2}
                    onBlur={(e) =>
                      void onSaveStudioSettings({
                        lora_max: Number(e.target.value),
                      })
                    }
                    className="df-input mt-0.5 w-full font-mono text-[10px]"
                  />
                </label>
              </div>
            )}
            {onSaveStudioSettings && studioSettings && (
              <>
                <label className="block">
                  <span className="text-xs text-dfui-muted">
                    Max images per run (config)
                  </span>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    defaultValue={studioSettings.image_number_max ?? imageNumberMax}
                    onBlur={(e) =>
                      void onSaveStudioSettings({
                        image_number_max: Number(e.target.value),
                      })
                    }
                    className="df-input mt-1 w-full px-2.5 py-1.5 font-mono text-xs"
                  />
                </label>
                <label className="flex items-center gap-2 text-[11px] text-dfui-muted">
                  <input
                    type="checkbox"
                    checked={studioSettings.seed_random ?? true}
                    onChange={(e) =>
                      void onSaveStudioSettings({
                        seed_random: e.target.checked,
                      })
                    }
                    className="accent-dfui-accent"
                  />
                  Random seed (web UI default)
                </label>
              </>
            )}
            {onSaveStudioSettings && studioSettings && (
              <div className="space-y-2 rounded-lg border border-dfui-border/40 p-2">
                <p className="text-[10px] font-medium uppercase tracking-wide text-dfui-muted">
                  Paths (saved to config)
                </p>
                <label className="block">
                  <span className="text-[10px] text-dfui-tertiary">Checkpoints</span>
                  <textarea
                    rows={2}
                    defaultValue={studioSettings.path_checkpoints ?? ""}
                    onBlur={(e) =>
                      void onSaveStudioSettings({
                        path_checkpoints: e.target.value,
                      })
                    }
                    className="df-input mt-0.5 w-full font-mono text-[10px]"
                  />
                </label>
                <label className="block">
                  <span className="text-[10px] text-dfui-tertiary">LoRAs</span>
                  <textarea
                    rows={2}
                    defaultValue={studioSettings.path_loras ?? ""}
                    onBlur={(e) =>
                      void onSaveStudioSettings({ path_loras: e.target.value })
                    }
                    className="df-input mt-0.5 w-full font-mono text-[10px]"
                  />
                </label>
              </div>
            )}
            <label className="block">
              <span className="text-xs text-dfui-muted">Seed (−1 = random)</span>
              <input
                type="number"
                value={settings.seed ?? -1}
                onChange={(e) => onChange({ seed: Number(e.target.value) })}
                className="df-input mt-1 w-full px-2.5 py-1.5 font-mono text-xs"
              />
            </label>
            <label className="block">
              <span className="text-xs text-dfui-muted">Negative prompt</span>
              <textarea
                value={settings.negative_prompt ?? ""}
                onChange={(e) => onChange({ negative_prompt: e.target.value })}
                rows={2}
                className="df-input mt-1 w-full px-2.5 py-1.5 text-xs resize-none"
              />
            </label>
            {showEditStrength && (
              <label className="block">
                <span className="text-xs text-dfui-muted">
                  Edit strength — {Math.round((settings.edit_strength ?? 0.98) * 100)}%
                </span>
                <input
                  type="range"
                  min={0.2}
                  max={1}
                  step={0.01}
                  value={settings.edit_strength ?? 0.98}
                  onChange={(e) =>
                    onChange({ edit_strength: Number(e.target.value) })
                  }
                  className="mt-1 w-full accent-dfui-accent"
                />
              </label>
            )}
            {showAdvancedSampling && (
              <>
                {!isCustomPerf && (
                  <p className="rounded-md border border-dfui-border/40 bg-dfui-bg/40 px-2 py-1 text-[10px] leading-snug text-dfui-tertiary">
                    Advanced overrides are active. Changing these values will run with custom sampling.
                  </p>
                )}
                <label className="block">
                  <span className="text-xs text-dfui-muted">
                    Steps — {settings.steps ?? 20}
                  </span>
                  <input
                    type="range"
                    min={4}
                    max={60}
                    value={settings.steps ?? 20}
                    onChange={(e) =>
                      onChange({ performance: CUSTOM_PERF, steps: Number(e.target.value) })
                    }
                    className="mt-1 w-full accent-dfui-accent"
                  />
                </label>
                <label className="block">
                  <span className="text-xs text-dfui-muted">
                    CFG — {settings.cfg_scale ?? 4}
                  </span>
                  <input
                    type="range"
                    min={1}
                    max={12}
                    step={0.1}
                    value={settings.cfg_scale ?? 4}
                    onChange={(e) =>
                      onChange({ performance: CUSTOM_PERF, cfg_scale: Number(e.target.value) })
                    }
                    className="mt-1 w-full accent-dfui-accent"
                  />
                </label>
                <label className="block">
                  <span className="text-xs text-dfui-muted">Sampler</span>
                  <select
                    value={settings.sampler ?? "dpmpp_2m_sde_gpu"}
                    onChange={(e) =>
                      onChange({ performance: CUSTOM_PERF, sampler: e.target.value })
                    }
                    className="df-select mt-1 w-full px-2.5 py-2 text-xs"
                  >
                    {(uiDefaults?.samplers ?? ["dpmpp_2m_sde_gpu"]).map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-xs text-dfui-muted">Scheduler</span>
                  <select
                    value={settings.scheduler ?? "karras"}
                    onChange={(e) =>
                      onChange({ performance: CUSTOM_PERF, scheduler: e.target.value })
                    }
                    className="df-select mt-1 w-full px-2.5 py-2 text-xs"
                  >
                    {(uiDefaults?.schedulers ?? ["karras"]).map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>
                {isQwenModel && (
                  <div className="space-y-2 rounded-lg border border-dfui-border/40 p-2">
                    <p className="text-[10px] font-medium uppercase tracking-wide text-dfui-muted">
                      Qwen Image defaults
                    </p>
                    <label className="block">
                      <span className="text-xs text-dfui-muted">Edit graph</span>
                      <select
                        value={settings.qwen_edit_mode ?? "auto"}
                        onChange={(e) =>
                          onChange({
                            qwen_edit_mode: e.target.value as GenerationSettings["qwen_edit_mode"],
                          })
                        }
                        className="df-select mt-1 w-full px-2.5 py-2 text-xs"
                      >
                        <option value="auto">Auto (Plus when extra references)</option>
                        <option value="single">Single (TextEncodeQwenImageEdit)</option>
                        <option value="plus">Plus (TextEncodeQwenImageEditPlus)</option>
                      </select>
                    </label>
                    <label className="block">
                      <span className="text-xs text-dfui-muted">
                        AuraFlow shift — {settings.qwen_image_shift ?? 3.1}
                      </span>
                      <input
                        type="range"
                        min={1}
                        max={6}
                        step={0.1}
                        value={settings.qwen_image_shift ?? 3.1}
                        onChange={(e) =>
                          onChange({ qwen_image_shift: Number(e.target.value) })
                        }
                        className="mt-1 w-full accent-dfui-accent"
                      />
                    </label>
                    <label className="block">
                      <span className="text-xs text-dfui-muted">
                        Edit scale (MP) — {settings.qwen_scale_megapixels ?? "auto"}
                      </span>
                      <input
                        type="number"
                        min={0}
                        max={4}
                        step={0.05}
                        placeholder="auto (recipe / VRAM)"
                        value={settings.qwen_scale_megapixels ?? ""}
                        onChange={(e) => {
                          const raw = e.target.value.trim();
                          onChange({
                            qwen_scale_megapixels: raw === "" ? undefined : Number(raw),
                          });
                        }}
                        className="df-input mt-1 w-full px-2.5 py-1.5 font-mono text-xs"
                      />
                    </label>
                  </div>
                )}
              </>
            )}
            <label className="block">
              <span className="text-xs text-dfui-muted">ControlNet preset</span>
              <select
                value={settings.cn_selection ?? "None"}
                onChange={(e) => onChange({ cn_selection: e.target.value })}
                className="df-select mt-1 w-full px-2.5 py-2 text-xs"
              >
                <option value="None">None</option>
                {(uiDefaults?.controlnet_presets ?? []).map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
                <option value="Custom...">Custom…</option>
              </select>
            </label>
            {(settings.cn_selection === "Custom..." ||
              settings.input_image) && (
              <label className="block">
                <span className="text-xs text-dfui-muted">Input image path</span>
                <input
                  value={settings.input_image ?? ""}
                  onChange={(e) => onChange({ input_image: e.target.value })}
                  placeholder="D:\path\to\image.png"
                  className="df-input mt-1 w-full px-2.5 py-1.5 font-mono text-[10px]"
                />
              </label>
            )}
            <p className="text-[10px] leading-snug text-dfui-tertiary">
              Model and LoRA tiles use the same cache thumbnails as the Gradio
              web UI (engine/cache/checkpoints and loras). Style cards mirror the
              multiselect list; live step preview uses the same worker as webui.py.
            </p>
            <label className="block">
              <span className="text-xs text-dfui-muted">Subject</span>
              <input
                value={settings.subject ?? ""}
                onChange={(e) => onChange({ subject: e.target.value })}
                className="df-input mt-1 w-full px-2.5 py-1.5 text-xs"
              />
            </label>
            <label className="block">
              <span className="text-xs text-dfui-muted">Lighting</span>
              <input
                value={settings.lighting ?? ""}
                onChange={(e) => onChange({ lighting: e.target.value })}
                className="df-input mt-1 w-full px-2.5 py-1.5 text-xs"
              />
            </label>
            <label className="block">
              <span className="text-xs text-dfui-muted">Camera</span>
              <input
                value={settings.camera ?? ""}
                onChange={(e) => onChange({ camera: e.target.value })}
                className="df-input mt-1 w-full px-2.5 py-1.5 text-xs"
              />
            </label>
          </div>
          </div>
        )}
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

function PathLabel(caption: string): string {
  const bracketEnd = caption.indexOf("] ");
  if (caption.startsWith("[") && bracketEnd > 0) {
    return caption.slice(bracketEnd + 2).trim();
  }
  const parts = caption.split(/[/\\]/);
  return parts[parts.length - 1] ?? caption;
}
