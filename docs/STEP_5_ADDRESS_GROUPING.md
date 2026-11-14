# Step 5 - Address Normalization and Building Grouping

Date: 2026-11-13

## Normalization rules

- Preserve the complete original address as `ADDRESS_RAW`.
- Uppercase and remove non-address punctuation.
- Normalize common street suffixes and cardinal directions.
- Extract `SUITE`, `STE`, `UNIT`, and `#` suffixes from address line 1.
- Treat a non-empty address line 2 as the suite/unit when present.
- Reduce ZIP+4 values to ZIP5 for the building key.
- Build the physical-building key from street address, city, state, and ZIP, excluding suite.
- Never use fuzzy matching to merge different street numbers.

Every normalized record includes a confidence score and JSON-encoded warnings. Missing street numbers, invalid state codes, missing ZIP5 values, and conflicting suite values lower confidence.

## Manual overrides

High-priority addresses can be corrected with an explicit JSON override keyed by the exact raw address components. Each override records a note in the normalization warnings. Overrides are opt-in and do not mutate the original CMS values.

Example:

```json
{
  "14545 FRIAR ST|SUITE 210|VAN NUYS|CA|91411": {
    "building_key": "14545 FRIAR ST VAN NUYS CA 91411",
    "suite": "210",
    "note": "verified during top-50 address review"
  }
}
```

## Building output

The grouping job emits one row per `BUILDING_KEY` with:

- A stable SHA-256-derived building ID
- Unique hospice count
- Unique non-empty suite count
- Sorted enrollment IDs
- Sorted original address variants
- Minimum normalization confidence

## CLI

```bash
python -m pipeline.group_buildings \
  --enrollments data/processed/hospice_enrollments.csv \
  --output-enrollments data/processed/hospice_enrollments_normalized.csv \
  --output-buildings data/processed/buildings.csv \
  --overrides data/reference/address_overrides.json
```

