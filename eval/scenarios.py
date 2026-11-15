"""Ten-scenario deterministic evaluation of PhantomCare's screening and safety rules.

Every scenario is SYNTHETIC. Expected outcomes are written by hand from the published
rules (engine/scoring_v1.json and engine/indicators.IndicatorThresholds) before the code
runs; the derivation is recorded next to each expectation. These results measure whether
the implementation follows its own rules. They are NOT real-world detection accuracy.

Run with:
    python -m eval.scenarios --output eval/scenario_results.json
"""

from __future__ import annotations

import argparse
import json
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.interactive import AgentToolTrace, _validated_agent_summary
from agent.investigation import investigate_building
from api.schemas import BuildingAnalysisResponse
from engine.indicators import AerialReview, IndicatorEngine, OwnershipMetrics
from engine.scoring import score_indicators

RUN_AT = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
DATA_LABEL = "synthetic"
DISCLAIMER = (
    "All ten scenarios use synthetic inputs. A pass means the implementation followed its "
    "own published rules; it is not a measure of real-world fraud-detection accuracy."
)

EXEC_SUITE = {
    "property_id": "SYN-1001",
    "property_type": "Office",
    "property_subtype": "Executive Suite",
    "building_name": "Synthetic Business Center",
    "rentable_building_area_sqft": 2400,
    "gross_building_area_sqft": 2600,
}
NO_OWNER_SHARING = OwnershipMetrics()
HEAVY_OWNER_SHARING = OwnershipMetrics(
    max_hospices_per_owner=12, owners_shared_across_hospices=1, shared_owner_address_count=1
)


@dataclass(frozen=True)
class ScoringScenario:
    scenario_id: str
    description: str
    hospice_count: int
    percentile: float
    county_median: float
    costar: dict[str, Any] | None
    ownership: OwnershipMetrics
    expected: dict[str, Any]
    aerial_review: AerialReview | None = None


@dataclass
class ScenarioResult:
    scenario_id: str
    description: str
    data: str
    expected: dict[str, Any]
    actual: dict[str, Any]
    checks: dict[str, bool] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(self.checks.values())


