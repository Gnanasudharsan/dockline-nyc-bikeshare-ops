import { expect, test } from "@playwright/test";
import { mockApi } from "./fixtures";

test("home shows the live sentence and KPI strip", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "stations have no bikes to rent",
  );
  await expect(page.getByText("Bikes available")).toBeVisible();
  await expect(page.getByRole("list", { name: "Map legend" }).first()).toContainText("Starving");
  await expect(page.getByText("Not affiliated with Citi Bike or Lyft")).toBeVisible();
});

test("ask shows the answer, the numbers, and the metric definition", async ({ page }) => {
  await mockApi(page);
  await page.goto("/ask");
  await page.getByLabel("Your question").fill("How many stations have no bikes right now?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByRole("article", { name: "Answer" })).toContainText(
    "142 stations have no bikes",
  );
  await expect(page.getByText("In-service stations with no bike to rent right now.")).toBeVisible();
  await page.getByText("Show the query").click();
  await expect(page.getByText('"empty_stations"').first()).toBeVisible();
});

test("ask explains a refusal and offers a question it can answer", async ({ page }) => {
  await mockApi(page, {
    ask: {
      question: "How many trips were taken yesterday?",
      status: "refused",
      answer: "Dockline can't answer that from its certified metrics.",
      metrics: [],
      query: null,
      rows: [],
      data_freshness_seconds: null,
      suggestion: "What was the availability rate yesterday?",
      answer_source: "none",
      elapsed_ms: 800,
    },
  });
  await page.goto("/ask");
  await page.getByLabel("Your question").fill("How many trips were taken yesterday?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(
    page.getByRole("button", { name: /Ask instead: What was the availability rate yesterday/ }),
  ).toBeVisible();
});

test("ask shows rate-limit errors in plain words", async ({ page }) => {
  await mockApi(page, {
    askStatus: 429,
    ask: { detail: "Too many questions. Wait 30 seconds and try again." },
  });
  await page.goto("/ask");
  await page.getByLabel("Your question").fill("How many bikes?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  // Next.js also renders a role="alert" route announcer, so target the message itself.
  await expect(page.locator("p[role=alert]")).toHaveText(
    "Too many questions. Wait 30 seconds and try again.",
  );
});

test("theme toggle switches to dark and back", async ({ page }) => {
  await mockApi(page);
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/about");
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

test("every page has one h1, a main landmark, and a skip link", async ({ page }) => {
  await mockApi(page);
  for (const path of ["/", "/live", "/ask", "/insights", "/how-it-works", "/about"]) {
    await page.goto(path);
    await expect(page.locator("h1")).toHaveCount(1);
    await expect(page.locator("main#main")).toHaveCount(1);
    await expect(page.getByRole("link", { name: "Skip to content" })).toHaveCount(1);
  }
});
