import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Download,
  ExternalLink,
  KeyRound,
  Search,
} from "lucide-react";
import {
  downloadModel,
  onDownloadComplete,
  onDownloadProgress,
  type DownloadProgressPayload,
} from "../lib/tauri-api";

type Props = {
  civitaiApiKey: string;
  onApiKeyChange: (key: string) => void;
  onRefreshInventory: () => void;
};

type MarketplaceType = "Checkpoint" | "LORA";

type CivitaiFile = {
  id: number;
  name: string;
  downloadUrl: string;
  primary?: boolean;
  sizeKB?: number;
  type?: string;
  metadata?: { format?: string; fp?: string; size?: string };
};

type CivitaiModel = {
  id: number;
  name: string;
  type: MarketplaceType | string;
  nsfw?: boolean;
  stats?: { downloadCount?: number; rating?: number };
  creator?: { username?: string };
  modelVersions?: Array<{
    id: number;
    name: string;
    baseModel?: string;
    files?: CivitaiFile[];
    images?: Array<{ url: string; nsfw?: boolean }>;
  }>;
};

function formatBytes(kb?: number) {
  if (!kb) return "";
  if (kb > 1024 * 1024) return `${(kb / 1024 / 1024).toFixed(1)} GB`;
  if (kb > 1024) return `${(kb / 1024).toFixed(0)} MB`;
  return `${kb.toFixed(0)} KB`;
}

function pickModelFile(model: CivitaiModel) {
  const version = model.modelVersions?.[0];
  const files = version?.files ?? [];
  const modelFile =
    files.find((f) => f.primary && f.type === "Model") ??
    files.find((f) => f.type === "Model") ??
    files.find((f) => /\.(safetensors|ckpt|pt)$/i.test(f.name));
  if (!version || !modelFile) return null;
  return { version, file: modelFile };
}

function categoryForType(type: string) {
  return type.toUpperCase() === "LORA" ? "loras" : "checkpoints";
}

