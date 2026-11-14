# Step 4 - CMS Ingestion

Date: 2026-11-13

## Inputs

The pipeline accepts the three relational CMS hospice files used by PhantomCare:

- Hospice Enrollments
- Hospice All Owners
- Hospice Additional Addresses

Files may be local CSV paths or URLs supported by pandas. A separate downloader is available for pinning official CMS downloads to local paths before an import.

## Behavior

1. Read every value as text so identifiers and ZIP codes retain leading zeros.
2. Map documented CMS headings to stable internal column names.
3. Fail with an actionable error when required columns are absent.
4. Preserve the source filename, source row number, and a deterministic SHA-256 row hash.
5. Reject rows missing required identifiers or address fields and count rejection reasons.
6. Filter enrollment rows to California and Los Angeles County.
7. Restrict owners and additional addresses to retained enrollment IDs.
8. Deduplicate using documented relational keys, keeping the earliest source row.
9. Sort outputs deterministically and write clean CSVs plus `import_summary.json`.

## County-filter guardrail

The official Hospice Enrollments dictionary documents state and ZIP fields but not a county field. When a source extract has no county column, the importer requires an authoritative LA County ZIP-code allowlist. It deliberately refuses to infer county membership from city names.

## CLI

```bash
python -m pipeline.import_cms \
  --enrollments data/raw/HOSPICE_ENROLLMENTS.csv \
  --owners data/raw/HOSPICE_ALL_OWNERS.csv \
  --additional-addresses data/raw/HOSPICE_ADDITIONAL_ADDRESSES.csv \
  --la-county-zip-file data/reference/la_county_zip_codes.txt \
  --output data/processed
```

Do not commit raw CMS extracts or licensed sponsor data unless repository policy explicitly permits it.

