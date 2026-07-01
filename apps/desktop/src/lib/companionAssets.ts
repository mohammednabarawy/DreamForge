import type { ModelDependencyItem, RepairAction } from "./tauri-api";

const NODE_TO_PACK: Record<string, string> = {
  UltimateSDUpscale: "ComfyUI_UltimateSDUpscale",
  IPAdapterModelLoader: "ComfyUI_IPAdapter_plus",
  IPAdapter: "ComfyUI_IPAdapter_plus",
  INPAINT_LoadFooocusInpaint: "comfyui-inpaint-nodes",
  INPAINT_ShrinkMask: "comfyui-inpaint-nodes",
  INPAINT_StabilizeMask: "comfyui-inpaint-nodes",
  INPAINT_ColorMatch: "comfyui-inpaint-nodes",
  InpaintPreprocessor: "comfyui_controlnet_aux",
  DepthAnythingV2Preprocessor: "comfyui_controlnet_aux",
  OpenposePreprocessor: "comfyui_controlnet_aux",
  "LayerMask: SegformerB2ClothesUltra": "ComfyUI_LayerStyle",
  "RemBGSession+": "ComfyUI_essentials",
  "ImageRemoveBackground+": "ComfyUI_essentials",
};

export function resolvePackIdFromRepairAction(action: RepairAction): string | undefined {
  const packId = typeof action.pack_id === "string" ? action.pack_id.trim() : "";
  if (packId && packId !== "unknown") return packId;
  for (const node of action.nodes ?? []) {
    const mapped = NODE_TO_PACK[String(node)];
    if (mapped) return mapped;
  }
  return undefined;
}

export function customNodeItemFromPackId(
  packId: string,
  nodes?: string[],
  installVia?: "pinned" | "manager",
): ModelDependencyItem {
  const via = installVia ?? "pinned";
  return {
    kind: "custom_node_pack",
    pack_id: packId,
    id: packId,
    filename: packId,
    relative: `engines/comfyui/custom_nodes/${packId}`,
    category: "custom_nodes",
    install_via: via,
    note:
      via === "manager"
        ? nodes && nodes.length > 0
          ? `Install via ComfyUI-Manager: ${nodes.join(", ")}`
          : "Install via ComfyUI-Manager (cm-cli)."
        : nodes && nodes.length > 0
          ? `Install ComfyUI nodes: ${nodes.join(", ")}`
          : "Install ComfyUI custom node pack from the pinned DreamForge recipe.",
  };
}

export function customNodeItemsFromActions(actions?: RepairAction[]): ModelDependencyItem[] {
  const seen = new Set<string>();
  const items: ModelDependencyItem[] = [];
  for (const action of actions ?? []) {
    if (action.action !== "install_custom_node_pack") continue;
    const packId = resolvePackIdFromRepairAction(action);
    if (!packId || seen.has(packId)) continue;
    seen.add(packId);
    items.push(
      customNodeItemFromPackId(
        packId,
        action.nodes,
        action.install_via === "manager" ? "manager" : "pinned",
      ),
    );
  }
  return items;
}

export function isCustomNodePackItem(item: ModelDependencyItem): boolean {
  return item.kind === "custom_node_pack";
}

export function isWorkflowModelItem(item: ModelDependencyItem): boolean {
  return item.kind === "workflow_model" || Boolean(item.catalog_id?.trim());
}

export function workflowModelItemFromCatalogId(catalogId: string): ModelDependencyItem {
  return {
    kind: "workflow_model",
    catalog_id: catalogId,
    id: catalogId,
    filename: catalogId,
    relative: `segformer_b2_clothes/model.safetensors`,
    category: "segformer_b2_clothes",
    install_via: "direct",
    note: "Workflow segmentation weights required by the selected tool.",
  };
}

export function clampUpscaleBy(value: number): number {
  if (!Number.isFinite(value)) return 2;
  return Math.max(1, Math.min(4, value));
}

export function clampUpscaleTile(value: number, fallback = 1024): number {
  if (!Number.isFinite(value)) return fallback;
  const rounded = Math.round(value / 8) * 8;
  return Math.max(64, Math.min(2048, rounded));
}
