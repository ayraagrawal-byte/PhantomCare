# Step 9 - Review-Priority Score

Date: 2026-11-13

## Version

The initial configuration is `review-priority-v1`. Its weights and claim thresholds live in `engine/scoring_v1.json`, separate from application code.

## Configured weights

| Indicator | Weight |
|---|---:|
| Address clustering | 35% |
| Building-type fit | 25% |
| Space per hospice | 20% |
| Ownership network | 20% |
| Aerial context | 0% |

Aerial context is displayed but never scored.

## Missing-data behavior

Missing sponsor data is not interpreted as a zero-valued signal. Missing indicators are excluded, and the remaining configured weights are rescaled to sum to one. The output includes both configured and effective weights plus the list of missing indicators.

An available indicator with a measured zero remains in the calculation. This distinguishes evidence of no signal from an absence of data.

## Claim levels

- `high_priority`: total score at least 70 and at least three independent indicators scoring 60 or higher
- `worth_a_look`: total score at least 35, or at least one strong indicator
- `no_indicators_found`: neither condition is met

Consequently, clustering alone can produce a score of 100 after missing-data rescaling but can never produce a high-priority claim. The decision reason states this explicitly.

## Explainability

Each result contains:

- Raw indicator score
- Effective calculation weight
- Weighted contribution
- Total score
- Configuration version
- Configured weights
- Missing indicators
- Strong indicators
- Human-readable claim-level reason

