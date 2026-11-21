import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Download,
  ExternalLink,
  KeyRound,
  Layers,
  Search,
  ShieldAlert,
  ShieldCheck,
  X,
  Zap,
} from "lucide-react";
import { relocateDownloadedModel } from "../lib/studioBridge";
import { openExternalUrl } from "../lib/externalLinks";
import {
  type AssetDeviceCompatibility,
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
  setCredential,
  supportedArchitectures,
} from "../lib/discover";

type Props = {
  civitaiApiKey: string;
  kind: DiscoverKind;
  onRefreshInventory: () => void;
  workflow?: { width?: number; height?: number; batch?: number };
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

export function MarketplaceTab({ kind, onRefreshInventory, workflow }: Props) {
  const [query, setQuery] = useState("");
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string>("all");
  const [assets, setAssets] = useState<DiscoverAsset[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [supportedArches, setSupportedArches] = useState<string[]>([]);
  const [compute, setCompute] = useState<ComputeProfileInfo | null>(null);
  const [credentialProvider, setCredentialProvider] = useState<"civitai" | "huggingface">("civitai");
  const [credentialConfigured, setCredentialConfigured] = useState<Record<string, boolean>>({});
  const [queue, setQueue] = useState<DownloadItem[]>([]);
  const [variantSel, setVariantSel] = useState<Record<string, DiscoverAssetFile>>({});
  const [recommendations, setRecommendations] = useState<Record<string, RatedFileVariant | null>>({});
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [showKeyField, setShowKeyField] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [compatibleOnly, setCompatibleOnly] = useState(false);
  const seenInstalled = useRef(new Set<string>());
  const queryRef = useRef("");
  const pageRef = useRef(1);
  const cursorsRef = useRef<Record<string, string>>({});
  const searchReqRef = useRef(0);
  const didMountQueryRef = useRef(false);
  const recommendationWorkflow = useMemo(
    () => ({ width: workflow?.width, height: workflow?.height, batch: workflow?.batch ?? 1 }),
    [workflow?.width, workflow?.height, workflow?.batch],
  );

  useEffect(() => setRecommendations({}), [recommendationWorkflow]);

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
      .then((res) => setCredentialConfigured(Object.fromEntries(Object.entries(res.status ?? {}).map(([id, value]) => [id, Boolean(value?.configured)]))))
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
            void Promise.allSettled(newlyInstalled.map((i) =>
              relocateDownloadedModel({
                path: i.final_path,
                category: i.category,
                filename: i.filename,
              })
            )).then(() => onRefreshInventory());
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

  const runSearch = useCallback(async (append = false, explicitQuery?: string) => {
    const reqId = ++searchReqRef.current;
    const activeQuery = (explicitQuery ?? queryRef.current).trim();
    setSearching(true);
    setError(null);
    if (!append) {
      setAssets([]);
      cursorsRef.current = {};
    }
    const page = append ? pageRef.current + 1 : 1;
    try {
      const res = await discoverySearch({
        query: activeQuery,
        kind,
        limit: 24,
        page,
        provider_ids: selectedProvider === "all" ? undefined : [selectedProvider],
        provider_cursors: append ? cursorsRef.current : undefined,
      });
      if (reqId !== searchReqRef.current) return;
      if (res.compute_profile) {
        setCompute(res.compute_profile);
      }
      setAssets((current) => {
        if (!append) return res.assets;
        const merged = new Map(current.map((asset) => [asset.id, asset]));
        res.assets.forEach((asset) => merged.set(asset.id, asset));
        return [...merged.values()];
      });
      pageRef.current = page;
      cursorsRef.current = Object.fromEntries(
        res.providers.filter((entry) => entry.next_cursor).map((entry) => [entry.provider, entry.next_cursor]),
      );
      setHasMore(res.providers.some((entry) => Boolean(entry.next_cursor) || entry.assets.length >= 24));
      if (res.provider_errors > 0 && res.provider_ok === 0) {
        const details = res.providers
          .filter((entry) => !entry.ok && entry.error)
          .map((entry) => `${entry.provider}: ${entry.error}`);
        setError(
          details.length > 0
            ? details.join(" · ")
            : "No search provider responded. Check your connection or API key.",
        );
      }
    } catch (e) {
      if (reqId !== searchReqRef.current) return;
      setError(String(e));
      if (!append) setAssets([]);
    } finally {
      if (reqId === searchReqRef.current) setSearching(false);
    }
  }, [kind, selectedProvider]);

  useEffect(() => {
    void runSearch(false);
  }, [runSearch]);

  // Live debounced search as user types so marketplace filters reliably without requiring Enter.
  useEffect(() => {
    if (!didMountQueryRef.current) {
      didMountQueryRef.current = true;
      return;
    }
    const timer = window.setTimeout(() => {
      void runSearch(false, query);
    }, 320);
    return () => window.clearTimeout(timer);
  }, [query, runSearch]);

  useEffect(() => {
    if (!assets.length) return;
    let cancelled = false;
    // Only invoke per-asset recommendation RPC when inline compatibility wasn't already supplied by search.
    const missingCompat = assets.filter(
      (asset) => !asset.compatibility && !(asset.id in recommendations),
    );
    missingCompat.forEach((asset) => {
      void recommendFileVariants(asset, compute?.vram_profile ?? "auto", recommendationWorkflow)
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
  }, [assets, compute?.vram_profile, recommendations, recommendationWorkflow]);

  const selectedFile = useCallback(
    (asset: DiscoverAsset) => {
      const version = activeVersion(asset);
      if (!version) return undefined;
      const manual = variantSel[asset.id];
      if (manual) return manual;
      const inlineIdx = asset.compatibility?.recommended_file_index;
      if (inlineIdx != null && version.files[inlineIdx]) {
        return version.files[inlineIdx];
      }
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
      const res = await setCredential(credentialProvider, apiKeyInput.trim());
      setCredentialConfigured((current) => ({ ...current, [credentialProvider]: Boolean(res.status?.[credentialProvider]?.configured) }));
      setShowKeyField(false);
      setApiKeyInput("");
      void runSearch(false, queryRef.current);
    } catch (e) {
      setSettingsError(String(e));
    }
  };

  const queueByAsset = useMemo(() => {
    const map: Record<string, DownloadItem> = {};
    queue.forEach((item) => {
      const key = [item.provider, item.provider_asset_id, item.provider_version_id, item.filename].join(":");
      if (!map[key] || ACTIVE_STATES.has(item.state)) map[key] = item;
    });
    return map;
  }, [queue]);

  const activeQueue = useMemo(
    () => queue.filter((i) => i.state !== "cancelled"),
    [queue],
  );

  const downloadButtonState = (asset: DiscoverAsset) => {
    if (asset.is_local) return "installed";
    const version = activeVersion(asset);
    const file = selectedFile(asset);
    const key = [asset.provenance.provider, asset.provenance.provider_asset_id, asset.provenance.provider_version_id || version?.provider_version_id || "", file?.filename || ""].join(":");
    const item = queueByAsset[key];
    if (item?.state === "installed") return "installed";
    if (item && ACTIVE_STATES.has(item.state)) return "downloading";
    return "download";
  };

  const archUnsupported = (asset: DiscoverAsset) =>
    Boolean(
      asset.compatibility?.status === "unsupported_arch" ||
        (asset.architecture && supportedArches.length > 0 && !supportedArches.includes(asset.architecture)),
    );

  const effectiveCompatibility = (asset: DiscoverAsset): AssetDeviceCompatibility | null => {
    if (asset.compatibility) {
      const base = asset.compatibility;
      const manual = variantSel[asset.id];
      const version = activeVersion(asset);
      if (
        manual &&
        version &&
        base.status !== "unsupported_arch" &&
        base.status !== "cpu_only"
      ) {
        const idx = version.files.findIndex((f) => f.filename === manual.filename);
        const estFromList = idx >= 0 ? base.file_estimates_mb?.[idx] : undefined;
        const estMb =
          estFromList && estFromList > 0
            ? estFromList
            : manual.size_bytes > 0
              ? Math.round((manual.size_bytes * 1.25) / (1024 * 1024))
              : base.estimated_mb;
        if (estMb > 0 && base.usable_vram_mb > 0) {
          const variantTag = manual.variant ? ` (${formatVariant(manual.variant)})` : "";
          const estText = `~${(estMb / 1024).toFixed(1)} GB`;
          if (estMb <= base.usable_vram_mb) {
            return {
              ...base,
              status: "compatible",
              label: "Compatible",
              estimated_mb: estMb,
              recommended_variant: manual.variant || base.recommended_variant,
              reason: `Selected variant fits ${base.device_name} · ${estText}${variantTag}.`,
              fits: true,
            };
          }
          if (estMb <= base.tight_vram_mb) {
            return {
              ...base,
              status: "tight",
              label: "Tight fit",
              estimated_mb: estMb,
              recommended_variant: manual.variant || base.recommended_variant,
              reason: `Selected variant is a tight fit on ${base.device_name} · ${estText}${variantTag} (memory offload recommended).`,
              fits: true,
            };
          }
          return {
            ...base,
            status: "too_large",
            label: "Exceeds VRAM",
            estimated_mb: estMb,
            recommended_variant: manual.variant || base.recommended_variant,
            reason: `Selected variant needs ${estText}${variantTag}, exceeding ${base.device_name}.`,
            fits: false,
          };
        }
      }
      return base;
    }
    const rec = recommendations[asset.id];
    if (!rec) return null;
    const status =
      archUnsupported(asset)
        ? "unsupported_arch"
        : rec.fits === true
          ? "compatible"
          : rec.fits === false
            ? "too_large"
            : "unknown";
    return {
      status,
      label:
        status === "compatible"
          ? "Compatible"
          : status === "too_large"
            ? "Exceeds VRAM"
            : status === "unsupported_arch"
              ? "Unsupported arch"
              : "Check VRAM",
      reason:
        status === "compatible"
          ? `Fits your device (~${(rec.estimated_mb / 1024).toFixed(1)} GB).`
          : status === "too_large"
            ? `Estimated ~${(rec.estimated_mb / 1024).toFixed(1)} GB exceeds your VRAM.`
            : "Compatibility could not be verified automatically.",
      estimated_mb: rec.estimated_mb,
      usable_vram_mb: compute?.vram_mb ?? 0,
      tight_vram_mb: compute?.vram_mb ?? 0,
      device_name: compute?.device_name ?? "Your device",
      device_vram_gb: compute?.vram_gb ?? 0,
      backend: compute?.backend ?? "cpu",
      recommended_variant: rec.variant,
      recommended_file_index: rec.index,
      recommended: rec,
      compatible_files_count: rec.fits ? 1 : 0,
      fits: rec.fits === true,
    };
  };

  const displayedAssets = useMemo(() => {
    if (!compatibleOnly) return assets;
    return assets.filter((asset) => {
      const compat = asset.compatibility;
      if (compat) return compat.status === "compatible" || compat.status === "tight";
      const rec = recommendations[asset.id];
      return rec?.fits === true;
    });
  }, [assets, compatibleOnly, recommendations]);

  const deviceSummary = useMemo(() => {
    if (!compute) return null;
    const backendLabel = compute.backend ? compute.backend.toUpperCase() : "CPU";
    const memText =
      compute.vram_gb > 0
        ? compute.backend === "mps"
          ? `${compute.vram_gb.toFixed(0)} GB Unified`
          : `${compute.vram_gb.toFixed(0)} GB VRAM`
        : "CPU mode";
    return `${compute.device_name} · ${memText} (${backendLabel})`;
  }, [compute]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="space-y-2">
        <div className="flex gap-2">
          <div className="relative min-w-0 flex-1">
            <input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                queryRef.current = e.target.value;
                setHasMore(false);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") void runSearch(false, query);
                if (e.key === "Escape" && query) {
                  e.preventDefault();
                  setQuery("");
                  queryRef.current = "";
                  void runSearch(false, "");
                }
              }}
              placeholder={`Search ${prettyKind(kind)} (e.g. minimax h3, krea2, flux, sdxl)…`}
              className="df-input w-full py-1.5 pl-2.5 pr-7 text-xs"
            />
            {query && (
              <button
                type="button"
                aria-label="Clear search"
                title="Clear search"
                onClick={() => {
                  setQuery("");
                  queryRef.current = "";
                  void runSearch(false, "");
                }}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-dfui-muted hover:text-dfui-fg"
              >
                <X size={12} />
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={() => void runSearch(false, query)}
            disabled={searching}
            className="df-button-primary inline-flex items-center justify-center rounded-md px-3 py-1.5 text-xs disabled:opacity-50"
            title="Search"
          >
            <Search size={14} />
          </button>
        </div>
        {deviceSummary && (
          <div className="flex items-center justify-between gap-2 rounded-md border border-dfui-border/50 bg-dfui-bg/35 px-2 py-1">
            <span className="inline-flex min-w-0 items-center gap-1.5 truncate font-mono text-[9px] text-dfui-secondary" title={`Device compatibility evaluated for ${deviceSummary}`}>
              <Cpu size={11} className="shrink-0 text-dfui-accent" />
              <span className="truncate">{deviceSummary}</span>
            </span>
            <button
              type="button"
              aria-pressed={compatibleOnly}
              onClick={() => setCompatibleOnly((v) => !v)}
              className={`shrink-0 rounded-full border px-2 py-0.5 text-[9px] font-medium transition ${
                compatibleOnly
                  ? "border-emerald-400/50 bg-emerald-500/20 text-emerald-200"
                  : "border-dfui-border/60 text-dfui-muted hover:text-dfui-fg"
              }`}
              title="Show only models that fit your device"
            >
              {compatibleOnly ? "Compatible only ✓" : "Compatible only"}
            </button>
          </div>
        )}
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
            <select value={credentialProvider} onChange={(e) => setCredentialProvider(e.target.value as "civitai" | "huggingface")} className="df-input px-1 py-0.5 text-[9px]" aria-label="Credential provider">
              <option value="civitai">Civitai</option>
              <option value="huggingface">Hugging Face</option>
            </select>
            <p className="min-w-0 flex-1 text-[10px] text-dfui-tertiary">
              {credentialConfigured[credentialProvider]
                ? `Using saved ${credentialProvider === "civitai" ? "Civitai" : "Hugging Face"} token`
                : `Add a ${credentialProvider === "civitai" ? "Civitai API key" : "Hugging Face token"} for gated downloads.`}
            </p>
            <button
              type="button"
              onClick={() => setShowKeyField(true)}
              className="shrink-0 rounded border border-dfui-border/60 px-1.5 py-0.5 text-[9px] text-dfui-secondary transition hover:text-dfui-fg"
            >
              {credentialConfigured[credentialProvider] ? "Update" : "Add key"}
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
                placeholder={credentialProvider === "civitai" ? "Civitai API key" : "Hugging Face token"}
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
          {displayedAssets.map((asset) => {
            const version = activeVersion(asset);
            if (!version) return null;
            const image = version.thumbnail_url || asset.versions[0]?.thumbnail_url;
            const compat = effectiveCompatibility(asset);
            const file = selectedFile(asset);
            const queueKey = [asset.provenance.provider, asset.provenance.provider_asset_id, asset.provenance.provider_version_id || version.provider_version_id || "", file?.filename || ""].join(":");
            const queueItem = queueByAsset[queueKey];
            const buttonState = downloadButtonState(asset);
            const unsupported = archUnsupported(asset);
            const multiFile = version.files.length > 1;

            const compatBadgeStyle =
              compat?.status === "compatible"
                ? "border-emerald-400/40 bg-emerald-950/80 text-emerald-200"
                : compat?.status === "tight"
                  ? "border-amber-400/45 bg-amber-950/80 text-amber-200"
                  : compat?.status === "too_large" || compat?.status === "unsupported_arch"
                    ? "border-red-400/45 bg-red-950/80 text-red-200"
                    : compat?.status === "cpu_only"
                      ? "border-orange-400/40 bg-orange-950/80 text-orange-200"
                      : "border-white/15 bg-black/65 text-gray-300";

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
                    decoding="async"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <div className="absolute inset-0 bg-dfui-panel" />
                )}
                <div className="absolute inset-x-0 top-0 flex items-start justify-between gap-1.5 p-1.5">
                  <div className="flex min-w-0 flex-wrap items-center gap-1">
                    <span className="rounded bg-black/60 px-1.5 py-0.5 font-mono text-[8px] text-white backdrop-blur">
                      {asset.architecture || version.base_model || kind}
                    </span>
                    {compat && (
                      <span
                        title={compat.reason}
                        className={`inline-flex items-center gap-0.5 rounded border px-1.5 py-0.5 font-mono text-[8px] font-medium backdrop-blur ${compatBadgeStyle}`}
                      >
                        {compat.status === "compatible" ? (
                          <ShieldCheck size={9} />
                        ) : compat.status === "tight" ? (
                          <Zap size={9} />
                        ) : compat.status === "too_large" || compat.status === "unsupported_arch" ? (
                          <ShieldAlert size={9} />
                        ) : (
                          <AlertTriangle size={9} />
                        )}
                        {compat.label}
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => void openExternalUrl(asset.provenance.source_url)}
                    className="shrink-0 rounded bg-black/45 p-1 text-white backdrop-blur transition hover:bg-black/70"
                    title="Open in source"
                    aria-label={`Open ${asset.name} in source`}
                  >
                    <ExternalLink size={12} />
                  </button>
                </div>
                {unsupported && (
                  <div className="absolute inset-x-1 top-7 rounded border border-amber-500/40 bg-amber-950/75 px-1.5 py-0.5 text-[8px] leading-tight text-amber-200 backdrop-blur">
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
                    {compat && (
                      <span
                        title={compat.reason}
                        className={`truncate font-mono text-[8px] ${
                          compat.status === "compatible"
                            ? "text-emerald-300"
                            : compat.status === "tight"
                              ? "text-amber-300"
                              : compat.status === "too_large" || compat.status === "unsupported_arch"
                                ? "text-red-300"
                                : "text-gray-300"
                        }`}
                      >
                        {compat.estimated_mb > 0
                          ? `~${(compat.estimated_mb / 1024).toFixed(1)} GB`
                          : compat.label}
                        {compat.recommended_variant
                          ? ` · ${formatVariant(compat.recommended_variant)}`
                          : ""}
                        {compat.device_vram_gb > 0
                          ? ` · ${compat.device_name}`
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
          {!searching && displayedAssets.length === 0 && (
            <div className="col-span-2 py-10 text-center text-xs text-dfui-muted">
              {compatibleOnly && assets.length > 0
                ? `None of the ${assets.length} result(s) fit your current device. Turn off "Compatible only" to view all.`
                : `No ${prettyKind(kind)} found. Try a different search.`}
            </div>
          )}
          {searching && (
            <div className="col-span-2 py-10 text-center font-mono text-xs text-dfui-muted">
              Searching...
            </div>
          )}
        </div>
        {assets.length > 0 && hasMore && (
          <button
            type="button"
            onClick={() => void runSearch(true)}
            disabled={searching}
            className="mx-auto mt-3 block rounded-md border border-dfui-border/60 px-4 py-1.5 text-[10px] text-dfui-secondary transition hover:text-dfui-fg disabled:opacity-50"
          >
            {searching ? "Loading…" : "Load more results"}
          </button>
        )}
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
