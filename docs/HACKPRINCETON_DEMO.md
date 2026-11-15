# PhantomCare two-minute demo

## Live demonstration path

**0:00–0:20 — Problem.** “Public hospice registrations are easy to view one at a time but hard to investigate as buildings, organizations, and evidence networks. PhantomCare prioritizes unusual registrations; it does not decide that anyone committed fraud.”

**0:20–0:40 — Unusual building.** Open the dashboard, point out the measured offline result—468 analyzed buildings from 569 registrations—and search for `12444 VICTORY`. Select the single result.

**0:40–1:10 — Evidence fusion.** Show the CMS indicators and source references, the honest CoStar no-exact-match state, the Vexcel ortho image with provenance and limitations, and the ownership-network evidence. Say explicitly that aerial imagery gives geographic context and does not prove occupancy or healthcare activity.

**1:10–1:35 — Auditable investigation.** Click **Investigate this building**. In the safe demo configuration, call this a deterministic investigation—not live AI. Expand all eight genuine read-only tool records, show citations and unknowns, then download the JSON case file.

**1:35–1:50 — Impact.** “The output is a reproducible lead package for human review: what is unusual, which records support it, what remains unknown, and what to verify next.”

**1:50–2:00 — Safety.** “Live AI is a separately gated mode. It cannot run from a credential alone: it also requires explicit enablement, durable rate and concurrency controls, time/token/tool limits, and it falls back deterministically.”

## Fallback path

The demo is designed to succeed without external services. Use the checked-in offline artifact in `data/runtime` (real public CMS data plus the real CoStar and Vexcel records; no network needed), keep `PHANTOMCARE_AGENT_LIVE_ENABLED=false`, and show the visible **Deterministic fallback** badge and reason. If Vexcel imagery cannot render, show its missing-data state and continue with the provenance text and CMS/ownership records. Never describe this path as live AI.

## If controlled live AI is later approved

Use a synthetic target only after the release prerequisites are present. Explain the distinction: deterministic scoring ranks buildings from fixed rules; live AI may choose among the same read-only evidence tools to assemble a cited investigation. Show actual tool calls and result mode. If the model or limiter fails, point out the automatic deterministic result rather than retrying during the demo.

## Presenter guardrails

- Say “investigation lead,” “unusual pattern,” and “requires verification.”
- Do not say “fraud detected,” “shell company,” “fake hospice,” or that aerial imagery proves service activity.
- Measured on `claude/sprint-recovery`: 122 backend tests, 5 frontend unit tests, 20 real-browser tests (10 desktop, 10 mobile), and the ten-scenario synthetic evaluation (10/10) passing. See `docs/EVALUATION_SUMMARY.md`.
- The current data limitation is important: the one exact CoStar match and the one Vexcel image belong to different offline buildings.
