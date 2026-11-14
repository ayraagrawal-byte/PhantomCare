from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from api.analysis import (
    AnalysisRepository,
    analysis_summary,
    building_detail,
    building_network,
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
        "latitude": 34.0522 if building_id == "bldg_high" else None,
        "longitude": -118.2437 if building_id == "bldg_high" else None,
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
    (tmp_path / "ownership_network.json").write_text(
        json.dumps(
            {
                "owners": [
                    {
                        "owner_key": "owner_masked",
                        "display_name": "Individual owner abc123",
                        "owner_type": "individual",
                        "is_masked": True,
                        "hospice_count": 2,
                    }
                ],
                "edges": [
                    {
                        "owner_key": "owner_masked",
                        "enrollment_id": "E-1",
                        "ownership_percent": 50,
                        "source_row_hash": "row",
                    }
                ],
                "buildings": [
                    {"building_id": "bldg_high", "metrics": {}, "owner_keys": ["owner_masked"]}
                ],
                "limitations": ["Context only.", "Does not establish fraud."],
            }
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
    assert buildings[0].latitude == 34.0522
    network = building_network("bldg_high", repository)
    assert [node.kind for node in network.nodes] == ["building", "owner", "hospice"]
    assert network.nodes[1].is_masked is True
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
        "/analysis/buildings/{building_id}/network",
    } <= paths
