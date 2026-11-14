import { expect, test } from "@playwright/test";

const targetAddress = "12444 VICTORY BLVD N HOLLYWOOD CA 91606";

test("complete deterministic investigation journey", async ({ page }) => {
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("requestfailed", (request) => {
    // React dev-mode effect cleanup and browser downloads intentionally abort
    // superseded requests; report only transport failures that users would see.
    if (request.failure()?.errorText !== "net::ERR_ABORTED") {
      failedRequests.push(`${request.failure()?.errorText}: ${request.url()}`);
    }
  });

  await page.goto("/");
  await expect(page.getByText("Analysis online")).toBeVisible();
  const summary = page.getByLabel("Analysis summary");
  await expect(summary.getByText("569", { exact: true })).toBeVisible();
  await expect(summary.getByText("468", { exact: true })).toBeVisible();
  await expect(summary.getByText("119", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "High priority" }).click();
  await expect(page.getByText("No buildings match this view.")).toBeVisible();
  await page.getByRole("button", { name: "All buildings" }).click();

  const search = page.getByRole("searchbox", { name: "Search addresses" });
  await search.fill("12444 VICTORY");
  await expect(page.getByText("Showing 1 of 468 buildings")).toBeVisible();
  await page.getByRole("button", { name: new RegExp(targetAddress) }).click();

  const inspector = page.locator(".inspector");
  await expect(inspector.getByRole("heading", { name: targetAddress })).toBeVisible();
  await expect(inspector.getByText("No exact property record is available")).toBeVisible();
  await expect(inspector.getByAltText(/Vexcel ortho context/)).toBeVisible();

  await inspector.getByRole("button", { name: "Investigate this building" }).click();
  await expect(inspector.getByText("Deterministic fallback", { exact: true })).toBeVisible();
  await expect(inspector.getByText(/Live AI was not used/)).toBeVisible();
  await expect(inspector.getByText("CMS", { exact: true })).toBeVisible();
  await expect(inspector.getByText("CoStar", { exact: true })).toBeVisible();
  await expect(inspector.getByText("Vexcel", { exact: true })).toBeVisible();
  await expect(inspector.getByText("Recommended next step")).toBeVisible();

  await inspector.getByText(/Inspect 8 genuine tool calls/).click();
  await expect(inspector.getByText("get_source_records", { exact: true })).toBeVisible();
  await expect(inspector.getByText(/derived:bldg_793ac00ed2ae2571/).first()).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await inspector.getByRole("link", { name: "Download JSON case file" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^phantomcare-case_.*\.json$/);

  expect(consoleErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
});

test("rapid selection and failed detail request never leave stale evidence", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Analysis online")).toBeVisible();
  const rows = page.locator(".building-row");
  const secondAddress = (await rows.nth(1).locator(".building-main strong").textContent()) ?? "";
  await rows.nth(0).click();
  await rows.nth(1).click();
  await expect(page.locator(".inspector h2")).toHaveText(secondAddress);

  await page.route("**/analysis/buildings/*", async (route) => {
    if (!route.request().url().includes("/network") && !route.request().url().includes("/aerial")) {
      await route.fulfill({ status: 503, json: { detail: { message: "Fixture failure" } } });
    } else {
      await route.continue();
    }
  });
  await rows.nth(2).click();
  await expect(page.locator(".inspector-empty[role='alert']")).toContainText(
    "Could not load building evidence",
  );
  await expect(page.locator(".inspector h2")).toHaveCount(0);
});

test("nonexistent investigation target returns a neutral 404", async ({ request }) => {
  const response = await request.post(
    "http://127.0.0.1:8000/investigations/bldg_0000000000000000",
  );
  expect(response.status()).toBe(404);
  expect((await response.json()).detail.code).toBe("investigation_target_not_found");
});

test("responsive layout and keyboard selection remain usable", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Analysis online")).toBeVisible();
  const search = page.getByRole("searchbox", { name: "Search addresses" });
  await search.focus();
  await search.fill("12444 VICTORY");
  await page.keyboard.press("Tab");
  const row = page.getByRole("button", { name: new RegExp(targetAddress) });
  await row.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".inspector h2")).toHaveText(targetAddress);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
    ),
  ).toBe(true);
});
