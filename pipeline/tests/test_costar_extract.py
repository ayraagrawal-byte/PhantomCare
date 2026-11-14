from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from pipeline.costar_extract import CostarExtract, CostarExtractError


def write_kit(root: Path) -> None:
    (root / "data").mkdir(parents=True)
    (root / "schemas").mkdir()
    property_record = {
        "id": 77,
        "propertyType": 5,
        "propertySubtype": 12,
        "buildingClass": 2,
        "buildingRating": 4,
        "grossBuildingAreaSquareFeet": 32000,
        "rentableBuildingAreaSquareFeet": 30000,
        "numStoriesAboveGrade": 3,
        "floors": [{"id": 1}, {"id": 2}, {"id": 3}],
        "primaryAddress": {
            "streetNumber": "14545",
            "streetName": "Friar",
            "streetType": "Street",
            "city": "Van Nuys",
            "state": "CA",
            "postcode": "91411-1234",
            "latitude": 34.187,
            "longitude": -118.45,
        },
    }
    (root / "data" / "commercial-property.jsonl").write_text(
        json.dumps(property_record) + "\n", encoding="utf-8"
    )
    occupancies = [
        {"id": 1, "propertyId": 77, "tenantLocationId": 10},
        {"id": 2, "propertyId": 77, "tenantLocationId": 10},
        {"id": 3, "propertyId": 77, "tenantLocationId": 11},
    ]
    (root / "data" / "location-occupancy.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in occupancies), encoding="utf-8"
    )
    pd.DataFrame(
        [
            {"PropertyId": "77", "MatterportModelId": "model-b"},
            {"PropertyId": "77", "MatterportModelId": "model-a"},
        ]
    ).to_csv(root / "commercial-properties.csv", index=False)
    (root / "schemas" / "enums.json").write_text(
        json.dumps(
            {
                "PropertyType": {"5": "Office"},
                "PropertySubtype": {"12": "Office_OfficeBuilding"},
                "BuildingClass": {"2": "B"},
            }
        ),
        encoding="utf-8",
    )


def test_costar_extract_matches_normalized_building_and_preserves_provenance(
    tmp_path: Path,
) -> None:
    write_kit(tmp_path)
    extract = CostarExtract(tmp_path)

    matches = extract.lookup("14545 FRIAR ST VAN NUYS CA 91411")

    assert len(matches) == 1
    match = matches[0]
    assert match["property_type"] == "Office"
    assert match["gross_building_area_sqft"] == 32000
    assert match["floor_count"] == 3
    assert match["occupancy_record_count"] == 3
    assert match["unique_tenant_location_count"] == 2
    assert match["matterport_model_ids"] == ["model-a", "model-b"]
    assert len(match["source"]["row_sha256"]) == 64
    assert "not a current tenant count" in match["occupancy_scope"]


def test_missing_kit_file_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(CostarExtractError, match="Required CoStar extract file"):
        CostarExtract(tmp_path)

