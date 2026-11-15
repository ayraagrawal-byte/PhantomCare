import json
from pathlib import Path

from eval.scenarios import build_report, run_scenarios


def test_ten_synthetic_scenarios_pass_and_are_labeled() -> None:
    report = build_report(run_scenarios())

    assert report["scenario_count"] == 10
    assert report["scenarios_passed"] == 10, [
        (s["scenario_id"], s["actual"]) for s in report["scenarios"] if not s["passed"]
    ]
    assert report["data"] == "synthetic"
    assert "not a measure of real-world" in report["disclaimer"]
    assert all(scenario["data"] == "synthetic" for scenario in report["scenarios"])


def test_missing_costar_cannot_reach_high_priority() -> None:
    result = next(r for r in run_scenarios() if r.scenario_id == "S02_missing_costar")

    assert result.actual["missing"] == ["building_type_fit", "space_per_hospice"]
    assert result.actual["level"] == "worth_a_look"


def test_scenario_suite_is_deterministic_and_committed_report_is_current() -> None:
    first = build_report(run_scenarios())
    assert first == build_report(run_scenarios())
    committed = json.loads(Path("eval/scenario_results.json").read_text(encoding="utf-8"))
    assert committed == first
