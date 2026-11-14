"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AnalysisSummary,
  BuildingDetail,
  BuildingNetwork,
  BuildingListItem,
  InvestigationResult,
  ReviewLevel,
  fetchAnalysis,
  fetchCaseForTarget,
  fetchBuildingNetwork,
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
  const [caseResult, setCaseResult] = useState<InvestigationResult | null>(null);
  const [network, setNetwork] = useState<BuildingNetwork | null>(null);
  const [caseStatus, setCaseStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
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
    setCaseStatus("loading");
    setCaseResult(null);
    setNetwork(null);
    try {
      const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const [detailOutcome, caseOutcome, networkOutcome] = await Promise.allSettled([
        fetch(`${base}/analysis/buildings/${buildingId}`),
        fetchCaseForTarget(buildingId),
        fetchBuildingNetwork(buildingId),
      ]);
      if (detailOutcome.status === "rejected") throw detailOutcome.reason;
      const response = detailOutcome.value;
      if (!response.ok) throw new Error(`Building detail returned ${response.status}.`);
      setSelected((await response.json()) as BuildingDetail);
      if (caseOutcome.status === "fulfilled") {
        setCaseResult(caseOutcome.value);
        setCaseStatus("ready");
      } else {
        setCaseStatus("error");
      }
      if (networkOutcome.status === "fulfilled") setNetwork(networkOutcome.value);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Building detail could not be loaded.");
      setCaseStatus("error");
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
          {selected ? <BuildingInspector building={selected} network={network} caseResult={caseResult} caseStatus={caseStatus} /> : <InspectorEmpty />}
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

function BuildingInspector({ building, network, caseResult, caseStatus }: { building: BuildingDetail; network: BuildingNetwork | null; caseResult: InvestigationResult | null; caseStatus: string }) {
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
      <NetworkPanel network={network} />
      <CasePanel result={caseResult} status={caseStatus} />
    </div>
  );
}

function NetworkPanel({ network }: { network: BuildingNetwork | null }) {
  if (!network) return <section className="network-panel"><p className="section-label">Ownership network</p><p className="case-muted">No linked ownership network is available.</p></section>;
  const owners = network.nodes.filter((node) => node.kind === "owner");
  const hospices = network.nodes.filter((node) => node.kind === "hospice");
  return (
    <section className="network-panel">
      <div className="network-heading"><p className="section-label">Ownership network</p><span>{network.links.length} links</span></div>
      <div className="network-graph" aria-label={`Network with ${hospices.length} hospices and ${owners.length} owners`}>
        <div className="network-column"><span className="network-node building-node">Selected building</span></div>
        <div className="network-column">{hospices.slice(0, 8).map((node) => <span className="network-node hospice-node" key={node.id}>{node.label}</span>)}</div>
        <div className="network-column">{owners.slice(0, 8).map((node) => <span className="network-node owner-node" key={node.id}>{node.label}{node.is_masked ? " · masked" : ""}<small>{node.count} linked</small></span>)}</div>
      </div>
      {network.nodes.length > 17 && <p className="network-more">Showing the first eight hospices and owners.</p>}
      <small className="network-limit">{network.limitations[1]}</small>
    </section>
  );
}

function CasePanel({ result, status }: { result: InvestigationResult | null; status: string }) {
  return (
    <section className="case-panel">
      <p className="section-label">Guided investigation</p>
      {status === "loading" && <p className="case-muted">Loading case trace…</p>}
      {status === "error" && <p className="case-muted">The case artifact could not be loaded.</p>}
      {status === "ready" && !result && <p className="case-muted">No investigation has been generated for this building.</p>}
      {result?.stopped_reason && (
        <div className="early-stop"><strong>Stopped early</strong><span>{result.stopped_reason}</span></div>
      )}
      {result?.case_file && (
        <>
          <div className="case-heading"><h3>Case file</h3><code>{result.case_file.case_id}</code></div>
          <p className="case-disclaimer">{result.case_file.disclaimer}</p>
          <div className="finding-list">
            {result.case_file.findings.map((finding) => (
              <article key={finding.title}>
                <div><strong>{finding.title}</strong><span>{Math.round(finding.strength * 100)}% strength</span></div>
                <p>{finding.summary}</p>
                <small>{finding.evidence.length} attached evidence record{finding.evidence.length === 1 ? "" : "s"}</small>
              </article>
            ))}
          </div>
        </>
      )}
      {result && (
        <div className="trace-list">
          <h3>Investigation trace</h3>
          {result.trace.map((event) => (
            <div key={event.event_id}><span>{formatLevel(event.event_type)}</span><p>{event.message}</p></div>
          ))}
        </div>
      )}
    </section>
  );
}
