import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { downloadCompanionEntries, installCustomNodePacks, verifyCompanionEntries } from "../lib/studioBridge";
import {
  checkModelDependencies,
  type DownloadProgressPayload,
  type ModelDependencyItem,
} from "../lib/tauri-api";
import { isCustomNodePackItem } from "../lib/companionAssets";

export type CompanionDownloadPhase = "idle" | "confirm" | "running" | "done" | "error";

export type CompanionDownloadLine = {
  ts: number;
  level: "info" | "ok" | "warn" | "error";
  text: string;
};

export type CompanionVerifyResult = {
  ready: boolean;
  stillMissing: ModelDependencyItem[];
};

function itemLabel(item: ModelDependencyItem): string {
  return item.id ?? item.filename ?? item.relative ?? "companion";
}

function itemDestination(item: ModelDependencyItem): string {
  return item.relative ?? `${item.category ?? "models"}/${item.filename ?? itemLabel(item)}`;
}

function manualInstallText(model: string, missing: ModelDependencyItem[]): string {
  const lines = [
    `DreamForge missing assets for: ${model || "workflow-assets"}`,
    "",
    "Download each file and place it at the listed destination under your models folder.",
    "",
  ];
  for (const item of missing) {
    lines.push(`- ${itemLabel(item)}`);
    lines.push(`  Destination: ${itemDestination(item)}`);
    lines.push(`  URL: ${item.url ?? "No direct URL configured. Use the note below."}`);
    if (item.note) lines.push(`  Note: ${item.note}`);
    if (item.expected_path) lines.push(`  Expected path: ${item.expected_path}`);
    lines.push("");
  }
  return lines.join("\n").trim();
}

type Options = {
  verifyReady?: () => Promise<CompanionVerifyResult>;
  /** When false, downloads/installs are deferred until ComfyUI is ready. */
  requireComfyReady?: () => boolean;
};

