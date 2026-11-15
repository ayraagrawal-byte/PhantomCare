import { expect, test, type Page } from "@playwright/test";
import { buildingPosition, type BuildingListItem } from "../lib/analysis";

const targetAddress = "12444 VICTORY BLVD N HOLLYWOOD CA 91606";
const streetTiles = "https://tile.openstreetmap.org/**";
const buildingList = "**/analysis/buildings?limit=500";

async function openDashboard(page: Page) {
  await page.goto("/");
  if ((page.viewportSize()?.width ?? Infinity) <= 760) {
    await page.getByRole("button", { name: "Expand Case Queue" }).click();
  }
}

async function findBuilding(page: Page, address: string) {
  await page.getByRole("searchbox", { name: "Search addresses" }).fill(address);
  return page.locator(".building-row").filter({ hasText: address });
}

async function openTopResults(page: Page) {
  await expect(page.getByText("Analysis online")).toBeVisible();
  const groups = page.locator(".score-group-toggle");
  for (const group of await groups.all()) {
    if (Number(await group.locator(".group-count").innerText()) < 3) continue;
    if (await group.getAttribute("aria-expanded") === "false") await group.click();
    break;
  }
  return page.locator(".building-row");
}

test.beforeEach(async ({ page }) => {
  // Keep browser QA independent of the public tile service and its request limits.
  await page.route(streetTiles, (route) => route.fulfill({
    contentType: "image/svg+xml",
    body: '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><path fill="#ddd" d="M0 0h256v256H0z"/></svg>',
  }));
});

test("hotspots navigate and share selection with the evidence inspector", async ({ page }, testInfo) => {
  // Isolate two real coordinates so map navigation and marker selection are easy to exercise.
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
      building.building_key === targetAddress
        ? building
        : building.building_key === "3111 LOS FELIZ BLVD LOS ANGELES CA 90039"
        ? { ...building, review_level: "high_priority" }
        : { ...building, latitude: null, longitude: null, verified_location: null },
    ) });
  });
  await openDashboard(page);
  const hotspots = page.getByRole("region", { name: "Los Angeles County map" });
  const map = hotspots.getByRole("region", { name: "Interactive LA County street map" });
  await expect(hotspots.getByRole("region", { name: "Coverage" }).getByText("2", { exact: true })).toBeVisible();
  await expect(map.locator(".hotspot-marker")).toHaveCount(2);
  await expect(hotspots.getByRole("group", { name: "Map legend" }).getByText("High priority", { exact: true })).toBeVisible();
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
  await expect(marker).toHaveClass(/hotspot-verified/);
  expect(await marker.evaluate((dot) => getComputedStyle(dot, "::before").borderTopColor)).toBe("rgb(34, 197, 94)");
  await expect(map.locator(".hotspot-cluster")).toHaveCount(0);
  if (testInfo.project.use.hasTouch) await marker.tap();
  else await marker.click();
  const popup = map.locator(".hotspot-popup");
  await expect(popup).toContainText(targetAddress);
  await expect(popup).toContainText(/hospices.*Review score/);
  await expect(popup).toContainText("LA County CAMS · standardized match · Address point");
  await expect(marker).toHaveClass(/is-selected/);
  await popup.getByRole("link", { name: "View building evidence" }).click();
  await expect(page.locator("#building-evidence").getByRole("heading", { name: targetAddress })).toBeVisible();
  await expect(page.getByRole("button", { name: new RegExp(targetAddress), expanded: true })).toBeVisible();
});

