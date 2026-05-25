import type { OutputItem } from "./tauri-api";

export const DEFAULT_SESSION_ID = "dreamforge";

export type OutputSession = {
  id: string;
  label: string;
  items: OutputItem[];
  latest: string;
};

export type SessionMeta = {
  id: string;
  label: string;
};

const RESERVED_SESSION_IDS = new Set(["root", "unsorted", "eval"]);

/** Folder-safe session id under outputs/{id}/ */
export function sanitizeSessionId(name: string): string {
  const slug = name
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/[^a-z0-9_-]+/g, "")
    .replace(/_+/g, "_")
    .replace(/^[-_]+|[-_]+$/g, "")
    .slice(0, 48);
  if (!slug || RESERVED_SESSION_IDS.has(slug)) return "";
  return slug;
}

export function uniqueSessionId(base: string, taken: Set<string>): string {
  let id = base;
  let n = 2;
  while (taken.has(id)) {
    id = `${base}_${n}`;
    n += 1;
  }
  return id;
}

function outputStamp() {
  return new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
}

export function outputPathForSession(
  sessionId: string,
  kind: "gen" | "edit" | "inpaint" | "upscale" = "gen",
): string {
  const stamp = outputStamp();
  const folder = sessionId === "root" ? "outputs" : `outputs/${sessionId || DEFAULT_SESSION_ID}`;
  const name =
    kind === "gen" ? `gen_${stamp}.png` : `${kind}_${stamp}.png`;
  return `${folder}/${name}`;
}

export function groupOutputsBySession(outputs: OutputItem[]): OutputSession[] {
  const map = new Map<string, OutputItem[]>();
  for (const item of outputs) {
    const key = item.session || "unsorted";
    const list = map.get(key) ?? [];
    list.push(item);
    map.set(key, list);
  }

  const sessions: OutputSession[] = [];
  for (const [id, items] of map) {
    items.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
    sessions.push({
      id,
      label: formatSessionLabel(id),
      items,
      latest: items[0]?.timestamp ?? "",
    });
  }

  return sessions.sort((a, b) => b.latest.localeCompare(a.latest));
}

/** Merge disk sessions, empty user-created sessions, and ensure the active id is listed. */
export function mergeSessionList(
  fromOutputs: OutputSession[],
  registry: SessionMeta[],
  activeId: string,
): OutputSession[] {
  const map = new Map<string, OutputSession>();
  for (const s of fromOutputs) {
    map.set(s.id, s);
  }
  for (const meta of registry) {
    if (!map.has(meta.id)) {
      map.set(meta.id, {
        id: meta.id,
        label: meta.label || formatSessionLabel(meta.id),
        items: [],
        latest: "",
      });
    }
  }
  const active = activeId.trim() || DEFAULT_SESSION_ID;
  if (!map.has(active)) {
    map.set(active, {
      id: active,
      label: formatSessionLabel(active),
      items: [],
      latest: "",
    });
  }

  const list = [...map.values()];
  list.sort((a, b) => {
    if (a.id === active) return -1;
    if (b.id === active) return 1;
    const byLatest = b.latest.localeCompare(a.latest);
    if (byLatest !== 0) return byLatest;
    return a.label.localeCompare(b.label);
  });
  return list;
}

export function collectSessionImagePaths(session: OutputSession | undefined): string[] {
  if (!session) return [];
  const paths: string[] = [];
  for (const item of session.items) {
    for (const p of item.images) {
      if (p && !paths.includes(p)) paths.push(p);
    }
  }
  return paths;
}

function formatSessionLabel(id: string): string {
  if (id === "root") return "Outputs (root)";
  if (id === "unsorted") return "Unsorted";
  if (id === "eval") return "Eval runs";
  if (id === "mission_control" || id === "dreamforge") return "DreamForge";
  return id.replace(/_/g, " ");
}
