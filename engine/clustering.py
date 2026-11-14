from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

REQUIRED_BUILDING_COLUMNS = {"BUILDING_ID", "BUILDING_KEY", "HOSPICE_COUNT"}
REQUIRED_ENROLLMENT_COLUMNS = {"ENROLLMENT_ID", "BUILDING_KEY"}


class ClusteringError(ValueError):
    """Raised when clustering inputs cannot produce a trustworthy baseline."""


def _require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ClusteringError(f"{label} is missing required columns: {', '.join(missing)}")


def reconcile_building_counts(buildings: pd.DataFrame, enrollments: pd.DataFrame) -> None:
    _require_columns(buildings, REQUIRED_BUILDING_COLUMNS, "buildings")
    _require_columns(enrollments, REQUIRED_ENROLLMENT_COLUMNS, "enrollments")

    expected = (
        enrollments.groupby("BUILDING_KEY")["ENROLLMENT_ID"]
        .nunique()
        .rename("EXPECTED_HOSPICE_COUNT")
    )
    observed = buildings.set_index("BUILDING_KEY")["HOSPICE_COUNT"].astype(int)
    comparison = pd.concat([expected, observed.rename("OBSERVED_HOSPICE_COUNT")], axis=1)
    comparison = comparison.fillna(-1).astype(int)
    mismatches = comparison.loc[
        comparison["EXPECTED_HOSPICE_COUNT"] != comparison["OBSERVED_HOSPICE_COUNT"]
    ]
    if not mismatches.empty:
        examples = "; ".join(
            f"{key}: expected {row.EXPECTED_HOSPICE_COUNT}, "
            f"observed {row.OBSERVED_HOSPICE_COUNT}"
            for key, row in mismatches.head(5).iterrows()
        )
        raise ClusteringError(f"building counts do not reconcile: {examples}")


def _empirical_percentile(counts: pd.Series) -> pd.Series:
    frequencies = counts.value_counts().sort_index()
    cumulative = frequencies.cumsum().div(len(counts)).mul(100)
    return counts.map(cumulative).astype(float)


def _optional_home_health_counts(home_health: pd.DataFrame | None) -> pd.Series:
    if home_health is None:
        return pd.Series(dtype="int64", name="HOME_HEALTH_COUNT")
    required = {"BUILDING_KEY", "AGENCY_ID"}
    _require_columns(home_health, required, "home health agencies")
    return (
        home_health.groupby("BUILDING_KEY")["AGENCY_ID"]
        .nunique()
        .rename("HOME_HEALTH_COUNT")
    )


def calculate_clustering_baseline(
    buildings: pd.DataFrame,
    enrollments: pd.DataFrame,
    *,
    home_health: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if buildings.empty:
        raise ClusteringError("cannot calculate a baseline from an empty building dataset")
    reconcile_building_counts(buildings, enrollments)

    result = buildings.copy()
    result["HOSPICE_COUNT"] = pd.to_numeric(result["HOSPICE_COUNT"], errors="raise").astype(int)
    median = float(result["HOSPICE_COUNT"].median())
    result["LA_MEDIAN_HOSPICES_PER_BUILDING"] = median
    result["HOSPICE_COUNT_PERCENTILE"] = _empirical_percentile(result["HOSPICE_COUNT"])
    result["HOSPICE_COUNT_RANK"] = (
        result["HOSPICE_COUNT"].rank(method="min", ascending=False).astype(int)
    )
    result["ABOVE_MEDIAN_COUNT"] = (result["HOSPICE_COUNT"] - median).clip(lower=0)
    result["COUNT_TO_MEDIAN_RATIO"] = (
        result["HOSPICE_COUNT"] / median if median > 0 else 0.0
    )

    home_health_counts = _optional_home_health_counts(home_health)
    result = result.merge(
        home_health_counts,
        how="left",
        left_on="BUILDING_KEY",
        right_index=True,
    )
    result["HOME_HEALTH_COUNT"] = result["HOME_HEALTH_COUNT"].fillna(0).astype(int)
    result["TOTAL_AGENCY_COUNT"] = result["HOSPICE_COUNT"] + result["HOME_HEALTH_COUNT"]

    return result.sort_values(
        ["HOSPICE_COUNT", "TOTAL_AGENCY_COUNT", "BUILDING_KEY"],
        ascending=[False, False, True],
        kind="stable",
    ).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calculate LA County hospice clustering baselines and ranks."
    )
    parser.add_argument("--buildings", type=Path, required=True)
    parser.add_argument("--enrollments", type=Path, required=True)
    parser.add_argument("--home-health", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    buildings = pd.read_csv(args.buildings, dtype={"BUILDING_KEY": str})
    enrollments = pd.read_csv(args.enrollments, dtype=str, keep_default_na=False)
    home_health = (
        pd.read_csv(args.home_health, dtype=str, keep_default_na=False)
        if args.home_health
        else None
    )
    ranked = calculate_clustering_baseline(
        buildings,
        enrollments,
        home_health=home_health,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ranked.to_csv(args.output, index=False)


if __name__ == "__main__":
    main()

