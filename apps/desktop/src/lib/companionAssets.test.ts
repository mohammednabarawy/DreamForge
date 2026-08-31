import { describe, expect, it } from "vitest";
import { mergeAllCompanionMissing, workflowModelItemFromCatalogId } from "./companionAssets";
import { describeError } from "./errors";
import { computeGenerateReadiness } from "./generationReadiness";
import { computePlanSettingsSnapshot } from "./workflowPlanActions";
import type { GenerationSettings } from "./tauri-api";

const flux = workflowModelItemFromCatalogId("flux_kontext_unet");
const settings = {
  model: "[diffusion_models] flux1-dev-kontext_fp8_scaled.safetensors",
  prompt: "Change the shirt to blue", input_image: "source.png",
} as GenerationSettings;
const snapshot = computePlanSettingsSnapshot(settings, "edit");
const checks = {
  modelMissing: [], studioMissing: [], taskWorkflowMissing: [],
  settingsSnapshot: snapshot,
  agentPlan: { settings_snapshot: snapshot, readiness: { ready: false,
    recommended_actions: [{ action: "download_model_companions", catalog_ids: ["flux_kontext_unet"] }] } },
};

describe("current companion readiness", () => {
  it.each(["krea2TurboFP8_krea2TURBO.safetensors", "Krea2_Turbo_convrot_int8mixed.safetensors"])(
    "does not block %s with a previous Flux plan", (filename) => {
      const current = { ...settings, model: `[diffusion_models] ${filename}` };
      const missing = mergeAllCompanionMissing({ ...checks,
        settingsSnapshot: computePlanSettingsSnapshot(current, "edit") });
      expect(missing).toEqual([]);
      expect(computeGenerateReadiness({
        workerReady: true, generating: false, engineState: "ready", engineLabel: "Ready",
        prompt: current.prompt!, model: current.model!, modelDependenciesReady: true,
        missingCompanionCount: missing.length, settings: current, studioMode: "edit",
        editPlanState: "stale",
      }).ok).toBe(true);
    },
  );
  it("keeps current plan assets and real model, studio, and Toolbox dependencies", () => {
    expect(mergeAllCompanionMissing(checks)).toEqual([flux]);
    expect(mergeAllCompanionMissing({ ...checks, settingsSnapshot: "different-mode", modelMissing: [flux] })).toEqual([flux]);
    expect(mergeAllCompanionMissing({ ...checks, settingsSnapshot: "different-mode", studioMissing: [flux] })).toEqual([flux]);
    expect(mergeAllCompanionMissing({ ...checks, settingsSnapshot: "different-mode", taskWorkflowMissing: [flux] })).toEqual([flux]);
    expect(mergeAllCompanionMissing({ ...checks, settingsSnapshot: "different-mode",
      skipBaseModelCompanions: true, customToolWorkflowMissing: [flux] })).toEqual([flux]);
  });
  it("keeps worker repair details but does not recycle a readiness error after a successful check", () => {
    const lastError = describeError({ code: "missing_model_dependencies", message: "Missing 1 companion file(s)",
      details: { missing: [flux], model: settings.model, studio_mode: "edit", source: "readiness" } });
    expect(lastError.details?.missing).toEqual([flux]);
    expect(mergeAllCompanionMissing({ ...checks, agentPlan: null, lastError })).toEqual([]);
    expect(mergeAllCompanionMissing({ ...checks, agentPlan: null,
      lastError: { ...lastError, details: { missing: [flux] } } })).toEqual([flux]);
  });
});