SCORING_SCENARIOS: tuple[ScoringScenario, ...] = (
    ScoringScenario(
        "S01_full_signal_hotspot",
        "Clustering, executive-suite context, low area per registration, shared ownership.",
        hospice_count=12,
        percentile=99.5,
        county_median=1,
        costar=EXEC_SUITE,
        ownership=HEAVY_OWNER_SHARING,
        # 99.5>=99 ->100; exec suite ->100; 2400/12=200<250 ->100; owner 12>=10 ->100.
        # 0.35*100+0.25*100+0.20*100+0.20*100 = 100; 4 strong >=3 -> high priority.
        expected={"level": "high_priority", "total": 100.0, "strong": 4, "missing": [],
                  "case_written": True},
    ),
    ScoringScenario(
        "S02_missing_costar",
        "Same CMS and ownership signal with no CoStar match (the real 12444 Victory pattern).",
        hospice_count=12,
        percentile=99.5,
        county_median=1,
        costar=None,
        ownership=HEAVY_OWNER_SHARING,
        # Without CoStar, building_type_fit AND space_per_hospice are both unavailable.
        # Weights renormalize over clustering(.35)+ownership(.20); both 100 -> total 100,
        # but only 2 strong indicators < 3 required -> worth a look, never high priority.
        expected={"level": "worth_a_look", "total": 100.0, "strong": 2,
                  "missing": ["building_type_fit", "space_per_hospice"], "case_written": True},
    ),
    ScoringScenario(
        "S03_medical_office_context",
        "Clustered registrations inside a large medical office building, no shared owners.",
        hospice_count=12,
        percentile=99.5,
        county_median=1,
        costar={**EXEC_SUITE, "property_subtype": "Medical Office",
                "building_name": "Synthetic Medical Plaza",
                "rentable_building_area_sqft": 60000},
        ownership=NO_OWNER_SHARING,
        # clustering 100; medical ->0; 60000/12=5000>=1000 ->0; ownership ->0.
        # total 0.35*100 = 35 >= 35 -> worth a look; 1 strong.
        expected={"level": "worth_a_look", "total": 35.0, "strong": 1, "missing": [],
                  "case_written": True},
    ),
    ScoringScenario(
        "S04_single_registration",
        "One registration at a building with no CoStar match and no ownership links.",
        hospice_count=1,
        percentile=10,
        county_median=1,
        costar=None,
        ownership=NO_OWNER_SHARING,
        # clustering: 10<90 and 1 not > median 1 -> 0; ownership 0; CoStar indicators missing.
        expected={"level": "no_indicators_found", "total": 0.0, "strong": 0,
                  "missing": ["building_type_fit", "space_per_hospice"], "case_written": False},
    ),
    ScoringScenario(
        "S05_generic_office_moderate",
        "Moderate clustering in a generic office with moderate shared ownership.",
        hospice_count=6,
        percentile=96,
        county_median=1,
        costar={"property_id": "SYN-2002", "property_type": "Office",
                "property_subtype": "General", "building_name": "Synthetic Plaza",
                "rentable_building_area_sqft": 4000},
        ownership=OwnershipMetrics(max_hospices_per_owner=5, owners_shared_across_hospices=1),
        # 96>=95 ->80; generic office ->25; 4000/6=666.7<1000 ->45; owner 5>=5 ->65.
        # 28+6.25+9+13 = 56.25; strong = clustering, ownership = 2 -> worth a look.
        expected={"level": "worth_a_look", "total": 56.25, "strong": 2, "missing": [],
                  "case_written": True},
    ),
    ScoringScenario(
        "S06_costar_without_area",
        "Exact CoStar match whose record has no usable area measurement.",
        hospice_count=12,
        percentile=99.5,
        county_median=1,
        costar={**EXEC_SUITE, "rentable_building_area_sqft": None,
                "gross_building_area_sqft": None},
        ownership=HEAVY_OWNER_SHARING,
        # space_per_hospice unavailable; renormalize .35+.25+.20=.80, all 100 -> 100;
        # 3 strong -> high priority.
        expected={"level": "high_priority", "total": 100.0, "strong": 3,
                  "missing": ["space_per_hospice"], "case_written": True},
    ),
    ScoringScenario(
        "S10_synthetic_cross_source_fusion",
        "SYNTHETIC same-building CoStar + Vexcel fusion (no real building has both).",
        hospice_count=12,
        percentile=99.5,
        county_median=1,
        costar=EXEC_SUITE,
        ownership=HEAVY_OWNER_SHARING,
        aerial_review=AerialReview(
            reviewer="synthetic-reviewer",
            reviewed_at=RUN_AT,
            observations=("Synthetic: single-story commercial exterior.",),
            image_record_id="SYN-VEXCEL-0001",
        ),
        # aerial_context weight is 0: imagery is cited as context but must not move the
        # score. Expected identical to S01 (100, high priority, 4 strong), plus a vexcel
        # evidence record and no aerial-derived case finding.
        expected={"level": "high_priority", "total": 100.0, "strong": 4, "missing": [],
                  "case_written": True, "vexcel_evidence_present": True,
                  "aerial_changes_score": False, "aerial_case_finding": False},
    ),
)


def _score(scenario: ScoringScenario, building_id: str):
    indicators = IndicatorEngine().evaluate_building(
        building_id=building_id,
        hospice_count=scenario.hospice_count,
        percentile=scenario.percentile,
        county_median=scenario.county_median,
        costar=scenario.costar,
        ownership=scenario.ownership,
        aerial_review=scenario.aerial_review,
        run_at=RUN_AT,
    )
    return indicators, score_indicators(target_id=building_id, indicators=indicators)


