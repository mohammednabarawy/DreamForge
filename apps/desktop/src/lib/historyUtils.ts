import type { OutputItem } from "./tauri-api";

export const HISTORY_PAGE_SIZE = 50;

export type HistorySortOrder = "newest" | "oldest";

export type HistoryDateGroup = {
  id: string;
  label: string;
  items: OutputItem[];
};

/**
 * Normalize ISO-8601 strings for WebKit/WKWebView & V8 compatibility.
 * Specifically converts compact offsets like `+0300` into `+03:00` so Safari/WKWebView
 * does not return NaN from `Date.parse()`.
 */
export function normalizeIsoTimestamp(raw: string | undefined | null): string {
  if (typeof raw !== "string") return "";
  let text = raw.trim();
  if (!text) return "";
  if (text.includes(" ") && !text.includes("T")) {
    text = text.replace(" ", "T");
  }
  text = text.replace(/([+-]\d{2})(\d{2})$/, "$1:$2");
  return text;
}

export function parseIsoTimestampMs(raw: string | undefined | null): number | null {
  const normalized = normalizeIsoTimestamp(raw);
  if (!normalized) return null;
  const ms = Date.parse(normalized);
  return Number.isFinite(ms) ? ms : null;
}

export function parseHistoryTimestamp(item: Pick<OutputItem, "created_at" | "timestamp">): number {
  return (
    parseIsoTimestampMs(item.created_at) ??
    parseIsoTimestampMs(item.timestamp) ??
    0
  );
}

function startOfLocalDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

function dateGroupLabel(dayStart: number, todayStart: number): string {
  if (!Number.isFinite(dayStart) || dayStart <= 0) return "Earlier";
  const dayMs = 86_400_000;
  if (dayStart === todayStart) return "Today";
  if (dayStart === todayStart - dayMs) return "Yesterday";
  if (dayStart >= todayStart - 6 * dayMs && dayStart < todayStart) {
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

/** Flat list sorted by timestamp, grouped by local calendar day. */
export function groupHistoryByDate(
  items: OutputItem[],
  sortOrder: HistorySortOrder = "newest",
): HistoryDateGroup[] {
  if (items.length === 0) return [];
  const todayStart = startOfLocalDay(new Date());
  const buckets = new Map<number, OutputItem[]>();
  const dir = sortOrder === "oldest" ? 1 : -1;
  const sorted = [...items].sort(
    (a, b) => (parseHistoryTimestamp(a) - parseHistoryTimestamp(b)) * dir,
  );
  for (const item of sorted) {
    const ts = parseHistoryTimestamp(item);
    const dayStart = ts > 0 ? startOfLocalDay(new Date(ts)) : 0;
    const list = buckets.get(dayStart) ?? [];
    list.push(item);
    buckets.set(dayStart, list);
  }
  return [...buckets.entries()]
    .sort(([a], [b]) => (a - b) * dir)
    .map(([dayStart, groupItems]) => ({
      id: String(dayStart),
      label: dateGroupLabel(dayStart, todayStart),
      items: groupItems,
    }));
}

export function formatRelativeTime(iso: string | undefined | null): string {
  const ms = parseIsoTimestampMs(iso);
  if (ms === null) return "";
  const now = Date.now();
  const diff = now - ms;
  if (diff < 60_000) return "just now";
  const min = Math.floor(diff / 60_000);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d ago`;
  return new Date(ms).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export function formatExactDateTime(iso: string | undefined | null): string {
  const ms = parseIsoTimestampMs(iso);
  if (ms === null) return "";
  return new Date(ms).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
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
