"use client";

import { useState, type CSSProperties, type KeyboardEvent } from "react";
import type { BuildingListItem, ReviewLevel } from "../lib/analysis";

export const reviewLabels: Record<ReviewLevel, string> = {
  high_priority: "High Priority",
  worth_a_look: "Investigate",
  no_indicators_found: "No Flags",
};

const scoreGroups = [
  { minimum: 80, label: "Score 80–100" },
  { minimum: 60, label: "Score 60–79" },
  { minimum: 40, label: "Score 40–59" },
  { minimum: 0, label: "Score 0–39" },
];

function navigate(event: KeyboardEvent<HTMLDivElement>) {
  if (!(event.target instanceof HTMLButtonElement) || !event.target.matches(".building-row")) return;
  const rows = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>(":scope > div > .building-row"));
  const index = rows.indexOf(event.target);
  const next = {
    ArrowDown: rows[index + 1],
    ArrowUp: rows[index - 1],
    Home: rows[0],
    End: rows.at(-1),
  }[event.key];
  if (!next) return;
  event.preventDefault();
  next.focus();
}

export default function AnimatedBuildingList({
  buildings, selectedId, reveal, showMatches, hideEmpty, onSelect,
}: {
  buildings: BuildingListItem[];
  selectedId: string | null;
  reveal: { id: string } | null;
  showMatches: boolean;
  hideEmpty: boolean;
  onSelect: (id: string) => void;

}) {
  const [toggles, setToggles] = useState<Record<number, { open: boolean; reveal: typeof reveal }>>({});
  const groups = scoreGroups.map((group) => ({ ...group, rows: [] as BuildingListItem[] }));
  for (const building of buildings) {
    const score = Math.round(building.total_score);
    const group = groups.find(({ minimum }) => score >= minimum) ?? groups[groups.length - 1];
    group.rows.push(building);
  }

  return (
    <div className="animated-building-list" role="group" aria-label="Ranked building results">
      {groups.filter(({ rows }) => !hideEmpty || rows.length > 0).map(({ minimum, label, rows }, index, displayedGroups) => {

        const revealed = reveal !== null && rows.some(({ building_id }) => reveal.id === building_id);
        const toggle = toggles[minimum];
        const open = toggle && (!revealed || toggle.reveal === reveal)
          ? toggle.open
          : revealed || index === 0 || showMatches;
        const firstRank = displayedGroups.slice(0, index).reduce((count, group) => count + group.rows.length, 0);
        return (
          <section className="score-group" data-score-minimum={minimum} key={minimum}>
            <h3>
              <button type="button" className="score-group-toggle" aria-expanded={open}
                aria-controls={`score-group-${minimum}`}
                onClick={() => setToggles({ ...toggles, [minimum]: { open: !open, reveal } })}>
                <span className="queue-chevron" aria-hidden="true" />
                <span>{label}</span>
                <span className="group-count" aria-label={`${rows.length} buildings`}>{rows.length}</span>
              </button>
            </h3>
            <div id={`score-group-${minimum}`} hidden={!open}
              className="score-group-rows" onKeyDown={navigate}>
              {open && rows.map((building, rowIndex) => {
                    const expanded = selectedId === building.building_id;
                    return (
                      <div key={building.building_id}>
                        <button type="button"
                          className={rowIndex < 8 ? "building-row building-row-enter" : "building-row"}
                          style={rowIndex < 8 ? { "--row-index": rowIndex } as CSSProperties : undefined}
                          aria-expanded={expanded} aria-controls="building-evidence"
                          onClick={() => onSelect(building.building_id)}>
                          <span className="rank">{String(firstRank + rowIndex + 1).padStart(2, "0")}</span>
                          <span className="building-main"><strong>{building.building_key}</strong></span>
                          <span className={`level level-${building.review_level}`}>{reviewLabels[building.review_level]}</span>
                          <span className="score">{Math.round(building.total_score)}</span>
                          <span className="queue-chevron" aria-hidden="true" />
                        </button>
                      </div>
                    );
                  })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
