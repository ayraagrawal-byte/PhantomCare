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

## CMS ingestion

Import the three relational hospice files with:

```bash
python -m pipeline.import_cms \
  --enrollments data/raw/HOSPICE_ENROLLMENTS.csv \
  --owners data/raw/HOSPICE_ALL_OWNERS.csv \
  --additional-addresses data/raw/HOSPICE_ADDITIONAL_ADDRESSES.csv \
  --la-county-zip-file data/reference/la_county_zip_codes.txt \
  --output data/processed
```

The importer validates documented CMS columns, preserves source provenance, filters related records to retained LA County enrollments, and writes an import summary. See `docs/STEP_4_CMS_INGESTION.md` for the county-filter guardrail.

Normalize imported addresses and group enrollments by physical building with:

```bash
python -m pipeline.group_buildings \
  --enrollments data/processed/hospice_enrollments.csv \
  --output-enrollments data/processed/hospice_enrollments_normalized.csv \
  --output-buildings data/processed/buildings.csv
```

Generate the deterministic clustering baseline with:

```bash
python -m engine.clustering \
  --buildings data/processed/buildings.csv \
  --enrollments data/processed/hospice_enrollments_normalized.csv \
  --output data/processed/buildings_ranked.csv
```

Cache sponsor enrichment for the highest-ranked buildings with:

```bash
python -m pipeline.enrich_buildings \
  --provider costar \
  --buildings data/processed/buildings_ranked.csv \
  --cache-dir cache \
  --output data/processed/costar_enrichment.json
```

Vexcel live mode uses the event-provided `VEXCEL_API_KEY`. Matterport uses `MATTERPORT_API_KEY` and `MATTERPORT_API_TOKEN` server-side. CoStar is an encrypted data extract rather than a live API. Use `--cache-only` for offline demonstrations.

Match ranked buildings to the decrypted CoStar extract with:

```bash
python -m pipeline.costar_extract \
  --kit work/sponsor/costar-kit \
  --buildings data/processed/buildings_ranked.csv \
  --output data/processed/costar_matches.json
```

The deterministic indicator engine is implemented in `engine/indicators.py`. It consumes the clustering baseline, exact CoStar matches, masked ownership metrics, and optional human-reviewed aerial notes. It does not call an LLM.


## Current milestone

Step 2 provides a runnable application shell only. Data ingestion, scoring, mapping, and agent behavior will be added in later milestones.
