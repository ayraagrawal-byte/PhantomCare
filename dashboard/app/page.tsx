"use client";

import dynamic from "next/dynamic";
import AppHeader from "./app-header";
import Assessment from "./assessment";
import AnimatedBuildingList, { reviewLabels } from "./animated-building-list";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
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
  loading: () => <div className="hotspot-placeholder" role="status">Loading map...</div>,
});

const filters: Array<{ label: string; value: ReviewLevel | "all" }> = [
  { label: "All Buildings", value: "all" },
  { label: reviewLabels.worth_a_look, value: "worth_a_look" },
  { label: reviewLabels.no_indicators_found, value: "no_indicators_found" },
];

const mobileQueueQuery = "(max-width: 760px)";

function subscribeToQueueViewport(onChange: () => void) {
  const viewport = window.matchMedia(mobileQueueQuery);
  viewport.addEventListener("change", onChange);
  return () => viewport.removeEventListener("change", onChange);
}

export default function Home() {
  const mobileQueue = useSyncExternalStore(subscribeToQueueViewport, () => window.matchMedia(mobileQueueQuery).matches, () => false);
  const [queuePreference, setQueuePreference] = useState<boolean | null>(null);
  const queueOpen = queuePreference ?? !mobileQueue;
  const [summary, setSummary] = useState<AnalysisSummary | null>(null);
  const [buildings, setBuildings] = useState<BuildingListItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mapReveal, setMapReveal] = useState<{ id: string } | null>(null);
  const [mapFocus, setMapFocus] = useState<{ buildingId: string } | null>(null);
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
    () => filterBuildings(buildings, level, query).sort((a, b) => b.total_score - a.total_score),
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
      setError(reason instanceof Error ? reason.message : "Building detail could not be loaded.");
      setCaseStatus("error");
    }
  }

  async function runAgentInvestigation(buildingId: string) {
    const requestId = selectionRequest.current;
    setAgentStatus("loading");
    setAgentResult(null);
    try {
      const result = await runInteractiveInvestigation(buildingId);
      if (requestId !== selectionRequest.current) return;
      setAgentResult(result);
      setAgentStatus("ready");
    } catch {
      if (requestId === selectionRequest.current) setAgentStatus("error");
    }
  }

  const ranked = [...buildings].sort((a, b) => b.total_score - a.total_score);
  const rank = ranked.findIndex(({ building_id }) => building_id === selectedId);
  const active = ranked[rank];

  return (
    <>
      <AppHeader />
      <main>
      {status === "error" && (
        <section className="error-panel" role="alert">
          <strong>Analysis is temporarily unavailable.</strong>
          <span>Check your connection and reload the page. {error}</span>
        </section>
      )}

      <div className="investigation-grid" data-queue-open={queueOpen}>
        <header className="case-heading-bar" id="investigations">
          <h1>{active ? <><span>Case {String(rank + 1).padStart(2, "0")}</span>{active.building_key}</> : "Investigate Healthcare Facilities"}</h1>
          <div className="case-heading-actions">
            {active && <span className="case-priority">Review priority <strong>{reviewLabels[active.review_level]} ({Math.round(active.total_score)})</strong></span>}
            {active && <button className="investigate-button" type="button" disabled={!selected || agentStatus === "loading"}
              onClick={() => void runAgentInvestigation(active.building_id)}>
              {agentStatus === "loading" ? "Investigating…" : "Investigate Building"}
            </button>}
            <span className="sr-only" role="status">{status === "loading" ? "Loading analysis" : status === "ready" ? "Analysis online" : "Analysis unavailable"}</span>
          </div>
        </header>

      <section className="workspace" id="buildings" aria-labelledby="queue-title">
          <div className="queue-toolbar">
            <h2 className="panel-title" id="queue-title" hidden={!queueOpen}>Case Queue (LA County) {summary && <span>{summary.building_count.toLocaleString()}</span>}</h2>
            <button className="queue-toggle" type="button" aria-controls="case-queue-content"
              aria-expanded={queueOpen} aria-label={queueOpen ? "Collapse Case Queue" : "Expand Case Queue"}
              onClick={() => setQueuePreference(!queueOpen)}>
              <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d={queueOpen ? "m10 3-5 5 5 5" : "m6 3 5 5-5 5"} />
              </svg>
            </button>
          </div>
          <div id="case-queue-content" hidden={!queueOpen}>
          <div className="section-heading">
            <label className="search">
              <span className="sr-only">Search addresses</span>
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search address or building ID" type="search" />
            </label>
          </div>
          <div className="filters" role="group" aria-label="Filter review level">
            {filters.map((filter) => (
              <button aria-pressed={level === filter.value} key={filter.value} onClick={() => setLevel(filter.value)} type="button">
                {filter.label}
              </button>
            ))}
          </div>
          <div className="building-list" aria-busy={status === "loading"}>
            {status === "loading" && [1, 2, 3].map((item) => <div className="skeleton" key={item} />)}
            {status === "ready" && visible.length === 0 && <p className="empty-state">No buildings match this view.</p>}
            {visible.length > 0 && (
              <AnimatedBuildingList
                key={JSON.stringify([level, query.trim().toLowerCase()])}
                buildings={visible}
                selectedId={selectedId}
                reveal={mapReveal}
                showMatches={Boolean(query.trim())}
                hideEmpty={level !== "all" || Boolean(query.trim())}
                onSelect={(id) => {
                  if (id === selectedId) {
                    selectionRequest.current += 1;
                    setSelectedId(null);
                    setSelected(null);
                    setCaseStatus("idle");
                  } else {
                    setMapFocus({ buildingId: id });
                    void inspectBuilding(id);
                  }
                }}

              />
            )}
          </div>
          </div>
      </section>
      <div className="case-main">
        <div id="map">
      <HotspotMap buildings={buildings} total={summary?.building_count ?? buildings.length}
        status={status} warning={mapWarning} selectedId={selectedId} focusOnSelection={mapFocus?.buildingId === selectedId ? mapFocus : null} onSelect={(buildingId, focus) => {
          if (focus) setMapFocus({ buildingId });
          else if (buildingId !== selectedId) setMapFocus(null);
          setMapReveal({ id: buildingId });
          if (!visible.some((building) => building.building_id === buildingId)) {
            setLevel("all");
            setQuery("");
          }
          if (buildingId !== selectedId || (!selected && caseStatus === "error")) void inspectBuilding(buildingId);
        }} />

        </div>
        <section className="inspector" id="building-evidence" aria-label="Building evidence" aria-live="polite">
          {selected ? <BuildingInspector building={selected} aerial={aerial} network={network} caseResult={caseResult} caseStatus={caseStatus} agentResult={agentResult} agentStatus={agentStatus} onInvestigate={() => runAgentInvestigation(selected.building_id)} /> : caseStatus === "loading" ? <div className="inspector-empty" role="status">Loading building evidence…</div> : caseStatus === "error" ? <div className="inspector-empty" role="alert">Could not load building evidence. {error}</div> : <InspectorEmpty />}
          {!selected && <><span id="registrations" /><span id="ownership" /><span id="reports" /></>}
        </section>
      </div>
      </div>
      <Assessment investigation={agentResult} result={caseResult} />

      </main>
    </>
  );
}

