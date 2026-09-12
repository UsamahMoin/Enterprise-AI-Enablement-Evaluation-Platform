/**
 * Regenerates the screenshots used in the README.
 *
 *   npx playwright test screenshots --update-snapshots
 *
 * Kept as a test rather than a manual step so the images in the README cannot
 * quietly drift away from what the app actually renders.
 */
import { expect, test, type Page } from "@playwright/test";

const DIR = "../docs/screenshots";

test.use({ viewport: { width: 1440, height: 1000 } });

async function signIn(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("demo1234");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

test("capture README screenshots", async ({ page }) => {
  await signIn(page, "employee@demo.com");
  await expect(page.getByText("Recommended workflows")).toBeVisible();
  await page.screenshot({ path: `${DIR}/dashboard.png`, fullPage: true });

  await page.goto("/workflows");
  await expect(page.getByRole("heading", { name: "Workflow library" })).toBeVisible();
  await page.screenshot({ path: `${DIR}/workflow-library.png` });

  await page.goto("/workflows/generate_unit_tests");
  await page.getByLabel("Paste your code").fill(
    "def calculate_total(items):\n    total = 0\n    for item in items:\n        total += item\n    return total",
  );
  await page.getByLabel("Constraints").fill("No external dependencies. Cover empty input.");
  await page.getByRole("button", { name: "Run workflow" }).click();
  await expect(page.getByRole("heading", { name: "Evaluation", exact: true })).toBeVisible({
    timeout: 30_000,
  });
  await page.screenshot({ path: `${DIR}/execution-evaluation.png`, fullPage: true });

  await page.goto("/workflows/generate_unit_tests");
  await page.getByLabel("Paste your code").fill("# SSN: 123-45-6789\ndef add(a, b):\n    return a + b");
  await page.getByRole("button", { name: "Run workflow" }).click();
  await expect(
    page.getByRole("heading", { name: "Potential sensitive information detected" }),
  ).toBeVisible();
  await page.screenshot({ path: `${DIR}/governance-block.png` });

  await page.getByRole("button", { name: "Sign out" }).click();
  await signIn(page, "admin@demo.com");

  await page.goto("/analytics");
  await expect(page.getByText("Effective adoption")).toBeVisible();
  await page.screenshot({ path: `${DIR}/adoption-analytics.png`, fullPage: true });

  await page.getByRole("button", { name: "Quality" }).click();
  await expect(page.getByText("Quality by workflow")).toBeVisible();
  await page.screenshot({ path: `${DIR}/quality-dashboard.png`, fullPage: true });

  await page.getByRole("button", { name: "Prompt versions" }).click();
  await expect(page.getByText("Prompt version comparison")).toBeVisible();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${DIR}/prompt-versions.png`, fullPage: true });

  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Enterprise AI overview" })).toBeVisible();
  await page.screenshot({ path: `${DIR}/admin-overview.png`, fullPage: true });

  await page.goto("/governance");
  await expect(page.getByText("Pre-execution pipeline")).toBeVisible();
  await page.screenshot({ path: `${DIR}/governance.png`, fullPage: true });
});
