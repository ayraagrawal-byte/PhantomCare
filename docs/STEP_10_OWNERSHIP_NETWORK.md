# Step 10 - Masked Ownership Network

Date: 2026-11-13

## Purpose

The ownership engine turns retained CMS owner rows into an explainable hospice-owner graph. It is a review aid, not a fraud classifier.

## Privacy rules

- Source owner associate IDs are replaced with stable SHA-256-derived keys.
- Individual first, middle, and last names never enter application output.
- Individual display labels are masked.
- Owner addresses are reduced to non-reversible fingerprints used only for shared-address counts.
- Organization names remain visible because they describe legal entities rather than people.

## Building metrics

For each building, the engine reports:

- `max_hospices_per_owner`: largest number of retained hospices linked to any owner touching the building
- `owners_shared_across_hospices`: owners touching the building that link to more than one retained hospice
- `shared_owner_address_count`: distinct owner-address fingerprints used by more than one owner

These values feed the deterministic ownership indicator from Step 8. Shared ownership is common in legitimate healthcare groups and is never presented as proof of improper activity.

## CLI

```bash
python -m engine.ownership \
  --owners data/processed/hospice_owners.csv \
  --enrollments data/processed/hospice_enrollments_normalized.csv \
  --buildings data/processed/buildings.csv \
  --output data/processed/ownership_network.json
```
