/** VRAM / unified-memory profiles — keep in sync with backend/dreamforge_vram_profiles.py */

export type VramProfile =
  | "auto"
  | "16gb"
  | "24gb"
  | "32gb"
  | "12gb"
  | "8gb"
  | "5gb"
  | "no_gpu"
  | "mps_24gb"
  | "mps_32gb"
  | "mps_16gb"
  | "mps_8gb"
  | "mps_4gb"
  | "mps";

const MAC_PROFILES: VramProfile[] = ["mps_32gb", "mps_24gb", "mps_16gb", "mps_8gb", "mps_4gb"];
const CUDA_PROFILES: VramProfile[] = ["32gb", "24gb", "16gb", "12gb", "8gb", "5gb", "no_gpu"];

export function isVramProfile(value: string): value is VramProfile {
  return (
    value === "auto" ||
    value === "mps" ||
    MAC_PROFILES.includes(value as VramProfile) ||
    CUDA_PROFILES.includes(value as VramProfile)
  );
}

export const CUDA_VRAM_OPTIONS: { value: VramProfile; label: string }[] = [
  { value: "32gb", label: "32 GB+ — NVIDIA / discrete" },
  { value: "24gb", label: "24 GB — NVIDIA / discrete" },
  { value: "16gb", label: "16 GB — NVIDIA / discrete" },
  { value: "12gb", label: "12 GB" },
  { value: "8gb", label: "8 GB" },
  { value: "5gb", label: "5 GB (tight VRAM)" },
  { value: "no_gpu", label: "CPU only" },
];

export const MAC_VRAM_OPTIONS: { value: VramProfile; label: string }[] = [
  { value: "mps_32gb", label: "32 GB+ unified (Max / Ultra)" },
  { value: "mps_24gb", label: "24 GB unified (M2/M3/M4 Max, 32 GB RAM)" },
  { value: "mps_16gb", label: "16 GB unified (M1/M2/M3 Pro, 16–18 GB RAM)" },
  { value: "mps_8gb", label: "8 GB unified (base M-series, ~8–12 GB RAM)" },
  { value: "mps_4gb", label: "4 GB unified (8 GB RAM or less)" },
];

/** Map hardware telemetry to a concrete profile (matches backend RAM thresholds). */
export function vramProfileFromHardware(
  vramGb: number | null,
  mpsAvailable: boolean | null,
): VramProfile {
  if (mpsAvailable) {
    if (vramGb != null) {
      if (vramGb >= 30) return "mps_32gb";
      if (vramGb >= 22) return "mps_24gb";
      if (vramGb >= 14) return "mps_16gb";
      if (vramGb >= 10) return "mps_8gb";
      return "mps_4gb";
    }
    return "mps_8gb";
  }
  if (vramGb == null) return "16gb";
  if (vramGb >= 30) return "32gb";
  if (vramGb >= 22) return "24gb";
  if (vramGb >= 14) return "16gb";
  if (vramGb >= 10.5) return "12gb";
  if (vramGb >= 7) return "8gb";
  return "5gb";
}

/** Resolve `auto` using worker hint or hardware telemetry. */
export function resolveVramProfile(
  selected: VramProfile | string | undefined,
  vramGb: number | null,
  mpsAvailable: boolean | null,
  hint?: string | null,
): VramProfile {
  const sel = (selected ?? "auto").toLowerCase();
  if (sel !== "auto" && sel !== "default" && isVramProfile(sel)) {
    return sel;
  }
  if (hint && isVramProfile(hint)) {
    return hint;
  }
  return vramProfileFromHardware(vramGb, mpsAvailable);
}

const MAC_ORDER: VramProfile[] = ["mps_32gb", "mps_24gb", "mps_16gb", "mps_8gb", "mps_4gb"];
const CUDA_ORDER: VramProfile[] = ["32gb", "24gb", "16gb", "12gb", "8gb", "5gb", "no_gpu"];

/** Step down one profile for OOM repair actions. */
export function lowerVramProfile(current: VramProfile | undefined): VramProfile {
  const p = current ?? "auto";
  if (p === "auto") return "auto";
  const macIdx = MAC_ORDER.indexOf(p as (typeof MAC_ORDER)[number]);
  if (macIdx >= 0) {
    return MAC_ORDER[Math.min(macIdx + 1, MAC_ORDER.length - 1)];
  }
  const cudaIdx = CUDA_ORDER.indexOf(p as (typeof CUDA_ORDER)[number]);
  if (cudaIdx >= 0) {
    return CUDA_ORDER[Math.min(cudaIdx + 1, CUDA_ORDER.length - 1)];
  }
  return "5gb";
}
