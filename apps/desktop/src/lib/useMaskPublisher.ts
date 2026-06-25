import { useCallback, useEffect, useRef, useState } from "react";
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

/**
 * Debounced mask export with monotonic sequence — avoids stale writes when
 * the user paints quickly or taps grow/shrink repeatedly (Krita/Photoshop-style).
 *
 * Masks are exported at the editor canvas resolution; the backend resizes to
 * the source image before Comfy upload.
 */
export function useMaskPublisher(
  getMaskCanvas: () => HTMLCanvasElement | null,
  onMaskChange?: (path: string) => void,
  debounceMs = MASK_PUBLISH_DEBOUNCE_MS,
) {
  const sequenceRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [syncing, setSyncing] = useState(false);

  const cancelScheduled = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const exportMaskNow = useCallback(async (): Promise<string | undefined> => {
    cancelScheduled();
    sequenceRef.current += 1;

    const mask = getMaskCanvas();
    if (!mask || mask.width <= 0 || mask.height <= 0) return undefined;

    setSyncing(true);
    try {
      const dataUrl = mask.toDataURL("image/png");
      const path = await writeTempPng(dataUrl);
      onMaskChange?.(path);
      return path;
    } catch {
      return undefined;
    } finally {
      setSyncing(false);
    }
  }, [cancelScheduled, getMaskCanvas, onMaskChange]);

  const publishMask = useCallback(
    async (options?: { immediate?: boolean }): Promise<string | undefined> => {
      const mask = getMaskCanvas();
      if (!mask || mask.width <= 0 || mask.height <= 0) return undefined;

      if (!options?.immediate) {
        cancelScheduled();
        return new Promise((resolve) => {
          timerRef.current = setTimeout(() => {
            timerRef.current = null;
            void publishMask({ immediate: true }).then(resolve);
          }, debounceMs);
        });
      }

      const seq = ++sequenceRef.current;
      setSyncing(true);
      try {
        const dataUrl = mask.toDataURL("image/png");
        const path = await writeTempPng(dataUrl);
        if (seq !== sequenceRef.current) return undefined;
        onMaskChange?.(path);
        return path;
      } catch {
        return undefined;
      } finally {
        if (seq === sequenceRef.current) setSyncing(false);
      }
    },
    [cancelScheduled, debounceMs, getMaskCanvas, onMaskChange],
  );

  useEffect(() => cancelScheduled, [cancelScheduled]);

  return { publishMask, exportMaskNow, syncing, cancelScheduled };
}
