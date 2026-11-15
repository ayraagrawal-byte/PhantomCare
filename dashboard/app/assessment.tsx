import type { InteractiveInvestigation, InvestigationResult } from "../lib/analysis";

export default function Assessment({ investigation, result }: { investigation: InteractiveInvestigation | null; result: InvestigationResult | null }) {
  const findings = investigation?.fusion_layers.flatMap(({ establishes }) => establishes) ?? [];
  const facts = [...new Set(findings.length ? findings : result?.case_file?.findings.map(({ summary }) => summary) ?? [])];
  return (
    <div className="assessment-strip">
      <section className="assessment">
        <h2 className="panel-title">Cross-Source Assessment</h2>
        {facts.length ? <ul>{facts.map((fact) => <li key={fact}>{fact}</li>)}</ul> : <p className="panel-message">No cross-source findings are available to display.</p>}
      </section>
      <section className="screening-notice" id="screening-notice">
        <h2>Not a Fraud Determination</h2>
        <p>Screening results identify potential anomalies for human review. They do not establish fraud, noncompliance, or quality of care.</p>
      </section>
    </div>
  );
}
