/** Photoshop-style quick-mask tint (not exported to Comfy). */
export const MASK_OVERLAY_RGBA = { r: 255, g: 96, b: 96, a: 97 } as const;

export function isMaskPixelSelected(data: Uint8ClampedArray, offset: number): boolean {
  return (data[offset] + data[offset + 1] + data[offset + 2]) / 3 > 127;
}

export function getOffscreenMask(
  w: number,
  h: number,
  maskRef: { current: HTMLCanvasElement | null },
): HTMLCanvasElement {
  if (!maskRef.current) {
    maskRef.current = document.createElement("canvas");
  }
  const mask = maskRef.current;
  if (mask.width !== w || mask.height !== h) {
    mask.width = w;
    mask.height = h;
    const ctx = mask.getContext("2d");
    if (ctx) {
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, w, h);
    }
  }
  return mask;
}

export function drawMaskOverlayView(
  view: HTMLCanvasElement,
  baseImage: HTMLImageElement,
  mask: HTMLCanvasElement,
  overlayHelperRef: { current: HTMLCanvasElement | null },
): void {
  const w = view.width;
  const h = view.height;
  const ctx = view.getContext("2d");
  if (!ctx || w <= 0 || h <= 0) return;

  ctx.clearRect(0, 0, w, h);
  ctx.globalCompositeOperation = "source-over";
  ctx.globalAlpha = 1;
  ctx.drawImage(baseImage, 0, 0, w, h);

  const maskCtx = mask.getContext("2d");
  if (!maskCtx) return;
  const maskData = maskCtx.getImageData(0, 0, w, h);

  if (!overlayHelperRef.current) {
    overlayHelperRef.current = document.createElement("canvas");
  }
  const overlay = overlayHelperRef.current;
  if (overlay.width !== w || overlay.height !== h) {
    overlay.width = w;
    overlay.height = h;
  }
  const octx = overlay.getContext("2d");
  if (!octx) return;

  const overlayData = octx.createImageData(w, h);
  const { r, g, b, a } = MASK_OVERLAY_RGBA;
  for (let i = 0; i < maskData.data.length; i += 4) {
    if (isMaskPixelSelected(maskData.data, i)) {
      overlayData.data[i] = r;
      overlayData.data[i + 1] = g;
      overlayData.data[i + 2] = b;
      overlayData.data[i + 3] = a;
    }
  }
  octx.putImageData(overlayData, 0, 0);

  ctx.globalCompositeOperation = "source-over";
  ctx.globalAlpha = 1;
  ctx.drawImage(overlay, 0, 0, w, h);
}

export function scaleImageDimensions(
  naturalW: number,
  naturalH: number,
  maxDim: number,
): { w: number; h: number } {
  let w = naturalW;
  let h = naturalH;
  const scale = Math.min(1, maxDim / Math.max(w, h));
  return { w: Math.round(w * scale), h: Math.round(h * scale) };
}

/** Scale editor mask to source image pixels before Comfy upload. */
export function exportMaskPngDataUrl(
  mask: HTMLCanvasElement,
  exportSize?: { width: number; height: number } | null,
): string {
  const targetW = exportSize?.width ?? mask.width;
  const targetH = exportSize?.height ?? mask.height;
  if (targetW === mask.width && targetH === mask.height) {
    return mask.toDataURL("image/png");
  }
  const out = document.createElement("canvas");
  out.width = targetW;
  out.height = targetH;
  const ctx = out.getContext("2d");
  if (!ctx) return mask.toDataURL("image/png");
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(mask, 0, 0, targetW, targetH);
  return out.toDataURL("image/png");
}
