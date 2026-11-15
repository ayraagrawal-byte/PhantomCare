# PhantomCare — Devpost draft

> Draft. Review every claim before submitting; all numbers are measured on this repository.

## Inspiration

Hospice registrations are public, but they are published one enrollment at a time.
Patterns that matter — many registrations at one address, shared ownership, a building
that cannot plausibly house them — only appear when the records are read as buildings.

## What it does

PhantomCare turns CMS hospice enrollment and ownership records for Los Angeles County
(569 registrations at 468 physical addresses) into a ranked, explainable review queue.
For each building it shows:

- **Evidence**: CMS registration concentration, masked ownership links, CoStar property
  context where an exact match exists, and Vexcel aerial imagery where available.
- **Comparison**: what each source establishes, side by side.
- **Uncertainty**: missing data, limitations, and what remains unknown.
- **Action**: a recommended next step, a human-review checklist, and a downloadable
  JSON case file with source citations.

It never labels anyone as fraudulent. Output is a lead package for human review.

## How we built it

- **Pipeline (Python):** CMS ingestion, address normalization, building grouping,
  clustering baseline, masked ownership graph (owner IDs hashed, individual names
  suppressed), CoStar exact matching.
- **Deterministic scoring:** versioned weights and claim rules (`engine/scoring_v1.json`).
  High priority requires three independent strong indicators, so a building with no
  CoStar match (two indicators unavailable) cannot reach high priority.
- **Investigation agent:** eight read-only evidence tools with an auditable trace. An
  optional LangChain Deep Agents path (`create_deep_agent`) lets a model choose among the
  same tools, bounded by tool, token, time and rate limits, and its output is rejected if it
  alleges fraud or cites evidence the tools never returned. **The public demo runs the
  deterministic fallback and labels it as such; live AI was not used in our demo.**
- **API / dashboard:** FastAPI and Next.js, with an interactive Leaflet hotspot map.

## Data sources

| Source | Status in the demo |
| --- | --- |
| CMS hospice enrollments and owners | Real public data |
| CoStar | Real record; one exact match (3800 Barham Blvd), with a linked Matterport model ID |
| Vexcel | Real ortho imagery; one building (12444 Victory Blvd) |
| Same-building CoStar + Vexcel fusion | **Synthetic** evaluation scenario only |

## Challenges

Our only exact CoStar match and our only Vexcel image are different buildings. Rather
than pretend otherwise, the UI shows each source's real coverage and the fused case is
demonstrated with a clearly labeled synthetic scenario.

## Accomplishments

- A ten-scenario synthetic evaluation with hand-derived expected outcomes: 10/10
  scenarios, 67/67 checks. These measure rule conformance, not real-world accuracy.
- Writing those scenarios exposed two safety bugs in the AI-output validator
  (paraphrased fraud allegations and fabricated citations); both are fixed.
- 129 backend tests, 5 frontend unit tests, and 22 real-browser tests (desktop and mobile)
  passing.

## What we learned

Explainability is mostly about saying what you *don't* know: every score in PhantomCare
carries its missing inputs and limitations next to it.

## What's next

Broader CoStar and Vexcel coverage so real buildings can be fused; reviewer feedback
captured in the case file; a controlled, rate-limited live-AI pilot on synthetic targets
before any real use.

## Built with

Python, FastAPI, pandas, LangChain Deep Agents (optional path), Next.js, React,
TypeScript, Leaflet, Playwright, Vitest, pytest.
