# PhantomCare — two-minute judging script

Setup: dashboard open locally (see `docs/DEMO_RECOVERY_RUNBOOK.md`), live AI **off**.
Every number below was measured on this repository; do not substitute others.

## 0:00–0:15 — Opening

> "In Los Angeles County, 569 hospice registrations sit at just 468 street addresses.
> One office building can hold a dozen 'hospices.' Some are legitimate. Some are a
> known Medicare abuse pattern. Nobody can investigate 468 buildings by hand —
> so we built the triage desk."

## 0:15–0:35 — Judge interaction

> "Pick any address in the queue — or try this one."

Hand a judge the search box (or type `12444 VICTORY`). Select the building.
Point at the review level and the score breakdown: every indicator shows its inputs,
its evidence count and its limitations. Point at **Missing data**: no exact CoStar
record exists here, so two indicators are unavailable and the building is capped at
"worth a look" — without a CoStar match a building cannot reach high priority, because
high priority needs three independent strong indicators.

## 0:35–1:05 — Evidence, three real sources

- **CMS (real, public):** registration concentration at this normalized address.
- **Vexcel (real imagery):** the ortho image with retrieval date and provenance.
  Say it: *"Aerial imagery is exterior context. It cannot show whether a hospice operates inside."*
- **CoStar (real record, different building):** search `3800 BARHAM` to show a real
  exact property match: class B office, 85,831 sq ft, 6 stories, 44 tenant locations.
  Click **Investigate**. The cross-source comparison shows one registration in a large
  multi-tenant office (~85,831 sq ft per registration), so *CoStar context lowers concern
  here*. That is the point: property data separates real anomalies from ordinary leasing.

Be explicit: *"In our real data, the one CoStar match and the one Vexcel image are
different buildings. Our same-building CoStar-plus-Vexcel fusion is a labeled
synthetic scenario."*

## 1:05–1:35 — Investigate

Click **Investigate this building**. Point at the **Deterministic fallback** badge:
*"Live AI is not running in this demo — this is the deterministic path, and it says so."*
Show: Evidence (CMS / Ownership / CoStar / Vexcel layers) → Comparison (what each
establishes) → Uncertainty (what remains unknown) → Action (recommended next step and
the human-review checklist). Expand the eight read-only tool calls and their source
references. Download the JSON case file.

## 1:35–1:50 — One measured technical result

> "We wrote ten synthetic scenarios with expected outcomes derived by hand from our
> published scoring rules. All ten pass — 67 of 67 checks. Writing them caught two
> real safety bugs: paraphrased fraud allegations like 'fraud ring' and fabricated
> citations were slipping past our AI-output validator. Both are fixed and tested."

(These are rule-conformance results on synthetic data — not real-world detection accuracy.)

## 1:50–2:00 — Public-interest impact

> "Investigators get a reproducible lead package — what is unusual, which records
> support it, what is still unknown, and what to verify next — without anyone being
> accused by an algorithm. PhantomCare prioritizes questions; people make findings."

## Words to avoid

"Fraud detected", "fake hospice", "shell company", "AI found", "proves". Say
"unusual pattern", "worth review", "requires verification".
