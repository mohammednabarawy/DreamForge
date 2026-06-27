import type { InpaintContextPlan } from "./studioBridge";

export type ObjectContainLayout = {
  scale: number;
  displayW: number;
  displayH: number;
  offsetX: number;
  offsetY: number;
};

/** Map source image pixels to displayed object-contain coordinates. */
export function objectContainLayout(
  frameW: number,
  frameH: number,
  imageW: number,
  imageH: number,
): ObjectContainLayout {
  if (frameW <= 0 || frameH <= 0 || imageW <= 0 || imageH <= 0) {
    return { scale: 1, displayW: 0, displayH: 0, offsetX: 0, offsetY: 0 };
  }
  const scale = Math.min(frameW / imageW, frameH / imageH);
  const displayW = imageW * scale;
  const displayH = imageH * scale;
  return {
    scale,
    displayW,
    displayH,
    offsetX: (frameW - displayW) / 2,
    offsetY: (frameH - displayH) / 2,
  };
}

export function imageBoxToPercentRect(
  box: number[],
  imageSize: [number, number],
): { left: number; top: number; width: number; height: number } | null {
  const [imgW, imgH] = imageSize;
  if (box.length < 4 || imgW <= 0 || imgH <= 0) return null;
  const [x0, y0, x1, y1] = box;
  return {
    left: (x0 / imgW) * 100,
    top: (y0 / imgH) * 100,
    width: ((x1 - x0) / imgW) * 100,
    height: ((y1 - y0) / imgH) * 100,
  };
}

export function inpaintOverlayRects(context: InpaintContextPlan | undefined) {
  const imageSize = context?.image_size;
  if (!imageSize || imageSize.length < 2) {
    return { crop: null as ReturnType<typeof imageBoxToPercentRect>, mask: null };
  }
  const size = imageSize as [number, number];
  const cropBox = context?.crop?.enabled ? context.crop.box : undefined;
  const maskBox = context?.mask_empty ? undefined : context?.mask_bbox;
  return {
    crop: cropBox ? imageBoxToPercentRect(cropBox, size) : null,
    mask: maskBox ? imageBoxToPercentRect(maskBox, size) : null,
  };
}