test("localhost uses the loopback API and displays all current CAMS matches", async ({ page }) => {
  const buildings = page.waitForResponse("http://127.0.0.1:8000/analysis/buildings?limit=500");
  await page.goto("http://localhost:3000/");
  expect((await buildings).ok()).toBe(true);
  await expect(page.getByRole("region", { name: "Coverage" }).getByText("467", { exact: true })).toBeVisible();
  const legend = page.getByRole("group", { name: "Map legend" });
  await expect(legend.getByText("High priority", { exact: true })).toHaveCount(0);
  await expect(legend.locator(".legend-neutral")).toHaveCSS("background-color", "rgb(20, 108, 255)");
  await expect(legend.locator(".legend-watch")).toHaveCSS("background-color", "rgb(255, 229, 0)");
  await page.reload();
  await expect(page.getByRole("region", { name: "Coverage" }).getByText("467", { exact: true })).toBeVisible();
});

test("map legend explores classifications and location accuracy independently", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const response = page.waitForResponse(buildingList);
  await openDashboard(page);
  const buildings: BuildingListItem[] = await (await response).json();
  const legend = page.getByRole("group", { name: "Map legend" });
  const results = page.locator(".legend-results");
  const categories = [
    ["No Indicators Found", (building: BuildingListItem) => building.review_level === "no_indicators_found"],
    ["Investigate", (building: BuildingListItem) => building.review_level === "worth_a_look"],
    ["Verified Address Point", (building: BuildingListItem) => building.verified_location && buildingPosition(building)],
    ["Approximate Location", (building: BuildingListItem) => building.approximate_location && buildingPosition(building)],
  ] as const;
  const building = buildings.find(({ building_key }) => building_key === targetAddress)!;
  for (const [label, matches] of categories) {
    const category = legend.getByRole("button", { name: label, exact: true });
    await category.focus();
    await page.keyboard.press("Enter");
    await expect(category).toHaveAttribute("aria-expanded", "true");
    await expect(legend.locator('[aria-expanded="true"]')).toHaveCount(1);
    const expected = buildings.filter(matches).sort((a, b) => b.total_score - a.total_score);
    await expect(results.getByRole("heading")).toHaveText(`${label} ${expected.length} buildings`);
    await expect(results.locator("li strong")).toHaveText(expected.slice(0, 25).map(({ building_key }) => building_key));
    await expect(results).toHaveCSS("animation-name", "none");
    await results.getByRole("button", { name: "Next", exact: true }).click();
    await expect(results.locator("li strong")).toHaveText(expected.slice(25, 50).map(({ building_key }) => building_key));
    const search = results.getByRole("searchbox");
    await search.fill(building.building_id);
    await expect(results.locator("li")).toHaveCount(matches(building) ? 1 : 0);
    if (label === "Verified Address Point") {
      const row = results.getByRole("button", { name: new RegExp(targetAddress) });
      await row.focus();
      await page.keyboard.press("Enter");
      await expect(row).toHaveAttribute("aria-pressed", "true");
      await expect(page.locator(".hotspot-marker.is-selected")).toHaveAttribute("title", targetAddress);
      await expect(page.locator(".case-heading-bar h1")).toContainText(targetAddress);
      await expect(page.locator("#building-evidence").getByRole("heading", { name: targetAddress })).toBeVisible();
    }
  }
  await legend.getByRole("button", { name: "Approximate Location", exact: true }).click();
  await expect(results).toHaveCount(0);
  const unmapped = buildings.find((item) => !buildingPosition(item))!;
  await legend.getByRole("button", { name: unmapped.review_level === "worth_a_look" ? "Investigate" : "No Indicators Found", exact: true }).click();
  await results.getByRole("searchbox").fill(unmapped.building_key);
  const row = results.locator("li button").filter({ hasText: unmapped.building_key });
  await row.click();
  await expect(page.locator("#building-evidence").getByRole("heading", { name: unmapped.building_key })).toBeVisible();
  await expect(page.locator(".hotspot-marker.is-selected")).toHaveCount(0);
});

