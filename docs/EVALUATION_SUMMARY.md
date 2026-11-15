# Evaluation summary

## Ten-scenario rule-conformance suite

```bash
python -m eval.scenarios --output eval/scenario_results.json
```

- Implementation: `eval/scenarios.py`; pytest wrapper: `eval/tests/test_scenarios.py`.
- Report: `eval/scenario_results.json` (fixed timestamp; byte-identical across runs; the
  test suite fails if the committed report drifts from a fresh run).
- Result: **10/10 scenarios, 67/67 checks.**
- **All inputs are synthetic.** A pass means the code followed its own published rules
  (`engine/scoring_v1.json`, `engine/indicators.IndicatorThresholds`). It is not a measure
  of real-world fraud-detection accuracy, precision or recall.

### Metric definitions

- `scenarios_passed`: scenarios whose every check equals its hand-derived expected value.
- `checks_passed`: individual expected-vs-actual comparisons that matched.

Expected values were derived by hand from the scoring rules and written into each scenario
before running; the arithmetic is recorded beside each expectation in `eval/scenarios.py`.

| ID | What it verifies | Expected |
| --- | --- | --- |
| S01 | Full four-signal hotspot | high priority, 100.0, 4 strong |
| S02 | Missing CoStar (real 12444 Victory pattern) | worth a look, 100.0, 2 strong, `building_type_fit` + `space_per_hospice` missing |
| S03 | Clustering inside a medical office, no shared owners | worth a look, 35.0 |
| S04 | Single registration, no context | no indicators, no case |
| S05 | Moderate generic-office case | worth a look, 56.25 |
| S06 | CoStar record without area | high priority, `space_per_hospice` missing |
| S07 | Owner masking through the real offline pipeline | no private name or owner ID in artifacts |
| S08 | Fraud-allegation rejection (7 phrasings) + neutral control | all 7 rejected, control accepted |
| S09 | Citation validation | uncited, fabricated, and real+fabricated rejected; all-real accepted |
| S10 | **Synthetic** same-building CoStar + Vexcel fusion | Vexcel cited, score unchanged by imagery, no imagery-based finding |

Every scoring scenario also checks that each nonzero indicator carries a source record,
that every case-file citation traces to indicator evidence, and that cases keep the
non-fraud disclaimer.

### Missing-CoStar expectation

A missing CoStar match removes **two** indicators (building-type fit and space per
hospice), because both depend on the property record. With the remaining weights
renormalized the score can still be 100, but only two strong indicators remain and high
priority requires three, so the level is "worth a look". This is the intended guardrail
(a building with no CoStar match cannot reach high priority), and it matches the real
artifact for 12444 Victory Blvd.

Caveat (not a test failure): renormalization means a *single* missing indicator can raise
the total. Example: clustering 80, building type 100, ownership 65, space 0 scores 66
(worth a look); with the area measurement missing instead, it scores 82.5 (high
priority). Whether that is acceptable is a scoring-policy decision for the team.

### Bugs found by the suite (fixed)

Initial run: 8/10. Both failures were genuine defects in
`agent/interactive._validated_agent_summary`, not fixture errors:

1. Paraphrased allegations ("committing hospice fraud", "fraud ring", "sham hospices",
   "prove fraud", "illegal billing scheme") passed the exact-substring blocklist.
2. A summary citing one real and one fabricated reference was accepted.

The validator now rejects allegation vocabulary (allowing neutral denials such as
"not evidence of fraud") and requires every cited reference to have been returned by a
tool. Expectations were not changed.

## Other measured checks (this branch)

| Check | Result |
| --- | --- |
| `pytest` (with `.[dev,agent]`) | 122 passed |
| Mocked-model Deep Agents tests | 4 passed (`agent/tests/test_deep_agent_mocked.py`) |
| `npm run test` | 5 passed |
| `npm run test:e2e` | 20 passed (10 desktop, 10 mobile) |
| Offline demo (`python -m eval.offline_demo`) | passed |

## Real-data limitation

In `data/runtime`, exactly one building has an exact CoStar match (3800 Barham Blvd) and
exactly one has Vexcel imagery (12444 Victory Blvd). They do not overlap. Any same-building
CoStar + Vexcel demonstration is synthetic (S10) and must be labeled as such.
