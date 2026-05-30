import { useCallback, useEffect, useRef, useState } from "react";
import {
  checkModelDependencies,
  downloadModel,
  onDownloadComplete,
  onDownloadProgress,
  type DownloadProgressPayload,
  type ModelDependencyItem,
} from "../lib/tauri-api";

export type CompanionDownloadPhase = "idle" | "confirm" | "running" | "done" | "error";

export type CompanionDownloadLine = {
  ts: number;
  level: "info" | "ok" | "warn" | "error";
  text: string;
};

function formatBytes(n: number): string {
  if (n <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v < 10 && i > 0 ? v.toFixed(1) : Math.round(v)} ${units[i]}`;
}

function itemLabel(item: ModelDependencyItem): string {
  return item.id ?? item.filename ?? item.relative ?? "companion";
}

async function downloadOneCompanion(
  params: {
    url: string;
    category: string;
    filename: string;
  },
  onProgress: (p: DownloadProgressPayload) => void,
  runId: number,
  runIdRef: { current: number },
): Promise<DownloadProgressPayload> {
  return new Promise((resolve, reject) => {
    const cleanups: Array<() => void> = [];
    const finish = (fn: () => void) => {
      cleanups.forEach((c) => c());
      fn();
    };

    void onDownloadProgress((p) => {
      if (runId !== runIdRef.current) return;
      if (p.filename === params.filename) onProgress(p);
    }).then((u) => cleanups.push(u));

    void onDownloadComplete((p) => {
      if (runId !== runIdRef.current) return;
      if (p.filename !== params.filename) return;
      finish(() => resolve(p));
    }).then((u) => cleanups.push(u));

    void downloadModel(params).catch((e) => finish(() => reject(e)));
  });
}

export function useCompanionDownload() {
  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState<CompanionDownloadPhase>("idle");
  const [lines, setLines] = useState<CompanionDownloadLine[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [currentItem, setCurrentItem] = useState<ModelDependencyItem | null>(null);
  const [fileProgress, setFileProgress] =
    useState<DownloadProgressPayload | null>(null);
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

  const runDownload = useCallback(
    async (model: string, missing: ModelDependencyItem[]) => {
      const runId = ++runIdRef.current;
      setPhase("running");
      setLines([]);
      setCurrentIndex(0);
      setTotalCount(missing.length);
      setCurrentItem(null);
      setFileProgress(null);
      setModelName(model);

      append("info", `Model: ${model}`);
      append("info", `${missing.length} companion file(s) to fetch`);
      append(
        "info",
        "Large files (CLIP / VAE) can take several minutes — progress updates below.",
      );

      if (missing.length === 0) {
        append("info", "Rechecking dependencies…");
        try {
          const check = await checkModelDependencies(model);
          if (check.ready) append("ok", "All companion files are present.");
          else
            append(
              "warn",
              `Still missing ${check.missing?.length ?? 0} file(s) after check.`,
            );
        } catch (e) {
          append("error", `Dependency check failed: ${String(e)}`);
        }
        setPhase("done");
        return;
      }

      let failures = 0;
      for (let i = 0; i < missing.length; i += 1) {
        if (runId !== runIdRef.current) return;
        const item = missing[i];
        setCurrentIndex(i + 1);
        setCurrentItem(item);
        setFileProgress(null);

        const label = itemLabel(item);
        append(
          "info",
          `[${i + 1}/${missing.length}] ${label}${item.relative ? ` → ${item.relative}` : ""}`,
        );

        if (!item.url) {
          append("warn", "  Skipped: no download URL configured for this companion.");
          failures += 1;
          continue;
        }

        const category = item.category ?? "clip";
        const filename =
          item.filename ?? item.relative?.split("/").pop() ?? `${label}.bin`;

        append("info", `  URL: ${item.url}`);
        append("info", `  Destination: backend/models/${category}/${filename}`);

        try {
          const result = await downloadOneCompanion(
            { url: item.url, category, filename },
            (p) => setFileProgress(p),
            runId,
            runIdRef,
          );
          const dl = result.downloaded ?? 0;
          const tot = result.total ?? dl;
          const status = result.status ?? "complete";
          append(
            "ok",
            `  ${status === "exists" ? "Already present" : "Done"} (${formatBytes(dl)}${
              tot > 0 ? ` / ${formatBytes(tot)}` : ""
            })`,
          );
        } catch (e) {
          failures += 1;
          const msg = String(e);
          append("error", `  Failed: ${msg}`);
          if (
            msg.includes("401") ||
            msg.includes("403") ||
            msg.toLowerCase().includes("gated")
          ) {
            append(
              "warn",
              "  Tip: set HF_TOKEN or HUGGING_FACE_HUB_TOKEN in your environment for gated Hugging Face files.",
            );
          }
        }
      }

      setFileProgress(null);
      setCurrentItem(null);
      append("info", "Verifying model dependencies…");
      try {
        const check = await checkModelDependencies(model);
        if (check.ready) {
          append("ok", "All required companions are now on disk.");
          setPhase(failures > 0 ? "error" : "done");
        } else {
          append(
            "warn",
            `Still missing ${check.missing?.length ?? 0} file(s):`,
          );
          for (const m of check.missing ?? []) {
            append("warn", `  • ${itemLabel(m)}${m.note ? ` — ${m.note}` : ""}`);
          }
          setPhase("error");
        }
      } catch (e) {
        append("error", `Verification failed: ${String(e)}`);
        setPhase("error");
      }
    },
    [append],
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
      append("info", `${missing.length} companion file(s) need approval before download.`);
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

  const retry = useCallback(() => {
    if (!modelName) return;
    void checkModelDependencies(modelName).then((res) => {
      void runDownload(modelName, res.missing ?? []);
    });
  }, [modelName, runDownload]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && phase !== "running") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, phase, close]);

  return {
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
    close,
    retry,
  };
}
