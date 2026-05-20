/**
 * E2E: навигация SPA и загрузка главной страницы.
 *
 * Frontend поднимается через webServer в playwright.config.ts.
 * Backend не обязателен для этих сценариев.
 */
import { test, expect } from "@playwright/test";

async function openSidebar(page: import("@playwright/test").Page) {
  const menuButton = page.locator("header button").first();
  await expect(menuButton).toBeVisible();
  await menuButton.click();
  await expect(page.getByRole("button", { name: "История тестов" })).toBeVisible();
}

test.describe("Comparison flow", () => {
  test("navigate to history page", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    await openSidebar(page);
    await page.getByRole("button", { name: "История тестов" }).click();

    await expect(page.getByRole("heading", { name: "История тестов" })).toBeVisible();
  });

  test("home page loads and shows welcome", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    await expect(page.locator("body")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /Добро пожаловать в/i }),
    ).toBeVisible();
    await expect(page.getByText("TestBDBench").first()).toBeVisible();
  });
});
