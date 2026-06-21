import type { OutputItem } from "./tauri-api";

export const HISTORY_PAGE_SIZE = 50;

export type HistoryDateGroup = {
  id: string;
  label: string;
  items: OutputItem[];
};

function startOfLocalDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

function itemTimestamp(item: OutputItem): number {
  const raw = item.created_at ?? item.timestamp;
  const ms = Date.parse(raw);
  return Number.isFinite(ms) ? ms : 0;
}

function dateGroupLabel(dayStart: number, todayStart: number): string {
  const dayMs = 86_400_000;
  if (dayStart === todayStart) return "Today";
  if (dayStart === todayStart - dayMs) return "Yesterday";
  if (dayStart >= todayStart - 6 * dayMs) {
    return new Date(dayStart).toLocaleDateString(undefined, { weekday: "long" });
  }
  return new Date(dayStart).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year:
      new Date(dayStart).getFullYear() !== new Date(todayStart).getFullYear()
        ? "numeric"
        : undefined,
  });
}

/** Flat list sorted newest-first, grouped by local calendar day. */
export function groupHistoryByDate(items: OutputItem[]): HistoryDateGroup[] {
  if (items.length === 0) return [];
  const todayStart = startOfLocalDay(new Date());
  const buckets = new Map<number, OutputItem[]>();
  const sorted = [...items].sort(
    (a, b) => itemTimestamp(b) - itemTimestamp(a),
  );
  for (const item of sorted) {
    const dayStart = startOfLocalDay(new Date(itemTimestamp(item)));
    const list = buckets.get(dayStart) ?? [];
    list.push(item);
    buckets.set(dayStart, list);
  }
  return [...buckets.entries()]
    .sort(([a], [b]) => b - a)
    .map(([dayStart, groupItems]) => ({
      id: String(dayStart),
      label: dateGroupLabel(dayStart, todayStart),
      items: groupItems,
    }));
}

export function formatRelativeTime(iso: string): string {
  const value = typeof iso === "string" ? iso : "";
  try {
    const d = new Date(value);
    const now = Date.now();
    const diff = now - d.getTime();
    const sec = Math.floor(diff / 1000);
    if (sec < 60) return "just now";
    const min = Math.floor(sec / 60);
    if (min < 60) return `${min}m ago`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr}h ago`;
    const day = Math.floor(hr / 24);
    if (day < 7) return `${day}d ago`;
    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  } catch {
    return value;
  }
}

export function excerptPrompt(prompt: string | undefined | null, max = 72): string {
  const t = (typeof prompt === "string" ? prompt : "").replace(/\s+/g, " ").trim();
  if (!t) return "";
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1)}…`;
}

export function modelBadgeLabel(stem: string, family: string): string {
  const s = stem?.trim();
  if (s && s !== "unknown") return s;
  const f = family?.trim();
  if (f && f !== "unknown") return f;
  return "model";
}