function InspectorEmpty() {
  return (
    <div className="inspector-empty">
      <p className="section-label">Evidence inspector</p>
      <h2>Select a Building</h2>
      <p>Choose a building from the review queue to view its evidence and investigation details.</p>
    </div>
  );
}

function BuildingInspector({ building, aerial, network, caseResult, caseStatus, agentResult, agentStatus, onInvestigate }: { building: BuildingDetail; aerial: AerialEvidence | null; network: BuildingNetwork | null; caseResult: InvestigationResult | null; caseStatus: string; agentResult: InteractiveInvestigation | null; agentStatus: string; onInvestigate: () => void }) {
  return (
    <div>
      <div className="evidence-grid">
        <section className="document-panel" id="registrations">
          <h2 className="panel-title">CMS Registration</h2>
          <dl className="evidence-facts"><div><dt>Hospices</dt><dd>{building.hospice_count}</dd></div></dl>
          <p className="evidence-source">Source: CMS hospice registration data</p>
        </section>
        <section className="document-panel">
          <h2 className="panel-title">CoStar Property</h2>
          <BuildingContextCard building={building} />
          <dl className="evidence-facts"><div><dt>Match status</dt><dd>{formatLevel(building.costar_match_status)}</dd></div></dl>
        </section>
        <section className="document-panel">
          <h2 className="panel-title">Vexcel Aerial</h2>
          {aerial ? <AerialCard evidence={aerial} /> : <p className="panel-message">No aerial imagery is available for this building.</p>}
        </section>
      </div>
      <div className="inspector-head">
        <h2>{building.building_key}</h2><p>{building.priority.claim_reason}</p>
        <small>Scoring model {building.priority.score.model_version}</small>
      </div>

      {building.priority.strong_indicators.length > 0 && (
        <p className="queue-signals"><strong>Strong signals</strong> {building.priority.strong_indicators.map(formatLevel).join(", ")}</p>
      )}

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
      <div id="ownership"><NetworkPanel network={network} /></div>
      <FusionPanel result={agentResult} status={agentStatus} onInvestigate={onInvestigate} />
      <div id="reports"><CasePanel result={caseResult} status={caseStatus} /></div>
    </div>
  );
}

