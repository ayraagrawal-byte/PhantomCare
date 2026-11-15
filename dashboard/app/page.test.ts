import { describe, expect, it } from "vitest";
import { BuildingListItem, buildingPosition, filterBuildings, formatLevel, resolveApiUrl } from "../lib/analysis";

const buildings: BuildingListItem[] = [
  { building_id:"bldg_high", building_key:"100 REVIEW ST LOS ANGELES CA 90012", hospice_count:8, total_score:84, review_level:"high_priority", strong_indicator_count:3, costar_match_status:"exact_match", latitude:34.0522, longitude:-118.2437 },
  { building_id:"bldg_watch", building_key:"200 MAIN ST VAN NUYS CA 91401", hospice_count:3, total_score:46, review_level:"worth_a_look", strong_indicator_count:1, costar_match_status:"not_configured", latitude:null, longitude:null },
];

describe("analysis dashboard helpers", () => {
  it("uses the local API on loopback even when the bundle was built with a remote API", () => {
    const remote = "https://phantomcare-api.vercel.app";
    expect(resolveApiUrl("127.0.0.1", remote)).toBe("http://127.0.0.1:8000");
    expect(resolveApiUrl("localhost")).toBe("http://127.0.0.1:8000");
    expect(resolveApiUrl("localhost", "http://127.0.0.1:8001/")).toBe("http://127.0.0.1:8001");
    expect(resolveApiUrl("dashboard-preview.vercel.app", remote)).toBe(remote);
  });
  it("filters by review level and address search", () => {
    expect(filterBuildings(buildings,"high_priority","review")).toEqual([buildings[0]]);
    expect(filterBuildings(buildings,"worth_a_look","review")).toEqual([]);
    expect(filterBuildings(buildings,"all","van nuys")).toEqual([buildings[1]]);
  });
  it("turns API enum values into readable labels", () => {
    expect(formatLevel("worth_a_look")).toBe("Investigate");
    expect(formatLevel("space_per_hospice")).toBe("Space Per Hospice");
  });
  it("keeps the disclaimer explicit", () => {
    expect("Review priorities are screening aids, not findings of fraud.").toContain("not findings of fraud");
  });
  it("preserves geographic coordinates and rejects missing or invalid pairs", () => {
    expect(buildingPosition(buildings[0])).toEqual([34.0522, -118.2437]);
    expect(buildingPosition(buildings[1])).toBeNull();
    expect(buildingPosition({ ...buildings[0], latitude: 34.9 })).toEqual([34.9, -118.2437]);
    expect(buildingPosition({ ...buildings[0], longitude: null })).toBeNull();
    expect(buildingPosition({ ...buildings[0], latitude: NaN })).toBeNull();
    expect(buildingPosition({ ...buildings[0], longitude: 181 })).toBeNull();
  });
});
