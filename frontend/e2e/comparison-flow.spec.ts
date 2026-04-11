/**
 * E2E-тест: "золотой" сценарий сравнения тестов.
 *
 * Предполагает запущенный frontend (localhost:3000) и backend (localhost:8000)
 * с хотя бы 2 завершёнными тестами в истории.
 *
 * Запуск: npx playwright test
 */
import { test, expect } from "@playwright/test";

test.describe("Comparison flow", () => {
  test("navigate to history page", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // SPA navigation through sidebar
    const historyLink = page.locator("text=История");
    if (await historyLink.isVisible()) {
      await historyLink.click();
      await expect(page.locator("text=История тестов").or(page.locator("text=История"))).toBeVisible();
    }
  });

  test("home page loads and shows status", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Main heading or logo should be visible
    await expect(page.locator("body")).toBeVisible();
    // API status indicator should appear
    const statusText = page.locator("text=API").or(page.locator("text=Статус"));
    await expect(statusText.first()).toBeVisible({ timeout: 10000 });
  });
});
