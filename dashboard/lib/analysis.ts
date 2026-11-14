export type ReviewLevel = "high_priority" | "worth_a_look" | "no_indicators_found";

export interface AnalysisSummary {
  generated_at: string;
  enrollment_count: number;
  building_count: number;
  high_priority_count: number;
  worth_a_look_count: number;
  disclaimer: string;
}

export interface BuildingListItem {
  building_id: string;
  building_key: string;
  hospice_count: number;
  total_score: number;
  review_level: ReviewLevel;
  strong_indicator_count: number;
  costar_match_status: string;
  latitude: number | null;
  longitude: number | null;
}

interface Indicator {
  indicator: string;
  score_contribution: number;
  evidence: unknown[];
  limitations: string[];
}

export interface BuildingDetail {
  building_id: string;
  building_key: string;
  hospice_count: number;
  costar_match_status: string;
  indicators: Indicator[];
  priority: {
    score: { total: number; level: ReviewLevel; model_version: string };
    missing_indicators: string[];
    strong_indicators: string[];
    claim_reason: string;
  };
}

export interface BuildingNetwork {
  building_id: string;
  nodes: Array<{ id: string; label: string; kind: "building" | "owner" | "hospice"; is_masked: boolean; count: number }>;
  links: Array<{ source: string; target: string }>;
  limitations: string[];
}

interface Finding {
  title: string;
  summary: string;
  strength: number;
  evidence: unknown[];
  limitations: string[];
}

export interface InvestigationResult {
  target_id: string;
  case_file: null | {
    case_id: string;
    created_at: string;
    disclaimer: string;
    findings: Finding[];
  };
  trace: Array<{
    event_id: string;
    event_type: string;
    message: string;
    occurred_at: string;
  }>;
  stopped_reason: string | null;
}

const apiUrl = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function getJson<T>(path: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(`${apiUrl}${path}`, { signal });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: { message?: string };
    } | null;
    throw new Error(body?.detail?.message ?? `Analysis API returned ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export async function fetchAnalysis(signal: AbortSignal) {
  const [summary, buildings] = await Promise.all([
    getJson<AnalysisSummary>("/analysis/summary", signal),
    getJson<BuildingListItem[]>("/analysis/buildings?limit=500", signal),
  ]);
  return { summary, buildings };
}

export async function fetchCaseForTarget(
  targetId: string,
): Promise<InvestigationResult | null> {
  const response = await fetch(`${apiUrl}/cases/targets/${targetId}`);
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Case API returned ${response.status}.`);
  return response.json() as Promise<InvestigationResult>;
}

export async function fetchBuildingNetwork(targetId: string): Promise<BuildingNetwork> {
  const response = await fetch(`${apiUrl}/analysis/buildings/${targetId}/network`);
  if (!response.ok) throw new Error(`Network API returned ${response.status}.`);
  return response.json() as Promise<BuildingNetwork>;
}

export function filterBuildings(
  buildings: BuildingListItem[],
  level: ReviewLevel | "all",
  query: string,
): BuildingListItem[] {
  const term = query.trim().toLowerCase();
  return buildings.filter((building) => {
    const matchesLevel = level === "all" || building.review_level === level;
    const matchesQuery =
      !term ||
      building.building_key.toLowerCase().includes(term) ||
      building.building_id.toLowerCase().includes(term);
    return matchesLevel && matchesQuery;
  });
}

export function formatLevel(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function projectLaPoint(latitude: number, longitude: number): { x: number; y: number } | null {
  const bounds = { north: 34.82, south: 33.68, west: -118.95, east: -117.63 };
  if (latitude < bounds.south || latitude > bounds.north || longitude < bounds.west || longitude > bounds.east) return null;
  return {
    x: ((longitude - bounds.west) / (bounds.east - bounds.west)) * 100,
    y: ((bounds.north - latitude) / (bounds.north - bounds.south)) * 100,
  };
}
