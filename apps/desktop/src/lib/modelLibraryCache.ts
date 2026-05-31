import type { InventoryPayload, LoraGalleryItem, ModelGalleryItem } from "./tauri-api";
import { parseInventoryResponse } from "./inventory";

const STORAGE_KEY = "dreamforge.modelLibrary.v1";

export type ModelLibrarySnapshot = {
  savedAt: number;
  modelsRoot?: string;
  modelGallery: ModelGalleryItem[];
  loraGallery: LoraGalleryItem[];
  inventory: InventoryPayload;
};

export function readModelLibrarySnapshot(): ModelLibrarySnapshot | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ModelLibrarySnapshot;
    if (!parsed || !Array.isArray(parsed.modelGallery) || !Array.isArray(parsed.loraGallery)) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function writeModelLibrarySnapshot(snapshot: ModelLibrarySnapshot): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    /* quota or private mode */
  }
}

export function clearModelLibrarySnapshot(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export function hydrateInventoryFromSnapshot(
  snapshot: ModelLibrarySnapshot | null,
): ReturnType<typeof parseInventoryResponse> | null {
  if (!snapshot?.inventory) return null;
  return parseInventoryResponse(snapshot.inventory as Record<string, unknown>);
}
