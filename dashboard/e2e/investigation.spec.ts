import { expect, test } from "@playwright/test";

const targetAddress = "12444 VICTORY BLVD N HOLLYWOOD CA 91606";
const streetTiles = "https://tile.openstreetmap.org/**";
const buildingList = "**/analysis/buildings?limit=500";

test.beforeEach(async ({ page }) => {
  // Keep browser QA independent of the public tile service and its request limits.
  await page.route(streetTiles, (route) => route.fulfill({
    contentType: "image/svg+xml",
    body: '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><path fill="#ddd" d="M0 0h256v256H0z"/></svg>',
  }));
});

test("hotspots navigate and share selection with the evidence inspector", async ({ page }, testInfo) => {
  // Isolate two real coordinates so the marker interaction has a stable cluster to expand.
  await page.route("**/analysis/summary", async (route) => {
    const response = await route.fetch();
    await route.fulfill({ response, json: {
      ...await response.json(), cams_mapped_count: 2, approximate_mapped_count: 0,
    } });
  });
  await page.route(buildingList, async (route) => {
    const response = await route.fetch();
    const buildings = await response.json();
    await route.fulfill({ response, json: buildings.map((building: Record<string, unknown>) =>
      building.building_key === targetAddress || building.building_key === "3111 LOS FELIZ BLVD LOS ANGELES CA 90039"
        ? building
        : { ...building, latitude: null, longitude: null, verified_location: null },
    ) });
  });
  await page.goto("/");
  const hotspots = page.getByRole("region", { name: "LA County hotspots" });
  const map = hotspots.getByRole("region", { name: "Interactive LA County street map" });
  await expect(hotspots.getByText("2 mapped of 468 analyzed buildings")).toBeVisible();
  await expect(map.getByRole("link", { name: "OpenStreetMap contributors" })).toBeVisible();
  await expect(map.locator(".leaflet-tile-loaded").first()).toBeVisible();
  const initialTile = await map.locator(".leaflet-tile").first().getAttribute("src");
  await map.getByRole("button", { name: "Zoom in" }).click();
  await expect.poll(async () => map.locator(".leaflet-tile").first().getAttribute("src")).not.toBe(initialTile);
  await hotspots.getByRole("button", { name: "Reset view" }).click();
  await expect.poll(async () => map.locator(".leaflet-tile").first().getAttribute("src")).toBe(initialTile);

  if (!testInfo.project.use.hasTouch) {
    const pane = map.locator(".leaflet-map-pane");
    const initialPosition = await pane.getAttribute("style");
    const box = (await map.boundingBox())!;
    await page.mouse.move(box.x + box.width * 0.75, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.55, box.y + box.height / 2, { steps: 8 });
    await page.mouse.up();
    await expect.poll(() => pane.getAttribute("style")).not.toBe(initialPosition);
    await hotspots.getByRole("button", { name: "Reset view" }).click();
  }

  const marker = map.getByTitle(targetAddress, { exact: true });
  // At narrow widths both locations may initially share a cluster.
  const cluster = map.locator(".hotspot-cluster");
  if (await cluster.count()) await cluster.first().click();
  if (testInfo.project.use.hasTouch) await marker.tap();
  else await marker.click();
  const popup = map.locator(".hotspot-popup");
  await expect(popup).toContainText(targetAddress);
  await expect(popup).toContainText(/hospices.*Review score/);
  await expect(popup).toContainText("LA County CAMS · standardized match · Address point");
  await expect(marker).toHaveClass(/is-selected/);
  await popup.getByRole("link", { name: "View building evidence" }).click();
  await expect(page.locator("#building-evidence").getByRole("heading", { name: targetAddress })).toBeVisible();
  await expect(page.getByRole("button", { name: new RegExp(targetAddress), pressed: true })).toBeVisible();
});

test("localhost uses the loopback API and displays all current CAMS matches", async ({ page }) => {
  const buildings = page.waitForResponse("http://127.0.0.1:8000/analysis/buildings?limit=500");
  await page.goto("http://localhost:3000/");
  expect((await buildings).ok()).toBe(true);
  await expect(page.getByText("467 mapped of 468 analyzed buildings")).toBeVisible();
  await page.reload();
  await expect(page.getByText("467 mapped of 468 analyzed buildings")).toBeVisible();
});

test("rejects a stale two-point response when the API advertises the current cache", async ({ page }) => {
  await page.route(buildingList, async (route) => {
    const response = await route.fetch();
    const buildings = await response.json();
    let remaining = 2;
    await route.fulfill({ response, json: buildings.map((building: Record<string, unknown>) =>
      building.verified_location && remaining-- > 0
        ? building
        : { ...building, latitude: null, longitude: null, verified_location: null },
    ) });
  });
  await page.goto("/");
  const hotspots = page.getByRole("region", { name: "LA County hotspots" });
  await expect(hotspots.getByRole("alert")).toContainText("do not match the CAMS cache");
  await expect(hotspots.getByText(/mapped of/)).toHaveCount(0);
  await expect(hotspots.locator(".hotspot-marker, .hotspot-cluster")).toHaveCount(0);
  await expect(page.getByText("Showing 468 of 468 buildings")).toBeVisible();
});

test("hotspots report a tile outage while preserving mapped locations", async ({ page }) => {
  await page.route(streetTiles, (route) => route.abort());
  await page.goto("/");
  const hotspots = page.getByRole("region", { name: "LA County hotspots" });
  await expect(hotspots.getByRole("status").filter({ hasText: "Some street tiles are unavailable" })).toBeVisible();
  await expect(hotspots.getByText("467 mapped of 468 analyzed buildings")).toBeVisible();
  await expect(hotspots.locator(".hotspot-cluster").first()).toBeVisible();
  const row = page.locator(".building-row").filter({ hasText: targetAddress });
  await row.click();
  await expect(hotspots.getByTitle(targetAddress, { exact: true })).toHaveClass(/is-selected/);
});

test("approximate markers retain separate counts and disclose street-level precision", async ({ page }) => {
  await page.goto("/");
  const hotspots = page.getByRole("region", { name: "LA County hotspots" });
  await expect(hotspots.getByText("344 verified · 123 approximate · 1 unmapped")).toBeVisible();
  const address = "16430 VENTURA BLVD ENCINO CA 91436";
  await page.locator(".building-row").filter({ hasText: address }).click();
  const marker = hotspots.getByTitle(address, { exact: true });
  await expect(marker).toHaveClass(/hotspot-approximate/);
  await marker.click();
  await expect(hotspots.locator(".hotspot-popup")).toContainText("Census street interpolation");
  await expect(hotspots.locator(".hotspot-popup")).toContainText("Building position unconfirmed");
  await expect(page.locator("#building-evidence").getByRole("heading", { name: address })).toBeVisible();
});

test("reviewed parcel positions disclose parcel precision and open evidence", async ({ page }) => {
  await page.goto("/");
  const address = "444 E HUNTINGTON DR ARCADIA CA 91006";
  const hotspots = page.getByRole("region", { name: "LA County hotspots" });
  await page.locator(".building-row").filter({ hasText: address }).click();
  const marker = hotspots.getByTitle(address, { exact: true });
  await expect(marker).toHaveClass(/hotspot-approximate/);
  await marker.click();
  await expect(hotspots.locator(".hotspot-popup")).toContainText("Parcel location");
  await expect(page.locator("#building-evidence").getByRole("heading", { name: address })).toBeVisible();
});

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
