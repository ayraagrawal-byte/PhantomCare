from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from api.app import app
from api.cases import CaseRepository, case_detail, case_for_target, list_cases


def result(*, target_id: str = "bldg_1", stopped: bool = False) -> dict[str, object]:
    case_id = f"case_{target_id}"
    evidence = {
        "source": "derived",
        "record_id": target_id,
        "retrieved_at": "2026-11-14T00:00:00Z",
        "fields": {"hospice_count": 8},
    }
    case_file = None
    if not stopped:
        case_file = {
            "case_id": case_id,
            "target_id": target_id,
            "created_at": "2026-11-14T00:00:00Z",
            "score": {
                "target_id": target_id,
                "total": 80,
                "level": "high_priority",
                "model_version": "review-priority-v1",
                "components": [
                    {
                        "indicator": "address_clustering",
                        "weight": 1,
                        "raw_score": 80,
                        "weighted_score": 80,
                    }
                ],
            },
            "findings": [
                {
                    "title": "Elevated address clustering",
                    "summary": "Registration count is elevated relative to the baseline.",
                    "strength": 0.7,
                    "evidence": [evidence],
                    "limitations": ["This may occur in legitimate organizations."],
                }
            ],
        }
    return {
        "target_id": target_id,
        "case_file": case_file,
        "trace": [
            {
                "event_id": f"event_{target_id}",
                "case_id": case_id,
                "occurred_at": "2026-11-14T00:00:00Z",
                "event_type": "early_stopped" if stopped else "case_written",
                "message": "Stopped early." if stopped else "Case written.",
                "evidence": [] if stopped else [evidence],
            }
        ],
        "stopped_reason": "Insufficient evidence." if stopped else None,
    }


def repository(tmp_path: Path) -> CaseRepository:
    (tmp_path / "investigation_cases.json").write_text(
        json.dumps([result(target_id="bldg_1"), result(target_id="bldg_2", stopped=True)])
    )
    return CaseRepository(tmp_path)


def test_lists_completed_cases_and_returns_target_results(tmp_path: Path) -> None:
    repo = repository(tmp_path)

    cases = list_cases(repo, limit=100)
    assert len(cases) == 1
    assert cases[0].case_id == "case_bldg_1"
    assert cases[0].finding_count == 1
    assert case_detail("case_bldg_1", repo).target_id == "bldg_1"
    stopped = case_for_target("bldg_2", repo)
    assert stopped.case_file is None
    assert stopped.stopped_reason == "Insufficient evidence."


def test_missing_target_and_artifacts_return_structured_errors(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    with pytest.raises(HTTPException) as missing:
        case_for_target("unknown", repo)
    assert missing.value.status_code == 404

    unavailable = CaseRepository(tmp_path / "missing")
    with pytest.raises(HTTPException) as absent:
        list_cases(unavailable, limit=100)
    assert absent.value.status_code == 503
    assert absent.value.detail["code"] == "cases_unavailable"


def test_case_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"])
    assert {"/cases", "/cases/{case_id}", "/cases/targets/{target_id}"} <= paths
