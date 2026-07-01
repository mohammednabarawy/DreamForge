import type { ModelGalleryItem } from "./tauri-api";

export const WORKFLOW_MODEL_DEFAULT = "__workflow_default__";

export type WorkflowModelLibraryOption = {
  category: string;
  relative_path: string;
  filename: string;
  caption: string;
};

export type CustomToolWorkflowModelSlot = {
  ref_key: string;
  node_id: string;
  field: string;
  class_type: string;
  filename: string;
  workflow_filename: string;
  folders: string;
  search_folders: string;
  selection: string;
  effective_filename: string;
  uses_workflow_default: boolean;
  library_options?: WorkflowModelLibraryOption[];
};

export function galleryModelsForWorkflowSlot(
  slot: Pick<CustomToolWorkflowModelSlot, "search_folders" | "folders">,
  gallery: ModelGalleryItem[],
): ModelGalleryItem[] {
  const folders = new Set(
    String(slot.search_folders || slot.folders || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  );
  if (!folders.size) return gallery;
  return gallery.filter((item) => folders.has(item.category));
}

export function galleryModelFilename(item: ModelGalleryItem): string {
  const relative = item.relative_path || item.engine_name || item.caption;
  const parts = relative.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] || relative;
}

export function workflowModelSlotLabel(slot: CustomToolWorkflowModelSlot): string {
  const node = slot.node_id ? `node ${slot.node_id}` : slot.class_type;
  return `${slot.class_type} (${node})`;
}
