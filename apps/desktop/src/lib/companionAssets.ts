import type { ModelDependencyItem, RepairAction } from "./tauri-api";
import type { AgentPlanSnapshot } from "./studioBridge";
import type { FriendlyError } from "./errors";

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

export function isDownloadableCompanionItem(item: ModelDependencyItem): boolean {
  if (item.kind === "custom_tool") return false;
  const itemId = String(item.id ?? item.filename ?? "").trim();
  if (itemId === "workflow_not_api_format" || itemId === "workflow_file_missing") {
    return false;
  }
  return true;
}

export function isCustomNodePackItem(item: ModelDependencyItem): boolean {
  return item.kind === "custom_node_pack";
}

export function isWorkflowModelItem(item: ModelDependencyItem): boolean {
  if (item.kind !== "workflow_model") return false;
  const catalogId = String(item.catalog_id ?? item.id ?? "").trim();
  if (!catalogId || catalogId.startsWith("graph_model:")) return false;
  return true;
}

export function workflowModelItemFromCatalogId(catalogId: string): ModelDependencyItem {
  return {
    kind: "workflow_model",
    catalog_id: catalogId,
    id: catalogId,
    filename: catalogId,
    relative: catalogId,
    category: "workflow_models",
    install_via: "direct",
    note: "Workflow weights required by the selected tool.",
  };
}

export function companionItemsFromErrorDetails(
  details?: Record<string, unknown> | null,
): ModelDependencyItem[] {
  const missing = details?.missing;
  if (!Array.isArray(missing)) return [];
  return missing.filter(
    (item): item is ModelDependencyItem =>
      typeof item === "object" && item !== null && Boolean(item),
  );
}

export function companionItemsFromActions(actions?: RepairAction[]): ModelDependencyItem[] {
  const items: ModelDependencyItem[] = [];
  for (const action of actions ?? []) {
    if (action.action !== "download_model_companions") continue;
    if (Array.isArray(action.missing)) {
      items.push(...(action.missing as ModelDependencyItem[]));
      continue;
    }
    for (const catalogId of Array.isArray(action.catalog_ids) ? action.catalog_ids : []) {
      const id = String(catalogId ?? "").trim();
      if (!id) continue;
      items.push(workflowModelItemFromCatalogId(id));
    }
  }
  return items;
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

function dependencyKey(item: ModelDependencyItem): string {
  return `${item.id ?? ""}|${item.url ?? ""}|${item.filename ?? ""}|${item.relative ?? ""}|${item.expected_path ?? ""}`;
}

function mergeDependencyItems(...groups: Array<ModelDependencyItem[] | undefined>): ModelDependencyItem[] {
  const merged: ModelDependencyItem[] = [];
  const keys = new Set<string>();
  for (const group of groups) {
    for (const item of group ?? []) {
      if (!isDownloadableCompanionItem(item)) continue;
      const key = dependencyKey(item);
      if (keys.has(key)) continue;
      keys.add(key);
      merged.push(item);
    }
  }
  return merged;
}

export function mergeAllCompanionMissing(args: {
  modelMissing: ModelDependencyItem[];
  studioMissing: ModelDependencyItem[];
  taskWorkflowMissing: ModelDependencyItem[];
  customToolWorkflowMissing?: ModelDependencyItem[];
  agentPlan?: AgentPlanSnapshot | null;
  settingsSnapshot: string;
  lastError?: FriendlyError | null;
  skipBaseModelCompanions?: boolean;
}): ModelDependencyItem[] {
  // A review plan can outlive a model/mode change; only its current snapshot applies.
  const plan = args.agentPlan?.settings_snapshot === args.settingsSnapshot
    ? args.agentPlan : null;
  // Readiness errors describe these same checks; never feed them back as missing assets.
  const lastError = args.lastError?.details?.source === "readiness" ? null : args.lastError;
  return mergeDependencyItems(
    args.skipBaseModelCompanions ? [] : args.modelMissing,
    args.studioMissing,
    args.taskWorkflowMissing,
    args.customToolWorkflowMissing ?? [],
    companionItemsFromActions(plan?.readiness?.recommended_actions),
    companionItemsFromErrorDetails(lastError?.details),
    companionItemsFromActions(lastError?.failureReport?.repair_actions),
    companionItemsFromActions(
      (lastError?.details?.recommended_actions as RepairAction[] | undefined) ?? [],
    ),
    customNodeItemsFromActions(lastError?.failureReport?.repair_actions),
  );
}
