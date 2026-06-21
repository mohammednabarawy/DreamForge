import { useCallback, useEffect, useRef, useState } from "react";
import { writeTempPng } from "./studioBridge";

const DEFAULT_DEBOUNCE_MS = 280;

/**
 * Debounced mask export with monotonic sequence — avoids stale writes when
 * the user paints quickly or taps grow/shrink repeatedly (Krita/Photoshop-style).
 */
export function useMaskPublisher(
  getMaskCanvas: () => HTMLCanvasElement | null,
  onMaskChange?: (path: string) => void,
  debounceMs = DEFAULT_DEBOUNCE_MS,
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

  return { publishMask, syncing, cancelScheduled };
}
