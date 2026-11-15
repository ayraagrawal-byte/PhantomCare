from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from api.analysis import (
    AnalysisRepository,
    analysis_summary,
    building_aerial,
    building_aerial_image,
    building_detail,
    building_network,
    list_buildings,
)
from api.app import app
from api.contracts import ReviewLevel
from api.contracts.geocodes import CAMS_LAYER


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
        "building_context": (
            {
                "property_id": "77",
                "building_name": "Review Executive Suites",
                "property_type": "Office",
                "property_subtype": "Office Building",
                "building_class": "B",
                "gross_building_area_sqft": 32000,
                "rentable_building_area_sqft": 30000,
                "stories_above_grade": 3,
                "floor_count": 3,
                "occupancy_record_count": 4,
                "unique_tenant_location_count": 3,
                "occupancy_scope": "current_or_past_records; not a current tenant count",
                "matterport_model_ids": ["model-1"],
            }
            if building_id == "bldg_high"
            else None
        ),
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
    image = b"\xff\xd8\xfffixture"
    (tmp_path / "vexcel").mkdir()
    (tmp_path / "vexcel" / "bldg_high.jpg").write_bytes(image)
    (tmp_path / "vexcel_evidence.json").write_text(
        json.dumps(
            [
                {
                    "target_id": "bldg_high",
                    "address": "100 TEST ST",
                    "latitude": 34.0522,
                    "longitude": -118.2437,
                    "provider": "vexcel",
                    "kind": "ortho",
                    "retrieved_at": "2026-11-14T00:00:00Z",
                    "image_filename": "bldg_high.jpg",
                    "image_sha256": hashlib.sha256(image).hexdigest(),
                    "limitations": ["Context only."],
                }
            ]
        )
    )
    return AnalysisRepository(tmp_path)


def test_analysis_endpoints_validate_sort_filter_and_detail(tmp_path: Path) -> None:
    repository = _artifacts(tmp_path)

    assert analysis_summary(repository).building_count == 2
    buildings = list_buildings(repository, level=None, limit=100)
    assert [item.building_id for item in buildings] == ["bldg_high", "bldg_low"]
    assert list_buildings(repository, limit=1, offset=1) == [buildings[1]]
    filtered = list_buildings(repository, level=ReviewLevel.HIGH_PRIORITY, limit=100)
    assert [item.building_id for item in filtered] == ["bldg_high"]
    detail = building_detail("bldg_high", repository)
    assert detail.priority.score.total == 80
    assert buildings[0].latitude == 34.0522
    assert detail.building_context is not None
    assert detail.building_context.rentable_building_area_sqft == 30000
    network = building_network("bldg_high", repository)
    assert [node.kind for node in network.nodes] == ["building", "owner", "hospice"]
    assert network.nodes[1].is_masked is True
    aerial = building_aerial("bldg_high", repository)
    assert aerial.provider == "vexcel"
    assert str(building_aerial_image("bldg_high", repository).path).endswith("bldg_high.jpg")
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


def test_list_uses_aerial_center_only_for_a_matching_address(tmp_path: Path) -> None:
    repository = _artifacts(tmp_path)
    manifest = tmp_path / "vexcel_evidence.json"
    evidence = json.loads(manifest.read_text())[0]
    evidence["target_id"] = "bldg_low"
    manifest.write_text(json.dumps([evidence]))
    assert list_buildings(repository, limit=100)[1].latitude is None

    evidence["address"] = "bldg_low TEST ST LOS ANGELES CA 90012"
    manifest.write_text(json.dumps([evidence]))
    item = list_buildings(repository, limit=100)[1]
    assert (item.latitude, item.longitude) == (34.0522, -118.2437)
    assert item.coordinate_source == "Vexcel imagery address center"
    assert item.costar_match_status == "not_configured"
    assert building_detail("bldg_low", repository).latitude is None

    manifest.write_text(json.dumps([evidence, evidence]))
    assert list_buildings(repository, limit=100)[1].latitude is None


def test_cached_cams_locations_override_legacy_points_and_match_current_address(tmp_path: Path):
    repository = _artifacts(tmp_path)
    before = list_buildings(repository, limit=100)
    cache = {
        "schema_version": 1,
        "source_url": CAMS_LAYER,
        "retrieved_at": "2026-11-14T00:00:00Z",
        "results": {
            "bldg_high": {
                "building_key": before[0].building_key,
                "reason": "ambiguous_points",
            },
            "bldg_low": {
                "building_key": before[1].building_key,
                "location": {
                    "feature_id": 42,
                    "county_record_source": "LA City",
                    "matched_address": "100 Test St Los Angeles 90012",
                    "confidence": "exact",
                    "latitude": 34.05,
                    "longitude": -118.25,
                },
            },
        },
    }
    path = tmp_path / "cams_geocodes.json"
    path.write_text(json.dumps(cache))
    assert analysis_summary(repository).cams_mapped_count == 1
    high, low = list_buildings(repository, limit=100)
    assert high.latitude is None and high.longitude is None
    assert low.verified_location.feature_id == 42
    assert low.verified_location.precision == "address_point"
    assert (low.latitude, low.longitude) == (34.05, -118.25)
    assert low.coordinate_source == "LA County CAMS"
    assert [high.total_score, low.total_score] == [item.total_score for item in before]

    cache["results"]["bldg_low"]["building_key"] = "Old address"
    path.write_text(json.dumps(cache))
    assert list_buildings(repository, limit=100)[1].verified_location is None


def test_runtime_supplemental_points_preserve_original_verified_coordinates():
    repository = AnalysisRepository(Path("data/runtime"))
    original = repository.cams_locations()
    supplemental = repository.supplemental_locations(original)
    assert len(supplemental) == 140
    summary = analysis_summary(repository)
    rows = {row.building_id: row for row in list_buildings(repository, limit=500)}
    assert len(rows) == summary.building_count == 468
    preserved = 0
    for key, result in original.items():
        row = rows[key]
        if result.location:
            assert row.verified_location == result.location
            assert row.approximate_location is None
            assert (row.latitude, row.longitude) == (
                result.location.latitude,
                result.location.longitude,
            )
            preserved += 1
        elif automatic := supplemental[key].anchor:
            outcome = supplemental[key]
            expected = outcome.verified or automatic
            assert (row.latitude, row.longitude) == (expected.latitude, expected.longitude)
    assert preserved == 328
    reviewed = repository.reviewed_locations(supplemental)
    assert len(reviewed) == 23
    for key, point in reviewed.items():
        assert supplemental[key].anchor is None
        assert (rows[key].latitude, rows[key].longitude) == (point.latitude, point.longitude)
        assert (rows[key].verified_location or rows[key].approximate_location) == point
    assert sum(row.latitude is None for row in rows.values()) == 1
    verified_count = sum(row.verified_location is not None for row in rows.values())
    assert verified_count == summary.cams_mapped_count
    approximate = [row for row in rows.values() if row.approximate_location]
    assert len(approximate) == summary.approximate_mapped_count > 0
    for row in approximate:
        assert row.verified_location is None
        assert row.coordinate_source == row.approximate_location.source
        assert (row.latitude, row.longitude) == (
            row.approximate_location.latitude,
            row.approximate_location.longitude,
        )


def test_analysis_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"])
    assert {
        "/analysis/summary",
        "/analysis/buildings",
        "/analysis/buildings/{building_id}",
        "/analysis/buildings/{building_id}/network",
        "/analysis/buildings/{building_id}/aerial",
        "/analysis/buildings/{building_id}/aerial/image",
    } <= paths
