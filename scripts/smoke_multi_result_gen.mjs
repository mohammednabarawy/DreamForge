/**
 * Supplemental smoke: live multi-image generation + result tray.
 * Uses a low-VRAM streaming profile to stay under the Windows commit limit.
 * Requires DreamForge Tauri dev with WebView2 remote debugging.
 */
import { chromium } from "playwright";

const CDP = process.env.DREAMFORGE_CDP_URL ?? "http://127.0.0.1:9333";
const VRAM = process.env.DREAMFORGE_SMOKE_VRAM ?? "8gb";
const IMAGES = Number(process.env.DREAMFORGE_SMOKE_IMAGES ?? 2);

async function setReactValue(locator, value) {
  await locator.evaluate((el, value) => {
    const proto =
      el.tagName === "SELECT"
        ? window.HTMLSelectElement.prototype
        : el.tagName === "TEXTAREA"
          ? window.HTMLTextAreaElement.prototype
          : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
    setter?.call(el, String(value));
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }, value);
}

async function openGenerationTab(page) {
  const tab = page.locator('[data-tab-id="settings"]').first();
  if (await tab.isVisible().catch(() => false)) return tab.click();
  return page.getByRole("button", { name: "Generation", exact: true }).first().click();
}

async function waitGenerateEnabled(page, attempts = 60) {
  const btn = page
    .locator("button.bg-gradient-to-r")
    .filter({ hasText: /^Generate$/ })
    .first();
  for (let i = 0; i < attempts; i++) {
    if (await btn.isEnabled().catch(() => false)) return btn;
    await page.waitForTimeout(2000);
  }
  throw new Error("GPU engine never became ready");
}

async function main() {
  const browser = await chromium.connectOverCDP(CDP);
  const page = browser
    .contexts()[0]
    .pages()
    .find((p) => p.url().includes("5173"));
  if (!page) throw new Error("DreamForge page not found");

  await page.locator(".df-command-route-row button").filter({ hasText: /^Generate$/ }).first().click();

  // Pick a small fast checkpoint — avoids 11 GB Fill/Ideogram commit spikes on batch jobs.
  await page.locator('[data-tab-id="models"]').first().click().catch(() => {});
  const schnell = page.getByRole("button").filter({ hasText: /schnell/i }).first();
  if (await schnell.isVisible({ timeout: 12_000 }).catch(() => false)) {
    await schnell.click();
    await page.waitForTimeout(600);
    console.log("Selected flux1-schnell checkpoint");
  }

  await openGenerationTab(page);

  // Clear any stale source image so this is a pure txt2img job.
  const clearImage = page.getByTitle("Remove attached image").first();
  if (await clearImage.isVisible().catch(() => false)) {
    await clearImage.click();
    await page.waitForTimeout(400);
  }

  // Low-VRAM streaming profile keeps model weights off the commit charge.
  const vramSelect = page.locator('select').filter({ hasText: /VRAM/ }).first();
  if (await vramSelect.isVisible().catch(() => false)) {
    await setReactValue(vramSelect, VRAM);
    console.log(`Set VRAM profile = ${VRAM}`);
  }

  // Restart engine so the new profile is applied with a freshly released model.
  const restart = page.getByRole("button", { name: /Restart GPU engine/i }).first();
  if (await restart.isVisible().catch(() => false)) {
    await restart.click().catch(() => {});
    await page.waitForTimeout(3000);
  }
  await waitGenerateEnabled(page);

  await openGenerationTab(page);
  const slider = page.locator('label:has-text("Image number") input[type="range"]').first();
  await slider.waitFor({ state: "visible", timeout: 20_000 });
  await setReactValue(slider, IMAGES);
  await page.locator("textarea").first().fill("smoke test: a single red sphere on white background");

  const generateBtn = await waitGenerateEnabled(page);
  console.log(`Starting ${IMAGES}-image txt2img job (vram=${VRAM})…`);
  await generateBtn.click();

  const tray = page.getByRole("region", { name: "Generation candidates" });
  await tray.waitFor({ state: "visible", timeout: 300_000 });
  const label = (await tray.innerText()).split("\n")[0];
  console.log(`PASS multi-result-tray-live — ${label}`);
  await browser.close();
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : err);
  process.exit(1);
});
