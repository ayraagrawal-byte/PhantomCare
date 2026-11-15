import pytest

from pipeline.geocode_cams import fetch_candidates, match_address

ADDRESS = "12444 VICTORY BLVD N HOLLYWOOD CA 91606"
POINT = {"x": -118.40455077456429, "y": 34.186449947793363}


def candidate(*, geometry=POINT, **fields):
    return {
        "attributes": {
            "OBJECTID": 1953945,
            "ZipCode": "91606",
            "Number": "12444",
            "NumberSuffix": "12444",
            "FullName": "Victory Blvd",
            "FullAddress": "12444 Victory Blvd North Hollywood 91606",
            "PostComm1": "North Hollywood",
            "LegalComm": "Los Angeles",
            "Source": "LA City",
            **fields,
        },
        "geometry": geometry,
    }


def test_exact_address_preserves_official_geometry_and_provenance():
    result = match_address("12444 Victory Blvd North Hollywood CA 91606", [candidate()])
    location = result.location
    assert location is not None
    assert location.confidence == "exact"
    assert location.precision == "address_point"
    assert location.feature_id == 1953945
    assert location.source == "LA County CAMS"
    assert location.county_record_source == "LA City"
    assert location.latitude == POINT["y"]
    assert location.longitude == POINT["x"]


def test_standardizes_directional_postal_and_suffix_spellings():
    assert match_address(ADDRESS, [candidate()]).location.confidence == "standardized"
    feature = candidate(
        FullName="Victory Wy", FullAddress="12444 Victory Wy North Hollywood 91606"
    )
    result = match_address(ADDRESS.replace("BLVD", "WAY"), [feature])
    assert result.location.confidence == "standardized"


@pytest.mark.parametrize(
    ("key", "feature", "reason"),
    [
        (ADDRESS, candidate(ZipCode="91605"), "no_address_match"),
        (ADDRESS, candidate(NumberSuffix="12444A"), "no_address_match"),
        (ADDRESS, candidate(FullName="W Victory Blvd"), "no_address_match"),
        (ADDRESS.replace("N HOLLYWOOD", "BURBANK"), candidate(), "community_mismatch"),
        (ADDRESS.replace("BLVD", "BLVD 100"), candidate(), "community_mismatch"),
        (ADDRESS, candidate(UnitName="100"), "unit_records_only"),
        (ADDRESS, candidate(geometry=None), "invalid_geometry"),
        (ADDRESS, candidate(geometry={"x": 34.18, "y": -118.4}), "invalid_geometry"),
        (ADDRESS, candidate(geometry={"x": float("inf"), "y": 34.18}), "invalid_geometry"),
        ("PO BOX 14 LOS ANGELES CA 90012", candidate(), "unsupported_address"),
    ],
)
def test_rejects_unverified_addresses_and_geometry(key, feature, reason):
    result = match_address(key, [feature])
    assert result.location is None
    assert result.reason == reason


def test_ambiguity_requires_coincident_points_and_prefers_literal_record():
    exact = candidate(OBJECTID=200, FullAddress="12444 Victory Blvd N Hollywood 91606")
    alias = candidate(OBJECTID=100)
    assert match_address(ADDRESS, [alias, exact]).location.feature_id == 200
    conflicting = candidate(OBJECTID=100, geometry={**POINT, "x": -118.405})
    result = match_address(ADDRESS, [conflicting, exact])
    assert result.location is None
    assert result.reason == "ambiguous_points"


def test_batched_query_requests_wgs84_and_consumes_all_pages(monkeypatch):
    offsets = []

    def page(params):
        offset = params["resultOffset"]
        offsets.append(offset)
        assert params["outSR"] == 4326
        assert "ZipCode = '91606' AND Number IN ('12444')" in params["where"]
        return {
            "features": [candidate(OBJECTID=offset + 100)],
            "spatialReference": {"wkid": 4326},
            "exceededTransferLimit": offset == 0,
        }

    monkeypatch.setattr("pipeline.geocode_cams.query_page", page)
    assert len(list(fetch_candidates({("91606", "12444")}))) == 2
    assert offsets == [0, 1]