function FusionPanel({ result, status, onInvestigate }: { result: InteractiveInvestigation | null; status: string; onInvestigate: () => void }) {
  return (
    <section className="fusion-panel">
      <div className="fusion-heading"><div><p className="section-label">Cross-source investigation</p><h3>CMS + CoStar + Vexcel</h3></div>{result && <span className={`agent-mode mode-${result.mode}`}>{result.mode === "live_ai" ? "Live AI" : "Deterministic fallback"}</span>}</div>
      <p className="case-muted">Run a bounded, read-only investigation. Screening scores remain deterministic and unchanged.</p>
      <button className="investigate-button" disabled={status === "loading"} onClick={onInvestigate} type="button">{status === "loading" ? "Investigating…" : "Investigate this building"}</button>
      {status === "error" && <p className="fusion-error" role="alert">The interactive investigation could not be completed.</p>}
      {result && <>
        {result.fallback_reason && <p className="fallback-reason">Live AI was not used: {formatLevel(result.fallback_reason)}.</p>}
        <p className="fusion-summary">{result.reasoning_summary}</p>
        <div className="fusion-grid">{result.fusion_layers.map((layer) => <article key={layer.source}><strong>{layer.source}</strong>{layer.establishes.map((fact) => <p key={fact}>{fact}</p>)}<small>{layer.evidence_references.length ? `${layer.evidence_references.length} evidence reference(s)` : "No source record available"}</small>{layer.limitations.map((item) => <em key={item}>{item}</em>)}</article>)}</div>
        <div className="next-step"><strong>Recommended next step</strong><p>{result.recommended_next_step}</p></div>
        {result.unknowns.length > 0 && <details><summary>What remains unknown</summary><ul>{result.unknowns.map((item) => <li key={item}>{item}</li>)}</ul></details>}
        <details><summary>Inspect {result.tool_trace.length} genuine tool calls</summary><div className="tool-trace">{result.tool_trace.map((event, index) => <article key={`${event.tool_name}-${index}`}><strong>{event.tool_name}</strong><p>{event.result_summary}</p><small>{event.evidence_references.join(" · ") || "No evidence reference returned"}</small></article>)}</div></details>
        <small className="fusion-disclaimer">{result.disclaimer}</small>
      </>}
    </section>
  );
}

function AerialCard({ evidence }: { evidence: AerialEvidence }) {
  return (
    <figure className="aerial-card">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img alt={`Vexcel ortho context for ${evidence.address}`} src={absoluteApiUrl(evidence.image_url)} />
      <figcaption><div><p className="section-label">Vexcel aerial context</p><strong>Verified ortho imagery</strong></div><span>Retrieved {new Date(evidence.retrieved_at).toLocaleDateString()}</span></figcaption>
      {evidence.limitations.map((item) => <small key={item}>{item}</small>)}
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
      {network.limitations.map((item) => <small className="network-limit" key={item}>{item}</small>)}
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
            <div key={event.event_id}>
              <span>{formatLevel(event.event_type)}</span>{" "}
              <time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleTimeString("en-US", {
                hour: "2-digit", minute: "2-digit", timeZone: "America/Los_Angeles",
              })} PT</time>
              <p>{event.message}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
