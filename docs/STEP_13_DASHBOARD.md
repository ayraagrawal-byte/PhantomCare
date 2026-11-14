# Step 13 - Interactive Review Dashboard

Date: 2026-11-14

The Next.js dashboard consumes the validated Step 12 API and presents run status, analysis totals, score-ranked buildings, review-level and address filters, and a detailed evidence inspector. Loading, empty, and API-error states are explicit.

The inspector shows score rationale, data availability, indicator strength, evidence counts, and limitations. The interface never invents coordinates or displays a placeholder map; geographic visualization can be added after artifacts include verified building coordinates. Missing CoStar inputs are labeled, including the fact that available scoring weights were rebalanced.
