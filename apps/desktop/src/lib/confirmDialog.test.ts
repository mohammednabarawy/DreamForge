import { describe, expect, it } from "vitest";
import {
  requestConfirm,
  resolveConfirmDialog,
  subscribeConfirmDialog,
} from "./confirmDialog";

describe("in-app confirm dialog queue", () => {
  it("resolves confirm and cancel decisions cleanly in FIFO order without window.confirm", async () => {
    const seen: Array<{ id: number; title: string } | null> = [];
    const unsubscribe = subscribeConfirmDialog((pending) => {
      seen.push(pending ? { id: pending.id, title: pending.title } : null);
    });

    const first = requestConfirm({
      title: "Delete generation?",
      message: "Delete item A",
      destructive: true,
    });
    const second = requestConfirm({
      title: "Delete project?",
      message: "Delete project B",
      destructive: true,
    });

    const firstActive = seen.at(-1);
    expect(firstActive?.title).toBe("Delete generation?");
    resolveConfirmDialog(firstActive!.id, true);
    await expect(first).resolves.toBe(true);

    const secondActive = seen.at(-1);
    expect(secondActive?.title).toBe("Delete project?");
    resolveConfirmDialog(secondActive!.id, false);
    await expect(second).resolves.toBe(false);

    expect(seen.at(-1)).toBeNull();
    unsubscribe();
  });
});
