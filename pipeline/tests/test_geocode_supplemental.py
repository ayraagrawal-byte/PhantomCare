from pipeline.geocode_supplemental import census_anchor, corroborate, nearby_features

ADDRESS = "100 W TEST ST LOS ANGELES CA 90012"


def census(*, address="100 W TEST ST, LOS ANGELES, CA, 90012", county="06037"):
    return {
        "matchedAddress": address,
        "geographies": {"Counties": [{"GEOID": county}]},
        "coordinates": {"x": -118.25, "y": 34.05},
        "tigerLine": {"tigerLineId": "1234"},
    }


def point(object_id=1, *, latitude=34.0505, **fields):
    return {
        "attributes": {
            "OBJECTID": object_id,
            "ZipCode": "90012",
            "Number": "100",
            "FullName": "West Test Street",
            "FullAddress": "100 W Test St Los Angeles 90012",
            "Source": "LA City",
            **fields,
        },
        "geometry": {"x": -118.25, "y": latitude},
    }


def test_unique_compatible_point_inside_radius_is_verified():
    anchor = census_anchor(ADDRESS, [census()])
    match = point()
    wrong_street = point(2, FullName="W Other St")
    wrong_house = point(3, Number="101")
    wrong_zip = point(4, ZipCode="90013")
    candidates = [match, wrong_street, wrong_house, wrong_zip]
    outcome = corroborate(ADDRESS, anchor, candidates, candidates)
    assert outcome.verified.feature_id == 1
    assert outcome.verified.latitude == match["geometry"]["y"]
    assert 55 < outcome.verified_distance_meters < 56
    assert outcome.nearby_matching_feature_ids == [1]


def test_proximity_alone_cannot_verify_wrong_addresses_or_unresolved_units():
    anchor = census_anchor(ADDRESS, [census()])
    unverified_candidates = [
        point(1, FullName="East Test Street"),
        point(2, latitude=34.051, FullName="West Test Street"),
        point(3, UnitName="A"),
    ]
    for candidate in unverified_candidates:
        outcome = corroborate(ADDRESS, anchor, [candidate], [candidate])
        assert outcome.verified is None
        assert outcome.anchor.precision == "street_interpolation"


def test_competing_points_remain_approximate_even_if_one_is_closer():
    anchor = census_anchor(ADDRESS, [census()])
    candidates = [point(1), point(2, latitude=34.0502)]
    outcome = corroborate(ADDRESS, anchor, candidates, candidates)
    assert outcome.verified is None
    assert outcome.nearby_matching_feature_ids == [1, 2]
    assert outcome.reason == "unit_or_conflicting_points"


def test_civic_only_requires_independent_county_evidence_and_stays_approximate():
    address = ADDRESS.replace("ST LOS", "ST 103 LOS")
    anchor = census_anchor(address, [census()])
    assert anchor.address_basis == "civic_address_only"
    assert corroborate(address, anchor, [], []).anchor is None
    result = corroborate(address, anchor, [point()], [point()])
    assert result.anchor is not None and result.verified is None
    assert census_anchor(address, [census(), census()]) is None
    assert census_anchor(ADDRESS.replace("100 ", "101 "), [census()]) is None


def test_neighboring_county_anchor_is_labeled_and_cannot_be_cams_verified():
    anchor = census_anchor(ADDRESS, [census(county="06111")])
    assert anchor.county == "Ventura"
    outcome = corroborate(ADDRESS, anchor, [point()], [point()])
    assert outcome.anchor is not None and outcome.verified is None


def test_county_radius_search_uses_meters_and_wgs84(monkeypatch):
    def query(params):
        assert params["distance"] == 100
        assert params["units"] == "esriSRUnit_Meter"
        assert params["inSR"] == params["outSR"] == 4326
        assert params["geometry"] == "-118.25,34.05"
        return {"features": [point()], "spatialReference": {"wkid": 4326}}

    monkeypatch.setattr("pipeline.geocode_supplemental.query_page", query)
    anchor = census_anchor(ADDRESS, [census()])
    assert nearby_features(anchor, ("90012", "100")) == [point()]