export function MarketplaceTab({
  civitaiApiKey,
  onApiKeyChange,
  onRefreshInventory,
}: Props) {
  const [query, setQuery] = useState("");
  const [type, setType] = useState<MarketplaceType>("Checkpoint");
  const [models, setModels] = useState<CivitaiModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloads, setDownloads] = useState<Record<string, DownloadProgressPayload>>({});

  useEffect(() => {
    const unsubs: Array<() => void> = [];
    void onDownloadProgress((p) => {
      setDownloads((prev) => ({ ...prev, [p.filename]: p }));
    }).then((u) => unsubs.push(u));
    void onDownloadComplete((p) => {
      setDownloads((prev) => ({ ...prev, [p.filename]: p }));
      onRefreshInventory();
    }).then((u) => unsubs.push(u));
    return () => unsubs.forEach((u) => u());
  }, [onRefreshInventory]);

  const searchModels = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("limit", "24");
      params.set("types", type);
      params.set("sort", query.trim() ? "Most Downloaded" : "Highest Rated");
      params.set("period", "AllTime");
      params.set("nsfw", "false");
      if (query.trim()) params.set("query", query.trim());
      const res = await fetch(`https://civitai.com/api/v1/models?${params.toString()}`);
      if (!res.ok) throw new Error(`Civitai returned ${res.status}`);
      const data = (await res.json()) as { items?: CivitaiModel[] };
      setModels((data.items ?? []).filter((m) => m.type === type));
    } catch (e) {
      setError(String(e));
      setModels([]);
    } finally {
      setLoading(false);
    }
  }, [query, type]);

  useEffect(() => {
    void searchModels();
  }, [searchModels]);

  const visibleModels = useMemo(
    () => models.filter((m) => Boolean(pickModelFile(m))),
    [models],
  );

  const handleDownload = async (model: CivitaiModel) => {
    const picked = pickModelFile(model);
    if (!picked) return;
    const { file } = picked;
    const category = categoryForType(model.type);
    setDownloads((prev) => ({
      ...prev,
      [file.name]: {
        filename: file.name,
        percentage: 0,
        downloaded: 0,
        total: file.sizeKB ? Math.round(file.sizeKB * 1024) : undefined,
        status: "downloading",
        category,
      },
    }));
    try {
      await downloadModel({
        url: file.downloadUrl,
        category,
        filename: file.name,
        apiKey: civitaiApiKey.trim() || null,
      });
    } catch (e) {
      setDownloads((prev) => ({
        ...prev,
        [file.name]: {
          filename: file.name,
          percentage: 0,
          status: "error",
          category,
        },
      }));
      setError(`Download failed: ${String(e)}`);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="space-y-2">
        <div className="flex gap-1.5">
          {(["Checkpoint", "LORA"] as MarketplaceType[]).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setType(mode)}
              className={`flex-1 rounded-md border px-2 py-1.5 text-[10px] font-semibold transition ${
                type === mode
                  ? "border-dfui-accent bg-dfui-accent/15 text-dfui-fg"
                  : "border-dfui-border/60 text-dfui-muted hover:text-dfui-fg"
              }`}
            >
              {mode === "LORA" ? "LoRAs" : "Checkpoints"}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void searchModels();
            }}
            placeholder={`Search Civitai ${type === "LORA" ? "LoRAs" : "checkpoints"}...`}
            className="df-input min-w-0 flex-1 px-2.5 py-1.5 text-xs"
          />
          <button
            type="button"
            onClick={() => void searchModels()}
            disabled={loading}
            className="df-button-primary inline-flex items-center justify-center rounded-md px-3 py-1.5 text-xs disabled:opacity-50"
            title="Search Civitai"
          >
            <Search size={14} />
          </button>
        </div>
        <label className="flex items-center gap-2 rounded-md border border-dfui-border/50 bg-dfui-bg/30 px-2 py-1.5">
          <KeyRound size={12} className="text-dfui-muted" />
          <input
            value={civitaiApiKey}
            onChange={(e) => onApiKeyChange(e.target.value)}
            type="password"
            placeholder="Civitai API key for gated downloads"
            className="min-w-0 flex-1 bg-transparent text-[10px] text-dfui-fg outline-none placeholder:text-dfui-tertiary"
          />
        </label>
        {error && (
          <p className="rounded-md border border-red-500/30 bg-red-500/10 px-2 py-1.5 text-[10px] text-red-200">
            {error}
          </p>
        )}
      </div>

      <div className="df-gallery-pane">
        <div className="df-gallery-grid">
          {visibleModels.map((m) => {
            const picked = pickModelFile(m);
            if (!picked) return null;
            const { version, file } = picked;
            const image = version.images?.find((i) => !i.nsfw)?.url ?? version.images?.[0]?.url;
            const progress = downloads[file.name];
            const isDownloading = progress?.status === "downloading";
            const done = progress?.status === "complete" || progress?.status === "exists";
            const pct = Math.max(0, Math.min(100, progress?.percentage ?? 0));

            return (
              <article
                key={`${m.id}-${version.id}`}
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
                    {version.baseModel ?? type}
                  </span>
                  <a
                    href={`https://civitai.com/models/${m.id}?modelVersionId=${version.id}`}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded bg-black/45 p-1 text-white backdrop-blur transition hover:bg-black/70"
                    title="Open on Civitai"
                  >
                    <ExternalLink size={12} />
                  </a>
                </div>
                <div className="df-gallery-tile-caption">
                  <p className="line-clamp-2 text-[11px] font-semibold leading-tight text-white">
                    {m.name}
                  </p>
                  <p className="mt-0.5 truncate text-[9px] text-gray-300">
                    {m.creator?.username ?? "Civitai"} · {formatBytes(file.sizeKB)}
                  </p>
                  <p className="mb-1 truncate font-mono text-[8px] text-gray-400">
                    {file.metadata?.format ?? file.name}
                  </p>
                  <button
                    type="button"
                    onClick={() => void handleDownload(m)}
                    disabled={isDownloading || done}
                    className="flex h-7 w-full items-center justify-center gap-1 rounded bg-white/18 px-2 text-[10px] text-white backdrop-blur-sm transition hover:bg-white/28 disabled:opacity-100"
                  >
                    {isDownloading ? (
                      <span className="relative h-1.5 w-full overflow-hidden rounded-full bg-white/15">
                        <span
                          className="absolute inset-y-0 left-0 rounded-full bg-dfui-accent transition-all duration-300"
                          style={{ width: `${pct}%` }}
                        />
                      </span>
                    ) : done ? (
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
          {!loading && visibleModels.length === 0 && (
            <div className="col-span-2 py-10 text-center text-xs text-dfui-muted">
              No downloadable {type === "LORA" ? "LoRAs" : "checkpoints"} found.
            </div>
          )}
          {loading && (
            <div className="col-span-2 py-10 text-center font-mono text-xs text-dfui-muted">
              Searching Civitai...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
