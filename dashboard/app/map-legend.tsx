"use client";

import { useId, useMemo, useState } from "react";
import { buildingPosition, filterBuildings, formatLevel, type BuildingListItem } from "../lib/analysis";

const categories = [
  { id: "neutral", label: "No Indicators Found", matches: (building: BuildingListItem) => building.review_level === "no_indicators_found" },
  { id: "watch", label: "Investigate", matches: (building: BuildingListItem) => building.review_level === "worth_a_look" },
  { id: "verified", label: "Verified Address Point", matches: (building: BuildingListItem) => Boolean(building.verified_location && buildingPosition(building)) },
  { id: "approximate", label: "Approximate Location", matches: (building: BuildingListItem) => Boolean(building.approximate_location && buildingPosition(building)) },
  { id: "hot", label: "High priority", matches: (building: BuildingListItem) => building.review_level === "high_priority" },
] as const;

type Category = (typeof categories)[number];
const pageSize = 25;

export default function MapLegend({ buildings, selectedId, onSelect }: {
  buildings: BuildingListItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const panelId = useId();
  const [active, setActive] = useState<Category | null>(null);
  const matches = useMemo(() => active ? buildings.filter(active.matches) : [], [active, buildings]);

  return (
    <>
      <div className="map-legend" role="group" aria-label="Map legend">
        {categories.filter((category) => category.id !== "hot" || buildings.some(category.matches)).map((category) => (
          <button key={category.id} type="button" aria-expanded={active === category} aria-controls={panelId}
            onClick={() => setActive(active === category ? null : category)}>
            <i className={`legend-${category.id}`} aria-hidden="true" />
            {category.label}
            <span className="queue-chevron" aria-hidden="true" />
          </button>
        ))}
      </div>
      <div id={panelId} hidden={!active}>
        {active && <LegendResults key={active.id} title={active.label} buildings={matches} selectedId={selectedId} onSelect={onSelect} />}
      </div>
    </>
  );
}

function LegendResults({ title, buildings, selectedId, onSelect }: {
  title: string;
  buildings: BuildingListItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const titleId = useId();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const matches = useMemo(() => filterBuildings(buildings, "all", query).sort((a, b) => b.total_score - a.total_score), [buildings, query]);
  const current = Math.min(page, Math.max(0, Math.ceil(matches.length / pageSize) - 1));
  const start = current * pageSize;
  const end = Math.min(start + pageSize, matches.length);

  return (
    <section className="legend-results" aria-labelledby={titleId}>
      <header>
        <h2 id={titleId}>{title} <span>{buildings.length.toLocaleString()} buildings</span></h2>
        <input type="search" aria-label={`Search ${title} buildings`} placeholder="Search address or building ID"
          value={query} onChange={(event) => { setQuery(event.target.value); setPage(0); }} />
      </header>
      {matches.length ? (
        <ul className="legend-building-list">
          {matches.slice(start, end).map((building) => (
            <li key={building.building_id}>
              <button type="button" aria-pressed={selectedId === building.building_id} onClick={() => onSelect(building.building_id)}>
                <strong>{building.building_key}</strong>
                <span>{formatLevel(building.review_level)}</span>
                <span className="legend-score" aria-label={`Review score ${Math.round(building.total_score)}`}>{Math.round(building.total_score)}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : <p className="panel-message">No buildings match this view.</p>}
      <div className="legend-pagination">
        <span role="status">{matches.length ? `${start + 1}–${end} of ${matches.length.toLocaleString()}` : "0 results"}</span>
        <button type="button" disabled={current === 0} onClick={() => setPage(current - 1)}>Previous</button>
        <button type="button" disabled={end >= matches.length} onClick={() => setPage(current + 1)}>Next</button>
      </div>
    </section>
  );
}