export function useCompanionDownload(options?: Options) {
  const verifyReadyRef = useRef(options?.verifyReady);
  verifyReadyRef.current = options?.verifyReady;
  const requireComfyReadyRef = useRef(options?.requireComfyReady);
  requireComfyReadyRef.current = options?.requireComfyReady;

  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState<CompanionDownloadPhase>("idle");
  const [lines, setLines] = useState<CompanionDownloadLine[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [currentItem, setCurrentItem] = useState<ModelDependencyItem | null>(null);
  const [fileProgress, setFileProgress] = useState<DownloadProgressPayload | null>(null);
  const [modelName, setModelName] = useState("");
  const [pendingMissing, setPendingMissing] = useState<ModelDependencyItem[]>([]);
  const runIdRef = useRef(0);

  const append = useCallback((level: CompanionDownloadLine["level"], text: string) => {
    setLines((prev) => [...prev, { ts: Date.now(), level, text }]);
  }, []);

  const close = useCallback(() => {
    if (phase === "running") return;
    setOpen(false);
    setPhase("idle");
    setLines([]);
    setCurrentIndex(0);
    setTotalCount(0);
    setCurrentItem(null);
    setFileProgress(null);
    setModelName("");
    setPendingMissing([]);
  }, [phase]);

  const verifyDownloads = useCallback(
    async (model: string, requested: ModelDependencyItem[]): Promise<CompanionVerifyResult> => {
      if (requested.length > 0) {
        const exact = await verifyCompanionEntries(requested);
        return {
          ready: Boolean(exact.ready),
          stillMissing: (exact.missing ?? []) as ModelDependencyItem[],
        };
      }
      if (verifyReadyRef.current) {
        return verifyReadyRef.current();
      }
      const check = await checkModelDependencies(model);
      return {
        ready: Boolean(check.ready),
        stillMissing: check.missing ?? requested,
      };
    },
    [],
  );

  const runDownload = useCallback(
    async (model: string, missing: ModelDependencyItem[]) => {
      if (requireComfyReadyRef.current && !requireComfyReadyRef.current()) {
        append("warn", "ComfyUI server is still starting — download will wait until the engine is ready.");
        setPhase("confirm");
        return;
      }
      const runId = ++runIdRef.current;
      setPhase("running");
      setLines([]);
      setCurrentIndex(0);
      setTotalCount(missing.length);
      setCurrentItem(null);
      setFileProgress(null);
      setModelName(model);

      append("info", `Model: ${model}`);
      append("info", `Preparing to download ${missing.length} required asset(s).`);
      append(
        "info",
        "Large model files can take several minutes. You can keep DreamForge open while this runs.",
      );

      if (missing.length === 0) {
        append("info", "Rechecking dependencies…");
        try {
          const verify = await verifyDownloads(model, missing);
          if (verify.ready) append("ok", "All companion files are present.");
          else
            append(
              "warn",
              `Still missing ${verify.stillMissing.length} file(s) after check.`,
            );
        } catch (e) {
          append("error", `Dependency check failed: ${String(e)}`);
        }
        setPhase("done");
        return;
      }

      const customNodePacks = missing.filter(isCustomNodePackItem);
      const modelAssets = missing.filter((item) => !isCustomNodePackItem(item));

      let failures = 0;
      if (customNodePacks.length > 0) {
        const packIds = customNodePacks
          .map((item) => item.pack_id ?? item.id)
          .filter((value): value is string => Boolean(value?.trim()));
        append(
          "info",
          `Installing ${packIds.length} ComfyUI custom node pack(s)…`,
        );
        setTotalCount(customNodePacks.length + modelAssets.length);
        for (let i = 0; i < customNodePacks.length; i += 1) {
          if (runId !== runIdRef.current) return;
          const item = customNodePacks[i];
          setCurrentIndex(i + 1);
          setCurrentItem(item);
          append("info", `Installing custom node pack: ${itemLabel(item)}`);
        }
        try {
          const payload = await installCustomNodePacks(packIds);
          if (runId !== runIdRef.current) return;
          for (const message of payload.messages ?? []) {
            append("info", message);
          }
          for (const packId of payload.installed ?? []) {
            append("ok", `Installed custom node pack: ${packId}`);
          }
          for (const err of payload.errors ?? []) {
            failures += 1;
            append(
              "error",
              `Failed ${err.pack_id ?? "custom node pack"}: ${err.error ?? "unknown error"}`,
            );
          }
          if (payload.ready) {
            append("ok", "Custom node packs are installed and registered.");
          } else if (!payload.errors?.length) {
            append("warn", "Custom node packs installed but ComfyUI still needs a restart.");
          }
        } catch (e) {
          failures += customNodePacks.length;
          append("error", `Custom node install failed: ${String(e)}`);
        }
      }

      const withoutUrl = modelAssets.filter((item) => !item.url);
      for (const item of withoutUrl) {
        append(
          "warn",
          `Manual install needed for ${itemLabel(item)}: no direct download URL configured.`,
        );
        failures += 1;
      }

      const downloadable = modelAssets.filter((item) => item.url);
      if (downloadable.length > 0) {
        append("info", `Downloading ${downloadable.length} asset(s) to the models folder…`);
        setTotalCount(customNodePacks.length + downloadable.length);
        for (let i = 0; i < downloadable.length; i += 1) {
          if (runId !== runIdRef.current) return;
          const item = downloadable[i];
          setCurrentIndex(customNodePacks.length + i + 1);
          setCurrentItem(item);
          setFileProgress({
            filename: item.filename ?? itemLabel(item),
            percentage: 0,
            downloaded: 0,
            total: 0,
          });
          append(
            "info",
            `Starting ${i + 1} of ${downloadable.length}: ${itemLabel(item)}${item.relative ? ` → ${item.relative}` : ""}`,
          );
        }

        try {
          const payload = await downloadCompanionEntries(downloadable);
          if (runId !== runIdRef.current) return;
          if (payload.ok === false && payload.error) {
            failures += downloadable.length;
            append("error", `  ${payload.error}`);
          }
          for (const result of payload.results ?? []) {
            const label = result.id ?? result.path ?? "asset";
            if (result.status === "downloaded") {
              append("ok", `  Download complete: ${label}`);
            } else if (result.status === "exists") {
              append("ok", `  Already present: ${label}`);
            } else {
              append("info", `  ${label}: ${result.status ?? "ok"}`);
            }
          }
          for (const err of payload.errors ?? []) {
            failures += 1;
            append("error", `  Failed ${err.id ?? err.relative ?? "asset"}: ${err.error ?? "unknown error"}`);
          }
          const last = downloadable[downloadable.length - 1];
          setFileProgress({
            filename: last?.filename ?? itemLabel(last ?? downloadable[0]),
            percentage: 100,
            downloaded: payload.downloaded ?? 0,
            total: payload.downloaded ?? 0,
          });
        } catch (e) {
          failures += downloadable.length;
          append("error", `Download batch failed: ${String(e)}`);
        }
      }

      setFileProgress(null);
      setCurrentItem(null);
      append("info", "Checking that DreamForge can see the downloaded assets…");
      try {
        const verify = await verifyDownloads(model, missing);
        if (verify.ready) {
          append("ok", "All required companions are now on disk.");
          setPhase(failures > 0 ? "error" : "done");
        } else {
          append(
            "warn",
            `DreamForge still cannot see ${verify.stillMissing.length} required asset(s):`,
          );
          for (const m of verify.stillMissing) {
            append(
              "warn",
              `  • ${itemLabel(m)}${m.relative ? ` → ${m.relative}` : ""}${m.note ? ` — ${m.note}` : ""}`,
            );
          }
          setPhase("error");
        }
      } catch (e) {
        append("error", `Verification failed: ${String(e)}`);
        setPhase("error");
      }
    },
    [append, verifyDownloads],
  );

  const start = useCallback(
    (model: string, missing: ModelDependencyItem[]) => {
      setOpen(true);
      setPhase("confirm");
      setLines([]);
      setCurrentIndex(0);
      setTotalCount(missing.length);
      setCurrentItem(null);
      setFileProgress(null);
      setModelName(model);
      setPendingMissing(missing);
      append("info", `Model: ${model}`);
      append("info", `${missing.length} required asset(s) need your approval before download.`);
      for (const item of missing.slice(0, 8)) {
        append("info", `  • ${itemLabel(item)}${item.relative ? ` → ${item.relative}` : ""}`);
      }
      if (missing.length > 8) append("info", `  • ${missing.length - 8} more…`);
    },
    [append],
  );

  const approve = useCallback(() => {
    if (!modelName) return;
    void runDownload(modelName, pendingMissing);
  }, [modelName, pendingMissing, runDownload]);

  const copyLinks = useCallback(async () => {
    const links = pendingMissing
      .map((item) => item.url)
      .filter((url): url is string => Boolean(url?.trim()));
    if (links.length === 0) {
      append("warn", "No direct download links are configured for these assets.");
      return;
    }
    try {
      await navigator.clipboard.writeText([...new Set(links)].join("\n"));
      append("ok", `Copied ${new Set(links).size} download link(s) to clipboard.`);
    } catch (e) {
      append("error", `Could not copy links: ${String(e)}`);
    }
  }, [append, pendingMissing]);

  const copyManualList = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(manualInstallText(modelName, pendingMissing));
      append("ok", "Copied manual download/install list to clipboard.");
    } catch (e) {
      append("error", `Could not copy manual list: ${String(e)}`);
    }
  }, [append, modelName, pendingMissing]);

  const retry = useCallback(() => {
    if (!modelName) return;
    void verifyDownloads(modelName, pendingMissing).then((verify) => {
      void runDownload(modelName, verify.stillMissing.length ? verify.stillMissing : pendingMissing);
    });
  }, [modelName, pendingMissing, runDownload, verifyDownloads]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && phase !== "running") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, phase, close]);

  return useMemo(
    () => ({
      open,
      phase,
      lines,
      currentIndex,
      totalCount,
      currentItem,
      fileProgress,
      modelName,
      pendingMissing,
      busy: phase === "running",
      start,
      approve,
      copyLinks,
      copyManualList,
      close,
      retry,
    }),
    [
      open,
      phase,
      lines,
      currentIndex,
      totalCount,
      currentItem,
      fileProgress,
      modelName,
      pendingMissing,
      start,
      approve,
      copyLinks,
      copyManualList,
      close,
      retry,
    ],
  );
}
