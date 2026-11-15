# Deployment runtime artifacts

This directory contains the minimum evidence artifacts required by the public demo API.

- CMS source: Q4 2026 Hospice Enrollments, Hospice All Owners, and Hospice Additional Addresses from `data.cms.gov`.
- Geographic filter: 2020 Census ZCTA-to-county relationship rows for Los Angeles County (`06037`).
- CoStar: exact-match derived building context only; the licensed raw extract is excluded.
- Vexcel: one cached ortho image for the top-ranked demo address, retrieved under the event key. Remove it when the hackathon data-access period ends.
- CAMS: `cams_geocodes.json` caches address-point matches and rejection reasons for the normalized building keys. Source credit: County of Los Angeles, Enterprise Geographic Information Systems (eGIS), Internal Services Department.
- Supplemental locations: `supplemental_geocodes.json` records the follow-up investigation of the 140 remaining addresses. The source CAMS cache is preserved.
- Reviewed locations: `reviewed_geocodes.json` records the original CMS addresses and evidence for the final 24 cases. The API applies a reviewed point only when the automatic caches still leave that building ID and address unresolved.
- Privacy: raw CMS rows and raw individual names are excluded; individual owners remain masked in the network artifact.

These artifacts are reproducible locally from the ignored raw files and sponsor cache. They are screening outputs, not findings of fraud.

### Refresh the CAMS cache

Run `python -m pipeline.geocode_cams --analysis-dir data/runtime` after updating
`building_analysis.json`. The batch job queries the public
[CAMS address-point layer](https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/eGIS_Addressing_ADDRESS_POINTSv2/FeatureServer/0)
using house number and ZIP and validates the whole street and community locally.
It saves exact and conservative standardized matches with the County feature ID,
upstream record source, matching address and unmodified WGS84 point. Distinct
candidate points, unmatched records and unit-only results stay unmapped.
The API reads the cache locally and requires both the current building ID and
address to match before publishing a point.

The current run matched 328 of 468 buildings (286 exact, 42 standardized).
The other 140 had no compatible street address (75), only unit/floor points (45),
an unverified community or extra address tokens (17), or conflicting points (3).
CAMS locations carry address-point precision, which can vary by contributing
source. Use is informational and subject to the
[LA County eGIS terms](https://egis-lacounty.hub.arcgis.com/pages/terms-of-use).

Run `python -m pipeline.geocode_supplemental --analysis-dir data/runtime` after refreshing
the CAMS cache. This requires network access to the public Census and CAMS services.
The dashboard reads both caches offline. See the [coverage report](../../docs/MAP_COVERAGE.md)
for the final counts, validation rules and unresolved addresses.
