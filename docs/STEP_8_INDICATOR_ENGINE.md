# Step 8 - Deterministic Indicator Engine

Date: 2026-11-13

## Principle

Every indicator is computed in Python from validated inputs. The model cannot invent, calculate, or override indicator values. Every non-zero result carries evidence and every result states its limitations.

## Indicators

- `address_clustering`: hospice count relative to the LA County empirical distribution
- `building_type_fit`: CoStar property context, including executive-suite, generic-office, medical-use, and other classifications
- `space_per_hospice`: rentable area per registration, falling back to gross area only when RBA is unavailable
- `ownership_network`: masked aggregate owner-link metrics
- `aerial_context`: human-reviewed Vexcel observations retained as context with zero score

## Guardrails

- Missing sponsor data receives a zero contribution plus a limitation; it is never treated as an adverse fact.
- Generic office context receives only a modest signal.
- Medical-use context receives no building-type signal.
- Aerial imagery is never scored as proof of operations.
- Space-per-hospice ratios do not claim how much space any organization actually leases.
- Ownership results contain aggregate metrics, not individual names.
- Every result uses the phrase and framing of indicators worth reviewing, not conclusions of fraud.

## Thresholds

Thresholds are held in an immutable configuration object and covered by tests. Step 9 will apply versioned weights and claim-level rules to these raw indicator scores.

