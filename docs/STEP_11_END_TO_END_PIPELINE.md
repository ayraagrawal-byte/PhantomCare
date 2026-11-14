# Step 11 - End-to-End Analysis Pipeline

Date: 2026-11-14

`pipeline.analysis` connects the implemented stages into one reproducible command:

1. Validate and import the three CMS relational files.
2. Restrict the dataset to Los Angeles County.
3. Normalize addresses and group enrollments by physical building.
4. Calculate the county clustering baseline.
5. Build the privacy-preserving ownership network.
6. Optionally exact-match buildings to the decrypted CoStar extract.
7. Calculate deterministic, evidence-bearing indicators.
8. Apply the versioned review-priority scoring rules.
9. Write machine-readable artifacts for the API and dashboard.

## Safety behavior

- Sponsor credentials are never accepted as command arguments or written to outputs.
- CoStar enrichment is optional; missing licensed data remains explicitly missing rather than becoming a zero signal.
- Multiple CoStar records at the same exact address are marked ambiguous and are not silently selected.
- Individual owner names and raw owner IDs are absent from the ownership graph.
- Every summary includes the statement that priorities are screening aids, not findings of fraud.

## Command

```bash
python -m pipeline.analysis \
  --enrollments data/raw/HOSPICE_ENROLLMENTS.csv \
  --owners data/raw/HOSPICE_ALL_OWNERS.csv \
  --additional-addresses data/raw/HOSPICE_ADDITIONAL_ADDRESSES.csv \
  --costar-kit work/sponsor/costar-kit \
  --output data/analysis
```

`--costar-kit` is optional, allowing a safe public-data-only demonstration.
