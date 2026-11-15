"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AnalysisSummary,
  AerialEvidence,
  BuildingDetail,
  BuildingNetwork,
  BuildingListItem,
  InvestigationResult,
  InteractiveInvestigation,
  ReviewLevel,
  fetchAnalysis,
  fetchAerialEvidence,
  fetchBuildingDetail,
  fetchCaseForTarget,
  fetchBuildingNetwork,
  filterBuildings,
  formatLevel,
  absoluteApiUrl,
  runInteractiveInvestigation,
} from "../lib/analysis";

const HotspotMap = dynamic(() => import("./hotspot-map"), {
  ssr: false,
  loading: () => <section className="map-panel"><div className="map-copy"><h2>LA County hotspots</h2><p role="status">Loading map?</p></div></section>,
});

const filters: Array<{ label: string; value: ReviewLevel | "all" }> = [
  { label: "All buildings", value: "all" },
  { label: "High priority", value: "high_priority" },
  { label: "Worth a look", value: "worth_a_look" },
  { label: "No indicators", value: "no_indicators_found" },
];

export default function Home() {
  const [summary, setSummary] = useState<AnalysisSummary | null>(null);
  const [buildings, setBuildings] = useState<BuildingListItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selected, setSelected] = useState<BuildingDetail | null>(null);
  const [caseResult, setCaseResult] = useState<InvestigationResult | null>(null);
  const [network, setNetwork] = useState<BuildingNetwork | null>(null);
  const [aerial, setAerial] = useState<AerialEvidence | null>(null);
  const [agentResult, setAgentResult] = useState<InteractiveInvestigation | null>(null);
  const [agentStatus, setAgentStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [caseStatus, setCaseStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [level, setLevel] = useState<ReviewLevel | "all">("all");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const selectionRequest = useRef(0);
  const [error, setError] = useState("");
  const [mapWarning, setMapWarning] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetchAnalysis(controller.signal)
      .then((result) => {
        setSummary(result.summary);
        setBuildings(result.buildings);
        setMapWarning(result.mapWarning);
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
    const requestId = ++selectionRequest.current;
    setSelectedId(buildingId);
    setSelected(null);
    setError("");
    setCaseStatus("loading");
    setCaseResult(null);
    setNetwork(null);
    setAerial(null);
    setAgentResult(null);
    setAgentStatus("idle");
    try {
      const [detailOutcome, caseOutcome, networkOutcome, aerialOutcome] = await Promise.allSettled([
        fetchBuildingDetail(buildingId),
        fetchCaseForTarget(buildingId),
        fetchBuildingNetwork(buildingId),
        fetchAerialEvidence(buildingId),
      ]);
      if (requestId !== selectionRequest.current) return;
      if (detailOutcome.status === "rejected") throw detailOutcome.reason;
      setSelected(detailOutcome.value);
      if (caseOutcome.status === "fulfilled") {
        setCaseResult(caseOutcome.value);
        setCaseStatus("ready");
      } else {
        setCaseStatus("error");
      }
      if (networkOutcome.status === "fulfilled") setNetwork(networkOutcome.value);
      if (aerialOutcome.status === "fulfilled") setAerial(aerialOutcome.value);
    } catch (reason) {
      if (requestId !== selectionRequest.current) return;
      setSelected(null);
      setSelectedId(null);
      setError(reason instanceof Error ? reason.message : "Building detail could not be loaded.");
      setCaseStatus("error");
    }
  }

  async function runAgentInvestigation(buildingId: string) {
    setAgentStatus("loading");
    setAgentResult(null);
    try {
      setAgentResult(await runInteractiveInvestigation(buildingId));
      setAgentStatus("ready");
    } catch {
      setAgentStatus("error");
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
          <span className="dataset-note">Data snapshot: CMS Q4 2026 public records with CoStar and Vexcel hackathon evidence.</span>
        </p>
      </section>

      {status === "error" && (
        <section className="error-panel" role="alert">
          <strong>Analysis is temporarily unavailable.</strong>
          <span>Check your connection and reload the page. {error}</span>
        </section>
      )}

      <section className="metrics" aria-label="Analysis summary">
        <Metric label="Hospice enrollments" value={summary?.enrollment_count} />
        <Metric label="Physical buildings" value={summary?.building_count} />
        <Metric label="High priority" value={summary?.high_priority_count} tone="hot" />
        <Metric label="Worth a look" value={summary?.worth_a_look_count} tone="watch" />
      </section>

      <HotspotMap buildings={buildings} total={summary?.building_count ?? buildings.length}
        status={status} warning={mapWarning} selectedId={selectedId} onSelect={(buildingId) => {
          if (!visible.some((building) => building.building_id === buildingId)) {
            setLevel("all");
            setQuery("");
          }
          if (buildingId !== selectedId) void inspectBuilding(buildingId);
        }} />

      <section className="workspace">
        <div className="list-panel">
          <div className="section-heading">
            <div><p className="section-label">Review queue</p><h2>Ranked buildings</h2><p className="result-count">Showing {visible.length} of {buildings.length} buildings</p></div>
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
              <button className="building-row" aria-pressed={selectedId === building.building_id} key={building.building_id} onClick={() => inspectBuilding(building.building_id)} type="button">
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
        <aside className="inspector" id="building-evidence" aria-live="polite">
          {selected ? <BuildingInspector building={selected} aerial={aerial} network={network} caseResult={caseResult} caseStatus={caseStatus} agentResult={agentResult} agentStatus={agentStatus} onInvestigate={() => runAgentInvestigation(selected.building_id)} /> : caseStatus === "loading" ? <div className="inspector-empty" role="status">Loading building evidence…</div> : caseStatus === "error" ? <div className="inspector-empty" role="alert">Could not load building evidence. {error}</div> : <InspectorEmpty />}
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

function BuildingInspector({ building, aerial, network, caseResult, caseStatus, agentResult, agentStatus, onInvestigate }: { building: BuildingDetail; aerial: AerialEvidence | null; network: BuildingNetwork | null; caseResult: InvestigationResult | null; caseStatus: string; agentResult: InteractiveInvestigation | null; agentStatus: string; onInvestigate: () => void }) {
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
      <BuildingContextCard building={building} />
      {aerial && <AerialCard evidence={aerial} />}
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
      <FusionPanel result={agentResult} status={agentStatus} onInvestigate={onInvestigate} />
      <CasePanel result={caseResult} status={caseStatus} />
    </div>
  );
}

function FusionPanel({ result, status, onInvestigate }: { result: InteractiveInvestigation | null; status: string; onInvestigate: () => void }) {
  return (
    <section className="fusion-panel">
      <div className="fusion-heading"><div><p className="section-label">Cross-source investigation</p><h3>CMS + CoStar + Vexcel</h3></div>{result && <span className={`agent-mode mode-${result.mode}`}>{result.mode === "live_ai" ? "Live AI" : "Deterministic fallback"}</span>}</div>
      <p className="case-muted">Run a bounded, read-only investigation. Screening scores remain deterministic and unchanged.</p>
      <ol className="investigation-flow" aria-label="Investigation stages"><li>Registration anomaly</li><li>Physical-property evidence</li><li>Cross-source comparison</li><li>Uncertainty</li><li>Human action</li></ol>
      <button className="investigate-button" disabled={status === "loading"} onClick={onInvestigate} type="button">{status === "loading" ? "Investigating…" : "Investigate this building"}</button>
      {status === "error" && <p className="fusion-error" role="alert">The interactive investigation could not be completed.</p>}
      {result && <>
        {result.fallback_reason && <p className="fallback-reason">Live AI was not used: {formatLevel(result.fallback_reason)}.</p>}
        <p className="fusion-summary">{result.reasoning_summary}</p>
        <div className="fusion-grid">{result.fusion_layers.map((layer) => <article key={layer.source}><strong>{layer.source}</strong>{layer.data_class && <span className={`data-class data-class-${layer.data_class}`}>{DATA_CLASS_LABELS[layer.data_class]}</span>}{layer.establishes.map((fact) => <p key={fact}>{fact}</p>)}<small>{layer.evidence_references.length ? `${layer.evidence_references.length} evidence reference(s)` : "No source record available"}</small>{layer.limitations.map((item) => <em key={item}>{item}</em>)}</article>)}</div>
        {result.cross_source_comparison && <ComparisonPanel comparison={result.cross_source_comparison} />}
        <div className="next-step"><strong>Recommended next step</strong><p>{result.recommended_next_step}</p></div>
        {result.review_checklist && result.review_checklist.length > 0 && <div className="review-checklist"><strong>Human-review checklist</strong><ul>{result.review_checklist.map((item) => <li key={item}>{item}</li>)}</ul></div>}
        {result.unknowns.length > 0 && <details><summary>What remains unknown</summary><ul>{result.unknowns.map((item) => <li key={item}>{item}</li>)}</ul></details>}
        <details><summary>Inspect {result.tool_trace.length} genuine tool calls</summary><div className="tool-trace">{result.tool_trace.map((event, index) => <article key={`${event.tool_name}-${index}`}><strong>{event.tool_name}</strong><p>{event.result_summary}</p><small>{event.evidence_references.join(" · ") || "No evidence reference returned"}</small></article>)}</div></details>
        <small className="fusion-disclaimer">{result.disclaimer}</small>
      </>}
    </section>
  );
}

const DATA_CLASS_LABELS = {
  public_record: "Public CMS record",
  derived_masked: "Derived · owners masked",
  licensed_property_data: "Licensed CoStar data",
  aerial_imagery: "Vexcel aerial imagery",
} as const;

function ComparisonPanel({ comparison }: { comparison: NonNullable<InteractiveInvestigation["cross_source_comparison"]> }) {
  return (
    <div className="comparison-panel">
      <strong>Cross-source comparison</strong>
      <small>Compared: {comparison.sources_compared.join(" + ")}</small>
      {comparison.combined_observations.length > 0 && <><h4>What becomes clearer combined</h4><ul>{comparison.combined_observations.map((item) => <li key={item}>{item}</li>)}</ul></>}
      <h4>Still uncertain</h4><ul>{comparison.remains_uncertain.map((item) => <li key={item}>{item}</li>)}</ul>
      <h4>Records to request</h4><ul>{comparison.records_to_request.map((item) => <li key={item}>{item}</li>)}</ul>
    </div>
  );
}

const MATTERPORT_MODEL_ID = /^[A-Za-z0-9]{11}$/;

function AerialCard({ evidence }: { evidence: AerialEvidence }) {
  return (
    <figure className="aerial-card">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img alt={`Vexcel ortho context for ${evidence.address}`} src={absoluteApiUrl(evidence.image_url)} />
      <figcaption><div><p className="section-label">Vexcel aerial context</p><strong>Verified ortho imagery</strong></div><span>{new Date(evidence.retrieved_at).toLocaleDateString()}</span></figcaption>
      <small>{evidence.limitations[0]}</small>
    </figure>
  );
}

function BuildingContextCard({ building }: { building: BuildingDetail }) {
  const context = building.building_context;
  if (!context) return <section className="context-card context-missing"><p className="section-label">CoStar building context</p><p>No exact property record is available for this address.</p></section>;
  const area = context.rentable_building_area_sqft ?? context.gross_building_area_sqft;
  return (
    <section className="context-card">
      <div className="context-heading"><div><p className="section-label">CoStar building context</p><h3>{context.building_name ?? context.property_type ?? "Matched property"}</h3></div><span>Property {context.property_id}</span></div>
      <div className="context-grid">
        <div><span>Type</span><strong>{[context.property_type, context.property_subtype].filter(Boolean).join(" · ") || "Not reported"}</strong></div>
        <div><span>Area</span><strong>{area ? `${Math.round(area).toLocaleString()} sq ft` : "Not reported"}</strong></div>
        <div><span>Floors</span><strong>{context.stories_above_grade ?? context.floor_count ?? "Not reported"}</strong></div>
        <div><span>Occupancy records</span><strong>{context.occupancy_record_count}</strong></div>
        <div><span>Unique tenant locations</span><strong>{context.unique_tenant_location_count}</strong></div>
        <div><span>Matterport</span><strong>{context.matterport_model_ids.length ? `${context.matterport_model_ids.length} model available` : "No model linked"}</strong></div>
      </div>
      {context.occupancy_scope && <small className="context-caveat">Occupancy count scope: {context.occupancy_scope.replaceAll("_", " ")}.</small>}
      {context.matterport_model_ids.filter((id) => MATTERPORT_MODEL_ID.test(id)).slice(0, 1).map((id) => (
        <p className="matterport-link" key={id}>
          <a href={`https://my.matterport.com/show/?m=${id}`} rel="noopener noreferrer" target="_blank">Open sponsor-linked Matterport model ↗</a>
          <small>Linked to CoStar property {context.property_id} in the sponsor dataset. Hosted by Matterport; it shows the property, not any specific hospice suite, and is not evidence of occupancy.</small>
        </p>
      ))}
      <small className="context-caveat">Licensed CoStar data, shown in-app for the hackathon only.</small>
    </section>
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
      <p className="section-label">Evidence review</p>
      {status === "loading" && <p className="case-muted">Loading case trace…</p>}
      {status === "error" && <p className="case-muted">The case artifact could not be loaded.</p>}
      {status === "ready" && !result && <p className="case-muted">No investigation has been generated for this building.</p>}
      {result?.stopped_reason && (
        <div className="early-stop"><strong>Stopped early</strong><span>{result.stopped_reason}</span></div>
      )}
      {result?.case_file && (
        <>
          <div className="case-heading"><h3>Case file</h3><code>{result.case_file.case_id}</code></div>
          <a className="download-case" href={absoluteApiUrl(`/cases/${result.case_file.case_id}/download`)}>Download JSON case file</a>
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
          <h3>Deterministic review trace</h3>
          {result.trace.map((event) => (
            <div key={event.event_id}><span>{formatLevel(event.event_type)}</span><p>{event.message}</p></div>
          ))}
        </div>
      )}
    </section>
  );
}
