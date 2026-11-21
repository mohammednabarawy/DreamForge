import { describe, expect, it } from "vitest";
import {
  formatRelativeTime,
  groupHistoryByDate,
  normalizeIsoTimestamp,
  parseHistoryTimestamp,
} from "./historyUtils";
import {
  hasFavoriteManifest,
  normalizeManifestKey,
  toggleFavoriteInSet,
} from "./historyStorage";
import type { OutputItem } from "./tauri-api";

function makeItem(overrides: Partial<OutputItem>): OutputItem {
  return {
    manifest_path: "/outputs/dreamforge/a.generation_manifest.json",
    timestamp: "2026-11-21T18:00:00+03:00",
    created_at: "2026-11-21T18:00:00+0300",
    session: "dreamforge",
    title: "gen_a",
    prompt: "studio hero shot",
    model_family: "sdxl",
    model_name: "model.safetensors",
    model_stem: "model",
    images: ["/outputs/dreamforge/a.png"],
    styles: [],
    ...overrides,
  };
}

describe("history timestamp normalization and grouping", () => {
  it("normalizes compact timezone offsets (+0300) for WKWebView/Safari safety", () => {
    expect(normalizeIsoTimestamp("2026-11-21T21:06:13+0300")).toBe(
      "2026-11-21T21:06:13+03:00",
    );
    expect(normalizeIsoTimestamp("2026-11-21 08:30:00-0500")).toBe(
      "2026-11-21T08:30:00-05:00",
    );
  });

  it("parses compact offset timestamps without returning NaN or 1970", () => {
    const item = makeItem({ created_at: "2026-11-21T21:06:13+0300" });
    const ms = parseHistoryTimestamp(item);
    expect(ms).toBe(Date.parse("2026-11-21T21:06:13+03:00"));
    expect(formatRelativeTime("2026-11-21T21:06:13+0300")).not.toContain("Invalid");
    expect(formatRelativeTime("not-a-date")).toBe("");
  });

  it("groups and sorts history items in both newest and oldest order", () => {
    const older = makeItem({
      manifest_path: "/outputs/dreamforge/older.generation_manifest.json",
      created_at: "2026-07-13T10:00:00+0300",
      timestamp: "2026-07-13T10:00:00+03:00",
    });
    const newer = makeItem({
      manifest_path: "/outputs/dreamforge/newer.generation_manifest.json",
      created_at: "2026-11-21T21:06:13+0300",
      timestamp: "2026-11-21T21:06:13+03:00",
    });

    const newestGroups = groupHistoryByDate([older, newer], "newest");
    expect(newestGroups.map((g) => g.items[0].manifest_path)).toEqual([
      newer.manifest_path,
      older.manifest_path,
    ]);

    const oldestGroups = groupHistoryByDate([older, newer], "oldest");
    expect(oldestGroups.map((g) => g.items[0].manifest_path)).toEqual([
      older.manifest_path,
      newer.manifest_path,
    ]);
  });

  it("matches favorites reliably across Windows slashes and drive casing", () => {
    const favs = new Set(["D:\\DreamForge\\outputs\\a.generation_manifest.json"]);
    expect(normalizeManifestKey("d:/DreamForge/outputs/a.generation_manifest.json")).toBe(
      normalizeManifestKey("D:\\DreamForge\\outputs\\a.generation_manifest.json"),
    );
    expect(
      hasFavoriteManifest(favs, "d:/DreamForge/outputs/a.generation_manifest.json"),
    ).toBe(true);
    const toggledOff = toggleFavoriteInSet(
      favs,
      "d:/DreamForge/outputs/a.generation_manifest.json",
    );
    expect(toggledOff.size).toBe(0);
  });
});
