# Step 6 - Address-Clustering Baseline

Date: 2026-11-13

## Purpose

The clustering baseline ranks LA County buildings using deterministic enrollment counts before sponsor enrichment or model-generated analysis is introduced. It is both an MVP output and the comparison baseline for later combined scoring.

## Metrics

For every physical building, the job calculates:

- Unique hospice enrollments
- LA County median hospices per building
- Empirical cumulative percentile for hospice count
- Competition-style count rank, with tied counts sharing the same rank
- Count above the county median
- Ratio of building count to the county median
- Optional unique home-health agency count
- Total hospice plus home-health agency count

The empirical percentile is the percentage of buildings with a hospice count less than or equal to the current building's count. Tied buildings therefore receive the same percentile.

## Reconciliation guardrail

Before calculating any metric, the job independently recomputes unique enrollment counts from normalized enrollment records. It fails if any building is missing or if any stored count disagrees. This prevents rankings from being generated from stale or partially updated building files.

## CLI

```bash
python -m engine.clustering \
  --buildings data/processed/buildings.csv \
  --enrollments data/processed/hospice_enrollments_normalized.csv \
  --output data/processed/buildings_ranked.csv
```

Home-health data is optional and must already contain normalized `BUILDING_KEY` and `AGENCY_ID` columns.

