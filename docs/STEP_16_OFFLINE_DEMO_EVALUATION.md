# Step 16 - Offline Demo and Evaluation

Date: 2026-11-14

The offline demo generates synthetic CMS enrollment, owner, and CoStar-compatible records, then runs the real ingestion, grouping, clustering, ownership, indicator, scoring, investigation, and artifact-writing code paths.

The fixture contains three synthetic buildings. The expected hotspot combines address clustering, executive-suite context, low area per registration, and shared masked ownership. The evaluation requires exactly one high-priority building and one completed case; the other two buildings must stop early.

Privacy and language checks verify that the synthetic individual's source name and owner ID do not enter application artifacts and that every case retains the non-fraud disclaimer.

```bash
python -m eval.offline_demo --output data/demo
```

The command needs no network connection, API keys, licensed event data, or `.env` file. It writes dashboard-ready analysis artifacts, case traces, fixtures, and `evaluation_results.json` under the selected output directory and exits nonzero if a guardrail fails.
