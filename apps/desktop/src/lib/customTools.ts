import { readTextFile } from "./tauri-api";

export interface CustomToolBinding {
  type: "image" | "mask" | "text" | "number" | "boolean";
  node_id: string;
  field: string;
  label?: string;
}

export interface CustomTool {
  id: string;
  name: string;
  description: string;
  workflow_path: string;
  source_workflow_path?: string;
  workflow_sha256?: string;
  workflow_format?: "ui" | "api";
  managed_workflow_version?: number;
  bindings: Record<string, CustomToolBinding>;
  /** node_id:field -> library filename, or omit for workflow default / download */
  model_overrides?: Record<string, string>;
}

export function normalizeWorkflowPath(path: string): string {
  return String(path || "")
    .trim()
    .replace(/\\/g, "/")
    .toLowerCase();
}

/** Resolve a custom tool by id, with fallbacks when ids drift after re-import. */
export function resolveCustomTool(
  tools: CustomTool[] | undefined,
  customToolId: string | undefined | null,
): CustomTool | undefined {
  const id = String(customToolId || "").trim();
  const list = tools ?? [];
  if (!list.length) return undefined;
  if (id) {
    const direct = list.find((item) => item.id === id);
    if (direct) return direct;
  }
  if (list.length === 1) {
    return list[0];
  }
  return undefined;
}

/** Upsert a tool by workflow path so re-import keeps a stable tool id. */
export function upsertCustomTool(list: CustomTool[], tool: CustomTool): CustomTool[] {
  const normalized = normalizeWorkflowPath(tool.source_workflow_path || tool.workflow_path);
  const existingIndex = list.findIndex(
    (item) =>
      item.id === tool.id ||
      normalizeWorkflowPath(item.source_workflow_path || item.workflow_path) === normalized,
  );
  if (existingIndex < 0) {
    return [...list, tool];
  }
  const stableId = list[existingIndex].id;
  const merged = { ...tool, id: stableId };
  return list.map((item, index) => (index === existingIndex ? merged : item));
}

export interface ParsedComfyWorkflow {
  nodes: Record<string, any>;
  /** True when the workflow can be imported and executed by DreamForge. */
  importable: boolean;
  uiFormat?: boolean;
  error?: string;
  warning?: string;
  repairedNodes?: string[];
}

function isUiWorkflow(data: Record<string, unknown>): boolean {
  return Array.isArray(data.nodes);
}

function workflowRoot(data: Record<string, unknown>): Record<string, unknown> {
  if (data.prompt && typeof data.prompt === "object" && !Array.isArray(data.prompt)) {
    return data.prompt as Record<string, unknown>;
  }
  return data;
}

function countApiNodes(data: Record<string, unknown>): { valid: number; missing: number; total: number } {
  const root = workflowRoot(data);
  let valid = 0;
  let missing = 0;
  let total = 0;
  for (const value of Object.values(root)) {
    if (!value || typeof value !== "object") continue;
    const node = value as Record<string, unknown>;
    if (!node.inputs || typeof node.inputs !== "object") continue;
    total += 1;
    if (node.class_type) valid += 1;
    else missing += 1;
  }
  return { valid, missing, total };
}

function looksLikeApiPrompt(data: Record<string, unknown>): boolean {
  if (isUiWorkflow(data)) return false;
  const { valid, missing, total } = countApiNodes(data);
  if (!valid || !total) return false;
  if (!missing) return true;
  return valid >= missing;
}

function normalizeWorkflowNodes(json: Record<string, unknown>): Record<string, any> {
  if (json.prompt && typeof json.prompt === "object" && !Array.isArray(json.prompt)) {
    return json.prompt as Record<string, any>;
  }
  if (Array.isArray(json.nodes)) {
    const nodes: Record<string, any> = {};
    for (const raw of json.nodes) {
      if (!raw || typeof raw !== "object") continue;
      const node = raw as Record<string, unknown>;
      const id = String(node.id ?? "");
      if (!id) continue;
      nodes[id] = {
        class_type: node.type ?? node.class_type,
        _meta: node,
      };
    }
    return nodes;
  }
  if (typeof json === "object" && json !== null) {
    const hasClassTypes = Object.values(json).some(
      (value) =>
        value &&
        typeof value === "object" &&
        "class_type" in (value as Record<string, unknown>),
    );
    if (hasClassTypes) {
      return json as Record<string, any>;
    }
  }
  return {};
}

