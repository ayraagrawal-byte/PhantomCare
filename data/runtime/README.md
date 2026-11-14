# Deployment runtime artifacts

This directory contains the minimum evidence artifacts required by the public demo API.

- CMS source: Q4 2026 Hospice Enrollments, Hospice All Owners, and Hospice Additional Addresses from `data.cms.gov`.
- Geographic filter: 2020 Census ZCTA-to-county relationship rows for Los Angeles County (`06037`).
- CoStar: exact-match derived building context only; the licensed raw extract is excluded.
- Vexcel: one cached ortho image for the top-ranked demo address, retrieved under the event key. Remove it when the hackathon data-access period ends.
- Privacy: raw CMS rows and raw individual names are excluded; individual owners remain masked in the network artifact.

These artifacts are reproducible locally from the ignored raw files and sponsor cache. They are screening outputs, not findings of fraud.