test("coincident dots can be selected individually through the marker popup", async ({ page }) => {
  await openDashboard(page);
  const map = page.getByRole("region", { name: "Interactive LA County street map" });
  const address = "5301 LAUREL CANYON BLVD VALLEY VILLAGE CA 91607";
  const alias = "5301 LAUREL CANTON BL VALLEY VILLAGE CA 91607";
  await (await findBuilding(page, address)).click();
  const marker = map.getByTitle(address, { exact: true });
  await expect(marker).toHaveClass(/is-selected/);
  await marker.click();
  const popup = map.locator(".hotspot-popup");
  await popup.getByText("Other buildings at or near this point").click();
  await popup.getByRole("button", { name: alias, exact: true }).click();
  await expect(popup.locator("strong").first()).toHaveText(alias);
  await expect(page.locator("#building-evidence").getByRole("heading", { name: alias })).toBeVisible();
});

test("workspace navigation reaches real sections on desktop and mobile", async ({ page }, testInfo) => {
  await openDashboard(page);
  const inspector = page.getByRole("region", { name: "Building evidence" });
  await expect(inspector.getByRole("heading", { name: "Select a Building", exact: true })).toBeVisible();
  await expect(inspector.locator("p")).toHaveText([
    "Evidence inspector",
    "Choose a building from the review queue to view its evidence and investigation details.",
  ]);
  const nav = page.getByRole("navigation", { name: "Workspace" });
  if (testInfo.project.use.hasTouch) {
    await expect(nav).toBeHidden();
    await page.getByRole("button", { name: "Menu", exact: true }).click();
  }
  await expect(nav.getByRole("link", { name: "Investigations", exact: true })).toHaveAttribute("aria-current", "location");
  await nav.getByRole("link", { name: "Map", exact: true }).click();
  await expect(page).toHaveURL(/#map$/);
  await expect(page.getByRole("region", { name: "Interactive LA County street map" })).toBeInViewport();
  if (testInfo.project.use.hasTouch) await expect(nav).toBeHidden();
  await page.getByRole("searchbox", { name: "Search addresses" }).scrollIntoViewIfNeeded();
  await expect(page.getByRole("searchbox", { name: "Search addresses" })).toBeInViewport();
});

test("Case Queue toggles without losing the current case or map view", async ({ page }, testInfo) => {
  await page.goto("/");
  const masthead = page.getByRole("banner");
  await expect(masthead).toContainText("Hospice Registration & Property Investigation Platform");
  await expect(masthead.locator("time")).toHaveCount(0);
  await expect(masthead.getByRole("link")).toHaveCount(1);
  await expect(masthead.getByText(/Los Angeles County|Review Queue|Updated/)).toHaveCount(0);
  const toggle = page.locator(".queue-toggle");
  await expect(toggle).toHaveAttribute("aria-expanded", testInfo.project.use.hasTouch ? "false" : "true");
  if (testInfo.project.use.hasTouch) await toggle.click();
  const search = page.getByRole("searchbox", { name: "Search addresses" });
  await page.getByRole("button", { name: "Investigate", exact: true }).first().click();
  await search.fill(targetAddress);
  await page.locator(".building-row").click();
  await expect(page.locator(".inspector-head h2")).toHaveText(targetAddress);
  const map = page.locator(".hotspot-map");
  const width = (await map.boundingBox())!.width;
  const marker = map.locator(".hotspot-marker.is-selected");
  await toggle.focus();
  await page.keyboard.press("Enter");
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(toggle).toBeFocused();
  await expect(search).toBeHidden();
  if (!testInfo.project.use.hasTouch) await expect.poll(async () => (await map.boundingBox())!.width).toBeGreaterThan(width + 50);
  await expect(map.locator(".leaflet-tile-loaded").first()).toBeVisible();
  await expect(marker).toHaveAttribute("title", targetAddress);
  await expect(page.locator(".inspector-head h2")).toHaveText(targetAddress);
  await page.keyboard.press("Space");
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(search).toHaveValue(targetAddress);
  await expect(page.getByRole("group", { name: "Filter review level" }).getByRole("button", { name: "Investigate" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".score-group-toggle")).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator(".building-row")).toHaveAttribute("aria-expanded", "true");
});


test("review queue groups all buildings and combines search with classification filters", async ({ page }) => {
  const response = page.waitForResponse(buildingList);
  await openDashboard(page);
  const buildings: { building_id: string; total_score: number; review_level: string }[] = await (await response).json();
  expect(buildings).toHaveLength(468);
  const queue = page.getByRole("region", { name: "Case Queue (LA County) 468" });
  const groups = queue.locator(".score-group");
  const filters = queue.getByRole("group", { name: "Filter review level" });
  await expect(filters.getByRole("button")).toHaveText(["All Buildings", "Investigate", "No Flags"]);
  const ranges = [
    { min: 80, max: 100 },
    { min: 60, max: 79 },
    { min: 40, max: 59 },
    { min: 0, max: 39 },
  ];
  await expect(groups).toHaveCount(ranges.length);
  for (const [index, { min, max }] of ranges.entries()) {
    const count = buildings.filter(({ total_score }) => Math.round(total_score) >= min && Math.round(total_score) <= max).length;
    const group = groups.nth(index);
    const toggle = group.getByRole("button", { name: new RegExp(`Score ${min}–${max}`) });
    await expect(toggle).toHaveAttribute("aria-expanded", index === 0 ? "true" : "false");
    await expect(toggle.locator(".group-count")).toHaveText(String(count));
    if (index > 0) await toggle.click();
    await expect(group.locator(".building-row")).toHaveCount(count);
    const scores = (await group.locator(".score").allTextContents()).map(Number);
    expect(scores).toEqual([...scores].sort((a, b) => b - a));
  }
  await expect(queue.locator(".building-row")).toHaveCount(468);
  for (const [label, level] of [["No Flags", "no_indicators_found"], ["Investigate", "worth_a_look"]]) {
    await filters.getByRole("button", { name: label, exact: true }).click();
    await expect.poll(async () => (await groups.locator(".group-count").allTextContents()).reduce((sum, count) => sum + Number(count), 0))
      .toBe(buildings.filter(({ review_level }) => review_level === level).length);
  }
  const building = buildings.find(({ review_level }) => review_level === "worth_a_look")!;
  await queue.getByRole("button", { name: "No Flags", exact: true }).click();
  await queue.getByRole("searchbox").fill(building.building_id);
  await expect(queue.getByText("No buildings match this view.")).toBeVisible();
  await queue.getByRole("button", { name: "Investigate", exact: true }).click();
  const row = queue.locator(".building-row");
  await expect(row).toHaveCount(1);
  await expect(groups).toHaveCount(1);
  await row.click();
  await expect(row).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("button", { name: "Investigate this building", exact: true })).toBeVisible();
  await row.click();
  await expect(row).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByRole("button", { name: "Investigate this building", exact: true })).toHaveCount(0);
});

