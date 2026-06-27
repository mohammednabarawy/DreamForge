/**
 * Real UI smoke test for inpaint, extend/outpaint, and multi-result settings.
 * Requires DreamForge Tauri dev with WebView2 remote debugging on port 9222.
 *
 *   set WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9222
 *   cd apps/desktop && npm run tauri dev
 */
import { chromium } from "playwright";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const ASSETS = join(ROOT, "outputs", "smoke_ui");
const SOURCE = join(ASSETS, "source.png");
const MASK = join(ASSETS, "mask.png");
const CDP_URL = process.env.DREAMFORGE_CDP_URL ?? "http://127.0.0.1:9222";
const APP_URL = process.env.DREAMFORGE_APP_URL ?? "http://127.0.0.1:5173";

const results = [];

function pass(name, detail = "") {
  results.push({ name, ok: true, detail });
  console.log(`PASS  ${name}${detail ? ` — ${detail}` : ""}`);
}

function fail(name, detail = "") {
  results.push({ name, ok: false, detail });
  console.error(`FAIL  ${name}${detail ? ` — ${detail}` : ""}`);
}

async function waitForAppPage(browser, timeoutMs = 120_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    for (const context of browser.contexts()) {
      for (const page of context.pages()) {
        const url = page.url();
        if (url.includes("5173") || url.includes("localhost")) {
          return page;
        }
      }
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("Timed out waiting for DreamForge webview page");
}

async function tauriInvoke(page, command, args = {}) {
  return page.evaluate(
    async ({ command, args }) => {
      const tauri = window.__TAURI__;
      const invoke =
        tauri?.core?.invoke ??
        tauri?.invoke ??
        globalThis.__TAURI_INTERNALS__?.invoke;
      if (typeof invoke !== "function") {
        throw new Error("Tauri invoke unavailable — run via npm run tauri dev, not vite-only");
      }
      return invoke(command, args);
    },
    { command, args },
  );
}

async function dropImagePath(page, imagePath) {
  const ok = await page.evaluate((path) => {
    const candidates = [
      ...document.querySelectorAll("[title*='Attach a reference']"),
      ...document.querySelectorAll("[title*='Drop or pick']"),
    ];
    const el = candidates[0]?.closest(".relative") ?? candidates[0];
    if (!el) return false;
    const dt = new DataTransfer();
    dt.setData("application/x-dreamforge-image-path", path);
    dt.setData("text/plain", path);
    for (const type of ["dragenter", "dragover", "drop"]) {
      el.dispatchEvent(
        new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer: dt }),
      );
    }
    return true;
  }, imagePath);
  if (!ok) throw new Error("Could not find image drop target");
}

async function paintMaskStroke(page) {
  const canvas = page.locator("canvas").first();
  await canvas.waitFor({ state: "visible", timeout: 30_000 });
  const box = await canvas.boundingBox();
  if (!box) throw new Error("Mask canvas has no bounding box");
  const cx = box.x + box.width * 0.5;
  const cy = box.y + box.height * 0.5;
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  await page.mouse.move(cx + 40, cy + 20, { steps: 8 });
  await page.mouse.up();
}

/** Set a React-controlled <input> value so onChange actually fires. */
async function setReactInputValue(locator, value) {
  await locator.evaluate((el, value) => {
    const proto =
      el.tagName === "TEXTAREA"
        ? window.HTMLTextAreaElement.prototype
        : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
    setter?.call(el, String(value));
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }, value);
}

async function clickStudioMode(page, label) {
  const btn = page
    .locator(".df-command-route-row button")
    .filter({ hasText: new RegExp(`^${label}$`) })
    .first();
  await btn.waitFor({ state: "visible", timeout: 20_000 });
  await btn.click();
}

async function openInspectorGenerationTab(page) {
  const tab = page.locator('[data-tab-id="settings"]').first();
  if (await tab.isVisible().catch(() => false)) {
    await tab.click();
    return;
  }
  const fallback = page.getByRole("button", { name: "Generation", exact: true }).first();
  await fallback.waitFor({ state: "visible", timeout: 15_000 });
  await fallback.click();
}

