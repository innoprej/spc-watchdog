/** Record deterministic replay footage without adding Playwright to the app. */

const path = require("node:path");
const { chromium } = require("playwright");

async function main() {
  const [url, scenario, outputDirectory] = process.argv.slice(2);
  if (!url || !scenario || !outputDirectory) {
    throw new Error("usage: node capture_demo_footage.cjs URL SCENARIO OUTPUT_DIRECTORY");
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: {
      dir: path.resolve(outputDirectory),
      size: { width: 1920, height: 1080 },
    },
  });
  const page = await context.newPage();
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);

  if (scenario === "scenario-1") {
    await page.getByRole("heading", { name: "Verified conclusion" }).waitFor({
      timeout: 100_000,
    });
    await page.waitForTimeout(6000);
  } else if (scenario === "scenario-2") {
    const approve = page.getByRole("button", { name: "APPROVE & ACTIVATE V2" });
    await approve.waitFor({ timeout: 110_000 });
    await page.waitForTimeout(4000);
    await approve.scrollIntoViewIfNeeded();
    await page.waitForTimeout(2500);
    await approve.click();
    await page.getByText("OCAP v2 active — next investigation starts smarter").waitFor({
      timeout: 15_000,
    });
    await page.waitForTimeout(3000);
    await page.getByRole("heading", { name: "Verified conclusion" }).waitFor({
      timeout: 75_000,
    });
    await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }));
    await page.waitForTimeout(6000);
  } else {
    throw new Error(`unsupported scenario: ${scenario}`);
  }

  await context.close();
  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
