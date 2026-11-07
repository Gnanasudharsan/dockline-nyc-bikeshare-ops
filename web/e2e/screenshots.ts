import { test } from "@playwright/test";
import path from "node:path";

// Real local stack (API on :8070). Output: docs/design/screenshots/<page>-<theme>-<size>.png
const OUT = path.resolve(__dirname, "../../docs/design/screenshots");
const PAGES = [
  ["home", "/"],
  ["live", "/live"],
  ["ask", "/ask"],
  ["insights", "/insights"],
  ["how-it-works", "/how-it-works"],
  ["about", "/about"],
] as const;
const SIZES = [
  ["mobile", 360, 780],
  ["desktop", 1440, 900],
] as const;

for (const [name, url] of PAGES) {
  for (const theme of ["light", "dark"] as const) {
    for (const [size, width, height] of SIZES) {
      test(`${name} ${theme} ${size}`, async ({ page }) => {
        await page.setViewportSize({ width, height });
        await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
        await page.goto(url);
        await page.waitForLoadState("networkidle").catch(() => undefined);
        await page.waitForTimeout(name === "home" || name === "live" ? 6000 : 2500);
        await page.screenshot({
          path: `${OUT}/${name}-${theme}-${size}.png`,
          // Full-page capture stretches the viewport, which resizes the WebGL map mid-render.
          fullPage: name !== "home",
        });
      });
    }
  }
}
