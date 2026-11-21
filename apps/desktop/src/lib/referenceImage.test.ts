import { describe, expect, it } from "vitest";
import {
  clearImagePathDragSession,
  readImagePathFromDrop,
  setImagePathDragData,
} from "./referenceImage";

function makeDataTransfer(initial: Record<string, string> = {}): DataTransfer {
  const store = new Map<string, string>(
    Object.entries(initial).map(([k, v]) => [k.toLowerCase(), v]),
  );
  return {
    effectAllowed: "none",
    dropEffect: "none",
    get types() {
      return Array.from(store.keys());
    },
    files: [] as unknown as FileList,
    items: [] as unknown as DataTransferItemList,
    setData(type: string, data: string) {
      store.set(type.toLowerCase(), data);
    },
    getData(type: string) {
      return store.get(type.toLowerCase()) ?? "";
    },
    clearData() {
      store.clear();
    },
    setDragImage() {},
  } as unknown as DataTransfer;
}

describe("cross-platform dragged image path handling", () => {
  it("normalizes Windows file:// URIs to backslash drive paths", () => {
    clearImagePathDragSession();
    const dt = makeDataTransfer({
      "text/uri-list": "file:///C:/Users/Test%20User/Pictures/render.png",
    });
    expect(readImagePathFromDrop(dt)).toBe("C:\\Users\\Test User\\Pictures\\render.png");
  });

  it("preserves macOS/POSIX file:// URIs with forward slashes", () => {
    clearImagePathDragSession();
    const dt = makeDataTransfer({
      "text/uri-list": "file:///Users/medo/Desktop/My%20Render.png",
    });
    expect(readImagePathFromDrop(dt)).toBe("/Users/medo/Desktop/My Render.png");
  });

  it("encodes both Windows and macOS paths into text/uri-list", () => {
    const winDt = makeDataTransfer();
    setImagePathDragData(winDt, "D:\\DreamForge\\outputs\\out 1.png");
    expect(winDt.getData("text/uri-list")).toBe("file:///D:/DreamForge/outputs/out%201.png");

    const macDt = makeDataTransfer();
    setImagePathDragData(macDt, "/Users/medo/Desktop/DreamForge/outputs/out 1.png");
    expect(macDt.getData("text/uri-list")).toBe(
      "file:///Users/medo/Desktop/DreamForge/outputs/out%201.png",
    );
    clearImagePathDragSession();
  });
});
