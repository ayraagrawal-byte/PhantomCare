"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AnalysisSummary,
  BuildingDetail,
  BuildingListItem,
  ReviewLevel,
  fetchAnalysis,
  filterBuildings,
  formatLevel,
} from "../lib/analysis";

const filters: Array<{ label: string; value: ReviewLevel | "all" }> = [
  { label: "All buildings", value: "all" },
  { label: "High priority", value: "high_priority" },
  { label: "Worth a look", value: "worth_a_look" },
  { label: "No indicators", value: "no_indicators_found" },
];

export default function Home() {
  const [summary, setSummary] = useState<AnalysisSummary | null>(null);
  const [buildings, setBuildings] = useState<BuildingListItem[]>([]);
  const [selected, setSelected] = useState<BuildingDetail | null>(null);
  const [level, setLevel] = useState<ReviewLevel | "all">("all");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetchAnalysis(controller.signal)
      .then((result) => {
        setSummary(result.summary);
        setBuildings(result.buildings);
        setStatus("ready");
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "Analysis could not be loaded.");
        setStatus("error");
      });
    return () => controller.abort();
  }, []);

  const visible = useMemo(
    () => filterBuildings(buildings, level, query),
    [buildings, level, query],
  );

  async function inspectBuilding(buildingId: string) {
    try {
      const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const response = await fetch(`${base}/analysis/buildings/${buildingId}`);
      if (!response.ok) throw new Error(`Building detail returned ${response.status}.`);
      setSelected((await response.json()) as BuildingDetail);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Building detail could not be loaded.");
    }
  }

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#top" aria-label="PhantomCare home">
          <span className="brand-mark">P</span><span>PhantomCare</span>
        </a>
        <div className="run-status" aria-live="polite">
          <span className={`status-dot ${status}`} />
          {status === "loading" ? "Loading analysis" : status === "ready" ? "Analysis online" : "Analysis unavailable"}
        </div>
      </header>

      <section className="intro" id="top">
        <div>
          <p className="eyebrow">Los Angeles County · Review workspace</p>
          <h1>Building signals,<br />with the evidence attached.</h1>
        </div>
        <p className="lede">
          Rank hospice registration clusters using explainable public-record and building-context
          indicators. Every score shows its inputs, limitations, and missing data.
        </p>
      </section>

      {status === "error" && (
        <section className="error-panel" role="alert">
          <strong>Analysis is not available.</strong><span>{error}</span>
          <code>python -m pipeline.analysis … --output data/analysis</code>
        </section>
      )}

      <section className="metrics" aria-label="Analysis summary">
        <Metric label="Hospice enrollments" value={summary?.enrollment_count} />
        <Metric label="Physical buildings" value={summary?.building_count} />
        <Metric label="High priority" value={summary?.high_priority_count} tone="hot" />
        <Metric label="Worth a look" value={summary?.worth_a_look_count} tone="watch" />
      </section>

      <section className="workspace">
        <div className="list-panel">
          <div className="section-heading">
            <div><p className="section-label">Review queue</p><h2>Ranked buildings</h2></div>
            <label className="search">
              <span className="sr-only">Search addresses</span>
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search address or building ID" type="search" />
            </label>
          </div>
          <div className="filters" aria-label="Filter review level">
            {filters.map((filter) => (
              <button className={level === filter.value ? "active" : ""} key={filter.value} onClick={() => setLevel(filter.value)} type="button">
                {filter.label}
              </button>
            ))}
          </div>
          <div className="building-list" aria-busy={status === "loading"}>
            {status === "loading" && [1, 2, 3].map((item) => <div className="skeleton" key={item} />)}
            {status === "ready" && visible.length === 0 && <p className="empty-state">No buildings match this view.</p>}
            {visible.map((building, index) => (
              <button className="building-row" key={building.building_id} onClick={() => inspectBuilding(building.building_id)} type="button">
                <span className="rank">{String(index + 1).padStart(2, "0")}</span>
                <span className="building-main">
                  <strong>{building.building_key}</strong>
                  <small>{building.hospice_count} hospices · {building.strong_indicator_count} strong signals</small>
                </span>
                <span className={`level level-${building.review_level}`}>{formatLevel(building.review_level)}</span>
                <span className="score">{Math.round(building.total_score)}</span>
              </button>
            ))}
          </div>
        </div>
        <aside className="inspector" aria-live="polite">
          {selected ? <BuildingInspector building={selected} /> : <InspectorEmpty />}
        </aside>
      </section>

      <footer>
        <span>{summary?.disclaimer ?? "Review priorities are screening aids, not findings of fraud."}</span>
        <span>{summary ? `Analysis generated ${new Date(summary.generated_at).toLocaleString()}` : "Awaiting analysis artifacts"}</span>
      </footer>
    </main>
  );
}

function Metric({ label, value, tone = "default" }: { label: string; value?: number; tone?: string }) {
  return <article className={`metric metric-${tone}`}><span>{label}</span><strong>{value ?? "—"}</strong></article>;
}

function InspectorEmpty() {
  return (
    <div className="inspector-empty">
      <span className="crosshair" aria-hidden="true">＋</span><p className="section-label">Evidence inspector</p>
      <h2>Select a building</h2><p>Open a ranked building to inspect its score, evidence, missing inputs, and limitations.</p>
    </div>
  );
}

function BuildingInspector({ building }: { building: BuildingDetail }) {
  return (
    <div>
      <div className="inspector-head">
        <p className="section-label">Evidence inspector</p><span className="big-score">{Math.round(building.priority.score.total)}</span>
        <h2>{building.building_key}</h2><p>{building.priority.claim_reason}</p>
      </div>
      <dl className="facts">
        <div><dt>Hospices</dt><dd>{building.hospice_count}</dd></div>
        <div><dt>CoStar match</dt><dd>{building.costar_match_status.replaceAll("_", " ")}</dd></div>
        <div><dt>Model</dt><dd>{building.priority.score.model_version}</dd></div>
      </dl>
      {building.priority.missing_indicators.length > 0 && (
        <div className="missing-note">Missing data: {building.priority.missing_indicators.map(formatLevel).join(", ")}. Available weights were rebalanced.</div>
      )}
      <div className="indicator-stack">
        {building.indicators.map((indicator) => (
          <article key={indicator.indicator}>
            <div className="indicator-title"><strong>{formatLevel(indicator.indicator)}</strong><span>{Math.round(indicator.score_contribution)} / 100</span></div>
            <div className="bar"><span style={{ width: `${indicator.score_contribution}%` }} /></div>
            <p>{indicator.evidence.length} evidence records</p>
            {indicator.limitations.map((limitation) => <small key={limitation}>{limitation}</small>)}
          </article>
        ))}
      </div>
    </div>
  );
}
