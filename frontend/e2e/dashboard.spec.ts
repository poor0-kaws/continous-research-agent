import { expect, test } from "@playwright/test";

test("shows the guarded research workspace", async ({ page }) => {
  await page.route("**/api/topics", async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.goto("/");

  await expect(page.getByText("ContResAI")).toBeVisible();
  await expect(page.getByText("Guarded browsing")).toBeVisible();
  await expect(page.getByText("No confirmed knowledge yet")).toBeVisible();
});
