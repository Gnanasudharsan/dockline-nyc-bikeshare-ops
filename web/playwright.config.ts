import { defineConfig, devices } from "@playwright/test";

/**
 * Two projects:
 * - e2e: behavior tests against a mocked API (no backend needed; runs in CI).
 * - screenshots: every page × light/dark × mobile (360 px)/desktop (1440 px) against the
 *   real local stack, saved to docs/design/screenshots/ for design review.
 */
const port = Number(process.env.PORT ?? 3010);

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: true,
  reporter: [["list"]],
  use: { baseURL: `http://localhost:${port}`, trace: "retain-on-failure" },
  projects: [
    { name: "e2e", testMatch: /.*\.e2e\.ts/, use: { ...devices["Desktop Chrome"] } },
    { name: "screenshots", testMatch: /screenshots\.ts/, use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: process.env.PLAYWRIGHT_NO_SERVER
    ? undefined
    : {
        command: `npm run start -- --port ${port}`,
        port,
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
