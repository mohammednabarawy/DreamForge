import { describe, expect, it } from "vitest";
import { engineBootFailureError } from "./errors";

describe("GPU boot diagnostics", () => {
  it("keeps the boot cause when stderr contains only a warning and source line", () => {
    const warning = "D:/DreamForge/backend/dreamforge_comfy_launch.py:152: UserWarning: expandable_segments not supported on this platform\n  q = torch.arange(4096, device=device)";
    const cause = "GPU worker did not become ready in time.";
    const error = engineBootFailureError(cause, warning);
    expect(error.message).toBe(cause);
    expect(error.details?.worker_log_tail).toBe(warning);
    expect(engineBootFailureError(undefined, warning).message).not.toContain("torch.arange");
    expect(engineBootFailureError(cause, warning + "\nRuntimeError: CUDA out of memory").message)
      .toBe("RuntimeError: CUDA out of memory");
  });
});
