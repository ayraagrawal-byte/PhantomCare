# Step 15 - Case API and Dashboard

Date: 2026-11-14

Investigation outputs now retain their target building ID whether they produce a case file or stop early. This makes both outcomes traceable from the building review interface.

## API

- `GET /cases` lists completed case files in score order.
- `GET /cases/{case_id}` returns a completed or early-stopped investigation and its trace.
- `GET /cases/targets/{target_id}` resolves the investigation associated with a building.

All investigation artifacts are validated before serving. Missing or malformed artifacts return an actionable `503 cases_unavailable`; unknown case and target IDs return structured 404 responses.

## Dashboard

Selecting a building now loads its investigation alongside the indicator evidence. The inspector displays neutral findings, strength after limitation penalties, attached evidence counts, the non-fraud disclaimer, early-stop reasons, and the ordered investigation trace.