function uiInputIsLinked(meta: Record<string, unknown> | undefined, field: string): boolean {
  if (!meta || !Array.isArray(meta.inputs)) return false;
  for (const input of meta.inputs) {
    if (!input || typeof input !== "object") continue;
    const row = input as Record<string, unknown>;
    if (String(row.name ?? "") !== field) continue;
    return row.link != null;
  }
  return false;
}

export async function parseComfyWorkflowJson(path: string): Promise<ParsedComfyWorkflow> {
  try {
    const { parseComfyWorkflowFile } = await import("./studioBridge");
    const remote = await parseComfyWorkflowFile(path);
    if (remote?.ok) {
      const nodes = (remote.nodes ?? {}) as Record<string, any>;
      const uiFormat = Boolean(remote.ui_format);
      const importable = Boolean(
        remote.api_format || uiFormat || Object.keys(nodes).length > 0,
      );
      return {
        nodes,
        importable,
        uiFormat,
        error: importable ? undefined : remote.error || remote.warning || undefined,
        warning: remote.warning || undefined,
        repairedNodes: remote.repaired_nodes ?? [],
      };
    }
  } catch {
    // Fall back to local parse when the worker bridge is unavailable.
  }

  try {
    const content = await readTextFile(path);
    if (!content) throw new Error("File could not be read");
    const json = JSON.parse(content) as Record<string, unknown>;
    const uiFormat = isUiWorkflow(json);
    const importable = looksLikeApiPrompt(json) || uiFormat;
    const nodes = normalizeWorkflowNodes(json);
    if (!Object.keys(nodes).length) {
      throw new Error("Invalid ComfyUI workflow format");
    }
    return { nodes, importable, uiFormat };
  } catch (err: any) {
    return { nodes: {}, importable: false, error: err.message };
  }
}

const TEXT_NODE_TYPES = new Set([
  "CLIPTextEncode",
  "TextEncodeQwenImageEdit",
  "TextEncodeQwenImageEditPlus",
]);

export function detectPotentialBindings(nodes: Record<string, any>): Record<string, any> {
  const potentials: Record<string, any> = {};
  for (const [id, node] of Object.entries(nodes)) {
    if (!node || typeof node !== "object") continue;
    const type = String(node.class_type ?? "");
    if (type === "LoadImage") {
      potentials[id] = { type: "image", node_id: id, field: "image", label: `LoadImage (${id})` };
    } else if (type === "LoadImageMask") {
      potentials[id] = { type: "mask", node_id: id, field: "image", label: `LoadImageMask (${id})` };
    } else if (TEXT_NODE_TYPES.has(type)) {
      const inputs = (node as Record<string, unknown>).inputs as Record<string, unknown> | undefined;
      const textValue = inputs?.text;
      if (Array.isArray(textValue) && textValue.length === 2) {
        continue;
      }
      if (uiInputIsLinked((node as Record<string, unknown>)._meta as Record<string, unknown>, "text")) {
        continue;
      }
      potentials[id] = { type: "text", node_id: id, field: "text", label: `Prompt (${type} ${id})` };
    } else if (type === "KSampler" || type === "KSamplerAdvanced") {
      potentials[`${id}_seed`] = { type: "number", node_id: id, field: "seed", label: `Seed (${id})` };
      potentials[`${id}_steps`] = { type: "number", node_id: id, field: "steps", label: `Steps (${id})` };
      potentials[`${id}_cfg`] = { type: "number", node_id: id, field: "cfg", label: `CFG (${id})` };
    }
  }
  return potentials;
}