async function main() {
  if (!existsSync(SOURCE) || !existsSync(MASK)) {
    throw new Error(`Missing smoke assets in ${ASSETS}`);
  }

  console.log(`Connecting CDP ${CDP_URL} ...`);
  const browser = await chromium.connectOverCDP(CDP_URL);
  const page = await waitForAppPage(browser);
  await page.bringToFront();
  await page.waitForLoadState("domcontentloaded");

  const onSetup = await page.getByText("DreamForge Setup", { exact: false }).isVisible().catch(() => false);
  if (onSetup) {
    fail("setup-gate", "Setup wizard is blocking the studio UI");
  } else {
    pass("setup-gate", "Studio shell reachable");
  }

  // --- Multi-result (first — avoid extend edit_task polluting generate) ---
  try {
    await clickStudioMode(page, "Generate");
    await page.waitForTimeout(2500);
    await page.locator('[data-tab-id="models"]').first().click();
    await page.waitForTimeout(1200);
    const modelTile = page
      .locator('button.df-gallery-tile[title*="schnell" i]')
      .first();
    if (await modelTile.isVisible({ timeout: 10_000 }).catch(() => false)) {
      await modelTile.click();
      await page.waitForTimeout(2500);
    }
    await openInspectorGenerationTab(page);
    await page.getByText(/Image number/i).first().waitFor({ timeout: 15_000 });
    const ranges = page.locator('label:has-text("Image number") input[type="range"]');
    await setReactInputValue(ranges.first(), 3);
    pass("multi-result-ui", "Image number control present (set to 3)");

    const sliderVal = await ranges.first().inputValue();
    if (Number(sliderVal) === 3) {
      pass("multi-result-dry-run", "Image number slider reflects React state = 3");
    } else {
      fail("multi-result-dry-run", `Expected slider value 3, got ${sliderVal}`);
    }

    const generateBtn = page
      .locator("button.bg-gradient-to-r")
      .filter({ hasText: /^Generate$/ })
      .first();
    for (let i = 0; i < 60 && !(await generateBtn.isEnabled().catch(() => false)); i++) {
      const title = (await generateBtn.getAttribute("title").catch(() => "")) ?? "";
      const restart = page.getByRole("button", { name: /Restart GPU engine/i }).first();
      if (
        /restart gpu engine/i.test(title) ||
        (await restart.isVisible().catch(() => false))
      ) {
        await restart.click().catch(() => {});
        await page.waitForTimeout(5000);
        continue;
      }
      await page.waitForTimeout(2000);
    }
    if (await generateBtn.isEnabled().catch(() => false)) {
      await setReactInputValue(ranges.first(), 2);
      await page.waitForTimeout(500);
      const sliderVal2 = await ranges.first().inputValue();
      if (Number(sliderVal2) !== 2) {
        fail("multi-result-tray", `Slider did not stick at 2 before generate (got ${sliderVal2})`);
      } else {
      await page.locator("textarea").first().fill("smoke: a single red sphere on white background");
      await generateBtn.click();
      const trayVisible = await page
        .getByRole("region", { name: "Generation candidates" })
        .waitFor({ state: "visible", timeout: 480_000 })
        .then(() => true)
        .catch(() => false);
      if (trayVisible) {
        const trayText = await page
          .getByRole("region", { name: "Generation candidates" })
          .innerText();
        pass("multi-result-tray", `Result tray visible: ${trayText.split("\n")[0]}`);
      } else {
        fail("multi-result-tray", "Generation finished without multi-candidate tray within 480s");
      }
      }
    } else {
      fail("multi-result-tray", "Generate stayed disabled — pick a model and ensure GPU engine is ready");
    }
  } catch (err) {
    fail("multi-result-flow", err instanceof Error ? err.message : String(err));
  }

  // --- Inpaint flow ---
  try {
    await clickStudioMode(page, "Inpaint");
    await openInspectorGenerationTab(page);
    await page.getByText("Flux Fill inpaint", { exact: true }).first().waitFor({ timeout: 15_000 });
    pass("inpaint-mode", "Inpaint settings panel visible");

    await page
      .locator('p:text-is("Edit task")')
      .locator("xpath=..")
      .getByRole("button", { name: "Replace", exact: true })
      .click();
    await dropImagePath(page, SOURCE);
    await page.waitForTimeout(1200);
    pass("inpaint-source", "Source image attached via path drop");

    await paintMaskStroke(page);
    await page.waitForTimeout(2500);

    const planHasMask = await page
      .getByText(/mask coverage|Mask coverage/i)
      .first()
      .isVisible({ timeout: 25_000 })
      .catch(() => false);
    if (planHasMask) {
      pass("inpaint-dry-run", "Workflow plan shows mask coverage after auto dry-run");
    } else {
      const dry = await tauriInvoke(page, "dry_run", {
        params: {
          model: "flux-fill-dev.safetensors",
          prompt: "replace the marked area with a red ball",
          input_image: SOURCE,
          inpaint_mask_path: MASK,
          edit_type: "inpaint",
          cn_type: "inpaint",
          edit_task: "replace",
          image_number: 1,
          json: true,
        },
      });
      const plan = dry?.plan ?? dry;
      const ctx = plan?.inpaint_context;
      if (ctx && ctx.mask_empty === false) {
        pass("inpaint-dry-run", `Tauri dry_run mask_empty=false (coverage=${ctx.mask_coverage})`);
      } else {
        fail("inpaint-dry-run", "Neither workflow plan nor Tauri dry_run confirmed inpaint context");
      }
    }
  } catch (err) {
    fail("inpaint-flow", err instanceof Error ? err.message : String(err));
  }

  // --- Extend / outpaint flow ---
  try {
    await clickStudioMode(page, "Inpaint");
    await openInspectorGenerationTab(page);
    await page.getByRole("button", { name: "Extend", exact: true }).click();
    await page.getByText("Canvas extend").waitFor({ timeout: 10_000 });
    await page.getByRole("button", { name: "left", exact: true }).click();
    pass("extend-ui", "Extend task controls visible");

    await dropImagePath(page, SOURCE);
    await page.waitForTimeout(1500);

    const outpaintPlan = await page
      .getByText(/outpaint|Extend left/i)
      .first()
      .isVisible({ timeout: 20_000 })
      .catch(() => false);
    if (outpaintPlan) {
      pass("extend-dry-run", "Workflow plan shows outpaint context");
    } else {
      const dry = await tauriInvoke(page, "dry_run", {
        params: {
          model: "flux-fill-dev.safetensors",
          prompt: "extend the scene",
          input_image: SOURCE,
          edit_task: "extend",
          edit_type: "outpaint",
          cn_type: "outpaint",
          outpaint_direction: "left",
          outpaint_amount: 256,
          outpaint_feathering: 40,
          image_number: 1,
          json: true,
        },
      });
      const plan = dry?.plan ?? dry;
      const status = plan?.inpaint_context?.status;
      if (status === "outpaint") {
        pass("extend-dry-run", `Tauri dry_run status=outpaint dir=${plan.inpaint_context.outpaint?.direction}`);
      } else {
        fail("extend-dry-run", `Expected outpaint plan, got status=${status ?? "missing"}`);
      }
    }
  } catch (err) {
    fail("extend-flow", err instanceof Error ? err.message : String(err));
  }

  const failed = results.filter((r) => !r.ok);
  console.log("\n--- Smoke summary ---");
  console.log(`Total: ${results.length}  Passed: ${results.length - failed.length}  Failed: ${failed.length}`);
  if (failed.length) {
    for (const item of failed) {
      console.error(`  x ${item.name}: ${item.detail}`);
    }
    await browser.close().catch(() => {});
    process.exit(1);
  }
  await browser.close().catch(() => {});
}

main().catch(async (err) => {
  console.error(err);
  process.exit(1);
});