def _evaluate_scoring(scenario: ScoringScenario) -> ScenarioResult:
    building_id = f"bldg_syn_{scenario.scenario_id.lower()}"
    indicators, decision = _score(scenario, building_id)
    building = BuildingAnalysisResponse.model_validate(
        {
            "building_id": building_id,
            "building_key": f"SYNTHETIC {scenario.scenario_id}",
            "hospice_count": scenario.hospice_count,
            "indicators": [indicator.model_dump(mode="json") for indicator in indicators],
            "priority": decision.to_dict(),
            "costar_match_status": "exact_match" if scenario.costar else "no_exact_match",
        }
    )
    case = investigate_building(building, run_at=RUN_AT)
    indicator_refs = {
        (evidence.source.value, evidence.record_id)
        for indicator in indicators
        for evidence in indicator.evidence
    }
    finding_refs = {
        (evidence.source.value, evidence.record_id)
        for finding in (case.case_file.findings if case.case_file else ())
        for evidence in finding.evidence
    }
    actual: dict[str, Any] = {
        "level": decision.score.level.value,
        "total": decision.score.total,
        "strong": len(decision.strong_indicators),
        "missing": sorted(decision.missing_indicators),
        "case_written": case.case_file is not None,
    }
    checks = {name: actual[name] == scenario.expected[name] for name in actual}
    # Provenance: every scored, nonzero indicator cites a source record, and every
    # case-file finding cites only evidence that an indicator actually produced.
    checks["scored_indicators_have_provenance"] = all(
        indicator.evidence
        for indicator in indicators
        if indicator.score_contribution > 0
    )
    checks["case_citations_traceable"] = finding_refs <= indicator_refs
    if case.case_file:
        checks["case_disclaimer_present"] = (
            "not conclusions of fraud" in case.case_file.disclaimer
        )
    if "vexcel_evidence_present" in scenario.expected:
        without_aerial = ScoringScenario(**{**asdict_shallow(scenario), "aerial_review": None})
        _, baseline = _score(without_aerial, building_id)
        actual["vexcel_evidence_present"] = any(
            source == "vexcel" for source, _ in indicator_refs
        )
        actual["aerial_changes_score"] = baseline.score.total != decision.score.total
        actual["aerial_case_finding"] = any(source == "vexcel" for source, _ in finding_refs)
        for name in ("vexcel_evidence_present", "aerial_changes_score", "aerial_case_finding"):
            checks[name] = actual[name] == scenario.expected[name]
    return ScenarioResult(
        scenario.scenario_id, scenario.description, DATA_LABEL, scenario.expected, actual, checks
    )


def asdict_shallow(scenario: ScoringScenario) -> dict[str, Any]:
    return {name: getattr(scenario, name) for name in scenario.__dataclass_fields__}


def _owner_masking() -> ScenarioResult:
    """S07: run the real ingestion -> ownership -> scoring -> case pipeline offline."""
    from eval.offline_demo import PRIVATE_FIXTURE_ID, PRIVATE_FIXTURE_NAME, run_offline_demo

    expected = {"private_name_in_artifacts": False, "private_owner_id_in_artifacts": False,
                "artifacts_written": True}
    with tempfile.TemporaryDirectory() as directory:
        run_offline_demo(directory)
        outputs = [
            path for path in Path(directory).rglob("*.json")
            if "fixtures" not in path.parts
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in outputs)
    actual = {
        "private_name_in_artifacts": PRIVATE_FIXTURE_NAME in text,
        "private_owner_id_in_artifacts": PRIVATE_FIXTURE_ID in text,
        "artifacts_written": bool(outputs),
    }
    return ScenarioResult(
        "S07_owner_masking",
        "A synthetic individual owner's name and ID never reach application artifacts.",
        DATA_LABEL, expected, actual, {k: actual[k] == expected[k] for k in expected},
    )


TRACE = [
    AgentToolTrace(
        tool_name="get_source_records",
        purpose="synthetic",
        input_identifiers={"target_id": "bldg_syn"},
        result_summary="synthetic",
        evidence_references=("derived:bldg_syn", "costar:SYN-1001"),
    )
]
ALLEGATIONS = (
    "This hospice is fraudulent. [derived:bldg_syn]",
    "The operator is committing hospice fraud [derived:bldg_syn].",
    "This looks like a fraud ring operating out of costar:SYN-1001.",
    "These are sham hospices registered at derived:bldg_syn.",
    "The records prove fraud [derived:bldg_syn].",
    "No hospice operates here [costar:SYN-1001].",
    "This is an illegal billing scheme [derived:bldg_syn].",
)
NEUTRAL = (
    "Registration concentration merits human review; this is not evidence of fraud and "
    "occupancy is unverified [derived:bldg_syn] [costar:SYN-1001]."
)


