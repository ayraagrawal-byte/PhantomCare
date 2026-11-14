from __future__ import annotations

import pandas as pd
import pytest

from engine.clustering import (
    ClusteringError,
    calculate_clustering_baseline,
    reconcile_building_counts,
)


def buildings() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"BUILDING_ID": "B-1", "BUILDING_KEY": "100 MAIN ST", "HOSPICE_COUNT": 1},
            {"BUILDING_ID": "B-2", "BUILDING_KEY": "200 MAIN ST", "HOSPICE_COUNT": 1},
            {"BUILDING_ID": "B-3", "BUILDING_KEY": "300 MAIN ST", "HOSPICE_COUNT": 2},
            {"BUILDING_ID": "B-4", "BUILDING_KEY": "400 MAIN ST", "HOSPICE_COUNT": 5},
        ]
    )


def enrollments() -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    counts = {"100 MAIN ST": 1, "200 MAIN ST": 1, "300 MAIN ST": 2, "400 MAIN ST": 5}
    sequence = 0
    for building_key, count in counts.items():
        for _ in range(count):
            sequence += 1
            rows.append({"ENROLLMENT_ID": f"E-{sequence}", "BUILDING_KEY": building_key})
    return pd.DataFrame(rows)


def test_baseline_calculates_median_percentiles_and_stable_ranks() -> None:
    ranked = calculate_clustering_baseline(buildings(), enrollments())

    assert ranked["BUILDING_ID"].tolist() == ["B-4", "B-3", "B-1", "B-2"]
    assert ranked["LA_MEDIAN_HOSPICES_PER_BUILDING"].unique().tolist() == [1.5]
    assert ranked.set_index("BUILDING_ID").loc["B-4", "HOSPICE_COUNT_PERCENTILE"] == 100
    assert ranked.set_index("BUILDING_ID").loc["B-1", "HOSPICE_COUNT_PERCENTILE"] == 50
    assert ranked.set_index("BUILDING_ID").loc["B-1", "HOSPICE_COUNT_RANK"] == 3
    assert ranked.set_index("BUILDING_ID").loc["B-2", "HOSPICE_COUNT_RANK"] == 3


def test_home_health_counts_are_optional_and_separate() -> None:
    home_health = pd.DataFrame(
        [
            {"AGENCY_ID": "H-1", "BUILDING_KEY": "100 MAIN ST"},
            {"AGENCY_ID": "H-2", "BUILDING_KEY": "100 MAIN ST"},
            {"AGENCY_ID": "H-2", "BUILDING_KEY": "100 MAIN ST"},
        ]
    )

    ranked = calculate_clustering_baseline(
        buildings(),
        enrollments(),
        home_health=home_health,
    ).set_index("BUILDING_ID")

    assert ranked.loc["B-1", "HOME_HEALTH_COUNT"] == 2
    assert ranked.loc["B-1", "TOTAL_AGENCY_COUNT"] == 3
    assert ranked.loc["B-4", "HOME_HEALTH_COUNT"] == 0


def test_reconciliation_rejects_stale_building_counts() -> None:
    stale = buildings()
    stale.loc[stale["BUILDING_ID"] == "B-4", "HOSPICE_COUNT"] = 4

    with pytest.raises(ClusteringError, match="do not reconcile"):
        reconcile_building_counts(stale, enrollments())


def test_empty_dataset_cannot_create_baseline() -> None:
    with pytest.raises(ClusteringError, match="empty building dataset"):
        calculate_clustering_baseline(
            pd.DataFrame(columns=list(buildings().columns)),
            pd.DataFrame(columns=list(enrollments().columns)),
        )

