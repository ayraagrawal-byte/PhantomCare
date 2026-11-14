# Step 14 - Guided Investigation and Case Files

Date: 2026-11-14

The investigation workflow converts validated building analysis into a neutral, evidence-bound case file. It is deterministic and does not use a language model.

## Guardrails

- Stop when the review score is below 35 or the level is `no_indicators_found`.
- Stop when fewer than two evidence records are available.
- Create findings only for recognized indicators scoring at least 35 with attached evidence.
- Use fixed, neutral claim language; never generate allegations.
- Reduce finding strength when limitations are present.
- Run a skeptical-review stage that explicitly records retained findings and limitations.
- Preserve deterministic case and trace IDs for reproducibility.
- Attach the disclaimer that indicators are not conclusions of fraud.

## Trace

Successful investigations record `started`, `tool_called`, `tool_completed`, `skeptic_review`, and `case_written` events. Early stops record their reason and do not create an empty case file.

## CLI

```bash
python -m agent.investigation \
  --input data/analysis/building_analysis.json \
  --output data/analysis/investigation_cases.json
```
