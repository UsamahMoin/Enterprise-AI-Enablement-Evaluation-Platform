import { expect, test, type Page } from "@playwright/test";

async function signIn(page: Page, email = "employee@demo.com") {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("demo1234");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

test("rejects bad credentials without signing in", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("employee@demo.com");
  await page.getByLabel("Password").fill("not-the-password");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByText(/incorrect email or password/i)).toBeVisible();
  await expect(page).toHaveURL(/\/login/);
});

test("signs in and renders the employee dashboard from seeded data", async ({ page }) => {
  await signIn(page);

  await expect(page.getByRole("heading", { name: /welcome/i })).toBeVisible();
  await expect(page.getByText("Recommended workflows")).toBeVisible();
  await expect(page.getByText("Workflows completed")).toBeVisible();
  await expect(page.getByText("Estimated time saved")).toBeVisible();
});

test("filters the workflow library and shows governance metadata", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: "Workflows" }).click();

  await expect(page.getByRole("heading", { name: "Workflow library" })).toBeVisible();
  await page.getByLabel("Department").selectOption("Finance");
  await expect(page.getByText("Analyze Financial Variance")).toBeVisible();
  await expect(page.getByText("Human review required").first()).toBeVisible();

  // Clear the department filter first: the prohibited workflow sits in HR.
  await page.getByLabel("Department").selectOption("All");
  await page.getByLabel("Risk").selectOption("PROHIBITED");
  await expect(page.getByText(/registered as a prohibited use case/i).first()).toBeVisible();
});

test("runs a workflow and records a human decision", async ({ page }) => {
  await signIn(page);
  await page.goto("/workflows/generate_unit_tests");

  await page.getByLabel("Paste your code").fill("def add(a, b):\n    return a + b");
  await page.getByRole("button", { name: "Run workflow" }).click();

  await expect(page.getByRole("heading", { name: "Evaluation", exact: true })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText("/ 100 overall")).toBeVisible();
  await expect(page.getByText("Deterministic checks", { exact: true })).toBeVisible();
  // No reference material was supplied, so groundedness must be reported N/A.
  await expect(page.getByText(/groundedness is n\/a/i)).toBeVisible();

  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText(/you recorded approved/i)).toBeVisible();
});

test("blocks sensitive data before it reaches the provider", async ({ page }) => {
  await signIn(page);
  await page.goto("/workflows/generate_unit_tests");

  await page.getByLabel("Paste your code").fill("# SSN: 123-45-6789\ndef add(a, b):\n    return a + b");
  await page.getByRole("button", { name: "Run workflow" }).click();

  await expect(
    page.getByRole("heading", { name: "Potential sensitive information detected" }),
  ).toBeVisible();
  await expect(page.getByText("Social Security Number", { exact: true })).toBeVisible();
  await expect(page.getByText(/was not sent to the AI provider/i).first()).toBeVisible();
  await expect(page.getByText("/ 100 overall")).toHaveCount(0);
});

test("employees cannot see analytics, admins can", async ({ page }) => {
  await signIn(page, "employee@demo.com");
  await expect(page.getByRole("link", { name: "Analytics" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);

  await page.getByRole("button", { name: "Sign out" }).click();
  await signIn(page, "admin@demo.com");

  await page.getByRole("link", { name: "Analytics" }).click();
  await expect(page.getByText("Effective adoption")).toBeVisible();
  await expect(page.getByText("Department adoption")).toBeVisible();

  await page.getByRole("button", { name: "Quality" }).click();
  await expect(page.getByText(/judge . human gap/i)).toBeVisible();

  await page.getByRole("button", { name: "Prompt versions" }).click();
  await expect(page.getByText("Prompt version comparison")).toBeVisible();
});

test("admin overview flags workflows below the quality threshold", async ({ page }) => {
  await signIn(page, "admin@demo.com");
  await page.getByRole("link", { name: "Admin" }).click();

  await expect(page.getByRole("heading", { name: "Enterprise AI overview" })).toBeVisible();
  await expect(page.getByText("Workflows requiring attention")).toBeVisible();
  await expect(page.getByText("Most used workflows")).toBeVisible();
});

test("governance page lists policies and an audit trail without raw values", async ({ page }) => {
  await signIn(page, "admin@demo.com");
  await page.getByRole("link", { name: "Governance" }).click();

  await expect(page.getByText("Pre-execution pipeline")).toBeVisible();
  await expect(page.getByText("Sensitive data detection", { exact: true })).toBeVisible();
  await expect(page.getByText("Audit log")).toBeVisible();
  // The audit trail stores categories, never the detected value.
  await expect(page.getByText("123-45-6789")).toHaveCount(0);
});

test("governance page explains provider capabilities and their limits", async ({ page }) => {
  await signIn(page, "admin@demo.com");
  await page.goto("/governance");

  await expect(page.getByText("Model providers")).toBeVisible();

  // Each provider's governance-relevant capabilities are stated, including the
  // one that costs something: a self-hosted provider cannot moderate.
  const localRow = page.getByRole("row").filter({ hasText: "local" }).first();
  await expect(localRow).toContainText("RESTRICTED");
  await expect(localRow).toContainText("None");

  await expect(page.getByText(/routing a workflow to a self-hosted model/i)).toBeVisible();
  await expect(page.getByText(/never as passed/i)).toBeVisible();
});
