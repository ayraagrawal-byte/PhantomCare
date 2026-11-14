from datetime import UTC, datetime

import pytest

from engine.indicators import AerialReview, IndicatorEngine, OwnershipMetrics

NOW = datetime(2026, 11, 13, 22, 0, tzinfo=UTC)


def costar_record(**overrides):
    record = {
        "property_id": 77,
        "property_type": "Office",
        "property_subtype": "Office_OfficeBuilding",
        "building_name": "Van Nuys Executive Suites",
        "gross_building_area_sqft": 32000,
        "rentable_building_area_sqft": 30000,
        "source": {"line_number": 4, "row_sha256": "a" * 64},
    }
    record.update(overrides)
    return record


def test_clustering_uses_empirical_percentile_thresholds() -> None:
    result = IndicatorEngine().address_clustering(
        building_id="B-1",
        hospice_count=46,
        percentile=99.4,
        county_median=1,
        run_at=NOW,
    )

    assert result.score_contribution == 100
    assert result.evidence[0].source.value == "derived"
    assert "does not show" in result.limitations[0]


def test_executive_suite_context_is_flagged_but_limited() -> None:
    result = IndicatorEngine().building_type_fit(
        building_id="B-1", costar=costar_record(), run_at=NOW
    )

    assert result.score_contribution == 100
    assert result.value["classification"] == "executive_suite_or_virtual_office_context"
    assert "not the legitimacy" in result.limitations[0]


def test_medical_context_is_not_flagged() -> None:
    result = IndicatorEngine().building_type_fit(
        building_id="B-1",
        costar=costar_record(
            property_type="Healthcare",
            property_subtype="Medical Office",
            building_name="Medical Plaza",
        ),
        run_at=NOW,
    )
    assert result.score_contribution == 0


def test_space_per_hospice_prefers_rentable_area() -> None:
    result = IndicatorEngine().space_per_hospice(
        building_id="B-1",
        hospice_count=100,
        costar=costar_record(),
        run_at=NOW,
    )

    assert result.value["area_basis"] == "rentable_building_area_sqft"
    assert result.value["space_per_hospice_sqft"] == 300
    assert result.score_contribution == 75
    assert len(result.evidence) == 2


def test_missing_costar_data_produces_limitations_not_guesses() -> None:
    results = IndicatorEngine().evaluate_building(
        building_id="B-1",
        hospice_count=2,
        percentile=75,
        county_median=1,
        costar=None,
        run_at=NOW,
    )
    by_name = {result.indicator: result for result in results}

    assert by_name["building_type_fit"].score_contribution == 0
    assert by_name["space_per_hospice"].score_contribution == 0
    assert by_name["building_type_fit"].evidence == ()


def test_ownership_metrics_are_scored_without_names() -> None:
    result = IndicatorEngine().ownership_network(
        building_id="B-1",
        metrics=OwnershipMetrics(
            max_hospices_per_owner=12,
            owners_shared_across_hospices=3,
            shared_owner_address_count=2,
        ),
        run_at=NOW,
    )

    assert result.score_contribution == 100
    assert "name" not in str(result.value).lower()
    assert "legitimate" in result.limitations[0]


def test_aerial_review_is_context_only_and_never_scores() -> None:
    result = IndicatorEngine().aerial_context(
        review=AerialReview(
            reviewer="Reviewer A",
            reviewed_at=NOW,
            observations=("Generic surface parking visible",),
            image_record_id="vexcel-1",
        )
    )

    assert result.score_contribution == 0
    assert result.evidence[0].source.value == "vexcel"
    assert "never scored" in result.limitations[0]


def test_zero_hospice_count_is_rejected_for_ratio() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        IndicatorEngine().space_per_hospice(
            building_id="B-1",
            hospice_count=0,
            costar=costar_record(),
            run_at=NOW,
        )

