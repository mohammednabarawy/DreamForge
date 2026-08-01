import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2,
  Download,
  ExternalLink,
  KeyRound,
  Layers,
  Search,
  X,
} from "lucide-react";
import { relocateDownloadedModel } from "../lib/studioBridge";
import {
  type ComputeProfileInfo,
  type DiscoverAsset,
  type DiscoverAssetFile,
  type DownloadItem,
  type ProviderInfo,
  type RatedFileVariant,
  cancelDownload,
  clearCompletedDownloads,
  computeProfile,
  credentialStatus,
  discoverySearch,
  downloadQueueStatus,
  enqueueDownload,
  listProviders,
  pauseDownload,
  recommendFileVariants,
  resumeDownload,
  loadDiscoverKind,
  saveDiscoverKind,
  setCredential,
  supportedArchitectures,
} from "../lib/discover";

type Props = {
  civitaiApiKey: string;
  onRefreshInventory: () => void;
};

type DiscoverKind = "checkpoint" | "lora";

const ACTIVE_STATES = new Set([
  "queued",
  "resolving",
  "checking_disk",
  "downloading",
  "verifying",
  "registering",
]);

function formatBytes(bytes?: number) {
  if (!bytes) return "";
  if (bytes > 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`;
  if (bytes > 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(0)} MB`;
  return `${(bytes / 1024).toFixed(0)} KB`;
}

function categoryForKind(kind: DiscoverKind) {
  return kind === "lora" ? "loras" : "checkpoints";
}

function prettyKind(kind: DiscoverKind) {
  return kind === "lora" ? "LoRAs" : "Checkpoints";
}

function activeVersion(asset: DiscoverAsset) {
  if (!asset.versions.length) return undefined;
  const found = asset.versions.find((v) => v.id === asset.version_id);
  return found ?? asset.versions[0];
}

function formatVariant(variant: string) {
  if (!variant) return "Base";
  return variant
    .split("_")
    .map((s) => s.toUpperCase())
    .join(" ");
}

export function MarketplaceTab({ onRefreshInventory }: Props) {
  const [query, setQuery] = useState("");
  const [kind, setKindState] = useState<DiscoverKind>(() => loadDiscoverKind());
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string>("all");
  const [assets, setAssets] = useState<DiscoverAsset[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [supportedArches, setSupportedArches] = useState<string[]>([]);
  const [compute, setCompute] = useState<ComputeProfileInfo | null>(null);
  const [credentialConfigured, setCredentialConfigured] = useState(false);
  const [queue, setQueue] = useState<DownloadItem[]>([]);
  const [variantSel, setVariantSel] = useState<Record<string, DiscoverAssetFile>>({});
  const [recommendations, setRecommendations] = useState<Record<string, RatedFileVariant | null>>({});
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [showKeyField, setShowKeyField] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const seenInstalled = useRef(new Set<string>());

  const setKind = useCallback((next: DiscoverKind) => {
    setKindState(next);
    saveDiscoverKind(next);
  }, []);

  useEffect(() => {
    void listProviders()
      .then(setProviders)
      .catch((e) => setError(String(e)));
    void supportedArchitectures()
      .then(setSupportedArches)
      .catch(() => undefined);
    void computeProfile("auto")
      .then(setCompute)
      .catch(() => undefined);
    void credentialStatus()
      .then((res) => setCredentialConfigured(Boolean(res.status?.civitai?.configured)))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    let alive = true;
    const tick = () => {
      void downloadQueueStatus()
        .then((items) => {
          if (!alive) return;
          setQueue(items);
          const newlyInstalled = items.filter(
            (i) => i.state === "installed" && !seenInstalled.current.has(i.id),
          );
          if (newlyInstalled.length) {
            newlyInstalled.forEach((i) => seenInstalled.current.add(i.id));
            newlyInstalled.forEach((i) => {
              void relocateDownloadedModel({
                path: i.final_path,
                category: i.category,
                filename: i.filename,
              }).catch(() => undefined);
            });
            void onRefreshInventory();
          }
        })
        .catch(() => undefined);
    };
    tick();
    const timer = setInterval(tick, 2000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [onRefreshInventory]);

  const runSearch = useCallback(async () => {
    setSearching(true);
    setError(null);
    try {
      const res = await discoverySearch({
        query: query.trim(),
        kind,
        limit: 24,
        page: 1,
        provider_ids: selectedProvider === "all" ? undefined : [selectedProvider],
      });
      setAssets(res.assets);
      if (res.provider_errors > 0 && res.provider_ok === 0) {
        setError("No search provider responded. Check your connection or API key.");
      }
    } catch (e) {
      setError(String(e));
      setAssets([]);
    } finally {
      setSearching(false);
    }
  }, [query, kind, selectedProvider]);

  useEffect(() => {
    void runSearch();
  }, [runSearch]);

  useEffect(() => {
    if (!assets.length) return;
    let cancelled = false;
    assets.forEach((asset) => {
      if (cancelled || asset.id in recommendations) return;
      void recommendFileVariants(asset, compute?.vram_profile ?? "auto")
        .then((res) => {
          if (cancelled || !res.ok) return;
          setRecommendations((prev) => ({
            ...prev,
            [asset.id]: res.recommended,
          }));
        })
        .catch(() => undefined);
    });
    return () => {
      cancelled = true;
    };
  }, [assets, compute?.vram_profile, recommendations]);

  const selectedFile = useCallback(
    (asset: DiscoverAsset) => {
      const version = activeVersion(asset);
      if (!version) return undefined;
      const manual = variantSel[asset.id];
      if (manual) return manual;
      const recommended = recommendations[asset.id];
      if (recommended) {
        const rec = version.files[recommended.index];
        if (rec) return rec;
      }
      return version.files.find((f) => f.sha256) ?? version.files[0];
    },
    [recommendations, variantSel],
  );

  const handleDownload = async (asset: DiscoverAsset) => {
    const version = activeVersion(asset);
    if (!version) return;
    const file = selectedFile(asset);
    if (!file) return;
    try {
      const res = await enqueueDownload({
        url: file.download_url || "",
        category: categoryForKind(kind),
        filename: file.filename,
        expected_sha256: file.sha256,
        provider: asset.provenance.provider,
        provider_asset_id: asset.provenance.provider_asset_id,
        provider_version_id: asset.provenance.provider_version_id || version.provider_version_id,
      });
      if (!res.ok) {
        setError(res.error ?? "Failed to queue download.");
        return;
      }
      void downloadQueueStatus().then(setQueue).catch(() => undefined);
    } catch (e) {
      setError(`Download failed: ${String(e)}`);
    }
  };

  const handleSaveApiKey = async () => {
    setSettingsError(null);
    try {
      const res = await setCredential("civitai", apiKeyInput.trim());
      setCredentialConfigured(Boolean(res.status?.civitai?.configured));
      setShowKeyField(false);
      setApiKeyInput("");
    } catch (e) {
      setSettingsError(String(e));
    }
  };

  const queueByAsset = useMemo(() => {
    const map: Record<string, DownloadItem> = {};
    queue.forEach((item) => {
      if (!map[item.provider_asset_id]) map[item.provider_asset_id] = item;
    });
    return map;
  }, [queue]);

  const activeQueue = useMemo(
    () => queue.filter((i) => i.state !== "cancelled"),
    [queue],
  );

  const downloadButtonState = (asset: DiscoverAsset) => {
    if (asset.is_local) return "installed";
    const item = queueByAsset[asset.provenance.provider_asset_id];
    if (item && ACTIVE_STATES.has(item.state)) return "downloading";
    return "download";
  };

  const archUnsupported = (asset: DiscoverAsset) =>
    Boolean(asset.architecture && !supportedArches.includes(asset.architecture));

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="space-y-2">
        <div className="flex gap-1.5">
          {(["checkpoint", "lora"] as DiscoverKind[]).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setKind(mode)}
              className={`flex-1 rounded-md border px-2 py-1.5 text-[10px] font-semibold transition ${
                kind === mode
                  ? "border-dfui-accent bg-dfui-accent/15 text-dfui-fg"
                  : "border-dfui-border/60 text-dfui-muted hover:text-dfui-fg"
              }`}
            >
              {prettyKind(mode)}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void runSearch();
            }}
            placeholder={`Search ${prettyKind(kind)}...`}
            className="df-input min-w-0 flex-1 px-2.5 py-1.5 text-xs"
          />
          <button
            type="button"
            onClick={() => void runSearch()}
            disabled={searching}
            className="df-button-primary inline-flex items-center justify-center rounded-md px-3 py-1.5 text-xs disabled:opacity-50"
            title="Search"
          >
            <Search size={14} />
          </button>
        </div>
        {providers.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <select
              value={selectedProvider}
              onChange={(e) => setSelectedProvider(e.target.value)}
              className="df-input flex-1 px-2 py-1 text-[10px]"
              title="Search provider"
            >
              <option value="all">All providers</option>
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.display_name}
                </option>
              ))}
            </select>
            {providers.map((p) => (
              <span
                key={p.id}
                className={`rounded-full px-2 py-0.5 text-[9px] ${
                  p.credential_configured
                    ? "bg-emerald-500/15 text-emerald-300"
                    : "bg-dfui-border/30 text-dfui-muted"
                }`}
                title={
                  p.credential_configured
                    ? `${p.display_name} API key configured`
                    : `${p.display_name} no API key`
                }
              >
                {p.display_name}
                {p.credential_configured ? " ✓" : ""}
              </span>
            ))}
          </div>
        )}
        {!showKeyField ? (
          <div className="flex items-center gap-2 rounded-md border border-dfui-border/50 bg-dfui-bg/30 px-2 py-1.5">
            <KeyRound size={12} className="text-dfui-muted" />
            <p className="min-w-0 flex-1 text-[10px] text-dfui-tertiary">
              {credentialConfigured
                ? "Using saved Civitai API key from App settings"
                : "No Civitai API key set. Add one for gated downloads."}
            </p>
            <button
              type="button"
              onClick={() => setShowKeyField(true)}
              className="shrink-0 rounded border border-dfui-border/60 px-1.5 py-0.5 text-[9px] text-dfui-secondary transition hover:text-dfui-fg"
            >
              {credentialConfigured ? "Update" : "Add key"}
            </button>
          </div>
        ) : (
          <div className="space-y-1.5 rounded-md border border-dfui-border/50 bg-dfui-bg/30 px-2 py-1.5">
            <div className="flex gap-1.5">
              <input
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void handleSaveApiKey();
                }}
                type="password"
                placeholder="Civitai API key"
                className="df-input min-w-0 flex-1 px-2 py-1 text-[10px]"
              />
              <button
                type="button"
                onClick={() => void handleSaveApiKey()}
                className="shrink-0 rounded border border-dfui-accent/60 bg-dfui-accent/15 px-2 py-1 text-[9px] text-dfui-fg transition hover:bg-dfui-accent/25"
              >
                Save
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowKeyField(false);
                  setApiKeyInput("");
                }}
                className="shrink-0 rounded border border-dfui-border/60 px-1.5 py-1 text-[9px] text-dfui-muted transition hover:text-dfui-fg"
                title="Cancel"
              >
                <X size={10} />
              </button>
            </div>
            {settingsError && (
              <p className="text-[9px] text-red-300">{settingsError}</p>
            )}
          </div>
        )}
        {error && (
          <p className="rounded-md border border-red-500/30 bg-red-500/10 px-2 py-1.5 text-[10px] text-red-200">
            {error}
          </p>
        )}
      </div>

      <div className="df-gallery-pane">
        <div className="df-gallery-grid">
          {assets.map((asset) => {
            const version = activeVersion(asset);
            if (!version) return null;
            const image = version.thumbnail_url || asset.versions[0]?.thumbnail_url;
            const queueItem = queueByAsset[asset.provenance.provider_asset_id];
            const buttonState = downloadButtonState(asset);
            const recommended = recommendations[asset.id] ?? null;
            const file = selectedFile(asset);
            const unsupported = archUnsupported(asset);
            const multiFile = version.files.length > 1;

            return (
              <article
                key={asset.id}
                className="group df-gallery-tile df-gallery-tile-idle"
              >
                {image ? (
                  <img
                    src={image}
                    className="absolute inset-0 h-full w-full object-cover opacity-70 transition-opacity group-hover:opacity-45"
                    alt=""
                    loading="lazy"
                  />
                ) : (
                  <div className="absolute inset-0 bg-dfui-panel" />
                )}
                <div className="absolute inset-x-0 top-0 flex justify-between gap-2 p-1.5">
                  <span className="rounded bg-black/55 px-1.5 py-0.5 font-mono text-[8px] text-white backdrop-blur">
                    {asset.architecture || version.base_model || kind}
                  </span>
                  <a
                    href={asset.provenance.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded bg-black/45 p-1 text-white backdrop-blur transition hover:bg-black/70"
                    title="Open in source"
                  >
                    <ExternalLink size={12} />
                  </a>
                </div>
                {unsupported && (
                  <div className="absolute inset-x-1 top-6 rounded border border-amber-500/40 bg-amber-950/70 px-1.5 py-0.5 text-[8px] leading-tight text-amber-200 backdrop-blur">
                    Architecture "{asset.architecture}" is not supported by this
                    engine — it may not run after download.
                  </div>
                )}
                <div className="df-gallery-tile-caption">
                  <p className="line-clamp-2 text-[11px] font-semibold leading-tight text-white">
                    {asset.name}
                  </p>
                  <p className="mt-0.5 truncate text-[9px] text-gray-300">
                    {asset.provenance.author || asset.provenance.provider}
                    {asset.deduplicated_from
                      ? ` · also on ${asset.deduplicated_from}`
                      : ""}
                  </p>
                  <div className="mb-1 flex flex-col gap-0.5">
                    {asset.versions.length > 1 && (
                      <span className="inline-flex items-center gap-1 font-mono text-[8px] text-gray-400">
                        <Layers size={9} />
                        {asset.versions.length} versions
                      </span>
                    )}
                    {recommended && (
                      <span
                        className={`truncate font-mono text-[8px] ${
                          recommended.fits === false
                            ? "text-amber-300"
                            : recommended.fits === null
                              ? "text-gray-400"
                              : "text-emerald-300"
                        }`}
                      >
                        {recommended.fits === false
                          ? "May exceed your VRAM · "
                          : recommended.fits === null
                            ? "Unverified fit · "
                            : "Recommended fit · "}
                        {formatVariant(recommended.variant)}
                        {recommended.estimated_mb > 0
                          ? ` · ~${(recommended.estimated_mb / 1024).toFixed(1)} GB`
                          : ""}
                      </span>
                    )}
                  </div>
                  {multiFile && (
                    <select
                      value={file?.filename ?? version.files[0].filename}
                      onChange={(e) => {
                        const next =
                          version.files.find((f) => f.filename === e.target.value) ??
                          version.files[0];
                        setVariantSel((prev) => ({
                          ...prev,
                          [asset.id]: next,
                        }));
                      }}
                      className="df-input mb-1 w-full px-1.5 py-0.5 text-[9px]"
                      title="File variant"
                    >
                      {version.files.map((f) => (
                        <option key={f.filename} value={f.filename}>
                          {formatVariant(f.variant) || "Base"} · {formatBytes(f.size_bytes)}
                          {f.sha256 ? "" : " · no hash"}
                        </option>
                      ))}
                    </select>
                  )}
                  <button
                    type="button"
                    onClick={() => void handleDownload(asset)}
                    disabled={buttonState !== "download"}
                    className="flex h-7 w-full items-center justify-center gap-1 rounded bg-white/18 px-2 text-[10px] text-white backdrop-blur-sm transition hover:bg-white/28 disabled:opacity-100"
                  >
                    {buttonState === "downloading" ? (
                      <span className="relative h-1.5 w-full overflow-hidden rounded-full bg-white/15">
                        <span
                          className="absolute inset-y-0 left-0 rounded-full bg-dfui-accent transition-all duration-300"
                          style={{
                            width: `${Math.max(0, Math.min(100, queueItem?.progress_pct ?? 0))}%`,
                          }}
                        />
                      </span>
                    ) : buttonState === "installed" ? (
                      <>
                        <CheckCircle2 size={12} />
                        Installed
                      </>
                    ) : (
                      <>
                        <Download size={12} />
                        Download
                      </>
                    )}
                  </button>
                </div>
              </article>
            );
          })}
          {!searching && assets.length === 0 && (
            <div className="col-span-2 py-10 text-center text-xs text-dfui-muted">
              No {prettyKind(kind)} found. Try a different search.
            </div>
          )}
          {searching && (
            <div className="col-span-2 py-10 text-center font-mono text-xs text-dfui-muted">
              Searching...
            </div>
          )}
        </div>
      </div>

      {activeQueue.length > 0 && (
        <div className="shrink-0 rounded-md border border-dfui-border/60 bg-dfui-bg/30 p-2">
          <div className="mb-1.5 flex items-center justify-between">
            <p className="text-[10px] font-semibold text-dfui-fg">
              Downloads ({activeQueue.length})
            </p>
            <button
              type="button"
              onClick={() => {
                void clearCompletedDownloads()
                  .then(() => downloadQueueStatus())
                  .then(setQueue)
                  .catch(() => undefined);
              }}
              className="rounded border border-dfui-border/50 px-1.5 py-0.5 text-[9px] text-dfui-muted transition hover:text-dfui-fg"
              title="Clear finished downloads"
            >
              Clear finished
            </button>
          </div>
          <div className="max-h-36 space-y-1 overflow-y-auto">
            {activeQueue.map((item) => (
              <div
                key={item.id}
                className="flex items-center gap-2 rounded border border-dfui-border/40 bg-dfui-panel/60 px-1.5 py-1"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[9px] text-dfui-fg">{item.filename}</p>
                  <div className="mt-0.5 flex items-center gap-1.5">
                    <div className="relative h-1 flex-1 overflow-hidden rounded-full bg-dfui-border/40">
                      <div
                        className="absolute inset-y-0 left-0 rounded-full bg-dfui-accent transition-all duration-300"
                        style={{
                          width: `${Math.max(0, Math.min(100, item.progress_pct))}%`,
                        }}
                      />
                    </div>
                    <span className="w-12 shrink-0 text-right font-mono text-[8px] text-dfui-muted">
                      {item.state === "installed"
                        ? "100%"
                        : item.state === "failed_auth"
                          ? "AUTH"
                          : item.state.startsWith("failed")
                            ? "ERR"
                            : `${item.progress_pct.toFixed(0)}%`}
                    </span>
                  </div>
                  {item.state === "failed_auth" && (
                    <p className="mt-0.5 truncate text-[8px] text-red-300">
                      Auth required — add the provider API key to retry.
                    </p>
                  )}
                  {item.state.startsWith("failed") && item.error && (
                    <p className="mt-0.5 truncate text-[8px] text-red-300">{item.error}</p>
                  )}
                </div>
                <div className="flex shrink-0 gap-1">
                  {item.state === "downloading" && (
                    <button
                      type="button"
                      onClick={() =>
                        void pauseDownload(item.id)
                          .then(() => downloadQueueStatus())
                          .then(setQueue)
                          .catch(() => undefined)
                      }
                      className="rounded border border-dfui-border/50 px-1.5 py-0.5 text-[9px] text-dfui-secondary transition hover:text-dfui-fg"
                      title="Pause"
                    >
                      Pause
                    </button>
                  )}
                  {(item.state === "paused" || item.state === "failed_network") && (
                    <button
                      type="button"
                      onClick={() =>
                        void resumeDownload(item.id)
                          .then(() => downloadQueueStatus())
                          .then(setQueue)
                          .catch(() => undefined)
                      }
                      className="rounded border border-dfui-accent/60 bg-dfui-accent/15 px-1.5 py-0.5 text-[9px] text-dfui-fg transition hover:bg-dfui-accent/25"
                      title="Resume"
                    >
                      Resume
                    </button>
                  )}
                  {!["installed", "cancelled"].includes(item.state) && (
                    <button
                      type="button"
                      onClick={() =>
                        void cancelDownload(item.id)
                          .then(() => downloadQueueStatus())
                          .then(setQueue)
                          .catch(() => undefined)
                      }
                      className="rounded border border-dfui-border/50 px-1.5 py-0.5 text-[9px] text-dfui-muted transition hover:text-red-300"
                      title="Cancel"
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
