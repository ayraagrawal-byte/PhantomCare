# PhantomCare

Evidence-backed hospice registration and building-fit investigation platform for Los Angeles County.

PhantomCare is being built as an explainable investigation workflow. It will combine public CMS hospice enrollment and ownership records with licensed building data while preserving evidence provenance and avoiding accusations of fraud.

## Repository layout

```text
api/          FastAPI application and backend tests
dashboard/    Next.js dashboard
pipeline/     CMS ingestion and enrichment jobs (Step 3)
engine/       Deterministic indicators and scoring (Step 3+)
agent/        Investigation workflow (later milestone)
eval/         Evaluation fixtures and measured results
docs/         Architecture and implementation records
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- npm 10+

## Backend

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
uvicorn api.app:app --reload
```

The API is available at `http://localhost:8000`; health status is exposed at `GET /health`.

Run backend checks with:

```bash
pytest
ruff check .
```

## Dashboard

```bash
npm install
npm run dev
```

The dashboard is available at `http://localhost:3000`.

## Configuration

Copy `.env.example` to `.env` and customize values locally. Never commit sponsor API keys or cached licensed data.

## Current milestone

Step 2 provides a runnable application shell only. Data ingestion, scoring, mapping, and agent behavior will be added in later milestones.
