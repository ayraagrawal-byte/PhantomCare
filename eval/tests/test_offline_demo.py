from __future__ import annotations

import json
from pathlib import Path

from eval.offline_demo import HOTSPOT_ADDRESS, run_offline_demo


def test_offline_demo_runs_real_pipeline_and_passes_guardrails(tmp_path: Path) -> None:
    report = run_offline_demo(tmp_path)

    assert report.passed is True
    assert report.status == "passed"
    assert report.building_count == 3
    assert report.high_priority_count == 1
    assert report.completed_case_count == 1
    assert report.early_stop_count == 2
    assert report.private_owner_data_absent is True

    buildings = json.loads((tmp_path / "building_analysis.json").read_text())
    hotspot = next(item for item in buildings if item["building_key"] == HOTSPOT_ADDRESS)
    assert hotspot["priority"]["score"]["level"] == "high_priority"
    assert hotspot["costar_match_status"] == "exact_match"
    assert (tmp_path / "investigation_cases.json").exists()
    assert json.loads((tmp_path / "evaluation_results.json").read_text())["status"] == "passed"
