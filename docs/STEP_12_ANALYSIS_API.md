# Step 12 - Analysis API

Date: 2026-11-14

FastAPI now serves the validated artifacts produced by `pipeline.analysis`:

- `GET /analysis/summary` returns run time, record counts, priority counts, and the screening disclaimer.
- `GET /analysis/buildings` returns score-sorted building summaries and supports `level` and `limit` query parameters.
- `GET /analysis/buildings/{building_id}` returns indicators, evidence, limitations, missing-data details, and the complete scoring explanation.

The API validates every artifact against Pydantic response contracts before returning it. Missing, unreadable, or malformed artifacts produce an actionable `503 analysis_unavailable` response. Unknown building IDs produce a structured 404.

The artifact directory defaults to `data/analysis` and can be changed with `PHANTOMCARE_ANALYSIS_DIR`. Endpoints are read-only, and sponsor credentials are neither loaded nor returned by the API.
