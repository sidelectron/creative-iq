import { test, expect } from "@playwright/test";

test.describe("Phase 8 smoke", () => {
  test("login page renders", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /Sign in/i })).toBeVisible();
  });

  test("register page renders", async ({ page }) => {
    await page.goto("/register");
    await expect(page.getByRole("heading", { name: /Create account/i })).toBeVisible();
  });
});

test.describe("Phase 8 journey (mocked API)", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      sessionStorage.setItem("ci_access_token", "e2e-test-token");
      sessionStorage.setItem("ci_refresh_token", "e2e-refresh-token");
      sessionStorage.setItem(
        "ci_selected_brand_id",
        "00000000-0000-0000-0000-000000000099",
      );
    });

    await page.route("**/api/v1/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "00000000-0000-0000-0000-000000000001",
          email: "e2e@test.com",
          full_name: "E2E User",
          is_active: true,
        }),
      });
    });

    await page.route("**/api/v1/brands?*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              id: "00000000-0000-0000-0000-000000000099",
              name: "E2E Brand",
              industry: "beauty",
              created_at: new Date().toISOString(),
              role: "admin",
            },
          ],
          total: 1,
          page: 1,
          page_size: 100,
        }),
      });
    });

    await page.route("**/api/v1/brands/*/ads?*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [],
          total: 0,
          page: 1,
          page_size: 50,
        }),
      });
    });

    await page.route("**/api/v1/brands/*/tests?*", async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [],
          total: 0,
          page: 1,
          page_size: 100,
        }),
      });
    });
  });

  test("shell: ads explorer loads with brand context", async ({ page }) => {
    await page.goto("/ads");
    await expect(page.getByText(/Drag and drop video files here/i)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/No ads yet/i)).toBeVisible();
  });

  test("shell: A/B wizard opens from tests hub", async ({ page }) => {
    await page.goto("/tests");
    const wizardLink = page.getByRole("link", { name: /New test wizard/i });
    await expect(wizardLink).toBeVisible({ timeout: 20_000 });
    await wizardLink.click();
    await expect(page.getByRole("heading", { name: /Design A\/B test/i })).toBeVisible({ timeout: 15_000 });
  });
});