test("case queue supports keyboard input and reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openDashboard(page);

  const rows = await openTopResults(page);
  await rows.first().focus();
  await expect(rows.first()).toHaveClass(/building-row-enter/);
  await expect(rows.first()).toHaveCSS("animation-name", "none");
  await page.keyboard.press("ArrowDown");
  await expect(rows.nth(1)).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(rows.nth(1)).toHaveAttribute("aria-expanded", "true");
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
  await openDashboard(page);
  const hotspots = page.getByRole("region", { name: "Los Angeles County map" });
  await expect(hotspots.getByRole("alert")).toContainText("do not match the CAMS cache");
  await expect(hotspots.getByRole("region", { name: "Coverage" }).getByText("2", { exact: true })).toHaveCount(0);
  await expect(hotspots.locator(".hotspot-marker, .hotspot-cluster")).toHaveCount(0);
  await expect.poll(async () => (await page.locator(".group-count").allTextContents()).reduce((sum, count) => sum + Number(count), 0)).toBe(468);
});

test("hotspots report a tile outage while preserving mapped locations", async ({ page }) => {
  await page.route(streetTiles, (route) => route.abort());
  await openDashboard(page);
  const hotspots = page.getByRole("region", { name: "Los Angeles County map" });
  await expect(hotspots.getByRole("status").filter({ hasText: "Some street tiles are unavailable" })).toBeVisible();
  await expect(hotspots.getByRole("region", { name: "Coverage" }).getByText("467", { exact: true })).toBeVisible();
  await expect(hotspots.locator(".hotspot-marker")).toHaveCount(467);
  await expect(hotspots.locator(".hotspot-cluster")).toHaveCount(0);
  const row = await findBuilding(page, targetAddress);
  await row.click();
  await expect(hotspots.getByTitle(targetAddress, { exact: true })).toHaveClass(/is-selected/);
});

