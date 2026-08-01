import { bridgeInvoke } from "./studioBridge";

const SURFACE_KEY = "dreamforge.discoverLibrary.surface.v1";
const LIBRARY_TAB_KEY = "dreamforge.discoverLibrary.libraryTab.v1";
const DISCOVER_KIND_KEY = "dreamforge.discoverLibrary.discoverKind.v1";

export type DiscoverLibrarySurface = "discover" | "library";
export type DiscoverLibraryTab = "models" | "loras" | "styles" | "settings" | "automation";
export type DiscoverTab = "discover" | "discover_workflows";
const DISCOVER_TAB_KEY = "dreamforge.discoverLibrary.discoverTab.v1";

export function loadDiscoverTab(): DiscoverTab {
  try {
    return localStorage.getItem(DISCOVER_TAB_KEY) === "discover_workflows"
      ? "discover_workflows"
      : "discover";
  } catch {
    return "discover";
  }
}

export function saveDiscoverTab(tab: DiscoverTab): void {
  try {
    localStorage.setItem(DISCOVER_TAB_KEY, tab);
  } catch {
    /* private mode or storage quota */
  }
}

export function loadDiscoverLibrarySurface(): DiscoverLibrarySurface {
  try {
    return localStorage.getItem(SURFACE_KEY) === "discover" ? "discover" : "library";
  } catch {
    return "library";
  }
}

export function saveDiscoverLibrarySurface(surface: DiscoverLibrarySurface): void {
  try {
    localStorage.setItem(SURFACE_KEY, surface);
  } catch {
    /* private mode or storage quota */
  }
}

export function loadDiscoverLibraryTab(): DiscoverLibraryTab {
  try {
    const tab = localStorage.getItem(LIBRARY_TAB_KEY);
    return tab === "loras" || tab === "styles" || tab === "settings" || tab === "automation"
      ? tab
      : "models";
  } catch {
    return "models";
  }
}

export function saveDiscoverLibraryTab(tab: DiscoverLibraryTab): void {
  try {
    localStorage.setItem(LIBRARY_TAB_KEY, tab);
  } catch {
    /* private mode or storage quota */
  }
}

export function loadDiscoverKind(): "checkpoint" | "lora" {
  try {
    return localStorage.getItem(DISCOVER_KIND_KEY) === "lora" ? "lora" : "checkpoint";
  } catch {
    return "checkpoint";
  }
}

export function saveDiscoverKind(kind: "checkpoint" | "lora"): void {
  try {
    localStorage.setItem(DISCOVER_KIND_KEY, kind);
  } catch {
    /* private mode or storage quota */
  }
}

export type AssetKindValue = "checkpoint" | "lora" | "vae" | "embedding" | "upscaler" | "text_encoder" | "style" | "workflow" | "unknown";

export type DiscoverAssetFile = {
  filename: string;
  sha256: string;
  size_bytes: number;
  variant: string;
  format: string;
  download_url: string;
  local_path: string;
};

export type DiscoverAssetVersion = {
  id: string;
  name: string;
  files: DiscoverAssetFile[];
  provider_version_id: string;
  base_model: string;
  published_at: string;
  notes: string;
  thumbnail_url: string;
};

export type DiscoverProvenance = {
  provider: string;
  source_url: string;
  provider_asset_id: string;
  provider_version_id: string;
  author: string;
  license: string;
  downloaded_at: string;
  sha256: string;
};

export type DiscoverAsset = {
  id: string;
  name: string;
  kind: AssetKindValue;
  architecture: string;
  versions: DiscoverAssetVersion[];
  provenance: DiscoverProvenance;
  tags: string[];
  description: string;
  version_id: string;
  created_at: string;
  is_local: boolean;
  license_label: string;
  /** Set when this physical file (same SHA256) was already returned by another provider. */
  deduplicated_from?: string;
};

export type ProviderInfo = {
  id: string;
  display_name: string;
  supported_kinds: string[];
  requires_credential: boolean;
  enabled: boolean;
  credential_configured: boolean;
};

export type ProviderListResult = {
  ok: boolean;
  providers: ProviderInfo[];
};

export type ProviderSearchResultEnvelope = {
  provider: string;
  ok: boolean;
  error: string;
  error_code: string;
  from_cache: boolean;
  total: number;
  page: number;
};

export type DiscoverySearchResult = {
  ok: boolean;
  query: string;
  kind: string;
  page: number;
  limit: number;
  count: number;
  assets: DiscoverAsset[];
  providers: ProviderSearchResultEnvelope[];
  provider_ok: number;
  provider_errors: number;
};

export type CredentialStatusEntry = {
  configured: boolean;
  tail: string;
};

export type CredentialStatusResult = {
  ok: boolean;
  status: Record<string, CredentialStatusEntry>;
};

export type DownloadStateValue =
  | "queued"
  | "resolving"
  | "checking_disk"
  | "downloading"
  | "paused"
  | "verifying"
  | "registering"
  | "installed"
  | "failed_network"
  | "failed_auth"
  | "failed_integrity"
  | "failed_disk"
  | "cancelled";

