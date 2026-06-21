import { useCallback, useMemo } from "react";
import type { GenerationSettings } from "../lib/tauri-api";
import type { StudioMode } from "../lib/model-selection";
import type { ModelGalleryItem } from "../lib/tauri-api";
import type { VramProfile } from "../lib/vramProfiles";
import {
  applyVramQualityDefaults,
  enforceCreativeTaskSettings,
  resolveCreativeTaskPatch,
} from "../lib/creativeTask";

export type UseCreativeTaskOptions = {
  studioMode: StudioMode;
  gallery: ModelGalleryItem[];
  vramProfile?: VramProfile | string;
  vramGb?: number | null;
  mpsAvailable?: boolean | null;
  advancedMode?: boolean;
  selectedImage?: string;
};

export function useCreativeTask(options: UseCreativeTaskOptions) {
  const {
    studioMode,
    gallery,
    vramProfile,
    vramGb = null,
    mpsAvailable = null,
    advancedMode,
    selectedImage,
  } = options;

  const enforce = useCallback(
    (settings: GenerationSettings) =>
      enforceCreativeTaskSettings(settings, {
        studioMode,
        gallery,
        advancedMode,
        vramProfile,
        vramGb,
        mpsAvailable,
        selectedImage,
      }),
    [
      studioMode,
      gallery,
      advancedMode,
      vramProfile,
      vramGb,
      mpsAvailable,
      selectedImage,
    ],
  );

  const resolvePatch = useCallback(
    (settings: GenerationSettings, imageOverride?: string) =>
      resolveCreativeTaskPatch({
        studioMode,
        gallery,
        settings,
        advancedMode,
        vramProfile,
        vramGb,
        mpsAvailable,
        selectedImage: imageOverride ?? selectedImage,
      }),
    [
      studioMode,
      gallery,
      advancedMode,
      vramProfile,
      vramGb,
      mpsAvailable,
      selectedImage,
    ],
  );

  const applyVramDefaults = useCallback(
    (settings: GenerationSettings) =>
      applyVramQualityDefaults(
        settings,
        studioMode,
        vramProfile,
        vramGb,
        mpsAvailable,
      ),
    [studioMode, vramProfile, vramGb, mpsAvailable],
  );

  return useMemo(
    () => ({ enforce, resolvePatch, applyVramDefaults }),
    [enforce, resolvePatch, applyVramDefaults],
  );
}