test("approximate markers retain separate counts and disclose street-level precision", async ({ page }) => {
  await openDashboard(page);
  const hotspots = page.getByRole("region", { name: "Los Angeles County map" });
  const locationData = hotspots.getByRole("region", { name: "Location Data" });
  for (const count of ["344", "123", "1"]) {
    await expect(locationData.getByText(count, { exact: true })).toBeVisible();
  }
  const address = "16430 VENTURA BLVD ENCINO CA 91436";
  await (await findBuilding(page, address)).click();
  const marker = hotspots.getByTitle(address, { exact: true });
  await expect(marker).toHaveClass(/hotspot-approximate/);
  expect(await marker.evaluate((dot) => {
    const style = getComputedStyle(dot, "::before");
    return style.borderTopStyle === "solid" && style.borderTopColor === "rgb(255, 48, 48)";
  })).toBe(true);
  await marker.click();
  await expect(hotspots.locator(".hotspot-popup")).toContainText("Census street interpolation");
  await expect(hotspots.locator(".hotspot-popup")).toContainText("Building position unconfirmed");
  await expect(page.locator("#building-evidence").getByRole("heading", { name: address })).toBeVisible();
});

test("reviewed parcel positions disclose parcel precision and open evidence", async ({ page }) => {
  await openDashboard(page);
  const address = "444 E HUNTINGTON DR ARCADIA CA 91006";
  const hotspots = page.getByRole("region", { name: "Los Angeles County map" });
  await (await findBuilding(page, address)).click();
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

  await openDashboard(page);
  await expect(page.getByText("Analysis online")).toBeVisible();
  const summary = page.getByRole("region", { name: "Coverage" });
  for (const value of ["468", "467", "99.8%"]) {
    await expect(summary.getByText(value, { exact: true })).toBeVisible();
  }

  const search = page.getByRole("searchbox", { name: "Search addresses" });
  await search.fill("12444 VICTORY");
  await expect(page.locator(".building-row")).toHaveCount(1);
  await page.locator(".building-row").filter({ hasText: targetAddress }).click();

  const inspector = page.locator(".inspector");
  await expect(inspector.getByRole("heading", { name: targetAddress })).toBeVisible();
  await expect(inspector.getByRole("heading", { name: "CMS Registration" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^(Investigation Timeline|Uncertainty|Human Next Step)$/i })).toHaveCount(0);
  await expect(inspector.locator(".trace-list time").first()).toHaveAttribute("datetime", /T/);
  await expect(inspector.getByText("No exact property record is available")).toBeVisible();
  await expect(inspector.getByAltText(/Vexcel ortho context/)).toBeVisible();

  await inspector.getByRole("button", { name: "Investigate this building" }).click();
  await expect(inspector.getByText("Deterministic fallback", { exact: true })).toBeVisible();
  await expect(inspector.getByText(/Live AI was not used/)).toBeVisible();
  await expect(inspector.getByText("CMS", { exact: true })).toBeVisible();
  await expect(inspector.getByText("CoStar", { exact: true })).toBeVisible();
  await expect(inspector.getByText("Vexcel", { exact: true })).toBeVisible();
  await expect(inspector.getByText("Recommended next step")).toBeVisible();
  const checklist = inspector.locator(".review-checklist");
  await expect(checklist.getByText("Human-review checklist")).toBeVisible();
  await expect(checklist).toContainText("No exact CoStar property record");
  await expect(checklist).toContainText("Treat Vexcel imagery as exterior context only");
  await expect(page.getByRole("heading", { name: "Not a Fraud Determination" })).toBeVisible();

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

test("real CoStar match shows licensed context, Matterport link and cross-source comparison", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Analysis online")).toBeVisible();
  await page.getByRole("searchbox", { name: "Search addresses" }).fill("3800 BARHAM");
  await page.getByRole("button", { name: /3800 BARHAM BLVD/ }).click();
  const inspector = page.locator(".inspector");
  const context = inspector.locator(".context-card");
  await expect(context.getByRole("heading", { name: "Barham Plaza" })).toBeVisible();
  await expect(context).toContainText("85,831 sq ft");
  await expect(context).toContainText("Licensed CoStar data");
  const tour = context.getByRole("link", { name: /sponsor-linked Matterport model/ });
  await expect(tour).toHaveAttribute("href", "https://my.matterport.com/show/?m=cqDGKrH5ZTu");
  await expect(tour).toHaveAttribute("rel", /noopener/);
  await expect(context).toContainText("not any specific hospice suite");
  await expect(inspector.locator(".aerial-card")).toHaveCount(0);

  await inspector.getByRole("button", { name: "Investigate this building" }).click();
  await expect(inspector.getByText("Deterministic fallback", { exact: true })).toBeVisible();
  await expect(inspector.locator(".data-class-licensed_property_data")).toHaveText("Licensed CoStar data");
  const comparison = inspector.locator(".comparison-panel");
  await expect(comparison).toContainText("Compared: CMS + CoStar + Ownership");
  await expect(comparison).toContainText("85,831 sq ft per registration");
  await expect(comparison).toContainText("no Vexcel imagery was retrieved");
});

test("rapid selection and failed detail request never leave stale evidence", async ({ page }) => {
  await openDashboard(page);
  await expect(page.getByText("Analysis online")).toBeVisible();
  const rows = await openTopResults(page);
  const secondAddress = (await rows.nth(1).locator(".building-main strong").textContent()) ?? "";
  await rows.nth(0).click();
  await rows.nth(1).click();
  await expect(page.locator(".inspector-head h2")).toHaveText(secondAddress);

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

test("switching buildings during an investigation keeps the new inspector clear", async ({ page }) => {
  let release = () => {};
  const hold = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/investigations/*", async (route) => {
    const response = await route.fetch();
    await hold;
    await route.fulfill({ response });
  });
  try {
    await openDashboard(page);
    const rows = await openTopResults(page);
    const inspector = page.locator(".inspector");
    const newAddress = await rows.nth(1).locator(".building-main strong").innerText();
    await rows.first().click();
    const investigate = inspector.getByRole("button", { name: "Investigate this building" });
    const started = page.waitForRequest("**/investigations/*");
    await investigate.click();
    await started;
    await rows.nth(1).click();
    await expect(inspector.getByRole("heading", { name: newAddress })).toBeVisible();
    const completed = page.waitForResponse("**/investigations/*");
    release();
    await (await completed).finished();
    await page.evaluate(() => new Promise<void>((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
    ));
    await expect(investigate).toBeEnabled();
    await expect(inspector.getByText("Deterministic fallback", { exact: true })).toHaveCount(0);
  } finally {
    release();
  }
});

test("responsive layout and keyboard selection remain usable", async ({ page }) => {
  await openDashboard(page);
  await expect(page.getByText("Analysis online")).toBeVisible();
  const search = page.getByRole("searchbox", { name: "Search addresses" });
  await search.focus();
  await search.fill("12444 VICTORY");
  await page.keyboard.press("Tab");
  const row = page.locator(".building-row").filter({ hasText: targetAddress });
  await row.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".inspector-head h2")).toHaveText(targetAddress);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
    ),
  ).toBe(true);
});
