import { useCallback, useEffect, useRef, useState } from "react";
import { exportMaskPngDataUrl } from "./inpaintMaskOverlay";
import { writeTempPng } from "./studioBridge";

export const MASK_PUBLISH_DEBOUNCE_MS = 280;

export function maskHasSelection(mask: HTMLCanvasElement): boolean {
  const ctx = mask.getContext("2d", { willReadFrequently: true });
  if (!ctx) return false;
  const { data } = ctx.getImageData(0, 0, mask.width, mask.height);
  for (let i = 0; i < data.length; i += 4) {
    if ((data[i] + data[i + 1] + data[i + 2]) / 3 > 127) return true;
  }
  return false;
}

export type MaskPublisherOptions = {
  debounceMs?: number;
  /** Full-resolution source size — mask is scaled up on export when set. */
  getExportSize?: () => { width: number; height: number } | null;
  onError?: (message: string) => void;
  onSyncingChange?: (syncing: boolean) => void;
};

/**
 * Debounced mask export with monotonic sequence — avoids stale writes when
 * the user paints quickly or taps grow/shrink repeatedly (Krita/Photoshop-style).
 */
export function useMaskPublisher(
  getMaskCanvas: () => HTMLCanvasElement | null,
  onMaskChange?: (path: string) => void,
  options: MaskPublisherOptions = {},
) {
  const { debounceMs = MASK_PUBLISH_DEBOUNCE_MS, getExportSize, onError, onSyncingChange } =
    options;
  const sequenceRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onSyncingChangeRef = useRef(onSyncingChange);
  onSyncingChangeRef.current = onSyncingChange;
  const [syncing, setSyncing] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);

  const setSyncingState = useCallback((next: boolean) => {
    setSyncing(next);
    onSyncingChangeRef.current?.(next);
  }, []);

  const cancelScheduled = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
      setSyncingState(false);
    }
  }, [setSyncingState]);

  const reportError = useCallback(
    (message: string) => {
      setLastError(message);
      onError?.(message);
    },
    [onError],
  );

  const writeMask = useCallback(
    async (mask: HTMLCanvasElement): Promise<string | undefined> => {
      const exportSize = getExportSize?.() ?? null;
      const dataUrl = exportMaskPngDataUrl(mask, exportSize);
      const path = await writeTempPng(dataUrl);
      setLastError(null);
      onMaskChange?.(path);
      return path;
    },
    [getExportSize, onMaskChange],
  );

  const exportMaskNow = useCallback(async (): Promise<string | undefined> => {
    cancelScheduled();
    sequenceRef.current += 1;

    const mask = getMaskCanvas();
    if (!mask || mask.width <= 0 || mask.height <= 0) return undefined;

    setSyncingState(true);
    try {
      return await writeMask(mask);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to save inpaint mask";
      reportError(message);
      return undefined;
    } finally {
      setSyncingState(false);
    }
  }, [cancelScheduled, getMaskCanvas, reportError, setSyncingState, writeMask]);

  const publishMask = useCallback(
    async (opts?: { immediate?: boolean }): Promise<string | undefined> => {
      const mask = getMaskCanvas();
      if (!mask || mask.width <= 0 || mask.height <= 0) return undefined;

      if (!opts?.immediate) {
        cancelScheduled();
        setSyncingState(true);
        return new Promise((resolve) => {
          timerRef.current = setTimeout(() => {
            timerRef.current = null;
            void publishMask({ immediate: true }).then(resolve);
          }, debounceMs);
        });
      }

      const seq = ++sequenceRef.current;
      setSyncingState(true);
      try {
        const path = await writeMask(mask);
        if (seq !== sequenceRef.current) return undefined;
        return path;
      } catch (err) {
        if (seq !== sequenceRef.current) return undefined;
        const message =
          err instanceof Error ? err.message : "Failed to save inpaint mask";
        reportError(message);
        return undefined;
      } finally {
        if (seq === sequenceRef.current) setSyncingState(false);
      }
    },
    [cancelScheduled, debounceMs, getMaskCanvas, reportError, setSyncingState, writeMask],
  );

  useEffect(() => cancelScheduled, [cancelScheduled]);

  useEffect(
    () => () => {
      cancelScheduled();
      setSyncingState(false);
    },
    [cancelScheduled, setSyncingState],
  );

  return { publishMask, exportMaskNow, syncing, lastError, cancelScheduled };
}
