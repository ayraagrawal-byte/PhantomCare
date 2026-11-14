const plannedCapabilities = [
  "CMS enrollment clustering",
  "Building-fit indicators",
  "Masked ownership networks",
  "Evidence-backed case files",
];

export default function Home() {
  return (
    <main>
      <section className="hero">
        <p className="eyebrow">Los Angeles County · Investigation workspace</p>
        <h1>Medicare records show the address. PhantomCare examines the building.</h1>
        <p className="lede">
          A review-priority tool that brings hospice enrollment, ownership, and building context
          together without making accusations.
        </p>
        <div className="notice">
          <strong>Step 2 application shell</strong>
          <span>Data ingestion and measured indicators arrive in the next milestone.</span>
        </div>
      </section>

      <section aria-labelledby="capabilities-heading" className="capabilities">
        <p className="section-label">Planned workflow</p>
        <h2 id="capabilities-heading">From raw records to reviewable evidence</h2>
        <div className="capability-grid">
          {plannedCapabilities.map((capability, index) => (
            <article key={capability}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <h3>{capability}</h3>
            </article>
          ))}
        </div>
      </section>

      <footer>
        PhantomCare reports indicators worth reviewing—not conclusions of fraud.
      </footer>
    </main>
  );
}

