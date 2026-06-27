/** Timed single-image txt2img to verify boot fix + speed after VRAM flag change. */
import { chromium } from "playwright";

const CDP = process.env.DREAMFORGE_CDP_URL ?? "http://127.0.0.1:9333";

async function main() {
  const browser = await chromium.connectOverCDP(CDP);
  const page = browser
    .contexts()[0]
    .pages()
    .find((p) => p.url().includes("5173"));
  if (!page) throw new Error("DreamForge page not found");

  await page.locator(".df-command-route-row button").filter({ hasText: /^Generate$/ }).first().click();
  await page.waitForTimeout(3000);
  await page.locator('[data-tab-id="models"]').first().click().catch(() => {});
  await page.waitForTimeout(1200);
  const schnell = page.locator('button.df-gallery-tile[title*="schnell" i]').first();
  if (await schnell.isVisible({ timeout: 8000 }).catch(() => false)) {
    await schnell.click();
    console.log("picked schnell checkpoint:", await schnell.getAttribute("title"));
    await page.waitForTimeout(2500);
  } else {
    console.log("WARNING: schnell tile not found, using current model");
  }
  const clear = page.getByTitle("Remove attached image").first();
  if (await clear.isVisible().catch(() => false)) await clear.click();

  const tab = page.locator('[data-tab-id="settings"]').first();
  if (await tab.isVisible().catch(() => false)) await tab.click();

  await page.locator("textarea").first().fill("a red cube on a white background, studio product photo");

  const btn = page
    .locator("button.bg-gradient-to-r")
    .filter({ hasText: /^Generate$/ })
    .first();
  for (let i = 0; i < 40 && !(await btn.isEnabled().catch(() => false)); i++) {
    await page.waitForTimeout(1500);
  }
  if (!(await btn.isEnabled().catch(() => false))) {
    throw new Error("Generate button never enabled");
  }

  const t0 = Date.now();
  console.log("clicking Generate…");
  await btn.click();

  let done = false;
  let failed = "";
  for (let i = 0; i < 200; i++) {
    const body = await page.locator("body").innerText();
    if (/Generation complete/i.test(body)) {
      done = true;
      break;
    }
    if (/virtual memory|FAILED|Start failed|did not finish/i.test(body)) {
      failed = (body.match(/(virtual memory[^\n]*|Start failed[^\n]*|did not finish[^\n]*)/i) || [])[0] ?? "failed";
      break;
    }
    await page.waitForTimeout(1500);
  }
  const secs = Math.round((Date.now() - t0) / 1000);
  console.log(`completed=${done} failed=${failed || "no"} elapsed_s=${secs}`);
  await browser.close();
  process.exit(done ? 0 : 3);
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : err);
  process.exit(1);
});
