from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from api.analysis import (
    AnalysisRepository,
    analysis_summary,
    building_detail,
    list_buildings,
)
from api.app import app
from api.contracts import ReviewLevel


def _priority(building_id: str, total: float, level: str) -> dict[str, object]:
    return {
        "score": {
            "target_id": building_id,
            "total": total,
            "level": level,
            "model_version": "review-priority-v1",
            "components": [
                {
                    "indicator": "address_clustering",
                    "weight": 1,
                    "raw_score": total,
                    "weighted_score": total,
                }
            ],
        },
        "configured_weights": {"address_clustering": 1},
        "effective_weights": {"address_clustering": 1},
        "missing_indicators": [],
        "strong_indicators": ["address_clustering"] if total >= 60 else [],
        "claim_reason": "Fixture decision.",
    }


def _building(building_id: str, total: float, level: str) -> dict[str, object]:
    return {
        "building_id": building_id,
        "building_key": f"{building_id} TEST ST LOS ANGELES CA 90012",
        "hospice_count": 2,
        "indicators": [
            {
                "indicator": "address_clustering",
                "value": {"hospice_count": 2},
                "score_contribution": total,
                "evidence": [
                    {
                        "source": "derived",
                        "record_id": building_id,
                        "retrieved_at": "2026-11-14T00:00:00Z",
                        "fields": {"hospice_count": 2},
                    }
                ],
                "limitations": [],
            }
        ],
        "priority": _priority(building_id, total, level),
        "costar_match_status": "not_configured",
    }


def _artifacts(tmp_path: Path) -> AnalysisRepository:
    (tmp_path / "analysis_summary.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-11-14T00:00:00Z",
                "enrollment_count": 4,
                "building_count": 2,
                "high_priority_count": 1,
                "worth_a_look_count": 1,
                "disclaimer": "Screening aids, not findings of fraud.",
            }
        )
    )
    (tmp_path / "building_analysis.json").write_text(
        json.dumps(
            [
                _building("bldg_low", 40, "worth_a_look"),
                _building("bldg_high", 80, "high_priority"),
            ]
        )
    )
    return AnalysisRepository(tmp_path)


def test_analysis_endpoints_validate_sort_filter_and_detail(tmp_path: Path) -> None:
    repository = _artifacts(tmp_path)

    assert analysis_summary(repository).building_count == 2
    buildings = list_buildings(repository, level=None, limit=100)
    assert [item.building_id for item in buildings] == ["bldg_high", "bldg_low"]
    filtered = list_buildings(repository, level=ReviewLevel.HIGH_PRIORITY, limit=100)
    assert [item.building_id for item in filtered] == ["bldg_high"]
    detail = building_detail("bldg_high", repository)
    assert detail.priority.score.total == 80
    with pytest.raises(HTTPException) as caught:
        building_detail("missing", repository)
    assert caught.value.status_code == 404


def test_missing_or_invalid_artifacts_return_actionable_503(tmp_path: Path) -> None:
    repository = AnalysisRepository(tmp_path)

    with pytest.raises(HTTPException) as missing:
        analysis_summary(repository)
    assert missing.value.status_code == 503
    assert missing.value.detail["code"] == "analysis_unavailable"
    (tmp_path / "building_analysis.json").write_text('{"not": "a list"}')
    with pytest.raises(HTTPException) as invalid:
        list_buildings(repository, level=None, limit=100)
    assert invalid.value.status_code == 503
    assert "failed validation" in invalid.value.detail["message"]


def test_analysis_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"])
    assert {
        "/analysis/summary",
        "/analysis/buildings",
        "/analysis/buildings/{building_id}",
    } <= paths
