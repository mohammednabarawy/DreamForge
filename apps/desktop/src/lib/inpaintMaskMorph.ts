export function isMaskPixelSelected(data: Uint8ClampedArray, offset: number): boolean {
  return (data[offset] + data[offset + 1] + data[offset + 2]) / 3 > 127;
}

export function readMaskBinary(
  data: Uint8ClampedArray,
  width: number,
  height: number,
): Uint8Array {
  const binary = new Uint8Array(width * height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      binary[y * width + x] = isMaskPixelSelected(data, i) ? 1 : 0;
    }
  }
  return binary;
}

export function writeMaskImageData(
  target: ImageData,
  binary: Uint8Array,
  width: number,
  height: number,
) {
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = y * width + x;
      const i = idx * 4;
      const v = binary[idx] ? 255 : 0;
      target.data[i] = v;
      target.data[i + 1] = v;
      target.data[i + 2] = v;
      target.data[i + 3] = 255;
    }
  }
}

/** Morphological grow (dilate) or shrink (erode) by N pixels on an 8-connected grid. */
export function morphMaskBinary(
  binary: Uint8Array,
  width: number,
  height: number,
  pixels: number,
  grow: boolean,
): Uint8Array {
  const steps = Math.max(0, Math.floor(pixels));
  if (steps === 0) return binary;

  let current = binary;
  for (let step = 0; step < steps; step++) {
    const next = new Uint8Array(width * height);
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const idx = y * width + x;
        if (grow) {
          let selected = current[idx] === 1;
          if (!selected) {
            for (let dy = -1; dy <= 1 && !selected; dy++) {
              for (let dx = -1; dx <= 1 && !selected; dx++) {
                const nx = x + dx;
                const ny = y + dy;
                if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue;
                if (current[ny * width + nx] === 1) selected = true;
              }
            }
          }
          next[idx] = selected ? 1 : 0;
        } else {
          let selected = current[idx] === 1;
          if (selected) {
            for (let dy = -1; dy <= 1 && selected; dy++) {
              for (let dx = -1; dx <= 1 && selected; dx++) {
                const nx = x + dx;
                const ny = y + dy;
                if (nx < 0 || nx >= width || ny < 0 || ny >= height) {
                  selected = false;
                  break;
                }
                if (current[ny * width + nx] !== 1) selected = false;
              }
            }
          }
          next[idx] = selected ? 1 : 0;
        }
      }
    }
    current = next;
  }
  return current;
}

export const MORPH_PIXEL_MIN = 1;
export const MORPH_PIXEL_MAX = 32;

export function clampMorphPixels(raw: number, fallback = 1): number {
  if (!Number.isFinite(raw)) return fallback;
  return Math.max(MORPH_PIXEL_MIN, Math.min(MORPH_PIXEL_MAX, Math.floor(raw)));
}