def _fraud_claims() -> ScenarioResult:
    """S08: unsupported allegations are rejected; a neutral cited summary is accepted."""
    expected = {"allegations_rejected": len(ALLEGATIONS), "neutral_summary_accepted": True}
    rejected = [text for text in ALLEGATIONS if _validated_agent_summary(text, TRACE) is None]
    actual = {
        "allegations_rejected": len(rejected),
        "neutral_summary_accepted": _validated_agent_summary(NEUTRAL, TRACE) is not None,
        "allegations_accepted": [t for t in ALLEGATIONS if t not in rejected],
    }
    return ScenarioResult(
        "S08_fraud_claims_rejected",
        "Model summaries that allege fraud fall back; neutral, cited language is allowed.",
        DATA_LABEL, expected, actual,
        {k: actual[k] == expected[k] for k in expected},
    )


def _citation_validation() -> ScenarioResult:
    """S09: summaries must cite only evidence references that tools actually returned."""
    cases = {
        "uncited": "Registration concentration merits review.",
        "fabricated_only": "Registration concentration merits review [costar:SYN-9999].",
        "real_plus_fabricated": (
            "Registration concentration merits review [derived:bldg_syn] [vexcel:abc123]."
        ),
    }
    expected = {name: "rejected" for name in cases} | {"all_real": "accepted"}
    actual = {
        name: "rejected" if _validated_agent_summary(text, TRACE) is None else "accepted"
        for name, text in cases.items()
    }
    actual["all_real"] = (
        "accepted"
        if _validated_agent_summary(
            "Merits review [derived:bldg_syn] [costar:SYN-1001].", TRACE
        )
        else "rejected"
    )
    return ScenarioResult(
        "S09_citation_validation",
        "Uncited or fabricated evidence references cause fallback.",
        DATA_LABEL, expected, actual, {k: actual[k] == expected[k] for k in expected},
    )


def run_scenarios() -> list[ScenarioResult]:
    scoring = {scenario.scenario_id: scenario for scenario in SCORING_SCENARIOS}
    runners: list[Callable[[], ScenarioResult]] = [
        *(lambda s=s: _evaluate_scoring(s) for s in scoring.values()),
        _owner_masking,
        _fraud_claims,
        _citation_validation,
    ]
    return sorted((runner() for runner in runners), key=lambda result: result.scenario_id)


def build_report(results: list[ScenarioResult]) -> dict[str, Any]:
    passed = sum(result.passed for result in results)
    return {
        "suite": "phantomcare-ten-scenario-v1",
        "data": DATA_LABEL,
        "disclaimer": DISCLAIMER,
        "generated_at": RUN_AT.isoformat(),
        "scenario_count": len(results),
        "scenarios_passed": passed,
        "check_count": sum(len(result.checks) for result in results),
        "checks_passed": sum(sum(result.checks.values()) for result in results),
        "metric_definition": (
            "scenarios_passed = scenarios whose every check equals its hand-derived expected "
            "value. checks_passed = individual expected-vs-actual comparisons that matched."
        ),
        "scenarios": [
            {**asdict(result), "passed": result.passed} for result in results
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ten synthetic evaluation scenarios.")
    parser.add_argument("--output", type=Path, default=Path("eval/scenario_results.json"))
    args = parser.parse_args()
    report = build_report(run_scenarios())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for scenario in report["scenarios"]:
        failed = [name for name, ok in scenario["checks"].items() if not ok]
        status = "PASS" if scenario["passed"] else f"FAIL {failed}"
        print(f"{scenario['scenario_id']:<36} {status}")
    print(
        f"{report['scenarios_passed']}/{report['scenario_count']} scenarios, "
        f"{report['checks_passed']}/{report['check_count']} checks (synthetic data)"
    )
    if report["scenarios_passed"] != report["scenario_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