export type DownloadItem = {
  id: string;
  url: string;
  filename: string;
  category: string;
  expected_sha256: string;
  provider: string;
  provider_asset_id: string;
  provider_version_id: string;
  state: DownloadStateValue;
  error: string;
  error_code: string;
  progress_pct: number;
  downloaded_bytes: number;
  total_bytes: number;
  speed_mbs: number;
  eta_seconds: number;
  final_path: string;
  queued_at: string;
  started_at: string;
  finished_at: string;
};

export type DownloadEnqueueParams = {
  url: string;
  category: string;
  filename: string;
  expected_sha256?: string;
  provider?: string;
  provider_asset_id?: string;
  provider_version_id?: string;
};

export type DownloadEnqueueResult = {
  ok: boolean;
  item: DownloadItem;
  already_queued: boolean;
  error?: string;
};

export type DownloadQueueStatusResult = {
  ok: boolean;
  items: DownloadItem[];
  count: number;
};

export type DownloadItemResult = {
  ok: boolean;
  item: DownloadItem;
  error?: string;
};

export type ClearCompletedResult = {
  ok: boolean;
  removed: number;
};

export type ComputeProfileInfo = {
  vram_mb: number;
  vram_gb: number;
  backend: string;
  vendor: string;
  device_name: string;
  recommended_profile: string;
  vram_profile: string;
  has_gpu: boolean;
};

export type ComputeProfileResult = {
  ok: boolean;
  profile: ComputeProfileInfo;
};

export type RatedFileVariant = {
  index: number;
  filename: string;
  sha256: string;
  size_bytes: number;
  variant: string;
  format: string;
  estimated_mb: number;
  /** true = fits, false = too big, null = unverifiable (unknown architecture). */
  fits: boolean | null;
};

export type RecommendationResult = {
  ok: boolean;
  files: RatedFileVariant[];
  recommended: RatedFileVariant | null;
  architecture: string;
  profile: ComputeProfileInfo;
  error?: string;
};

export async function listProviders(): Promise<ProviderInfo[]> {
  const res = await bridgeInvoke<ProviderListResult>("provider_list");
  return res.providers ?? [];
}

export async function discoverySearch(params: {
  query: string;
  kind?: string;
  limit?: number;
  page?: number;
  nsfw?: boolean;
  sort?: string;
  provider_ids?: string[];
}): Promise<DiscoverySearchResult> {
  return bridgeInvoke<DiscoverySearchResult>("discovery_search", {
    query: params.query,
    kind: params.kind ?? "",
    limit: params.limit ?? 20,
    page: params.page ?? 1,
    nsfw: params.nsfw ?? false,
    sort: params.sort ?? "relevance",
    provider_ids: params.provider_ids ?? null,
  });
}

export async function credentialStatus(): Promise<CredentialStatusResult> {
  return bridgeInvoke<CredentialStatusResult>("credential_status");
}

export async function setCredential(provider: string, secret: string): Promise<CredentialStatusResult> {
  return bridgeInvoke<CredentialStatusResult>("credential_set", {
    provider,
    secret,
  });
}

export async function enqueueDownload(params: DownloadEnqueueParams): Promise<DownloadEnqueueResult> {
  return bridgeInvoke<DownloadEnqueueResult>("download_enqueue", {
    url: params.url,
    category: params.category,
    filename: params.filename,
    expected_sha256: params.expected_sha256 ?? "",
    provider: params.provider ?? "",
    provider_asset_id: params.provider_asset_id ?? "",
    provider_version_id: params.provider_version_id ?? "",
  });
}

export async function downloadQueueStatus(): Promise<DownloadItem[]> {
  const res = await bridgeInvoke<DownloadQueueStatusResult>("download_queue_status");
  return res.items ?? [];
}

export async function pauseDownload(itemId: string): Promise<DownloadItemResult> {
  return bridgeInvoke<DownloadItemResult>("download_pause", { item_id: itemId });
}

export async function resumeDownload(itemId: string): Promise<DownloadItemResult> {
  return bridgeInvoke<DownloadItemResult>("download_resume", { item_id: itemId });
}

export async function cancelDownload(itemId: string): Promise<DownloadItemResult> {
  return bridgeInvoke<DownloadItemResult>("download_cancel", { item_id: itemId });
}

export async function clearCompletedDownloads(): Promise<number> {
  const res = await bridgeInvoke<ClearCompletedResult>("download_clear_completed");
  return res.removed ?? 0;
}

export async function supportedArchitectures(): Promise<string[]> {
  const res = await bridgeInvoke<{ ok: boolean; architectures: string[] }>(
    "discover_supported_architectures",
  );
  return res.architectures ?? [];
}

export async function recommendFileVariants(
  asset: DiscoverAsset,
  vramProfile = "auto",
): Promise<RecommendationResult> {
  return bridgeInvoke<RecommendationResult>("discover_recommend_file_variants", {
    asset,
    vram_profile: vramProfile,
  });
}

export async function computeProfile(vramProfile = "auto"): Promise<ComputeProfileInfo> {
  const res = await bridgeInvoke<ComputeProfileResult>("get_compute_profile", {
    vram_profile: vramProfile,
  });
  return res.profile;
}
